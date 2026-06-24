@echo off
pip install pyinstaller -q
python -m PyInstaller --onefile --name Dota2GSI --paths src --add-data "src/speak.ps1;src" --add-data "config.yaml;." --add-data "AIPromt.md;." src/server.py
echo Done: dist\Dota2GSI.exe
