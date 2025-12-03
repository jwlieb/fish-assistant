# Fish Assistant 🐟🐟🐟🐟🐟🐟🐟🐟🐟🐟

Personal voice assistant that may or may not be housed in a talking fish. Modular skills, wake-word, model routing, STT/TTS, more integrations to come. Perhaps singing or rap-battling.

Local-first with small, swappable adapters and a simple event bus.

For hardware setup, go here: https://www.hackster.io/jwlieb/big-mouth-billy-bass-personal-assistant-a23f66

---

## Status

- Event contracts (`assistant/contracts.py`) with `topic`, `ts_ms`, `corr_id`.
- Async event bus that awaits subscribers (deterministic).
- Identity router (`assistant/router.py`): `nlu.intent → skill.request`, plus `skill.response.say → tts.request`.
- Rules-based NLU (`assistant/core/nlu/`) that classifies intents and extracts entities.
- STT integration (`assistant/core/stt/`) using faster-whisper for speech-to-text.
- Local TTS adapter (pyttsx3) → WAV with duration tracking.
- Playback adapter (sounddevice) emitting `audio.playback.start/end`.
- End-to-end pipeline: `audio.recorded → STT → NLU → Skills → TTS → Playback`.
- **Server-client architecture** for distributed deployment (laptop + PocketBeagle).
- **Conversation loop** with VAD for continuous listening.
- **Billy Bass motor control** with GPIO/PWM synchronization.
- Smoke tests covering the full pipeline.

---

## Quick start

### Fastest Setup (Server-Client Mode)

**For live testing with PocketBeagle + laptop, see [QUICKSTART.md](QUICKSTART.md)**

```bash
# On laptop (server)
./scripts/setup-env.sh server
pip install -e ".[server]"
fish server --port 8000

# On PocketBeagle (client)
./scripts/setup-env.sh client
pip install -e ".[client]"
fish client --port 8001
```

### Installation Options

**Full installation (development/testing):**
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev,client,server]"    # Installs all dependencies
```

**Client mode (PocketBeagle - minimal footprint):**
```bash
pip install -e ".[client]"      # Only client dependencies
```

**Server mode (laptop - with STT/TTS):**
```bash
pip install -e ".[server]"      # Server dependencies (includes HTTP server)
```

> Requirements: Python 3.10+ and FFmpeg headers (needed by `faster-whisper` / `av`).  
> On macOS with Homebrew: `brew install ffmpeg`

### CLI Commands

**Full mode (everything local):**
```bash
fish run                    # Interactive mode (text input)
fish converse               # Continuous conversation loop with VAD
fish test:pipeline          # Test full pipeline with audio recording
```

**Server mode (laptop with HTTP API):**
```bash
fish server --port 8000 [--client-url http://<client-ip>:8001]
```

**Client mode (PocketBeagle with playback + motors):**
```bash
fish client --port 8001
```

**Utility commands:**
```bash
fish audio:list             # List audio devices
fish demo:record-and-transcribe --duration 5  # Record and transcribe
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
  app.py                # mode-aware component wiring (full/server/client)
  cli.py                # "fish" command (run/server/client/converse)
  server.py             # FastAPI HTTP server (STT/TTS endpoints)
  client_server.py       # FastAPI HTTP client (audio playback endpoint)
  core/
    bus.py              # async pub/sub (publish awaits; handlers can spawn background work)
    contracts.py        # event dataclasses (topics, ts_ms, corr_id)
    config.py           # configuration management
    router.py           # identity routing + say→TTS
    audio/
      devices.py        # audio device enumeration
      playback.py       # play(wav_path) → start/end events
      recorder.py        # record audio → audio.recorded events
      billy_bass.py      # GPIO/PWM motor control
      client_push.py     # server-to-client audio push service
    nlu/
      nlu.py           # NLU component (listens on stt.transcript)
      rules.py         # rules-based intent classifier
      types.py         # NLU result types
    stt/
      stt.py           # STT component (listens on audio.recorded)
      whisper_adapter.py  # faster-whisper transcription
      remote_stt_adapter.py  # HTTP STT adapter
    tts/
      tts.py           # TTS component (listens on tts.request)
      pyttsx3_adapter.py  # local TTS synthesis
      remote_tts_adapter.py  # HTTP TTS adapter
    ux/
      conversation_loop.py  # VAD-based continuous listening
  skills/               # modular skills
scripts/                # helper scripts (setup-env.sh, find-ips.sh)
tests/                  # test suite
```

---

## Architecture

### Full Mode (Everything Local)
```
audio.recorded ─► STT (whisper) ─► stt.transcript ─► NLU (rules) ─► nlu.intent ─► Router ─► skill.request
                                                                                              │
                                                                                              ▼
                                                                    tts.request ◄─ skill.response.say
                                                                          │
                                                             TTS (pyttsx3) ─► tts.audio ─► Playback ─► start/end
```

### Server-Client Mode (Distributed)
```
┌─────────────────────────────────┐         ┌──────────────────────────────────┐
│  Server (Laptop)                │         │  Client (PocketBeagle)            │
│                                 │         │                                  │
│  Microphone ─► STT ─► NLU ─►   │  HTTP   │  HTTP                            │
│  Skills ─► TTS ─► [Push Audio] ─┼────────►│  /api/audio/play ─► Playback ─► │
│                                 │         │  Billy Bass Motors               │
└─────────────────────────────────┘         └──────────────────────────────────┘
```

- Contracts are the stable surface; adapters are replaceable.
- `corr_id` traces a single interaction across all stages.
- Server-client split enables heavy computation on laptop, lightweight playback on PocketBeagle.

---

## Configuration

Fish Assistant supports configuration via environment variables or a `.env` file.

**Quick setup:** Use `./scripts/setup-env.sh` to create `.env` files interactively.

### Environment Variables

**Deployment Mode:**
- `DEPLOYMENT_MODE`: `"full"`, `"server"`, or `"client"` - default: `"full"`
- `SERVER_HOST`: Server bind host - default: `"0.0.0.0"`
- `SERVER_PORT`: Server port - default: `8000`
- `CLIENT_SERVER_URL`: Client URL for server to push audio (server mode only)

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

**Server Mode (Laptop):**
```bash
DEPLOYMENT_MODE=server
CLIENT_SERVER_URL=http://192.168.1.50:8001
STT_MODE=local
TTS_MODE=local
BILLY_BASS_ENABLED=false
```

**Client Mode (PocketBeagle):**
```bash
DEPLOYMENT_MODE=client
STT_MODE=remote
STT_SERVER_URL=http://192.168.1.100:8000
TTS_MODE=remote
TTS_SERVER_URL=http://192.168.1.100:8000
BILLY_BASS_ENABLED=true
```

**Full Mode (Local Development):**
```bash
DEPLOYMENT_MODE=full
STT_MODE=local
TTS_MODE=local
BILLY_BASS_ENABLED=false  # Disable if no hardware
```

See [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration options.

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
pytest tests/ -v

# Run specific test suites
pytest tests/ -v -k pipeline_smoke      # Full pipeline test
pytest tests/test_server_endpoints.py -v  # Server API tests
pytest tests/test_client_endpoint.py -v  # Client API tests
pytest tests/test_client_push.py -v      # Client push service tests

# Test with real audio (requires microphone)
fish test:pipeline --duration 5
```

What the tests prove:
- **Server endpoints**: STT/TTS HTTP API functionality
- **Client endpoints**: Audio playback API
- **Client push**: Server-to-client audio push service
- **Component modes**: Full/server/client mode initialization
- **Remote adapters**: STT/TTS remote adapter functionality
- **Pipeline**: End-to-end event flow with `corr_id` propagation

See [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) for comprehensive test scenarios.

---

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Fast setup guide for server-client mode
- **[DEMO.md](DEMO.md)** - Complete demo guide with hardware wiring
- **[CONFIGURATION.md](CONFIGURATION.md)** - Detailed configuration options
- **[ARCHITECTURE_POCKETBEAGLE.md](ARCHITECTURE_POCKETBEAGLE.md)** - Architecture decisions
- **[TESTING_CHECKLIST.md](TESTING_CHECKLIST.md)** - Comprehensive testing guide

## Development notes

- **Bus**: `publish()` awaits all subscribers via `asyncio.gather`. For long work (e.g., audio playback), publish a "start" event and then `asyncio.create_task(...)` the long operation; publish "end" when done.
- **STT**: Uses faster-whisper with VAD filtering. Transcription runs in thread pool via `asyncio.to_thread()` to avoid blocking the event loop. Model size defaults to "tiny" for speed.
- **TTS**: pyttsx3 runs in a thread via `asyncio.to_thread()`. Remote TTS adapters use HTTP to call server endpoints.
- **Playback**: Uses sounddevice (not playsound) for cross-platform audio playback. Cleans up temporary WAV files after playback.
- **Server-Client**: Server pushes TTS audio to client via HTTP POST when `CLIENT_SERVER_URL` is configured.
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
5. Server-client architecture ✅  
6. Conversation loop with VAD ✅  
7. Billy Bass motor control ✅  
8. Skills: time, timer, joke, weather(mock), music(stub)  
9. Conversation memory/context tracking  
10. UX & controls: PTT/VAD, state broadcasts  
11. Persistence & config: KV, typed config, structured logging  
12. Packaging & deploy: systemd service, device setup doc  
13. Privacy & safety: mic kill switch, log redaction

Target MVP feel:
- Query→speak P50 < 800 ms on a laptop (rules NLU, local TTS).
- Playback start < 150 ms after `tts.audio`.

---

## License

MIT
