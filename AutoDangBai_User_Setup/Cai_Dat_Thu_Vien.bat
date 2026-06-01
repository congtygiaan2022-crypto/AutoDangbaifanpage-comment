@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ====================================================
echo   DANG TU DONG CAI DAT CAC THU VIEN BAT BUOC...
echo ====================================================
echo.

pip install -r requirements.txt

echo.
if %errorlevel% equ 0 (
    echo ====================================================
    echo   CAI DAT THU VIEN THANH CONG!
    echo   Bay gio ban co the mo file 'Chay_Tool.bat' de chay ung dung.
    echo ====================================================
) else (
    echo ====================================================
    echo   [LOI] Cai dat thu vien that bai.
    echo   Vui long kiem tra xem ban da cai dat Python (tich chon Add to PATH) chua.
    echo ====================================================
)

echo.
pause
