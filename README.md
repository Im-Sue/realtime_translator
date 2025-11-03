# 实时同声传译器 (Real-Time Simultaneous Interpreter)

[![Version](https://img.shields.io/badge/version-2.0-blue.svg)](https://github.com/yourusername/simultaneous_interpretation)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Custom-orange.svg)](#license)

> 中文 | [English](README_EN.md)

🎙️ 基于火山引擎的实时双向同声传译系统，支持中英文互译，专为Zoom等在线会议场景优化。

## ✨ 核心特性

### 🚀 v2.0 双向翻译（耳机模式）

- **双通道独立并发执行**
  - **Channel 1**: 麦克风(中文) → 火山引擎(S2S) → VB-CABLE(英文) → Zoom → 对方听到英文
  - **Channel 2**: Zoom(英文) → 系统音频 → 火山引擎(S2T) → 字幕窗口(中文) → 你看到中文字幕

- **物理隔离，无回声**
  - 耳机物理隔离，杜绝扬声器声音被麦克风捕获
  - 简化架构，无需复杂冲突检测逻辑

- **智能字幕窗口**
  - 半透明悬浮窗口，支持拖动和缩放
  - 双击切换字体大小（14pt ↔ 20pt）
  - ESC键快速隐藏/显示
  - 双缓冲区智能去重，避免重复字幕
  - 支持历史记录回溯（可配置保留条数）

- **高性能音频处理**
  - 16kHz单声道音频捕获，低延迟传输
  - Ogg Opus音频解码（FFmpeg支持）
  - 线程安全的音频队列管理
  - 自动音频设备检测和回退机制

### 🔧 技术架构

#### 核心模块

1. **音频捕获模块** (`core/audio_capture.py`)
   - 麦克风音频捕获（用户语音）
   - 系统音频捕获（对方语音）
   - 支持设备自动检测和回退
   - 实时音频流缓冲

2. **音频输出模块** (`core/audio_output.py`)
   - VB-CABLE虚拟音频设备输出
   - Ogg Opus音频格式解码
   - 双输出监听支持（可选）
   - 音频播放队列管理

3. **火山引擎客户端** (`core/volcengine_client.py`)
   - WebSocket长连接管理
   - S2S（语音到语音）翻译
   - S2T（语音到文本）翻译
   - 自动重连和错误重试机制
   - Protobuf协议封装

4. **字幕窗口模块** (`gui/subtitle_window.py`)
   - Tkinter悬浮窗口
   - 双缓冲区智能去重
   - 可配置样式和位置
   - 时间戳显示（可选）
   - 线程安全更新

5. **系统音频捕获** (`core/system_audio_capture.py`)
   - Windows立体声混音支持
   - VB-CABLE虚拟音频设备支持
   - 多设备回退策略

#### 音频路径流程

```
【Channel 1 - 你说对方听】
麦克风 → AudioCapturer → VolcengineTranslator(s2s) → OggOpusPlayer → VB-CABLE Input → Zoom麦克风

【Channel 2 - 对方说你看】
Zoom扬声器 → 系统音频/VB-CABLE → SystemAudioCapturer → VolcengineTranslator(s2t) → SubtitleWindow
```

## 🎯 支持的平台

### 在线会议软件

通过VB-CABLE虚拟音频设备，本系统支持所有能选择音频输入设备的会议软件：

- ✅ **Zoom** - 完全支持，推荐使用
- ✅ **Microsoft Teams** - 完全支持
- ✅ **腾讯会议** - 完全支持
- ✅ **飞书会议** - 完全支持
- ✅ **钉钉会议** - 完全支持
- ✅ **Google Meet** - 完全支持
- ✅ **Webex** - 完全支持
- ✅ **Skype** - 完全支持

### 即时通讯软件

同样支持语音通话功能的IM软件：

- ✅ **Discord** - 支持语音频道
- ✅ **Telegram (Desktop)** - 支持语音通话
- ✅ **WhatsApp (Desktop)** - 支持语音通话
- ✅ **微信 (PC版)** - 支持语音/视频通话
- ✅ **QQ** - 支持语音/视频通话
- ✅ **Slack** - 支持语音通话

**配置方法**: 在各软件的音频设置中，将麦克风设置为 **CABLE Output (VB-Audio Virtual Cable)** 即可。

## 📋 系统要求

### 软件环境

- **操作系统**: Windows 10/11
- **Python**: 3.8+
- **依赖库**:
  ```
  asyncio
  websockets
  sounddevice
  numpy
  pyyaml
  protobuf
  tkinter (通常Python自带)
  ```

### 必需软件

- **VB-CABLE虚拟音频设备**
  - 下载地址: [https://vb-audio.com/Cable/](https://vb-audio.com/Cable/)
  - 用途: 将翻译后的英文音频传递给Zoom

- **FFmpeg** (可选，推荐)
  - 用于Ogg Opus音频解码
  - 提升音质和解码性能

### 火山引擎配置

- 注册火山引擎账号: [https://www.volcengine.com/](https://www.volcengine.com/)
- 开通"同声传译2.0"服务
- 获取`app_key`和`access_key`

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置系统

#### 方案A: 立体声混音方案（推荐，适用于有线耳机）

1. **启用Windows立体声混音**
   - 右键任务栏音量图标 → "声音"
   - 切换到"录制"标签
   - 右键空白处 → "显示已禁用的设备"
   - 找到"立体声混音"或"Stereo Mix"
   - 右键 → "启用"

2. **Zoom音频设置**
   - 麦克风: **CABLE Output (VB-Audio Virtual Cable)**
   - 扬声器: **Speakers (Realtek HD Audio)** 或默认扬声器

3. **连接有线耳机**到Realtek声卡接口

#### 方案B: VB-CABLE B方案（适用于蓝牙音箱）

1. **Zoom音频设置**
   - 麦克风: **CABLE Output (VB-Audio Virtual Cable)**
   - 扬声器: **CABLE Input (VB-Audio Virtual Cable)**

2. **修改配置文件** `config_v2.yaml`:
   ```yaml
   audio:
     system_audio:
       device: "CABLE Output"  # 改为VB-CABLE Output
   ```

3. **设置Windows音频监听**
   - 右键"CABLE Output" → 属性 → "侦听"标签
   - 勾选"侦听此设备"
   - "通过此设备播放" → 选择你的蓝牙音箱

### 3. 配置火山引擎

编辑 `realtime_translator/config_v2.yaml`:

```yaml
volcengine:
  ws_url: "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
  app_key: "你的app_key"
  access_key: "你的access_key"
  resource_id: "volc.service_type.10053"
```

### 4. 运行程序

```bash
cd realtime_translator
python main_v2.py
```

## ⚙️ 配置说明

### 音频配置

```yaml
audio:
  # 麦克风配置
  microphone:
    device: "麦克风"  # 你的麦克风设备名称
    sample_rate: 16000
    channels: 1
    chunk_size: 1600  # 100ms @ 16kHz

  # 系统音频配置
  system_audio:
    device: "立体声混音"  # 方案A: 立体声混音
    # device: "CABLE Output"  # 方案B: VB-CABLE
    fallback_device: "Microsoft 声音映射器 - Input"
    sample_rate: 16000
    channels: 1

  # VB-CABLE输出配置
  vbcable_output:
    device: "CABLE Input"
    sample_rate: 24000
    use_ffmpeg: true
```

### 翻译通道配置

```yaml
channels:
  # Channel 1: 中文 → 英文（语音）
  zh_to_en:
    mode: "s2s"  # speech to speech
    source_language: "zh"
    target_language: "en"
    enabled: true

  # Channel 2: 英文 → 中文（文本）
  en_to_zh:
    mode: "s2t"  # speech to text
    source_language: "en"
    target_language: "zh"
    enabled: true
```

### 字幕窗口配置

```yaml
subtitle_window:
  enabled: true
  width: 600  # 窗口宽度
  height: 800  # 窗口高度（竖向布局）
  font_size: 14  # 字体大小
  bg_color: "#000000"  # 背景色（黑色）
  text_color: "#FFFFFF"  # 文字色（白色）
  opacity: 0.85  # 不透明度（85%）
  position: "top_right"  # 位置（右上角）
  max_history: 1000  # 最大历史记录条数
  show_timestamp: false  # 是否显示时间戳

  # 可选位置: top_center, bottom_center, top_left, top_right
```

## 🎮 使用指南

### 启动流程

1. **启动程序**: `python main_v2.py`
2. **检查设备**: 确认麦克风、扬声器、VB-CABLE设备已正确识别
3. **戴上耳机**: 🎧 **重要！必须使用耳机，避免回声**
4. **启动Zoom**: 配置麦克风为"CABLE Output"
5. **开始翻译**:
   - 你说中文 → 对方听到英文
   - 对方说英文 → 你看到中文字幕（屏幕右上角）

### 字幕窗口操作

- **拖动**: 左键拖动窗口移动位置
- **双击**: 切换字体大小（14pt ↔ 20pt）
- **ESC键**: 隐藏/显示窗口
- **关闭程序**: Ctrl+C

### 日志查看

程序运行日志保存在 `realtime_translator_v2.log`，UTF-8编码。

## 🔧 故障排除

### 1. 音频设备未找到

**问题**: 程序提示"未找到XXX设备"

**解决**:
- 运行 `python -c "import sounddevice; print(sounddevice.query_devices())"` 查看所有设备
- 修改 `config_v2.yaml` 中的设备名称为实际设备名

### 2. 立体声混音无法使用

**问题**: 无法启用立体声混音，或立体声混音无声音

**解决**:
- 确认声卡支持立体声混音（Realtek等）
- 切换到"方案B: VB-CABLE方案"
- 检查声卡驱动是否最新

### 3. VB-CABLE无声音

**问题**: Zoom中选择CABLE Output后无声音

**解决**:
- 检查VB-CABLE是否正确安装
- 重启电脑后重新测试
- 在Windows声音设置中测试CABLE设备

### 4. 字幕窗口不显示

**问题**: 程序启动但没有字幕窗口

**解决**:
- 检查配置文件 `subtitle_window.enabled: true`
- 按ESC键尝试显示窗口
- 检查日志文件是否有错误信息

### 5. 翻译延迟过高

**问题**: 翻译结果延迟明显（>3秒）

**解决**:
- 检查网络连接质量
- 确认火山引擎服务状态
- 降低音频质量或调整chunk_size
- 检查CPU占用率

### 6. 程序闪退

**问题**: 程序启动后立即崩溃

**解决**:
- 检查Python版本是否符合要求（3.8+）
- 确认所有依赖已安装 `pip install -r requirements.txt`
- 查看日志文件获取错误详情
- 检查火山引擎密钥是否正确

## 📊 性能指标

- **端到端延迟**: 1.5-3秒（取决于网络质量）
- **音频采样率**: 16kHz（输入）/ 24kHz（输出）
- **音频格式**: PCM（输入）/ Ogg Opus（输出）
- **内存占用**: ~200MB
- **CPU占用**: 5-15%（取决于翻译频率）

## 🗂️ 项目结构

```
simultaneous_interpretation/
├── realtime_translator/
│   ├── main_v2.py                 # v2.0主程序入口
│   ├── config_v2.yaml             # v2.0配置文件
│   ├── core/
│   │   ├── audio_capture.py       # 音频捕获模块
│   │   ├── audio_output.py        # 音频输出模块
│   │   ├── system_audio_capture.py # 系统音频捕获
│   │   ├── volcengine_client.py   # 火山引擎客户端
│   │   └── conflict_resolver.py   # 冲突解决器（v1遗留）
│   ├── gui/
│   │   └── subtitle_window.py     # 字幕窗口模块
│   └── tests/
│       └── test_improvements.py   # 单元测试
├── ast_python_client/             # 火山引擎SDK
│   └── ast_python/
│       └── python_protogen/       # Protobuf定义
├── README.md                      # 本文件
└── requirements.txt               # 依赖列表
```

## 🔄 版本历史

### v2.0 (当前版本) - 双向翻译

- ✅ 双通道独立并发执行
- ✅ 耳机物理隔离，无回声
- ✅ 简化架构，移除冲突检测
- ✅ 智能字幕窗口（双缓冲区去重）
- ✅ 线程安全的UI更新
- ✅ 完善的错误处理和重试机制
- ✅ 支持所有主流会议和IM软件（Zoom、Teams、腾讯会议、飞书、Discord、Telegram等）

### v1.0 - 单向翻译

- ✅ 基础麦克风到VB-CABLE翻译
- ✅ 火山引擎S2S集成
- ✅ 音频冲突检测机制

## 🚧 计划中功能 (Roadmap)

### v3.0 - 智能语音增强

- ⏳ **音色模拟** - 自定义输出语音的音色特征
  - 支持多种预设音色（男声/女声/不同年龄段）
  - 音色参数可调（音调、语速、情感色彩）
  - 个性化音色克隆（需额外训练）
  - 实时音色切换

- ⏳ **语音优化**
  - 智能降噪和背景音消除
  - 自动音量均衡
  - 语速自适应调节
  - 回声消除增强

- ⏳ **高级翻译特性**
  - 多语言支持扩展（支持更多语言对）
  - 专业术语库定制
  - 上下文记忆增强
  - 语义理解优化

### v4.0 - 企业级功能

- ⏳ **会议管理**
  - GUI控制面板
  - 翻译历史记录和导出
  - 实时质量监控
  - 统计报表生成

- ⏳ **多人会议支持**
  - 多路音频分离
  - 说话人识别
  - 个性化翻译设置
  - 会议录制和回放

- ⏳ **高级配置**
  - 翻译质量优化选项
  - 网络优化和缓存
  - 多设备同步
  - 云端配置管理

**注**: 音色模拟功能取决于火山引擎API的支持情况，部分功能可能需要API升级或额外付费。我们将持续跟进火山引擎API更新，优先实现用户最需要的功能。

## 🤝 作者信息

**作者**: Sue

**联系方式**:
- X (Twitter): [@ssssy83717](https://x.com/ssssy83717)
- Telegram: [@Sue_muyu](https://t.me/Sue_muyu)

## 📄 License

**版权所有 © 2024 Sue**

本项目采用自定义许可协议：

### 个人使用
✅ **允许** 个人学习、研究、非商业使用
⚠️ **要求** 保留版权声明和作者信息

### 商业使用
❌ **禁止** 未经授权的商业使用
✅ **需要** 联系作者获取商业授权许可

如需商业授权，请通过以下方式联系：
- X: [@ssssy83717](https://x.com/ssssy83717)
- Telegram: [@Sue_muyu](https://t.me/Sue_muyu)

### 免责声明

本软件按"原样"提供，不提供任何明示或暗示的保证，包括但不限于适销性、特定用途适用性和非侵权性的保证。在任何情况下，作者或版权持有人均不对任何索赔、损害或其他责任负责。

## 🙏 致谢

- [火山引擎](https://www.volcengine.com/) - 提供同声传译API服务
- [VB-CABLE](https://vb-audio.com/Cable/) - 虚拟音频设备
- [sounddevice](https://python-sounddevice.readthedocs.io/) - Python音频库

## 📮 反馈与支持

如遇到问题或有改进建议，欢迎通过以下方式联系：

- **Issues**: 提交GitHub Issue（如有开源仓库）
- **X**: [@ssssy83717](https://x.com/ssssy83717)
- **Telegram**: [@Sue_muyu](https://t.me/Sue_muyu)

---

**⚡ 快速开始**: `pip install -r requirements.txt && python realtime_translator/main_v2.py`

**🎧 重要提示**: 请务必使用耳机，避免音频回声！
