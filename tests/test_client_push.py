"""
Tests for client audio push service.
"""

import pytest
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from assistant.core.audio.client_push import ClientAudioPush
from assistant.core.bus import Bus
from assistant.core.contracts import TTSAudio
from assistant.core.config import Config


@pytest.fixture
def bus():
    """Create a bus instance for testing."""
    return Bus()


@pytest.fixture
def temp_wav_file():
    """Create a temporary WAV file for testing."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    # Write minimal WAV header (44 bytes)
    with open(path, "wb") as f:
        # WAV header
        f.write(b"RIFF")
        f.write((36).to_bytes(4, "little"))  # File size - 8
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write((16).to_bytes(4, "little"))  # fmt chunk size
        f.write((1).to_bytes(2, "little"))  # Audio format (PCM)
        f.write((1).to_bytes(2, "little"))  # Channels
        f.write((16000).to_bytes(4, "little"))  # Sample rate
        f.write((32000).to_bytes(4, "little"))  # Byte rate
        f.write((2).to_bytes(2, "little"))  # Block align
        f.write((16).to_bytes(2, "little"))  # Bits per sample
        f.write(b"data")
        f.write((0).to_bytes(4, "little"))  # Data size
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_client_push_disabled_when_no_url(bus):
    """Test that client push does nothing when CLIENT_SERVER_URL is not set."""
    # Save original value
    original_url = Config.CLIENT_SERVER_URL
    Config.CLIENT_SERVER_URL = None
    
    try:
        client_push = ClientAudioPush(bus)
        await client_push.start()
        
        # Publish a TTS audio event
        audio_event = TTSAudio(wav_path="/tmp/test.wav", duration_s=1.0)
        await bus.publish(audio_event.topic, audio_event.dict())
        
        # Should not raise any errors (graceful degradation)
    finally:
        Config.CLIENT_SERVER_URL = original_url


@pytest.mark.asyncio
async def test_client_push_success(bus, temp_wav_file):
    """Test successful audio push to client."""
    # Save original value
    original_url = Config.CLIENT_SERVER_URL
    Config.CLIENT_SERVER_URL = "http://localhost:8001"
    
    try:
        client_push = ClientAudioPush(bus)
        await client_push.start()
        
        # Mock httpx client
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "duration_s": 1.0}
        mock_response.raise_for_status = MagicMock()
        
        with patch("assistant.core.audio.client_push.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance
            
            # Publish a TTS audio event
            audio_event = TTSAudio(wav_path=temp_wav_file, duration_s=1.0)
            await bus.publish(audio_event.topic, audio_event.dict())
            
            # Give async operations time to complete
            import asyncio
            await asyncio.sleep(0.1)
            
            # Verify POST was called
            assert mock_client_instance.post.called
            call_args = mock_client_instance.post.call_args
            assert call_args[0][0] == "http://localhost:8001/api/audio/play"
            assert "files" in call_args[1]
    finally:
        Config.CLIENT_SERVER_URL = original_url


@pytest.mark.asyncio
async def test_client_push_handles_missing_file(bus):
    """Test that client push handles missing audio files gracefully."""
    # Save original value
    original_url = Config.CLIENT_SERVER_URL
    Config.CLIENT_SERVER_URL = "http://localhost:8001"
    
    try:
        client_push = ClientAudioPush(bus)
        await client_push.start()
        
        # Publish a TTS audio event with non-existent file
        audio_event = TTSAudio(wav_path="/nonexistent/file.wav", duration_s=1.0)
        await bus.publish(audio_event.topic, audio_event.dict())
        
        # Should not raise any errors (graceful degradation)
        import asyncio
        await asyncio.sleep(0.1)
    finally:
        Config.CLIENT_SERVER_URL = original_url


@pytest.mark.asyncio
async def test_client_push_handles_network_error(bus, temp_wav_file):
    """Test that client push handles network errors gracefully."""
    # Save original value
    original_url = Config.CLIENT_SERVER_URL
    Config.CLIENT_SERVER_URL = "http://localhost:8001"
    
    try:
        client_push = ClientAudioPush(bus)
        await client_push.start()
        
        # Mock httpx client to raise an error
        import httpx
        with patch("assistant.core.audio.client_push.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_instance.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.return_value = mock_client_instance
            
            # Publish a TTS audio event
            audio_event = TTSAudio(wav_path=temp_wav_file, duration_s=1.0)
            await bus.publish(audio_event.topic, audio_event.dict())
            
            # Should not crash the pipeline (error is logged but not raised)
            import asyncio
            await asyncio.sleep(0.1)
    finally:
        Config.CLIENT_SERVER_URL = original_url

