# Hi3861 Firmware

云端固件版本为 `demo/60_eye_care_cloud`。

## 功能

- BH1750 光照采集
- DHT20 温湿度采集
- HC-SR501 活动检测
- GPIO14 外接蜂鸣器控制
- Hi3861 内置 Wi-Fi STA
- MQTT 连接华为云 IoTDA
- 5 秒属性上报
- 云端命令处理和断线重连

## 接入完整 SDK

参考工程基于 `hi3861_hdu_iot_application`。将本目录中的
`demo/60_eye_care_cloud` 放入：

```text
src/vendor/pzkj/pz_hi3861/demo/60_eye_care_cloud
```

替换公共 BSP：

```text
firmware/common-bsp/src/bsp_wifi.c
firmware/common-bsp/src/bsp_mqtt.c
firmware/common-bsp/include/bsp_wifi.h
firmware/common-bsp/include/bsp_mqtt.h
```

并用 `project-integration/BUILD.gn` 配置 `demo/BUILD.gn`，只启用：

```text
60_eye_care_cloud:template
```

## 编译与烧录

使用 DevEco Device Tool 或 VS Code：

```text
Ctrl+Shift+B
```

出现 `BootromDownloadBoot.` 时短按一次板子的 RST。

烧录前必须填写 `cloud_config.h`。实际配置不要提交到 Git。
