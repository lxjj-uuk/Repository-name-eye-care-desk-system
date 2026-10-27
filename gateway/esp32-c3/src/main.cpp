#include <Arduino.h>
#include <ArduinoJson.h>
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
constexpr uint32_t kUploadIntervalMs = 5000;
constexpr uint32_t kWifiRetryMs = 10000;

Preferences preferences;
BLEServer *bleServer = nullptr;
BLECharacteristic *statusCharacteristic = nullptr;
bool bleConnected = false;
bool wifiReady = false;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastUploadMs = 0;

String ssid;
String wifiPassword;
String deviceId;
String uploadToken;

void notifyStatus(const String &state, const String &detail = "") {
  if (statusCharacteristic == nullptr) {
    return;
  }
  JsonDocument document;
  document["state"] = state;
  document["detail"] = detail;
  document["device_id"] = deviceId;
  document["ip"] = WiFi.isConnected() ? WiFi.localIP().toString() : "";
  String payload;
  serializeJson(document, payload);
  statusCharacteristic->setValue(payload.c_str());
  if (bleConnected) {
    statusCharacteristic->notify();
  }
  Serial.printf("[ble] %s %s\n", state.c_str(), detail.c_str());
}

void loadSettings() {
  preferences.begin("eye-care", false);
  ssid = preferences.getString("ssid", "");
  wifiPassword = preferences.getString("password", "");
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
  WiFi.setSleep(false);
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

bool postTelemetry(const String &body) {
  if (!wifiReady || WiFi.status() != WL_CONNECTED) {
    return false;
  }

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  const String endpoint = String(EYE_CARE_CLOUD_URL) + "/ingest/telemetry";
  if (!http.begin(client, endpoint)) {
    return false;
  }
  http.setTimeout(10000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + uploadToken);

  const int code = http.POST(body);
  const String response = http.getString();
  http.end();
  Serial.printf("[cloud] HTTP %d %s\n", code, response.c_str());
  return code >= 200 && code < 300;
}

bool postSensorLine(const char *line) {
  float lux = 0.0F;
  int luxStatus = -1;
  float temperature = 0.0F;
  float humidity = 0.0F;
  int dhtStatus = -1;
  int occupied = 0;
  if (sscanf(line,
             "[eye-care] lux=%f(%d) temp=%f rh=%f(%d) occupied=%d",
             &lux, &luxStatus, &temperature, &humidity, &dhtStatus,
             &occupied) != 6) {
    return false;
  }

  JsonDocument document;
  document["device_id"] = deviceId;
  document["occupied"] = occupied != 0;
  document["sit_cont_min"] = 0;
  document["sit_total_min"] = 0;
  document["last_motion_min"] = occupied != 0 ? 0 : 1;
  document["risk"] = occupied != 0 ? 0.2 : 0.1;
  document["risk_level"] = "low";

  if (luxStatus == 0) {
    document["lux"] = static_cast<int>(round(lux));
    document["light_state"] =
        lux < 150.0F ? "dark" : lux > 1000.0F ? "too_bright" : "normal";
  }
  if (dhtStatus == 0) {
    document["temperature"] = temperature;
    document["humidity"] = humidity;
  }

  String body;
  serializeJson(document, body);
  return postTelemetry(body);
}

class ProvisioningCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) override {
    const String value = characteristic->getValue();
    JsonDocument document;
    const DeserializationError error = deserializeJson(document, value);
    if (error) {
      notifyStatus("provisioning_error", "invalid_json");
      return;
    }

    const char *newSsid = document["ssid"] | "";
    const char *newPassword = document["password"] | "";
    if (strlen(newSsid) == 0) {
      notifyStatus("provisioning_error", "ssid_required");
      return;
    }

    ssid = newSsid;
    wifiPassword = newPassword;
    deviceId = document["device_id"] | deviceId;
    uploadToken = document["upload_token"] | uploadToken;
    saveSettings();
    notifyStatus("credentials_saved");
    connectWifi();
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
  Serial1.begin(115200, SERIAL_8N1, EYE_CARE_UART_RX_PIN,
                EYE_CARE_UART_TX_PIN);

  loadSettings();
  setupBle();
  connectWifi();
}

void loop() {
  if (!wifiReady || WiFi.status() != WL_CONNECTED) {
    wifiReady = false;
    const uint32_t now = millis();
    if (!ssid.isEmpty() && now - lastWifiAttemptMs >= kWifiRetryMs) {
      lastWifiAttemptMs = now;
      connectWifi();
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
        if (now - lastUploadMs >= kUploadIntervalMs &&
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
