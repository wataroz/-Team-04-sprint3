@echo off
setlocal
cd /d "%~dp0"

set URL=http://localhost:5000/
set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
set PYTHON=C:\Users\User\AppData\Local\Programs\Python\Python311\python.exe

rem Install Python deps on first run
%PYTHON% -c "import flask, pdfplumber, sqlalchemy, linebot, dotenv" 2>nul
if errorlevel 1 (
  echo Installing Python dependencies...
  %PYTHON% -m pip install -r requirements.txt
)

rem Copy .env.example to .env if .env doesn't exist yet
if not exist ".env" (
  echo [INFO] .env not found — copying .env.example to .env
  copy ".env.example" ".env" >nul
  echo [ACTION] กรุณาเปิดไฟล์ .env แล้วใส่ LINE tokens ของคุณครับ
)

rem Start the Flask server in a minimized window
start "MoneyMind server" /min cmd /c "%PYTHON% backend\app.py"

rem Give Flask a moment to bind the port
timeout /t 2 /nobreak >nul

rem Launch Chrome pointed at the app
%CHROME% --new-window "%URL%"

endlocal
