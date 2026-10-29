#include <Arduino.h>
#include <BLE2902.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

#include "cloud_config.h"

namespace {

constexpr char kServiceUuid[] = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
constexpr char kRxUuid[] = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";
constexpr char kStatusUuid[] = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";
constexpr uint32_t kWifiRetryMs = 10000;
constexpr uint32_t kCommandPollMs = 5000;

Preferences preferences;
BLEServer *bleServer = nullptr;
BLECharacteristic *statusCharacteristic = nullptr;
bool bleConnected = false;
bool wifiReady = false;
bool wifiProvisioningRequested = false;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastUploadMs = 0;
uint32_t lastCommandPollMs = 0;
uint32_t uploadIntervalMs = 5000;

String ssid;
String wifiPassword;
String deviceId;
String uploadToken;

String jsonEscape(const String &value) {
  String escaped;
  escaped.reserve(value.length() + 8);
  for (size_t i = 0; i < value.length(); i++) {
    const char character = value.charAt(i);
    if (character == '"' || character == '\\') {
      escaped += '\\';
      escaped += character;
    } else if (character == '\n') {
      escaped += "\\n";
    } else if (character == '\r') {
      escaped += "\\r";
    } else {
      escaped += character;
    }
  }
  return escaped;
}

bool jsonStringValue(const String &json, const char *key, String &value) {
  const String marker = String("\"") + key + "\"";
  const int keyPosition = json.indexOf(marker);
  if (keyPosition < 0) {
    return false;
  }
  int position = json.indexOf(':', keyPosition + marker.length());
  if (position < 0) {
    return false;
  }
  position++;
  while (position < static_cast<int>(json.length()) &&
         isspace(static_cast<unsigned char>(json.charAt(position)))) {
    position++;
  }
  if (position >= static_cast<int>(json.length()) ||
      json.charAt(position) != '"') {
    return false;
  }

  value = "";
  position++;
  while (position < static_cast<int>(json.length())) {
    char character = json.charAt(position++);
    if (character == '"') {
      return true;
    }
    if (character == '\\' && position < static_cast<int>(json.length())) {
      character = json.charAt(position++);
      if (character == 'n') {
        value += '\n';
      } else if (character == 'r') {
        value += '\r';
      } else if (character == 't') {
        value += '\t';
      } else {
        value += character;
      }
    } else {
      value += character;
    }
  }
  return false;
}

bool jsonIntValue(const String &json, const char *key, int &value) {
  const String marker = String("\"") + key + "\"";
  const int keyPosition = json.indexOf(marker);
  if (keyPosition < 0) {
    return false;
  }
  int position = json.indexOf(':', keyPosition + marker.length());
  if (position < 0) {
    return false;
  }
  position++;
  while (position < static_cast<int>(json.length()) &&
         isspace(static_cast<unsigned char>(json.charAt(position)))) {
    position++;
  }
  const int start = position;
  while (position < static_cast<int>(json.length()) &&
         (isdigit(static_cast<unsigned char>(json.charAt(position))) ||
          json.charAt(position) == '-')) {
    position++;
  }
  if (position == start) {
    return false;
  }
  value = json.substring(start, position).toInt();
  return true;
}

void notifyStatus(const String &state, const String &detail = "") {
  if (statusCharacteristic == nullptr) {
    return;
  }
  const String payload = String("{\"state\":\"") + jsonEscape(state) +
                         "\",\"detail\":\"" + jsonEscape(detail) +
                         "\",\"device_id\":\"" + jsonEscape(deviceId) +
                         "\",\"ip\":\"" +
                         (WiFi.isConnected() ? WiFi.localIP().toString() : "") +
                         "\"}";
  statusCharacteristic->setValue(payload.c_str());
  if (bleConnected) {
    statusCharacteristic->notify();
  }
  Serial.printf("[ble] %s %s\n", state.c_str(), detail.c_str());
}

void loadSettings() {
  preferences.begin("eye-care", false);
#if defined(EYE_CARE_FORCE_DEV_WIFI) && EYE_CARE_FORCE_DEV_WIFI
  ssid = EYE_CARE_DEV_WIFI_SSID;
  wifiPassword = EYE_CARE_DEV_WIFI_PASSWORD;
  preferences.putString("ssid", ssid);
  preferences.putString("password", wifiPassword);
#else
  ssid = preferences.getString("ssid", "");
  wifiPassword = preferences.getString("password", "");
#endif
  deviceId = preferences.getString(
      "device_id", EYE_CARE_DEFAULT_DEVICE_ID);
  uploadToken = preferences.getString(
      "upload_token", EYE_CARE_DEFAULT_UPLOAD_TOKEN);
}

void saveSettings() {
  preferences.putString("ssid", ssid);
  preferences.putString("password", wifiPassword);
  preferences.putString("device_id", deviceId);
  preferences.putString("upload_token", uploadToken);
}

void clearWifiSettings() {
  ssid = "";
  wifiPassword = "";
  preferences.remove("ssid");
  preferences.remove("password");
  WiFi.disconnect(true, true);
  wifiReady = false;
}

bool connectWifi() {
  if (ssid.isEmpty()) {
    notifyStatus("provisioning_required");
    return false;
  }

  notifyStatus("wifi_connecting", ssid);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(true);
  WiFi.begin(ssid.c_str(), wifiPassword.c_str());

  const uint32_t started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 20000) {
    delay(250);
  }

  if (WiFi.status() != WL_CONNECTED) {
    wifiReady = false;
    notifyStatus("wifi_failed", "check_2g_wifi_and_password");
    return false;
  }

  wifiReady = true;
  notifyStatus("online", WiFi.localIP().toString());
  return true;
}

bool requestCloud(const char *method,
                  const String &path,
                  const String &body,
                  String &response,
                  int &statusCode) {
  if (!wifiReady || WiFi.status() != WL_CONNECTED) {
    return false;
  }

  const String endpoint = String(EYE_CARE_CLOUD_URL) + path;
  WiFiClient plainClient;
  WiFiClientSecure secureClient;
  WiFiClient *transport = &plainClient;
  if (endpoint.startsWith("https://")) {
    secureClient.setInsecure();
    transport = &secureClient;
  }
  HTTPClient http;
  if (!http.begin(*transport, endpoint)) {
    return false;
  }
  http.setTimeout(10000);
  if (!body.isEmpty()) {
    http.addHeader("Content-Type", "application/json");
  }
  http.addHeader("Authorization", "Bearer " + uploadToken);

  if (strcmp(method, "GET") == 0) {
    statusCode = http.GET();
  } else {
    statusCode = http.POST(body);
  }
  response = http.getString();
  if (statusCode < 0) {
    Serial.printf("[cloud] error=%d detail=%s endpoint=%s local_ip=%s\n",
                  statusCode, http.errorToString(statusCode).c_str(),
                  endpoint.c_str(),
                  WiFi.localIP().toString().c_str());
  }
  http.end();
  Serial.printf("[cloud] %s HTTP %d %s\n", method, statusCode,
                response.c_str());
  return statusCode >= 200 && statusCode < 300;
}

bool postTelemetry(const String &body) {
  String response;
  int statusCode = 0;
  return requestCloud("POST", "/ingest/telemetry", body, response, statusCode);
}

bool postSensorLine(const char *line) {
  float lux = 0.0F;
  int luxStatus = -1;
  float temperature = 0.0F;
  float humidity = 0.0F;
  int dhtStatus = -1;
  int occupied = 0;
  int sitContMin = 0;
  int sitTotalMin = 0;
  int lastMotionMin = 0;
  float risk = 0.1F;
  char riskLevel[16] = "low";
  const int parsed = sscanf(
      line,
      "[eye-care] lux=%f(%d) temp=%f rh=%f(%d) occupied=%d "
      "sit=%d total=%d last_motion=%d risk=%f risk_level=%15s",
      &lux, &luxStatus, &temperature, &humidity, &dhtStatus, &occupied,
      &sitContMin, &sitTotalMin, &lastMotionMin, &risk, riskLevel);
  if (parsed != 11) {
    if (sscanf(line,
               "[eye-care] lux=%f(%d) temp=%f rh=%f(%d) occupied=%d",
               &lux, &luxStatus, &temperature, &humidity, &dhtStatus,
               &occupied) != 6) {
      return false;
    }
    risk = occupied != 0 ? 0.2F : 0.1F;
  }

  String body = String("{\"device_id\":\"") + jsonEscape(deviceId) +
                "\",\"occupied\":" + (occupied != 0 ? "true" : "false") +
                ",\"sit_cont_min\":" + String(sitContMin) +
                ",\"sit_total_min\":" + String(sitTotalMin) +
                ",\"last_motion_min\":" + String(lastMotionMin) +
                ",\"risk\":" + String(risk, 2) +
                ",\"risk_level\":\"" + jsonEscape(riskLevel) + "\"";

  if (luxStatus == 0) {
    const char *lightState =
        lux < 150.0F ? "dark" : lux > 1000.0F ? "too_bright" : "normal";
    body += ",\"lux\":" + String(static_cast<int>(round(lux)));
    body += ",\"light_state\":\"" + String(lightState) + "\"";
  }
  if (dhtStatus == 0) {
    body += ",\"temperature\":" + String(temperature, 1);
    body += ",\"humidity\":" + String(humidity, 1);
  }
  body += "}";

  return postTelemetry(body);
}

bool nextJsonObject(const String &json, int &cursor, String &object) {
  while (cursor < static_cast<int>(json.length())) {
    const int start = json.indexOf('{', cursor);
    if (start < 0) {
      return false;
    }

    int depth = 0;
    bool inString = false;
    bool escaped = false;
    for (int i = start; i < static_cast<int>(json.length()); i++) {
      const char character = json.charAt(i);
      if (inString) {
        if (escaped) {
          escaped = false;
        } else if (character == '\\') {
          escaped = true;
        } else if (character == '"') {
          inString = false;
        }
        continue;
      }
      if (character == '"') {
        inString = true;
      } else if (character == '{') {
        depth++;
      } else if (character == '}') {
        depth--;
        if (depth == 0) {
          object = json.substring(start, i + 1);
          cursor = i + 1;
          return true;
        }
      }
    }
    cursor = start + 1;
  }
  return false;
}

bool executeCloudCommand(const String &commandName,
                         const String &commandJson,
                         String &message) {
  if (commandName == "buzz") {
    String pattern = "short";
    int duration = 200;
    jsonStringValue(commandJson, "pattern", pattern);
    if (!jsonIntValue(commandJson, "duration_ms", duration)) {
      duration = pattern == "long" ? 1000 : 200;
    }
    char line[64];
    snprintf(line, sizeof(line), "BUZZ,%s,%d\n", pattern.c_str(), duration);
    Serial1.print(line);
    message = "buzzer command forwarded";
    return true;
  }

  if (commandName == "set_threshold") {
    int luxMin = 0;
    int luxMax = 0;
    int sitWarn = 0;
    int sitStrong = 0;
    if (!jsonIntValue(commandJson, "lux_min", luxMin) ||
        !jsonIntValue(commandJson, "lux_max", luxMax) ||
        !jsonIntValue(commandJson, "sit_warn_min", sitWarn) ||
        !jsonIntValue(commandJson, "sit_strong_min", sitStrong)) {
      message = "threshold values incomplete";
      return false;
    }
    char line[96];
    snprintf(line, sizeof(line), "THRESH,%d,%d,%d,%d\n",
             luxMin, luxMax, sitWarn, sitStrong);
    Serial1.print(line);
    message = "thresholds forwarded";
    return true;
  }

  if (commandName == "set_report_interval") {
    int seconds = 0;
    if (!jsonIntValue(commandJson, "seconds", seconds) || seconds < 5) {
      message = "invalid report interval";
      return false;
    }
    uploadIntervalMs = static_cast<uint32_t>(seconds) * 1000UL;
    message = "report interval updated";
    return true;
  }

  if (commandName == "reset_sitting") {
    Serial1.print("RESET\n");
    message = "sitting counter reset";
    return true;
  }

  message = "unsupported command";
  return false;
}

void acknowledgeCommand(const String &requestId, bool ok,
                        const String &message) {
  const String body = String("{\"result_code\":") + (ok ? "0" : "1") +
                      ",\"result\":{\"message\":\"" + jsonEscape(message) +
                      "\"}}";
  String response;
  int statusCode = 0;
  requestCloud(
      "POST", "/ingest/commands/" + requestId + "/ack",
      body, response, statusCode);
}

void processCloudCommands(const String &response) {
  int cursor = 0;
  String commandJson;
  while (nextJsonObject(response, cursor, commandJson)) {
    String status;
    String requestId;
    String commandName;
    if (!jsonStringValue(commandJson, "status", status) ||
        status != "sent" ||
        !jsonStringValue(commandJson, "request_id", requestId) ||
        !jsonStringValue(commandJson, "command_name", commandName)) {
      continue;
    }

    String message;
    const bool ok =
        executeCloudCommand(commandName, commandJson, message);
    Serial.printf("[command] %s %s\n", commandName.c_str(),
                  message.c_str());
    acknowledgeCommand(requestId, ok, message);
  }
}

void pollCloudCommands() {
  String response;
  int statusCode = 0;
  const String path =
      "/devices/" + deviceId + "/commands?limit=10";
  if (requestCloud("GET", path, "", response, statusCode)) {
    processCloudCommands(response);
  }
}

class ProvisioningCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) override {
    const String value = characteristic->getValue().c_str();

    String command;
    if (jsonStringValue(value, "command", command) && command == "buzz") {
      String pattern = "short";
      int duration = 200;
      jsonStringValue(value, "pattern", pattern);
      jsonIntValue(value, "duration_ms", duration);
      char line[48];
      snprintf(line, sizeof(line), "BUZZ,%s,%d\n", pattern.c_str(), duration);
      Serial1.print(line);
      notifyStatus("buzzer_command_sent", pattern);
      return;
    }

    String newSsid;
    String newPassword;
    String newDeviceId;
    String newUploadToken;
    if (!jsonStringValue(value, "ssid", newSsid) || newSsid.isEmpty()) {
      notifyStatus("provisioning_error", "ssid_required");
      return;
    }

    ssid = newSsid;
    jsonStringValue(value, "password", newPassword);
    wifiPassword = newPassword;
    if (jsonStringValue(value, "device_id", newDeviceId) &&
        !newDeviceId.isEmpty()) {
      deviceId = newDeviceId;
    }
    if (jsonStringValue(value, "upload_token", newUploadToken) &&
        !newUploadToken.isEmpty()) {
      uploadToken = newUploadToken;
    }
    saveSettings();
    notifyStatus("credentials_saved");
    wifiProvisioningRequested = true;
  }
};

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *) override {
    bleConnected = true;
    notifyStatus(wifiReady ? "online" : "connected");
  }

  void onDisconnect(BLEServer *) override {
    bleConnected = false;
    bleServer->startAdvertising();
  }
};

void setupBle() {
  uint8_t mac[6] = {0};
  WiFi.macAddress(mac);
  char name[24];
  snprintf(name, sizeof(name), "EyeCare-%02X%02X", mac[4], mac[5]);

  BLEDevice::init(name);
  bleServer = BLEDevice::createServer();
  bleServer->setCallbacks(new ServerCallbacks());
  BLEService *service = bleServer->createService(kServiceUuid);

  BLECharacteristic *rxCharacteristic = service->createCharacteristic(
      kRxUuid, BLECharacteristic::PROPERTY_WRITE);
  rxCharacteristic->setCallbacks(new ProvisioningCallbacks());

  statusCharacteristic = service->createCharacteristic(
      kStatusUuid, BLECharacteristic::PROPERTY_READ |
                       BLECharacteristic::PROPERTY_NOTIFY);
  statusCharacteristic->addDescriptor(new BLE2902());
  service->start();

  BLEAdvertising *advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID(kServiceUuid);
  advertising->setScanResponse(true);
  advertising->start();
  Serial.printf("[ble] advertising as %s\n", name);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial1.setRxBufferSize(1024);
  Serial1.begin(115200, SERIAL_8N1, EYE_CARE_UART_RX_PIN,
                EYE_CARE_UART_TX_PIN);

  loadSettings();
  setupBle();
  connectWifi();
}

void loop() {
  if (wifiProvisioningRequested) {
    wifiProvisioningRequested = false;
    connectWifi();
  }

  if (!wifiReady || WiFi.status() != WL_CONNECTED) {
    wifiReady = false;
    const uint32_t now = millis();
    if (!ssid.isEmpty() && now - lastWifiAttemptMs >= kWifiRetryMs) {
      lastWifiAttemptMs = now;
      connectWifi();
    }
  }

  if (wifiReady) {
    const uint32_t now = millis();
    if (now - lastCommandPollMs >= kCommandPollMs) {
      lastCommandPollMs = now;
      pollCloudCommands();
    }
  }

  static String uartLine;
  while (Serial1.available() > 0) {
    const char character = static_cast<char>(Serial1.read());
    if (character == '\n') {
      uartLine.trim();
      if (!uartLine.isEmpty()) {
        Serial.printf("[uart] %s\n", uartLine.c_str());
        const uint32_t now = millis();
        if (now - lastUploadMs >= uploadIntervalMs &&
            postSensorLine(uartLine.c_str())) {
          lastUploadMs = now;
        }
      }
      uartLine = "";
    } else if (uartLine.length() < 256) {
      uartLine += character;
    }
  }

  delay(10);
}
