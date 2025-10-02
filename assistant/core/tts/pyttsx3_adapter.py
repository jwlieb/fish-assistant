import os
import tempfile
import logging
import pyttsx3

class Pyttsx3Adapter:
    """
    Simple TTS adapter using pyttsx3.
    Synchronously synthesizes text into a temporary WAV file.
    """

    def __init__(self, voice: str | None = None):
        self.voice = voice
        self.log = logging.getLogger("pyttsx3")

    def synth(self, text: str) -> str:
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        engine = pyttsx3.init()
        if self.voice:
            for v in engine.getProperty("voices"):
                if self.voice in (v.id, v.name):
                    engine.setProperty("voice", v.id)
                    break
            else:
                self.log.warning("requested voice '%s' not found; using default", self.voice)
        engine.save_to_file(text, out_path)
        self.log.debug("pyttsx3 saving to %s", out_path)
        engine.runAndWait()
        self.log.info("pyttsx3 wrote %s", out_path)
        return out_path
