@echo off
REM Runway product layer: double-click to start the approval queue (port 8000) and the UI (port 5173).
cd /d "%~dp0"

where python >nul 2>nul || (echo Python not found. Install Python 3.10+ from python.org and tick "Add python.exe to PATH", then run this again. & pause & exit /b 1)
where npm >nul 2>nul || (echo Node.js not found. Install the LTS version from nodejs.org, then run this again. & pause & exit /b 1)

if not exist "queue_service\.venv\Scripts\python.exe" (
  echo Creating Python environment...
  python -m venv "queue_service\.venv" || (echo Could not create venv. & pause & exit /b 1)
)
echo Installing Python packages...
"queue_service\.venv\Scripts\python.exe" -m pip install -q -r "queue_service\requirements.txt" || (echo pip install failed. & pause & exit /b 1)

REM Always check UI packages: teammates may have added new ones (fast when nothing changed).
echo Checking UI packages...
pushd frontend
call npm install --no-audit --no-fund || (echo npm install failed. & popd & pause & exit /b 1)
popd

start "Runway queue (port 8000)" /D "%~dp0queue_service" cmd /k ".venv\Scripts\python.exe -m uvicorn app:app --reload --host 0.0.0.0 --port 8000"
start "Runway UI (port 5173)" /D "%~dp0frontend" cmd /k "npm run dev"

echo Waiting for servers...
timeout /t 6 /nobreak >nul
start "" http://localhost:5173
echo.
echo Runway is starting in two new windows. Close those windows to stop it.
echo Teammates on the same Wi-Fi: http://YOUR-IP:8000  (run ipconfig to find your IPv4 address)
timeout /t 8 >nul
