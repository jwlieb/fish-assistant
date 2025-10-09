import os
import tempfile
import logging
import pyttsx3
import time

class Pyttsx3Adapter:
    """
    Simple TTS adapter using pyttsx3.
    Synchronously synthesizes text into a temporary WAV file.
    """

    def __init__(self, voice: str | None = None):
        self.voice = voice
        self.log = logging.getLogger("pyttsx3")

    def synth(self, text: str) -> str:
        # Create temp file path
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        # Initialize engine
        engine = pyttsx3.init()

        # Add explicit rate and volume
        try:
            engine.setProperty('rate', 150) # speaking rate
            engine.setProperty('volume', 1.0)
        except Exception as e:
            self.log.warning("Could not set engine properties: %s", e)

        # Set voice using stable fallback logic.
        voice_set = False
        STABLE_VOICES = ['com.apple.voice.compact.en-GB.Daniel', 'com.apple.speech.synthesis.voice.Albert']

        # Try user's voice first.
        if self.voice:
            for v in engine.getProperty("voices"):
                if self.voice in (v.id, v.name):
                    engine.setProperty("voice", v.id)
                    voice_set = True
                    break
        
        # If user voice failed or wasn't provided, try stable defaults.
        if not voice_set:
            available_ids = [v.id for v in engine.getProperty("voices")]
            for stable_id in STABLE_VOICES:
                if stable_id in available_ids:
                    engine.setProperty("voice", stable_id)
                    self.log.warning("Requested voice not set; falling back to stable voice: %s", stable_id)
                    voice_set = True
                    break
        
        # Final fallback warning
        if not voice_set:
             self.log.warning("Could not set any stable voice; using default engine voice.")
        
        # Queue save command
        engine.save_to_file(text, out_path)
        self.log.debug("pyttsx3 saving to %s", out_path)

        # Run and wait for completion
        engine.runAndWait()

        # naive workaround to file empty race condition
        # this is a ttsx3 issue...
        # higher quality model the longer the sleep
        # en-GB Daniel (classic) needs 3s, Albert needs 0.5
        time.sleep(3)

        # Explicit stop to finalize file write and release resources
        engine.stop()

        self.log.info("pyttsx3 wrote %s", out_path)
        return out_path
