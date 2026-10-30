from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Command,
    Device,
    DeviceConfig,
    DeviceNetwork,
    Event,
    Telemetry,
    utcnow,
)
from ..schemas import (
    DeviceOut,
    EventListOut,
    EventOut,
    HistoryOut,
    LatestOut,
    NetworkStatusOut,
    TelemetryOut,
    ThresholdOut,
    ThresholdUpdate,
)
from ..security import require_token


router = APIRouter(
    prefix="/devices",
    tags=["devices"],
    dependencies=[Depends(require_token)],
)


def ensure_device(db: Session, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        device = Device(device_id=device_id, name=device_id)
        db.add(device)
        db.add(DeviceConfig(device_id=device_id))
        db.commit()
        db.refresh(device)
    return device


def get_config(db: Session, device_id: str) -> DeviceConfig:
    config = db.get(DeviceConfig, device_id)
    if config is None:
        ensure_device(db, device_id)
        config = db.get(DeviceConfig, device_id)
    return config


def naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("", response_model=List[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).order_by(Device.created_at.asc()).all()


@router.get("/{device_id}/latest", response_model=LatestOut)
def latest(device_id: str, db: Session = Depends(get_db)):
    ensure_device(db, device_id)
    row = (
        db.query(Telemetry)
        .filter(Telemetry.device_id == device_id)
        .order_by(Telemetry.ts.desc())
        .first()
    )
    config = get_config(db, device_id)
    return LatestOut(
        device_id=device_id,
        telemetry=TelemetryOut.model_validate(row) if row else None,
        config=ThresholdOut.model_validate(config) if config else None,
    )


@router.get("/{device_id}/network", response_model=NetworkStatusOut)
def network_status(device_id: str, db: Session = Depends(get_db)):
    ensure_device(db, device_id)
    status = db.get(DeviceNetwork, device_id)
    if status is None:
        return NetworkStatusOut(device_id=device_id)
    return status


@router.get("/{device_id}/history", response_model=HistoryOut)
def history(
    device_id: str,
    from_ts: Optional[datetime] = Query(default=None, alias="from"),
    to_ts: Optional[datetime] = Query(default=None, alias="to"),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    ensure_device(db, device_id)
    end = naive_utc(to_ts) or utcnow()
    start = naive_utc(from_ts) or (end - timedelta(hours=24))
    rows = (
        db.query(Telemetry)
        .filter(
            Telemetry.device_id == device_id,
            Telemetry.ts >= start,
            Telemetry.ts <= end,
        )
        .order_by(Telemetry.ts.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return HistoryOut(
        device_id=device_id,
        items=[TelemetryOut.model_validate(row) for row in rows],
    )


@router.get("/{device_id}/events", response_model=EventListOut)
def events(
    device_id: str,
    from_ts: Optional[datetime] = Query(default=None, alias="from"),
    to_ts: Optional[datetime] = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    ensure_device(db, device_id)
    end = naive_utc(to_ts) or utcnow()
    start = naive_utc(from_ts) or (end - timedelta(days=7))
    rows = (
        db.query(Event)
        .filter(
            Event.device_id == device_id,
            Event.ts >= start,
            Event.ts <= end,
        )
        .order_by(Event.ts.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return EventListOut(
        device_id=device_id,
        items=[EventOut.model_validate(row) for row in rows],
    )


@router.get("/{device_id}/thresholds", response_model=ThresholdOut)
def get_thresholds(device_id: str, db: Session = Depends(get_db)):
    ensure_device(db, device_id)
    return get_config(db, device_id)


@router.put("/{device_id}/thresholds", response_model=ThresholdOut)
def update_thresholds(
    device_id: str,
    body: ThresholdUpdate,
    db: Session = Depends(get_db),
):
    ensure_device(db, device_id)
    config = get_config(db, device_id)
    updates = body.model_dump(exclude_unset=True)

    lux_min = updates.get("lux_min", config.lux_min)
    lux_max = updates.get("lux_max", config.lux_max)
    sit_warn = updates.get("sit_warn_min", config.sit_warn_min)
    sit_strong = updates.get("sit_strong_min", config.sit_strong_min)
    if lux_min >= lux_max:
        raise HTTPException(status_code=400, detail="lux_min must be less than lux_max")
    if sit_warn >= sit_strong:
        raise HTTPException(
            status_code=400,
            detail="sit_warn_min must be less than sit_strong_min",
        )

    for key, value in updates.items():
        setattr(config, key, value)
    config.updated_at = utcnow()

    if updates:
        db.add(
            Command(
                device_id=device_id,
                command_name="set_threshold",
                params=updates,
                status="pending",
                request_id=uuid4().hex,
                requested_by="app",
            )
        )
    db.commit()
    db.refresh(config)
    return config
