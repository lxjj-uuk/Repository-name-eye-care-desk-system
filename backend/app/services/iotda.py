import json
import logging
import threading
import time
from typing import Any, Dict
import uuid

import paho.mqtt.client as mqtt
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkiotda.v5 import (
    CreateCommandRequest,
    DeviceCommandRequest,
    ShowDeviceShadowRequest,
)
from huaweicloudsdkiotda.v5.iotda_client import IoTDAClient

from ..config import settings


logger = logging.getLogger(__name__)


def _client() -> IoTDAClient:
    if not settings.iotda_configured:
        raise RuntimeError(
            "IoTDA is not configured: set IOTDA_ACCESS_KEY, "
            "IOTDA_SECRET_KEY and IOTDA_PROJECT_ID"
        )
    credentials = BasicCredentials(
        settings.iotda_access_key,
        settings.iotda_secret_key,
        settings.iotda_project_id,
    )
    return (
        IoTDAClient.new_builder()
        .with_credentials(credentials)
        .with_endpoint(settings.iotda_base_url.rstrip("/"))
        .build()
    )


def fetch_device_shadow(device_id: str) -> Dict[str, Any]:
    request = ShowDeviceShadowRequest(
        device_id=device_id,
        instance_id=settings.iotda_instance_id or None,
    )
    response = _client().show_device_shadow(request)
    services: Dict[str, Dict[str, Any]] = {}
    event_times = []

    for shadow in response.shadow or []:
        if not shadow.reported:
            continue
        services[shadow.service_id] = shadow.reported.properties or {}
        if shadow.reported.event_time:
            event_times.append(shadow.reported.event_time)

    return {
        "device_id": device_id,
        "services": services,
        "event_time": max(event_times) if event_times else None,
    }


def send_command(
    device_id: str, command_name: str, params: Dict[str, Any]
) -> Dict[str, Any]:
    if settings.iotda_mock:
        logger.info(
            "mock IoTDA command device=%s command=%s params=%s",
            device_id,
            command_name,
            params,
        )
        return {
            "mock": True,
            "result": "ok",
            "message": "mock mode: command recorded but not sent to IoTDA",
        }

    if settings.iotda_app_mqtt_configured:
        request_id = str(uuid.uuid4())
        timestamp = str(int(time.time() * 1000))
        username = (
            f"accessKey={settings.iotda_app_access_key}"
            f"|timestamp={timestamp}"
            f"|instanceId={settings.iotda_instance_id}"
        )
        published = threading.Event()
        state = {"error": None}
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"eye-care-backend-{timestamp}",
            protocol=mqtt.MQTTv311,
        )
        client.username_pw_set(username, settings.iotda_app_access_code)
        client.tls_set()

        def on_connect(client, userdata, flags, reason_code, properties):
            if str(reason_code) != "Success":
                state["error"] = f"MQTT connect rejected: {reason_code}"
                published.set()
                return
            topic = (
                f"$oc/devices/{device_id}/sys/commands/"
                f"request_id={request_id}"
            )
            payload = json.dumps(
                {
                    "service_id": "config",
                    "command_name": command_name,
                    "paras": params,
                }
            )
            client.publish(topic, payload, qos=1)

        def on_publish(client, userdata, message_id, reason_code, properties):
            if str(reason_code) != "Success":
                state["error"] = f"MQTT publish rejected: {reason_code}"
            published.set()

        client.on_connect = on_connect
        client.on_publish = on_publish
        client.connect(
            settings.iotda_app_mqtt_host,
            settings.iotda_app_mqtt_port,
            keepalive=30,
        )
        client.loop_start()
        try:
            if not published.wait(timeout=10):
                raise TimeoutError("timed out publishing IoTDA command")
            if state["error"]:
                raise RuntimeError(state["error"])
        finally:
            client.disconnect()
            client.loop_stop()
        return {
            "transport": "mqtt",
            "request_id": request_id,
            "result": "published",
        }

    request = CreateCommandRequest(
        device_id=device_id,
        instance_id=settings.iotda_instance_id or None,
        body=DeviceCommandRequest(
            service_id="config",
            command_name=command_name,
            paras=params,
        ),
    )
    response = _client().create_command(request)
    return {
        "command_id": response.command_id,
        "response": response.response,
        "error_code": response.error_code,
        "error_msg": response.error_msg,
    }
