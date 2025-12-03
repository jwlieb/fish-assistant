# Fish Assistant 🐟🐟🐟🐟🐟🐟🐟🐟🐟🐟

Personal voice assistant that may or may not be housed in a talking fish. Modular skills, wake-word, model routing, STT/TTS, more integrations to come. Perhaps singing or rap-battling.

Local-first with small, swappable adapters and a simple event bus.

---

## Status (MVP, in progress)

- Event contracts (`assistant/contracts.py`) with `topic`, `ts_ms`, `corr_id`.
- Async event bus that awaits subscribers (deterministic).
- Identity router (`assistant/router.py`): `nlu.intent → skill.request`, plus `skill.response.say → tts.request`.
- Rules-based NLU (`assistant/core/nlu/`) that classifies intents and extracts entities.
- STT integration (`assistant/core/stt/`) using faster-whisper for speech-to-text.
- Local TTS adapter (pyttsx3) → WAV with duration tracking.
- Playback adapter (sounddevice) emitting `audio.playback.start/end`.
- End-to-end pipeline: `audio.recorded → STT → NLU → Skills → TTS → Playback`.
- Smoke tests covering the full pipeline.

Next: **Conversation loop** with VAD for continuous listening.

---

## Quick start

### Full installation (development/testing)
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev,client,server]"    # Installs all dependencies
```

### Client mode (PocketBeagle - minimal footprint)
```bash
pip install -e ".[client]"      # Only client dependencies
```

### Server mode (laptop - with STT/TTS)
```bash
pip install -e ".[server]"      # Server dependencies (also needs client for HTTP)
# Or for full server: pip install -e ".[client,server]"
```

> Requirements: Python 3.10+ and FFmpeg headers (needed by `faster-whisper` / `av`).  
> On macOS with Homebrew: `brew install ffmpeg`

Use the CLI:

```bash
# Interactive mode (text input)
fish run

# Test full pipeline with audio recording
fish test:pipeline --duration 5

# List audio devices
fish audio:list

# Record and transcribe (direct STT test)
fish demo:record-and-transcribe --duration 5
```

Expected event flow (full pipeline):
```
audio.recorded → stt.transcript → nlu.intent → skill.request → skill.response → tts.request → tts.audio → audio.playback.start → audio.playback.end
```

> On macOS the player is `afplay`; on Linux, `aplay` (install `alsa-utils`).

---

## Repository map

```
assistant/
  app.py                # mode-aware wiring (dev/device), subscribers
  cli.py                # "fish" command (say/intent)
  core/
    bus.py              # async pub/sub (publish awaits; handlers can spawn background work)
    contracts.py        # event dataclasses (topics, ts_ms, corr_id)
    router.py           # identity routing + say→TTS
    audio/
      devices.py        # audio device enumeration
      playback.py       # play(wav_path) → start/end events
      recorder.py       # record audio → audio.recorded events
    nlu/
      nlu.py           # NLU component (listens on stt.transcript)
      rules.py         # rules-based intent classifier
      types.py         # NLU result types
    stt/
      stt.py           # STT component (listens on audio.recorded)
      whisper_adapter.py  # faster-whisper transcription
    tts/
      tts.py           # TTS component (listens on tts.request)
      pyttsx3_adapter.py  # local TTS synthesis
    memory/             # (later) conversation history
    ux/                 # (later) state + PTT/VAD
  skills/               # modular skills
tests/
```

---

## Architecture

```
audio.recorded ─► STT (whisper) ─► stt.transcript ─► NLU (rules) ─► nlu.intent ─► Router ─► skill.request
                                                                                              │
                                                                                              ▼
                                                                    tts.request ◄─ skill.response.say
                                                                          │
                                                             TTS (pyttsx3) ─► tts.audio ─► Playback ─► start/end
```

- Contracts are the stable surface; adapters are replaceable.
- `corr_id` traces a single interaction across all stages.

---

## Configuration

Fish Assistant supports configuration via environment variables or a `.env` file.

### Environment Variables

**STT (Speech-to-Text) Configuration:**
- `STT_MODE`: `"local"` (use faster-whisper) or `"remote"` (use HTTP server) - default: `"local"`
- `STT_SERVER_URL`: Remote STT server URL - default: `"http://localhost:8000"`
- `STT_MODEL_SIZE`: Model size for local STT - `"tiny"`, `"base"`, `"small"`, `"medium"` - default: `"tiny"`
- `STT_TIMEOUT`: Request timeout in seconds (remote only) - default: `30.0`

**TTS (Text-to-Speech) Configuration:**
- `TTS_MODE`: `"local"` (use pyttsx3) or `"remote"` (use HTTP server) - default: `"local"`
- `TTS_SERVER_URL`: Remote TTS server URL - default: `"http://localhost:8000"`
- `TTS_VOICE`: Voice name (optional, adapter-specific) - default: `None`
- `TTS_TIMEOUT`: Request timeout in seconds (remote only) - default: `30.0`

**Billy Bass Configuration:**
- `BILLY_BASS_ENABLED`: Enable motor control - `"true"` or `"false"` - default: `"true"`

### Example Configurations

**Local Development (everything runs locally):**
```bash
STT_MODE=local
STT_MODEL_SIZE=tiny
TTS_MODE=local
BILLY_BASS_ENABLED=false  # Disable if no hardware
```

**PocketBeagle (remote STT/TTS):**
```bash
STT_MODE=remote
STT_SERVER_URL=http://192.168.1.100:8000
TTS_MODE=remote
TTS_SERVER_URL=http://192.168.1.100:8000
BILLY_BASS_ENABLED=true
```

**Using .env file:**
Create a `.env` file in the project root (see `.env.example` for template):
```bash
STT_MODE=remote
STT_SERVER_URL=http://localhost:8000
TTS_MODE=remote
TTS_SERVER_URL=http://localhost:8000
```

### Programmatic Configuration

You can also configure adapters programmatically:
```python
from assistant.core.stt.stt import STT
from assistant.core.stt.remote_stt_adapter import RemoteSTTAdapter
from assistant.core.tts.tts import TTS
from assistant.core.tts.remote_tts_adapter import RemoteTTSAdapter

# Use remote adapters
stt_adapter = RemoteSTTAdapter(server_url="http://localhost:8000")
stt = STT(bus, adapter=stt_adapter)

tts_adapter = RemoteTTSAdapter(server_url="http://localhost:8000")
tts = TTS(bus, adapter=tts_adapter)
```

---

## Testing

```bash
# Run all tests
pytest -vv -s

# Run specific test suites
pytest -vv -s -k pipeline_smoke      # Full pipeline test (starts from stt.transcript)
pytest -vv -s tests/test_stt_integration.py  # STT component integration test

# Test with real audio (requires microphone)
fish test:pipeline --duration 5
```

What the tests prove:
- **test_pipeline_smoke**: `stt.transcript → nlu.intent → skill.request → skill.response → tts.request → tts.audio → audio.playback.start/end` with `corr_id` propagation
- **test_stt_integration**: `audio.recorded → stt.transcript` with STT component integration
- **test:pipeline CLI**: Full end-to-end test with real audio recording

---

## Development notes

- **Bus**: `publish()` awaits all subscribers via `asyncio.gather`. For long work (e.g., audio playback), publish a "start" event and then `asyncio.create_task(...)` the long operation; publish "end" when done.
- **STT**: Uses faster-whisper with VAD filtering. Transcription runs in thread pool via `asyncio.to_thread()` to avoid blocking the event loop. Model size defaults to "tiny" for speed.
- **TTS**: pyttsx3 runs in a thread via `asyncio.to_thread()`; pyttsx3 struggles when run in worker threads, needs hacky time.sleep
- **Playback**: Uses sounddevice (not playsound) for cross-platform audio playback. Cleans up temporary WAV files after playback.
- **Router**: identity mapping by default. Overrides can be registered:
  ```python
  router.register_intent("meteo", "weather")
  ```

---

## Roadmap

1. Core runtime ✅  
2. Audio I/O (local TTS + playback) ✅  
3. STT integration (Whisper) ✅  
4. Minimal NLU (rules-based) ✅  
5. Skills: time, timer, joke, weather(mock), music(stub)  
6. Conversation loop with VAD for continuous listening  
7. Conversation memory/context tracking  
8. Hardware: audio→mouth envelope, GPIO/PWM driver  
9. UX & controls: PTT/VAD, state broadcasts  
10. Persistence & config: KV, typed config, structured logging  
11. Reliability & tests: unit+integration, `-m hw`, latency notes  
12. Packaging & deploy: systemd service, device setup doc  
13. Privacy & safety: mic kill switch, log redaction

Target MVP feel:
- Query→speak P50 < 800 ms on a laptop (rules NLU, local TTS).
- Playback start < 150 ms after `tts.audio`.

---

## License

MIT
