from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .. import models


def _avg(values):
    return round(sum(values) / len(values), 1) if values else None


def generate_daily_report(
    db: Session, device_id: str, report_date: date
) -> Optional[models.Report]:
    start = datetime.combine(report_date, time.min)
    end = start + timedelta(days=1)
    rows = (
        db.query(models.Telemetry)
        .filter(
            models.Telemetry.device_id == device_id,
            models.Telemetry.ts >= start,
            models.Telemetry.ts < end,
        )
        .order_by(models.Telemetry.ts.asc())
        .all()
    )
    if not rows:
        return None

    config = db.get(models.DeviceConfig, device_id)
    lux_min = config.lux_min if config else 150
    lux_values = [row.lux for row in rows if row.lux is not None]
    temp_values = [row.temperature for row in rows if row.temperature is not None]
    humi_values = [row.humidity for row in rows if row.humidity is not None]
    sit_values = [row.sit_cont_min for row in rows if row.sit_cont_min is not None]
    risk_values = [row.risk for row in rows if row.risk is not None]

    avg_lux = _avg(lux_values)
    avg_temp = _avg(temp_values)
    avg_humi = _avg(humi_values)
    max_sit = max(sit_values) if sit_values else 0
    max_risk = round(max(risk_values), 3) if risk_values else 0.0
    poor_light_ratio = (
        round(sum(1 for value in lux_values if value < lux_min) / len(lux_values), 3)
        if lux_values
        else None
    )

    if max_risk >= 0.7 or max_sit >= 60:
        risk_level = "high"
    elif max_risk >= 0.4 or max_sit >= 45:
        risk_level = "medium"
    else:
        risk_level = "low"

    parts = [f"{report_date.isoformat()} 共记录 {len(rows)} 条数据"]
    if avg_lux is not None:
        parts.append(f"平均照度 {avg_lux} lux")
    if poor_light_ratio is not None:
        parts.append(f"偏低光照占比 {round(poor_light_ratio * 100)}%")
    if max_sit:
        parts.append(f"最长连续久坐 {max_sit} 分钟")
    parts.append(f"最高用眼风险 {max_risk:.2f}")
    summary = "；".join(parts) + "。"

    data: Dict[str, Any] = {
        "sample_count": len(rows),
        "avg_lux": avg_lux,
        "min_lux": min(lux_values) if lux_values else None,
        "max_lux": max(lux_values) if lux_values else None,
        "avg_temperature": avg_temp,
        "avg_humidity": avg_humi,
        "max_sit_cont_min": max_sit,
        "max_risk": max_risk,
        "poor_light_ratio": poor_light_ratio,
        "risk_level": risk_level,
    }

    report = (
        db.query(models.Report)
        .filter(
            models.Report.device_id == device_id,
            models.Report.report_date == report_date,
        )
        .first()
    )
    if report is None:
        report = models.Report(device_id=device_id, report_date=report_date)
        db.add(report)

    report.summary = summary
    report.risk_level = risk_level
    report.data = data
    db.commit()
    db.refresh(report)
    return report
