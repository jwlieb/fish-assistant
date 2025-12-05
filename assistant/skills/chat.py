"""
Simple conversational AI skill using Groq API.
"""

import logging
import os
import asyncio
from typing import Optional
from assistant.core.contracts import SkillRequest, SkillResponse, same_trace

logger = logging.getLogger("chat_skill")

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not available. Install with: pip install httpx")


class ChatSkill:
    """Simple chat skill using Groq API for AI responses."""
    
    def __init__(self, bus):
        self.bus = bus
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        
        if not self.api_key:
            logger.warning("GROQ_API_KEY not set. Chat skill will not work. Get a free key at https://console.groq.com/")
        else:
            logger.info(f"ChatSkill initialized with model: {self.model}")

    async def start(self):
        if not HTTPX_AVAILABLE:
            logger.error("ChatSkill: httpx not available, cannot make API calls")
            return
        if not self.api_key:
            logger.error("ChatSkill: GROQ_API_KEY not set, chat skill disabled")
            return
        self.bus.subscribe("skill.request", self._on_request)

    async def _on_request(self, payload: dict):
        try:
            req = SkillRequest(**payload)
        except Exception:
            return
        
        if req.skill != "chat":
            return
        
        original_text = req.payload.get("original_text", "").strip()
        if not original_text:
            return
        
        logger.info("ChatSkill: Generating response for: '%s'", original_text)
        
        try:
            response_text = await self._groq_chat(original_text)
            
            if not response_text:
                response_text = "I'm not sure how to respond to that."
            
            resp = SkillResponse(skill="chat", say=response_text)
            same_trace(req, resp)
            await self.bus.publish(resp.topic, resp.dict())
            
        except Exception as e:
            logger.exception("ChatSkill: Error generating response: %s", e)
            resp = SkillResponse(skill="chat", say="Sorry, I'm having trouble connecting right now.")
            same_trace(req, resp)
            await self.bus.publish(resp.topic, resp.dict())

    async def _groq_chat(self, user_input: str) -> Optional[str]:
        """Generate response using Groq API."""
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a witty talking fish assistant who speaks only in rhymes. Keep responses brief and conversational, under 50 words."
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            
            return None

