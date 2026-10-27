# ESP32-C3 网关

固件负责：

- BLE 配网
- WiFi 配置持久化
- 从 Hi3861 UART 读取传感器数据
- HTTPS 上传到固定 FastAPI 云端
- 无按键、无状态 LED，状态通过 BLE 返回给 App

## 接线

```text
Hi3861 TX → ESP32 GPIO4 (RX)
Hi3861 RX → ESP32 GPIO5 (TX)
Hi3861 GND → ESP32 GND
```

两块板共用稳定 5V 电源。

## BLE 配网

设备广播名称：

```text
EyeCare-XXXX
```

向 RX characteristic 写入：

```json
{
  "ssid": "home-2.4g",
  "password": "wifi-password",
  "device_id": "hi3861_001",
  "upload_token": "cloud-upload-token"
}
```

状态从 status characteristic 读取或订阅通知。

## 构建

```powershell
cd E:\Hi3861\eye-care-desk-system\gateway\esp32-c3
pio run
pio run --target upload
```
