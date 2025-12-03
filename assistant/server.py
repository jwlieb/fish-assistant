"""
FastAPI HTTP server for Fish Assistant.

Exposes STT and TTS endpoints for remote clients.
Can run standalone or alongside the full assistant pipeline.
"""

import logging
import tempfile
import os
import asyncio
from typing import Optional, Callable, AsyncContextManager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from assistant.core.config import Config

# Optional imports for server dependencies
try:
    from assistant.core.stt.whisper_adapter import WhisperAdapter
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    WhisperAdapter = None

try:
    from assistant.core.tts.pyttsx3_adapter import Pyttsx3Adapter
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    Pyttsx3Adapter = None

logger = logging.getLogger("server")


# Initialize adapters (lazy-loaded on first request)
_stt_adapter = None
_tts_adapter = None


def get_stt_adapter():
    """Get or create STT adapter instance."""
    if not WHISPER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="STT service unavailable: faster-whisper not installed"
        )
    global _stt_adapter
    if _stt_adapter is None:
        _stt_adapter = WhisperAdapter(model_size=Config.STT_MODEL_SIZE)
    return _stt_adapter


def get_tts_adapter():
    """Get or create TTS adapter instance."""
    if not PYTTSX3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="TTS service unavailable: pyttsx3 not installed"
        )
    global _tts_adapter
    if _tts_adapter is None:
        _tts_adapter = Pyttsx3Adapter(voice=Config.TTS_VOICE)
    return _tts_adapter


def create_app(lifespan: Optional[Callable[[FastAPI], AsyncContextManager]] = None) -> FastAPI:
    """
    Create FastAPI app with optional lifespan.
    
    Args:
        lifespan: Optional lifespan context manager for startup/shutdown
    
    Returns:
        FastAPI app instance
    """
    app_kwargs = {
        "title": "Fish Assistant API",
        "description": "STT and TTS endpoints for Fish Assistant",
        "version": "0.1.0"
    }
    
    if lifespan:
        app_kwargs["lifespan"] = lifespan
    
    app = FastAPI(**app_kwargs)
    
    # Add CORS middleware to allow cross-origin requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict this
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "service": "fish-assistant"}
    
    @app.post("/api/stt/transcribe")
    async def transcribe_audio(
        audio: UploadFile = File(..., description="WAV audio file"),
        model_size: str = Form(default="tiny", description="Model size hint")
    ):
        """
        Transcribe audio file to text.
        
        Accepts multipart/form-data with:
        - audio: WAV file
        - model_size: Optional model size hint (tiny, base, small, medium)
        
        Returns JSON with transcribed text.
        """
        # Validate file type
        if not audio.filename.endswith(('.wav', '.WAV')):
            raise HTTPException(
                status_code=400,
                detail="Only WAV files are supported"
            )
        
        # Save uploaded file to temporary location
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        try:
            # Write uploaded content to temp file
            with open(temp_path, "wb") as f:
                content = await audio.read()
                f.write(content)
            
            logger.info(
                "Transcribing audio: %s (%d bytes, model_size: %s)",
                audio.filename, len(content), model_size
            )
            
            # Transcribe using adapter
            adapter = get_stt_adapter()
            text = adapter.transcribe(temp_path)
            
            logger.info("Transcription complete: %s", text[:50] if text else "(empty)")
            
            return JSONResponse(content={"text": text})
            
        except Exception as e:
            logger.exception("Error transcribing audio: %s", e)
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
        finally:
            # Clean up temp file
            try:
                os.remove(temp_path)
            except Exception:
                pass
    
    @app.post("/api/tts/synthesize")
    async def synthesize_speech(
        request: dict,
        background_tasks: BackgroundTasks
    ):
        """
        Synthesize text to speech.
        
        Accepts JSON with:
        {
            "text": "text to synthesize",
            "voice": "optional voice name"
        }
        
        Returns binary WAV file.
        """
        text = request.get("text", "")
        voice = request.get("voice")
        
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        logger.info("Synthesizing speech: %d chars (voice: %s)", len(text), voice or "default")
        
        try:
            # Get adapter (use provided voice if specified, otherwise use config)
            if not PYTTSX3_AVAILABLE:
                raise HTTPException(
                    status_code=503,
                    detail="TTS service unavailable: pyttsx3 not installed"
                )
            if voice:
                adapter = Pyttsx3Adapter(voice=voice)
            else:
                adapter = get_tts_adapter()
            
            # Synthesize to temp file
            wav_path = adapter.synth(text.strip())
            
            if not os.path.exists(wav_path):
                raise HTTPException(status_code=500, detail="TTS synthesis failed: no output file")
            
            logger.info("Synthesis complete: %s", wav_path)
            
            # Schedule cleanup after response is sent
            def cleanup_file():
                try:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
                except Exception:
                    pass  # Ignore cleanup errors
            
            background_tasks.add_task(cleanup_file)
            
            # Return file response
            return FileResponse(
                wav_path,
                media_type="audio/wav",
                filename="synthesized.wav"
            )
            
        except Exception as e:
            logger.exception("Error synthesizing speech: %s", e)
            raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")
    
    return app


# Create default app instance (for backward compatibility)
app = create_app()

