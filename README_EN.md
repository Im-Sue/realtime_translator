# Real-Time Simultaneous Interpreter

[![Version](https://img.shields.io/badge/version-2.0-blue.svg)](https://github.com/yourusername/simultaneous_interpretation)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Custom-orange.svg)](#license)

🎙️ Real-time bidirectional simultaneous interpretation system based on Volcengine, supporting Chinese-English translation, optimized for online meeting scenarios like Zoom.

> [中文文档](README.md) | English

## ✨ Core Features

### 🚀 v2.0 Bidirectional Translation (Headphone Mode)

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
  - Dual-buffer intelligent deduplication to avoid duplicate subtitles
  - History playback support (configurable retention count)

- **High-Performance Audio Processing**
  - 16kHz mono audio capture with low-latency transmission
  - Ogg Opus audio decoding (FFmpeg support)
  - Thread-safe audio queue management
  - Automatic audio device detection and fallback mechanism

### 🔧 Technical Architecture

#### Core Modules

1. **Audio Capture Module** (`core/audio_capture.py`)
   - Microphone audio capture (user voice)
   - System audio capture (other party's voice)
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
   - Dual-buffer intelligent deduplication
   - Configurable style and position
   - Timestamp display (optional)
   - Thread-safe updates

5. **System Audio Capture** (`core/system_audio_capture.py`)
   - Windows Stereo Mix support
   - VB-CABLE virtual audio device support
   - Multi-device fallback strategy

#### Audio Path Flow

```
【Channel 1 - You speak, they hear】
Microphone → AudioCapturer → VolcengineTranslator(s2s) → OggOpusPlayer → VB-CABLE Input → Zoom Microphone

【Channel 2 - They speak, you see】
Zoom Speaker → System Audio/VB-CABLE → SystemAudioCapturer → VolcengineTranslator(s2t) → SubtitleWindow
```

## 🎯 Supported Platforms

### Online Meeting Software

Through VB-CABLE virtual audio device, this system supports all meeting software that allows audio input device selection:

- ✅ **Zoom** - Fully supported, recommended
- ✅ **Microsoft Teams** - Fully supported
- ✅ **Tencent Meeting (腾讯会议)** - Fully supported
- ✅ **Feishu/Lark (飞书)** - Fully supported
- ✅ **DingTalk (钉钉)** - Fully supported
- ✅ **Google Meet** - Fully supported
- ✅ **Webex** - Fully supported
- ✅ **Skype** - Fully supported

### Instant Messaging Software

Also supports IM software with voice call features:

- ✅ **Discord** - Voice channel support
- ✅ **Telegram (Desktop)** - Voice call support
- ✅ **WhatsApp (Desktop)** - Voice call support
- ✅ **WeChat (PC)** - Voice/video call support
- ✅ **QQ** - Voice/video call support
- ✅ **Slack** - Voice call support

**Configuration Method**: In each software's audio settings, set the microphone to **CABLE Output (VB-Audio Virtual Cable)**.

## 📋 System Requirements

### Software Environment

- **Operating System**: Windows 10/11
- **Python**: 3.8+
- **Dependencies**:
  ```
  asyncio
  websockets
  sounddevice
  numpy
  pyyaml
  protobuf
  tkinter (usually comes with Python)
  ```

### Required Software

- **VB-CABLE Virtual Audio Device**
  - Download: [https://vb-audio.com/Cable/](https://vb-audio.com/Cable/)
  - Purpose: Pass translated English audio to Zoom

- **FFmpeg** (Optional, Recommended)
  - For Ogg Opus audio decoding
  - Improves audio quality and decoding performance

### Volcengine Configuration

- Register Volcengine account: [https://www.volcengine.com/](https://www.volcengine.com/)
- Enable "Simultaneous Interpretation 2.0" service
- Obtain `app_key` and `access_key`

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure System

#### Option A: Stereo Mix Solution (Recommended for Wired Headphones)

1. **Enable Windows Stereo Mix**
   - Right-click volume icon in taskbar → "Sound"
   - Switch to "Recording" tab
   - Right-click empty area → "Show Disabled Devices"
   - Find "Stereo Mix"
   - Right-click → "Enable"

2. **Zoom Audio Settings**
   - Microphone: **CABLE Output (VB-Audio Virtual Cable)**
   - Speaker: **Speakers (Realtek HD Audio)** or default speaker

3. **Connect wired headphones** to Realtek sound card port

#### Option B: VB-CABLE B Solution (For Bluetooth Speakers)

1. **Zoom Audio Settings**
   - Microphone: **CABLE Output (VB-Audio Virtual Cable)**
   - Speaker: **CABLE Input (VB-Audio Virtual Cable)**

2. **Modify configuration file** `config_v2.yaml`:
   ```yaml
   audio:
     system_audio:
       device: "CABLE Output"  # Change to VB-CABLE Output
   ```

3. **Set Windows Audio Monitoring**
   - Right-click "CABLE Output" → Properties → "Listen" tab
   - Check "Listen to this device"
   - "Playback through this device" → Select your Bluetooth speaker

### 3. Configure Volcengine

Edit `realtime_translator/config_v2.yaml`:

```yaml
volcengine:
  ws_url: "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
  app_key: "your_app_key"
  access_key: "your_access_key"
  resource_id: "volc.service_type.10053"
```

### 4. Run Program

```bash
cd realtime_translator
python main_v2.py
```

## ⚙️ Configuration Guide

### Audio Configuration

```yaml
audio:
  # Microphone configuration
  microphone:
    device: "Microphone"  # Your microphone device name
    sample_rate: 16000
    channels: 1
    chunk_size: 1600  # 100ms @ 16kHz

  # System audio configuration
  system_audio:
    device: "Stereo Mix"  # Option A: Stereo Mix
    # device: "CABLE Output"  # Option B: VB-CABLE
    fallback_device: "Microsoft Sound Mapper - Input"
    sample_rate: 16000
    channels: 1

  # VB-CABLE output configuration
  vbcable_output:
    device: "CABLE Input"
    sample_rate: 24000
    use_ffmpeg: true
```

### Translation Channel Configuration

```yaml
channels:
  # Channel 1: Chinese → English (Speech)
  zh_to_en:
    mode: "s2s"  # speech to speech
    source_language: "zh"
    target_language: "en"
    enabled: true

  # Channel 2: English → Chinese (Text)
  en_to_zh:
    mode: "s2t"  # speech to text
    source_language: "en"
    target_language: "zh"
    enabled: true
```

### Subtitle Window Configuration

```yaml
subtitle_window:
  enabled: true
  width: 600  # Window width
  height: 800  # Window height (vertical layout)
  font_size: 14  # Font size
  bg_color: "#000000"  # Background color (black)
  text_color: "#FFFFFF"  # Text color (white)
  opacity: 0.85  # Opacity (85%)
  position: "top_right"  # Position (top right)
  max_history: 1000  # Maximum history count
  show_timestamp: false  # Show timestamp

  # Available positions: top_center, bottom_center, top_left, top_right
```

## 🎮 User Guide

### Startup Process

1. **Start program**: `python main_v2.py`
2. **Check devices**: Confirm microphone, speakers, VB-CABLE devices are correctly recognized
3. **Wear headphones**: 🎧 **Important! Must use headphones to avoid echo**
4. **Start Zoom**: Configure microphone as "CABLE Output"
5. **Start translation**:
   - You speak Chinese → They hear English
   - They speak English → You see Chinese subtitles (top right corner)

### Subtitle Window Operations

- **Drag**: Left-click drag to move window
- **Double-click**: Toggle font size (14pt ↔ 20pt)
- **ESC key**: Hide/show window
- **Close program**: Ctrl+C

### View Logs

Program runtime logs are saved in `realtime_translator_v2.log`, UTF-8 encoding.

## 🔧 Troubleshooting

### 1. Audio Device Not Found

**Problem**: Program shows "Device XXX not found"

**Solution**:
- Run `python -c "import sounddevice; print(sounddevice.query_devices())"` to view all devices
- Modify device name in `config_v2.yaml` to match actual device name

### 2. Stereo Mix Unavailable

**Problem**: Cannot enable Stereo Mix, or no sound from Stereo Mix

**Solution**:
- Confirm sound card supports Stereo Mix (Realtek, etc.)
- Switch to "Option B: VB-CABLE Solution"
- Check if sound card driver is up to date

### 3. No Sound from VB-CABLE

**Problem**: No sound after selecting CABLE Output in Zoom

**Solution**:
- Check if VB-CABLE is correctly installed
- Restart computer and test again
- Test CABLE device in Windows sound settings

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

### 6. Program Crashes

**Problem**: Program crashes immediately after startup

**Solution**:
- Check Python version meets requirements (3.8+)
- Confirm all dependencies are installed `pip install -r requirements.txt`
- View log file for error details
- Verify Volcengine keys are correct

## 📊 Performance Metrics

- **End-to-end latency**: 1.5-3 seconds (depends on network quality)
- **Audio sample rate**: 16kHz (input) / 24kHz (output)
- **Audio format**: PCM (input) / Ogg Opus (output)
- **Memory usage**: ~200MB
- **CPU usage**: 5-15% (depends on translation frequency)

## 🗂️ Project Structure

```
simultaneous_interpretation/
├── realtime_translator/
│   ├── main_v2.py                 # v2.0 main entry point
│   ├── config_v2.yaml             # v2.0 configuration file
│   ├── core/
│   │   ├── audio_capture.py       # Audio capture module
│   │   ├── audio_output.py        # Audio output module
│   │   ├── system_audio_capture.py # System audio capture
│   │   ├── volcengine_client.py   # Volcengine client
│   │   └── conflict_resolver.py   # Conflict resolver (v1 legacy)
│   ├── gui/
│   │   └── subtitle_window.py     # Subtitle window module
│   └── tests/
│       └── test_improvements.py   # Unit tests
├── ast_python_client/             # Volcengine SDK
│   └── ast_python/
│       └── python_protogen/       # Protobuf definitions
├── README.md                      # Chinese documentation
├── README_EN.md                   # This file (English)
└── requirements.txt               # Dependencies list
```

## 🔄 Version History

### v2.0 (Current) - Bidirectional Translation

- ✅ Dual-channel independent concurrent execution
- ✅ Headphone physical isolation, no echo
- ✅ Simplified architecture, removed conflict detection
- ✅ Smart subtitle window (dual-buffer deduplication)
- ✅ Thread-safe UI updates
- ✅ Comprehensive error handling and retry mechanism
- ✅ Support for all mainstream meeting and IM software (Zoom, Teams, Tencent Meeting, Feishu, Discord, Telegram, etc.)

### v1.0 - Unidirectional Translation

- ✅ Basic microphone to VB-CABLE translation
- ✅ Volcengine S2S integration
- ✅ Audio conflict detection mechanism

## 🚧 Roadmap (Planned Features)

### v3.0 - Intelligent Voice Enhancement

- ⏳ **Voice Cloning** - Customize output voice characteristics
  - Support for multiple preset voices (male/female/different ages)
  - Adjustable voice parameters (pitch, speed, emotion)
  - Personalized voice cloning (requires additional training)
  - Real-time voice switching

- ⏳ **Voice Optimization**
  - Intelligent noise reduction and background elimination
  - Automatic volume equalization
  - Adaptive speech rate adjustment
  - Echo cancellation enhancement

- ⏳ **Advanced Translation Features**
  - Multi-language support expansion (more language pairs)
  - Custom terminology database
  - Context memory enhancement
  - Semantic understanding optimization

### v4.0 - Enterprise Features

- ⏳ **Meeting Management**
  - GUI control panel
  - Translation history and export
  - Real-time quality monitoring
  - Statistical report generation

- ⏳ **Multi-participant Meeting Support**
  - Multi-channel audio separation
  - Speaker identification
  - Personalized translation settings
  - Meeting recording and playback

- ⏳ **Advanced Configuration**
  - Translation quality optimization options
  - Network optimization and caching
  - Multi-device synchronization
  - Cloud configuration management

**Note**: Voice cloning functionality depends on Volcengine API support. Some features may require API upgrades or additional fees. We will continue to track Volcengine API updates and prioritize implementing the most user-requested features.

## 🤝 Author

**Author**: Sue

**Contact**:
- X (Twitter): [@ssssy83717](https://x.com/ssssy83717)
- Telegram: [@Sue_muyu](https://t.me/Sue_muyu)

## 📄 License

**Copyright © 2024 Sue**

This project uses a custom license:

### Personal Use
✅ **Allowed** for personal learning, research, and non-commercial use
⚠️ **Required** to retain copyright notice and author information

### Commercial Use
❌ **Prohibited** without authorization
✅ **Required** to contact author for commercial licensing

For commercial licensing, please contact:
- X: [@ssssy83717](https://x.com/ssssy83717)
- Telegram: [@Sue_muyu](https://t.me/Sue_muyu)

### Disclaimer

This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability.

## 🙏 Acknowledgments

- [Volcengine](https://www.volcengine.com/) - Simultaneous interpretation API service
- [VB-CABLE](https://vb-audio.com/Cable/) - Virtual audio device
- [sounddevice](https://python-sounddevice.readthedocs.io/) - Python audio library

## 📮 Feedback & Support

If you encounter issues or have suggestions for improvement, please contact:

- **Issues**: Submit GitHub Issue (if open source repo available)
- **X**: [@ssssy83717](https://x.com/ssssy83717)
- **Telegram**: [@Sue_muyu](https://t.me/Sue_muyu)

---

**⚡ Quick Start**: `pip install -r requirements.txt && python realtime_translator/main_v2.py`

**🎧 Important Note**: Please use headphones to avoid audio echo!
