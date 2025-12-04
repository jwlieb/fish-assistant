"""
Client audio push service for server mode.

When CLIENT_SERVER_URL is configured, pushes TTS audio files to the client
for playback instead of (or in addition to) playing locally.
"""

import logging
import os
import httpx
from typing import Optional
from ..bus import Bus
from ..contracts import TTSAudio
from ..config import Config

logger = logging.getLogger("client_push")


class ClientAudioPush:
    """
    Subscribes to 'tts.audio' events and pushes audio files to client.
    
    Only pushes if CLIENT_SERVER_URL is configured. Handles errors gracefully
    to avoid crashing the pipeline.
    """
    
    def __init__(self, bus: Bus, client_url: Optional[str] = None):
        """
        Initialize client audio push service.
        
        Args:
            bus: Event bus instance
            client_url: Client server URL (defaults to Config.CLIENT_SERVER_URL)
        """
        self.bus = bus
        self.client_url = client_url or Config.CLIENT_SERVER_URL
        self.log = logging.getLogger("client_push")
        
        if not self.client_url:
            self.log.warning("ClientAudioPush initialized but CLIENT_SERVER_URL not configured")
    
    async def start(self):
        """Subscribe to tts.audio events."""
        if self.client_url:
            self.bus.subscribe("tts.audio", self._on_audio)
            self.log.info("Client audio push enabled: %s", self.client_url)
        else:
            self.log.debug("Client audio push disabled (no CLIENT_SERVER_URL)")
    
    async def _on_audio(self, payload: dict):
        """Handle tts.audio event by pushing to client."""
        self.log.info("ClientPush: Received tts.audio event")
        if not self.client_url:
            self.log.warning("ClientPush: CLIENT_SERVER_URL not configured, skipping push")
            return
        
        try:
            audio_event = TTSAudio(**payload)
            self.log.info("ClientPush: Parsed audio event: %s (%.2fs)", audio_event.wav_path, audio_event.duration_s)
        except Exception as e:
            self.log.warning("ClientPush: Malformed tts.audio event, skipping push: %s", e)
            return
        
        wav_path = audio_event.wav_path
        if not wav_path or not os.path.exists(wav_path):
            self.log.warning("ClientPush: Missing or invalid audio file, skipping push: %s", wav_path)
            return
        
        # Push to client asynchronously (don't block the pipeline)
        self.log.info("ClientPush: Starting push to client: %s", self.client_url)
        try:
            await self._push_to_client(wav_path)
            self.log.info("ClientPush: Successfully pushed audio to client")
        except Exception as e:
            self.log.error("ClientPush: Failed to push audio to client: %s", e, exc_info=True)
            # Don't raise - graceful degradation
    
    async def _push_to_client(self, wav_path: str):
        """Push audio file to client's /api/audio/play endpoint."""
        api_url = f"{self.client_url.rstrip('/')}/api/audio/play"
        
        file_size = os.path.getsize(wav_path) if os.path.exists(wav_path) else 0
        self.log.info("ClientPush: Pushing audio to %s", api_url)
        self.log.info("ClientPush: File: %s (%d bytes)", wav_path, file_size)
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(wav_path, "rb") as f:
                    files = {"audio": (os.path.basename(wav_path), f, "audio/wav")}
                    self.log.info("ClientPush: Sending HTTP POST request...")
                    response = await client.post(api_url, files=files)
                    self.log.info("ClientPush: Received HTTP response: %d", response.status_code)
                    response.raise_for_status()
                    
                    result = response.json()
                    self.log.info(
                        "ClientPush: Client accepted audio (duration: %.2fs, status: %s)",
                        result.get("duration_s", 0), result.get("status", "unknown")
                    )
        except httpx.TimeoutException:
            self.log.error("Timeout pushing audio to client after 30s")
            raise
        except httpx.HTTPStatusError as e:
            self.log.error(
                "Client returned error status %d: %s",
                e.response.status_code, e.response.text
            )
            raise
        except Exception as e:
            self.log.error("Unexpected error pushing to client: %s", e)
            raise

