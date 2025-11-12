import logging
from .rules import RulesNLU
from .types import NLUResult
from ..contracts import STTTranscript, NLUIntent, same_trace

class NLU:
    """
    Listens on 'stt.transcript' and emits 'nlu.intent'.
    Uses RulesNLU adapter for classification.
    """

    def __init__(self, bus, adapter: RulesNLU | None = None):
        self.bus = bus
        self.adapter = adapter or RulesNLU()
        self.log = logging.getLogger("nlu")

    async def start(self):
        self.bus.subscribe("stt.transcript", self._on_transcript)

    async def _on_transcript(self, payload: dict):
        try:
            stt_event = STTTranscript(**payload)
        except Exception:
            self.log.warning("malformed stt.transcript event, skipping")
            return

        text = stt_event.text.strip()
        if not text:
            self.log.debug("empty transcript, skipping")
            return

        self.log.info("classifying: %s", text)
        result: NLUResult = await self.adapter.classify(text)

        nlu_event = NLUIntent(
            intent=result.intent,
            entities=result.entities,
            confidence=result.confidence,
            original_text=result.original_text,
        )
        same_trace(stt_event, nlu_event)
        
        self.log.info("intent: %s (confidence: %.2f)", result.intent, result.confidence)
        await self.bus.publish(nlu_event.topic, nlu_event.dict())

