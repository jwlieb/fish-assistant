import asyncio
import logging
from assistant.core.bus import Bus
from assistant.core.audio.playback import Playback
from assistant.core.tts.tts import TTS


async def start_components(bus: Bus) -> None:
    """Subscribe components to the bus."""
    # Instantiate components with shared bus
    playback = Playback(bus)
    tts = TTS(bus)

    # Subscribe handlers
    await playback.start()
    await tts.start()


async def repl(bus: Bus) -> None:
    """Tiny REPL that publishes directly to assistant.reply to trigger TTS."""
    print("\n🐟 Fish Assistant Interactive Mode")
    print("Type a message to hear TTS. Type 'quit' to exit.")
    while True:
        try:
            user_input = input("\n> ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                break
            if user_input:
                await bus.publish("assistant.reply", {"text": user_input})
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            break


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    bus = Bus()
    print("🐟 Starting Fish Assistant...")
    await start_components(bus)
    print("🐟 Components ready.")
    await repl(bus)
    bus.clear()
    print("🐟 Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
