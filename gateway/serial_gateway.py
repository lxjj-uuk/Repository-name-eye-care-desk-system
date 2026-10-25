import os
import re
import time

import httpx
import serial
from serial.tools import list_ports


SERIAL_PORT = os.getenv("SERIAL_PORT", "AUTO")
BAUD_RATE = int(os.getenv("BAUD_RATE", "115200"))
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.getenv("API_TOKEN", "dev-token-change-me")
DEMO_USERNAME = os.getenv("DEMO_USERNAME", "demo")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo123")
DEVICE_ID = os.getenv("DEVICE_ID", "hi3861_001")
POST_INTERVAL_S = float(os.getenv("POST_INTERVAL_S", "5"))

SENSOR_LINE = re.compile(
    r"lux=\s*(-?\d+(?:\.\d+)?)\((-?\d+)\).*?"
    r"temp=\s*(-?\d+(?:\.\d+)?).*?"
    r"rh=\s*(-?\d+(?:\.\d+)?)\((-?\d+)\).*?"
    r"occupied=(\d+)"
)


def resolve_serial_port() -> str:
    requested = SERIAL_PORT.strip()
    if requested and requested.upper() not in {"AUTO", "*"}:
        return requested

    ports = list(list_ports.comports())
    ch340_ports = [
        port
        for port in ports
        if port.vid == 0x1A86
        and port.pid == 0x7523
        or "CH340" in (port.description or "").upper()
    ]
    if len(ch340_ports) == 1:
        return ch340_ports[0].device

    available = ", ".join(
        f"{port.device} ({port.description or 'unknown'})" for port in ports
    )
    if not ch340_ports:
        raise RuntimeError(
            "No online CH340 serial port found. "
            f"Available ports: {available or 'none'}"
        )
    raise RuntimeError(
        "Multiple CH340 serial ports found. "
        f"Set SERIAL_PORT explicitly to one of: "
        f"{', '.join(port.device for port in ch340_ports)}"
    )


def wait_for_serial_port() -> str:
    while True:
        try:
            return resolve_serial_port()
        except RuntimeError as exc:
            print(f"waiting for CH340: {exc}", flush=True)
            time.sleep(2)


class Gateway:
    def __init__(self) -> None:
        self.client = httpx.Client(timeout=10.0)
        self.token = API_TOKEN
        self.last_post = 0.0
        self.occupied_since = None
        self.last_occupied = None
        self.last_sit_cont = 0
        self.total_sit = 0

    def login(self) -> None:
        response = self.client.post(
            f"{BACKEND_URL}/auth/login",
            json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD},
            timeout=10.0,
        )
        response.raise_for_status()
        self.token = response.json()["access_token"]

    def post(self, payload: dict) -> None:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        response = self.client.post(
            f"{BACKEND_URL}/ingest/telemetry",
            json=payload,
            headers=headers,
        )
        if response.status_code == 401:
            self.login()
            headers["Authorization"] = f"Bearer {self.token}"
            response = self.client.post(
                f"{BACKEND_URL}/ingest/telemetry",
                json=payload,
                headers=headers,
            )
        response.raise_for_status()

    def update_sitting(self, occupied: bool) -> int:
        now = time.monotonic()
        if occupied:
            if self.occupied_since is None:
                self.occupied_since = now
                self.last_sit_cont = 0
            self.last_occupied = now
        elif self.last_occupied is not None and now - self.last_occupied > 60:
            self.occupied_since = None
            self.last_sit_cont = 0

        sit_cont = 0
        if self.occupied_since is not None:
            sit_cont = int((now - self.occupied_since) / 60)
        if sit_cont > self.last_sit_cont:
            self.total_sit += sit_cont - self.last_sit_cont
            self.last_sit_cont = sit_cont
        if self.occupied_since is None:
            self.total_sit = 0
        return sit_cont

    def handle_line(self, line: str) -> None:
        match = SENSOR_LINE.search(line)
        if not match:
            return
        now = time.monotonic()
        if now - self.last_post < POST_INTERVAL_S:
            return

        lux = float(match.group(1))
        lux_ret = int(match.group(2))
        temperature = float(match.group(3))
        humidity = float(match.group(4))
        dht_ret = int(match.group(5))
        occupied = match.group(6) == "1"
        sit_cont = self.update_sitting(occupied)

        payload = {
            "device_id": DEVICE_ID,
            "occupied": occupied,
            "sit_cont_min": sit_cont,
            "sit_total_min": self.total_sit,
        }
        if lux_ret == 0:
            payload["lux"] = int(round(lux))
            payload["light_state"] = (
                "dark" if lux < 150 else "too_bright" if lux > 1000 else "ok"
            )
        if dht_ret == 0:
            payload["temperature"] = round(temperature, 1)
            payload["humidity"] = round(humidity, 1)

        risk = 0.1
        if lux_ret == 0 and lux < 150:
            risk += 0.3
        risk += min(0.4, sit_cont / 150.0)
        risk = min(0.99, round(risk, 2))
        payload["risk"] = risk
        payload["risk_level"] = (
            "high" if risk >= 0.7 else "medium" if risk >= 0.4 else "low"
        )

        self.post(payload)
        self.last_post = now
        print(
            "posted:",
            f"lux={payload.get('lux', '--')}",
            f"temp={payload.get('temperature', '--')}",
            f"rh={payload.get('humidity', '--')}",
            f"occupied={occupied}",
            f"sit={sit_cont}",
            f"risk={risk}",
            flush=True,
        )


def main() -> None:
    serial_port = wait_for_serial_port()
    print(
        f"serial gateway: {serial_port}@{BAUD_RATE} -> {BACKEND_URL}",
        flush=True,
    )
    gateway = Gateway()
    gateway.login()
    print("backend login ok", flush=True)

    while True:
        try:
            with serial.Serial(serial_port, BAUD_RATE, timeout=1) as port:
                print(f"serial connected: {serial_port}", flush=True)
                while True:
                    raw = port.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        print("serial:", line, flush=True)
                    try:
                        gateway.handle_line(line)
                    except Exception as exc:  # noqa: BLE001
                        print("post failed:", exc, flush=True)
        except (serial.SerialException, OSError) as exc:
            print(
                f"serial disconnected from {serial_port}: {exc}",
                flush=True,
            )
            time.sleep(2)
            serial_port = wait_for_serial_port()
            print(f"retrying serial port: {serial_port}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
