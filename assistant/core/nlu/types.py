from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass(slots=True)
class NLUResult:
    intent: str = "unknown"
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    original_text: str = ""