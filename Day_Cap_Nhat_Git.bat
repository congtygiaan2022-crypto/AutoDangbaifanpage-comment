@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ====================================================
echo   DANG TU DONG DAY CAP NHAT LEN GITHUB...
echo ====================================================

rem Kiem tra thu muc Git
if not exist .git goto NO_GIT

rem Lay ngay gio hien tai
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set commit_msg=Auto-Update-%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%-%datetime:~8,2%-%datetime:~10,2%

echo.
echo [+] Buoc 1: Quet cac file thay doi...
git add .

echo [+] Buoc 2: Tao ban ghi commit...
git commit -m "%commit_msg%"

echo [+] Buoc 3: Day code len Github...
echo.
git branch -M main >nul 2>&1
git push origin main

if %errorlevel% neq 0 goto PUSH_ERROR

:PUSH_SUCCESS
echo ====================================================
echo   DA DAY BAN CAP NHAT LEN GITHUB THANH CONG
echo   Tat ca cac may con se tu dong duoc update khi mo tool
echo ====================================================
goto END

:PUSH_ERROR
echo ====================================================
echo   [LOI] Khong the day code len Github.
echo   Vui long kiem tra:
echo   1. Ket noi Internet cua ban.
echo   2. Ban da dang nhap Github tren may nay chua.
echo   3. May con co dang bi xung dot code conflict khong.
echo ====================================================
goto END

:NO_GIT
echo [LOI] Thu muc nay chua duoc khoi tao ket noi Git Repository
echo Vui long lam theo huong dan thiet lap ban dau truoc.
echo.

:END
echo.
echo Nhan phim bat ky de dong cua so nay.
pause >nul
