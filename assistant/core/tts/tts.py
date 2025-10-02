import asyncio
import logging
from assistant.core.tts.pyttsx3_adapter import Pyttsx3Adapter

class TTS:
    """
    Listens on 'assistant.reply' with payload {'text': str}
    Emits 'playback' with payload {'path': str, 'cleanup': bool}
    """

    def __init__(self, bus, adapter: Pyttsx3Adapter | None = None):
        self.bus = bus
        self.adapter = adapter or Pyttsx3Adapter()
        self.log = logging.getLogger("tts")

    async def start(self):
        self.bus.subscribe("assistant.reply", self._on_reply)

    async def _on_reply(self, payload: dict):
        text = (payload or {}).get("text", "").strip()
        if not text:
            self.log.debug("empty reply text, skipping")
            return
        # run blocking synth in thread
        self.log.info("synthesizing text (%d chars)", len(text))
        path = await asyncio.to_thread(self.adapter.synth, text)
        self.log.debug("synth complete: %s", path)
        await self.bus.publish("playback", {
            "path": path,
            "cleanup": True,
            "source": "tts",
        })