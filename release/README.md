# Eye Care 本地试用包

## 文件

- `eye-care-source.zip`：完整源代码，不含密码、数据库和本地构建产物。
- `EyeCare-app-signed.hap`：当前开发证书签名的 HarmonyOS App。
- `esp32-gateway.bin`：ESP32 网关固件。
- `hi3861-local-sensors.bin`：Hi3861 本地传感器固件。

## 启动本地服务

双击项目根目录的 `start-local.cmd`。

默认地址：

```text
当前云端 API：  http://39.106.195.83:8080
当前接口文档：  http://39.106.195.83:8080/docs
本地备用 API：  http://127.0.0.1:8080
```

数据库文件为 `backend/eye_care.db`，重启后数据保留。

当前竞赛版 App 和 ESP32 默认连接阿里云，AI 使用
`kimi-k3.1-pro`。云端服务已经通过真实 ESP32 遥测、AI 日报和蜂鸣器
ACK 验收。

手机网页入口：

```text
http://39.106.195.83:8080/mobile
```

ESP32 支持无密码 SoftAP 配网：

```text
热点：EyeCare-Setup
页面：http://192.168.4.1
```

首次配网或点击网页“开启配网热点”后使用。配网成功后设备会记住网络，
日常断电重启会自动重连。

本地 AI 备用环境可运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download-ai-model.ps1
backend\.venv\Scripts\python -m pip install -r backend\requirements-ai.txt
```

模型约 1.1 GB，不包含在源码压缩包中。App 点击“AI 深度分析”时会显示
分析进度，完成后显示云端模型、生成时间、动态原因分析和行动建议。

## 硬件

```text
Hi3861 IO11 TX  -> ESP32 D25 RX
Hi3861 IO12 RX  <- ESP32 D26 TX
Hi3861 GND      <-> ESP32 GND
```

ESP32 设备名由 MAC 地址生成，当前为 `EyeCare-5B98`。

推荐使用 Windows 移动热点联调：

```text
SSID：EyeCare-Local
密码：EyeCare2026
频段：2.4 GHz
```

热点启动后运行 `start-local.cmd`，脚本会使用 `192.168.137.1:8080`。

## 注意

- 当前 HAP 使用开发签名，不能直接用于应用市场上架。
- HarmonyOS 模拟器不支持蓝牙，BLE 配网必须使用真机或 nRF Connect 验证。
- ESP32、手机和电脑必须处于允许设备互访的同一局域网。
- 当前电脑已完成本地演示所需的防火墙调整；迁移到其他电脑时，必须允许
  TCP `8080` 的本地子网入站访问。
