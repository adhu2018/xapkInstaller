@echo off
chcp 65001
del /q .\venv\*.*
rd /s /q .\venv
py -3 -m venv venv&cd venv\Scripts&activate&cd ../..&python -m pip install -U pip&pip install -r requirements.txt&pip install pyinstaller&pyinstaller -F xapkInstaller.py -i NONE --clean