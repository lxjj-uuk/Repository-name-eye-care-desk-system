#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi

REPO_URL="${EYE_CARE_REPO_URL:-https://github.com/lxjj-uuk/Repository-name-eye-care-desk-system.git}"
APP_DIR="${EYE_CARE_APP_DIR:-/opt/eye-care-desk-system}"
DATA_DIR="${EYE_CARE_DATA_DIR:-/var/lib/eye-care}"
SERVICE_USER="eyecare"
SERVICE_NAME="eye-care-api"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git python3 python3-pip python3-venv

if ! swapon --show | grep -q "/swapfile"; then
    fallocate -l 1G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    if ! grep -q '^/swapfile ' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
fi

if [[ -d "${APP_DIR}/.git" ]]; then
    git -C "${APP_DIR}" fetch origin
    git -C "${APP_DIR}" checkout main
    git -C "${APP_DIR}" pull --ff-only origin main
else
    git clone --branch main "${REPO_URL}" "${APP_DIR}"
fi

if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
    useradd \
        --system \
        --home-dir "${APP_DIR}" \
        --shell /usr/sbin/nologin \
        "${SERVICE_USER}"
fi

install -d -m 0750 -o "${SERVICE_USER}" -g "${SERVICE_USER}" "${DATA_DIR}"

python3 -m venv "${APP_DIR}/backend/.venv"
"${APP_DIR}/backend/.venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/backend/.venv/bin/python" -m pip install \
    --no-cache-dir \
    -r "${APP_DIR}/backend/requirements-cloud.txt"

ENV_FILE="${APP_DIR}/backend/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
    cat > "${ENV_FILE}" <<EOF
DATABASE_URL=sqlite:////var/lib/eye-care/eye_care.db
API_TOKEN=dev-token-change-me
DEMO_USERNAME=demo
DEMO_PASSWORD=demo123
CORS_ORIGINS=*
IOTDA_MOCK=true
IOTDA_APP_MQTT_ENABLED=false
LLM_API_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_MAX_TOKENS=420
LLM_TEMPERATURE=0.35
LOCAL_LLM_MODEL_PATH=
EOF
fi

chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"
chown "${SERVICE_USER}:${SERVICE_USER}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Eye Care Desk API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${APP_DIR}/backend
EnvironmentFile=${ENV_FILE}
ExecStart=${APP_DIR}/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

for _ in $(seq 1 30); do
    if curl --fail --silent http://127.0.0.1:8080/health >/dev/null; then
        echo
        echo "Eye Care cloud API is ready:"
        curl --silent http://127.0.0.1:8080/health
        echo
        exit 0
    fi
    sleep 1
done

echo "API health check failed." >&2
journalctl -u "${SERVICE_NAME}" --no-pager -n 80 >&2
exit 1
