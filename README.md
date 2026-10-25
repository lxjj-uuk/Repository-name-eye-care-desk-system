# Eye Care Desk

工位用眼健康与桌面微环境监护系统。

## 系统结构

```text
BH1750 / DHT20 / HC-SR501
            |
          Hi3861
            |
       Wi-Fi + MQTT
            |
       Huawei Cloud IoTDA
            |
  Rule Engine + Application MQTT
            |
          FastAPI
            |
          MySQL
            |
      HarmonyOS App
```

## 目录

- `firmware/`：Hi3861 传感器、蜂鸣器、Wi-Fi、MQTT 和云端命令代码
- `backend/`：FastAPI、MySQL、IoTDA 应用侧 MQTT、AI 日报
- `app/`：HarmonyOS App
- `gateway/`：USB 串口调试备用网关
- `mcp/`：MCP 工具服务
- `iotda/`：华为云产品模型和导入文件生成器
- `docs/`：项目技术路线

## 快速启动

### 后端

```text
cd backend
copy .env.example .env
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
run-backend.cmd
```

填写本地 `.env` 后启动。不要提交 `.env`、密码或云端密钥。

### 固件

`firmware/demo/60_eye_care_cloud` 需要放入完整的 Hi3861 SDK：

```text
src/vendor/pzkj/pz_hi3861/demo/60_eye_care_cloud
```

同时复制：

- `firmware/common-bsp/src/*.c` 到 `common/bsp/src/`
- `firmware/common-bsp/include/*.h` 到 `common/bsp/include/`
- `firmware/project-integration/BUILD.gn` 覆盖 `demo/BUILD.gn`
- 参考 `firmware/project-integration` 中的 VS Code 任务

烧录前根据 `cloud_config.h` 的占位项填写 2.4 GHz Wi-Fi 和 IoTDA 参数。

### App

使用 DevEco Studio 打开 `app/`，执行项目同步后运行 `entry`。

默认后端地址为：

```text
http://10.0.2.2:8000
```

`10.0.2.2` 是 HarmonyOS 模拟器访问宿主机的地址。

## 安全说明

仓库不包含以下内容：

- 数据库密码
- Wi-Fi 名称和密码
- IoTDA 设备密钥
- IoTDA 应用接入凭证
- Kimi API Key
- MySQL 数据和运行日志
- HAP、固件 bin、虚拟环境和构建缓存

运行前请根据 `.env.example` 和 `firmware/demo/60_eye_care_cloud/cloud_config.h` 在本地填写配置。
