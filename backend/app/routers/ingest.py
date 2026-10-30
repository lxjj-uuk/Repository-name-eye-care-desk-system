from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Command, DeviceNetwork, Event, Telemetry, utcnow
from ..schemas import CommandAck, CommandOut, EventIn, EventOut, TelemetryIn, TelemetryOut
from ..security import require_token
from .devices import ensure_device, get_config


router = APIRouter(
    prefix="/ingest",
    tags=["ingest"],
    dependencies=[Depends(require_token)],
)


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def store_telemetry(body: TelemetryIn, db: Session):
    ensure_device(db, body.device_id)
    ts = _naive_utc(body.ts) or utcnow()
    row = Telemetry(
        device_id=body.device_id,
        ts=ts,
        lux=body.lux,
        temperature=body.temperature,
        humidity=body.humidity,
        light_state=body.light_state,
        occupied=body.occupied,
        sit_cont_min=body.sit_cont_min,
        sit_total_min=body.sit_total_min,
        last_motion_min=body.last_motion_min,
        risk=body.risk,
        risk_level=body.risk_level,
    )
    db.add(row)

    if body.wifi_ssid or body.wifi_ip:
        network = db.get(DeviceNetwork, body.device_id)
        if network is None:
            network = DeviceNetwork(device_id=body.device_id)
            db.add(network)
        if body.wifi_ssid:
            network.wifi_ssid = body.wifi_ssid
        if body.wifi_ip:
            network.wifi_ip = body.wifi_ip
        network.updated_at = utcnow()

    config = get_config(db, body.device_id)
    if body.lux is not None:
        if body.lux < config.lux_min:
            db.add(
                Event(
                    device_id=body.device_id,
                    ts=ts,
                    event_type="light_alert",
                    level="low",
                    payload={"lux": body.lux, "threshold": config.lux_min},
                )
            )
        elif body.lux > config.lux_max:
            db.add(
                Event(
                    device_id=body.device_id,
                    ts=ts,
                    event_type="light_alert",
                    level="high",
                    payload={"lux": body.lux, "threshold": config.lux_max},
                )
            )

    if (
        body.sit_cont_min is not None
        and body.sit_cont_min >= config.sit_warn_min
    ):
        recent = (
            db.query(Event)
            .filter(
                Event.device_id == body.device_id,
                Event.event_type == "sitting_alert",
                Event.ts >= ts - timedelta(minutes=5),
            )
            .first()
        )
        if recent is None:
            level = (
                "strong"
                if body.sit_cont_min >= config.sit_strong_min
                else "warn"
            )
            db.add(
                Event(
                    device_id=body.device_id,
                    ts=ts,
                    event_type="sitting_alert",
                    level=level,
                    payload={
                        "sit_cont_min": body.sit_cont_min,
                        "warn_threshold": config.sit_warn_min,
                        "strong_threshold": config.sit_strong_min,
                    },
                )
            )

    db.commit()
    db.refresh(row)
    return row


@router.post("/telemetry", response_model=TelemetryOut, status_code=201)
def ingest_telemetry(body: TelemetryIn, db: Session = Depends(get_db)):
    return store_telemetry(body, db)


@router.post("/events", response_model=EventOut, status_code=201)
def ingest_event(body: EventIn, db: Session = Depends(get_db)):
    ensure_device(db, body.device_id)
    ts = _naive_utc(body.ts) or utcnow()
    event = Event(
        device_id=body.device_id,
        ts=ts,
        event_type=body.event_type,
        level=body.level,
        payload=body.payload,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.post("/commands/{request_id}/ack", response_model=CommandOut)
def ack_command(
    request_id: str,
    body: CommandAck,
    db: Session = Depends(get_db),
):
    command = (
        db.query(Command).filter(Command.request_id == request_id).first()
    )
    if command is None:
        raise HTTPException(status_code=404, detail="command not found")
    command.status = "acked" if body.result_code == 0 else "failed"
    command.acked_at = utcnow()
    command.result = body.result
    db.commit()
    db.refresh(command)
    return command
