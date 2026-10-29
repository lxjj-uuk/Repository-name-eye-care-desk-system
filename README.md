# Eye Care Desk

工位用眼健康与桌面微环境监护系统。

## 系统结构

```text
BH1750 / DHT20 / 人体感应
            |
          Hi3861
            | UART2
          ESP32
       BLE 配网 + Wi-Fi
            |
         FastAPI
            |
      SQLite / PostgreSQL
            |
    规则风险模型 / 可选 LLM
            |
       HarmonyOS App
```

设备首次使用时由手机通过 BLE 写入 WiFi 名称和密码，之后 ESP32 自动
连接 WiFi 并上传传感器数据。设备不再依赖华为 IoTDA。

## 目录

- `firmware/demo/50_eye_care/`：Hi3861 本地传感器固件
- `gateway/esp32/`：ESP32 BLE 配网与 UART/WiFi 网关
- `backend/`：FastAPI、数据库、遥测、命令与 AI 日报
- `app/`：HarmonyOS App
- `scripts/`：本地环境启动、停止和防火墙脚本
- `docs/本地部署说明.md`：本地部署步骤

## 一键启动本地服务

双击项目根目录的：

```text
start-local.cmd
```

服务启动后可访问：

```text
API：      http://127.0.0.1:8080
接口文档：http://127.0.0.1:8080/docs
模拟器：   http://10.0.2.2:8080
```

本地服务使用：

- `backend/eye_care.db`：SQLite 持久化数据库
- `backend/.env`：本机环境配置，不提交到 Git
- `rule+risk-model`：未配置 LLM 时使用的本地分析模型

需要让 ESP32 或局域网手机访问时，先双击：

```text
enable-firewall.cmd
```

## ESP32

```powershell
cd gateway\esp32
..\..\backend\.venv\Scripts\pio.exe run
..\..\backend\.venv\Scripts\pio.exe run --target upload --upload-port COM6
```

电脑网络变化后，重新运行 `start-local.cmd`，它会更新本机局域网地址。
该地址写入被 Git 忽略的 `cloud_config.local`。

## Hi3861

将 `firmware/demo/50_eye_care` 放入完整 Hi3861 SDK：

```text
src/vendor/pzkj/pz_hi3861/demo/50_eye_care
```

接线：

```text
Hi3861 IO11 TX  -> ESP32 D25 RX
Hi3861 IO12 RX  <- ESP32 D26 TX
Hi3861 GND      <-> ESP32 GND
```

## App

使用 DevEco Studio 打开 `app/`。模拟器默认访问宿主机的
`http://10.0.2.2:8080`。

蓝牙相关功能必须在支持 BLE 的 HarmonyOS 真机测试；DevEco 模拟器
没有蓝牙服务。

## 停止服务

```text
stop-local.cmd
```

## 安全说明

以下内容已加入 Git 忽略，不应提交：

- `backend/.env`
- SQLite 数据库
- `cloud_config.local`
- WiFi 密码、API Token 和 LLM Key
- HAP、固件二进制、日志和构建缓存
