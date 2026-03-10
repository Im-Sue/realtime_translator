# Real-Time Simultaneous Interpreter

[![Version](https://img.shields.io/badge/version-3.0-blue.svg)](https://github.com/Im-Sue/simultaneous_interpretation)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Custom-orange.svg)](#license)

> [中文](README.md) | English

Real-time bidirectional simultaneous interpretation system based on Volcengine, supporting Chinese-English translation, optimized for online meeting scenarios like Zoom. Supports Windows and macOS.

**If this project helped you in an interview or at work, please leave positive feedback in Issues. Thank you for your support!**

## Core Features

### Bidirectional Translation (Headphone Mode)

- **Dual-Channel Independent Concurrent Execution**
  - **Channel 1**: Microphone(Chinese) → Volcengine(S2S) → VB-CABLE(English) → Zoom → Other party hears English
  - **Channel 2**: Zoom(English) → System Audio → Volcengine(S2T) → Subtitle Window(Chinese) → You see Chinese subtitles

- **Physical Isolation, No Echo**
  - Headphone physical isolation eliminates speaker sound captured by microphone
  - Simplified architecture without complex conflict detection logic

- **Smart Subtitle Window**
  - Semi-transparent floating window with drag and resize support
  - Double-click to toggle font size (14pt ↔ 20pt)
  - ESC key for quick hide/show
  - Intelligent subtitle aggregation and deduplication, English/Chinese displayed on separate lines
  - Chinese text beautification (auto-spacing after punctuation)
  - History playback support (configurable retention count)

- **Flexible Channel Control**
  - Channel 1 can be disabled (subtitle-only mode: view translations without voice output)
  - Set `zh_to_en.enabled: false` in `config.yaml`

- **High-Performance Audio Processing**
  - 16kHz mono audio capture with low-latency transmission
  - Ogg Opus audio decoding (FFmpeg support)
  - Thread-safe audio queue management
  - Automatic audio device detection and fallback mechanism

### Technical Architecture

#### Core Modules

1. **Audio Capture Module** (`core/audio_capture.py`)
   - Microphone audio capture (user voice)
   - Automatic device detection and fallback support
   - Real-time audio stream buffering

2. **Audio Output Module** (`core/audio_output.py`)
   - VB-CABLE virtual audio device output
   - Ogg Opus audio format decoding
   - Dual output monitoring support (optional)
   - Audio playback queue management

3. **Volcengine Client** (`core/volcengine_client.py`)
   - WebSocket persistent connection management
   - S2S (Speech-to-Speech) translation
   - S2T (Speech-to-Text) translation
   - Automatic reconnection and error retry mechanism
   - Protobuf protocol encapsulation

4. **Subtitle Window Module** (`gui/subtitle_window.py`)
   - Tkinter floating window
   - Intelligent text formatting and beautification
   - Configurable style and position
   - Timestamp display (optional)
   - Thread-safe updates

5. **System Audio Capture** (`core/system_audio_capture.py`)
   - Windows Stereo Mix support
   - macOS BlackHole virtual audio support
   - Multi-device fallback strategy

#### Audio Path Flow

```
[Channel 1 - You speak, they hear]
Microphone → AudioCapturer → VolcengineTranslator(s2s) → OggOpusPlayer → VB-CABLE Input → Zoom Microphone

[Channel 2 - They speak, you see]
Zoom Speaker → System Audio/Virtual Audio → SystemAudioCapturer → VolcengineTranslator(s2t) → SubtitleWindow
```

## Supported Platforms

### Operating Systems

- **Windows 10/11** - Fully supported (VB-CABLE + Stereo Mix)
- **macOS** - Fully supported (requires [BlackHole](https://existential.audio/blackhole/))

### Online Meeting Software

Through virtual audio devices, this system supports all meeting software that allows audio input device selection:

- Zoom, Microsoft Teams, Tencent Meeting, Feishu/Lark, DingTalk, Google Meet, Webex, Skype

### Instant Messaging Software

Also supports IM software with voice call features:

- Discord, Telegram (Desktop), WhatsApp (Desktop), WeChat (PC), QQ, Slack

**Configuration**: In each software's audio settings, set the microphone to **CABLE Output (VB-Audio Virtual Cable)**.

## System Requirements

### Software Environment

- **Operating System**: Windows 10/11 or macOS
- **Python**: 3.8+
- **Dependencies**: See `requirements.txt`

### Required Software

#### Windows

- **[VB-CABLE](https://vb-audio.com/Cable/)** - Virtual audio device to pass translated English audio to Zoom
- **FFmpeg** - For Ogg Opus audio decoding

#### macOS

- **[BlackHole](https://existential.audio/blackhole/)** - Virtual audio device (alternative to VB-CABLE)
- `use_ffmpeg` can be set to `false` on macOS

### Volcengine Configuration

- Register Volcengine account: [https://www.volcengine.com/](https://www.volcengine.com/)
- Enable "Simultaneous Interpretation 2.0" service: [https://console.volcengine.com/speech/service/10030](https://console.volcengine.com/speech/service/10030)
- Obtain `app_key` and `access_key`

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Configuration File

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` with your Volcengine credentials and audio device names.

List available audio devices:

```bash
python scripts/list_devices.py
```

### 3. Configure Audio Devices

#### Windows Setup

**Option A: Stereo Mix (Recommended for wired headphones)**

1. **Enable Windows Stereo Mix**
   - Right-click volume icon in taskbar → "Sound"
   - Switch to "Recording" tab
   - Right-click empty area → "Show Disabled Devices"
   - Find "Stereo Mix" → Right-click → "Enable"

2. **Zoom Audio Settings**
   - Microphone: **CABLE Output (VB-Audio Virtual Cable)**
   - Speaker: **Speakers (Realtek HD Audio)** or default speaker

3. Connect wired headphones to Realtek sound card port

**Option B: VB-CABLE B + Monitoring (For Bluetooth speakers)**

1. **Zoom Audio Settings**
   - Microphone: **CABLE Output (VB-Audio Virtual Cable)**
   - Speaker: **CABLE Input (VB-Audio Virtual Cable)**

2. **Modify configuration file** `config.yaml`:
   ```yaml
   audio:
     system_audio:
       device: "CABLE Output"
   ```

3. **Set Windows Audio Monitoring**
   - Right-click "CABLE Output" → Properties → "Listen" tab
   - Check "Listen to this device"
   - "Playback through this device" → Select your Bluetooth speaker

#### macOS Setup

1. Install [BlackHole](https://existential.audio/blackhole/) (16ch version recommended)

2. Update device names in `config.yaml`:
   ```yaml
   audio:
     microphone:
       device: "MacBook Air Microphone"
     system_audio:
       device: "BlackHole 16ch"
       fallback_device: "BlackHole 16ch"
     vbcable_output:
       device: "MacBook Air Speakers"
       use_ffmpeg: false
   ```

3. **Zoom Audio Settings**
   - Microphone: **BlackHole 16ch**
   - Speaker: Default speaker

### 4. Run

```bash
python main.py                    # Use default config.yaml
python main.py my_config.yaml     # Use custom config file
```

## Configuration

All settings are in `config.yaml`. See `config.yaml.example` for detailed comments.

### Audio Configuration

```yaml
audio:
  microphone:
    device: "Microphone"     # Your microphone device name
    sample_rate: 16000
    channels: 1
    chunk_size: 1600         # 100ms @ 16kHz

  system_audio:
    device: "Stereo Mix"     # Windows: Stereo Mix / macOS: BlackHole 16ch
    fallback_device: "Microsoft Sound Mapper - Input"
    sample_rate: 16000
    channels: 1

  vbcable_output:
    device: "CABLE Input"    # Windows: CABLE Input / macOS: Speaker name
    sample_rate: 24000
    use_ffmpeg: true         # Can be set to false on macOS
```

### Translation Channel Configuration

```yaml
channels:
  zh_to_en:
    mode: "s2s"              # speech to speech
    source_language: "zh"
    target_language: "en"
    enabled: true            # Set to false to disable (subtitle-only mode)

  en_to_zh:
    mode: "s2t"              # speech to text
    source_language: "en"
    target_language: "zh"
    enabled: true
```

### Subtitle Window Configuration

```yaml
subtitle_window:
  enabled: true
  width: 600
  height: 800
  font_size: 14              # Double-click window to toggle size
  bg_color: "#000000"
  text_color: "#FFFFFF"
  opacity: 0.85
  position: "top_right"      # Options: top_center, bottom_center, top_left, top_right
  max_history: 1000
  show_timestamp: false
```

## User Guide

### Startup Process

1. **Start program**: `python main.py`
   - macOS convenience scripts: `bash scripts/healthcheck.sh` to check environment, `bash scripts/run.sh` to start
2. **Check devices**: Confirm microphone, speakers, and virtual audio devices are correctly recognized
3. **Wear headphones**: **Important! Must use headphones to avoid echo**
4. **Start Zoom**: Set microphone to "CABLE Output" (Windows) or "BlackHole 16ch" (macOS)
5. **Start translation**:
   - You speak Chinese → They hear English
   - They speak English → You see Chinese subtitles (top right corner)

### Subtitle Window Operations

- **Drag**: Left-click drag to move window
- **Double-click**: Toggle font size (14pt ↔ 20pt)
- **ESC key**: Hide/show window
- **Close program**: Ctrl+C

## Troubleshooting

### 1. Audio Device Not Found

**Problem**: Program shows "Device XXX not found"

**Solution**:
- Run `python scripts/list_devices.py` to view all devices
- Update device name in `config.yaml` to match actual device name

### 2. Stereo Mix Unavailable (Windows)

**Problem**: Cannot enable Stereo Mix, or no sound from Stereo Mix

**Solution**:
- Confirm sound card supports Stereo Mix (Realtek, etc.)
- Switch to "Option B: VB-CABLE Solution"
- Check if sound card driver is up to date

### 3. No Sound from VB-CABLE / BlackHole

**Problem**: No sound after selecting virtual audio device in meeting software

**Solution**:
- Check if virtual audio device is correctly installed
- Restart computer and test again
- Test virtual audio device in system sound settings

### 4. Subtitle Window Not Showing

**Problem**: Program starts but no subtitle window appears

**Solution**:
- Check configuration file `subtitle_window.enabled: true`
- Press ESC key to try showing window
- Check log file for error messages

### 5. High Translation Latency

**Problem**: Translation result has noticeable delay (>3 seconds)

**Solution**:
- Check network connection quality
- Confirm Volcengine service status
- Reduce audio quality or adjust chunk_size
- Check CPU usage

### 6. Volcengine HTTP 401

**Problem**: 401 error when connecting to Volcengine

**Solution**:
- `app_key` and `access_key` must be from the same application
- Confirm "Simultaneous Interpretation 2.0" service is enabled
- Check if keys have expired or been reset

### 7. Program Crashes

**Problem**: Program crashes immediately after startup

**Solution**:
- Check Python version meets requirements (3.8+)
- Confirm all dependencies are installed `pip install -r requirements.txt`
- View log file for error details
- Verify Volcengine keys are correct

## Performance Metrics

| Metric | Value |
|--------|-------|
| End-to-end latency | 1.5-3 seconds (depends on network quality) |
| Audio sample rate | 16kHz (input) / 24kHz (output) |
| Audio format | PCM (input) / Ogg Opus (output) |
| Memory usage | ~200MB |
| CPU usage | 5-15% (depends on translation frequency) |

## Project Structure

```
realtime_translator/
├── main.py                      # Main entry point
├── config.yaml                  # Configuration (copied from example, gitignored)
├── config.yaml.example          # Config template (Windows/macOS device examples)
├── requirements.txt             # Dependencies
├── core/
│   ├── audio_capture.py         # Microphone audio capture
│   ├── audio_output.py          # Audio output (VB-CABLE)
│   ├── system_audio_capture.py  # System audio capture
│   ├── volcengine_client.py     # Volcengine client
│   └── conflict_resolver.py     # Conflict resolver (v1 legacy)
├── gui/
│   └── subtitle_window.py       # Subtitle window module
├── pb2/                         # Protobuf generated files
├── scripts/
│   ├── list_devices.py          # Audio device listing tool
│   ├── vbcable_translator.py    # Single-channel translator (debug)
│   ├── run.sh                   # macOS/Linux startup script
│   └── healthcheck.sh           # Health check script
└── README.md                    # Documentation
```

## Version History

### v3.0 (Current) - Smart Subtitle Enhancement

- Channel 2 intelligent subtitle aggregation and deduplication, English/Chinese on separate lines
- Chinese text beautification (auto-spacing after punctuation, smart line wrapping)
- Channel 1 can be disabled, supporting subtitle-only mode
- Subtitle display format optimization (line spacing, padding adjustments)
- macOS support (BlackHole virtual audio)
- Unified configuration template (Windows/macOS merged into one)

### v2.0 - Bidirectional Translation

- Dual-channel independent concurrent execution
- Headphone physical isolation, no echo
- Simplified architecture, removed conflict detection
- Smart subtitle window (dual-buffer deduplication)
- Thread-safe UI updates
- Comprehensive error handling and retry mechanism
- Support for all mainstream meeting and IM software

### v1.0 - Unidirectional Translation

- Basic microphone to VB-CABLE translation
- Volcengine S2S integration
- Audio conflict detection mechanism

## Roadmap

- **Voice Cloning** - Customize output voice characteristics
- **Noise Reduction** - Background elimination and auto volume equalization
- **Multi-language** - Support for more language pairs
- **Terminology Database** - Industry-specific terminology customization
- **GUI Control Panel** - Graphical configuration and monitoring
- **Multi-participant Support** - Multi-channel audio separation and speaker identification

**Note**: Some features depend on Volcengine API support.

## Author

**Author**: Sue

**Contact**:
- GitHub: [Im-Sue](https://github.com/Im-Sue/)
- X (Twitter): [@ssssy83717](https://x.com/ssssy83717)
- Telegram: [@Sue_muyu](https://t.me/Sue_muyu)

## Contributors

- [XiaoHai67890](https://github.com/XiaoHai67890)

## License

**Copyright © 2024 Sue**

This project uses a custom license:

### Personal Use
- **Allowed** for personal learning, research, and non-commercial use
- **Required** to retain copyright notice and author information

### Commercial Use
- **Prohibited** without authorization
- **Required** to contact author for commercial licensing

For commercial licensing, please contact:
- X: [@ssssy83717](https://x.com/ssssy83717)
- Telegram: [@Sue_muyu](https://t.me/Sue_muyu)

### Disclaimer

This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability.

## Acknowledgments

- [Volcengine](https://www.volcengine.com/) - Simultaneous interpretation API service
- [VB-CABLE](https://vb-audio.com/Cable/) - Windows virtual audio device
- [BlackHole](https://existential.audio/blackhole/) - macOS virtual audio device
- [sounddevice](https://python-sounddevice.readthedocs.io/) - Python audio library

## Feedback & Support

If you encounter issues or have suggestions, please contact:

- **Issues**: [GitHub Issues](https://github.com/Im-Sue/simultaneous_interpretation/issues)
- **X**: [@ssssy83717](https://x.com/ssssy83717)
- **Telegram**: [@Sue_muyu](https://t.me/Sue_muyu)

---

**Quick Start**: `pip install -r requirements.txt && cp config.yaml.example config.yaml && python main.py`

**Important**: Please use headphones to avoid audio echo!
