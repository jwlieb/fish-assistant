from faster_whisper import WhisperModel
from pathlib import Path
from typing import Literal

def transcribe_file(path: str | Path, model_size: Literal["tiny","base","small","medium"]="tiny") -> str:
    """
    Transcribe a WAV file using faster-whisper. Returns text string.
    """
    model = WhisperModel(model_size, device="cpu", compute_type="int8")  # simple default
    segments, _info = model.transcribe(str(path), vad_filter=True)
    chunks = []
    for seg in segments:
        if seg.text:
            chunks.append(seg.text.strip())
    return " ".join(chunks).strip()