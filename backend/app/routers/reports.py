from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Device, Report
from ..schemas import ReportOut
from ..security import require_token
from ..services.aggregation import generate_daily_report
from ..services.ai_report import generate_ai_report


router = APIRouter(
    prefix="/devices/{device_id}/reports",
    tags=["reports"],
    dependencies=[Depends(require_token)],
)


def _ensure_device(db: Session, device_id: str) -> None:
    if db.get(Device, device_id) is None:
        raise HTTPException(status_code=404, detail="device not found")


@router.get("/daily", response_model=ReportOut)
def get_daily_report(
    device_id: str,
    report_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
):
    _ensure_device(db, device_id)
    report = (
        db.query(Report)
        .filter(
            Report.device_id == device_id,
            Report.report_date == report_date,
        )
        .first()
    )
    if report is None:
        report = generate_daily_report(db, device_id, report_date)
    if report is None:
        raise HTTPException(status_code=404, detail="no telemetry for this date")
    return report


@router.post("/daily/generate", response_model=ReportOut)
def regenerate_daily_report(
    device_id: str,
    report_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
):
    _ensure_device(db, device_id)
    report = generate_daily_report(db, device_id, report_date)
    if report is None:
        raise HTTPException(status_code=404, detail="no telemetry for this date")
    return report


@router.post("/ai", response_model=ReportOut)
def ai_report(
    device_id: str,
    report_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
):
    _ensure_device(db, device_id)
    report = generate_ai_report(db, device_id, report_date)
    if report is None:
        raise HTTPException(status_code=404, detail="no telemetry for this date")
    return report


@router.get("", response_model=List[ReportOut])
def list_reports(
    device_id: str,
    limit: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    _ensure_device(db, device_id)
    return (
        db.query(Report)
        .filter(Report.device_id == device_id)
        .order_by(Report.report_date.desc())
        .limit(limit)
        .all()
    )
