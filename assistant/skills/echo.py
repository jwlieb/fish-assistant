import logging
from assistant.core.contracts import SkillRequest, SkillResponse, same_trace

logger = logging.getLogger("echo_skill")

class EchoSkill:
    def __init__(self, bus):
        self.bus = bus

    async def start(self):
        self.bus.subscribe("skill.request", self._on_request)

    async def _on_request(self, payload: dict):
        logger.info("EchoSkill: Received skill.request event")
        try:
            req = SkillRequest(**payload)
            logger.info("EchoSkill: Parsed request for skill: %s", req.skill)
        except Exception:
            logger.warning("EchoSkill: Malformed skill.request, skipping")
            return
        
        if req.skill != "echo":
            logger.debug("EchoSkill: Not for echo skill, ignoring")
            return
        
        original_text = req.payload.get("original_text", "").strip()
        if not original_text:
            logger.warning("EchoSkill: No original_text in payload")
            return
        
        logger.info("EchoSkill: Generating response for: '%s'", original_text)
        resp = SkillResponse(skill="echo", say=f"You said: {original_text}")
        same_trace(req, resp)
        logger.info("EchoSkill: Publishing skill.response: '%s'", resp.say)
        await self.bus.publish(resp.topic, resp.dict())
        logger.info("EchoSkill: Published skill.response successfully")