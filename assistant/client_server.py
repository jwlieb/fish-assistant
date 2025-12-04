"""
Simple HTTP server for Fish Assistant client mode.

Allows server to push audio files to client for playback.
"""

import logging
import tempfile
import os
import soundfile as sf
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from assistant.core.bus import Bus
from assistant.core.contracts import TTSAudio

logger = logging.getLogger("client_server")


def create_client_app(bus: Bus, lifespan=None) -> FastAPI:
    """
    Create FastAPI app for client mode.
    
    Args:
        bus: Event bus instance to publish audio events to
        lifespan: Optional lifespan context manager
    
    Returns:
        FastAPI app instance
    """
    app_kwargs = {
        "title": "Fish Assistant Client API",
        "description": "Client endpoint for receiving audio files",
        "version": "0.1.0"
    }
    
    if lifespan:
        app_kwargs["lifespan"] = lifespan
    
    app = FastAPI(**app_kwargs)
    
    # Add CORS middleware
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
        return {"status": "ok", "mode": "client"}
    
    @app.post("/api/audio/play")
    async def receive_audio(
        audio: UploadFile = File(..., description="WAV audio file to play")
    ):
        """
        Receive audio file and trigger playback.
        
        Accepts multipart/form-data with:
        - audio: WAV file
        
        Returns success status.
        """
        logger.info("Client: Received audio play request: %s", audio.filename)
        
        # Validate file type
        if not audio.filename.endswith(('.wav', '.WAV')):
            logger.warning("Client: Invalid file type: %s", audio.filename)
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
                "Client: Saved audio file: %s (%d bytes) -> %s",
                audio.filename, len(content), temp_path
            )
            
            # Get duration from audio file
            try:
                info = sf.info(temp_path)
                duration_s = info.frames / float(info.samplerate) if info.samplerate else 0.01
            except Exception as e:
                logger.warning("Could not read audio duration: %s", e)
                duration_s = 0.01  # minimal default to satisfy contract
            
            # Publish TTSAudio event to trigger playback
            logger.info("Client: Publishing tts.audio event to bus (duration=%.2fs)", duration_s)
            audio_event = TTSAudio(wav_path=temp_path, duration_s=duration_s)
            await bus.publish(audio_event.topic, audio_event.dict())
            logger.info("Client: Published tts.audio event successfully")
            
            return {
                "status": "ok",
                "message": "Audio queued for playback",
                "duration_s": duration_s
            }
            
        except Exception as e:
            logger.exception("Error receiving audio: %s", e)
            # Clean up temp file on error
            try:
                os.remove(temp_path)
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to process audio: {str(e)}")
    
    return app

