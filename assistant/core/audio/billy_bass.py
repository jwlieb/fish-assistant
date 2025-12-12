"""
Billy Bass motor controller for mouth, tail, and head animations.

Controls motor drivers (via PWM and GPIO) to animate:
- Mouth: Synchronized with audio playback amplitude
- Tail: Flaps during thinking state
- Head: Turns during listening and speaking states

Requires Adafruit_BBIO library (BeagleBone Black specific).
"""

import asyncio
import logging
import os
import soundfile as sf

try:
    import numpy as np
except ImportError:
    np = None
from typing import Optional
from ..contracts import PlaybackStart, PlaybackEnd, UXState

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
    Controls Billy Bass motors for mouth, tail, and head animations.
    
    Listens on:
    - 'audio.playback.start' and 'audio.playback.end' - Controls mouth motor based on audio amplitude
    - 'ux.state' - Triggers body animations based on conversation state
    
    Provides direct methods for manual control:
    - tail_flap() - Animate tail flapping
    - head_turn() - Turn head left/right
    - stop_body_motor() - Stop body motor
    """

    # Hardware pin configuration (BeagleBone Black)
    # Mouth motor pins
    MOUTH_PWM_PIN = "P1_36"
    MOUTH_IN1 = "P1_30"
    MOUTH_IN2 = "P1_32"
    # Body motor pins (for tail flap and head turn)
    BODY_PWM_PIN = "P1_33"
    BODY_IN1 = "P1_26"
    BODY_IN2 = "P1_28"
    # STBY pin is wired to positive rail, no GPIO control needed
    STBY_PIN = "P1_06"

    # Audio processing parameters
    CHUNK_SIZE_MS = 10  # Process audio in 10ms chunks (smaller = more responsive)
    NOISE_GATE_THRESHOLD = 500  # RMS threshold below which motor stops (higher = more precise)
    VOLUME_DIVISOR = 150  # Scale factor for volume to PWM conversion (lower = more movement)
    MIN_PWM = 5  # Minimum PWM when audio detected (for subtle movement)
    MAX_PWM = 80  # Maximum PWM (prevent over-driving motor)

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
        self._body_task: Optional[asyncio.Task] = None
        self._periodic_flap_task: Optional[asyncio.Task] = None

        if not BBIO_AVAILABLE:
            self.log.warning(
                "Adafruit_BBIO not available. Billy Bass motor control disabled. "
                "Install with: pip install Adafruit_BBIO"
            )
        elif not enabled:
            self.log.info("Billy Bass motor control disabled by configuration")

    async def start(self):
        """Subscribe to playback and UX state events."""
        if not self.enabled:
            self.log.warning("BillyBass: start() called but disabled")
            return
        
        self.log.info("BillyBass: Starting, initializing hardware...")
        self._initialize_hardware()
        
        if not self._initialized:
            self.log.error("BillyBass: Hardware initialization failed, motors will not work")
            return
        
        self.bus.subscribe("audio.playback.start", self._on_playback_start)
        self.bus.subscribe("audio.playback.end", self._on_playback_end)
        self.bus.subscribe("ux.state", self._on_ux_state)
        self.log.info("BillyBass: Subscribed to events, ready to control motors")
        
        # Start periodic tail flapping when idle
        self._periodic_flap_task = asyncio.create_task(self._periodic_idle_flap())

    def _initialize_hardware(self):
        """Initialize GPIO and PWM pins."""
        if self._initialized:
            return
        
        try:
            # STBY pin is wired to positive rail, no GPIO setup needed
            
            # Setup mouth motor direction pins
            GPIO.setup(self.MOUTH_IN1, GPIO.OUT)
            GPIO.setup(self.MOUTH_IN2, GPIO.OUT)
            
            # Setup body motor direction pins
            GPIO.setup(self.BODY_IN1, GPIO.OUT)
            GPIO.setup(self.BODY_IN2, GPIO.OUT)
            
            # Initialize PWM (start at 0% duty cycle)
            PWM.start(self.MOUTH_PWM_PIN, 0)
            PWM.start(self.BODY_PWM_PIN, 0)
            
            self._initialized = True
            self.log.info("Billy Bass hardware initialized")
        except Exception as e:
            self.log.exception("Failed to initialize Billy Bass hardware: %s", e)
            self.enabled = False

    async def _on_playback_start(self, payload: dict):
        """Handle playback start event - begin processing audio chunks."""
        if not self.enabled:
            self.log.warning("BillyBass: Received playback.start but disabled")
            return
        
        if not self._initialized:
            self.log.warning("BillyBass: Received playback.start but hardware not initialized")
            return
        
        try:
            event = PlaybackStart(**payload)
            self.log.info("BillyBass: Received playback.start for %s", event.wav_path)
        except Exception:
            self.log.warning("malformed audio.playback.start event, skipping")
            return

        wav_path = event.wav_path
        if not wav_path or not os.path.exists(wav_path):
            self.log.warning("BillyBass: Audio file not found: %s", wav_path)
            return

        # Publish UX state "speaking" so body animations trigger
        # This ensures animations work even if conversation loop isn't running (e.g., REPL mode)
        await self.bus.publish("ux.state", UXState(state="speaking").dict())

        # Cancel any existing task
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        # Start processing audio chunks
        self.log.info("BillyBass: Starting audio chunk processing for mouth motor")
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

        # Publish UX state "idle" to stop body animations
        if event.ok:
            await self.bus.publish("ux.state", UXState(state="idle").dict())

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
        Uses precise timing to stay synchronized with audio playback.
        """
        try:
            # Small delay to let audio playback start (account for device initialization)
            await asyncio.sleep(0.05)  # 50ms delay to sync with audio playback start
            
            # Open audio file
            with sf.SoundFile(wav_path) as audio_file:
                sample_rate = audio_file.samplerate
                channels = audio_file.channels
                chunk_size_samples = int(sample_rate * self.CHUNK_SIZE_MS / 1000)
                chunk_duration_s = self.CHUNK_SIZE_MS / 1000.0

                self.log.debug(
                    "Processing audio chunks: %d Hz, %d ch, %d samples/chunk, %.1fms/chunk",
                    sample_rate, channels, chunk_size_samples, self.CHUNK_SIZE_MS
                )

                # Track timing to maintain sync
                import time
                start_time = time.time()
                chunk_index = 0

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

                    # Control motor based on volume (Python 3.7 compatible)
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self._move_mouth, chunk_int16)

                    # Calculate precise sleep time to maintain sync
                    chunk_index += 1
                    expected_time = start_time + (chunk_index * chunk_duration_s)
                    current_time = time.time()
                    sleep_time = max(0, expected_time - current_time)
                    
                    # If we're behind, don't sleep (catch up)
                    # If we're ahead, sleep to maintain sync
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                    else:
                        # We're behind, skip a tiny sleep to catch up
                        await asyncio.sleep(0.001)  # Minimal sleep to yield to event loop

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
        Uses peak detection for more precise mouth movement.
        Actively closes mouth by reversing motor direction when no audio.
        """
        if not self._initialized:
            return

        try:
            if len(audio_chunk) == 0:
                volume = 0
                peak = 0
            else:
                # Calculate RMS volume (average energy)
                volume = np.sqrt(np.mean(audio_chunk.astype(np.float64) ** 2))
                # Calculate peak amplitude (for detecting speech bursts)
                peak = np.max(np.abs(audio_chunk.astype(np.float64)))

            # Use peak detection for more precise movement
            # Peak is better for detecting actual speech sounds vs background
            effective_volume = max(volume, peak * 0.7)  # Blend RMS and peak

            # Track previous state to detect transitions
            if not hasattr(self, '_prev_pwm'):
                self._prev_pwm = 0

            # Noise gate: stop motor if volume too low
            if effective_volume < self.NOISE_GATE_THRESHOLD:
                pwm_val = 0
            else:
                # Scale volume to PWM duty cycle with min/max limits
                # Use a more aggressive scaling for better responsiveness
                pwm_val = int((effective_volume - self.NOISE_GATE_THRESHOLD) / self.VOLUME_DIVISOR)
                pwm_val = max(self.MIN_PWM, min(self.MAX_PWM, pwm_val))

            # Log periodically to debug
            if not hasattr(self, '_mouth_log_counter'):
                self._mouth_log_counter = 0
            self._mouth_log_counter += 1
            if self._mouth_log_counter % 50 == 0:  # Log every 50 chunks (~1 second)
                self.log.info("BillyBass: volume=%.1f, peak=%.1f, pwm=%d", volume, peak, pwm_val)

            # Drive motor based on audio
            if pwm_val > 0:
                # Open mouth: drive motor forward
                GPIO.output(self.MOUTH_IN1, GPIO.HIGH)
                GPIO.output(self.MOUTH_IN2, GPIO.LOW)
                PWM.set_duty_cycle(self.MOUTH_PWM_PIN, pwm_val)
            else:
                # Close mouth: stop immediately
                # If transitioning from open to closed, briefly reverse to actively close
                if self._prev_pwm > 0:
                    # Transition: was open, now closing - briefly reverse to actively close
                    GPIO.output(self.MOUTH_IN1, GPIO.LOW)
                    GPIO.output(self.MOUTH_IN2, GPIO.HIGH)
                    PWM.set_duty_cycle(self.MOUTH_PWM_PIN, 25)  # Brief reverse pulse to close
                    # The next chunk (20ms later) will stop it, so this is just a quick pulse
                else:
                    # Already closed, ensure it stays stopped
                    PWM.set_duty_cycle(self.MOUTH_PWM_PIN, 0)
                    # Set both direction pins low to ensure no drift
                    GPIO.output(self.MOUTH_IN1, GPIO.LOW)
                    GPIO.output(self.MOUTH_IN2, GPIO.LOW)

            self._prev_pwm = pwm_val

        except Exception as e:
            self.log.exception("Error controlling motor: %s", e)

    def _stop_motor(self):
        """Stop the mouth motor by actively closing it, then setting PWM to 0."""
        if not self._initialized:
            return
        
        try:
            # Actively close mouth by briefly reversing motor direction
            GPIO.output(self.MOUTH_IN1, GPIO.LOW)
            GPIO.output(self.MOUTH_IN2, GPIO.HIGH)
            PWM.set_duty_cycle(self.MOUTH_PWM_PIN, 30)  # Brief reverse pulse to close
            # Small delay to let it close (this is in a thread, so OK)
            import time
            time.sleep(0.05)  # 50ms reverse pulse
            # Now stop
            PWM.set_duty_cycle(self.MOUTH_PWM_PIN, 0)
            GPIO.output(self.MOUTH_IN1, GPIO.LOW)
            GPIO.output(self.MOUTH_IN2, GPIO.LOW)
        except Exception as e:
            self.log.exception("Error stopping mouth motor: %s", e)

    async def tail_flap(self, duration_s: float = 0.5, speed: int = 100) -> None:
        """
        Animate tail flapping by rotating body motor in one direction.
        
        Args:
            duration_s: Duration of the flap animation in seconds
            speed: PWM duty cycle (0-100) for motor speed
        """
        if not self.enabled or not self._initialized:
            return
        
        try:
            # Set direction for tail flap (BODY_IN1=HIGH, BODY_IN2=LOW)
            GPIO.output(self.BODY_IN1, GPIO.HIGH)
            GPIO.output(self.BODY_IN2, GPIO.LOW)
            PWM.set_duty_cycle(self.BODY_PWM_PIN, min(100, max(0, speed)))
            
            await asyncio.sleep(duration_s)
            
            # Stop motor
            self.stop_body_motor()
        except Exception as e:
            self.log.exception("Error during tail flap: %s", e)
            self.stop_body_motor()

    async def head_turn(self, duration_s: float = 1.0, speed: int = 100) -> None:
        """
        Turn head by rotating body motor in opposite direction.
        
        Args:
            duration_s: Duration of the head turn in seconds (use float('inf') for continuous)
            speed: PWM duty cycle (0-100) for motor speed
        """
        if not self.enabled or not self._initialized:
            return
        
        try:
            # Set direction for head turn (BODY_IN1=LOW, BODY_IN2=HIGH)
            GPIO.output(self.BODY_IN1, GPIO.LOW)
            GPIO.output(self.BODY_IN2, GPIO.HIGH)
            PWM.set_duty_cycle(self.BODY_PWM_PIN, min(100, max(0, speed)))
            
            if duration_s != float('inf'):
                await asyncio.sleep(duration_s)
                self.stop_body_motor()
        except Exception as e:
            self.log.exception("Error during head turn: %s", e)
            self.stop_body_motor()

    def stop_body_motor(self) -> None:
        """Stop the body motor by setting PWM to 0."""
        if not self._initialized:
            return
        
        try:
            PWM.set_duty_cycle(self.BODY_PWM_PIN, 0)
        except Exception as e:
            self.log.exception("Error stopping body motor: %s", e)

    async def _listening_animation(self):
        """
        Occasional tail flaps while listening/waiting for speech.
        Creates a more natural, alive appearance.
        """
        if not self.enabled or not self._initialized:
            return
        
        try:
            import random
            while True:  # Run until cancelled
                # Wait a random time between flaps (2-5 seconds)
                wait_time = random.uniform(2.0, 5.0)
                await asyncio.sleep(wait_time)
                
                # Quick tail flap
                GPIO.output(self.BODY_IN1, GPIO.HIGH)
                GPIO.output(self.BODY_IN2, GPIO.LOW)
                PWM.set_duty_cycle(self.BODY_PWM_PIN, 70)
                await asyncio.sleep(0.2)  # Quick flap
                
                # Stop
                PWM.set_duty_cycle(self.BODY_PWM_PIN, 0)
        except asyncio.CancelledError:
            self.stop_body_motor()
            raise
        except Exception as e:
            self.log.exception("Error during listening animation: %s", e)
            self.stop_body_motor()

    async def _periodic_idle_flap(self):
        """
        Periodic tail flaps when idle (after client boots).
        Flaps every few seconds to keep the fish looking alive.
        Only flaps when no other body animation is active.
        """
        if not self.enabled or not self._initialized:
            return
        
        try:
            import random
            # Initial delay before first flap (let system settle)
            await asyncio.sleep(3.0)
            
            while True:  # Run until cancelled
                # Only flap if no active body task (not speaking, thinking, or listening)
                if self._body_task is None or self._body_task.done():
                    # Wait a random time between flaps (3-7 seconds)
                    wait_time = random.uniform(3.0, 7.0)
                    await asyncio.sleep(wait_time)
                    
                    # Double-check we're still idle before flapping
                    if self._body_task is None or self._body_task.done():
                        # Gentle tail flap
                        GPIO.output(self.BODY_IN1, GPIO.HIGH)
                        GPIO.output(self.BODY_IN2, GPIO.LOW)
                        PWM.set_duty_cycle(self.BODY_PWM_PIN, 60)
                        await asyncio.sleep(0.3)  # Gentle flap duration
                        
                        # Stop
                        PWM.set_duty_cycle(self.BODY_PWM_PIN, 0)
                else:
                    # Wait a bit before checking again if body task is active
                    await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            self.stop_body_motor()
            raise
        except Exception as e:
            self.log.exception("Error during periodic idle flap: %s", e)
            self.stop_body_motor()

    async def _on_ux_state(self, payload: dict):
        """Handle UX state changes to trigger body animations."""
        if not self.enabled:
            return
        
        try:
            event = UXState(**payload)
        except Exception:
            self.log.warning("malformed ux.state event, skipping")
            return
        
        state = event.state
        
        # Cancel any existing body animation task
        if self._body_task and not self._body_task.done():
            self._body_task.cancel()
            try:
                await self._body_task
            except asyncio.CancelledError:
                pass
            # Ensure motor stops when cancelling continuous animations
            self.stop_body_motor()
        
        if state == "thinking":
            # Occasional tail flaps while thinking
            self.log.debug("Thinking state: starting occasional tail flaps")
            self._body_task = asyncio.create_task(self._listening_animation())
        elif state == "listening":
            # Occasional tail flaps while listening
            self.log.debug("Listening state: starting occasional tail flaps")
            self._body_task = asyncio.create_task(self._listening_animation())
        elif state == "speaking":
            # Just turn head and look while speaking (continuous, gentle)
            self.log.debug("Speaking state: turning head to look")
            self._body_task = asyncio.create_task(self.head_turn(duration_s=float('inf'), speed=60))
        elif state == "idle":
            # Flap tail when done speaking, then stop (slower, more gentle)
            self.log.debug("Idle state: flapping tail, then stopping")
            self._body_task = asyncio.create_task(self.tail_flap(duration_s=0.7, speed=60))

    async def stop(self):
        """Cleanup resources before shutdown."""
        if not self.enabled:
            return
        
        self._stop_motor()
        self.stop_body_motor()
        
        # Cancel any running tasks
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
        
        if self._body_task and not self._body_task.done():
            self._body_task.cancel()
            try:
                await self._body_task
            except asyncio.CancelledError:
                pass
        
        if self._periodic_flap_task and not self._periodic_flap_task.done():
            self._periodic_flap_task.cancel()
            try:
                await self._periodic_flap_task
            except asyncio.CancelledError:
                pass

        # Cleanup hardware
        if self._initialized:
            try:
                PWM.stop(self.MOUTH_PWM_PIN)
                PWM.stop(self.BODY_PWM_PIN)
                PWM.cleanup()
                GPIO.cleanup()
                self._initialized = False
                self.log.info("Billy Bass hardware cleaned up")
            except Exception as e:
                self.log.exception("Error cleaning up hardware: %s", e)

