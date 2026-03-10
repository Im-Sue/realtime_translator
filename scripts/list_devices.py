import sounddevice as sd


def _safe_text(value):
    text = str(value)
    try:
        text.encode("gbk")
        return text
    except UnicodeEncodeError:
        return text.encode("unicode_escape").decode("ascii")


devices = sd.query_devices()
for i, d in enumerate(devices):
    name = _safe_text(d["name"])
    print(f"[{i}] {name}  (in:{d['max_input_channels']}, out:{d['max_output_channels']})")
