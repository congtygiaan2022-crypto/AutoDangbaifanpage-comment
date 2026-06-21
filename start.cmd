@echo off
cd /d "%~dp0"
pm2 start gui.py --name "Gams Auto Post Fanpage" --interpreter python
pause
