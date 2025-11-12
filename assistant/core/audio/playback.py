import asyncio
import os
import logging
import soundfile as sf
import sounddevice as sd
from ..contracts import TTSAudio, PlaybackStart, PlaybackEnd, same_trace

class Playback:
    """
    Listens on 'tts.audio' and emits 'audio.playback.start' and 'audio.playback.end'.
    Plays audio file and cleans it up after playback.
    """

    def __init__(self, bus):
        self.bus = bus
        self.log = logging.getLogger("playback")

    async def start(self):
        self.bus.subscribe("tts.audio", self._on_audio)

    async def _on_audio(self, payload: dict):
        try:
            audio_event = TTSAudio(**payload)
        except Exception:
            self.log.warning("malformed tts.audio event, skipping")
            return

        path = audio_event.wav_path
        if not path or not os.path.exists(path):
            self.log.warning("missing or invalid path: %s", path)
            return
        
        try:
            # Gather info
            size_bytes = os.path.getsize(path)
            info = sf.info(path)
            duration = info.frames / float(info.samplerate) if info.samplerate else 0.0
            self.log.info("playing: %s (%.2fs, %d bytes, %d Hz, %d ch)", 
                          path, duration, size_bytes, info.samplerate, info.channels)
            
            # Emit playback start
            start_event = PlaybackStart(wav_path=path)
            same_trace(audio_event, start_event)
            await self.bus.publish(start_event.topic, start_event.dict())
            
            # Read audio data (non-blocking)
            data, sr = sf.read(path, dtype="float32", always_2d=True)

            # Non-blocking play start
            sd.play(data, sr)
            self.log.debug("Playback started.")

            # blocking wait 
            await asyncio.to_thread(sd.wait)
            self.log.debug("Playback finished.")

            # Emit playback end
            end_event = PlaybackEnd(wav_path=path, ok=True)
            same_trace(audio_event, end_event)
            await self.bus.publish(end_event.topic, end_event.dict())

        except Exception as e:
            self.log.exception("failed to play %s", path)
            # Emit error end event
            end_event = PlaybackEnd(wav_path=path, ok=False)
            same_trace(audio_event, end_event)
            await self.bus.publish(end_event.topic, end_event.dict())
            return
        
        # Cleanup in worker thread
        await asyncio.to_thread(self._safe_cleanup, path) 

    # Cleanup logic
    def _safe_cleanup(self, path):
        try:
            os.remove(path)
            self.log.debug("cleaned up: %s", path)
        except Exception:
            # Note: logging exception from a thread requires care, 
            # but this synchronous approach is simpler here.
            self.log.exception("failed to cleanup: %s", path)