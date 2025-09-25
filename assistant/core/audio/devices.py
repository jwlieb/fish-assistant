import sounddevice as sd

def list_input_devices() -> list[tuple[int, str]]:
    infos = sd.query_devices()
    inputs = []
    for idx, d in enumerate(infos):
        if d["max_input_channels"] > 0:
            inputs.append((idx, d["name"]))
    return inputs

def get_default_input_index() -> int:
    default = sd.default.device
    if isinstance(default, (list, tuple)) and len(default) >= 1 and default[0] is not None:
        return int(default[0])
    # fallback to first input device
    for idx, _ in list_input_devices():
        return idx
    raise RuntimeError("No input device found")