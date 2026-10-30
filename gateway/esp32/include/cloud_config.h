#ifndef EYE_CARE_GATEWAY_CLOUD_CONFIG_H
#define EYE_CARE_GATEWAY_CLOUD_CONFIG_H

#if __has_include("cloud_config.local")
#include "cloud_config.local"
#endif

/*
 * Competition cloud endpoint. Local development can override this value
 * through the Git-ignored cloud_config.local file.
 */
#ifndef EYE_CARE_CLOUD_URL
#define EYE_CARE_CLOUD_URL "http://39.106.195.83:8080"
#endif

#ifndef EYE_CARE_DEFAULT_DEVICE_ID
#define EYE_CARE_DEFAULT_DEVICE_ID "hi3861_001"
#endif

#ifndef EYE_CARE_DEFAULT_UPLOAD_TOKEN
#define EYE_CARE_DEFAULT_UPLOAD_TOKEN "dev-token-change-me"
#endif

/* ESP32 UART remapped to pins available on the ESP32-D0WD dev board. */
#ifndef EYE_CARE_UART_RX_PIN
#define EYE_CARE_UART_RX_PIN 25
#endif

#ifndef EYE_CARE_UART_TX_PIN
#define EYE_CARE_UART_TX_PIN 26
#endif

#endif
