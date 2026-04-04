# 实时同传桌面应用

[![Version](https://img.shields.io/badge/version-3.x-blue.svg)](https://github.com/Im-Sue/simultaneous_interpretation)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![Tauri](https://img.shields.io/badge/Tauri-2.x-24c8db.svg)](https://tauri.app/)

> 中文 | [English](README_EN.md)

一个面向会议场景的实时同传桌面应用，当前主链路是 `Tauri + React` 桌面壳层配合 `Python sidecar` 翻译引擎，提供：

- `CH1`：你说中文，对方听英文语音
- `CH2`：对方说英文，你看中英双行字幕

当前分支已经从“单脚本 + Tk 字幕窗口”为主，演进到“桌面端主控 + sidecar 服务化 + 独立字幕浮窗”的形态；CLI 模式仍保留，主要用于兼容和调试。

## 当前能力

- 桌面端配置页支持火山引擎凭据、音频设备、字幕样式和通道开关配置。
- Tauri 主进程负责拉起 Python sidecar，并通过本地 WebSocket 与前端通信。
- `CH1` 默认支持 `PCM 48kHz` 直出到虚拟音频设备，也保留 `ogg_opus + FFmpeg` 回退链路。
- `CH2` 基于火山引擎字幕生命周期事件输出 `start / streaming / end`，桌面浮窗可稳定显示中英双行。
- 日志页支持实时日志查看、筛选、搜索和导出，方便定位设备、连接和播放问题。
- 配置文件在开发模式下存放于项目根目录，在打包模式下存放于应用数据目录，升级时不丢配置。

## 运行架构

```text
┌────────────────────────────┐
│ Tauri / React 桌面前端     │
│ - 配置页                   │
│ - 日志页                   │
│ - 字幕浮窗                 │
└────────────┬───────────────┘
             │ invoke + event
┌────────────▼───────────────┐
│ Tauri Rust 宿主            │
│ - 启动/停止 sidecar        │
│ - 管理主窗口/字幕浮窗      │
└────────────┬───────────────┘
             │ stdout 返回端口
┌────────────▼───────────────┐
│ Python sidecar             │
│ - /ws/control              │
│ - /ws/logs                 │
│ - /ws/subtitle             │
└────────────┬───────────────┘
             │
┌────────────▼───────────────┐
│ DualChannelTranslator      │
│ - CH1 麦克风 -> 英文语音   │
│ - CH2 系统音频 -> 中文字幕 │
└────────────────────────────┘
```

## 核心链路

### CH1 你说中文，对方听英文

```text
麦克风 -> AudioCapturer -> VolcengineTranslator(s2s)
      -> PcmStreamPlayer / OggOpusPlayer
      -> VB-CABLE Input -> 会议软件麦克风
```

### CH2 对方说英文，你看字幕

```text
系统音频 -> SystemAudioCapturer -> VolcengineTranslator(s2t)
        -> main.py 字幕状态机 -> /ws/subtitle
        -> React SubtitleOverlay
```

## 快速开始

### 1. 安装依赖

Python 依赖：

```bash
pip install -r requirements.txt
```

前端依赖：

```bash
pnpm install
```

### 2. 准备配置

```bash
cp config.yaml.example config.yaml
```

然后在 `config.yaml` 中填写：

- `volcengine.app_key`
- `volcengine.access_key`
- `audio.microphone.device`
- `audio.system_audio.device`
- `audio.vbcable_output.device`

可用设备可通过下面命令查看：

```bash
python scripts/list_devices.py
```

### 3. 启动方式

桌面开发模式：

```bash
pnpm tauri dev
```

这会启动 React 前端、Tauri 宿主和 Python sidecar。

CLI 兼容模式：

```bash
python main.py
python main.py my_config.yaml
```

CLI 模式下如果未注入桌面字幕回调，会回退到 Tk 字幕窗口实现。

## 配置重点

### 火山引擎

- 服务地址默认是 `wss://openspeech.bytedance.com/api/v4/ast/v2/translate`
- 当前需要同时配置 `app_key`、`access_key`、`resource_id`
- 桌面配置页支持“测试连接”，会使用真实认证头发起握手

### CH1 输出配置

当前桌面默认值已经调整为：

```yaml
audio:
  vbcable_output:
    device: "CABLE Input"
    sample_rate: 48000
    target_format: "pcm"
    use_ffmpeg: true
```

说明：

- `target_format: pcm` 是当前默认推荐路径，能直接配合 `PcmStreamPlayer` 做流式播放。
- `sample_rate: 48000` 适合虚拟声卡和会议软件链路。
- 如果需要兼容旧链路，可改回 `ogg_opus` 并启用 FFmpeg 解码。

### 配置文件位置

| 场景 | 配置位置 |
|------|----------|
| 开发模式 | 项目根目录下的 `config.yaml` |
| 打包模式 | `RT_APP_DATA` 或 `%APPDATA%/RealtimeTranslator/config.yaml` |

## 桌面端交互

### 主窗口

- 左侧是配置页，包含凭据、音频设备、通道和字幕设置。
- 右侧是日志页，展示 `SYS / CH1 / CH2` 三类实时日志。
- 顶部状态栏支持启动、停止、显示/隐藏字幕窗口。

### 字幕浮窗

- 独立 WebView 窗口，不依赖主窗口持续可见。
- 支持中英双行显示、滚动追加、静默态降显。
- 支持展开/收起和隐藏窗口。
- 样式由 `subtitle_window.font_size / opacity / text_color` 控制，并通过 `/ws/subtitle` 实时下发。

## 常见问题

### 1. 启动桌面端后一直显示“等待 sidecar 启动”

优先检查：

- Python 依赖是否安装完整
- `desktop_backend/sidecar.py` 能否单独启动
- Tauri 是否成功读取到 sidecar stdout 输出的端口信息

### 2. CH1 有日志但对方听不到声音

优先检查：

- `audio.vbcable_output.device` 是否指向正确的虚拟输出设备
- 会议软件麦克风是否选择了 `CABLE Output`
- 当前是否使用 `pcm / 48000Hz`，以及虚拟声卡是否支持对应采样率
- 日志页里 `CH1播放诊断` 是否出现连续 `underflow / rebuffer`

### 3. CH2 有翻译结果但字幕浮窗不更新

优先检查：

- 字幕窗口是否已显示
- `/ws/subtitle` 是否已连接
- `main.py` 是否输出了 `start / streaming / end` 生命周期事件
- 配置页保存后字幕配置是否正常广播

## 项目结构

```text
realtime_translator/
├── core/                    # Python 核心音频与火山引擎能力
├── desktop_backend/         # sidecar、服务层、桌面后端协议
├── src/                     # React 前端
├── src-tauri/               # Tauri Rust 宿主
├── docs/                    # 架构、模块规格、经验沉淀
├── main.py                  # CLI / 桌面共用翻译主控
├── config.yaml.example      # 配置模板
└── README.md
```

## 文档入口

- [docs 总览](./docs/README.md)
- [模块规格目录](./docs/04_模块规格/README.md)
- [系统整体架构](./docs/01_架构设计/系统整体架构.md)
- [运行链路架构说明](./docs/01_架构设计/运行链路架构说明.md)

## 当前状态

- 当前仓库主路径已经切到桌面端交互优先。
- 基础启停、日志、字幕、配置读写和火山连接测试已经打通。
- 分支内最近一次重点优化是 `CH1 PCM 直出 + 缓冲诊断`，以及 `CH2 字幕事件流` 对齐桌面浮窗。

## License

本项目采用仓库当前约定的自定义授权方式。涉及商业使用时，请先联系作者确认授权边界。
