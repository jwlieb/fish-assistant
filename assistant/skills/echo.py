class EchoSkill:
    def __init__(self, bus):
        self.bus = bus

    async def start(self):
        self.bus.subscribe("stt.transcript", self._on_transcript)

    async def _on_transcript(self, payload: dict):
        text = (payload or {}).get("text", "").strip()
        if not text:
            return
        reply = f"You said: {text}"
        await self.bus.publish("assistant.reply", {"text": reply})