import asyncio
import os
import logging

try:
    import soundfile as sf
except ImportError:
    sf = None
from ..contracts import TTSAudio, PlaybackStart, PlaybackEnd, same_trace
from .devices import get_default_output_index, list_output_devices
from typing import Optional

# Lazy import sounddevice to avoid initialization errors on systems without audio devices
try:
    import sounddevice as sd
    SD_AVAILABLE = True
    # Try to query output devices to verify sounddevice is working
    try:
        devices = sd.query_devices()
        output_devices = [d for d in devices if d.get("max_output_channels", 0) > 0]
        logging.getLogger("playback").info("sounddevice available: %d output devices found", len(output_devices))
        if output_devices:
            default_out = sd.default.device[1] if isinstance(sd.default.device, (list, tuple)) and len(sd.default.device) > 1 else None
            logging.getLogger("playback").info("Default output device: %s", default_out)
    except Exception as e:
        logging.getLogger("playback").warning("sounddevice available but cannot query devices: %s", e)
except Exception as e:
    SD_AVAILABLE = False
    logging.getLogger("playback").warning("sounddevice not available: %s", e)

class Playback:
    """
    Listens on 'tts.audio' and emits 'audio.playback.start' and 'audio.playback.end'.
    Plays audio file and cleans it up after playback.
    """

    def __init__(self, bus, output_device: Optional[int] = None):
        self.bus = bus
        self.log = logging.getLogger("playback")
        self.output_device = output_device
        # Cache output device on first use
        self._cached_output_device = None

    async def start(self):
        self.bus.subscribe("tts.audio", self._on_audio)
        self.log.info("Playback: Subscribed to tts.audio events")

    async def _on_audio(self, payload: dict):
        self.log.info("Playback: Received tts.audio event (payload keys: %s)", list(payload.keys()) if isinstance(payload, dict) else "not a dict")
        
        if not SD_AVAILABLE:
            self.log.error("Playback: sounddevice not available, cannot play audio.")
            return
        
        if sf is None:
            self.log.error("Playback: soundfile not available, cannot play audio.")
            return
        
        self.log.info("Playback: sounddevice is available, proceeding with playback")
        
        try:
            audio_event = TTSAudio(**payload)
            self.log.info("Playback: Parsed audio event: %s (%.2fs)", audio_event.wav_path, audio_event.duration_s)
        except Exception:
            self.log.warning("Playback: malformed tts.audio event, skipping")
            return

        path = audio_event.wav_path
        if not path or not os.path.exists(path):
            self.log.warning("Playback: missing or invalid path: %s", path)
            return
        
        try:
            # Gather info
            size_bytes = os.path.getsize(path)
            info = sf.info(path)
            duration = info.frames / float(info.samplerate) if info.samplerate else 0.0
            self.log.info("Playback: Starting playback: %s (%.2fs, %d bytes, %d Hz, %d ch)", 
                          path, duration, size_bytes, info.samplerate, info.channels)
            
            # Emit playback start
            start_event = PlaybackStart(wav_path=path)
            same_trace(audio_event, start_event)
            await self.bus.publish(start_event.topic, start_event.dict())
            
            # Read audio data (non-blocking)
            data, sr = sf.read(path, dtype="float32", always_2d=True)

            # Get output device (cache on first use)
            if self._cached_output_device is None:
                if self.output_device is not None:
                    self._cached_output_device = self.output_device
                    self.log.info("Playback: Using configured output device: %d", self.output_device)
                else:
                    # Try to find a valid output device
                    output_devices = list_output_devices()
                    if output_devices:
                        self.log.info("Playback: Found %d output devices: %s", 
                                    len(output_devices), [(idx, name) for idx, name in output_devices])
                        self._cached_output_device = get_default_output_index()
                        if self._cached_output_device is None and output_devices:
                            # Fallback to first available output device
                            self._cached_output_device = output_devices[0][0]
                            self.log.info("Playback: Using first available output device: %d (%s)", 
                                        self._cached_output_device, output_devices[0][1])
                        elif self._cached_output_device is not None:
                            self.log.info("Playback: Using default output device: %d", self._cached_output_device)
                    else:
                        self.log.warning("Playback: No output devices found, will try without specifying device")
            
            # Non-blocking play start
            self.log.info("Playback: Starting audio device playback (data shape: %s, sample rate: %d Hz, device: %s)...", 
                         data.shape, sr, self._cached_output_device)
            
            # Try to play with the cached device, fallback to other devices if it fails
            play_success = False
            devices_to_try = []
            if self._cached_output_device is not None:
                devices_to_try.append(self._cached_output_device)
            # Add other output devices as fallbacks
            all_outputs = list_output_devices()
            for idx, name in all_outputs:
                if idx not in devices_to_try:
                    devices_to_try.append(idx)
            
            # Try playing with current sample rate
            for device_idx in devices_to_try:
                try:
                    self.log.info("Playback: Trying device %d at %d Hz...", device_idx, sr)
                    sd.play(data, sr, device=device_idx)
                    self.log.info("Playback: sd.play() called successfully with device %d, waiting for playback to finish...", device_idx)
                    play_success = True
                    break
                except Exception as e:
                    self.log.warning("Playback: Failed to play with device %d: %s", device_idx, e)
                    continue
            
            if not play_success:
                # Last resort: try without specifying device
                try:
                    self.log.info("Playback: Trying without specifying device (using system default) at %d Hz...", sr)
                    sd.play(data, sr)
                    self.log.info("Playback: sd.play() called successfully without device")
                    play_success = True
                except Exception as e:
                    self.log.error("Playback: Failed to play audio with any device: %s", e)
                    raise
            
            if not play_success:
                raise RuntimeError("Failed to start audio playback with any available device")
            
            # blocking wait (Python 3.7 compatible)
            self.log.info("Playback: Waiting for playback to finish...")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, sd.wait)
            self.log.info("Playback: Audio playback finished")

            # Emit playback end
            end_event = PlaybackEnd(wav_path=path, ok=True)
            same_trace(audio_event, end_event)
            await self.bus.publish(end_event.topic, end_event.dict())
            self.log.info("Playback: Published playback.end event")

        except Exception as e:
            self.log.exception("failed to play %s", path)
            # Emit error end event
            end_event = PlaybackEnd(wav_path=path, ok=False)
            same_trace(audio_event, end_event)
            await self.bus.publish(end_event.topic, end_event.dict())
            return
        
        # Cleanup in worker thread (Python 3.7 compatible)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._safe_cleanup, path) 

    # Cleanup logic
    def _safe_cleanup(self, path):
        try:
            os.remove(path)
            self.log.debug("cleaned up: %s", path)
        except Exception:
            # Note: logging exception from a thread requires care, 
            # but this synchronous approach is simpler here.
            self.log.exception("failed to cleanup: %s", path)