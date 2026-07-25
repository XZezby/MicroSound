@echo off
cd /d "%~dp0"
python install_dependencies.py
python microsound.py
