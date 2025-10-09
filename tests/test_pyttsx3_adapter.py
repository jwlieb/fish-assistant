import os
import pytest
from assistant.core.tts.pyttsx3_adapter import Pyttsx3Adapter

# A safe minimum size check
MIN_AUDIO_BYTES = 4096 # A short WAV header plus minimal audio data will always be larger than this.

@pytest.fixture
def tts_adapter():
    """Provides a fresh Pyttsx3Adapter instance for testing."""
    return Pyttsx3Adapter()

def test_synth_creates_non_zero_duration_wav_file(tts_adapter):
    """
    Tests that synth() generates a file whose duration is greater than 0.0s 
    by checking its size is greater than a minimal byte count.
    """
    text = "Testing to ensure the file is not empty."
    
    # 1. Execute the synthesis
    path = tts_adapter.synth(text)
    
    # 2. ASSERTION: Check that the file was created
    assert os.path.exists(path), f"File was not created at expected path: {path}"
    
    # 3. ASSERTION: Explicitly check file size to confirm duration > 0.0s
    file_size = os.path.getsize(path)
    
    assert file_size > MIN_AUDIO_BYTES, \
        (f"File size is only {file_size} bytes. "
         f"This indicates a 0.0s duration file (empty content).")
    
    # Clean up the temporary file
    os.remove(path)