# AetherCoach

[![Quality](https://github.com/GabrielAllit1/AetherCoach/actions/workflows/quality.yml/badge.svg)](https://github.com/GabrielAllit1/AetherCoach/actions/workflows/quality.yml)

A local-first desktop coaching assistant that combines screen capture, OCR, and a locally hosted Ollama model to provide short, contextual feedback without sending screen content to a SALT19 cloud service.

> **Status:** Active public prototype, v1.1.0. Review the privacy notes and known limitations before use.

## What it demonstrates

- Local screen capture with `mss`
- OCR using Tesseract and OpenCV preprocessing
- Basic redaction before extracted text is passed to Ollama
- Multiple coaching modes for interviews, study, meetings, sales, confidence, and direct feedback
- Manual or interval-based analysis
- Local JSON session export
- Windows executable packaging with PyInstaller
- A loopback-only Ollama boundary that prevents configuration from redirecting OCR context to a remote host
- Concurrency protection for capture and analysis requests
- Automated compile and test checks through GitHub Actions

## Architecture

```text
Screen → local capture → OCR/preprocessing → basic redaction
       → local Ollama model → concise coaching feedback → local UI/export
```

The model receives extracted text rather than raw visual input. Ollama must be installed and running locally.

## Quick start

### Requirements

- Python 3.10+
- [Ollama](https://ollama.com/)
- Tesseract OCR
- A supported local model such as `llama3.2`, `mistral`, or `qwen2.5:7b`

### Run

```bash
git clone https://github.com/GabrielAllit1/AetherCoach.git
cd AetherCoach/aether_coach
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.2
python coach_app.py
```

Detailed setup and controls are documented in [aether_coach/README.md](aether_coach/README.md).

## Privacy and safety

AetherCoach is designed for local processing, but screen OCR can capture sensitive visible text. Basic pattern redaction is not a guarantee that all sensitive data will be removed.

- Do not use it on confidential, regulated, financial, medical, or authentication screens.
- Review locally exported session data before sharing it.
- The project does not claim that local processing eliminates all privacy risk.
- Coaching output is informational and should not replace qualified professional advice.
- The application locks its Ollama destination to `localhost`; remote model endpoints are intentionally unsupported.

## Known limitations

- OCR accuracy varies with resolution, scaling, font size, contrast, and window content.
- The model receives extracted text and does not perform general visual reasoning.
- Redaction is pattern-based and incomplete by design.
- Voice input is not part of the current product surface.

## Support continued development

AetherCoach is free and local-first. If it saves you time or helps you prepare, you can support continued independent development:

- [Buy Gabriel a coffee](https://buymeacoffee.com/salt19)
- [Explore SALT19 systems](https://salt19.com/founder)

Support is optional and does not unlock hidden functionality or transmit coaching data.

## Validation

```bash
python -m compileall aether_coach
python -m pytest -q
```

## Technology

Python · CustomTkinter · Ollama · Tesseract OCR · OpenCV · NumPy · MSS · PyInstaller

## Project links

- [SALT19](https://salt19.com)
- [Gabriel Allit — portfolio](https://salt19.com/founder)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## License

[MIT](LICENSE) © 2026 Gabriel V Allit
