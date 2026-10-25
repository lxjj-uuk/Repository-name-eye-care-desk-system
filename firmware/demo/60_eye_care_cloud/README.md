# 60_eye_care_cloud

工位用眼健康项目的 Wi-Fi/MQTT 云端固件版本。

## 保留的硬件连接

- BH1750 与 DHT20：I2C0，SCL=GPIO9，SDA=GPIO10，供电=3.3V
- HC-SR501：OUT=GPIO8，供电=5V
- 蜂鸣器：GPIO14，兼容当前外接蜂鸣器和原板载蜂鸣器驱动方式

## 云端功能

- 使用 Hi3861 内置 Wi-Fi 连接 2.4 GHz 热点
- 通过 MQTT 连接华为云 IoTDA
- 上报 `environment`、`health`、`config` 三组属性
- 接收并处理以下命令：
  - `buzz`
  - `set_threshold`
  - `set_report_interval`
  - `reset_sitting`
- Wi-Fi 或 MQTT 断开后，每 10 秒自动重连
- 断网期间传感器采样和本地光照报警继续运行

## 烧录前必须配置

打开 `cloud_config.h`，填写：

- 2.4 GHz Wi-Fi 名称和密码
- IoTDA MQTT 服务器 IP
- 设备 ID
- MQTT Client ID
- MQTT 用户名
- MQTT 密码

设备密钥不要提交到公开仓库，也不要发送到公开聊天。

## 编译入口

`demo/BUILD.gn` 当前启用了：

```text
60_eye_care_cloud:template
```

本地 USB 串口版本仍保留在 `50_eye_care`。云端版本不工作时可把入口切回：

```text
50_eye_care:template
```

## 串口预期日志

```text
[cloud] connecting Wi-Fi SSID=...
[cloud] Wi-Fi IP=192.168.x.x
MQTT initialized successfully
MQTT subscribed to topics successfully
[cloud] IoTDA connected, device=...
[eye-care-cloud] lux=... temp=... humi=... occupied=...
```

云端应能看到设备在线，并能收到属性数据。
