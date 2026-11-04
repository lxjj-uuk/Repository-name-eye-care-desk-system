import logging
import threading
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..db import SessionLocal
from .ai_memory import get_or_create_memory
from .ai_report import generate_ai_report


logger = logging.getLogger(__name__)
LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def _inside_window(hour: int, start: int, end: int) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def should_trigger_guardian(
    row: Optional[models.Telemetry],
    config: models.DeviceConfig,
    memory: models.UserMemory,
    now: Optional[datetime] = None,
) -> bool:
    if row is None:
        return False
    current = now or models.utcnow()
    if (current - row.ts).total_seconds() > 30:
        return False
    if not row.occupied:
        return False
    local_hour = row.ts.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).hour
    work_start = memory.work_start_hour if memory.work_start_hour is not None else 9
    work_end = memory.work_end_hour if memory.work_end_hour is not None else 18
    if not _inside_window(local_hour, work_start, work_end):
        return False
    if _inside_window(local_hour, memory.quiet_start_hour, memory.quiet_end_hour):
        return False
    return bool(
        (row.risk_level in {"medium", "high"})
        or (row.lux is not None and (row.lux < config.lux_min or row.lux > config.lux_max))
        or (
            row.sit_cont_min is not None
            and row.sit_cont_min >= config.sit_warn_min
        )
        or (row.humidity is not None and not 40 <= row.humidity <= 70)
        or (row.temperature is not None and not 18 <= row.temperature <= 26)
    )


def _last_ai_generated_at(report: Optional[models.Report]) -> Optional[datetime]:
    if report is None or not isinstance(report.data, dict):
        return None
    value = report.data.get("generated_at")
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except ValueError:
        return None


def run_guardian_once(db: Session) -> bool:
    device_id = "hi3861_001"
    row = (
        db.query(models.Telemetry)
        .filter(models.Telemetry.device_id == device_id)
        .order_by(models.Telemetry.ts.desc())
        .first()
    )
    config = db.get(models.DeviceConfig, device_id)
    if config is None:
        return False
    memory = get_or_create_memory(db, device_id)
    if not should_trigger_guardian(row, config, memory):
        return False

    report_date = row.ts.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).date()
    existing = (
        db.query(models.Report)
        .filter(
            models.Report.device_id == device_id,
            models.Report.report_date == report_date,
        )
        .first()
    )
    generated_at = _last_ai_generated_at(existing)
    if generated_at is not None:
        elapsed = (models.utcnow() - generated_at).total_seconds()
        if elapsed < settings.ai_guardian_cooldown_s:
            return False

    generated = generate_ai_report(db, device_id, report_date)
    if generated is None:
        return False
    action_count = len((generated.data or {}).get("proposed_actions") or [])
    logger.info(
        "AI guardian generated report device=%s date=%s actions=%d",
        device_id,
        report_date,
        action_count,
    )
    return True


def run_guardian(stop_event: threading.Event) -> None:
    interval = max(10.0, settings.ai_guardian_interval_s)
    while not stop_event.wait(interval):
        try:
            with SessionLocal() as db:
                run_guardian_once(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI guardian iteration failed: %s", exc)
