"""
Critical tests for client mode HTTP endpoint.
"""
import pytest
import tempfile
import os
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from assistant.client_server import create_client_app
from assistant.core.bus import Bus



@pytest.fixture
def bus():
    """Create a test event bus."""
    return Bus()


@pytest.fixture
def client_app(bus):
    """Create a test client app."""
    return create_client_app(bus)


@pytest.fixture
def client(client_app):
    """Create a test client for the client app."""
    return TestClient(client_app)


def test_client_health_endpoint(client):
    """Test client health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mode"] == "client"


def test_client_audio_play_endpoint(client):
    """Test client audio play endpoint accepts WAV files."""
    # Create a minimal test WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    
    try:
        # Create 0.5 seconds of silence at 16kHz
        sample_rate = 16000
        duration = 0.5
        samples = np.zeros(int(sample_rate * duration), dtype=np.float32)
        sf.write(wav_path, samples, sample_rate)
        
        # Upload file
        with open(wav_path, "rb") as audio_file:
            response = client.post(
                "/api/audio/play",
                files={"audio": ("test.wav", audio_file, "audio/wav")}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "duration_s" in data
        assert data["duration_s"] > 0
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


def test_client_audio_play_invalid_file_type(client):
    """Test client endpoint rejects non-WAV files."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"not a wav file")
        txt_path = f.name
    
    try:
        with open(txt_path, "rb") as audio_file:
            response = client.post(
                "/api/audio/play",
                files={"audio": ("test.txt", audio_file, "text/plain")}
            )
        
        assert response.status_code == 400
        assert "WAV" in response.json()["detail"]
    finally:
        if os.path.exists(txt_path):
            os.remove(txt_path)

