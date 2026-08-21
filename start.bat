@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtualenv...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create .venv — is Python installed?
    pause
    exit /b 1
  )
  echo Installing dependencies...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo.
echo Opening Job Agent UI...
echo Use the START SEARCH button inside the page.
echo.
".venv\Scripts\python.exe" -m streamlit run ui/app.py

pause
