"""
Billy Bass mouth motor controller.

Controls a motor driver (via PWM and GPIO) to animate the fish mouth
based on audio amplitude during playback.

Requires Adafruit_BBIO library (BeagleBone Black specific).
"""

import asyncio
import logging
import os
import numpy as np
import soundfile as sf
from typing import Optional
from ..contracts import PlaybackStart, PlaybackEnd

# Try to import BeagleBone GPIO/PWM libraries
try:
    import Adafruit_BBIO.PWM as PWM
    import Adafruit_BBIO.GPIO as GPIO
    BBIO_AVAILABLE = True
except ImportError:
    BBIO_AVAILABLE = False
    PWM = None
    GPIO = None


class BillyBass:
    """
    Listens on 'audio.playback.start' and 'audio.playback.end'.
    Controls mouth motor based on audio amplitude during playback.
    """

    # Hardware pin configuration (BeagleBone Black)
    MOUTH_PWM_PIN = "P1_36"
    MOUTH_IN1 = "P1_32"
    MOUTH_IN2 = "P1_30"
    STBY_PIN = "P1_06"

    # Audio processing parameters
    CHUNK_SIZE_MS = 20  # Process audio in 20ms chunks
    NOISE_GATE_THRESHOLD = 200  # RMS threshold below which motor stops
    VOLUME_DIVISOR = 500  # Scale factor for volume to PWM conversion

    def __init__(self, bus, enabled: bool = True):
        """
        Initialize Billy Bass controller.
        
        Args:
            bus: Event bus instance
            enabled: Whether to enable motor control (default: True)
                     Set to False to disable if hardware not available
        """
        self.bus = bus
        self.enabled = enabled and BBIO_AVAILABLE
        self.log = logging.getLogger("billy_bass")
        self._initialized = False
        self._current_task: Optional[asyncio.Task] = None

        if not BBIO_AVAILABLE:
            self.log.warning(
                "Adafruit_BBIO not available. Billy Bass motor control disabled. "
                "Install with: pip install Adafruit_BBIO"
            )
        elif not enabled:
            self.log.info("Billy Bass motor control disabled by configuration")

    async def start(self):
        """Subscribe to playback events."""
        if not self.enabled:
            return
        
        self._initialize_hardware()
        self.bus.subscribe("audio.playback.start", self._on_playback_start)
        self.bus.subscribe("audio.playback.end", self._on_playback_end)

    def _initialize_hardware(self):
        """Initialize GPIO and PWM pins."""
        if self._initialized:
            return
        
        try:
            # Setup standby pin (enable motor driver)
            GPIO.setup(self.STBY_PIN, GPIO.OUT)
            GPIO.output(self.STBY_PIN, GPIO.HIGH)
            
            # Setup motor direction pins
            GPIO.setup(self.MOUTH_IN1, GPIO.OUT)
            GPIO.setup(self.MOUTH_IN2, GPIO.OUT)
            
            # Initialize PWM (start at 0% duty cycle)
            PWM.start(self.MOUTH_PWM_PIN, 0)
            
            self._initialized = True
            self.log.info("Billy Bass hardware initialized")
        except Exception as e:
            self.log.exception("Failed to initialize Billy Bass hardware: %s", e)
            self.enabled = False

    async def _on_playback_start(self, payload: dict):
        """Handle playback start event - begin processing audio chunks."""
        if not self.enabled:
            return
        
        try:
            event = PlaybackStart(**payload)
        except Exception:
            self.log.warning("malformed audio.playback.start event, skipping")
            return

        wav_path = event.wav_path
        if not wav_path or not os.path.exists(wav_path):
            return

        # Cancel any existing task
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        # Start processing audio chunks
        self._current_task = asyncio.create_task(
            self._process_audio_chunks(wav_path)
        )

    async def _on_playback_end(self, payload: dict):
        """Handle playback end event - stop motor and cleanup."""
        if not self.enabled:
            return
        
        try:
            event = PlaybackEnd(**payload)
        except Exception:
            self.log.warning("malformed audio.playback.end event, skipping")
            return

        # Stop motor
        self._stop_motor()

        # Cancel processing task if still running
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

    async def _process_audio_chunks(self, wav_path: str):
        """
        Read audio file in chunks and control motor based on amplitude.
        
        This runs in parallel with the actual audio playback.
        """
        try:
            # Open audio file
            with sf.SoundFile(wav_path) as audio_file:
                sample_rate = audio_file.samplerate
                channels = audio_file.channels
                chunk_size_samples = int(sample_rate * self.CHUNK_SIZE_MS / 1000)
                chunk_duration_s = self.CHUNK_SIZE_MS / 1000.0

                self.log.debug(
                    "Processing audio chunks: %d Hz, %d ch, %d samples/chunk",
                    sample_rate, channels, chunk_size_samples
                )

                # Read and process chunks
                while True:
                    chunk = audio_file.read(chunk_size_samples, dtype="float32", always_2d=True)
                    
                    if len(chunk) == 0:
                        break  # End of file

                    # Convert to mono if stereo (take mean of channels)
                    if channels > 1:
                        chunk = np.mean(chunk, axis=1)
                    else:
                        chunk = chunk.flatten()

                    # Convert float32 [-1, 1] to int16 for RMS calculation
                    chunk_int16 = (chunk * 32767).astype(np.int16)

                    # Control motor based on volume
                    await asyncio.to_thread(self._move_mouth, chunk_int16)

                    # Sleep for chunk duration to maintain real-time processing
                    await asyncio.sleep(chunk_duration_s)

        except asyncio.CancelledError:
            self.log.debug("Audio chunk processing cancelled")
            raise
        except Exception as e:
            self.log.exception("Error processing audio chunks: %s", e)
        finally:
            self._stop_motor()

    def _move_mouth(self, audio_chunk: np.ndarray):
        """
        Calculate volume from audio chunk and set PWM duty cycle.
        
        This runs in a thread to avoid blocking the event loop.
        """
        if not self._initialized:
            return

        try:
            # Calculate RMS volume
            if len(audio_chunk) == 0:
                volume = 0
            else:
                volume = np.sqrt(np.mean(audio_chunk.astype(np.float64) ** 2))

            # Noise gate: stop motor if volume too low
            if volume < self.NOISE_GATE_THRESHOLD:
                pwm_val = 0
            else:
                # Scale volume to 0-100 PWM duty cycle
                pwm_val = min(100, int(volume / self.VOLUME_DIVISOR))

            # Drive motor (one direction opens mouth)
            GPIO.output(self.MOUTH_IN1, GPIO.HIGH)
            GPIO.output(self.MOUTH_IN2, GPIO.LOW)
            PWM.set_duty_cycle(self.MOUTH_PWM_PIN, pwm_val)

        except Exception as e:
            self.log.exception("Error controlling motor: %s", e)

    def _stop_motor(self):
        """Stop the motor by setting PWM to 0."""
        if not self._initialized:
            return
        
        try:
            PWM.set_duty_cycle(self.MOUTH_PWM_PIN, 0)
        except Exception as e:
            self.log.exception("Error stopping motor: %s", e)

    async def stop(self):
        """Cleanup resources before shutdown."""
        if not self.enabled:
            return
        
        self._stop_motor()
        
        # Cancel any running task
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        # Cleanup hardware
        if self._initialized:
            try:
                PWM.stop(self.MOUTH_PWM_PIN)
                PWM.cleanup()
                GPIO.cleanup()
                self._initialized = False
                self.log.info("Billy Bass hardware cleaned up")
            except Exception as e:
                self.log.exception("Error cleaning up hardware: %s", e)

