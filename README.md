# Fish Assistant 🐟🐟🐟🐟🐟🐟🐟🐟🐟🐟
Personal voice assistant that may or may not be housed in a talking fish. Modular skills, wake-word, model routing, STT/TTS, more integrations to come. Perhaps singing or rap-battling.

## Features
- Modular skills (`skills/*`)
- Router to delegate across models
- On‑device STT/TTS


## Quickstart
```bash
# Setup venv
python -m venv .venv && source .venv/bin/activate
pip install -e .


# Run the demo (record and transcribe audio)
fish demo:record-and-transcribe