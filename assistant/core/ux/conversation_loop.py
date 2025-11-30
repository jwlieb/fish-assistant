"""
Conversation loop with VAD for continuous listening.

Continuously listens for audio, uses VAD to detect speech start/stop,
records when speech is detected, and triggers the pipeline.
"""

import asyncio
import logging
import queue
from datetime import datetime

import numpy as np
import sounddevice as sd
import soundfile as sf

from ..bus import Bus
from ..contracts import AudioRecorded, PlaybackStart, PlaybackEnd, UXState
from ..audio.vad import VAD, FRAME_SIZE, SR, CHANNELS, DTYPE
from ..audio.recorder import TMP_DIR

# Audio constants
BLOCKSIZE = 1024  # samples per callback (64ms at 16kHz)
SILENCE_FRAMES_THRESHOLD = 10  # ~300ms of silence to stop recording
SPEECH_FRAMES_TO_START = 2  # ~60ms of speech to start recording


class ConversationLoop:
    """
    Continuous conversation loop with VAD.
    
    States: idle → listening → recording → thinking → speaking → idle
    """

    def __init__(self, bus: Bus, vad: VAD | None = None, device_index: int | None = None):
        self.bus = bus
        self.vad = vad or VAD(aggressiveness=2)
        self.device_index = device_index
        self.log = logging.getLogger("conversation_loop")
        
        # State
        self.state = "idle"
        self.running = False
        self.audio_queue = queue.Queue()
        self.recording_buffer: list[np.ndarray] = []
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
                    if self.state == "idle":
                        await self._detect_speech_start()
                    elif self.state == "recording":
                        await self._detect_speech_end()
                    elif self.state == "thinking":
                        # Waiting for pipeline to process
                        await asyncio.sleep(0.1)
                    elif self.state == "speaking":
                        # Waiting for TTS playback to finish
                        await asyncio.sleep(0.1)
                    
                    await asyncio.sleep(0.01)  # Small delay to prevent busy-waiting
                    
        except Exception as e:
            self.log.exception("Error in conversation loop: %s", e)
            await self.bus.publish("ux.state", UXState(state="error", note=str(e)).dict())
    
    async def _detect_speech_start(self):
        """Use VAD to detect when speech starts."""
        # Collect recent audio chunks (keep last 3 chunks = ~192ms)
        chunks = []
        while not self.audio_queue.empty() and len(chunks) < 3:
            chunks.append(self.audio_queue.get())
        
        if not chunks:
            return
        
        # Convert to single array
        recent_audio = np.concatenate(chunks)  # ~192ms = ~6-7 VAD frames
        
        # Check each VAD frame (480 samples = 30ms)
        speech_detected = False
        for i in range(0, len(recent_audio), FRAME_SIZE):
            frame = recent_audio[i:i + FRAME_SIZE]
            if len(frame) == FRAME_SIZE:
                if self.vad.is_speech(frame):
                    speech_detected = True
                    self.speech_frame_count += 1
                else:
                    self.speech_frame_count = 0
        
        # Start recording if we've seen enough consecutive speech frames
        if speech_detected and self.speech_frame_count >= SPEECH_FRAMES_TO_START:
            self.log.info("Speech detected, starting recording")
            self.state = "recording"
            self.recording_buffer = chunks.copy()  # Include the chunks that triggered detection
            self.silence_frame_count = 0
            self.speech_frame_count = 0
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
            return
        
        # Concatenate all recorded chunks
        full_audio = np.concatenate(self.recording_buffer)
        duration_s = len(full_audio) / SR
        
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
        await self.bus.publish("ux.state", UXState(state="thinking").dict())
    
    async def _on_playback_start(self, payload: dict):
        """When TTS playback starts, update state to speaking."""
        try:
            playback_event = PlaybackStart(**payload)
            if self.state == "thinking":
                self.log.info("Playback started, fish is speaking")
                self.state = "speaking"
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

