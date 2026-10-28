# 50_eye_care

本地传感器节点固件。Hi3861 负责光照、温湿度、人体检测和蜂鸣器，
通过 UART2 与 ESP32 网关通信，不再直接连接华为云。

## 接线

传感器与蜂鸣器：

- SCL = GPIO9
- SDA = GPIO10
- BH1750、DHT20 使用 3.3V
- 人体检测 OUT = GPIO8
- 蜂鸣器 I/O = GPIO14
- MH-FMD 蜂鸣器模块低电平触发

与 ESP32 通信：

```text
Hi3861 GPIO11 (UART2 TX) -> ESP32 GPIO16 (RX)
Hi3861 GPIO12 (UART2 RX) <- ESP32 GPIO17 (TX)
Hi3861 GND               <-> ESP32 GND
```

两块板分别 USB 供电时，不要连接 5V 到 5V。

## 串口协议

Hi3861 每两秒输出：

```text
[eye-care] lux=  386.2(0) temp= 24.8 rh= 51.0(0) occupied=1
```

ESP32 向 Hi3861 发送蜂鸣命令：

```text
BUZZ,short,200
BUZZ,long,1000
BUZZ,double,180
```

## 测试

串口波特率为 115200。设备启动时会先蜂鸣 500 ms，然后打印传感器初始化状态。
BH1750 和 DHT20 的状态码为 `0` 表示读取成功。
