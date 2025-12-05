import asyncio
import logging
from pathlib import Path
from typing import Union, Optional
from assistant.core.contracts import AudioRecorded, STTTranscript, same_trace


class STTAdapter:
    """Protocol for STT adapters - must implement transcribe method."""
    def transcribe(self, path: Union[str, Path]) -> str:
        """Transcribe audio file and return text."""
        raise NotImplementedError


class STT:
    """
    Listens on 'audio.recorded' and emits 'stt.transcript'.
    
    Can use either local (WhisperAdapter) or remote (RemoteSTTAdapter) adapters.
    """

    def __init__(
        self,
        bus,
        adapter: Optional[STTAdapter] = None,
        model_size: str = "tiny",  # "tiny", "base", "small", "medium"
    ):
        """
        Initialize STT component.
        
        Args:
            bus: Event bus instance
            adapter: STT adapter (WhisperAdapter or RemoteSTTAdapter).
                    If None, creates a local WhisperAdapter.
            model_size: Model size for local adapter (ignored if adapter provided)
        """
        self.bus = bus
        if adapter is None:
            # Only import whisper when actually needed (not in client mode)
            from assistant.core.stt.whisper_adapter import WhisperAdapter
            adapter = WhisperAdapter(model_size=model_size)
        self.adapter = adapter
        self.log = logging.getLogger("stt")

    async def start(self):
        self.bus.subscribe("audio.recorded", self._on_recorded)

    async def _on_recorded(self, payload: dict):
        try:
            audio_event = AudioRecorded(**payload)
        except Exception:
            self.log.warning("malformed audio.recorded event, skipping")
            return

        wav_path = audio_event.wav_path.strip()
        if not wav_path:
            self.log.debug("empty wav_path, skipping")
            return

        # Verify file exists
        if not Path(wav_path).exists():
            self.log.warning("audio file does not exist: %s", wav_path)
            return

        # run blocking transcription in thread (Python 3.7 compatible)
        self.log.info("STT: Transcribing audio file: %s (duration=%.2fs)", wav_path, audio_event.duration_s)
        try:
            # Use adapter's transcribe method
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, self.adapter.transcribe, wav_path)
            self.log.info("STT: Transcription complete: '%s'", text[:100] if text else "(empty)")
        except Exception as e:
            self.log.exception("STT: Transcription failed: %s", e)
            return

        if not text or not text.strip():
            self.log.warning("STT: Empty transcription (audio may be too short or silent), publishing empty transcript to reset state")
            # Publish empty transcript so conversation loop can reset to idle
            transcript_event = STTTranscript(text="")
            same_trace(audio_event, transcript_event)
            await self.bus.publish(transcript_event.topic, transcript_event.dict())
            return

        self.log.info("STT: Publishing stt.transcript event: '%s'", text.strip()[:50])
        transcript_event = STTTranscript(text=text.strip())
        same_trace(audio_event, transcript_event)
        await self.bus.publish(transcript_event.topic, transcript_event.dict())
        self.log.info("STT: Published stt.transcript event successfully")

    async def stop(self):
        """Cleans up resources before shutdown"""
        self.log.info("stopping STT component")

