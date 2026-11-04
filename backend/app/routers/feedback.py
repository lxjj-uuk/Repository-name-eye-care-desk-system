from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AIFeedback, Command, Report, UserMemory
from ..schemas import (
    AIFeedbackCreate,
    AIFeedbackOut,
    UserMemoryOut,
    UserMemoryUpdate,
)
from ..security import require_token
from ..services.ai_memory import apply_feedback, get_or_create_memory
from .devices import ensure_device


router = APIRouter(
    prefix="/devices",
    tags=["ai-feedback"],
    dependencies=[Depends(require_token)],
)


@router.post("/{device_id}/feedback", response_model=AIFeedbackOut)
def create_feedback(
    device_id: str,
    body: AIFeedbackCreate,
    db: Session = Depends(get_db),
):
    ensure_device(db, device_id)
    report = None
    if body.report_id is not None:
        report = db.get(Report, body.report_id)
        if report is None or report.device_id != device_id:
            raise HTTPException(status_code=404, detail="report not found")

    command = None
    if body.command_id is not None:
        command = db.get(Command, body.command_id)
        if command is None or command.device_id != device_id:
            raise HTTPException(status_code=404, detail="command not found")

    memory = get_or_create_memory(db, device_id)
    feedback = AIFeedback(
        device_id=device_id,
        report_id=body.report_id,
        command_id=body.command_id,
        feedback_type=body.feedback_type,
        note=(body.note or "").strip() or None,
        context=body.context,
    )
    db.add(feedback)

    apply_feedback(
        memory,
        body.feedback_type,
        command.command_name if command else None,
    )
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/{device_id}/memory", response_model=UserMemoryOut)
def get_memory(device_id: str, db: Session = Depends(get_db)):
    ensure_device(db, device_id)
    return get_or_create_memory(db, device_id)


@router.put("/{device_id}/memory", response_model=UserMemoryOut)
def update_memory(
    device_id: str,
    body: UserMemoryUpdate,
    db: Session = Depends(get_db),
):
    ensure_device(db, device_id)
    memory: UserMemory = get_or_create_memory(db, device_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(memory, key, value)
    db.commit()
    db.refresh(memory)
    return memory
