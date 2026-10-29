# Eye Care Desk Backend

工位用眼健康系统的后端骨架。

## 技术栈

- FastAPI
- SQLAlchemy
- SQLite（本地开发默认）
- MySQL（正式环境）
- IoTDA 命令转发（默认 mock）

## 快速启动

```powershell
cd C:\Users\asus\Documents\Codex\2026-10-17\y\eye-care\backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

打开：

```text
http://127.0.0.1:8080/docs
```

默认凭据：

```text
用户名：demo
密码：demo123
Bearer Token：dev-token-change-me
```

`API_TOKEN`、`DEMO_PASSWORD` 上线前必须修改。

## 本地验证流程

### 1. 登录

```powershell
$login = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/auth/login `
  -ContentType 'application/json' `
  -Body '{"username":"demo","password":"demo123"}'
$headers = @{ Authorization = "Bearer $($login.access_token)" }
```

### 2. 模拟设备上报

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/ingest/telemetry `
  -Headers $headers `
  -ContentType 'application/json' `
  -Body '{"lux":120,"temperature":24.5,"humidity":50,"occupied":true,"sit_cont_min":50,"risk":0.5,"risk_level":"medium"}'
```

### 3. 查询最新数据

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8080/devices/hi3861_001/latest -Headers $headers
```

### 4. 创建蜂鸣命令

```powershell
$cmd = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/devices/hi3861_001/commands `
  -Headers $headers `
  -ContentType 'application/json' `
  -Body '{"command_name":"buzz","params":{"pattern":"short"}}'
```

### 5. 确认并发送

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8080/commands/$($cmd.id)/confirm" `
  -Headers $headers
```

默认 `IOTDA_MOCK=true`，命令状态会变成 `sent`，但不会真的发到云端；后面把 mock 关掉并填 IoTDA 凭据即可。

### 6. 生成日报

```powershell
$today = Get-Date -Format 'yyyy-MM-dd'
Invoke-RestMethod -Uri "http://127.0.0.1:8080/devices/hi3861_001/reports/daily?date=$today" -Headers $headers
```

## API 一览

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/auth/login` | 获取 Bearer Token |
| GET | `/devices` | 设备列表 |
| GET | `/devices/{id}/latest` | 最新遥测和配置 |
| GET | `/devices/{id}/history` | 历史遥测 |
| GET | `/devices/{id}/events` | 事件列表 |
| GET | `/devices/{id}/thresholds` | 读取阈值 |
| PUT | `/devices/{id}/thresholds` | 修改阈值并生成待确认命令 |
| POST | `/devices/{id}/commands` | 创建待确认命令 |
| GET | `/devices/{id}/commands` | 命令列表 |
| POST | `/commands/{id}/confirm` | 确认并发送命令 |
| POST | `/commands/{id}/cancel` | 取消待确认命令 |
| GET | `/devices/{id}/reports/daily?date=` | 获取/生成日报 |
| POST | `/devices/{id}/reports/daily/generate?date=` | 重新生成日报 |
| POST | `/devices/{id}/reports/ai?date=` | 生成 AI 分析报告 |
| POST | `/ingest/telemetry` | 模拟设备上报遥测 |
| POST | `/ingest/events` | 模拟设备上报事件 |
| POST | `/ingest/commands/{request_id}/ack` | 设备回执 |

## MySQL 正式环境

1. 创建数据库和表：

```powershell
mysql -u root -p < sql/schema.sql
```

2. 修改 `.env`：

```text
DATABASE_URL=mysql+pymysql://eye_care:change-me@127.0.0.1:3306/eye_care?charset=utf8mb4
```

3. 重启后端。

`schema.sql` 已包含 `hi3861_001` 和默认阈值。应用启动时也会自动建表，但正式环境建议用 SQL 文件建表，字段类型和索引更明确。

## IoTDA 命令转发

默认 mock：

```text
IOTDA_MOCK=true
```

真实转发需要：

```text
IOTDA_MOCK=false
IOTDA_BASE_URL=https://iotda.cn-north-4.myhuaweicloud.com
IOTDA_PROJECT_ID=你的项目ID
IOTDA_TOKEN=你的IAM Token
```

当前实现使用 `X-Auth-Token` 调用 IoTDA 命令 API。IAM Token 会过期，正式版建议改成 AK/SK 签名或使用统一鉴权服务。不要把 AK/SK、Token 提交到 Git。

## AI 报告

`POST /devices/{id}/reports/ai?date=YYYY-MM-DD` 会：

1. 聚合当天遥测数据。
2. 用轻量风险模型计算综合风险。
3. 生成 `insights`（原因分析）和 `recommendations`（行动建议）。
4. 写入 `reports` 表并返回完整日报。

默认使用本地“规则 + 风险模型”，返回：

```json
{
  "data": {
    "source": "rule+risk-model",
    "insights": [
      {
        "title": "光照偏低",
        "detail": "平均照度 220 lux，偏低光照占比 38%。",
        "level": "warn"
      }
    ],
    "recommendations": [
      "把台灯调亮一档",
      "每工作 45-60 分钟起身活动 5 分钟"
    ]
  }
}
```

如果要接大模型，在 `.env` 里配置 OpenAI 兼容接口：

```text
LLM_API_URL=https://your-llm-endpoint/v1/chat/completions
LLM_API_KEY=your-key
LLM_MODEL=your-model
```

配置后接口会优先调用大模型；调用失败会自动回退到本地规则，并在 `source` 中标记 `llm` 或 `rule+risk-model`。

## 数据流

```text
Hi3861 → IoTDA → 规则引擎/FunctionGraph → MySQL
                                      ↑
App → FastAPI → IoTDA 命令 → Hi3861 → 回执
```

开发期可以先用 `/ingest/telemetry` 模拟设备，把 App 和日报流程跑通，再接真实 IoTDA。

## 安全说明

- 所有业务接口都需要 `Authorization: Bearer <API_TOKEN>`。
- App 不直接连接 IoTDA。
- 控制类命令先创建 `pending`，确认后才发送。
- 命令带 `request_id`，设备回执通过 `/ingest/commands/{request_id}/ack` 更新。
- 正式版把静态 Token 换成 JWT/OAuth，并加用户、设备和权限表。

## 测试

```powershell
python tests\test_smoke.py
```

测试会使用临时 SQLite 文件，覆盖登录、上报、最新值、历史、命令确认和日报。
