import asyncio
import logging
import soundfile as sf
from typing import Optional
from assistant.core.contracts import TTSRequest, TTSAudio, same_trace


class TTSAdapter:
    """Protocol for TTS adapters - must implement synth method."""
    def synth(self, text: str) -> str:
        """Synthesize text to speech and return path to WAV file."""
        raise NotImplementedError


class TTS:
    """
    Listens on 'tts.request' and emits 'tts.audio'.
    
    Can use either local (Pyttsx3Adapter) or remote (RemoteTTSAdapter) adapters.
    """

    def __init__(self, bus, adapter: Optional[TTSAdapter] = None):
        """
        Initialize TTS component.
        
        Args:
            bus: Event bus instance
            adapter: TTS adapter (Pyttsx3Adapter or RemoteTTSAdapter).
                    If None, creates a local Pyttsx3Adapter.
        """
        self.bus = bus
        if adapter is None:
            # Only import pyttsx3 when actually needed (not in client mode)
            from assistant.core.tts.pyttsx3_adapter import Pyttsx3Adapter
            adapter = Pyttsx3Adapter()
        self.adapter = adapter
        self.log = logging.getLogger("tts")

    async def start(self):
        self.bus.subscribe("tts.request", self._on_request)

    async def _on_request(self, payload: dict):
        try:
            req = TTSRequest(**payload)
        except Exception:
            self.log.warning("malformed tts.request event, skipping")
            return

        text = req.text.strip()
        if not text:
            self.log.debug("empty text, skipping")
            return

        # run blocking synth in thread (Python 3.7 compatible)
        self.log.info("TTS: Synthesizing text (%d chars): '%s'", len(text), text[:50])
        loop = asyncio.get_event_loop()
        path = await loop.run_in_executor(None, self.adapter.synth, text)
        self.log.info("TTS: Synthesis complete: %s", path)

        # Get duration from audio file
        try:
            info = sf.info(path)
            duration_s = info.frames / float(info.samplerate) if info.samplerate else 0.01
        except Exception:
            self.log.warning("could not read audio duration, using 0.01")
            duration_s = 0.01  # minimal default to satisfy contract

        audio_event = TTSAudio(wav_path=path, duration_s=duration_s)
        same_trace(req, audio_event)
        self.log.info("TTS: Publishing tts.audio event (path=%s, duration=%.2fs)", path, duration_s)
        await self.bus.publish(audio_event.topic, audio_event.dict())
        self.log.info("TTS: Published tts.audio event successfully")

    async def stop(self):
        """Cleans up resources before shutdown"""
        self.log.info("stopping TTS component")
        # self.bus.unsubscribe("assistant.reply", self._on_reply) 
    
        # close adapter if possible
        if hasattr(self.adapter, 'close') and callable(self.adapter.close):
            # prevent blocking event loop (Python 3.7 compatible)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.adapter.close)