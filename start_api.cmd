@echo off
setlocal
cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8000"
set "PYTHON=python"

if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

echo Starting UN WebTV API at http://%HOST%:%PORT%
"%PYTHON%" -m uvicorn main:app --host %HOST% --port %PORT%

if errorlevel 1 (
  echo.
  echo API stopped with an error. Check Python dependencies and try again.
  pause
)

endlocal
