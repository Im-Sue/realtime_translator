import sounddevice as sd
devices = sd.query_devices()
for i, d in enumerate(devices):
    print(f"[{i}] {d['name']}  (in:{d['max_input_channels']}, out:{d['max_output_channels']})")
