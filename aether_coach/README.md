# Aether Coach

Private real-time AI personal coach desktop app powered by local Ollama, screen capture, and OCR.

## What it does

- Captures your screen locally with `mss`
- Extracts visible text using Tesseract OCR + OpenCV preprocessing
- Sends redacted context to local Ollama
- Displays short coaching feedback in a discreet desktop UI
- Supports interview prep, study, meeting, sales, direct feedback, and confidence modes
- Exports session history as JSON

No cloud API is used by this app. Ollama must run locally.

## Install

### 1. Install Python
Use Python 3.10 or newer.

### 2. Install Ollama
Install Ollama, then run:

```bash
ollama serve
ollama pull llama3.2
```

Other good local models:

```bash
ollama pull mistral
ollama pull qwen2.5:7b
ollama pull phi3:medium
```

### 3. Install Tesseract OCR

Windows:
- Install from the official Tesseract Windows installer.
- Default path usually is: `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Optional: set `TESSERACT_CMD` environment variable to that path.

Ubuntu/Debian:

```bash
sudo apt install tesseract-ocr
```

macOS:

```bash
brew install tesseract
```

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 5. Run

```bash
python coach_app.py
```

## Windows executable build

From PowerShell:

```powershell
./build_windows.ps1
```

The EXE will be created under `dist/AetherCoach.exe`.

## Privacy notes

Aether Coach runs locally, but screen OCR can still capture sensitive visible text. The app includes basic redaction for emails, card-like numbers, and SSN-like patterns before sending context to Ollama. Do not use it on screens containing highly sensitive records unless you accept that local processing risk.

## Controls

- Start Monitoring: captures screen every selected interval.
- Pause: stops analysis without closing the app.
- Manual Analyze Now: runs one capture immediately.
- Copy Latest Feedback: copies the latest coach output.
- Export JSON Session: saves a local session log.

## Known limits

- OCR quality depends on screen resolution, font size, contrast, and window scaling.
- The model only receives extracted text, not raw visual reasoning.
- PyAudio installation can require OS audio build tools. Microphone input is included as a dependency path but not enabled in v1 UI.
