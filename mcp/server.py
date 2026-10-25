import os
from datetime import date as date_cls
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.mcpserver import MCPServer


BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
API_TOKEN = os.getenv("API_TOKEN", "dev-token-change-me")
DEMO_USERNAME = os.getenv("DEMO_USERNAME", "demo")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo123")
DEFAULT_DEVICE_ID = os.getenv("DEVICE_ID", "hi3861_001")


class BackendClient:
    def __init__(self) -> None:
        self.base_url = BACKEND_BASE_URL.rstrip("/")
        self.token = API_TOKEN
        self.client = httpx.Client(timeout=15.0)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def login(self) -> None:
        response = self.client.post(
            f"{self.base_url}/auth/login",
            json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD},
            timeout=10.0,
        )
        response.raise_for_status()
        self.token = response.json()["access_token"]

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.client.request(
            method,
            f"{self.base_url}{path}",
            headers=self._headers(),
            **kwargs,
        )
        if response.status_code == 401:
            self.login()
            response = self.client.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(),
                **kwargs,
            )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def _ai_report(self, device_id: str, date: str) -> Dict[str, Any]:
        try:
            return self.request(
                "POST",
                f"/devices/{device_id}/reports/ai",
                params={"date": date},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            return self.request(
                "GET",
                f"/devices/{device_id}/reports/daily",
                params={"date": date},
            )

    def get_today_summary(self, device_id: str, date: str) -> Dict[str, Any]:
        report = self._ai_report(device_id, date)
        data = report.get("data", {})
        return {
            "device_id": device_id,
            "date": date,
            "summary": report.get("summary"),
            "risk_level": report.get("risk_level"),
            "sample_count": data.get("sample_count"),
            "avg_lux": data.get("avg_lux"),
            "max_sit_cont_min": data.get("max_sit_cont_min"),
            "insights": data.get("insights", []),
            "recommendations": data.get("recommendations", []),
            "source": data.get("source"),
        }

    def get_light_curve(
        self,
        device_id: str,
        from_time: str,
        to_time: str,
        limit: int,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit}
        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time
        data = self.request(
            "GET",
            f"/devices/{device_id}/history",
            params=params,
        )
        points: List[Dict[str, Any]] = []
        for item in data.get("items", []):
            points.append(
                {
                    "ts": item.get("ts"),
                    "lux": item.get("lux"),
                    "temperature": item.get("temperature"),
                    "humidity": item.get("humidity"),
                    "occupied": item.get("occupied"),
                }
            )
        return {
            "device_id": device_id,
            "from": from_time or "last_24h",
            "to": to_time or "now",
            "count": len(points),
            "points": points,
        }

    def get_sitting_summary(self, device_id: str, date: str) -> Dict[str, Any]:
        summary = self.get_today_summary(device_id, date)
        return {
            "device_id": device_id,
            "date": date,
            "max_sit_cont_min": summary.get("max_sit_cont_min"),
            "sample_count": summary.get("sample_count"),
            "risk_level": summary.get("risk_level"),
            "insights": summary.get("insights", []),
        }

    def set_thresholds(
        self,
        device_id: str,
        lux_min: Optional[int],
        lux_max: Optional[int],
        sit_warn_min: Optional[int],
        sit_strong_min: Optional[int],
    ) -> Dict[str, Any]:
        payload: Dict[str, int] = {}
        if lux_min is not None:
            payload["lux_min"] = lux_min
        if lux_max is not None:
            payload["lux_max"] = lux_max
        if sit_warn_min is not None:
            payload["sit_warn_min"] = sit_warn_min
        if sit_strong_min is not None:
            payload["sit_strong_min"] = sit_strong_min
        if not payload:
            return {"error": "至少提供一个阈值参数"}

        config = self.request(
            "PUT",
            f"/devices/{device_id}/thresholds",
            json=payload,
        )
        commands = self.request(
            "GET",
            f"/devices/{device_id}/commands",
            params={"limit": 20},
        )
        command_id = None
        for item in commands:
            if (
                item.get("command_name") == "set_threshold"
                and item.get("status") == "pending"
            ):
                command_id = item.get("id")
                break
        return {
            "confirmation_required": True,
            "command_id": command_id,
            "status": "pending",
            "config": config,
            "message": "阈值已保存，等待 App 确认后下发到设备",
        }

    def buzz(
        self, device_id: str, pattern: str, duration_ms: int
    ) -> Dict[str, Any]:
        if pattern not in {"short", "long", "double"}:
            return {"error": "pattern 必须是 short、long 或 double"}
        command = self.request(
            "POST",
            f"/devices/{device_id}/commands",
            json={
                "command_name": "buzz",
                "params": {
                    "pattern": pattern,
                    "duration_ms": duration_ms,
                },
            },
        )
        return {
            "confirmation_required": True,
            "command_id": command.get("id"),
            "status": command.get("status"),
            "command": command,
            "message": "蜂鸣命令已创建，等待 App 确认后执行",
        }

    def get_pending_commands(
        self, device_id: str, limit: int
    ) -> Dict[str, Any]:
        commands = self.request(
            "GET",
            f"/devices/{device_id}/commands",
            params={"limit": limit},
        )
        pending = [item for item in commands if item.get("status") == "pending"]
        return {
            "device_id": device_id,
            "count": len(pending),
            "commands": pending,
        }


backend = BackendClient()

mcp = MCPServer(
    "eye-care-desk",
    version="0.1.0",
    instructions=(
        "工位用眼健康系统的 MCP 工具。读取数据可以直接调用；"
        "修改阈值和蜂鸣只创建待确认命令，必须由 App 用户确认后才能执行。"
    ),
)


@mcp.tool(
    description="读取某设备某天的光照、久坐、风险摘要、AI 原因分析和建议。"
)
def get_today_summary(
    device_id: str = DEFAULT_DEVICE_ID,
    date: str = "",
) -> Dict[str, Any]:
    target_date = date or date_cls.today().isoformat()
    return backend.get_today_summary(device_id, target_date)


@mcp.tool(
    description="读取某设备指定时间段的光照曲线，返回 ts、lux、温湿度和是否有人。"
)
def get_light_curve(
    device_id: str = DEFAULT_DEVICE_ID,
    from_time: str = "",
    to_time: str = "",
    limit: int = 200,
) -> Dict[str, Any]:
    return backend.get_light_curve(device_id, from_time, to_time, limit)


@mcp.tool(description="读取某设备某天的久坐统计和风险摘要。")
def get_sitting_summary(
    device_id: str = DEFAULT_DEVICE_ID,
    date: str = "",
) -> Dict[str, Any]:
    target_date = date or date_cls.today().isoformat()
    return backend.get_sitting_summary(device_id, target_date)


@mcp.tool(
    description=(
        "修改光照和久坐阈值。该工具只创建待确认命令，"
        "不会直接控制设备，需要 App 用户确认。"
    )
)
def set_thresholds(
    device_id: str = DEFAULT_DEVICE_ID,
    lux_min: Optional[int] = None,
    lux_max: Optional[int] = None,
    sit_warn_min: Optional[int] = None,
    sit_strong_min: Optional[int] = None,
) -> Dict[str, Any]:
    return backend.set_thresholds(
        device_id,
        lux_min,
        lux_max,
        sit_warn_min,
        sit_strong_min,
    )


@mcp.tool(
    description=(
        "请求设备蜂鸣提醒。该工具只创建待确认命令，"
        "需要 App 用户确认后才真正下发。"
    )
)
def buzz(
    device_id: str = DEFAULT_DEVICE_ID,
    pattern: str = "short",
    duration_ms: int = 200,
) -> Dict[str, Any]:
    return backend.buzz(device_id, pattern, duration_ms)


@mcp.tool(description="查看某设备当前待确认的控制命令。")
def get_pending_commands(
    device_id: str = DEFAULT_DEVICE_ID,
    limit: int = 20,
) -> Dict[str, Any]:
    return backend.get_pending_commands(device_id, limit)


if __name__ == "__main__":
    mcp.run()
