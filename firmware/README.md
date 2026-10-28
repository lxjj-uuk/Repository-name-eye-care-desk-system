# Hi3861 固件

量产架构使用本地传感器节点 `demo/50_eye_care`。Hi3861 只负责采集
BH1750、DHT20、人体传感器并控制蜂鸣器，通过 UART2 把数据发送给
ESP32 网关。

`demo/60_eye_care_cloud` 是保留的旧版直连华为 IoTDA 固件，只用于
历史兼容，不再作为客户交付版本。

## 放入 SDK

将整个目录复制到：

```text
src/vendor/pzkj/pz_hi3861/demo/50_eye_care
```

再用 `project-integration/BUILD.gn` 配置 `demo/BUILD.gn`，只启用：

```text
50_eye_care:template
```

## 编译

在完整 Hi3861 SDK 根目录执行：

```powershell
E:\DevEco-Device-Tool\core\deveco-venv\Scripts\hos.exe run --project-dir <SDK根目录> --environment hi3861
```

编译产物：

```text
src/out/hispark_pegasus/wifiiot_hispark_pegasus/Hi3861_wifiiot_app_allinone.bin
```

烧录时使用 `project-integration/flash-hi3861.ps1`，出现
`BootromDownloadBoot.` 后短按一次开发板 RST。

## 接线

```text
BH1750、DHT20: 3.3V / GND / SCL=GPIO9 / SDA=GPIO10
人体检测 OUT: GPIO8
蜂鸣器 I/O: GPIO14（低电平触发）

Hi3861 GPIO11 UART2 TX -> ESP32 GPIO16 RX
Hi3861 GPIO12 UART2 RX <- ESP32 GPIO17 TX
Hi3861 GND             <-> ESP32 GND
```

两块板分别 USB 供电时不要连接 5V 到 5V。
