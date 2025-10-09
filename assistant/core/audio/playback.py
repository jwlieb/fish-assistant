import asyncio
import os
import logging
import soundfile as sf
import sounddevice as sd

class Playback:
    """
    Listens on 'playback' with payload {'path': str, 'cleanup': bool}
    Plays audio file, then deletes if cleanup=True
    """

    def __init__(self, bus):
        self.bus = bus
        self.log = logging.getLogger("playback")

    async def start(self):
        self.bus.subscribe("playback", self._on_play)

    async def _on_play(self, payload: dict):
        path = (payload or {}).get("path")
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
            
            # Read audio data (non-blocking)
            data, sr = sf.read(path, dtype="float32", always_2d=True)

            # Non-blocking play start
            sd.play(data, sr)
            self.log.debug("Playback started.")

            # blocking wait 
            await asyncio.to_thread(sd.wait)
            await asyncio.sleep(3.0)
            self.log.debug("Playback finished.")

        except Exception:
            self.log.exception("failed to play %s", path)
            return
        
        # cleanup
        if payload.get("cleanup"):
            try:
                os.remove(path)
                self.log.debug("cleaned up: %s", path)
            except Exception:
                self.log.exception("failed to cleanup: %s", path)
