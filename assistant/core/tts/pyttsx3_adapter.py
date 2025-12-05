import os
import tempfile
import logging
import subprocess
import soundfile as sf
from typing import Optional
import pyttsx3
import time

class Pyttsx3Adapter:
    """
    Simple TTS adapter using pyttsx3.
    Synchronously synthesizes text into a temporary WAV file.
    """

    def __init__(self, voice: Optional[str] = None):
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
        
        # Resample to 44100 Hz for compatibility with USB audio devices
        # pyttsx3 typically outputs at 22050 Hz, but many USB devices only support 44100/48000 Hz
        resampled_path = self._resample_to_44100(out_path)
        
        return resampled_path
    
    def _resample_to_44100(self, input_path: str) -> str:
        """
        Resample audio file to 44100 Hz using sox or ffmpeg.
        Returns path to resampled file (or original if resampling fails/unnecessary).
        """
        try:
            # Check current sample rate
            info = sf.info(input_path)
            current_sr = info.samplerate
            
            if current_sr == 44100:
                # Already at target rate
                return input_path
            
            self.log.info("Resampling TTS audio from %d Hz to 44100 Hz", current_sr)
            
            # Create output path
            output_path = input_path.replace('.wav', '_44100.wav')
            
            # Try sox first (lightweight, commonly available on macOS/Linux)
            try:
                result = subprocess.run(
                    ['sox', input_path, '-r', '44100', output_path],
                    capture_output=True,
                    timeout=10,
                    check=True
                )
                if os.path.exists(output_path):
                    self.log.info("Resampled using sox: %s -> %s", input_path, output_path)
                    # Clean up original file
                    try:
                        os.remove(input_path)
                    except Exception:
                        pass
                    return output_path
            except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                self.log.debug("sox not available or failed: %s", e)
            
            # Fallback to ffmpeg
            try:
                result = subprocess.run(
                    ['ffmpeg', '-i', input_path, '-ar', '44100', '-y', output_path],
                    capture_output=True,
                    timeout=10,
                    check=True
                )
                if os.path.exists(output_path):
                    self.log.info("Resampled using ffmpeg: %s -> %s", input_path, output_path)
                    # Clean up original file
                    try:
                        os.remove(input_path)
                    except Exception:
                        pass
                    return output_path
            except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                self.log.warning("ffmpeg not available or failed: %s", e)
            
            # If both fail, return original (will likely fail on client but at least we tried)
            self.log.warning("Neither sox nor ffmpeg available for resampling, returning original file")
            return input_path
            
        except Exception as e:
            self.log.warning("Error during resampling: %s, returning original file", e)
            return input_path
