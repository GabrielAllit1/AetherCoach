$ErrorActionPreference = "Stop"

python -m pip install -r requirements.txt
python -m pip install -r ..\requirements-dev.txt

python -m compileall .
python -m pytest ..\tests -q

pyinstaller `
  --name AetherCoach `
  --onefile `
  --windowed `
  --clean `
  --collect-all customtkinter `
  coach_app.py

Write-Host "Build complete: dist/AetherCoach.exe"
