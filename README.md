# 实时同声传译器 (Real-Time Simultaneous Interpreter)

[![Version](https://img.shields.io/badge/version-3.0-blue.svg)](https://github.com/Im-Sue/simultaneous_interpretation)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Custom-orange.svg)](#license)

> 中文 | [English](README_EN.md)

基于火山引擎的实时双向同声传译系统，支持中英文互译，专为 Zoom 等在线会议场景优化。支持 Windows 和 macOS。

**如果你基于这个项目面试或者工作使用顺利，请在 Issues 里给予我一个正向反馈，感谢你的支持！！！**

## 核心特性

### 双向翻译（耳机模式）

- **双通道独立并发执行**
  - **Channel 1**: 麦克风(中文) → 火山引擎(S2S) → VB-CABLE(英文) → Zoom → 对方听到英文
  - **Channel 2**: Zoom(英文) → 系统音频 → 火山引擎(S2T) → 字幕窗口(中文) → 你看到中文字幕

- **物理隔离，无回声**
  - 耳机物理隔离，杜绝扬声器声音被麦克风捕获
  - 简化架构，无需复杂冲突检测逻辑

- **智能字幕窗口**
  - 半透明悬浮窗口，支持拖动和缩放
  - 双击切换字体大小（14pt ↔ 20pt）
  - ESC 键快速隐藏/显示
  - 智能字幕聚合与去重，英文/中文分行显示
  - 中文文本美化处理（标点后自动空格）
  - 支持历史记录回溯（可配置保留条数）

- **灵活的通道控制**
  - Channel 1 可选关闭（纯字幕模式：只看翻译不输出语音）
  - 在 `config.yaml` 中设置 `zh_to_en.enabled: false` 即可

- **高性能音频处理**
  - 16kHz 单声道音频捕获，低延迟传输
  - Ogg Opus 音频解码（FFmpeg 支持）
  - 线程安全的音频队列管理
  - 自动音频设备检测和回退机制

### 技术架构

#### 核心模块

1. **音频捕获模块** (`core/audio_capture.py`)
   - 麦克风音频捕获（用户语音）
   - 支持设备自动检测和回退
   - 实时音频流缓冲

2. **音频输出模块** (`core/audio_output.py`)
   - VB-CABLE 虚拟音频设备输出
   - Ogg Opus 音频格式解码
   - 双输出监听支持（可选）
   - 音频播放队列管理

3. **火山引擎客户端** (`core/volcengine_client.py`)
   - WebSocket 长连接管理
   - S2S（语音到语音）翻译
   - S2T（语音到文本）翻译
   - 自动重连和错误重试机制
   - Protobuf 协议封装

4. **字幕窗口模块** (`gui/subtitle_window.py`)
   - Tkinter 悬浮窗口
   - 智能文本格式化与美化
   - 可配置样式和位置
   - 时间戳显示（可选）
   - 线程安全更新

5. **系统音频捕获** (`core/system_audio_capture.py`)
   - Windows 立体声混音支持
   - macOS BlackHole 虚拟音频支持
   - 多设备回退策略

#### 音频路径流程

```
【Channel 1 - 你说对方听】
麦克风 → AudioCapturer → VolcengineTranslator(s2s) → OggOpusPlayer → VB-CABLE Input → Zoom麦克风

【Channel 2 - 对方说你看】
Zoom扬声器 → 系统音频/虚拟音频 → SystemAudioCapturer → VolcengineTranslator(s2t) → SubtitleWindow
```

## 支持的平台

### 操作系统

- **Windows 10/11** - 完全支持（VB-CABLE + 立体声混音）
- **macOS** - 完全支持（需安装 [BlackHole](https://existential.audio/blackhole/)）

### 在线会议软件

通过虚拟音频设备，本系统支持所有能选择音频输入设备的会议软件：

- Zoom、Microsoft Teams、腾讯会议、飞书会议、钉钉会议、Google Meet、Webex、Skype

### 即时通讯软件

同样支持语音通话功能的 IM 软件：

- Discord、Telegram (Desktop)、WhatsApp (Desktop)、微信 (PC版)、QQ、Slack

**配置方法**: 在各软件的音频设置中，将麦克风设置为 **CABLE Output (VB-Audio Virtual Cable)** 即可。

## 系统要求

### 软件环境

- **操作系统**: Windows 10/11 或 macOS
- **Python**: 3.8+
- **依赖库**: 见 `requirements.txt`

### 必需软件

#### Windows

- **[VB-CABLE](https://vb-audio.com/Cable/)** - 虚拟音频设备，将翻译后的英文音频传递给 Zoom
- **FFmpeg** - 用于 Ogg Opus 音频解码

#### macOS

- **[BlackHole](https://existential.audio/blackhole/)** - 虚拟音频设备（替代 VB-CABLE）
- macOS 下 `use_ffmpeg` 可设为 `false`

### 火山引擎配置

- 注册火山引擎账号: [https://www.volcengine.com/](https://www.volcengine.com/)
- 开通"同声传译2.0"服务: [https://console.volcengine.com/speech/service/10030](https://console.volcengine.com/speech/service/10030)
- 获取 `app_key` 和 `access_key`

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 创建配置文件

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml`，填入火山引擎凭据和音频设备名称。

查看可用音频设备：

```bash
python scripts/list_devices.py
```

### 3. 配置音频设备

#### Windows 配置

**方案A: 立体声混音（推荐，适用于有线耳机）**

1. **启用 Windows 立体声混音**
   - 右键任务栏音量图标 → "声音"
   - 切换到"录制"标签
   - 右键空白处 → "显示已禁用的设备"
   - 找到"立体声混音"或"Stereo Mix" → 右键 → "启用"

2. **Zoom 音频设置**
   - 麦克风: **CABLE Output (VB-Audio Virtual Cable)**
   - 扬声器: **Speakers (Realtek HD Audio)** 或默认扬声器

3. 连接有线耳机到 Realtek 声卡接口

**方案B: VB-CABLE B + 监听（适用于蓝牙音箱）**

1. **Zoom 音频设置**
   - 麦克风: **CABLE Output (VB-Audio Virtual Cable)**
   - 扬声器: **CABLE Input (VB-Audio Virtual Cable)**

2. **修改配置文件** `config.yaml`:
   ```yaml
   audio:
     system_audio:
       device: "CABLE Output"
   ```

3. **设置 Windows 音频监听**
   - 右键"CABLE Output" → 属性 → "侦听"标签
   - 勾选"侦听此设备"
   - "通过此设备播放" → 选择你的蓝牙音箱

#### macOS 配置

1. 安装 [BlackHole](https://existential.audio/blackhole/)（推荐 16ch 版本）

2. 修改 `config.yaml` 中的设备名称：
   ```yaml
   audio:
     microphone:
       device: "MacBook Air麦克风"
     system_audio:
       device: "BlackHole 16ch"
       fallback_device: "BlackHole 16ch"
     vbcable_output:
       device: "MacBook Air扬声器"
       use_ffmpeg: false
   ```

3. **Zoom 音频设置**
   - 麦克风: **BlackHole 16ch**
   - 扬声器: 默认扬声器

### 4. 运行程序

```bash
python main.py                    # 使用默认 config.yaml
python main.py my_config.yaml     # 使用指定配置文件
```

## 配置说明

所有配置项均在 `config.yaml` 中，详见 `config.yaml.example` 中的注释说明。

### 音频配置

```yaml
audio:
  microphone:
    device: "麦克风"        # 你的麦克风设备名称
    sample_rate: 16000
    channels: 1
    chunk_size: 1600        # 100ms @ 16kHz

  system_audio:
    device: "立体声混音"     # Windows: 立体声混音 / macOS: BlackHole 16ch
    fallback_device: "Microsoft 声音映射器 - Input"
    sample_rate: 16000
    channels: 1

  vbcable_output:
    device: "CABLE Input"   # Windows: CABLE Input / macOS: 扬声器名
    sample_rate: 24000
    use_ffmpeg: true        # macOS 可设为 false
```

### 翻译通道配置

```yaml
channels:
  zh_to_en:
    mode: "s2s"             # speech to speech
    source_language: "zh"
    target_language: "en"
    enabled: true           # 设为 false 可关闭（纯字幕模式）

  en_to_zh:
    mode: "s2t"             # speech to text
    source_language: "en"
    target_language: "zh"
    enabled: true
```

### 字幕窗口配置

```yaml
subtitle_window:
  enabled: true
  width: 600
  height: 800
  font_size: 14             # 双击窗口可切换大小
  bg_color: "#000000"
  text_color: "#FFFFFF"
  opacity: 0.85
  position: "top_right"     # 可选: top_center, bottom_center, top_left, top_right
  max_history: 1000
  show_timestamp: false
```

## 使用指南

### 启动流程

1. **启动程序**: `python main.py`
   - macOS 可使用便捷脚本：`bash scripts/healthcheck.sh` 检查环境，`bash scripts/run.sh` 启动
2. **检查设备**: 确认麦克风、扬声器、虚拟音频设备已正确识别
3. **戴上耳机**: **重要！必须使用耳机，避免回声**
4. **启动 Zoom**: 配置麦克风为 "CABLE Output"（Windows）或 "BlackHole 16ch"（macOS）
5. **开始翻译**:
   - 你说中文 → 对方听到英文
   - 对方说英文 → 你看到中文字幕（屏幕右上角）

### 字幕窗口操作

- **拖动**: 左键拖动窗口移动位置
- **双击**: 切换字体大小（14pt ↔ 20pt）
- **ESC 键**: 隐藏/显示窗口
- **关闭程序**: Ctrl+C

## 故障排除

### 1. 音频设备未找到

**问题**: 程序提示"未找到XXX设备"

**解决**:
- 运行 `python scripts/list_devices.py` 查看所有设备
- 修改 `config.yaml` 中的设备名称为实际设备名

### 2. 立体声混音无法使用（Windows）

**问题**: 无法启用立体声混音，或立体声混音无声音

**解决**:
- 确认声卡支持立体声混音（Realtek等）
- 切换到"方案B: VB-CABLE 方案"
- 检查声卡驱动是否最新

### 3. VB-CABLE / BlackHole 无声音

**问题**: 会议软件中选择虚拟音频设备后无声音

**解决**:
- 检查虚拟音频设备是否正确安装
- 重启电脑后重新测试
- 在系统声音设置中测试虚拟音频设备

### 4. 字幕窗口不显示

**问题**: 程序启动但没有字幕窗口

**解决**:
- 检查配置文件 `subtitle_window.enabled: true`
- 按 ESC 键尝试显示窗口
- 检查日志文件是否有错误信息

### 5. 翻译延迟过高

**问题**: 翻译结果延迟明显（>3秒）

**解决**:
- 检查网络连接质量
- 确认火山引擎服务状态
- 降低音频质量或调整 chunk_size
- 检查 CPU 占用率

### 6. 火山引擎 HTTP 401

**问题**: 连接火山引擎时返回 401 错误

**解决**:
- `app_key` 与 `access_key` 必须来自同一个应用
- 确认已开通"同声传译2.0"服务
- 检查密钥是否失效或被重置

### 7. 程序闪退

**问题**: 程序启动后立即崩溃

**解决**:
- 检查 Python 版本是否符合要求（3.8+）
- 确认所有依赖已安装 `pip install -r requirements.txt`
- 查看日志文件获取错误详情
- 检查火山引擎密钥是否正确

## 性能指标

| 指标 | 数值 |
|------|------|
| 端到端延迟 | 1.5-3 秒（取决于网络质量） |
| 音频采样率 | 16kHz（输入）/ 24kHz（输出） |
| 音频格式 | PCM（输入）/ Ogg Opus（输出） |
| 内存占用 | ~200MB |
| CPU 占用 | 5-15%（取决于翻译频率） |

## 项目结构

```
realtime_translator/
├── main.py                      # 主程序入口
├── config.yaml                  # 配置文件（从 example 复制，已 gitignore）
├── config.yaml.example          # 配置模板（含 Windows/macOS 设备示例）
├── requirements.txt             # 依赖列表
├── core/
│   ├── audio_capture.py         # 麦克风音频捕获
│   ├── audio_output.py          # 音频输出（VB-CABLE）
│   ├── system_audio_capture.py  # 系统音频捕获
│   ├── volcengine_client.py     # 火山引擎客户端
│   └── conflict_resolver.py     # 冲突解决器（v1 遗留）
├── gui/
│   └── subtitle_window.py       # 字幕窗口模块
├── pb2/                         # Protobuf 生成文件
├── scripts/
│   ├── list_devices.py          # 音频设备列表工具
│   ├── vbcable_translator.py    # 单通道翻译工具（调试用）
│   ├── run.sh                   # macOS/Linux 启动脚本
│   └── healthcheck.sh           # 健康检查脚本
└── README.md                    # 本文件
```

## 版本历史

### v3.0 (当前版本) - 智能字幕增强

- Channel 2 字幕智能聚合与去重，英文/中文分行显示
- 中文文本美化处理（标点后自动空格、智能换行）
- Channel 1 可选关闭，支持纯字幕模式
- 字幕显示格式优化（行间距、内边距调整）
- 支持 macOS（BlackHole 虚拟音频）
- 配置文件统一整合（Windows/macOS 合并到同一模板）

### v2.0 - 双向翻译

- 双通道独立并发执行
- 耳机物理隔离，无回声
- 简化架构，移除冲突检测
- 智能字幕窗口（双缓冲区去重）
- 线程安全的 UI 更新
- 完善的错误处理和重试机制
- 支持所有主流会议和 IM 软件

### v1.0 - 单向翻译

- 基础麦克风到 VB-CABLE 翻译
- 火山引擎 S2S 集成
- 音频冲突检测机制

## 计划中功能 (Roadmap)

- **音色模拟** - 自定义输出语音的音色特征
- **智能降噪** - 背景音消除和自动音量均衡
- **多语言扩展** - 支持更多语言对
- **专业术语库** - 行业术语定制
- **GUI 控制面板** - 图形化配置和监控
- **多人会议支持** - 多路音频分离和说话人识别

**注**: 部分功能取决于火山引擎 API 的支持情况。

## 作者信息

**作者**: Sue

**联系方式**:
- GitHub: [Im-Sue](https://github.com/Im-Sue/)
- X (Twitter): [@ssssy83717](https://x.com/ssssy83717)
- Telegram: [@Sue_muyu](https://t.me/Sue_muyu)

## 贡献者

- [XiaoHai67890](https://github.com/XiaoHai67890)

## License

**版权所有 © 2024 Sue**

本项目采用自定义许可协议：

### 个人使用
- **允许** 个人学习、研究、非商业使用
- **要求** 保留版权声明和作者信息

### 商业使用
- **禁止** 未经授权的商业使用
- **需要** 联系作者获取商业授权许可

如需商业授权，请通过以下方式联系：
- X: [@ssssy83717](https://x.com/ssssy83717)
- Telegram: [@Sue_muyu](https://t.me/Sue_muyu)

### 免责声明

本软件按"原样"提供，不提供任何明示或暗示的保证，包括但不限于适销性、特定用途适用性和非侵权性的保证。在任何情况下，作者或版权持有人均不对任何索赔、损害或其他责任负责。

## 致谢

- [火山引擎](https://www.volcengine.com/) - 提供同声传译 API 服务
- [VB-CABLE](https://vb-audio.com/Cable/) - Windows 虚拟音频设备
- [BlackHole](https://existential.audio/blackhole/) - macOS 虚拟音频设备
- [sounddevice](https://python-sounddevice.readthedocs.io/) - Python 音频库

## 反馈与支持

如遇到问题或有改进建议，欢迎通过以下方式联系：

- **Issues**: [GitHub Issues](https://github.com/Im-Sue/simultaneous_interpretation/issues)
- **X**: [@ssssy83717](https://x.com/ssssy83717)
- **Telegram**: [@Sue_muyu](https://t.me/Sue_muyu)

---

**快速开始**: `pip install -r requirements.txt && cp config.yaml.example config.yaml && python main.py`

**重要提示**: 请务必使用耳机，避免音频回声！
