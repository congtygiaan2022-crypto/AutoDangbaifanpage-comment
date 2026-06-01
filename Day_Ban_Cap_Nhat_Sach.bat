@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
python git_dev_push.py
