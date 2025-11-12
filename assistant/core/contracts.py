from dataclasses import dataclass, asdict, field
from typing import Any, Optional
import time
import uuid
import os

# Base Event
@dataclass(slots=True)
class Event:
    topic: str
    ts_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    corr_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def dict(self) -> dict[str, Any]:
        return asdict(self)

# Core Events

@dataclass(slots=True)
class AudioRecorded(Event):
    topic: str = "audio.recorded"
    wav_path: str = ""        # file path to recorded WAV
    duration_s: float = 0.0   # seconds

    def __post_init__(self) -> None:
        if not self.wav_path or self.duration_s <= 0.0:
            raise ValueError("AudioRecorded requires non-empty wav_path and duration_s > 0")
        # Optional existence check (best-effort; don't error hard)
        try:
            if self.wav_path.startswith("/") and not os.path.exists(self.wav_path):
                pass
        except Exception:
            pass

@dataclass(slots=True)
class STTTranscript(Event):
    topic: str = "stt.transcript"
    text: str = ""
    confidence: Optional[float] = None  # 0..1 optional
    # Optional per-word timing: [{"word":"hi","start":0.12,"end":0.28}]
    words: Optional[list[dict[str, Any]]] = None

@dataclass(slots=True)
class NLUIntent(Event):
    topic: str = "nlu.intent"
    intent: str = "unknown"   # e.g., "time", "timer", "weather"
    entities: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    original_text: str = ""

@dataclass(slots=True)
class SkillRequest(Event):
    topic: str = "skill.request"
    skill: str = ""           # target skill name (identity mapping by default)
    payload: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class SkillResponse(Event):
    topic: str = "skill.response"
    skill: str = ""
    say: Optional[str] = None     # simple text to speak (optional)
    data: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class TTSRequest(Event):
    topic: str = "tts.request"
    text: str = ""
    voice: Optional[str] = None   # adapter-specific (optional)

@dataclass(slots=True)
class TTSAudio(Event):
    topic: str = "tts.audio"
    wav_path: str = ""
    duration_s: float = 0.0

    def __post_init__(self) -> None:
        if not self.wav_path or self.duration_s <= 0.0:
            raise ValueError("TTSAudio requires non-empty wav_path and duration_s > 0")

@dataclass(slots=True)
class PlaybackStart(Event):
    topic: str = "audio.playback.start"
    wav_path: str = ""

@dataclass(slots=True)
class PlaybackEnd(Event):
    topic: str = "audio.playback.end"
    wav_path: str = ""
    ok: bool = True

# Fish mouth control
@dataclass(slots=True)
class MouthEnvelope(Event):
    topic: str = "anim.mouth.envelope"
    env: list[float] = field(default_factory=list)  # normalized [0..1]
    hop_ms: int = 20

# Fish state for debugging
@dataclass(slots=True)
class UXState(Event):
    topic: str = "ux.state"
    state: str = "idle"   # "idle","listening","thinking","speaking","error","muted"
    note: Optional[str] = None

# Debugging helper
def same_trace(parent: Event, child: Event) -> Event:
    """Copy corr_id so downstream events stay in the same trace."""
    child.corr_id = parent.corr_id
    return child

def to_dict(e: Event) -> dict[str, Any]:
    """Serialize any Event to a dict for the Bus or logging."""
    return e.dict()
