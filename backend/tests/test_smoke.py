import os
import warnings
from datetime import date
from uuid import uuid4


warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
)

os.environ["DATABASE_URL"] = f"sqlite:///./test_eye_care_{uuid4().hex}.db"
os.environ["API_TOKEN"] = "test-token"
os.environ["DEMO_USERNAME"] = "demo"
os.environ["DEMO_PASSWORD"] = "demo123"
os.environ["IOTDA_MOCK"] = "true"
os.environ["LLM_API_URL"] = ""
os.environ["LOCAL_LLM_MODEL_PATH"] = "Z:/missing-eye-care-model.gguf"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mobile = client.get("/mobile")
        assert mobile.status_code == 200
        assert "Eye Care Desk" in mobile.text


def test_full_flow():
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"username": "demo", "password": "demo123"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        telemetry = client.post(
            "/ingest/telemetry",
            headers=headers,
            json={
                "lux": 120,
                "temperature": 24.5,
                "humidity": 50.0,
                "occupied": True,
                "sit_cont_min": 50,
                "sit_total_min": 120,
                "last_motion_min": 3,
                "risk": 0.5,
                "risk_level": "medium",
                "wifi_ssid": "EyeCare-Test",
                "wifi_ip": "192.168.1.42",
            },
        )
        assert telemetry.status_code == 201

        latest = client.get(
            "/devices/hi3861_001/latest", headers=headers
        )
        assert latest.status_code == 200
        assert latest.json()["telemetry"]["lux"] == 120
        network = client.get(
            "/devices/hi3861_001/network", headers=headers
        )
        assert network.status_code == 200
        assert network.json()["wifi_ssid"] == "EyeCare-Test"
        assert network.json()["wifi_ip"] == "192.168.1.42"

        history = client.get(
            "/devices/hi3861_001/history", headers=headers
        )
        assert history.status_code == 200
        assert len(history.json()["items"]) >= 1

        command = client.post(
            "/devices/hi3861_001/commands",
            headers=headers,
            json={"command_name": "buzz", "params": {"pattern": "short"}},
        )
        assert command.status_code == 200
        command_id = command.json()["id"]

        confirmed = client.post(
            f"/commands/{command_id}/confirm", headers=headers
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "sent"

        report = client.get(
            "/devices/hi3861_001/reports/daily",
            headers=headers,
            params={"date": date.today().isoformat()},
        )
        assert report.status_code == 200
        assert "共记录" in report.json()["summary"]
        report_data = report.json()["data"]
        assert report_data["occupied_ratio"] == 1.0
        assert report_data["coverage"]["lux"] == 1.0

        ai_report = client.post(
            "/devices/hi3861_001/reports/ai",
            headers=headers,
            params={"date": date.today().isoformat()},
        )
        assert ai_report.status_code == 200
        ai_data = ai_report.json()["data"]
        assert ai_data["insights"]
        assert ai_data["recommendations"]
        assert ai_data["source"] in {"rule+risk-model", "llm"}


if __name__ == "__main__":
    test_health()
    test_full_flow()
    print("smoke tests passed")
