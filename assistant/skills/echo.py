from assistant.core.contracts import SkillRequest, SkillResponse, same_trace

class EchoSkill:
    def __init__(self, bus):
        self.bus = bus

    async def start(self):
        self.bus.subscribe("skill.request", self._on_request)

    async def _on_request(self, payload: dict):
        try:
            req = SkillRequest(**payload)
        except Exception:
            return
        
        if req.skill != "echo":
            return
        
        original_text = req.payload.get("original_text", "").strip()
        if not original_text:
            return
        
        resp = SkillResponse(skill="echo", say=f"You said: {original_text}")
        same_trace(req, resp)
        await self.bus.publish(resp.topic, resp.dict())