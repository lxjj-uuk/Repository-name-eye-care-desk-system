from typing import Any, Dict

from sqlalchemy.orm import Session

from .. import models


def get_or_create_memory(db: Session, device_id: str) -> models.UserMemory:
    memory = db.get(models.UserMemory, device_id)
    if memory is None:
        memory = models.UserMemory(
            device_id=device_id,
            feedback_stats={
                "handled": 0,
                "later": 0,
                "not_helpful": 0,
            },
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
    return memory


def memory_context(memory: models.UserMemory) -> Dict[str, Any]:
    return {
        "preferred_reminder": memory.preferred_reminder,
        "buzzer_acceptance": round(float(memory.buzzer_acceptance or 0), 2),
        "work_hours": [memory.work_start_hour, memory.work_end_hour],
        "quiet_hours": [memory.quiet_start_hour, memory.quiet_end_hour],
        "feedback_stats": dict(memory.feedback_stats or {}),
    }


def apply_feedback(
    memory: models.UserMemory,
    feedback_type: str,
    command_name: str | None = None,
) -> None:
    stats: Dict[str, Any] = dict(memory.feedback_stats or {})
    for key in ("handled", "later", "not_helpful"):
        stats[key] = int(stats.get(key, 0))
    stats[feedback_type] = stats.get(feedback_type, 0) + 1

    acceptance = float(memory.buzzer_acceptance or 0.5)
    if command_name == "buzz":
        if feedback_type == "handled":
            acceptance += 0.15
        elif feedback_type == "not_helpful":
            acceptance -= 0.2
    elif feedback_type == "handled":
        acceptance += 0.03
    elif feedback_type == "not_helpful":
        acceptance -= 0.03
    memory.buzzer_acceptance = round(max(0.0, min(1.0, acceptance)), 3)

    if memory.buzzer_acceptance >= 0.65:
        memory.preferred_reminder = "buzzer"
    elif memory.buzzer_acceptance <= 0.3:
        memory.preferred_reminder = "visual"
    else:
        memory.preferred_reminder = "balanced"
    memory.feedback_stats = stats
