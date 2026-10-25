from datetime import date

from fastapi.testclient import TestClient

from app.main import app


def main():
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"username": "demo", "password": "demo123"},
        )
        login.raise_for_status()
        headers = {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }
        response = client.post(
            "/devices/hi3861_001/reports/ai",
            headers=headers,
            params={"date": date.today().isoformat()},
        )
        print("status:", response.status_code)
        body = response.json()
        data = body.get("data", {})
        print("source:", data.get("source"))
        print("risk:", body.get("risk_level"))
        print("insights:", len(data.get("insights", [])))
        for item in data.get("insights", []):
            print(" -", item.get("level"), item.get("title"))
        print("recommendations:")
        for item in data.get("recommendations", []):
            print(" -", item)


if __name__ == "__main__":
    main()
