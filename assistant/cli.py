import typer
import asyncio
from pathlib import Path
from assistant.core.audio.devices import list_input_devices, get_default_input_index
from assistant.core.audio.recorder import record_wav, playback_wav
from assistant.core.stt.whisper_adapter import transcribe_file
from assistant.app import main as app_main

app = typer.Typer(help="Fish Assistant CLI")

@app.command("audio:list")
def audio_list():
    """List input audio devices."""
    for idx, name in list_input_devices():
        typer.echo(f"{idx:>2}  {name}")

@app.command("audio:test")
def audio_test(duration: float = typer.Option(5.0, "--duration", "-d"), device: int | None = None):
    """Record for DURATION seconds and play back."""
    if device is None:
        device = get_default_input_index()
    res = record_wav(duration_s=duration, device_index=device)
    typer.echo(f"[recorded] {res.path} ({res.duration_s:.2f}s)")
    playback_wav(res.path)
    typer.echo("[playback] done")

@app.command("stt:transcribe")
def stt_transcribe(path: Path, model_size: str = "tiny"):
    """Transcribe a WAV/MP3 file and print text."""
    text = transcribe_file(path, model_size=model_size)
    typer.echo(text)

@app.command("demo:record-and-transcribe")
def demo_record_and_transcribe(
    duration: float = typer.Option(5.0, "--duration", "-d"),
    device: int | None = None,
    model_size: str = "tiny",
    playback: bool = True,
):
    """Record, (optionally) play back, then transcribe and print."""
    if device is None:
        device = get_default_input_index()
    res = record_wav(duration_s=duration, device_index=device)
    typer.echo(f"[recorded] {res.path} ({res.duration_s:.2f}s)")
    if playback:
        playback_wav(res.path)
    text = transcribe_file(res.path, model_size=model_size)
    typer.echo(f"[transcript] {text}")

@app.command("test:pipeline")
def test_pipeline(
    duration: float = typer.Option(5.0, "--duration", "-d"),
    device: int | None = None,
    model_size: str = "tiny",
):
    """Test full pipeline: record audio → STT → NLU → Skills → TTS → Playback."""
    async def _test():
        from assistant.core.bus import Bus
        from assistant.core.contracts import AudioRecorded
        from assistant.app import start_components
        
        bus = Bus()
        await start_components(bus)
        
        typer.echo("🎤 Recording audio... (speak now)")
        if device is None:
            device = get_default_input_index()
        res = record_wav(duration_s=duration, device_index=device)
        typer.echo(f"✅ Recorded: {res.path} ({res.duration_s:.2f}s)")
        
        typer.echo("🔄 Processing through pipeline...")
        audio_event = AudioRecorded(wav_path=str(res.path), duration_s=res.duration_s)
        await bus.publish(audio_event.topic, audio_event.dict())
        
        # Wait a bit for processing (transcription can take time)
        await asyncio.sleep(10)
        typer.echo("✅ Pipeline test complete!")
    
    asyncio.run(_test())

@app.command("run")
def run_assistant():
    """Run the Fish Assistant in interactive mode."""
    asyncio.run(app_main())

@app.command("converse")
def converse(
    device: int | None = None,
):
    """Start continuous conversation loop with VAD (hands-free mode)."""
    async def _converse():
        from assistant.core.bus import Bus
        from assistant.core.ux.conversation_loop import ConversationLoop
        from assistant.app import start_components
        
        bus = Bus()
        
        # Start all components (STT, NLU, TTS, Playback, Skills)
        await start_components(bus)
        
        # Start conversation loop
        if device is None:
            device = get_default_input_index()
        
        typer.echo("🐟 Starting conversation loop...")
        typer.echo("📢 Speak naturally - the fish will listen and respond!")
        typer.echo("Press Ctrl+C to stop\n")
        
        loop = ConversationLoop(bus, device_index=device)
        
        try:
            await loop.start()
        except KeyboardInterrupt:
            typer.echo("\n🛑 Stopping conversation loop...")
            await loop.stop()
            typer.echo("✅ Stopped.")
    
    asyncio.run(_converse())


@app.command("server")
def server(
    host: str = typer.Option(None, "--host", "-H", help="Host to bind to"),
    port: int = typer.Option(None, "--port", "-p", help="Port to bind to"),
    device: int | None = typer.Option(None, "--device", "-d", help="Audio input device index"),
    client_url: str = typer.Option(None, "--client-url", "-c", help="Client server URL to push audio to"),
):
    """Start Fish Assistant in server mode (microphone + HTTP API)."""
    import uvicorn
    from contextlib import asynccontextmanager
    from assistant.core.config import Config
    from assistant.core.bus import Bus
    from assistant.core.ux.conversation_loop import ConversationLoop
    from assistant.app import start_server_components
    from assistant.server import create_app
    
    # Set deployment mode
    Config.DEPLOYMENT_MODE = "server"
    
    # Override host/port if provided
    if host:
        Config.SERVER_HOST = host
    if port:
        Config.SERVER_PORT = port
    
    # Override client URL if provided
    if client_url:
        Config.CLIENT_SERVER_URL = client_url
    
    # Global bus and loop task for lifespan management
    bus = Bus()
    loop_task = None
    conversation_loop = None
    
    @asynccontextmanager
    async def lifespan(app_instance):
        nonlocal loop_task, conversation_loop
        
        # Startup
        typer.echo(f"🌐 Starting HTTP server on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
        typer.echo("📡 API endpoints available at:")
        typer.echo(f"   - POST /api/stt/transcribe")
        typer.echo(f"   - POST /api/tts/synthesize")
        typer.echo(f"   - GET  /health")
        if Config.CLIENT_SERVER_URL:
            typer.echo(f"📤 Client audio push enabled: {Config.CLIENT_SERVER_URL}")
        
        # Start server components
        await start_server_components(bus)
        
        # Start conversation loop if device is available
        if device is not None or get_default_input_index() is not None:
            typer.echo("🐟 Starting conversation loop...")
            conversation_loop = ConversationLoop(bus, device_index=device)
            loop_task = asyncio.create_task(conversation_loop.start())
        else:
            typer.echo("⚠️  No audio input device found. Server will run without microphone.")
        
        typer.echo("Press Ctrl+C to stop\n")
        
        yield
        
        # Shutdown
        typer.echo("\n🛑 Stopping server...")
        if loop_task:
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
        if conversation_loop:
            await conversation_loop.stop()
        bus.clear()
        typer.echo("✅ Stopped.")
    
    # Create app with lifespan
    app = create_app(lifespan=lifespan)
    
    # Start uvicorn server (blocking)
    uvicorn.run(
        app,
        host=Config.SERVER_HOST,
        port=Config.SERVER_PORT,
        log_level="info"
    )


@app.command("client")
def client(
    host: str = typer.Option("0.0.0.0", "--host", "-H", help="Host to bind client server to"),
    port: int = typer.Option(8001, "--port", "-p", help="Port to bind client server to"),
):
    """Start Fish Assistant in client mode (playback + motors, remote STT/TTS)."""
    import uvicorn
    from assistant.core.config import Config
    from assistant.core.bus import Bus
    from assistant.app import start_client_components
    from assistant.client_server import create_client_app
    
    # Set deployment mode
    Config.DEPLOYMENT_MODE = "client"
    
    # Validate configuration
    if Config.STT_MODE != "remote" or Config.TTS_MODE != "remote":
        typer.echo("⚠️  Warning: Client mode requires STT_MODE=remote and TTS_MODE=remote")
        typer.echo(f"   Current: STT_MODE={Config.STT_MODE}, TTS_MODE={Config.TTS_MODE}")
        typer.echo(f"   Using server URLs: STT={Config.STT_SERVER_URL}, TTS={Config.TTS_SERVER_URL}")
    
    async def _start_client():
        bus = Bus()
        
        typer.echo("🐟 Starting Fish Assistant in client mode...")
        typer.echo(f"📡 Connecting to server:")
        typer.echo(f"   STT: {Config.STT_SERVER_URL}")
        typer.echo(f"   TTS: {Config.TTS_SERVER_URL}")
        
        # Start client components
        await start_client_components(bus)
        
        typer.echo(f"🌐 Starting client HTTP server on {host}:{port}")
        typer.echo("📡 Client endpoints:")
        typer.echo(f"   - POST /api/audio/play (receive audio files)")
        typer.echo(f"   - GET  /health")
        typer.echo("✅ Client ready. Waiting for audio playback events...")
        typer.echo("Press Ctrl+C to stop\n")
        
        # Create client HTTP app
        client_app = create_client_app(bus)
        
        # Start uvicorn server (blocking)
        uvicorn.run(
            client_app,
            host=host,
            port=port,
            log_level="info"
        )
    
    asyncio.run(_start_client())

if __name__ == "__main__":
    app()