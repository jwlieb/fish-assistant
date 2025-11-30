import asyncio
import logging
from assistant.core.bus import Bus
from assistant.core.router import Router
from assistant.core.nlu.nlu import NLU
from assistant.core.audio.playback import Playback
from assistant.core.audio.billy_bass import BillyBass
from assistant.core.tts.tts import TTS
from assistant.core.stt.stt import STT
from assistant.skills.echo import EchoSkill


async def start_components(bus: Bus) -> None:
    """Subscribe components to the bus."""
    # Instantiate components with shared bus
    router = Router(bus)  # routes nlu.intent → skill.request, skill.response → tts.request
    router.register_intent("unknown", "echo")  # route unknown intents to echo skill for testing
    stt = STT(bus)  # listens on audio.recorded → emits stt.transcript
    nlu = NLU(bus)  # listens on stt.transcript → emits nlu.intent
    playback = Playback(bus)  # listens on tts.audio → plays audio
    billy_bass = BillyBass(bus)  # listens on audio.playback.start/end → controls mouth motor
    tts = TTS(bus)  # listens on tts.request → emits tts.audio
    echo_skill = EchoSkill(bus)  # listens on skill.request → emits skill.response

    # Subscribe handlers (order doesn't matter for pub/sub)
    await stt.start()
    await nlu.start()
    await playback.start()
    await billy_bass.start()
    await tts.start()
    await echo_skill.start()


async def repl(bus: Bus) -> None:
    """Tiny REPL that publishes stt.transcript to test full pipeline."""
    print("\n🐟 Fish Assistant Interactive Mode")
    print("Type a message to test NLU → Skills → TTS. Type 'quit' to exit.")

    loop = asyncio.get_running_loop() # get the current loop for running sync code

    while True:
        try:
            # explicit print (main thread)
            print("\n> ", end="", flush=True)
            # input in worker thread to keep event loop responsive
            user_input = await asyncio.to_thread(input)
            user_input = user_input.strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                break

            if user_input:
                # publish as stt.transcript to test full pipeline
                from assistant.core.contracts import STTTranscript
                stt_event = STTTranscript(text=user_input)
                await bus.publish(stt_event.topic, stt_event.dict())

        except KeyboardInterrupt:
            break
        except EOFError:
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
