@echo off
title Eye Care FastAPI
pushd "%~dp0"
echo ==========================================
echo Eye Care FastAPI
echo Local: http://127.0.0.1:8000/docs
echo LAN:   http://YOUR_PC_IP:8000
echo Keep this window open while using the App.
echo ==========================================
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
echo.
echo FastAPI stopped. Press any key to close.
pause >nul
popd
