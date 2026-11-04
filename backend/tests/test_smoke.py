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
os.environ["AI_GUARDIAN_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.models import DeviceConfig, Telemetry, UserMemory, utcnow  # noqa: E402
from app.services.ai_guardian import should_trigger_guardian  # noqa: E402
from app.services.ai_report import _fallback_actions  # noqa: E402


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        health = response.json()
        assert health["status"] == "ok"
        assert health["ai"]["rag_documents"] >= 5
        assert set(health["ai"]["tools"]) >= {
            "buzz",
            "set_thresholds",
            "get_light_curve",
            "get_sitting_summary",
        }
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
        assert 2 <= len(ai_data["knowledge_sources"]) <= 3
        assert ai_data["evidence"]
        assert ai_data["ai_context"]["current"]["occupied"] is True
        assert ai_data["ai_context"]["last_command"]["name"] == "buzz"
        assert {item["tool"] for item in ai_data["tool_trace"]} >= {
            "get_light_curve",
            "get_sitting_summary",
        }
        assert ai_data["proposed_actions"]
        action_command_id = ai_data["proposed_actions"][0]["command_id"]

        daily_refresh = client.get(
            "/devices/hi3861_001/reports/daily",
            headers=headers,
            params={"date": date.today().isoformat()},
        )
        assert daily_refresh.status_code == 200
        assert daily_refresh.json()["data"]["insights"] == ai_data["insights"]
        assert daily_refresh.json()["data"]["knowledge_sources"]

        feedback = client.post(
            "/devices/hi3861_001/feedback",
            headers=headers,
            json={
                "report_id": ai_report.json()["id"],
                "command_id": action_command_id,
                "feedback_type": "handled",
                "context": {"source": "smoke-test"},
            },
        )
        assert feedback.status_code == 200
        assert feedback.json()["feedback_type"] == "handled"

        memory = client.get(
            "/devices/hi3861_001/memory",
            headers=headers,
        )
        assert memory.status_code == 200
        assert memory.json()["feedback_stats"]["handled"] == 1
        assert memory.json()["preferred_reminder"] == "buzzer"
        updated_memory = client.put(
            "/devices/hi3861_001/memory",
            headers=headers,
            json={
                "work_start_hour": 8,
                "work_end_hour": 19,
                "quiet_start_hour": 21,
                "quiet_end_hour": 7,
            },
        )
        assert updated_memory.status_code == 200
        assert updated_memory.json()["work_start_hour"] == 8
        assert updated_memory.json()["quiet_start_hour"] == 21

        ai_action = client.post(
            f"/commands/{action_command_id}/confirm",
            headers=headers,
        )
        assert ai_action.status_code == 200
        assert ai_action.json()["status"] == "sent"

        next_report = client.post(
            "/devices/hi3861_001/reports/ai",
            headers=headers,
            params={"date": date.today().isoformat()},
        )
        assert next_report.status_code == 200
        assert (
            next_report.json()["data"]["ai_context"]["user_memory"][
                "preferred_reminder"
            ]
            == "buzzer"
        )

        threshold_command = client.post(
            "/devices/hi3861_001/commands",
            headers=headers,
            json={
                "command_name": "set_threshold",
                "params": {"lux_min": 140},
            },
        )
        assert threshold_command.status_code == 200
        threshold_confirm = client.post(
            f"/commands/{threshold_command.json()['id']}/confirm",
            headers=headers,
        )
        assert threshold_confirm.status_code == 200
        thresholds = client.get(
            "/devices/hi3861_001/thresholds",
            headers=headers,
        )
        assert thresholds.json()["lux_min"] == 140


def test_low_risk_warning_can_propose_action():
    actions = _fallback_actions(
        "low",
        [{"key": "light", "level": "warn", "fact": "low light"}],
        {
            "current": {"occupied": True},
            "time_context": {"is_quiet_time": False},
            "data_quality": {"device_online": True},
            "user_memory": {"preferred_reminder": "balanced"},
        },
        DeviceConfig(
            device_id="hi3861_001",
            buzzer_enabled=True,
        ),
    )
    assert actions
    assert actions[0]["tool"] == "buzz"


def test_guardian_trigger():
    row = Telemetry(
        device_id="hi3861_001",
        ts=utcnow(),
        lux=80,
        risk_level="medium",
        occupied=True,
        sit_cont_min=50,
    )
    config = DeviceConfig(
        device_id="hi3861_001",
        lux_min=150,
        lux_max=1000,
        sit_warn_min=45,
        sit_strong_min=60,
    )
    memory = UserMemory(
        device_id="hi3861_001",
        work_start_hour=0,
        work_end_hour=0,
        quiet_start_hour=22,
        quiet_end_hour=8,
    )
    assert should_trigger_guardian(row, config, memory)
    row.occupied = False
    assert not should_trigger_guardian(row, config, memory)


if __name__ == "__main__":
    test_health()
    test_low_risk_warning_can_propose_action()
    test_guardian_trigger()
    test_full_flow()
    print("smoke tests passed")
