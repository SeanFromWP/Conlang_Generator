@echo off
chcp 65001 >nul

cd /d "%~dp0"

echo 正在同步 Flask 環境與 YAML 插件...
python -m pip install -r requirements.txt --quiet --upgrade

cd "src\conlang"
start /b python app.py
timeout /t 2 >nul
start http://127.0.0.1:5000