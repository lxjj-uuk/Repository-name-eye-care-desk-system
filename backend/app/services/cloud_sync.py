import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

from ..config import settings
from ..db import SessionLocal
from ..models import Telemetry
from ..routers.ingest import store_telemetry
from ..schemas import TelemetryIn


logger = logging.getLogger(__name__)


def _parse_event_time(value: Optional[str]) -> datetime:
    if value:
        raw = value.strip()
        for fmt in (
            "%Y%m%dT%H%M%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
        ):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                pass
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            logger.warning("unrecognized IoTDA event_time: %s", raw)
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _number(value: Any, cast):
    if value is None:
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def mqtt_payload_to_telemetry(payload: Dict[str, Any]) -> Optional[TelemetryIn]:
    notify_data = payload.get("notify_data") or {}
    body = notify_data.get("body") or {}
    service_items = body.get("services") or []
    services: Dict[str, Dict[str, Any]] = {}
    for item in service_items:
        service_id = item.get("service_id")
        if service_id:
            services[service_id] = item.get("properties") or {}

    environment = services.get("environment") or {}
    health = services.get("health") or {}
    if not environment and not health:
        return None

    occupied = health.get("occupied")
    if isinstance(occupied, str):
        occupied = occupied.strip().lower() in {"1", "true", "yes", "on"}

    return TelemetryIn(
        device_id=settings.iotda_internal_device_id,
        ts=_parse_event_time(
            payload.get("event_time_ms") or payload.get("event_time")
        ),
        lux=_number(
            environment.get("lux"), lambda value: int(round(float(value)))
        ),
        temperature=_number(environment.get("temperature"), float),
        humidity=_number(environment.get("humidity"), float),
        light_state=environment.get("light_state"),
        occupied=occupied if isinstance(occupied, bool) else None,
        sit_cont_min=_number(health.get("sit_cont_min"), int),
        sit_total_min=_number(health.get("sit_total_min"), int),
        last_motion_min=_number(health.get("last_motion_min"), int),
        risk=_number(health.get("risk"), float),
        risk_level=health.get("risk_level"),
    )


def store_mqtt_payload(raw_payload: bytes) -> bool:
    payload = json.loads(raw_payload.decode("utf-8"))
    telemetry = mqtt_payload_to_telemetry(payload)
    if telemetry is None:
        return False

    with SessionLocal() as db:
        exists = (
            db.query(Telemetry.id)
            .filter(
                Telemetry.device_id == telemetry.device_id,
                Telemetry.ts == telemetry.ts,
            )
            .first()
        )
        if exists:
            return False
        store_telemetry(telemetry, db)
    logger.info("IoTDA MQTT telemetry stored at %s", telemetry.ts)
    return True


def _new_client() -> mqtt.Client:
    timestamp = str(int(time.time() * 1000))
    username = (
        f"accessKey={settings.iotda_app_access_key}"
        f"|timestamp={timestamp}"
        f"|instanceId={settings.iotda_instance_id}"
    )
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=username,
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(username, settings.iotda_app_access_code)
    client.tls_set()

    def on_connect(client, userdata, flags, reason_code, properties):
        if str(reason_code) == "Success":
            logger.info(
                "IoTDA application MQTT connected, subscribing topic=%s",
                settings.iotda_app_mqtt_topic,
            )
            client.subscribe(settings.iotda_app_mqtt_topic, qos=1)
        else:
            logger.error("IoTDA application MQTT rejected: %s", reason_code)

    def on_disconnect(client, userdata, flags, reason_code, properties):
        logger.warning("IoTDA application MQTT disconnected: %s", reason_code)

    def on_message(client, userdata, message):
        try:
            if store_mqtt_payload(message.payload):
                logger.info("IoTDA MQTT message processed")
        except Exception:
            logger.exception("Failed to process IoTDA MQTT message")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    return client


def run_mqtt_subscriber(stop_event: threading.Event) -> None:
    logger.info("IoTDA application MQTT subscriber starting")
    while not stop_event.is_set():
        client = _new_client()
        try:
            client.connect(
                settings.iotda_app_mqtt_host,
                settings.iotda_app_mqtt_port,
                keepalive=30,
            )
            client.loop_start()
            while not stop_event.wait(1):
                if not client.is_connected():
                    break
        except Exception:
            logger.exception("IoTDA application MQTT connection failed")
        finally:
            try:
                client.disconnect()
            except Exception:
                pass
            client.loop_stop()
        stop_event.wait(5)
