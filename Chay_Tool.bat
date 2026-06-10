@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ====================================================
echo   DANG TU DONG DONG BO VA TAI PHAN MEM MOI TINH...
echo ====================================================
echo.

python launcher_git.py

if %errorlevel% neq 0 (
    echo.
    echo ====================================================
    echo   [LOI] Khong the khoi chay Tool.
    echo   Vui long kiem tra:
    echo   1. May tinh da cai dat Python (tich chon Add to PATH) chua.
    echo   2. May tinh da cai dat phan mem Git chua.
    echo   3. Da chay file 'Cai_Dat_Thu_Vien.bat' truoc do chua.
    echo ====================================================
    echo.
    pause
)
