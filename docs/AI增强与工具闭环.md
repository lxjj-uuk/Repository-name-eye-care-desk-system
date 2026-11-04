# AI 增强与工具闭环

## 1. 真实上下文

生成报告时，后端会把以下信息一起交给模型：

- 最新一条遥测：当前照度、温湿度、在座状态、连续久坐、风险
- 最近 6 小时的光照曲线抽样
- 当天的低照光占比、久坐统计、数据覆盖率
- 用户设置的光照与久坐阈值
- 当前时段、工作时间和免打扰时间
- 最近一次设备命令、状态和 ACK 结果
- 用户历史反馈形成的提醒偏好

构造逻辑位于 `backend/app/services/ai_context.py`，结果会写入
`Report.data.ai_context`，因此报告不是只依赖一个平均照度。

## 2. 小型 RAG 知识库

`knowledge/` 中每条 Markdown 都保留标题、来源、URL、标签和摘要。
`backend/app/services/knowledge.py` 会在生成报告时根据风险信号和当前上下文
检索最相关的 2–3 条知识。

报告中保存并展示：

- `evidence`：来自传感器统计的判断依据
- `knowledge_sources`：知识标题、来源、摘要和链接

检索不依赖外部向量数据库，部署轻且结果可解释。

## 3. MCP 白名单工具

允许模型选择的工具固定为：

- `buzz`
- `set_thresholds`
- `get_light_curve`
- `get_sitting_summary`

读取工具直接执行。控制工具只创建 `pending` 命令，并在报告中返回
`command_id`。用户点击“确认执行”后，网页调用
`POST /commands/{id}/confirm`，ESP32 拉取命令并返回 ACK。

模型不能直接控制 GPIO，也不能绕过参数范围校验。

## 4. 反馈与个性化记忆

报告下方提供“已处理 / 稍后提醒 / 没有帮助”三个反馈按钮。

反馈写入 `ai_feedback` 表，并由 `user_memory` 累加：

- 蜂鸣提醒接受度
- 偏好的提醒方式
- 工作时间
- 免打扰时间
- 历史反馈次数

下一次生成报告时，`user_memory` 会进入模型上下文。例如用户多次对蜂鸣
给出“没有帮助”，系统会把提醒偏好调整为视觉提醒，并降低后续蜂鸣提议。

## 5. 自动巡检

后端 `ai_guardian` 默认每 30 秒检查最新遥测。满足以下条件时自动生成
新版 AI 报告和待确认动作：

- 最新数据不超过 30 秒
- 当前有人
- 存在低照光、久坐、温湿度或中高风险信号
- 不在用户设置的免打扰时段
- 距离上次自动研判超过 5 分钟

网页每 10 秒检查一次新的 AI 动作，发现后会在任意页面顶部弹出
“AI 发现新的环境提醒”，不需要先点击报告按钮。

自动巡检不会直接控制硬件。它只生成 `pending` 动作，用户确认后才通过
ESP32 ACK 闭环执行。

## 演示顺序

1. 打开网页报告页，点击“生成今日研判”。
2. 展示判断依据与知识来源。
3. 展示 AI 提议动作，强调此时设备尚未执行。
4. 点击“确认执行”，等待 ESP32 ACK。
5. 点击“已处理”或“没有帮助”。
6. 再次生成报告，说明用户记忆已经进入新的 AI 上下文。

## 相关接口

```text
POST /devices/{device_id}/reports/ai
POST /devices/{device_id}/feedback
GET  /devices/{device_id}/memory
PUT  /devices/{device_id}/memory
POST /commands/{command_id}/confirm
POST /ingest/commands/{request_id}/ack
```
