@echo off
pip install pyinstaller -q
python -m PyInstaller --onefile --name Dota2GSI --paths src --add-data "src/speak.ps1;src" --add-data "gamestate_integration_gsi_config.cfg;." src/server.py
copy /Y config.yaml dist\config.yaml
copy /Y AIPromt.md dist\AIPromt.md
xcopy /Y /E /I Dota2MechanismOntology dist\Dota2MechanismOntology
echo Done: dist\Dota2GSI.exe + dist\config.yaml + dist\AIPromt.md + dist\Dota2MechanismOntology
