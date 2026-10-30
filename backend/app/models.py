from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=utcnow)

    config = relationship(
        "DeviceConfig",
        back_populates="device",
        uselist=False,
        cascade="all, delete-orphan",
    )


class DeviceConfig(Base):
    __tablename__ = "device_configs"

    device_id = Column(
        String(64),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        primary_key=True,
    )
    lux_min = Column(Integer, nullable=False, default=150)
    lux_max = Column(Integer, nullable=False, default=1000)
    sit_warn_min = Column(Integer, nullable=False, default=45)
    sit_strong_min = Column(Integer, nullable=False, default=60)
    buzzer_enabled = Column(Boolean, nullable=False, default=True)
    report_interval = Column(Integer, nullable=False, default=15)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    device = relationship("Device", back_populates="config")


class DeviceNetwork(Base):
    __tablename__ = "device_networks"

    device_id = Column(
        String(64),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        primary_key=True,
    )
    wifi_ssid = Column(String(128))
    wifi_ip = Column(String(64))
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(
        String(64),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ts = Column(DateTime, nullable=False, index=True)
    lux = Column(Integer)
    temperature = Column(Float)
    humidity = Column(Float)
    light_state = Column(String(32))
    occupied = Column(Boolean)
    sit_cont_min = Column(Integer)
    sit_total_min = Column(Integer)
    last_motion_min = Column(Integer)
    risk = Column(Float)
    risk_level = Column(String(16))
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(
        String(64),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ts = Column(DateTime, nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    level = Column(String(16))
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Command(Base):
    __tablename__ = "commands"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(
        String(64),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    command_name = Column(String(64), nullable=False)
    params = Column(JSON, nullable=False, default=dict)
    status = Column(String(16), nullable=False, default="pending")
    request_id = Column(String(64), nullable=False, unique=True, index=True)
    requested_by = Column(String(64), nullable=False, default="app")
    result = Column(JSON)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    confirmed_at = Column(DateTime)
    sent_at = Column(DateTime)
    acked_at = Column(DateTime)


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("device_id", "report_date", name="uq_report_device_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(
        String(64),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_date = Column(Date, nullable=False, index=True)
    summary = Column(Text)
    risk_level = Column(String(16))
    data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
