@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ====================================================
echo   DANG CHUAN BI VA DAY CAP NHAT CHO MAY CON (CLIENT)...
echo ====================================================

set REPO_DIR=AutoDangbaifanpage-comment
set REPO_URL=https://github.com/congtygiaan2022-crypto/AutoDangbaifanpage-comment.git

rem 1. Kiem tra va clone neu chua co repo
if not exist "%REPO_DIR%\.git" (
    echo [+] Thu muc %REPO_DIR% chua co Git. Dang tien hanh tai ve tu Github...
    
    rem Neu thu muc da co nhung trong, ta co the xoa di de git clone chay khong loi
    if exist "%REPO_DIR%" rmdir /s /q "%REPO_DIR%"
    
    git clone %REPO_URL% %REPO_DIR%
    if %errorlevel% neq 0 (
        echo [LOI] Khong the clone repository tu %REPO_URL%
        goto END
    )
)

echo.
echo [+] Sao chep cac file code sang thu muc cap nhat...
copy /y gui.py "%REPO_DIR%\"
copy /y page_worker.py "%REPO_DIR%\"
copy /y database.py "%REPO_DIR%\"
copy /y db_helper.py "%REPO_DIR%\"
copy /y facebook_automator.py "%REPO_DIR%\"
copy /y gemlogin_api.py "%REPO_DIR%\"
copy /y gpmlogin_api.py "%REPO_DIR%\"
copy /y requirements.txt "%REPO_DIR%\"
copy /y Chay_Chuong_Trinh.bat "%REPO_DIR%\"
copy /y Chay_Khong_CMD.pyw "%REPO_DIR%\"
copy /y launcher_git.py "%REPO_DIR%\"
copy /y HUONG_DAN_CAI_DAT.md "%REPO_DIR%\"
copy /y HUONG_DAN_CAI_DAT.txt "%REPO_DIR%\"
copy /y .gitignore "%REPO_DIR%\"

rem 2. Tien hanh add, commit va push
cd %REPO_DIR%
echo.
echo [+] Dang quet thay doi cua may con...
git add .

rem Lay ngay gio hien tai
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set commit_msg=Update-Client-%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%-%datetime:~8,2%-%datetime:~10,2%

echo [+] Dang tao commit...
git commit -m "%commit_msg%"

echo [+] Dang day cap nhat len Github may con...
git push origin main

if %errorlevel% neq 0 goto PUSH_ERROR

:PUSH_SUCCESS
echo ====================================================
echo   DA DAY CAP NHAT LEN GITHUB MAY CON THANH CONG!
echo   Tat ca may con khi chay "launcher_git.py" se tu cap nhat.
echo ====================================================
goto END

:PUSH_ERROR
echo ====================================================
echo   [LOI] Khong the day code len Github cho may con.
echo   Vui long kiem tra ket noi mang va quyen ghi vao repository.
echo ====================================================
goto END

:END
cd ..
echo.
echo Nhan phim bat ky de dong cua so nay.
pause >nul
