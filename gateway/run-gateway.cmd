@echo off
setlocal
set "SERIAL_PORT=AUTO"
set "BAUD_RATE=115200"
set "BACKEND_URL=http://127.0.0.1:8080"
set "API_TOKEN=dev-token-change-me"
set "DEVICE_ID=hi3861_001"
set "PYTHONIOENCODING=utf-8"
"%~dp0..\backend\.venv\Scripts\python.exe" "%~dp0serial_gateway.py"
pause
