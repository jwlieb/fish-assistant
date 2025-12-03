"""
Critical tests for deployment mode configuration.
"""
import pytest
from assistant.core.config import Config


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    """Reset environment variables before each test."""
    # Clear test variables
    for key in ["DEPLOYMENT_MODE", "STT_MODE", "TTS_MODE", "STT_SERVER_URL", 
                "TTS_SERVER_URL", "SERVER_HOST", "SERVER_PORT"]:
        monkeypatch.delenv(key, raising=False)


def test_config_defaults():
    """Test that config has sensible defaults."""
    assert Config.DEPLOYMENT_MODE in ["full", "server", "client"]
    assert Config.STT_MODE in ["local", "remote"]
    assert Config.TTS_MODE in ["local", "remote"]
    assert Config.STT_SERVER_URL.startswith("http")
    assert Config.TTS_SERVER_URL.startswith("http")
    assert isinstance(Config.SERVER_PORT, int)
    assert Config.SERVER_PORT > 0


def test_config_get_stt_adapter_remote():
    """Test that get_stt_adapter returns remote adapter when STT_MODE=remote."""
    Config.STT_MODE = "remote"
    Config.STT_SERVER_URL = "http://localhost:8000"
    adapter = Config.get_stt_adapter()
    
    # Should be RemoteSTTAdapter
    from assistant.core.stt.remote_stt_adapter import RemoteSTTAdapter
    assert isinstance(adapter, RemoteSTTAdapter)
    assert adapter.server_url == "http://localhost:8000"


def test_config_get_tts_adapter_remote():
    """Test that get_tts_adapter returns remote adapter when TTS_MODE=remote."""
    Config.TTS_MODE = "remote"
    Config.TTS_SERVER_URL = "http://localhost:8000"
    adapter = Config.get_tts_adapter()
    
    # Should be RemoteTTSAdapter
    from assistant.core.tts.remote_tts_adapter import RemoteTTSAdapter
    assert isinstance(adapter, RemoteTTSAdapter)
    assert adapter.server_url == "http://localhost:8000"

