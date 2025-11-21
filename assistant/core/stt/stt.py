import asyncio
import logging
from pathlib import Path
from typing import Literal
from assistant.core.stt.whisper_adapter import transcribe_file
from assistant.core.contracts import AudioRecorded, STTTranscript, same_trace

class STT:
    """
    Listens on 'audio.recorded' and emits 'stt.transcript'.
    """

    def __init__(self, bus, model_size: Literal["tiny", "base", "small", "medium"] = "tiny"):
        self.bus = bus
        self.model_size = model_size
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

        # run blocking transcription in thread
        self.log.info("transcribing audio file: %s", wav_path)
        try:
            text = await asyncio.to_thread(transcribe_file, wav_path, self.model_size)
            self.log.debug("transcription complete: %s", text[:50] if text else "(empty)")
        except Exception as e:
            self.log.exception("transcription failed: %s", e)
            return

        if not text or not text.strip():
            self.log.debug("empty transcription, skipping")
            return

        transcript_event = STTTranscript(text=text.strip())
        same_trace(audio_event, transcript_event)
        await self.bus.publish(transcript_event.topic, transcript_event.dict())

    async def stop(self):
        """Cleans up resources before shutdown"""
        self.log.info("stopping STT component")

