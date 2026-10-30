#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi

ENV_FILE="/opt/eye-care-desk-system/backend/.env"
PYTHON="/opt/eye-care-desk-system/backend/.venv/bin/python"
if [[ ! -f "${ENV_FILE}" || ! -x "${PYTHON}" ]]; then
    echo "Eye Care cloud backend is not installed." >&2
    exit 1
fi

read -r -s -p "Kimi API Key: " KIMI_API_KEY
echo
if [[ -z "${KIMI_API_KEY}" ]]; then
    echo "API key cannot be empty." >&2
    exit 1
fi

export KIMI_API_KEY
"${PYTHON}" - <<'PY'
import os
from pathlib import Path

env_path = Path("/opt/eye-care-desk-system/backend/.env")
updates = {
    "LLM_API_URL": "https://api.moonshot.cn/v1/chat/completions",
    "LLM_API_KEY": os.environ["KIMI_API_KEY"],
    "LLM_MODEL": "kimi-k3",
    "LLM_MAX_TOKENS": "600",
    "LLM_TEMPERATURE": "0.35",
    "LOCAL_LLM_MODEL_PATH": "",
}

lines = env_path.read_text(encoding="utf-8").splitlines()
seen = set()
result = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in updates:
        result.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        result.append(line)
for key, value in updates.items():
    if key not in seen:
        result.append(f"{key}={value}")

env_path.write_text("\n".join(result).rstrip() + "\n", encoding="utf-8")
env_path.chmod(0o600)
PY

unset KIMI_API_KEY
systemctl restart eye-care-api

for _ in $(seq 1 30); do
    if curl --fail --silent http://127.0.0.1:8080/health >/dev/null; then
        echo "Cloud AI configuration loaded."
        curl --silent http://127.0.0.1:8080/health
        echo
        exit 0
    fi
    sleep 1
done

echo "API health check failed." >&2
journalctl -u eye-care-api --no-pager -n 80 >&2
exit 1
