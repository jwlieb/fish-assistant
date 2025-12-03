"""
Critical tests for component initialization in different deployment modes.
"""
import pytest
import os
from assistant.core.bus import Bus
from assistant.core.config import Config
from assistant.app import (
    start_full_components,
    start_server_components,
    start_client_components,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config to defaults before each test."""
    original_mode = Config.DEPLOYMENT_MODE
    original_stt_mode = Config.STT_MODE
    original_tts_mode = Config.TTS_MODE
    
    yield
    
    # Restore original values
    Config.DEPLOYMENT_MODE = original_mode
    Config.STT_MODE = original_stt_mode
    Config.TTS_MODE = original_tts_mode


async def test_start_full_components():
    """Test that full mode components start correctly."""
    bus = Bus()
    
    # Set to full mode
    Config.DEPLOYMENT_MODE = "full"
    Config.STT_MODE = "local"
    Config.TTS_MODE = "local"
    
    # Should not raise
    await start_full_components(bus)
    
    # Verify components are subscribed
    assert len(bus._subs) > 0


@pytest.mark.skipif(
    not hasattr(Config, 'STT_MODEL_SIZE'),
    reason="Server dependencies not installed"
)
async def test_start_server_components():
    """Test that server mode components start correctly."""
    bus = Bus()
    
    # Set to server mode
    Config.DEPLOYMENT_MODE = "server"
    
    # Should not raise
    await start_server_components(bus)
    
    # Verify components are subscribed
    assert len(bus._subs) > 0


async def test_start_client_components():
    """Test that client mode components start correctly."""
    bus = Bus()
    
    # Set to client mode with remote adapters
    Config.DEPLOYMENT_MODE = "client"
    Config.STT_MODE = "remote"
    Config.TTS_MODE = "remote"
    Config.STT_SERVER_URL = "http://localhost:8000"
    Config.TTS_SERVER_URL = "http://localhost:8000"
    
    # Should not raise (even if server is not available)
    await start_client_components(bus)
    
    # Verify components are subscribed
    assert len(bus._subs) > 0



