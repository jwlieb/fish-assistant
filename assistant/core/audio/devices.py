from typing import List, Tuple, Optional
import logging

logger = logging.getLogger("devices")

# Lazy import sounddevice to avoid initialization errors on systems without audio devices
try:
    import sounddevice as sd
    SD_AVAILABLE = True
except Exception as e:
    SD_AVAILABLE = False
    sd = None
    logger.warning("sounddevice not available: %s", e)

def list_input_devices() -> List[Tuple[int, str]]:
    """List all available input audio devices."""
    if not SD_AVAILABLE or sd is None:
        logger.warning("sounddevice not available, cannot list input devices")
        return []
    
    try:
        # Query all devices - this may fail on systems with invalid default device (-1)
        infos = sd.query_devices()
        inputs = []
        for idx, d in enumerate(infos):
            try:
                if d["max_input_channels"] > 0:
                    inputs.append((idx, d["name"]))
            except (KeyError, TypeError):
                # Skip devices with invalid info
                continue
        return inputs
    except Exception as e:
        # Handle PortAudioError for device -1 or other audio system issues
        logger.warning("Failed to query audio devices: %s", e)
        return []

def list_output_devices() -> List[Tuple[int, str]]:
    """List all available output audio devices."""
    if not SD_AVAILABLE or sd is None:
        logger.warning("sounddevice not available, cannot list output devices")
        return []
    
    try:
        # Query all devices - this may fail on systems with invalid default device (-1)
        infos = sd.query_devices()
        outputs = []
        for idx, d in enumerate(infos):
            try:
                if d.get("max_output_channels", 0) > 0:
                    outputs.append((idx, d["name"]))
            except (KeyError, TypeError):
                # Skip devices with invalid info
                continue
        return outputs
    except Exception as e:
        # Handle PortAudioError for device -1 or other audio system issues
        logger.warning("Failed to query output audio devices: %s", e)
        return []

def get_default_output_index() -> Optional[int]:
    """Get default output device index, or None if not available."""
    if not SD_AVAILABLE or sd is None:
        logger.warning("sounddevice not available, cannot get default output device")
        return None
    
    try:
        # Try to get default device, but handle -1 or None gracefully
        default = sd.default.device
        if isinstance(default, (list, tuple)) and len(default) >= 2 and default[1] is not None:
            idx = int(default[1])
            if idx >= 0:  # Valid device index (not -1)
                # Verify device exists by querying it
                try:
                    device_info = sd.query_devices(idx)
                    if device_info.get("max_output_channels", 0) > 0:
                        return idx
                except Exception as e:
                    # Device doesn't exist or can't be queried (e.g., device -1)
                    logger.debug("Cannot query output device %d: %s", idx, e)
                    pass
        # fallback to first output device
        devices = list_output_devices()
        if devices:
            return devices[0][0]
        return None
    except Exception as e:
        # If querying devices fails (e.g., PortAudioError for device -1), return None
        logger.warning("Failed to get default output device: %s", e)
        return None

def get_default_input_index() -> Optional[int]:
    """Get default input device index, or None if not available."""
    if not SD_AVAILABLE or sd is None:
        logger.warning("sounddevice not available, cannot get default input device")
        return None
    
    try:
        # Try to get default device, but handle -1 or None gracefully
        default = sd.default.device
        if isinstance(default, (list, tuple)) and len(default) >= 1 and default[0] is not None:
            idx = int(default[0])
            if idx >= 0:  # Valid device index (not -1)
                # Verify device exists by querying it
                try:
                    device_info = sd.query_devices(idx)
                    if device_info.get("max_input_channels", 0) > 0:
                        return idx
                except Exception as e:
                    # Device doesn't exist or can't be queried (e.g., device -1)
                    logger.debug("Cannot query device %d: %s", idx, e)
                    pass
        # fallback to first input device
        devices = list_input_devices()
        if devices:
            return devices[0][0]
        return None
    except Exception as e:
        # If querying devices fails (e.g., PortAudioError for device -1), return None
        logger.warning("Failed to get default input device: %s", e)
        return None