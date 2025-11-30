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

if __name__ == "__main__":
    app()