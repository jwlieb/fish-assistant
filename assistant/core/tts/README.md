# TTS (Text-to-Speech) Adapters

The TTS component supports both local and remote synthesis adapters.

## Local Adapter (Default)

Uses `pyttsx3` to synthesize speech locally on the device.

```python
from assistant.core.tts.tts import TTS

# Uses local Pyttsx3Adapter by default
tts = TTS(bus)
```

**Pros:**
- No network dependency
- Works offline
- Fast for short texts

**Cons:**
- Requires system TTS engine
- Quality depends on system voices
- May be slow on low-power devices
- Not ideal for PocketBeagle (limited voices)

## Remote Adapter

Proxies synthesis requests to a remote server via HTTP.

```python
from assistant.core.tts.tts import TTS
from assistant.core.tts.remote_tts_adapter import RemoteTTSAdapter

# Use remote adapter
remote_adapter = RemoteTTSAdapter(
    server_url="http://localhost:8000",
    voice="default",
    timeout=30.0
)
tts = TTS(bus, adapter=remote_adapter)
```

**Pros:**
- Low memory footprint on device
- Can use high-quality cloud TTS (Google, Azure, AWS Polly)
- Suitable for PocketBeagle
- Better voice quality

**Cons:**
- Requires network connection
- Adds latency
- Requires server infrastructure

## Server API Specification

The remote adapter expects a server implementing:

**Endpoint:** `POST /api/tts/synthesize`

**Request:**
- Content-Type: `application/json`
- Body:
```json
{
  "text": "text to synthesize",
  "voice": "optional voice name"
}
```

**Response Options:**

### Option A: Binary WAV File (Recommended)
- Content-Type: `audio/wav`
- Body: Binary WAV file data

### Option B: JSON with URL
- Content-Type: `application/json`
- Body:
```json
{
  "wav_url": "http://server/path/to/file.wav"
}
```
The adapter will automatically download the file from the URL.

**Error Handling:**
- 4xx/5xx status codes will raise `httpx.HTTPStatusError`
- Network errors will raise `httpx.RequestError`
- Timeouts will raise `httpx.TimeoutException`

## Configuration

You can configure the adapter via environment variables or code:

```python
import os
from assistant.core.tts.remote_tts_adapter import RemoteTTSAdapter

server_url = os.getenv("TTS_SERVER_URL", "http://localhost:8000")
voice = os.getenv("TTS_VOICE", None)
adapter = RemoteTTSAdapter(server_url=server_url, voice=voice)
```

## Voice Selection

The `voice` parameter is optional and adapter-specific:
- **Local adapter**: Uses system voice names (e.g., "com.apple.voice.compact.en-GB.Daniel")
- **Remote adapter**: Uses server-defined voice names (depends on server implementation)

If `voice` is `None`, the adapter will use its default voice.

