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

        # Poll for file completion instead of fixed sleep
        # pyttsx3 has a race condition where runAndWait() returns before file is fully written
        # We poll for file existence, size, and validity to minimize latency
        max_wait = 5.0  # Maximum wait time (safety timeout)
        poll_interval = 0.05  # Check every 50ms
        stability_checks = 2  # Number of consecutive valid checks required
        waited = 0.0
        valid_checks = 0
        
        while waited < max_wait:
            if os.path.exists(out_path):
                file_size = os.path.getsize(out_path)
                if file_size > 0:
                    # File exists and has content, verify it's a valid audio file
                    try:
                        # Quick validation: try to read file info
                        info = sf.info(out_path)
                        if info.frames > 0 and info.samplerate > 0:
                            valid_checks += 1
                            if valid_checks >= stability_checks:
                                # File is valid and stable, ready to proceed
                                self.log.debug("File ready after %.2fs (size: %d bytes, frames: %d)", 
                                             waited, file_size, info.frames)
                                break
                        else:
                            valid_checks = 0  # Reset if file becomes invalid
                    except Exception:
                        # File might still be writing, continue polling
                        valid_checks = 0
                else:
                    valid_checks = 0  # Reset if file is empty
            else:
                valid_checks = 0  # Reset if file doesn't exist yet
            
            time.sleep(poll_interval)
            waited += poll_interval
        
        if waited >= max_wait:
            self.log.warning("File polling timeout after %.2fs, proceeding anyway", max_wait)
            # Verify file exists and has content before proceeding
            if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                raise RuntimeError(f"TTS output file not ready after {max_wait}s: {out_path}")

        # Explicit stop to finalize file write and release resources
        engine.stop()

        self.log.info("pyttsx3 wrote %s", out_path)
        
        # Resample to 48000 Hz for compatibility with USB audio devices
        # pyttsx3 typically outputs at 22050 Hz, but many USB devices only support 48000 Hz
        resampled_path = self._resample_to_48000(out_path)
        
        return resampled_path
    
    def _resample_to_48000(self, input_path: str) -> str:
        """
        Resample audio file to 48000 Hz using sox or ffmpeg.
        Returns path to resampled file (or original if resampling fails/unnecessary).
        """
        try:
            # Check current sample rate
            info = sf.info(input_path)
            current_sr = info.samplerate
            
            if current_sr == 48000:
                # Already at target rate
                return input_path
            
            self.log.info("Resampling TTS audio from %d Hz to 48000 Hz", current_sr)
            
            # Create output path
            output_path = input_path.replace('.wav', '_48000.wav')
            
            # Try sox first (lightweight, commonly available on macOS/Linux)
            try:
                result = subprocess.run(
                    ['sox', input_path, '-r', '48000', output_path],
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
                self.log.warning("sox not available or failed: %s", e)
                if isinstance(e, subprocess.CalledProcessError):
                    self.log.warning("sox stderr: %s", e.stderr.decode() if e.stderr else "none")
            
            # Fallback to ffmpeg
            try:
                result = subprocess.run(
                    ['ffmpeg', '-i', input_path, '-ar', '48000', '-y', output_path],
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
            self.log.error("Neither sox nor ffmpeg available for resampling! Audio will be at %d Hz (may fail on client)", current_sr)
            self.log.error("Install sox or ffmpeg to enable resampling: brew install sox  (macOS) or apt-get install sox  (Linux)")
            return input_path
            
        except Exception as e:
            self.log.warning("Error during resampling: %s, returning original file", e)
            return input_path
