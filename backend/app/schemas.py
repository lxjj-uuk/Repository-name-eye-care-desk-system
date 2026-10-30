from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DeviceOut(ORMModel):
    device_id: str
    name: str
    created_at: datetime


class TelemetryIn(BaseModel):
    device_id: str = "hi3861_001"
    ts: Optional[datetime] = None
    lux: Optional[int] = Field(default=None, ge=0, le=200000)
    temperature: Optional[float] = Field(default=None, ge=-40, le=85)
    humidity: Optional[float] = Field(default=None, ge=0, le=100)
    light_state: Optional[str] = None
    occupied: Optional[bool] = None
    sit_cont_min: Optional[int] = Field(default=None, ge=0, le=1440)
    sit_total_min: Optional[int] = Field(default=None, ge=0, le=1440)
    last_motion_min: Optional[int] = Field(default=None, ge=0, le=1440)
    risk: Optional[float] = Field(default=None, ge=0, le=1)
    risk_level: Optional[str] = None
    wifi_ssid: Optional[str] = None
    wifi_ip: Optional[str] = None


class TelemetryOut(ORMModel):
    id: int
    device_id: str
    ts: datetime
    lux: Optional[int] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    light_state: Optional[str] = None
    occupied: Optional[bool] = None
    sit_cont_min: Optional[int] = None
    sit_total_min: Optional[int] = None
    last_motion_min: Optional[int] = None
    risk: Optional[float] = None
    risk_level: Optional[str] = None
    created_at: datetime


class EventIn(BaseModel):
    device_id: str = "hi3861_001"
    ts: Optional[datetime] = None
    event_type: str
    level: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventOut(ORMModel):
    id: int
    device_id: str
    ts: datetime
    event_type: str
    level: Optional[str] = None
    payload: Dict[str, Any]
    created_at: datetime


class ThresholdUpdate(BaseModel):
    lux_min: Optional[int] = Field(default=None, ge=0, le=200000)
    lux_max: Optional[int] = Field(default=None, ge=0, le=200000)
    sit_warn_min: Optional[int] = Field(default=None, ge=1, le=240)
    sit_strong_min: Optional[int] = Field(default=None, ge=1, le=240)
    buzzer_enabled: Optional[bool] = None
    report_interval: Optional[int] = Field(default=None, ge=5, le=3600)


class ThresholdOut(ORMModel):
    device_id: str
    lux_min: int
    lux_max: int
    sit_warn_min: int
    sit_strong_min: int
    buzzer_enabled: bool
    report_interval: int
    updated_at: datetime


class CommandCreate(BaseModel):
    command_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    requested_by: str = "app"


class CommandOut(ORMModel):
    id: int
    device_id: str
    command_name: str
    params: Dict[str, Any]
    status: str
    request_id: str
    requested_by: str
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    acked_at: Optional[datetime] = None


class CommandAck(BaseModel):
    result_code: int
    result: Dict[str, Any] = Field(default_factory=dict)


class ReportOut(ORMModel):
    id: int
    device_id: str
    report_date: date
    summary: Optional[str] = None
    risk_level: Optional[str] = None
    data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class LatestOut(BaseModel):
    device_id: str
    telemetry: Optional[TelemetryOut] = None
    config: Optional[ThresholdOut] = None


class NetworkStatusOut(ORMModel):
    device_id: str
    wifi_ssid: Optional[str] = None
    wifi_ip: Optional[str] = None
    updated_at: Optional[datetime] = None


class HistoryOut(BaseModel):
    device_id: str
    items: List[TelemetryOut]


class EventListOut(BaseModel):
    device_id: str
    items: List[EventOut]
