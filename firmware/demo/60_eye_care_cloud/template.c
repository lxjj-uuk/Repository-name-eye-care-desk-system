#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "cmsis_os2.h"
#include "ohos_init.h"

#include "bsp_bh1750.h"
#include "bsp_buzzer.h"
#include "bsp_dht20.h"
#include "bsp_i2c.h"
#include "bsp_mqtt.h"
#include "bsp_pir.h"
#include "bsp_wifi.h"
#include "cJSON.h"
#include "cloud_config.h"
#include "wifi_device.h"

#define TASK_STACK_SIZE             (1024 * 14)
#define SENSOR_INTERVAL_SECONDS     2
#define RECONNECT_INTERVAL_SECONDS  10
#define MQTT_TEXT_MAX               1024
#define MQTT_TOPIC_MAX              192
#define COMMAND_ID_MAX              64

typedef struct {
    int lux_ok;
    int dht_ok;
    float lux;
    float temperature;
    float humidity;
    int occupied;
    int sit_cont_min;
    int sit_total_min;
    int last_motion_min;
    float risk;
    const char *risk_level;
    const char *light_state;
} eye_care_sample_t;

static double round_to_digits(float value, int digits)
{
    int factor = (digits == 1) ? 10 : 100;
    float scaled = value * factor;
    int rounded = (int)(scaled + (scaled >= 0.0f ? 0.5f : -0.5f));

    return (double)rounded / factor;
}

static volatile int g_cloud_connected = 0;
static int g_seconds_since_connect_attempt = RECONNECT_INTERVAL_SECONDS;
static int g_seconds_since_local_alert = 60;
static int g_sit_cont_seconds = 0;
static int g_sit_total_seconds = 0;
static int g_seconds_since_motion = 0;

static int g_lux_min = EYE_CARE_DEFAULT_LUX_MIN;
static int g_lux_max = EYE_CARE_DEFAULT_LUX_MAX;
static int g_sit_warn_min = EYE_CARE_DEFAULT_SIT_WARN_MIN;
static int g_sit_strong_min = EYE_CARE_DEFAULT_SIT_STRONG_MIN;
static int g_buzzer_enabled = 1;
static int g_report_interval_seconds = EYE_CARE_DEFAULT_REPORT_SECONDS;

static void cloud_disconnect(void);

static const cJSON *get_json_object(const cJSON *root, const char *name)
{
    if (root == NULL) {
        return NULL;
    }
    return cJSON_GetObjectItemCaseSensitive(root, name);
}

static int get_json_int(const cJSON *object, const char *name, int *value)
{
    const cJSON *item = get_json_object(object, name);

    if ((item == NULL) || !cJSON_IsNumber(item)) {
        return -1;
    }
    *value = item->valueint;
    return 0;
}

static const char *get_light_state(float lux)
{
    if (lux < (float)g_lux_min) {
        return "dark";
    }
    if (lux < 300.0f) {
        return "low";
    }
    if (lux > (float)g_lux_max) {
        return "too_bright";
    }
    if (lux > 800.0f) {
        return "bright";
    }
    return "ok";
}

static void update_health(eye_care_sample_t *sample, int elapsed_seconds)
{
    float risk;

    if (sample->occupied) {
        g_sit_cont_seconds += elapsed_seconds;
        g_sit_total_seconds += elapsed_seconds;
        g_seconds_since_motion = 0;
    } else {
        g_seconds_since_motion += elapsed_seconds;
        if (g_seconds_since_motion >= 60) {
            g_sit_cont_seconds = 0;
        }
    }

    sample->sit_cont_min = g_sit_cont_seconds / 60;
    sample->sit_total_min = g_sit_total_seconds / 60;
    sample->last_motion_min = g_seconds_since_motion / 60;

    risk = 0.1f;
    if ((strcmp(sample->light_state, "dark") == 0) ||
        (strcmp(sample->light_state, "low") == 0)) {
        risk += 0.3f;
    } else if (strcmp(sample->light_state, "too_bright") == 0) {
        risk += 0.15f;
    }
    risk += (float)sample->sit_cont_min / 150.0f;
    if (risk > 0.45f) {
        risk = 0.45f;
    }
    risk += 0.1f;
    if (risk > 0.99f) {
        risk = 0.99f;
    }
    sample->risk = risk;

    if ((sample->sit_cont_min >= g_sit_strong_min) || (sample->risk >= 0.7f)) {
        sample->risk_level = "high";
    } else if ((sample->sit_cont_min >= g_sit_warn_min) ||
               (sample->risk >= 0.4f)) {
        sample->risk_level = "medium";
    } else {
        sample->risk_level = "low";
    }
}

static void read_sensors(eye_care_sample_t *sample, int elapsed_seconds)
{
    memset(sample, 0, sizeof(*sample));
    sample->lux_ok = (bh1750_read_lux(&sample->lux) == 0);
    sample->dht_ok = (dht20_read(&sample->temperature, &sample->humidity) == 0);
    sample->occupied = pir_read();
    sample->light_state = get_light_state(sample->lux);
    update_health(sample, elapsed_seconds);

    printf("[eye-care-cloud] lux=%7.1f(%d) temp=%5.1f rh=%5.1f(%d) occupied=%d "
           "sit=%d total=%d risk=%.2f\n",
           sample->lux, sample->lux_ok, sample->temperature, sample->humidity,
           sample->dht_ok, sample->occupied, sample->sit_cont_min,
           sample->sit_total_min, sample->risk);
}

static int build_telemetry_json(const eye_care_sample_t *sample, char *output,
                                int output_size)
{
    cJSON *root = cJSON_CreateObject();
    cJSON *services;
    cJSON *service;
    cJSON *properties;
    char *json;
    int ret = -1;

    if (root == NULL) {
        return -1;
    }

    services = cJSON_CreateArray();
    if (services == NULL) {
        cJSON_Delete(root);
        return -1;
    }
    cJSON_AddItemToObject(root, "services", services);

    service = cJSON_CreateObject();
    cJSON_AddStringToObject(service, "service_id", "environment");
    properties = cJSON_CreateObject();
    cJSON_AddNumberToObject(properties, "lux",
                            sample->lux_ok ? (int)(sample->lux + 0.5f) : 0);
    cJSON_AddNumberToObject(properties, "temperature",
                            sample->dht_ok ?
                            round_to_digits(sample->temperature, 1) : 0);
    cJSON_AddNumberToObject(properties, "humidity",
                            sample->dht_ok ?
                            round_to_digits(sample->humidity, 1) : 0);
    cJSON_AddStringToObject(properties, "light_state", sample->light_state);
    cJSON_AddItemToObject(service, "properties", properties);
    cJSON_AddItemToArray(services, service);

    service = cJSON_CreateObject();
    cJSON_AddStringToObject(service, "service_id", "health");
    properties = cJSON_CreateObject();
    cJSON_AddBoolToObject(properties, "occupied", sample->occupied ? 1 : 0);
    cJSON_AddNumberToObject(properties, "sit_cont_min", sample->sit_cont_min);
    cJSON_AddNumberToObject(properties, "sit_total_min", sample->sit_total_min);
    cJSON_AddNumberToObject(properties, "last_motion_min", sample->last_motion_min);
    cJSON_AddNumberToObject(properties, "risk",
                            round_to_digits(sample->risk, 2));
    cJSON_AddStringToObject(properties, "risk_level", sample->risk_level);
    cJSON_AddItemToObject(service, "properties", properties);
    cJSON_AddItemToArray(services, service);

    service = cJSON_CreateObject();
    cJSON_AddStringToObject(service, "service_id", "config");
    properties = cJSON_CreateObject();
    cJSON_AddNumberToObject(properties, "lux_min", g_lux_min);
    cJSON_AddNumberToObject(properties, "lux_max", g_lux_max);
    cJSON_AddNumberToObject(properties, "sit_warn_min", g_sit_warn_min);
    cJSON_AddNumberToObject(properties, "sit_strong_min", g_sit_strong_min);
    cJSON_AddBoolToObject(properties, "buzzer_enabled", g_buzzer_enabled ? 1 : 0);
    cJSON_AddNumberToObject(properties, "report_interval",
                            g_report_interval_seconds);
    cJSON_AddItemToObject(service, "properties", properties);
    cJSON_AddItemToArray(services, service);

    json = cJSON_PrintUnformatted(root);
    if ((json != NULL) &&
        (sprintf_s(output, output_size, "%s", json) >= 0)) {
        ret = 0;
    }
    if (json != NULL) {
        cJSON_free(json);
    }
    cJSON_Delete(root);
    return ret;
}

static int publish_telemetry(const eye_care_sample_t *sample)
{
    char topic[MQTT_TOPIC_MAX] = {0};
    char payload[MQTT_TEXT_MAX] = {0};

    if (!g_cloud_connected) {
        return -1;
    }
    if (build_telemetry_json(sample, payload, sizeof(payload)) != 0) {
        printf("[cloud] build telemetry json failed\n");
        return -1;
    }
    if (sprintf_s(topic, sizeof(topic),
                  "$oc/devices/%s/sys/properties/report",
                  EYE_CARE_DEVICE_ID) < 0) {
        return -1;
    }
    if (MQTTClient_pub(topic, (unsigned char *)payload, strlen(payload)) != 0) {
        printf("[cloud] telemetry publish failed\n");
        cloud_disconnect();
        return -1;
    }
    printf("[cloud] telemetry published\n");
    return 0;
}

static int execute_buzz_command(const cJSON *paras, char *message, int message_size)
{
    const cJSON *pattern = get_json_object(paras, "pattern");
    const cJSON *duration_item = get_json_object(paras, "duration_ms");
    int duration_ms = 0;

    if (!g_buzzer_enabled) {
        sprintf_s(message, message_size, "buzzer disabled");
        return -1;
    }
    if ((pattern == NULL) || !cJSON_IsString(pattern)) {
        sprintf_s(message, message_size, "missing pattern");
        return -1;
    }
    if ((duration_item != NULL) && cJSON_IsNumber(duration_item)) {
        duration_ms = duration_item->valueint;
    }
    if ((duration_ms < 50) || (duration_ms > 5000)) {
        duration_ms = 0;
    }

    if (strcmp(pattern->valuestring, "short") == 0) {
        buzzer_beep((uint32_t)(duration_ms > 0 ? duration_ms : 200));
    } else if (strcmp(pattern->valuestring, "long") == 0) {
        buzzer_beep((uint32_t)(duration_ms > 0 ? duration_ms : 1000));
    } else if (strcmp(pattern->valuestring, "double") == 0) {
        uint32_t beep_ms = (uint32_t)(duration_ms > 0 ? duration_ms : 180);
        buzzer_beep(beep_ms);
        usleep(180 * 1000);
        buzzer_beep(beep_ms);
    } else {
        sprintf_s(message, message_size, "unsupported pattern");
        return -1;
    }
    sprintf_s(message, message_size, "buzzed");
    return 0;
}

static int execute_command(const char *command_name, const cJSON *paras,
                           char *message, int message_size)
{
    int value;

    if (strcmp(command_name, "buzz") == 0) {
        return execute_buzz_command(paras, message, message_size);
    }

    if (strcmp(command_name, "set_threshold") == 0) {
        int lux_min = g_lux_min;
        int lux_max = g_lux_max;
        int sit_warn = g_sit_warn_min;
        int sit_strong = g_sit_strong_min;

        (void)get_json_int(paras, "lux_min", &lux_min);
        (void)get_json_int(paras, "lux_max", &lux_max);
        (void)get_json_int(paras, "sit_warn_min", &sit_warn);
        (void)get_json_int(paras, "sit_strong_min", &sit_strong);
        if ((lux_min < 0) || (lux_max <= lux_min) || (lux_max > 200000) ||
            (sit_warn < 1) || (sit_warn > 240) ||
            (sit_strong < sit_warn) || (sit_strong > 240)) {
            sprintf_s(message, message_size, "invalid thresholds");
            return -1;
        }
        g_lux_min = lux_min;
        g_lux_max = lux_max;
        g_sit_warn_min = sit_warn;
        g_sit_strong_min = sit_strong;
        sprintf_s(message, message_size, "thresholds updated");
        return 0;
    }

    if (strcmp(command_name, "set_report_interval") == 0) {
        if ((get_json_int(paras, "seconds", &value) != 0) ||
            (value < 5) || (value > 3600)) {
            sprintf_s(message, message_size, "invalid interval");
            return -1;
        }
        g_report_interval_seconds = value;
        sprintf_s(message, message_size, "interval updated");
        return 0;
    }

    if (strcmp(command_name, "reset_sitting") == 0) {
        g_sit_cont_seconds = 0;
        g_seconds_since_motion = 0;
        sprintf_s(message, message_size, "sitting counter reset");
        return 0;
    }

    sprintf_s(message, message_size, "unsupported command");
    return -1;
}

static void send_command_response(const char *request_id, int ok,
                                  const char *message)
{
    char topic[MQTT_TOPIC_MAX] = {0};
    char payload[MQTT_TEXT_MAX] = {0};
    cJSON *root = cJSON_CreateObject();
    cJSON *paras;
    char *json;

    if (root == NULL) {
        return;
    }
    cJSON_AddNumberToObject(root, "result_code", ok ? 0 : 1);
    cJSON_AddStringToObject(root, "response_name", "command_response");
    paras = cJSON_CreateObject();
    cJSON_AddStringToObject(paras, "result", ok ? "ok" : "error");
    cJSON_AddStringToObject(paras, "message", message);
    cJSON_AddItemToObject(root, "paras", paras);

    json = cJSON_PrintUnformatted(root);
    if ((json != NULL) &&
        (sprintf_s(payload, sizeof(payload), "%s", json) >= 0) &&
        (sprintf_s(topic, sizeof(topic),
                   "$oc/devices/%s/sys/commands/response/request_id=%s",
                   EYE_CARE_DEVICE_ID, request_id) >= 0)) {
        if (MQTTClient_pub(topic, (unsigned char *)payload, strlen(payload)) != 0) {
            cloud_disconnect();
        }
    }
    if (json != NULL) {
        cJSON_free(json);
    }
    cJSON_Delete(root);
}

static int8_t cloud_command_callback(unsigned char *topic, unsigned char *payload)
{
    const char *request_marker = "request_id=";
    char request_id[COMMAND_ID_MAX] = {0};
    const char *request_start;
    cJSON *root;
    const cJSON *command_name;
    const cJSON *paras;
    char message[96] = {0};
    int ok;
    int i = 0;

    if ((topic == NULL) || (payload == NULL)) {
        return -1;
    }

    request_start = strstr((const char *)topic, request_marker);
    if (request_start != NULL) {
        request_start += strlen(request_marker);
        while ((request_start[i] != '\0') &&
               (request_start[i] != '/') &&
               (i < (COMMAND_ID_MAX - 1))) {
            request_id[i] = request_start[i];
            i++;
        }
        request_id[i] = '\0';
    }
    if (request_id[0] == '\0') {
        printf("[cloud] command without request_id\n");
        return -1;
    }

    root = cJSON_Parse((const char *)payload);
    if (root == NULL) {
        send_command_response(request_id, 0, "invalid json");
        return -1;
    }
    command_name = get_json_object(root, "command_name");
    paras = get_json_object(root, "paras");
    if ((command_name == NULL) || !cJSON_IsString(command_name)) {
        send_command_response(request_id, 0, "missing command");
        cJSON_Delete(root);
        return -1;
    }

    printf("[cloud] command=%s\n", command_name->valuestring);
    ok = (execute_command(command_name->valuestring, paras,
                          message, sizeof(message)) == 0);
    send_command_response(request_id, ok, message);
    cJSON_Delete(root);
    return ok ? 0 : -1;
}

static void cloud_disconnect(void)
{
    if (g_cloud_connected) {
        (void)MQTTClient_unConnectServer();
    }
    g_cloud_connected = 0;
}

static int cloud_connect(void)
{
    WifiLinkedInfo linked_info = {0};
    WifiErrorCode wifi_ret;
    char subscribe_topic[MQTT_TOPIC_MAX] = {0};
    char client_id[] = EYE_CARE_MQTT_CLIENT_ID;
    char username[] = EYE_CARE_MQTT_USERNAME;
    char password[] = EYE_CARE_MQTT_PASSWORD;

    if ((GetLinkedInfo(&linked_info) != WIFI_SUCCESS) ||
        (linked_info.connState != WIFI_CONNECTED)) {
        printf("[cloud] connecting Wi-Fi SSID=%s\n", EYE_CARE_WIFI_SSID);
        wifi_ret = WiFi_connectHotspots(EYE_CARE_WIFI_SSID,
                                       EYE_CARE_WIFI_PASSWORD);
        if (wifi_ret != WIFI_SUCCESS) {
            printf("[cloud] Wi-Fi connection failed: %d\n", wifi_ret);
            return -1;
        }
    }
    printf("[cloud] Wi-Fi IP=%s\n", WiFi_GetLocalIP());

    if (MQTTClient_connectServer(EYE_CARE_IOTDA_SERVER_IP,
                                 EYE_CARE_IOTDA_SERVER_PORT) != 0) {
        printf("[cloud] MQTT TCP connection failed\n");
        return -1;
    }
    if (MQTTClient_init(client_id, username, password) != 0) {
        printf("[cloud] MQTT authentication failed\n");
        (void)MQTTClient_unConnectServer();
        return -1;
    }

    if (sprintf_s(subscribe_topic, sizeof(subscribe_topic),
                  "$oc/devices/%s/sys/commands/#",
                  EYE_CARE_DEVICE_ID) < 0) {
        (void)MQTTClient_unConnectServer();
        return -1;
    }
    if (MQTTClient_subscribe(subscribe_topic) != 0) {
        printf("[cloud] MQTT subscribe failed\n");
        (void)MQTTClient_unConnectServer();
        return -1;
    }

    g_cloud_connected = 1;
    printf("[cloud] IoTDA connected, device=%s\n", EYE_CARE_DEVICE_ID);
    return 0;
}

static void eye_care_cloud_task(void)
{
    eye_care_sample_t sample;
    int bh1750_ok;
    int dht20_ok;
    uint32_t tick_freq;
    uint32_t last_loop_tick;
    uint32_t last_publish_tick;

    printf("\n===== eye care cloud firmware =====\n");
    bsp_i2c_init();
    bsp_i2c_scan();
    bh1750_ok = bh1750_init();
    dht20_ok = dht20_init();
    pir_init();
    buzzer_init();
    buzzer_beep(250);
    printf("[eye-care-cloud] init: bh1750=%d dht20=%d buzzer=GPIO14\n",
           bh1750_ok, dht20_ok);

    p_MQTTClient_sub_callback = cloud_command_callback;
    sleep(5);
    tick_freq = osKernelGetTickFreq();
    if (tick_freq == 0) {
        tick_freq = 1000;
    }
    last_loop_tick = osKernelGetTickCount();
    last_publish_tick = last_loop_tick;

    while (1) {
        uint32_t now_tick = osKernelGetTickCount();
        int elapsed_seconds = (int)((now_tick - last_loop_tick) / tick_freq);

        if (elapsed_seconds < 1) {
            elapsed_seconds = 1;
        }
        last_loop_tick = now_tick;

        g_seconds_since_connect_attempt += elapsed_seconds;
        if (!g_cloud_connected &&
            (g_seconds_since_connect_attempt >= RECONNECT_INTERVAL_SECONDS)) {
            g_seconds_since_connect_attempt = 0;
            (void)cloud_connect();
        }

        read_sensors(&sample, elapsed_seconds);

        if (g_cloud_connected) {
            if (MQTTClient_sub() < 0) {
                cloud_disconnect();
            }
        }

        if (g_cloud_connected &&
            ((uint32_t)(now_tick - last_publish_tick) >=
             (uint32_t)g_report_interval_seconds * tick_freq)) {
            last_publish_tick = now_tick;
            (void)publish_telemetry(&sample);
        }

        g_seconds_since_local_alert += elapsed_seconds;
        if (g_buzzer_enabled && sample.lux_ok &&
            (strcmp(sample.light_state, "dark") == 0) &&
            (g_seconds_since_local_alert >= 60)) {
            g_seconds_since_local_alert = 0;
            buzzer_beep(100);
        }

        sleep(SENSOR_INTERVAL_SECONDS);
    }
}

static void eye_care_cloud_demo(void)
{
    osThreadAttr_t attr = {0};

    attr.name = "EyeCareCloud";
    attr.stack_size = TASK_STACK_SIZE;
    attr.priority = osPriorityNormal;
    if (osThreadNew((osThreadFunc_t)eye_care_cloud_task, NULL, &attr) == NULL) {
        printf("[eye-care-cloud] create task failed\n");
    }
}

SYS_RUN(eye_care_cloud_demo);
