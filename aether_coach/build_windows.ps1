$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

pyinstaller `
  --name AetherCoach `
  --onefile `
  --windowed `
  --clean `
  --collect-all customtkinter `
  coach_app.py

Write-Host "Build complete: dist/AetherCoach.exe"
