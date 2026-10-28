#ifndef EYE_CARE_GATEWAY_CLOUD_CONFIG_H
#define EYE_CARE_GATEWAY_CLOUD_CONFIG_H

/*
 * Fixed production endpoint. Customers never edit this value.
 * Replace it with the final Render/VPS HTTPS address before release.
 */
#define EYE_CARE_CLOUD_URL "https://eye-care-cloud.onrender.com"

#define EYE_CARE_DEFAULT_DEVICE_ID "hi3861_001"
#define EYE_CARE_DEFAULT_UPLOAD_TOKEN "dev-token-change-me"

/* ESP32-C3 UART connected to Hi3861 TX/RX. */
#define EYE_CARE_UART_RX_PIN 16
#define EYE_CARE_UART_TX_PIN 17

#endif
