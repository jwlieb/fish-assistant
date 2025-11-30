import asyncio
import logging
import soundfile as sf
from typing import Protocol
from assistant.core.tts.pyttsx3_adapter import Pyttsx3Adapter
from assistant.core.contracts import TTSRequest, TTSAudio, same_trace


class TTSAdapter(Protocol):
    """Protocol for TTS adapters - must implement synth method."""
    def synth(self, text: str) -> str:
        """Synthesize text to speech and return path to WAV file."""
        ...


class TTS:
    """
    Listens on 'tts.request' and emits 'tts.audio'.
    
    Can use either local (Pyttsx3Adapter) or remote (RemoteTTSAdapter) adapters.
    """

    def __init__(self, bus, adapter: TTSAdapter | None = None):
        """
        Initialize TTS component.
        
        Args:
            bus: Event bus instance
            adapter: TTS adapter (Pyttsx3Adapter or RemoteTTSAdapter).
                    If None, creates a local Pyttsx3Adapter.
        """
        self.bus = bus
        self.adapter = adapter or Pyttsx3Adapter()
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

        # run blocking synth in thread
        self.log.info("synthesizing text (%d chars)", len(text))
        path = await asyncio.to_thread(self.adapter.synth, text)
        self.log.debug("synth complete: %s", path)

        # Get duration from audio file
        try:
            info = sf.info(path)
            duration_s = info.frames / float(info.samplerate) if info.samplerate else 0.01
        except Exception:
            self.log.warning("could not read audio duration, using 0.01")
            duration_s = 0.01  # minimal default to satisfy contract

        audio_event = TTSAudio(wav_path=path, duration_s=duration_s)
        same_trace(req, audio_event)
        await self.bus.publish(audio_event.topic, audio_event.dict())

    async def stop(self):
        """Cleans up resources before shutdown"""
        self.log.info("stopping TTS component")
        # self.bus.unsubscribe("assistant.reply", self._on_reply) 
    
        # close adapter if possible
        if hasattr(self.adapter, 'close') and callable(self.adapter.close):
            # prevent blocking event loop
            await asyncio.to_thread(self.adapter.close)