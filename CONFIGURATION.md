# Configuration Guide

Fish Assistant supports flexible configuration for switching between local and remote adapters.

## Quick Start

1. **Local Development** (default): Everything runs locally
   ```bash
   # No configuration needed - uses defaults
   fish run
   ```

2. **PocketBeagle** (remote STT/TTS):
   ```bash
   export STT_MODE=remote
   export STT_SERVER_URL=http://192.168.1.100:8000
   export TTS_MODE=remote
   export TTS_SERVER_URL=http://192.168.1.100:8000
   fish run
   ```

3. **Using .env file**:
   ```bash
   # Create .env file
   cp .env.example .env
   # Edit .env with your settings
   fish run
   ```

## Configuration Options

### STT (Speech-to-Text)

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `STT_MODE` | `local`, `remote` | `local` | Use local Whisper or remote server |
| `STT_SERVER_URL` | URL string | `http://localhost:8000` | Remote STT server URL |
| `STT_MODEL_SIZE` | `tiny`, `base`, `small`, `medium` | `tiny` | Whisper model size (local only) |
| `STT_TIMEOUT` | Float (seconds) | `30.0` | Request timeout (remote only) |

### TTS (Text-to-Speech)

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `TTS_MODE` | `local`, `remote` | `local` | Use local pyttsx3 or remote server |
| `TTS_SERVER_URL` | URL string | `http://localhost:8000` | Remote TTS server URL |
| `TTS_VOICE` | String or empty | `None` | Voice name (adapter-specific) |
| `TTS_TIMEOUT` | Float (seconds) | `30.0` | Request timeout (remote only) |

### Billy Bass

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `BILLY_BASS_ENABLED` | `true`, `false` | `true` | Enable motor control |

## Configuration Modes

### Mode 1: Local (Default)

Everything runs on the local machine. Good for development and testing.

```bash
# No configuration needed, or explicitly:
STT_MODE=local
TTS_MODE=local
```

**Pros:**
- No network dependency
- Works offline
- Fast iteration

**Cons:**
- Requires significant RAM for STT
- May be slow on low-power devices

### Mode 2: Hybrid (Recommended for PocketBeagle)

STT and TTS run remotely, everything else local.

```bash
STT_MODE=remote
STT_SERVER_URL=http://your-server:8000
TTS_MODE=remote
TTS_SERVER_URL=http://your-server:8000
```

**Pros:**
- Low memory footprint on device
- Can use powerful models
- Suitable for PocketBeagle

**Cons:**
- Requires network connection
- Requires server infrastructure

### Mode 3: Custom

Mix and match as needed.

```bash
# Remote STT, local TTS
STT_MODE=remote
STT_SERVER_URL=http://your-server:8000
TTS_MODE=local

# Or local STT, remote TTS
STT_MODE=local
TTS_MODE=remote
TTS_SERVER_URL=http://your-server:8000
```

## Environment Variables vs .env File

### Environment Variables

Set in your shell:
```bash
export STT_MODE=remote
export STT_SERVER_URL=http://localhost:8000
fish run
```

### .env File

Create a `.env` file in the project root:
```bash
STT_MODE=remote
STT_SERVER_URL=http://localhost:8000
TTS_MODE=remote
TTS_SERVER_URL=http://localhost:8000
```

The `.env` file is automatically loaded if `python-dotenv` is installed (it's in dependencies).

## Verification

When you start the assistant, it will print the current configuration:

```
🐟 Fish Assistant Configuration:
  STT Mode: remote
    Server: http://localhost:8000
    Model: tiny
    Timeout: 30.0s
  TTS Mode: remote
    Server: http://localhost:8000
    Voice: default
    Timeout: 30.0s
  Billy Bass: enabled
```

## Troubleshooting

### Remote adapters not working?

1. **Check server URL**: Make sure `STT_SERVER_URL` and `TTS_SERVER_URL` are correct
2. **Check network**: Test with `curl`:
   ```bash
   curl http://your-server:8000/api/stt/transcribe
   ```
3. **Check logs**: Look for connection errors in the logs
4. **Check timeout**: Increase `STT_TIMEOUT` or `TTS_TIMEOUT` if requests are timing out

### Local adapters not working?

1. **STT**: Make sure `faster-whisper` is installed and you have enough RAM
2. **TTS**: Make sure `pyttsx3` is installed and system TTS is available
3. **Check logs**: Look for import errors or initialization failures

### Configuration not taking effect?

1. **Check .env file**: Make sure it's in the project root
2. **Check environment variables**: Use `printenv | grep STT` to verify
3. **Restart**: Make sure you restart the application after changing config

## Advanced: Programmatic Configuration

You can also configure adapters programmatically in your code:

```python
from assistant.core.config import Config
from assistant.core.stt.stt import STT
from assistant.core.tts.tts import TTS

# Override config
Config.STT_MODE = "remote"
Config.STT_SERVER_URL = "http://custom-server:8000"

# Get adapters
stt_adapter = Config.get_stt_adapter()
tts_adapter = Config.get_tts_adapter()

# Use in components
stt = STT(bus, adapter=stt_adapter)
tts = TTS(bus, adapter=tts_adapter)
```

