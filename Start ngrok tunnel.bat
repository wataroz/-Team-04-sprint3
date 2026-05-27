@echo off
echo ─────────────────────────────────────────────────
echo  MoneyMind – ngrok HTTPS tunnel
echo  Webhook URL จะเป็น:
echo  https://XXXX-XX-XX-XX-XX.ngrok-free.app/webhook/line
echo ─────────────────────────────────────────────────
echo.

:: ตรวจว่า ngrok อยู่ใน PATH
where ngrok >nul 2>&1
IF ERRORLEVEL 1 (
    echo [!] ไม่พบ ngrok ในระบบ
    echo     กรุณาดาวน์โหลดที่ https://ngrok.com/download
    echo     แล้ว unzip ไว้ใน C:\ngrok\ngrok.exe
    echo     จากนั้นเพิ่ม C:\ngrok ใน PATH
    echo     หรือวาง ngrok.exe ไว้ใน folder นี้แล้วรันใหม่
    pause
    exit /b 1
)

echo กำลังเปิด tunnel ไปที่ localhost:5000 ...
echo กด Ctrl+C เพื่อหยุด tunnel
echo.
ngrok http 5000
pause
