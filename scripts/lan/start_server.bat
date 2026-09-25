@echo off
REM scripts\lan\start_server.bat
REM Starts the Solunex backend on the LAN server PC so every PC on the
REM router can reach it at http://<this PC's IP>:8000
REM One worker only: the sync agent runs inside this process.

cd /d "%~dp0\..\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
