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

@app.command("run")
def run_assistant():
    """Run the Fish Assistant in interactive mode."""
    asyncio.run(app_main())

if __name__ == "__main__":
    app()