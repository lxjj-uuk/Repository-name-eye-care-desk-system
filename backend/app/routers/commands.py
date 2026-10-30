from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Command, utcnow
from ..schemas import CommandCreate, CommandOut
from ..security import require_token
from ..services.iotda import send_command
from .devices import ensure_device, get_config


router = APIRouter(
    prefix="/devices",
    tags=["commands"],
    dependencies=[Depends(require_token)],
)
actions = APIRouter(
    prefix="/commands",
    tags=["commands"],
    dependencies=[Depends(require_token)],
)

ALLOWED_COMMANDS = {
    "buzz",
    "set_threshold",
    "set_report_interval",
    "reset_sitting",
    "wifi_setup",
}


def _as_int(name: str, value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{name} must be an integer")


def _validate_command(command_name: str, params: dict) -> None:
    if command_name not in ALLOWED_COMMANDS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported command, allowed: {sorted(ALLOWED_COMMANDS)}",
        )

    if command_name == "buzz":
        pattern = params.get("pattern")
        if pattern not in {"short", "long", "double"}:
            raise HTTPException(
                status_code=400, detail="pattern must be short, long or double"
            )
        if "duration_ms" in params:
            duration = _as_int("duration_ms", params["duration_ms"])
            if not 50 <= duration <= 5000:
                raise HTTPException(
                    status_code=400, detail="duration_ms must be 50-5000"
                )
            params["duration_ms"] = duration
        return

    if command_name == "set_threshold":
        allowed = {"lux_min", "lux_max", "sit_warn_min", "sit_strong_min"}
        unknown = set(params) - allowed
        if unknown:
            raise HTTPException(
                status_code=400, detail=f"unknown threshold fields: {sorted(unknown)}"
            )
        if not params:
            raise HTTPException(status_code=400, detail="at least one threshold is required")
        ranges = {
            "lux_min": (0, 200000),
            "lux_max": (0, 200000),
            "sit_warn_min": (1, 240),
            "sit_strong_min": (1, 240),
        }
        for key, value in list(params.items()):
            number = _as_int(key, value)
            low, high = ranges[key]
            if not low <= number <= high:
                raise HTTPException(
                    status_code=400, detail=f"{key} must be {low}-{high}"
                )
            params[key] = number
        return

    if command_name == "set_report_interval":
        if "seconds" not in params:
            raise HTTPException(status_code=400, detail="seconds is required")
        seconds = _as_int("seconds", params["seconds"])
        if not 5 <= seconds <= 3600:
            raise HTTPException(status_code=400, detail="seconds must be 5-3600")
        params["seconds"] = seconds
        return

    if params:
        raise HTTPException(
            status_code=400,
            detail=f"{command_name} takes no params",
        )


@router.post("/{device_id}/commands", response_model=CommandOut)
def create_command(
    device_id: str,
    body: CommandCreate,
    db: Session = Depends(get_db),
):
    ensure_device(db, device_id)
    _validate_command(body.command_name, body.params)
    command = Command(
        device_id=device_id,
        command_name=body.command_name,
        params=body.params,
        status="pending",
        request_id=uuid4().hex,
        requested_by=body.requested_by,
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


@router.get("/{device_id}/commands", response_model=List[CommandOut])
def list_commands(
    device_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    ensure_device(db, device_id)
    return (
        db.query(Command)
        .filter(Command.device_id == device_id)
        .order_by(Command.created_at.desc())
        .limit(limit)
        .all()
    )


@actions.get("/{command_id}", response_model=CommandOut)
def get_command(command_id: int, db: Session = Depends(get_db)):
    command = db.get(Command, command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="command not found")
    return command


@actions.post("/{command_id}/confirm", response_model=CommandOut)
def confirm_command(command_id: int, db: Session = Depends(get_db)):
    command = db.get(Command, command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="command not found")
    if command.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"only pending commands can be confirmed, current={command.status}",
        )

    command.status = "confirmed"
    command.confirmed_at = utcnow()
    db.commit()

    try:
        result = send_command(
            command.device_id, command.command_name, command.params or {}
        )
        command.status = "sent"
        command.sent_at = utcnow()
        command.result = result
        if command.command_name == "set_report_interval":
            seconds = int((command.params or {}).get("seconds", 0))
            if seconds > 0:
                get_config(db, command.device_id).report_interval = seconds
    except Exception as exc:  # noqa: BLE001
        command.status = "failed"
        command.result = {"error": str(exc)}
    db.commit()
    db.refresh(command)
    return command


@actions.post("/{command_id}/cancel", response_model=CommandOut)
def cancel_command(command_id: int, db: Session = Depends(get_db)):
    command = db.get(Command, command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="command not found")
    if command.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"only pending commands can be cancelled, current={command.status}",
        )
    command.status = "cancelled"
    db.commit()
    db.refresh(command)
    return command
