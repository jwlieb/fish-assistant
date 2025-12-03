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
        if not self.client_url:
            return
        
        try:
            audio_event = TTSAudio(**payload)
        except Exception as e:
            self.log.warning("Malformed tts.audio event, skipping push: %s", e)
            return
        
        wav_path = audio_event.wav_path
        if not wav_path or not os.path.exists(wav_path):
            self.log.warning("Missing or invalid audio file, skipping push: %s", wav_path)
            return
        
        # Push to client asynchronously (don't block the pipeline)
        try:
            await self._push_to_client(wav_path)
        except Exception as e:
            self.log.error("Failed to push audio to client: %s", e, exc_info=True)
            # Don't raise - graceful degradation
    
    async def _push_to_client(self, wav_path: str):
        """Push audio file to client's /api/audio/play endpoint."""
        api_url = f"{self.client_url.rstrip('/')}/api/audio/play"
        
        self.log.info("Pushing audio to client: %s (%s)", api_url, wav_path)
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(wav_path, "rb") as f:
                    files = {"audio": (os.path.basename(wav_path), f, "audio/wav")}
                    response = await client.post(api_url, files=files)
                    response.raise_for_status()
                    
                    result = response.json()
                    self.log.info(
                        "Successfully pushed audio to client: %s (duration: %.2fs)",
                        wav_path, result.get("duration_s", 0)
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

