@echo off
pip install pyinstaller -q
python -m PyInstaller --onefile --name Dota2GSI --paths src --add-data "src/speak.ps1;src" --add-data "config.yaml;." --add-data "AIPromt.md;." --add-data "gamestate_integration_gsi_config.cfg;." --add-data "Dota2MechanismOntology;Dota2MechanismOntology" src/server.py
echo Done: dist\Dota2GSI.exe
