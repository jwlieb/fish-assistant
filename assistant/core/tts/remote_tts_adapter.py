"""
Remote TTS adapter that proxies synthesis requests to a remote server.

Sends text via HTTP and receives WAV files. Maintains the same interface
as the local pyttsx3_adapter for drop-in replacement.

Server API Expected:
    POST /api/tts/synthesize
    Content-Type: application/json
    Body: {"text": "text to synthesize", "voice": "optional voice name"}
    
    Response:
        Option A: Binary WAV file (Content-Type: audio/wav)
        Option B: JSON with file URL: {"wav_url": "http://..."}
"""

import logging
import os
import tempfile
import asyncio
from typing import Optional
import httpx

logger = logging.getLogger("remote_tts")


async def synthesize_async(
    text: str,
    server_url: str,
    voice: Optional[str] = None,
    timeout: float = 30.0,
) -> str:
    """
    Synthesize text to speech by requesting from a remote TTS server.
    
    Args:
        text: Text to synthesize
        server_url: Base URL of TTS server (e.g., "http://localhost:8000")
        voice: Optional voice name (may be ignored by server)
        timeout: Request timeout in seconds
    
    Returns:
        Path to temporary WAV file
    
    Raises:
        httpx.HTTPError: On network errors
        ValueError: If text is empty
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")
    
    # Construct API endpoint
    api_url = f"{server_url.rstrip('/')}/api/tts/synthesize"
    
    logger.info("Requesting TTS synthesis from %s (text: %d chars)", api_url, len(text))
    
    # Prepare request payload
    payload = {"text": text.strip()}
    if voice:
        payload["voice"] = voice
    
    # Create temporary file for response
    fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(
                    api_url,
                    json=payload,
                    headers={"Accept": "audio/wav, application/json"}
                )
                response.raise_for_status()
                
                # Check content type
                content_type = response.headers.get("content-type", "").lower()
                
                if "application/json" in content_type:
                    # Server returned JSON with URL
                    result = response.json()
                    wav_url = result.get("wav_url") or result.get("url")
                    if wav_url:
                        logger.debug("Server returned WAV URL: %s", wav_url)
                        # Download the file
                        download_response = await client.get(wav_url)
                        download_response.raise_for_status()
                        with open(out_path, "wb") as f:
                            f.write(download_response.content)
                    else:
                        raise ValueError("Server returned JSON but no wav_url field")
                else:
                    # Server returned binary WAV file directly
                    with open(out_path, "wb") as f:
                        f.write(response.content)
                
                logger.debug("TTS synthesis complete: %s", out_path)
                return out_path
                
            except httpx.TimeoutException as e:
                logger.error("TTS request timed out after %.1fs", timeout)
                # Clean up temp file
                try:
                    os.remove(out_path)
                except Exception:
                    pass
                raise
            except httpx.HTTPStatusError as e:
                logger.error("TTS server error: %s %s", e.response.status_code, e.response.text)
                # Clean up temp file
                try:
                    os.remove(out_path)
                except Exception:
                    pass
                raise
            except httpx.RequestError as e:
                logger.error("TTS network error: %s", e)
                # Clean up temp file
                try:
                    os.remove(out_path)
                except Exception:
                    pass
                raise
    except Exception:
        # Clean up temp file on any error
        try:
            os.remove(out_path)
        except Exception:
            pass
        raise


def synthesize(
    text: str,
    server_url: str,
    voice: Optional[str] = None,
    timeout: float = 30.0,
) -> str:
    """
    Synchronous wrapper for synthesize_async.
    
    This maintains compatibility with the local pyttsx3_adapter interface
    while using async HTTP under the hood.
    
    Args:
        text: Text to synthesize
        server_url: Base URL of TTS server
        voice: Optional voice name
        timeout: Request timeout in seconds
    
    Returns:
        Path to temporary WAV file
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
                        synthesize_async(text, server_url, voice, timeout)
                    )
                )
                return future.result()
        else:
            return loop.run_until_complete(
                synthesize_async(text, server_url, voice, timeout)
            )
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(
            synthesize_async(text, server_url, voice, timeout)
        )


class RemoteTTSAdapter:
    """
    Adapter class for remote TTS that can be configured with server URL.
    
    Maintains the same interface as Pyttsx3Adapter for drop-in replacement.
    
    Usage:
        adapter = RemoteTTSAdapter(server_url="http://localhost:8000")
        wav_path = adapter.synth("Hello world")
    """
    
    def __init__(
        self,
        server_url: str,
        voice: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize remote TTS adapter.
        
        Args:
            server_url: Base URL of TTS server (e.g., "http://localhost:8000")
            voice: Optional voice name (may be ignored by server)
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.voice = voice
        self.timeout = timeout
        self.log = logging.getLogger("remote_tts")
    
    def synth(self, text: str) -> str:
        """
        Synthesize text to speech using remote server.
        
        Args:
            text: Text to synthesize
        
        Returns:
            Path to temporary WAV file
        """
        return synthesize(
            text,
            self.server_url,
            self.voice,
            self.timeout,
        )

