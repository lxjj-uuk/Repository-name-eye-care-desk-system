import logging
import threading
from datetime import timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..db import SessionLocal
from .ai_memory import get_or_create_memory


logger = logging.getLogger(__name__)
TRACKED_COMMANDS = {"buzz", "set_threshold", "reset_sitting"}


def _telemetry_snapshot(row: Optional[models.Telemetry]) -> Dict[str, Any]:
    if row is None:
        return {}
    return {
        "ts": row.ts.isoformat(),
        "lux": row.lux,
        "temperature": row.temperature,
        "humidity": row.humidity,
        "occupied": row.occupied,
        "sit_cont_min": row.sit_cont_min,
        "risk": row.risk,
        "risk_level": row.risk_level,
    }


def create_pending_outcome(
    db: Session,
    command: models.Command,
) -> Optional[models.ActionOutcome]:
    if command.command_name not in TRACKED_COMMANDS:
        return None
    existing = (
        db.query(models.ActionOutcome)
        .filter(models.ActionOutcome.command_id == command.id)
        .first()
    )
    if existing is not None:
        return existing
    latest = (
        db.query(models.Telemetry)
        .filter(models.Telemetry.device_id == command.device_id)
        .order_by(models.Telemetry.ts.desc())
        .first()
    )
    outcome = models.ActionOutcome(
        device_id=command.device_id,
        command_id=command.id,
        action_name=command.command_name,
        status="pending",
        baseline=_telemetry_snapshot(latest),
        due_at=models.utcnow()
        + timedelta(seconds=max(10, settings.outcome_verify_delay_s)),
    )
    db.add(outcome)
    db.flush()
    return outcome


def _classify(
    outcome: models.ActionOutcome,
    before: Dict[str, Any],
    after: Dict[str, Any],
    command: Optional[models.Command],
) -> tuple[str, str, str]:
    action = outcome.action_name
    if not after:
        return "inconclusive", "执行后没有收到新的遥测，暂时无法验证效果。", ""
    if action == "reset_sitting":
        before_sit = before.get("sit_cont_min")
        after_sit = after.get("sit_cont_min")
        if isinstance(before_sit, (int, float)) and isinstance(after_sit, (int, float)):
            if after_sit <= before_sit:
                return "improved", f"久坐计时已从 {before_sit} 分钟重置为 {after_sit} 分钟。", ""
        return "inconclusive", "重置后尚未收到有效的久坐计数。", "继续观察久坐计数是否恢复。"

    if action == "set_threshold":
        params = command.params if command and isinstance(command.params, dict) else {}
        lux = after.get("lux")
        lux_min = params.get("lux_min")
        lux_max = params.get("lux_max")
        if isinstance(lux, (int, float)) and isinstance(lux_min, (int, float)) and isinstance(lux_max, (int, float)):
            if lux_min <= lux <= lux_max:
                return "improved", f"调整后照度为 {lux} lux，已进入新的 {lux_min}–{lux_max} lux 范围。", ""
            return "unchanged", f"调整后照度为 {lux} lux，仍未进入新的 {lux_min}–{lux_max} lux 范围。", "建议检查灯具，或继续调整照明阈值。"
        return "inconclusive", "阈值已经应用，但暂时没有有效照度读数。", "检查 BH1750 传感器后再验证。"

    before_sit = before.get("sit_cont_min")
    after_sit = after.get("sit_cont_min")
    before_risk = before.get("risk")
    after_risk = after.get("risk")
    if after.get("occupied") is False:
        return "improved", "提醒后检测到人员离开座位，提醒可能已促成活动。", ""
    if isinstance(before_sit, (int, float)) and isinstance(after_sit, (int, float)):
        if after_sit < before_sit:
            return "improved", f"提醒后连续久坐从 {before_sit} 分钟降至 {after_sit} 分钟。", ""
        if after_sit > before_sit + 1:
            return "worse", f"提醒后连续久坐从 {before_sit} 分钟增加到 {after_sit} 分钟。", "建议升级提醒级别或检查蜂鸣器是否实际发声。"
    if isinstance(before_risk, (int, float)) and isinstance(after_risk, (int, float)):
        if after_risk <= before_risk - 0.05:
            return "improved", f"提醒后综合风险从 {before_risk:.2f} 降至 {after_risk:.2f}。", ""
        if after_risk >= before_risk + 0.05:
            return "worse", f"提醒后综合风险从 {before_risk:.2f} 升至 {after_risk:.2f}。", "建议升级提醒并复查环境。"
    return "unchanged", "提醒后环境指标暂未出现明显改善。", "建议升级为长蜂鸣，并结合光照或久坐原因继续调整。"


def verify_outcome(db: Session, outcome: models.ActionOutcome) -> bool:
    if outcome.status != "pending" or models.utcnow() < outcome.due_at:
        return False
    command = db.get(models.Command, outcome.command_id)
    latest = (
        db.query(models.Telemetry)
        .filter(models.Telemetry.device_id == outcome.device_id)
        .order_by(models.Telemetry.ts.desc())
        .first()
    )
    after = _telemetry_snapshot(latest)
    result, summary, next_action = _classify(
        outcome,
        dict(outcome.baseline or {}),
        after,
        command,
    )
    outcome.status = "verified"
    outcome.post_check = after
    outcome.outcome = result
    outcome.summary = summary
    outcome.next_action = next_action or None
    outcome.verified_at = models.utcnow()

    memory = get_or_create_memory(db, outcome.device_id)
    stats: Dict[str, Any] = dict(memory.feedback_stats or {})
    action_stats = dict(stats.get("action_outcomes") or {})
    action_stats[result] = int(action_stats.get(result, 0)) + 1
    stats["action_outcomes"] = action_stats
    memory.feedback_stats = stats
    db.flush()
    logger.info(
        "Verified action outcome command=%s action=%s result=%s",
        outcome.command_id,
        outcome.action_name,
        result,
    )
    return True


def verify_pending_outcomes(db: Session) -> int:
    rows = (
        db.query(models.ActionOutcome)
        .filter(
            models.ActionOutcome.status == "pending",
            models.ActionOutcome.due_at <= models.utcnow(),
        )
        .order_by(models.ActionOutcome.due_at.asc())
        .limit(20)
        .all()
    )
    verified = sum(1 for row in rows if verify_outcome(db, row))
    db.commit()
    return verified


def run_outcome_verifier(stop_event: threading.Event) -> None:
    while not stop_event.wait(10):
        try:
            with SessionLocal() as db:
                verify_pending_outcomes(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Outcome verifier iteration failed: %s", exc)
