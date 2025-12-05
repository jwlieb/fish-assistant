"""
Conversation loop with VAD for continuous listening.

Continuously listens for audio, uses VAD to detect speech start/stop,
records when speech is detected, and triggers the pipeline.
"""

import asyncio
import logging
import queue
import time
from datetime import datetime

import numpy as np
import sounddevice as sd
import soundfile as sf
from typing import Optional, List

from ..bus import Bus
from ..contracts import AudioRecorded, PlaybackStart, PlaybackEnd, UXState, STTTranscript
from ..audio.vad import VAD, FRAME_SIZE, SR, CHANNELS, DTYPE
from ..audio.recorder import TMP_DIR

# Audio constants
BLOCKSIZE = 1024  # samples per callback (64ms at 16kHz)
SILENCE_FRAMES_THRESHOLD = 15  # ~450ms of silence to stop recording (increased to avoid false stops)
SPEECH_FRAMES_TO_START = 3  # ~90ms of speech to start recording (increased to reduce false positives)


class ConversationLoop:
    """
    Continuous conversation loop with VAD.
    
    States: idle → listening → recording → thinking → speaking → idle
    """

    def __init__(self, bus: Bus, vad: Optional[VAD] = None, device_index: Optional[int] = None):
        self.bus = bus
        self.vad = vad or VAD(aggressiveness=2)
        self.device_index = device_index
        self.log = logging.getLogger("conversation_loop")
        
        # State
        self.state = "idle"
        self.running = False
        self.audio_queue = queue.Queue()
        self.recording_buffer: List[np.ndarray] = []
        self.silence_frame_count = 0
        self.speech_frame_count = 0
        
    async def start(self):
        """Start the conversation loop."""
        if self.running:
            self.log.warning("Conversation loop already running")
            return
        
        # Subscribe to playback events to track state
        self.bus.subscribe("audio.playback.start", self._on_playback_start)
        self.bus.subscribe("audio.playback.end", self._on_playback_end)
        # Subscribe to STT transcripts to log detected text
        self.bus.subscribe("stt.transcript", self._on_transcript)
        
        self.running = True
        self.state = "idle"
        await self.bus.publish("ux.state", UXState(state="idle").dict())
        
        # Start the main loop
        await self._run_loop()
    
    async def stop(self):
        """Stop the conversation loop."""
        self.running = False
        self.log.info("Stopping conversation loop")
        await self.bus.publish("ux.state", UXState(state="idle", note="stopped").dict())
    
    async def _run_loop(self):
        """Main conversation loop."""
        self.log.info("Starting conversation loop (device: %s)", self.device_index)
        
        if self.device_index is not None:
            sd.default.device = (self.device_index, None)
        
        def audio_callback(indata, frames_count, time_info, status):
            """Called every ~64ms with 1024 samples."""
            if status:
                self.log.warning("Audio callback status: %s", status)
            if self.running:
                # Calculate audio level for debugging
                audio_level = np.abs(indata).mean()
                if not hasattr(self, '_audio_log_counter'):
                    self._audio_log_counter = 0
                self._audio_log_counter += 1
                # Log audio level every 50 callbacks (~3 seconds) to avoid spam
                if self._audio_log_counter % 50 == 0:
                    self.log.info("Audio input: level=%.4f (device=%s)", audio_level, self.device_index)
                self.audio_queue.put(indata.copy())
        
        try:
            with sd.InputStream(
                samplerate=SR,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCKSIZE,
                callback=audio_callback
            ):
                while self.running:
                    try:
                        if self.state == "idle":
                            await self._detect_speech_start()
                        elif self.state == "recording":
                            await self._detect_speech_end()
                        elif self.state == "thinking":
                            # Waiting for pipeline to process (with timeout)
                            if not hasattr(self, '_thinking_start_time'):
                                self._thinking_start_time = time.time()
                            # Timeout after 30 seconds - something went wrong
                            if time.time() - self._thinking_start_time > 30:
                                self.log.warning("Thinking state timeout, resetting to idle")
                                self.state = "idle"
                                delattr(self, '_thinking_start_time')
                            await asyncio.sleep(0.1)
                        elif self.state == "speaking":
                            # Waiting for TTS playback to finish (with timeout)
                            if not hasattr(self, '_speaking_start_time'):
                                self._speaking_start_time = time.time()
                            # Timeout after 60 seconds - playback probably finished
                            if time.time() - self._speaking_start_time > 60:
                                self.log.warning("Speaking state timeout, resetting to idle")
                                self.state = "idle"
                                await self.bus.publish("ux.state", UXState(state="idle").dict())
                                delattr(self, '_speaking_start_time')
                            await asyncio.sleep(0.1)
                        else:
                            self.log.warning("Unknown state: %s, resetting to idle", self.state)
                            self.state = "idle"
                        
                        await asyncio.sleep(0.01)  # Small delay to prevent busy-waiting
                    except Exception as e:
                        self.log.exception("Error in conversation loop state machine: %s", e)
                        # Reset to idle on error
                        self.state = "idle"
                        await asyncio.sleep(0.1)
                    
        except Exception as e:
            self.log.exception("Error in conversation loop: %s", e)
            await self.bus.publish("ux.state", UXState(state="error", note=str(e)).dict())
    
    async def _detect_speech_start(self):
        """Use VAD to detect when speech starts."""
        # Collect recent audio chunks (keep last 5 chunks = ~320ms for better detection)
        chunks = []
        while not self.audio_queue.empty() and len(chunks) < 5:
            chunks.append(self.audio_queue.get())
        
        if not chunks:
            return
        
        # Convert to single array
        recent_audio = np.concatenate(chunks)  # ~320ms = ~10-11 VAD frames
        
        # Calculate audio level for debugging
        audio_level = np.abs(recent_audio).mean() * 100 if len(recent_audio) > 0 else 0
        
        # Check each VAD frame (480 samples = 30ms)
        speech_frames_in_window = 0
        total_frames = 0
        consecutive_speech = 0
        max_consecutive = 0
        
        for i in range(0, len(recent_audio), FRAME_SIZE):
            frame = recent_audio[i:i + FRAME_SIZE]
            if len(frame) == FRAME_SIZE:
                total_frames += 1
                try:
                    is_speech = self.vad.is_speech(frame)
                    if is_speech:
                        speech_frames_in_window += 1
                        consecutive_speech += 1
                        max_consecutive = max(max_consecutive, consecutive_speech)
                    else:
                        consecutive_speech = 0
                except Exception as e:
                    self.log.warning("VAD error on frame: %s", e)
                    consecutive_speech = 0
        
        # Update speech_frame_count based on consecutive speech
        if max_consecutive > 0:
            self.speech_frame_count = max(self.speech_frame_count, max_consecutive)
        else:
            # Only reset if we've seen no speech for a while (allow brief pauses)
            if self.speech_frame_count > 0:
                self.speech_frame_count -= 1  # Decay instead of instant reset
        
        # Log VAD activity more frequently when audio level is high
        should_log = False
        if not hasattr(self, '_vad_log_counter'):
            self._vad_log_counter = 0
        self._vad_log_counter += 1
        
        # Log every 10 calls, or more frequently if audio level is high
        if self._vad_log_counter % 10 == 0 or audio_level > 20:
            should_log = True
        
        if should_log:
            self.log.info(
                "VAD: audio_level=%.1f, speech_frames=%d/%d, consecutive=%d, count=%d (need %d)",
                audio_level, speech_frames_in_window, total_frames, max_consecutive, 
                self.speech_frame_count, SPEECH_FRAMES_TO_START
            )
        
        # Start recording if we've seen enough speech frames (either consecutive or total)
        # Use a lower threshold if audio level is high (likely speech)
        threshold = SPEECH_FRAMES_TO_START if audio_level < 30 else max(1, SPEECH_FRAMES_TO_START - 1)
        
        if speech_frames_in_window >= 2 and self.speech_frame_count >= threshold:
            self.log.info("Speech detected! Starting recording (speech_frames=%d/%d, consecutive=%d, audio_level=%.1f)", 
                         speech_frames_in_window, total_frames, max_consecutive, audio_level)
            self.state = "recording"
            self.recording_buffer = chunks.copy()  # Include the chunks that triggered detection
            self.silence_frame_count = 0
            self.speech_frame_count = 0  # Reset after detection
            await self.bus.publish("ux.state", UXState(state="listening").dict())
    
    async def _detect_speech_end(self):
        """Use VAD to detect when speech ends (silence)."""
        # Collect audio chunks while recording
        while not self.audio_queue.empty():
            chunk = self.audio_queue.get()
            self.recording_buffer.append(chunk)
        
        # Check recent frames for silence (last 2 chunks = ~128ms)
        if len(self.recording_buffer) >= 2:
            recent = np.concatenate(self.recording_buffer[-2:])
            
            # Count speech frames in recent audio
            speech_frames = 0
            for i in range(0, len(recent), FRAME_SIZE):
                frame = recent[i:i + FRAME_SIZE]
                if len(frame) == FRAME_SIZE:
                    if self.vad.is_speech(frame):
                        speech_frames += 1
            
            # If no speech detected, increment silence counter
            if speech_frames == 0:
                self.silence_frame_count += 1
                if self.silence_frame_count >= SILENCE_FRAMES_THRESHOLD:
                    # Silence detected for threshold duration, stop recording
                    await self._stop_and_process()
            else:
                # Speech still detected, reset silence counter
                self.silence_frame_count = 0
    
    async def _stop_and_process(self):
        """Stop recording and trigger pipeline."""
        if not self.recording_buffer:
            self.log.warning("No audio recorded, returning to idle")
            self.state = "idle"
            await self.bus.publish("ux.state", UXState(state="idle").dict())
            return
        
        # Concatenate all recorded chunks
        full_audio = np.concatenate(self.recording_buffer)
        duration_s = len(full_audio) / SR
        
        # Minimum duration check - if too short, likely false positive or noise
        MIN_RECORDING_DURATION = 0.5  # 500ms minimum
        if duration_s < MIN_RECORDING_DURATION:
            self.log.warning("Recording too short (%.2fs < %.2fs), likely false positive, returning to idle", 
                           duration_s, MIN_RECORDING_DURATION)
            self.state = "idle"
            self.recording_buffer = []
            self.silence_frame_count = 0
            await self.bus.publish("ux.state", UXState(state="idle").dict())
            return
        
        # Save to WAV file
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        wav_path = TMP_DIR / f"conv-{timestamp}.wav"
        sf.write(str(wav_path), full_audio, SR, subtype="PCM_16")
        
        self.log.info("Recording complete: %s (%.2fs)", wav_path, duration_s)
        
        # Publish audio.recorded event → triggers STT pipeline
        audio_event = AudioRecorded(
            wav_path=str(wav_path),
            duration_s=duration_s
        )
        await self.bus.publish(audio_event.topic, audio_event.dict())
        
        # Transition to thinking state
        self.state = "thinking"
        self.recording_buffer = []
        self.silence_frame_count = 0
        self._thinking_start_time = time.time()
        await self.bus.publish("ux.state", UXState(state="thinking").dict())
    
    async def _on_playback_start(self, payload: dict):
        """When TTS playback starts, update state to speaking."""
        try:
            playback_event = PlaybackStart(**payload)
            if self.state in ("thinking", "idle"):  # Allow transition from idle too (in case we missed thinking)
                self.log.info("Playback started, fish is speaking")
                self.state = "speaking"
                self._speaking_start_time = time.time()
                await self.bus.publish("ux.state", UXState(state="speaking").dict())
        except Exception as e:
            self.log.warning("Error handling playback.start: %s", e)
    
    async def _on_playback_end(self, payload: dict):
        """When TTS playback finishes, resume listening."""
        try:
            playback_event = PlaybackEnd(**payload)
            if playback_event.ok and self.state in ("thinking", "speaking"):
                self.log.info("Playback complete, resuming listening")
                self.state = "idle"
                await self.bus.publish("ux.state", UXState(state="idle").dict())
        except Exception as e:
            self.log.warning("Error handling playback.end: %s", e)
    
    async def _on_transcript(self, payload: dict):
        """When STT detects text, log it and reset state if empty."""
        try:
            transcript_event = STTTranscript(**payload)
            if not transcript_event.text or not transcript_event.text.strip():
                # Empty transcription - reset to idle immediately
                self.log.info("Empty transcription received, resetting to idle")
                if self.state == "thinking":
                    self.state = "idle"
                    await self.bus.publish("ux.state", UXState(state="idle").dict())
                return
            
            self.log.info("TEXT DETECTED: '%s'", transcript_event.text)
            if transcript_event.confidence is not None:
                self.log.debug("   Confidence: %.2f", transcript_event.confidence)
        except Exception as e:
            self.log.warning("Error handling stt.transcript: %s", e)
            # On error, also reset to idle to prevent getting stuck
            if self.state == "thinking":
                self.log.info("Error handling transcript, resetting to idle")
                self.state = "idle"
                await self.bus.publish("ux.state", UXState(state="idle").dict())

