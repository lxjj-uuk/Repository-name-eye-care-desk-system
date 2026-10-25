# 工位用眼健康 HarmonyOS App

工程路径：`D:\eye-care\app`

基线：DevEco Studio 6.1，API 23，Stage 模型，ArkTS/ArkUI。

## 页面结构

| 页面 | 文件 | 作用 |
|---|---|---|
| 主框架 | `entry/src/main/ets/pages/Home.ets` | 四个底部 Tab |
| 实时 | `entry/src/main/ets/pages/Dashboard.ets` | 光照、温湿度、久坐、风险，5 秒刷新 |
| 历史 | `entry/src/main/ets/pages/History.ets` | 最近 200 条数据，柱状图和列表 |
| 设置 | `entry/src/main/ets/pages/Settings.ets` | 后端地址、光照/久坐阈值、保存并下发 |
| 报告 | `entry/src/main/ets/pages/Report.ets` | 按日期获取日报和统计 |

公共代码：

| 文件 | 作用 |
|---|---|
| `common/AppConfig.ets` | 后端地址、设备 ID、演示账号 |
| `common/Models.ets` | 遥测、阈值、命令、日报类型 |
| `common/ApiClient.ets` | 登录、最新值、历史、阈值、命令、日报 |
| `common/MockData.ets` | 48 个模拟采样点、光照分布、AI 日报 |
| `common/DonutChart.ets` | Canvas 环形/扇形统计图 |

## 界面升级

- 深色渐变头部和 `AI READY` 状态标签。
- 实时页风险环形进度、光照分布环形图、指标卡片、AI 洞察卡。
- 历史页统计块、彩色柱状图、AI 趋势提示。
- 设置页演示数据开关、后端地址、阈值配置、AI 准备状态。
- 报告页 AI 原因分析、行动建议 chips 和统计卡片。

## 模拟数据与 AI 准备

App 现在默认使用真实后端数据；演示数据可以在设置页手动开启：

```text
AppConfig.useMockData = false
```

- `MockData.ets` 生成 48 个采样点，覆盖舒适、偏暗、过亮、离开四种状态。
- 实时页根据历史采样计算环形图占比。
- 报告页使用 `ReportData.insights` 和 `ReportData.recommendations` 展示 AI 原因分析与行动建议。
- 报告页的“AI 深度分析”按钮在真实模式下调用 `POST /devices/{id}/reports/ai`；演示模式直接使用 MockData。
- 报告页增加“待确认指令”卡片，MCP 创建的 `buzz` / `set_threshold` 命令会显示在这里，点击“确认执行”后下发。
- 后续接入大模型时，把 MockData 的返回值替换成后端/LLM 返回即可，页面结构不用重做。
- 设置页可以把演示模式打开；后端地址和演示开关都会持久化，重启 App 不会丢失。
- 连接失败时实时页会清掉旧模拟值并显示“后端连接失败”，不再继续显示过期数据。

## 后端地址

默认：

```text
http://10.0.2.2:8000
```

- `10.0.2.2` 是 HarmonyOS 模拟器访问电脑本机的地址。
- 真机请改成电脑局域网 IP，例如 `http://192.168.1.100:8000`。
- 也可以在 App 的“设置”页直接修改后端地址。
- 后端要用 `--host 0.0.0.0` 启动，并允许 Windows 防火墙放行 8000 端口。

启动后端：

```powershell
cd D:\eye-care\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

默认演示账号：

```text
demo / demo123
```

## 已实现接口

```text
POST /auth/login
GET  /devices/{id}/latest
GET  /devices/{id}/history
GET  /devices/{id}/thresholds
PUT  /devices/{id}/thresholds
GET  /devices/{id}/commands
POST /devices/{id}/commands
POST /commands/{id}/confirm
GET  /devices/{id}/reports/daily?date=
```

`ohos.permission.INTERNET` 已加入 `entry/src/main/module.json5`。

## 编译

命令行构建（已在本机验证成功）：

```powershell
$env:NODE_HOME = 'D:\DevEco Studio\tools\node'
$env:DEVECO_SDK_HOME = 'D:\DevEco Studio\sdk'
$env:HVIGOR_USER_HOME = 'D:\eye-care\downloads\hvigor-home'
$env:PATH = "D:\DevEco Studio\tools\node;D:\DevEco Studio\tools\ohpm\bin;D:\DevEco Studio\tools\hvigor\bin;$env:PATH"
hvigorw --mode module -p product=default -p module=entry@default -p buildMode=debug assembleHap --no-daemon
```

产物：

```text
D:\eye-care\app\entry\build\default\outputs\default\entry-default-unsigned.hap
```

当前是**未签名 HAP**。要安装到模拟器/真机，请在 DevEco Studio 里配置自动签名：

```text
File → Project Structure → Signing Configs → Automatically generate signature
```

登录华为账号后重新 Build，即可生成可安装的 HAP。

## 说明

- App 不直连 IoTDA，只访问 FastAPI 后端。
- 默认使用真实后端；没有后端时可在设置页打开演示数据。
- 修改阈值后，后端先写一条 `pending` 命令，App 再调用确认接口；当前 IoTDA 是 mock 模式。
- 实时页每 5 秒刷新一次；历史页和报告页手动刷新。
- 正式版把演示账号和静态 Token 换成 JWT/OAuth，并增加用户/设备绑定。
