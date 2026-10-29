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
API 文档：http://127.0.0.1:8080/docs
模拟器：  http://10.0.2.2:8080
局域网：  http://<电脑IP>:8080
```

数据库文件为 `backend/eye_care.db`，重启后数据保留。

AI 日报使用本机 `Qwen2.5-1.5B-Instruct`。首次部署运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download-ai-model.ps1
backend\.venv\Scripts\python -m pip install -r backend\requirements-ai.txt
```

模型约 1.1 GB，不包含在源码压缩包中。启动后访问
`http://127.0.0.1:8080/health`，`ai.local_available` 应为 `true`。
App 点击“AI 深度分析”时会显示分析进度，完成后显示本地模型、生成时间、
动态原因分析和行动建议。健康数据会直接由规则模型快速处理，存在真实风险
时才调用本地大模型。

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
