import copy
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .. import models
from .ai_memory import memory_context


LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def _local_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).isoformat()


def _inside_window(hour: int, start: int, end: int) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _period(hour: int) -> str:
    if 5 <= hour < 9:
        return "早晨"
    if 9 <= hour < 12:
        return "上午"
    if 12 <= hour < 14:
        return "午间"
    if 14 <= hour < 18:
        return "下午"
    if 18 <= hour < 22:
        return "傍晚"
    return "夜间"


def _sampled_curve(rows: List[models.Telemetry], limit: int = 24) -> List[Dict[str, Any]]:
    if len(rows) > limit:
        stride = max(1, len(rows) // limit)
        rows = rows[::stride][-limit:]
    return [
        {
            "ts": _local_iso(row.ts),
            "lux": row.lux,
            "occupied": row.occupied,
        }
        for row in rows
        if row.lux is not None or row.occupied is not None
    ]


def build_ai_context(
    db: Session,
    device_id: str,
    report_date: date,
    config: Optional[models.DeviceConfig],
    day_data: Dict[str, Any],
) -> Dict[str, Any]:
    start = datetime.combine(report_date, time.min)
    end = start + timedelta(days=1)
    cutoff = min(models.utcnow(), end)
    current_row = (
        db.query(models.Telemetry)
        .filter(
            models.Telemetry.device_id == device_id,
            models.Telemetry.ts >= start,
            models.Telemetry.ts < cutoff + timedelta(seconds=1),
        )
        .order_by(models.Telemetry.ts.desc())
        .first()
    )
    curve_rows = (
        db.query(models.Telemetry)
        .filter(
            models.Telemetry.device_id == device_id,
            models.Telemetry.ts >= max(start, cutoff - timedelta(hours=6)),
            models.Telemetry.ts < cutoff + timedelta(seconds=1),
        )
        .order_by(models.Telemetry.ts.desc())
        .limit(120)
        .all()
    )
    curve_rows.reverse()

    last_command = (
        db.query(models.Command)
        .filter(models.Command.device_id == device_id)
        .order_by(models.Command.created_at.desc())
        .first()
    )
    memory = db.get(models.UserMemory, device_id)
    local_now = cutoff.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
    hour = local_now.hour
    work_start = memory.work_start_hour if memory else 9
    work_end = memory.work_end_hour if memory else 18
    quiet_start = memory.quiet_start_hour if memory else 22
    quiet_end = memory.quiet_end_hour if memory else 8
    age_minutes = (
        round((models.utcnow() - current_row.ts).total_seconds() / 60, 1)
        if current_row
        else None
    )

    current = (
        {
            "ts": _local_iso(current_row.ts),
            "age_minutes": age_minutes,
            "lux": current_row.lux,
            "temperature": current_row.temperature,
            "humidity": current_row.humidity,
            "occupied": current_row.occupied,
            "sit_cont_min": current_row.sit_cont_min,
            "risk": current_row.risk,
            "risk_level": current_row.risk_level,
        }
        if current_row
        else None
    )
    command_context = (
        {
            "id": last_command.id,
            "name": last_command.command_name,
            "params": last_command.params or {},
            "status": last_command.status,
            "requested_by": last_command.requested_by,
            "result": last_command.result or {},
            "created_at": _local_iso(last_command.created_at),
            "acked_at": _local_iso(last_command.acked_at),
        }
        if last_command
        else None
    )

    return {
        "current": current,
        "today": copy.deepcopy(day_data),
        "sitting_summary": {
            "max_contiguous_min": day_data.get("max_sit_cont_min", 0),
            "max_total_min": day_data.get("max_sit_total_min", 0),
            "occupied_ratio": day_data.get("occupied_ratio"),
        },
        "recent_light_curve": _sampled_curve(curve_rows),
        "thresholds": {
            "lux_min": config.lux_min if config else 150,
            "lux_max": config.lux_max if config else 1000,
            "sit_warn_min": config.sit_warn_min if config else 45,
            "sit_strong_min": config.sit_strong_min if config else 60,
            "buzzer_enabled": config.buzzer_enabled if config else True,
        },
        "time_context": {
            "local_time": local_now.isoformat(),
            "date": local_now.date().isoformat(),
            "weekday": "星期" + "一二三四五六日"[local_now.weekday()],
            "period": _period(hour),
            "is_work_time": _inside_window(hour, work_start, work_end),
            "is_quiet_time": _inside_window(hour, quiet_start, quiet_end),
        },
        "last_command": command_context,
        "user_memory": (
            memory_context(memory)
            if memory
            else {
                "preferred_reminder": "balanced",
                "buzzer_acceptance": 0.5,
                "work_hours": [9, 18],
                "quiet_hours": [22, 8],
                "feedback_stats": {},
            }
        ),
        "data_quality": {
            "sample_count": day_data.get("sample_count", 0),
            "coverage": day_data.get("coverage", {}),
            "device_online": age_minutes is not None and age_minutes <= 10,
        },
        "tool_results": {
            "get_light_curve": {
                "range": "recent_6h",
                "count": len(curve_rows),
                "points": _sampled_curve(curve_rows),
            },
            "get_sitting_summary": {
                "max_contiguous_min": day_data.get("max_sit_cont_min", 0),
                "occupied_ratio": day_data.get("occupied_ratio"),
            },
        },
    }
