import asyncio
import json
import os
import sys
from datetime import date

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def result_payload(result) -> dict:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", None) or []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
    return {}


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[r"D:\eye-care\mcp\server.py"],
        cwd=r"D:\eye-care\mcp",
        env={
            **os.environ,
            "BACKEND_BASE_URL": "http://127.0.0.1:8000",
            "API_TOKEN": "dev-token-change-me",
            "PYTHONIOENCODING": "utf-8",
        },
    )
    async with stdio_client(params, errlog=sys.stderr) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", [tool.name for tool in tools.tools])

            summary = await session.call_tool(
                "get_today_summary",
                {
                    "device_id": "hi3861_001",
                    "date": date.today().isoformat(),
                },
            )
            summary_data = result_payload(summary)
            print("summary.risk:", summary_data.get("risk_level"))
            print("summary.insights:", len(summary_data.get("insights", [])))
            print("summary.source:", summary_data.get("source"))

            curve = await session.call_tool(
                "get_light_curve",
                {"device_id": "hi3861_001", "limit": 5},
            )
            curve_data = result_payload(curve)
            print("curve.count:", curve_data.get("count"))

            buzz = await session.call_tool(
                "buzz",
                {
                    "device_id": "hi3861_001",
                    "pattern": "short",
                    "duration_ms": 200,
                },
            )
            buzz_data = result_payload(buzz)
            print("buzz.status:", buzz_data.get("status"))
            print("buzz.command_id:", buzz_data.get("command_id"))

            pending = await session.call_tool(
                "get_pending_commands",
                {"device_id": "hi3861_001", "limit": 20},
            )
            pending_data = result_payload(pending)
            print("pending.count:", pending_data.get("count"))

    command_id = buzz_data.get("command_id")
    if command_id:
        login = httpx.post(
            "http://127.0.0.1:8000/auth/login",
            json={"username": "demo", "password": "demo123"},
            timeout=10.0,
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        confirmed = httpx.post(
            f"http://127.0.0.1:8000/commands/{command_id}/confirm",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        confirmed.raise_for_status()
        print("confirmed.status:", confirmed.json().get("status"))


if __name__ == "__main__":
    asyncio.run(main())
