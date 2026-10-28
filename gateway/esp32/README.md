# ESP32 网关

当前固件使用经典 ESP32（`ESP32-D0WD`），负责：

- BLE 常驻配网
- WiFi 配置持久化
- 从 Hi3861 UART 读取传感器数据
- HTTPS 上传到自有 FastAPI 云端
- 无按键、无状态 LED，状态由 BLE 返回给 App

## 接线

```text
Hi3861 GPIO11 TX -> ESP32 GPIO16 RX
Hi3861 GPIO12 RX <- ESP32 GPIO17 TX
Hi3861 GND       <-> ESP32 GND
```

两块板分别 USB 供电时不要连接 5V 到 5V。

## BLE 配网

设备广播名称：

```text
EyeCare-XXXX
```

服务 UUID：

```text
Service: 6e400001-b5a3-f393-e0a9-e50e24dcca9e
RX:      6e400002-b5a3-f393-e0a9-e50e24dcca9e
Status:  6e400003-b5a3-f393-e0a9-e50e24dcca9e
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

蜂鸣器链路测试：

```json
{
  "command": "buzz",
  "pattern": "short",
  "duration_ms": 250
}
```

状态从 Status characteristic 读取或订阅通知。

## 构建

```powershell
cd E:\Hi3861\eye-care-desk-system\gateway\esp32
E:\Hi3861\eye-care-desk-system\backend\.venv\Scripts\pio.exe run
E:\Hi3861\eye-care-desk-system\backend\.venv\Scripts\pio.exe run --target upload --upload-port COM6
```

发布前把 `include/cloud_config.h` 中的云端地址和上传令牌改为生产值。
