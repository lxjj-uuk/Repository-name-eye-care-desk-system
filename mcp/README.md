# Eye Care MCP Server

这是工位用眼健康系统的 MCP 工具层。大模型通过它读取数据、生成建议，并在用户确认后触发设备命令。

## 工具

| 工具 | 作用 | 是否需确认 |
|---|---|---|
| `get_today_summary` | 读取当天光照、久坐、风险、AI 分析 | 否 |
| `get_light_curve` | 读取指定时间段光照曲线 | 否 |
| `get_sitting_summary` | 读取久坐统计 | 否 |
| `set_thresholds` | 修改光照/久坐阈值 | 是 |
| `buzz` | 请求蜂鸣提醒 | 是 |
| `get_pending_commands` | 查看待确认命令 | 否 |

`set_thresholds` 和 `buzz` 只创建 `pending` 命令，不会直接控制设备。用户在鸿蒙 App 的“报告”页确认后，后端才会把命令标记为已发送。

## 运行

先启动 FastAPI：

```powershell
cd D:\eye-care\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

再启动 MCP Server（stdio 模式）：

```powershell
cd D:\eye-care\mcp
$env:BACKEND_BASE_URL = 'http://127.0.0.1:8000'
$env:API_TOKEN = 'dev-token-change-me'
D:\eye-care\backend\.venv\Scripts\python.exe server.py
```

MCP Server 默认使用 stdio，适合被 Codex、Claude Desktop 或其他 MCP 客户端拉起。

## 客户端配置示例

不同客户端的配置字段略有差异，核心是：

```json
{
  "mcpServers": {
    "eye-care-desk": {
      "command": "D:\\eye-care\\backend\\.venv\\Scripts\\python.exe",
      "args": ["D:\\eye-care\\mcp\\server.py"],
      "env": {
        "BACKEND_BASE_URL": "http://127.0.0.1:8000",
        "API_TOKEN": "dev-token-change-me",
        "DEVICE_ID": "hi3861_001"
      }
    }
  }
}
```

## 闭环流程

```text
大模型读取 get_today_summary
  → 生成建议
  → 调用 buzz 创建 pending 命令
  → 返回 command_id 给 App
  → App 报告页点击“确认执行”
  → FastAPI POST /commands/{id}/confirm
  → IoTDA 下发（当前 mock）
  → 设备回执
  → 报告显示执行结果
```

## 安全边界

- MCP Server 不直连 MySQL、IoTDA 或设备，只调用 FastAPI。
- 修改阈值和蜂鸣必须经过 App 用户确认。
- 工具参数有类型和范围校验。
- 所有命令写入 `commands` 表，保留状态、request_id 和时间。
- 大模型不能拿到数据库密码或设备密钥。

## 已验证

用 `test_mcp_client.py` 通过 stdio 实际调用：

```text
tools: get_today_summary, get_light_curve, get_sitting_summary,
       set_thresholds, buzz, get_pending_commands
summary.risk: high
summary.insights: 3
summary.source: rule+risk-model
curve.count: 1
buzz.status: pending
buzz.command_id: 2
pending.count: 1
confirmed.status: sent
```

说明 MCP Server、FastAPI、MySQL 和命令确认流程已经打通。App 的“报告”页会显示 `pending` 指令，点击“确认执行”即可完成后半段闭环。

## 版本说明

当前使用 MCP Python SDK 2.x，入口是 `mcp.server.mcpserver.MCPServer`。旧版 `FastMCP` 在 2.x 中已更名。
