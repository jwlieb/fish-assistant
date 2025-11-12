from typing import Dict, Awaitable, Callable

from .bus import Bus
from .contracts import NLUIntent, SkillRequest, SkillResponse, TTSRequest, same_trace

Handler = Callable[[Dict], Awaitable[None]]

class Router:
    """
    Tiny router:
      - Listens for NLUIntent and forwards as SkillRequest (intent name == skill name).
      - If a skill returns a simple 'say', forward it to TTSRequest.
    """

    def __init__(self, bus: Bus):
        self.bus = bus
        # Keep policy empty and identity by default; add overrides only when needed.
        self.intent_to_skill: dict[str, str] = {}

        self.bus.subscribe("nlu.intent", self._on_nlu_intent)
        self.bus.subscribe("skill.response", self._on_skill_response)

    def _resolve_skill(self, intent: str) -> str:
        # Identity by default; override via self.intent_to_skill[...] when necessary.
        return self.intent_to_skill.get(intent, intent)

    async def _on_nlu_intent(self, payload: Dict) -> None:
        # Parse to regain type safety; drop silently if malformed (simple behavior).
        try:
            e = NLUIntent(**payload)
        except Exception:
            return

        skill = self._resolve_skill(e.intent)
        if not skill:
            return

        req = SkillRequest(
            skill=skill,
            payload={"entities": e.entities, "original_text": e.original_text, "confidence": e.confidence},
        )
        same_trace(e, req)
        await self.bus.publish(req.topic, req.dict())

    async def _on_skill_response(self, payload: Dict) -> None:
        try:
            e = SkillResponse(**payload)
        except Exception:
            return

        if not e.say:
            return

        tts = TTSRequest(text=e.say)
        same_trace(e, tts)
        await self.bus.publish(tts.topic, tts.dict())

    # Optional: override routes in tests or future plugins
    def register_intent(self, intent: str, skill: str) -> None:
        self.intent_to_skill[intent] = skill
