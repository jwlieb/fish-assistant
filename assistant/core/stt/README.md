# STT (Speech-to-Text) Adapters

The STT component supports both local and remote transcription adapters.

## Local Adapter (Default)

Uses `faster-whisper` to run transcription locally on the device.

```python
from assistant.core.stt.stt import STT

# Uses local WhisperAdapter by default
stt = STT(bus, model_size="tiny")
```

**Pros:**
- No network dependency
- Works offline
- Fast for small models

**Cons:**
- Requires significant RAM (100-500MB+)
- CPU intensive
- Not suitable for PocketBeagle

## Remote Adapter

Proxies transcription requests to a remote server via HTTP.

```python
from assistant.core.stt.stt import STT
from assistant.core.stt.remote_stt_adapter import RemoteSTTAdapter

# Use remote adapter
remote_adapter = RemoteSTTAdapter(
    server_url="http://localhost:8000",
    model_size="tiny",
    timeout=30.0
)
stt = STT(bus, adapter=remote_adapter)
```

**Pros:**
- Low memory footprint on device
- Can use more powerful models
- Suitable for PocketBeagle

**Cons:**
- Requires network connection
- Adds latency
- Requires server infrastructure

## Server API Specification

The remote adapter expects a server implementing:

**Endpoint:** `POST /api/stt/transcribe`

**Request:**
- Content-Type: `multipart/form-data`
- Fields:
  - `audio`: WAV file (multipart file upload)
  - `model_size`: String ("tiny", "base", "small", "medium")

**Response:**
```json
{
  "text": "transcribed text here"
}
```

**Error Handling:**
- 4xx/5xx status codes will raise `httpx.HTTPStatusError`
- Network errors will raise `httpx.RequestError`
- Timeouts will raise `httpx.TimeoutException`

## Configuration

You can configure the adapter via environment variables or code:

```python
import os
from assistant.core.stt.remote_stt_adapter import RemoteSTTAdapter

server_url = os.getenv("STT_SERVER_URL", "http://localhost:8000")
adapter = RemoteSTTAdapter(server_url=server_url)
```

