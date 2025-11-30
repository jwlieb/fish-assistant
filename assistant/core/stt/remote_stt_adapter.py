"""
Remote STT adapter that proxies transcription requests to a remote server.

Uploads WAV files via HTTP and receives transcripts. Maintains the same
interface as the local whisper_adapter for drop-in replacement.

Server API Expected:
    POST /api/stt/transcribe
    Content-Type: multipart/form-data
    Body:
        - audio: WAV file (multipart file)
        - model_size: "tiny" | "base" | "small" | "medium" (form field)
    
    Response:
        {"text": "transcribed text here"}
"""

import logging
from pathlib import Path
from typing import Literal
import httpx
import asyncio

logger = logging.getLogger("remote_stt")


async def transcribe_file_async(
    path: str | Path,
    server_url: str,
    model_size: Literal["tiny", "base", "small", "medium"] = "tiny",
    timeout: float = 30.0,
) -> str:
    """
    Transcribe a WAV file by uploading it to a remote STT server.
    
    Args:
        path: Path to WAV file
        server_url: Base URL of STT server (e.g., "http://localhost:8000")
        model_size: Model size hint (may be ignored by server)
        timeout: Request timeout in seconds
    
    Returns:
        Transcribed text string
    
    Raises:
        httpx.HTTPError: On network errors
        FileNotFoundError: If audio file doesn't exist
    """
    wav_path = Path(path)
    if not wav_path.exists():
        raise FileNotFoundError(f"Audio file not found: {wav_path}")
    
    # Construct API endpoint
    api_url = f"{server_url.rstrip('/')}/api/stt/transcribe"
    
    logger.info("Uploading audio to %s (model: %s)", api_url, model_size)
    
    # Read file and upload
    async with httpx.AsyncClient(timeout=timeout) as client:
        with open(wav_path, "rb") as f:
            files = {"audio": (wav_path.name, f, "audio/wav")}
            data = {"model_size": model_size}
            
            try:
                response = await client.post(api_url, files=files, data=data)
                response.raise_for_status()
                
                result = response.json()
                text = result.get("text", "").strip()
                
                logger.debug("Transcription received: %s", text[:50] if text else "(empty)")
                return text
                
            except httpx.TimeoutException as e:
                logger.error("STT request timed out after %.1fs", timeout)
                raise
            except httpx.HTTPStatusError as e:
                logger.error("STT server error: %s %s", e.response.status_code, e.response.text)
                raise
            except httpx.RequestError as e:
                logger.error("STT network error: %s", e)
                raise


def transcribe_file(
    path: str | Path,
    server_url: str,
    model_size: Literal["tiny", "base", "small", "medium"] = "tiny",
    timeout: float = 30.0,
) -> str:
    """
    Synchronous wrapper for transcribe_file_async.
    
    This maintains compatibility with the local whisper_adapter interface
    while using async HTTP under the hood.
    
    Args:
        path: Path to WAV file
        server_url: Base URL of STT server
        model_size: Model size hint
        timeout: Request timeout in seconds
    
    Returns:
        Transcribed text string
    """
    try:
        # Try to get running event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we need to use a different approach
            # This shouldn't happen if called from asyncio.to_thread()
            logger.warning("Event loop is running, creating new thread for HTTP request")
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        transcribe_file_async(path, server_url, model_size, timeout)
                    )
                )
                return future.result()
        else:
            return loop.run_until_complete(
                transcribe_file_async(path, server_url, model_size, timeout)
            )
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(
            transcribe_file_async(path, server_url, model_size, timeout)
        )


class RemoteSTTAdapter:
    """
    Adapter class for remote STT that can be configured with server URL.
    
    Maintains the same interface as WhisperAdapter for drop-in replacement.
    
    Usage:
        adapter = RemoteSTTAdapter(server_url="http://localhost:8000")
        text = adapter.transcribe("audio.wav")
    """
    
    def __init__(
        self,
        server_url: str,
        model_size: Literal["tiny", "base", "small", "medium"] = "tiny",
        timeout: float = 30.0,
    ):
        """
        Initialize remote STT adapter.
        
        Args:
            server_url: Base URL of STT server (e.g., "http://localhost:8000")
            model_size: Model size hint (may be ignored by server)
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.model_size = model_size
        self.timeout = timeout
        self.log = logging.getLogger("remote_stt")
    
    def transcribe(self, path: str | Path) -> str:
        """
        Transcribe audio file using remote server.
        
        Args:
            path: Path to WAV file
        
        Returns:
            Transcribed text string
        """
        return transcribe_file(
            path,
            self.server_url,
            self.model_size,
            self.timeout,
        )

