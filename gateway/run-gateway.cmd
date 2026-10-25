@echo off
setlocal
set "SERIAL_PORT=AUTO"
set "BAUD_RATE=115200"
set "BACKEND_URL=http://127.0.0.1:8000"
set "API_TOKEN=dev-token-change-me"
set "DEVICE_ID=hi3861_001"
set "PYTHONIOENCODING=utf-8"
"D:\eye-care\backend\.venv\Scripts\python.exe" "D:\eye-care\gateway\serial_gateway.py"
pause
