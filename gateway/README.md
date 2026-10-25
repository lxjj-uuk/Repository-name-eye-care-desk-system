# Serial Gateway

开发期串口网关，把 Hi3861 的真实传感器串口数据转发到 FastAPI。

```text
BH1750 / DHT20 / HC-SR501
        ↓
Hi3861 串口 COM3, 115200
        ↓
serial_gateway.py
        ↓
POST /ingest/telemetry
        ↓
MySQL
        ↓
鸿蒙 App / FastAPI
```

## 启动顺序

1. 关闭 VS Code 的串口监视器，确保 COM3 空闲。
2. 启动 FastAPI：

```powershell
cd D:\eye-care\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

3. 双击：

```text
D:\eye-care\gateway\run-gateway.cmd
```

4. App 设置页关闭“演示数据模式”，后端地址填电脑局域网 IP 或模拟器地址。

## 串口格式

网关识别 `50_eye_care` 输出的这一行：

```text
[eye-care] lux=  386.2(0) temp= 24.8 rh= 51.0(0) occupied=1
```

每隔约 5 秒向 FastAPI 上报一次，并自动维护简单的连续久坐计时。

## 说明

这是开发期桥接方案，不需要先配 Wi-Fi 和 IoTDA。比赛最终版应改成：

```text
Hi3861 → Wi-Fi/MQTT → 华为云 IoTDA → FunctionGraph/MySQL → App
```

前端仍然访问同一套 FastAPI，页面不用重做。
