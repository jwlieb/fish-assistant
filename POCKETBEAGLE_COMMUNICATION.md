# How to Build Laptop-Beagle Communication

This guide demonstrates a practical pattern for offloading compute-intensive tasks from a PocketBeagle to a more powerful laptop/server. This pattern is useful for any PocketBeagle project that needs to balance real-time hardware control with heavy processing.

## Understanding the Communication Flow

There are two directions of communication:

1. **PocketBeagle → Laptop (Request-Response)**: PocketBeagle sends files/data to laptop for processing
   - Uses `SERVICE_SERVER_URL` (points to laptop, e.g., `http://192.168.6.1:8000`)
   - PocketBeagle makes HTTP requests to laptop endpoints

2. **Laptop → PocketBeagle (Push)**: Laptop sends processed results back to PocketBeagle
   - Uses `CLIENT_SERVER_URL` (points to PocketBeagle, e.g., `http://192.168.6.2:8001`)
   - Laptop makes HTTP requests to PocketBeagle endpoints

**IP Addresses (macOS USB connection):**
- PocketBeagle: `192.168.6.2` (default when connected via USB)
- Laptop: `192.168.6.1` (on the USB network)

## Frameworks & Libraries

**Server Side (Laptop):**
- **FastAPI**: Modern async web framework for HTTP endpoints
- **Uvicorn**: ASGI server for running FastAPI
- Any compute service (ML models, image processing, data analysis, etc.)

**Client Side (PocketBeagle):**
- **httpx**: Async HTTP client library (lighter than requests)
- **asyncio**: Python's async/await framework
- Hardware-specific libraries (GPIO, PWM, sensors, etc.)

## Step 1: Set Up the Server (Laptop)

Create a FastAPI server with endpoints for your compute services:

```python
# server.py
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
import tempfile
import os

app = FastAPI()

@app.post("/api/process/file")
async def process_file(
    file: UploadFile = File(...),
    options: str = Form(default="default")
):
    """Process any file type and return result."""
    # Save uploaded file temporarily
    suffix = os.path.splitext(file.filename)[1] if file.filename else ""
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    
    try:
        # Save uploaded content
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Call your processing service
        result = your_service.process(temp_path, options)
        
        # Return result (could be JSON, file, or both)
        if isinstance(result, dict):
            return JSONResponse(content=result)
        else:
            # Return processed file
            return FileResponse(
                result,
                media_type=file.content_type,
                filename=f"processed_{file.filename}"
            )
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/api/process/data")
async def process_data(request: dict):
    """Process JSON data and return result."""
    input_data = request.get("data")
    options = request.get("options", {})
    
    # Call your processing service
    result = your_service.process_data(input_data, options)
    
    return JSONResponse(content={"result": result})
```

Run the server:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Step 2: Make HTTP Requests from Client (PocketBeagle)

Call the server endpoints from your PocketBeagle client code:

### Upload File for Processing

```python
# client.py
import httpx
import asyncio
from pathlib import Path

async def process_file_remote(file_path: str, server_url: str = "http://192.168.6.1:8000"):
    """Upload file to server for processing."""
    api_url = f"{server_url}/api/process/file"
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            data = {"options": "default"}
            
            response = await client.post(api_url, files=files, data=data)
            response.raise_for_status()
            
            # Check if response is JSON or file
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return response.json()
            else:
                # Save response as file
                import tempfile
                import os
                fd, out_path = tempfile.mkstemp(suffix=file_path.suffix)
                os.close(fd)
                with open(out_path, "wb") as out_file:
                    out_file.write(response.content)
                return out_path

# Usage
result = asyncio.run(process_file_remote("sensor_data.csv"))
```

### Send JSON Data for Processing

```python
async def process_data_remote(data: dict, server_url: str = "http://192.168.6.1:8000"):
    """Send JSON data to server for processing."""
    api_url = f"{server_url}/api/process/data"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {"data": data, "options": {}}
        
        response = await client.post(api_url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        return result.get("result")

# Usage
sensor_readings = {"temperature": 25.3, "humidity": 60.2}
result = asyncio.run(process_data_remote(sensor_readings))
```

## Step 3: Set Up Client Endpoint (PocketBeagle)

Create a FastAPI endpoint to receive pushed data/files from the server:

```python
# client_server.py
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import tempfile
import os
from your_event_bus import Bus  # Your event system

app = FastAPI()
bus = Bus()  # Your event bus instance

@app.post("/api/receive/file")
async def receive_file(file: UploadFile = File(...)):
    """Receive file and process locally."""
    # Save uploaded file
    suffix = os.path.splitext(file.filename)[1] if file.filename else ""
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    
    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Publish event to trigger local processing
        await bus.publish("file.received", {
            "path": temp_path,
            "filename": file.filename,
            "content_type": file.content_type
        })
        
        return JSONResponse(content={
            "status": "ok",
            "message": "File received",
            "path": temp_path
        })
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

@app.post("/api/receive/data")
async def receive_data(request: dict):
    """Receive JSON data and process locally."""
    data = request.get("data")
    
    # Publish event to trigger local processing
    await bus.publish("data.received", {"data": data})
    
    return JSONResponse(content={"status": "ok", "message": "Data received"})
```

## Step 4: Implement Server-to-Client Push (Optional)

If the server needs to push data/files to the client:

```python
# client_push.py
import httpx
import os
from pathlib import Path
from typing import Union, Optional

class ClientPush:
    """Push files or data from server to client."""
    
    def __init__(self, client_url: str, timeout: float = 30.0):
        self.client_url = client_url.rstrip('/')
        self.timeout = timeout
    
    async def push_file(self, file_path: Union[str, Path], endpoint: str = "/api/receive/file"):
        """Push file to client."""
        api_url = f"{self.client_url}{endpoint}"
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                response = await client.post(api_url, files=files)
                response.raise_for_status()
                return response.json()
    
    async def push_data(self, data: dict, endpoint: str = "/api/receive/data"):
        """Push JSON data to client."""
        api_url = f"{self.client_url}{endpoint}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {"data": data}
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            return response.json()
```

## Step 5: Configuration

Use environment variables to configure server URLs. There are two different URLs depending on the direction of communication:

**SERVICE_SERVER_URL** (used by PocketBeagle): The URL of your laptop/server that provides compute services. The PocketBeagle connects TO this URL to request processing.

**CLIENT_SERVER_URL** (used by laptop/server): The URL of your PocketBeagle client. The server connects TO this URL to push data/files back to the PocketBeagle.

```python
# config.py
import os

# URL of the server (laptop) - used by PocketBeagle to request processing
SERVICE_SERVER_URL = os.getenv("SERVICE_SERVER_URL", "http://192.168.6.1:8000")

# URL of the client (PocketBeagle) - used by server to push data back
# Only needed if server needs to push data to PocketBeagle
CLIENT_SERVER_URL = os.getenv("CLIENT_SERVER_URL", "http://192.168.6.2:8001")
```

```python
# app.py on PocketBeagle - Use SERVICE_SERVER_URL
from config import SERVICE_SERVER_URL

# Call remote service on laptop
result = await process_file_remote("data.csv", server_url=SERVICE_SERVER_URL)
```

```python
# app.py on Laptop - Use CLIENT_SERVER_URL for pushing
from config import CLIENT_SERVER_URL
from client_push import ClientPush

# Push data to PocketBeagle
pusher = ClientPush(client_url=CLIENT_SERVER_URL)
await pusher.push_file("processed_data.csv")
```

## Step 6: Handle Async Context Properly

When calling async HTTP from sync code (common in event handlers):

```python
# Option 1: Use asyncio.to_thread() for blocking operations
import asyncio

async def handle_file_event(file_path: str):
    # Run blocking HTTP call in thread pool
    result = await asyncio.to_thread(
        adapter.process, file_path
    )

# Option 2: Make adapter fully async
async def handle_file_event(file_path: str):
    result = await adapter.process_async(file_path)
```

## Error Handling Best Practices

```python
import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)

async def process_with_retry(file_path: str, max_retries: int = 3):
    """Process with retry logic and exponential backoff."""
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # ... make request ...
                return result
        except httpx.TimeoutException:
            logger.warning(f"Timeout (attempt {attempt + 1}/{max_retries})")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:  # Server error
                logger.warning(f"Server error (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            raise  # Client errors (4xx) don't retry
        except httpx.RequestError as e:
            logger.error(f"Network error: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

## Network Considerations

### Latency Optimization
- Use connection pooling (httpx.AsyncClient as context manager)
- Keep server and client on same local network
- Consider WebSocket for lower latency (upgrade path)
- Batch multiple requests when possible

### Bandwidth
- File sizes vary by use case (images: 100KB-5MB, audio: 50-200KB, data: <10KB)
- Consider compression for large files (gzip, zstd)
- Stream large files instead of loading entirely into memory
- Use chunked uploads for files >10MB

### Reliability
- Set appropriate timeouts (30s default, adjust based on operation)
- Implement retry logic with exponential backoff
- Handle offline scenarios gracefully
- Use health check endpoints (`/health`)
- Monitor connection quality and adjust retry strategy

### Security
- Use HTTPS in production
- Implement authentication (API keys, tokens)
- Validate file types and sizes on server
- Sanitize file paths and names
- Rate limit endpoints to prevent abuse

## Complete Example: Configuration Files

```bash
# .env file on PocketBeagle (192.168.6.2)
# Points to the laptop/server for processing requests
SERVICE_SERVER_URL=http://192.168.6.1:8000

# Points to this PocketBeagle device (for server push, if needed)
CLIENT_SERVER_URL=http://192.168.6.2:8001
```

```bash
# .env file on Laptop (192.168.6.1)
# Points to the PocketBeagle for pushing data back
CLIENT_SERVER_URL=http://192.168.6.2:8001
```

**Note:** On macOS, the PocketBeagle typically appears at `192.168.6.2` when connected via USB. The laptop's IP on the USB network is usually `192.168.6.1`. Adjust these IPs based on your network configuration.

## Real-World Examples

### Image Processing
```python
# Server endpoint for image processing
@app.post("/api/process/image")
async def process_image(image: UploadFile = File(...)):
    # Process image (resize, filter, ML inference, etc.)
    processed = image_processor.process(image)
    return FileResponse(processed, media_type="image/jpeg")
```

### Sensor Data Analysis
```python
# Server endpoint for sensor data
@app.post("/api/analyze/sensors")
async def analyze_sensors(data: dict):
    # Analyze sensor readings, detect anomalies, etc.
    result = sensor_analyzer.analyze(data["readings"])
    return JSONResponse(content={"anomalies": result})
```

### ML Model Inference
```python
# Server endpoint for ML inference
@app.post("/api/infer")
async def run_inference(input_data: dict):
    # Run ML model inference
    prediction = ml_model.predict(input_data["features"])
    return JSONResponse(content={"prediction": prediction})
```

## Benefits for PocketBeagle Projects

1. **Memory Efficiency**: Large models/data never load on the Beagle (saves 100-500MB+ RAM)
2. **CPU Efficiency**: Heavy computation offloaded to more powerful machine
3. **Flexibility**: Same codebase works in full/server/client modes
4. **Scalability**: Server can handle multiple clients simultaneously
5. **Development Speed**: Test locally, deploy distributed
6. **Battery Life**: Reduced CPU usage extends battery life on portable devices

This pattern enables any PocketBeagle project to offload heavy processing while maintaining real-time hardware control.

---

## Advanced: Using the Adapter Pattern (Optional)

If you want to swap between local and remote implementations seamlessly, you can use the adapter pattern. This allows the same code to work whether processing happens locally or remotely.

### Create Adapter Classes

```python
# remote_file_adapter.py
import httpx
import asyncio
from pathlib import Path
from typing import Union, Optional

class RemoteFileAdapter:
    """HTTP client adapter that matches local adapter interface."""
    
    def __init__(self, server_url: str, timeout: float = 30.0):
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
    
    def process(self, file_path: Union[str, Path], options: Optional[dict] = None) -> Union[str, dict]:
        """Process file via HTTP - same interface as local adapter."""
        return asyncio.run(self._process_async(file_path, options))
    
    async def _process_async(self, file_path: Union[str, Path], options: Optional[dict] = None) -> Union[str, dict]:
        # Same implementation as Step 2 above
        api_url = f"{self.server_url}/api/process/file"
        # ... (rest of implementation)
```

### Use Adapters Interchangeably

```python
# config.py
SERVICE_MODE = os.getenv("SERVICE_MODE", "local")  # "local" or "remote"
# URL of laptop/server (used by PocketBeagle to request processing)
SERVICE_SERVER_URL = os.getenv("SERVICE_SERVER_URL", "http://192.168.6.1:8000")

# app.py
if SERVICE_MODE == "remote":
    adapter = RemoteFileAdapter(server_url=SERVICE_SERVER_URL)
else:
    adapter = LocalFileAdapter()  # Same interface

# Your code doesn't need to change
result = adapter.process("data.csv")
```

This pattern is useful if you want to test locally during development and deploy remotely in production without changing your application code.

