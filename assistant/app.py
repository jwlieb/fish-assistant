import asyncio
import logging
from assistant.core.bus import Bus
from assistant.core.config import Config
from assistant.core.router import Router
from assistant.core.nlu.nlu import NLU
from assistant.core.audio.playback import Playback
from assistant.core.audio.billy_bass import BillyBass
from assistant.core.tts.tts import TTS
from assistant.core.stt.stt import STT
from assistant.skills.echo import EchoSkill


async def _start_core_components(bus: Bus, stt_adapter, tts_adapter, skip_playback: bool = False) -> None:
    """Internal helper to start core components with given adapters."""
    router = Router(bus)
    router.register_intent("unknown", "echo")
    
    stt = STT(bus, adapter=stt_adapter)
    nlu = NLU(bus)
    playback = Playback(bus) if not skip_playback else None
    billy_bass = BillyBass(bus, enabled=Config.BILLY_BASS_ENABLED)
    tts = TTS(bus, adapter=tts_adapter)
    echo_skill = EchoSkill(bus)

    await stt.start()
    await nlu.start()
    if playback:
        await playback.start()
    await billy_bass.start()
    await tts.start()
    await echo_skill.start()


async def start_full_components(bus: Bus) -> None:
    """Start all components for full mode (everything local)."""
    stt_adapter = Config.get_stt_adapter()
    tts_adapter = Config.get_tts_adapter()
    await _start_core_components(bus, stt_adapter, tts_adapter)


async def start_server_components(bus: Bus) -> None:
    """Start components for server mode (microphone + full pipeline + HTTP server)."""
    # Use local adapters (server processes everything locally)
    from assistant.core.stt.whisper_adapter import WhisperAdapter
    from assistant.core.tts.pyttsx3_adapter import Pyttsx3Adapter
    
    stt_adapter = WhisperAdapter(model_size=Config.STT_MODEL_SIZE)
    tts_adapter = Pyttsx3Adapter(voice=Config.TTS_VOICE)
    
    # If CLIENT_SERVER_URL is configured, skip local playback (audio goes to client)
    skip_playback = bool(Config.CLIENT_SERVER_URL)
    await _start_core_components(bus, stt_adapter, tts_adapter, skip_playback=skip_playback)
    
    # If CLIENT_SERVER_URL is configured, push audio to client instead of playing locally
    if Config.CLIENT_SERVER_URL:
        from assistant.core.audio.client_push import ClientAudioPush
        client_push = ClientAudioPush(bus)
        await client_push.start()
        logging.info("Client audio push enabled, audio will be sent to: %s", Config.CLIENT_SERVER_URL)


async def start_client_components(bus: Bus) -> None:
    """Start components for client mode (playback + motors + remote adapters)."""
    # Client uses remote adapters to call server
    stt_adapter = Config.get_stt_adapter()  # Will return RemoteSTTAdapter if STT_MODE=remote
    tts_adapter = Config.get_tts_adapter()  # Will return RemoteTTSAdapter if TTS_MODE=remote
    
    # Ensure we're using remote adapters in client mode
    if Config.STT_MODE != "remote":
        logging.warning("Client mode should use remote STT. Setting STT_MODE=remote")
        from assistant.core.stt.remote_stt_adapter import RemoteSTTAdapter
        stt_adapter = RemoteSTTAdapter(
            server_url=Config.STT_SERVER_URL,
            model_size=Config.STT_MODEL_SIZE,
            timeout=Config.STT_TIMEOUT,
        )
    
    if Config.TTS_MODE != "remote":
        logging.warning("Client mode should use remote TTS. Setting TTS_MODE=remote")
        from assistant.core.tts.remote_tts_adapter import RemoteTTSAdapter
        tts_adapter = RemoteTTSAdapter(
            server_url=Config.TTS_SERVER_URL,
            voice=Config.TTS_VOICE,
            timeout=Config.TTS_TIMEOUT,
        )
    
    # Create components - client only needs playback and motors
    # STT/TTS are still needed for the pipeline, but they use remote adapters
    router = Router(bus)
    router.register_intent("unknown", "echo")
    
    stt = STT(bus, adapter=stt_adapter)
    nlu = NLU(bus)
    playback = Playback(bus)  # listens on tts.audio → plays audio
    billy_bass = BillyBass(bus, enabled=Config.BILLY_BASS_ENABLED)  # listens on audio.playback.start/end → controls mouth motor
    tts = TTS(bus, adapter=tts_adapter)
    echo_skill = EchoSkill(bus)

    # Subscribe handlers
    await stt.start()
    await nlu.start()
    await playback.start()
    await billy_bass.start()
    await tts.start()
    await echo_skill.start()


async def start_components(bus: Bus) -> None:
    """Subscribe components to the bus based on deployment mode."""
    mode = Config.DEPLOYMENT_MODE
    
    if mode == "server":
        await start_server_components(bus)
    elif mode == "client":
        await start_client_components(bus)
    else:  # mode == "full"
        await start_full_components(bus)


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
    Config.print_config()
    await start_components(bus)
    print("🐟 Components ready.")
    await repl(bus)
    bus.clear()
    print("🐟 Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
