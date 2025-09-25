from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import queue
import sys
import tempfile

import numpy as np
import sounddevice as sd
import soundfile as sf

# audio constants
SR = 16_000          # sample rate (Hz)
CHANNELS = 1         # mono
DTYPE = "int16"      # 16-bit PCM
BLOCKSIZE = 1024     # frames per audio callback

TMP_DIR = Path(tempfile.gettempdir()) / "fish"
TMP_DIR.mkdir(parents=True, exist_ok=True)

@dataclass
class RecordResult:
    path: Path
    duration_s: float
    sr: int = SR

def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def record_wav(duration_s: float = 5.0, device_index: int | None = None) -> RecordResult:
    """
    Record mono PCM16 WAV up to `duration_s`. Returns file path + duration.
    """
    if device_index is not None:
        sd.default.device = (device_index, None)

    q = queue.Queue()
    frames: list[np.ndarray] = []

    def _callback(indata, frames_count, time_info, status):
        if status:
            print(f"[audio] {status}", file=sys.stderr)
        q.put(indata.copy())

    with sd.InputStream(
        samplerate=SR, channels=CHANNELS, dtype=DTYPE, blocksize=BLOCKSIZE, callback=_callback
    ):
        sd.sleep(int(duration_s * 1000))
        while not q.empty():
            frames.append(q.get())

    audio = np.concatenate(frames, axis=0) if frames else np.zeros((1, CHANNELS), dtype=DTYPE)

    out = TMP_DIR / f"rec-{_stamp()}.wav"
    sf.write(out.as_posix(), audio, SR, subtype="PCM_16")

    return RecordResult(path=out, duration_s=len(audio) / SR)

def playback_wav(path: Path) -> None:
    """Blocking playback of a WAV/AIFF/etc file."""
    data, sr = sf.read(path.as_posix(), dtype="float32", always_2d=True)
    sd.play(data, sr, blocking=True)
