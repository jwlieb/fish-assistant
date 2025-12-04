import logging
from typing import Optional
from .rules import RulesNLU
from .types import NLUResult
from ..contracts import STTTranscript, NLUIntent, same_trace

class NLU:
    """
    Listens on 'stt.transcript' and emits 'nlu.intent'.
    Uses RulesNLU adapter for classification.
    """

    def __init__(self, bus, adapter: Optional[RulesNLU] = None):
        self.bus = bus
        self.adapter = adapter or RulesNLU()
        self.log = logging.getLogger("nlu")

    async def start(self):
        self.bus.subscribe("stt.transcript", self._on_transcript)

    async def _on_transcript(self, payload: dict):
        self.log.info("NLU: Received stt.transcript event")
        try:
            stt_event = STTTranscript(**payload)
            self.log.info("NLU: Parsed transcript: '%s'", stt_event.text)
        except Exception:
            self.log.warning("NLU: Malformed stt.transcript event, skipping")
            return

        text = stt_event.text.strip()
        if not text:
            self.log.warning("NLU: Empty transcript, skipping")
            return

        self.log.info("NLU: Classifying text: '%s'", text)
        result: NLUResult = await self.adapter.classify(text)

        nlu_event = NLUIntent(
            intent=result.intent,
            entities=result.entities,
            confidence=result.confidence,
            original_text=result.original_text,
        )
        same_trace(stt_event, nlu_event)
        
        self.log.info("NLU: Intent detected: %s (confidence: %.2f)", result.intent, result.confidence)
        self.log.info("NLU: Publishing nlu.intent event")
        await self.bus.publish(nlu_event.topic, nlu_event.dict())
        self.log.info("NLU: Published nlu.intent event successfully")

