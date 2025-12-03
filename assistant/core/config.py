"""
Configuration management for Fish Assistant.

Supports environment variables and .env files for configuring
local vs remote adapters and server URLs.
"""

import os
import logging
from typing import Literal, Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

logger = logging.getLogger("config")

# Load .env file if available
if DOTENV_AVAILABLE:
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.debug("Loaded .env file from %s", env_path)
    else:
        # Also try loading from current directory
        load_dotenv()


class Config:
    """
    Centralized configuration for Fish Assistant.
    
    Reads from environment variables with sensible defaults.
    """
    
    # STT Configuration
    STT_MODE: Literal["local", "remote"] = os.getenv("STT_MODE", "local")
    STT_SERVER_URL: str = os.getenv("STT_SERVER_URL", "http://localhost:8000")
    STT_MODEL_SIZE: Literal["tiny", "base", "small", "medium"] = os.getenv("STT_MODEL_SIZE", "tiny")
    STT_TIMEOUT: float = float(os.getenv("STT_TIMEOUT", "30.0"))
    
    # TTS Configuration
    TTS_MODE: Literal["local", "remote"] = os.getenv("TTS_MODE", "local")
    TTS_SERVER_URL: str = os.getenv("TTS_SERVER_URL", "http://localhost:8000")
    TTS_VOICE: Optional[str] = os.getenv("TTS_VOICE", None)
    TTS_TIMEOUT: float = float(os.getenv("TTS_TIMEOUT", "30.0"))
    
    # Billy Bass Configuration
    BILLY_BASS_ENABLED: bool = os.getenv("BILLY_BASS_ENABLED", "true").lower() in ("true", "1", "yes")
    
    # Deployment Mode Configuration
    DEPLOYMENT_MODE: Literal["full", "server", "client"] = os.getenv("DEPLOYMENT_MODE", "full")
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    
    # Client Configuration (for server mode to push audio to client)
    CLIENT_SERVER_URL: Optional[str] = os.getenv("CLIENT_SERVER_URL", None)
    
    @classmethod
    def get_stt_adapter(cls):
        """
        Get the appropriate STT adapter based on configuration.
        
        Returns:
            STT adapter instance (WhisperAdapter or RemoteSTTAdapter)
        """
        if cls.STT_MODE == "remote":
            from assistant.core.stt.remote_stt_adapter import RemoteSTTAdapter
            logger.info(
                "Using remote STT adapter: %s (model: %s, timeout: %.1fs)",
                cls.STT_SERVER_URL, cls.STT_MODEL_SIZE, cls.STT_TIMEOUT
            )
            return RemoteSTTAdapter(
                server_url=cls.STT_SERVER_URL,
                model_size=cls.STT_MODEL_SIZE,
                timeout=cls.STT_TIMEOUT,
            )
        else:
            from assistant.core.stt.whisper_adapter import WhisperAdapter
            logger.info("Using local STT adapter (model: %s)", cls.STT_MODEL_SIZE)
            return WhisperAdapter(model_size=cls.STT_MODEL_SIZE)
    
    @classmethod
    def get_tts_adapter(cls):
        """
        Get the appropriate TTS adapter based on configuration.
        
        Returns:
            TTS adapter instance (Pyttsx3Adapter or RemoteTTSAdapter)
        """
        if cls.TTS_MODE == "remote":
            from assistant.core.tts.remote_tts_adapter import RemoteTTSAdapter
            logger.info(
                "Using remote TTS adapter: %s (voice: %s, timeout: %.1fs)",
                cls.TTS_SERVER_URL, cls.TTS_VOICE or "default", cls.TTS_TIMEOUT
            )
            return RemoteTTSAdapter(
                server_url=cls.TTS_SERVER_URL,
                voice=cls.TTS_VOICE,
                timeout=cls.TTS_TIMEOUT,
            )
        else:
            from assistant.core.tts.pyttsx3_adapter import Pyttsx3Adapter
            logger.info("Using local TTS adapter (voice: %s)", cls.TTS_VOICE or "default")
            return Pyttsx3Adapter(voice=cls.TTS_VOICE)
    
    @classmethod
    def print_config(cls):
        """Print current configuration (useful for debugging)."""
        print("\n🐟 Fish Assistant Configuration:")
        print(f"  STT Mode: {cls.STT_MODE}")
        if cls.STT_MODE == "remote":
            print(f"    Server: {cls.STT_SERVER_URL}")
            print(f"    Model: {cls.STT_MODEL_SIZE}")
            print(f"    Timeout: {cls.STT_TIMEOUT}s")
        else:
            print(f"    Model: {cls.STT_MODEL_SIZE}")
        
        print(f"  TTS Mode: {cls.TTS_MODE}")
        if cls.TTS_MODE == "remote":
            print(f"    Server: {cls.TTS_SERVER_URL}")
            print(f"    Voice: {cls.TTS_VOICE or 'default'}")
            print(f"    Timeout: {cls.TTS_TIMEOUT}s")
        else:
            print(f"    Voice: {cls.TTS_VOICE or 'default'}")
        
        print(f"  Billy Bass: {'enabled' if cls.BILLY_BASS_ENABLED else 'disabled'}")
        print(f"  Deployment Mode: {cls.DEPLOYMENT_MODE}")
        if cls.DEPLOYMENT_MODE == "server":
            print(f"    Server: {cls.SERVER_HOST}:{cls.SERVER_PORT}")
            if cls.CLIENT_SERVER_URL:
                print(f"    Client: {cls.CLIENT_SERVER_URL}")
        print()

