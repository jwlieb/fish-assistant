# Fish Assistant 🐟🐟🐟🐟🐟🐟🐟🐟🐟🐟

Personal voice assistant that may or may not be housed in a talking fish. Modular skills, wake-word, model routing, STT/TTS, more integrations to come. Perhaps singing or rap-battling.

Local-first with small, swappable adapters and a simple event bus.

---

## Status (MVP, in progress)

- Event contracts (`assistant/contracts.py`) with `topic`, `ts_ms`, `corr_id`.
- Async event bus that awaits subscribers (deterministic).
- Identity router (`assistant/router.py`): `nlu.intent → skill.request`, plus `skill.response.say → tts.request`.
- Local TTS adapter (pyttsx3) → WAV with 0.0s guard.
- Playback adapter (system player) emitting `audio.playback.start/end`.
- End-to-end smoke test covering the path.

Next: minimal **rules-based NLU** that emits `nlu.intent`.

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Use the CLI:

```bash
fish run # simply wires to "echo" skill
```

Expected event flow:
```
tts.request → tts.audio → audio.playback.start → audio.playback.end
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
      devices.py        # devices
      playback.py       # play(wav_path) → start/end events
      recorder.py       # (stub)
    memory/             # (later)
    nlu/                # (later)
    ux/                 # (later) state + PTT/VAD
    tts/
        pyttsx3_adapter.py  # local TTS
    tts/
        whisper_adapter.py  # local STT
  skills/               # modular skills
tests/
```

---

## Architecture

```
stt.transcript ─► NLU (adapter) ─► nlu.intent ─► Router ─► skill.request
                                                     ▲            │
                                             tts.request ◄─ skill.response.say
                                                     │
                                        TTS (adapter) ─► tts.audio ─► Playback ─► start/end
```

- Contracts are the stable surface; adapters are replaceable.
- `corr_id` traces a single interaction across all stages.

---

## Configuration (TODO)

- `--mode` / `FISH_MODE`: `dev` (laptop) | `device` (PocketBeagle)
- `FISH_TTS`: `local` (pyttsx3) | `remote` (future)
- `FISH_PLAYBACK`: `system` | `alsa` (future)
- `FISH_TMP`: base temp directory (default `/tmp/fish`)

Example:
```bash
export FISH_MODE=dev
fish say "testing one two"
```

---

## Testing

```bash
pytest -vv -s
# or only the smoke test:
pytest -vv -s -k pipeline_smoke
```

What the smoke test proves:
- `nlu.intent → skill.request`
- (echo) `skill.response.say`
- `tts.request → tts.audio`
- `audio.playback.start → audio.playback.end`
- One `corr_id` flows end-to-end.

---

## Development notes

- **Bus**: `publish()` awaits all subscribers via `asyncio.gather`. For long work (e.g., audio playback), publish a “start” event and then `asyncio.create_task(...)` the long operation; publish “end” when done.
- **TTS**: pyttsx3 runs in a thread via `run_in_executor`; pyttsx3 struggles when run in worker threads, needs hacky time.sleep
- **Router**: identity mapping by default. Overrides can be registered:
  ```python
  router.register_intent("meteo", "weather")
  ```

---

## Roadmap

1. Core runtime ✅  
2. Audio I/O (local TTS + playback) ✅ in progress  
3. Minimal NLU (rules) → emit `nlu.intent`  
4. Skills: time, timer, joke, weather(mock), music(stub)  
5. Hardware: audio→mouth envelope, GPIO/PWM driver  
6. UX & controls: PTT/VAD, state broadcasts  
7. Persistence & config: KV, typed config, structured logging  
8. Reliability & tests: unit+integration, `-m hw`, latency notes  
9. Packaging & deploy: systemd service, device setup doc  
10. Privacy & safety: mic kill switch, log redaction

Target MVP feel:
- Query→speak P50 < 800 ms on a laptop (rules NLU, local TTS).
- Playback start < 150 ms after `tts.audio`.

---

## License

MIT
