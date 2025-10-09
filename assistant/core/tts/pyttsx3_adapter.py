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
        # create temp file path
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        # initialize engine
        engine = pyttsx3.init()

        # add explicit rate and volume
        try:
            engine.setProperty('rate', 150) # speaking rate
            engine.setProperty('volume', 1.0)
        except Exception as e:
            self.log.warning("Could not set engine properties: %s", e)

        # set voice if provided
        if self.voice:
            for v in engine.getProperty("voices"):
                if self.voice in (v.id, v.name):
                    engine.setProperty("voice", v.id)
                    break
            else:
                self.log.warning("requested voice '%s' not found; using default", self.voice)
        
        # queue save command
        engine.save_to_file(text, out_path)
        self.log.debug("pyttsx3 saving to %s", out_path)

        # run and wait for completion
        engine.runAndWait()

        # naive workaround to file empty race condition
        time.sleep(0.5)

        # explicit stop to finalize file write and release resources
        engine.stop()

        self.log.info("pyttsx3 wrote %s", out_path)
        return out_path
