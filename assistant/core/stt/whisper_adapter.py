from faster_whisper import WhisperModel
from pathlib import Path
from typing import Literal

def transcribe_file(path: str | Path, model_size: Literal["tiny","base","small","medium"]="tiny") -> str:
    """
    Transcribe a WAV file using faster-whisper. Returns text string.
    
    Note: This function is kept for backward compatibility.
    Consider using WhisperAdapter class for better integration.
    """
    model = WhisperModel(model_size, device="cpu", compute_type="int8")  # simple default
    segments, _info = model.transcribe(str(path), vad_filter=True)
    chunks = []
    for seg in segments:
        if seg.text:
            chunks.append(seg.text.strip())
    return " ".join(chunks).strip()


class WhisperAdapter:
    """
    Local STT adapter using faster-whisper.
    
    Usage:
        adapter = WhisperAdapter(model_size="tiny")
        text = adapter.transcribe("audio.wav")
    """
    
    def __init__(self, model_size: Literal["tiny", "base", "small", "medium"] = "tiny"):
        """
        Initialize Whisper adapter.
        
        Args:
            model_size: Whisper model size to use
        """
        self.model_size = model_size
    
    def transcribe(self, path: str | Path) -> str:
        """
        Transcribe audio file using local Whisper model.
        
        Args:
            path: Path to WAV file
        
        Returns:
            Transcribed text string
        """
        return transcribe_file(path, self.model_size)