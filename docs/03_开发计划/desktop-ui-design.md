# 实时同传桌面应用 — 整体设计方案

> 作者：Sue
> GitHub：https://github.com/Im-Sue/
> TG：@Sue_muyu
> 日期：2026-03-26
> 版本：v1.0
> 分支：desktop-ui

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    Tauri 2 桌面壳                             │
│                                                             │
│  ┌────────────────────┐      ┌──────────────────────────┐   │
│  │    主窗口           │      │   字幕浮窗（独立窗口）     │   │
│  │  ┌──────┬───────┐  │      │   横向半透明置顶条        │   │
│  │  │配置页│ 日志页 │  │      │   EN/ZH 双行滚动显示      │   │
│  │  │(Tab) │ (Tab)  │  │      │   decorations: false      │   │
│  │  └──────┴───────┘  │      │   always_on_top: true      │   │
│  └─────────┬──────────┘      └────────────┬─────────────┘   │
│            │                              │                  │
│            │    ws://127.0.0.1:{port}     │                  │
│            └──────────────┬───────────────┘                  │
│                           │                                  │
│  ┌────────────────────────┴─────────────────────────────┐   │
│  │          rt-engine.exe（Embedded Python）              │   │
│  │                                                       │   │
│  │  WebSocket Server (aiohttp/websockets)                │   │
│  │  ├─ /ws/control   ← 配置读写、启停、设备扫描          │   │
│  │  ├─ /ws/logs      → 日志实时推送                      │   │
│  │  └─ /ws/subtitle  → 字幕实时推送                      │   │
│  │                                                       │   │
│  │  DualChannelTranslator（核心不动）                     │   │
│  │  ├─ CH1: 麦克风→火山S2S→VB-CABLE                     │   │
│  │  └─ CH2: 系统音频→火山S2T→字幕                       │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 核心设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 桌面框架 | Tauri 2 (v2.10.1) | 已有构建产物，包体小，多窗口支持好 |
| Python 打包 | Embedded Python + .py 源码 | 比 PyInstaller 调试方便、启动快、更透明 |
| 前后端通信 | WebSocket (localhost) | 真正双向推送，适合字幕流/日志流实时场景 |
| UI 页面 | 2 页 + 1 独立字幕浮窗 | 精简实用，配置页折叠面板 + 日志页 |
| 翻译核心 | 不动 | DualChannelTranslator 已验证，仅做服务化封装 |

---

## 二、技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 桌面壳 | Tauri 2 | 2.x (Cargo.toml pinned) |
| 前端框架 | React + TypeScript | React 19.1 + TS 5.8 |
| 前端构建 | Vite + pnpm | Vite 6.3 |
| UI 组件库 | 纯 CSS 自定义组件（暗色主题 + CSS 变量系统） | 无第三方 UI 库 |
| Python 运行时 | Embedded Python | 3.12.8 |
| Python 依赖 | numpy / sounddevice / websockets / protobuf / PyYAML | 同 requirements.txt |
| 前后端通信 | WebSocket (`websockets` 库, 127.0.0.1) | websockets >= 14 |
| 翻译引擎 | 火山引擎 AST WebSocket + protobuf | 不动 |

---

## 三、目录结构

### 开发期

```
realtime_translator/
├── src/                        # React 前端源码
│   ├── App.tsx                 # 主路由（/ → 主窗口, /subtitle → 字幕浮窗）
│   ├── main.tsx                # React 入口
│   ├── index.css               # 全局样式（暗色主题 + CSS 变量）
│   ├── vite-env.d.ts
│   ├── pages/
│   │   ├── ConfigPage.tsx      # 配置页（折叠面板，含内联子组件）
│   │   └── LogPage.tsx         # 日志页
│   ├── components/
│   │   ├── SubtitleOverlay.tsx  # 字幕浮窗内容
│   │   └── StatusBar.tsx       # 顶部状态栏+启停按钮
│   ├── hooks/
│   │   └── useWebSocket.ts     # WS 连接管理（control/logs/subtitle 三条）
│   └── types/
│       └── ipc.ts              # 前后端消息类型定义
│
├── src-tauri/                  # Tauri Rust 壳
│   ├── src/
│   │   ├── lib.rs              # sidecar 拉起、多窗口管理、进程生命周期
│   │   └── main.rs             # Tauri 入口
│   ├── tauri.conf.json         # Tauri 配置（主窗口 + 字幕浮窗）
│   ├── Cargo.toml              # Rust 依赖
│   └── capabilities/
│       └── default.json        # 权限声明
│
├── core/                       # Python 翻译核心（不动）
│   ├── logging_utils.py        # 新增：结构化日志系统
│   ├── audio_capture.py
│   ├── audio_output.py
│   ├── system_audio_capture.py
│   └── volcengine_client.py
│
├── desktop_backend/            # Python 桌面后端服务
│   ├── sidecar.py              # 入口：WS server + 命令分发 + watchdog
│   └── services.py             # 合并的服务层（Config/Device/Health/Runtime）
│
├── gui/                        # Tkinter 字幕窗（保留兼容 CLI 模式）
│   └── subtitle_window.py
│
├── pb2/                        # protobuf（不动）
├── main.py                     # CLI 主入口（保留，已适配新日志系统）
├── config.yaml.example         # 配置模板
├── requirements.txt            # Python 依赖
├── package.json                # 前端依赖（React 19 + Tauri API）
├── pnpm-lock.yaml
├── vite.config.ts              # Vite 6 配置
├── tsconfig.json
├── tsconfig.node.json
├── index.html                  # HTML 入口
├── docs/                       # 项目文档知识库
│   ├── .ccb/                   # 协作索引、spec、ADR
│   ├── 02_需求设计/
│   │   └── desktop-ui-followup-notes.md
│   ├── 03_开发计划/
│   │   ├── desktop-ui-design.md    # 本文件
│   │   └── desktop-ui-tasks.md
│   └── 13_项目报告/
│       └── phase-report-2026-03-27.md
└── scripts/
    └── build_bundle.ps1        # Windows 构建脚本（PowerShell）
```

### 打包后（用户拿到的）

```
RealtimeTranslator/
├── realtime-translator.exe     # Tauri 壳（Win）/ .app（Mac）
├── python/                     # Embedded Python (~15MB)
│   ├── rt-engine.exe           # python.exe 改名
│   ├── python312.dll
│   ├── rt-engine._pth          # 搜索路径: ../deps, ../backend, ../backend/realtime_translator
│   ├── ffmpeg.exe              # 音频解码（静态构建）
│   └── ...
├── backend/                    # .py 源码（保持包结构）
│   └── realtime_translator/    # 项目根包
│       ├── desktop_backend/
│       │   ├── sidecar.py      # WS server 入口
│       │   └── services.py     # 合并的服务层
│       ├── core/               # 翻译核心
│       ├── pb2/                # protobuf
│       ├── gui/                # Tkinter 字幕（CLI 兼容）
│       ├── main.py             # DualChannelTranslator 定义
│       └── config.yaml.example
├── deps/                       # pip 预装依赖 (~45MB)
│   ├── numpy/
│   ├── sounddevice/
│   ├── websockets/
│   └── ...
└── （config.yaml 存储在 %APPDATA%/RealtimeTranslator/）
```

---

## 四、WebSocket 通信协议

### 启动握手

```
Tauri 拉起 rt-engine.exe
    ↓
Python stdout 输出一行: {"ready": true, "port": 18923}
    ↓
Tauri 读到后，前端连接 ws://127.0.0.1:18923
    ↓
三条 WS 连接并行建立:
  /ws/control   — 请求/响应式（配置、启停）
  /ws/logs      — 服务端推送（日志流）
  /ws/subtitle  — 服务端推送（字幕流）
```

### /ws/control 命令协议

**请求**（前端 → Python）：

```json
{"id": "uuid", "cmd": "命令名", "payload": {}}
```

**响应**（Python → 前端）：

```json
{"id": "uuid", "ok": true, "data": {}}
```

```json
{"id": "uuid", "ok": false, "error": "错误描述"}
```

**命令清单**：

| cmd | payload | 返回 data | 说明 |
|-----|---------|----------|------|
| `load_config` | `{}` | 完整配置对象 | 加载当前 config.yaml |
| `save_config` | 完整配置对象 | `{}` | 保存到 config.yaml |
| `scan_devices` | `{}` | `{input: [...], output: [...]}` | 扫描音频设备列表 |
| `test_connection` | volcengine 凭据 | `{ok, latency_ms}` | 测试火山引擎连通性 |
| `env_check` | `{}` | `{items: [{name, ok, msg}]}` | 环境健康检查 |
| `start` | `{}` | `{}` | 启动翻译 |
| `stop` | `{}` | `{stats}` | 停止翻译，返回统计 |
| `status` | `{}` | `{running, ch1, ch2, uptime}` | 运行状态查询 |

### /ws/logs 推送格式

```json
{
  "ts": "14:32:01.123",
  "level": "INFO",
  "channel": "CH1",
  "module": "volc",
  "msg": "WebSocket 已连接 session=a3f8..."
}
```

### /ws/subtitle 推送格式

```json
{
  "type": "update",
  "en": "I think we should discuss the quarterly results",
  "zh": "我认为我们应该先讨论季度业绩",
  "is_final": false
}
```

```json
{
  "type": "flush",
  "en": "I think we should discuss the quarterly results first.",
  "zh": "我认为我们应该先讨论季度业绩。",
  "is_final": true
}
```

---

## 五、UI 设计

### 页面 A：配置页（默认首页）

```
┌─────────────────────────────────────────────────────────┐
│  实时同传                                                │
│  ● 已停止 / ● 运行中 (00:12:34)     [▶ 启动] [■ 停止]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ▼ 火山引擎凭据                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │ WebSocket 地址  [wss://openspeech.bytedance...]   │  │
│  │ App Key         [________________________]        │  │
│  │ Access Key      [________________________]  (密文) │  │
│  │ Resource ID     [volc.service_type.10053__]       │  │
│  │                              [测试连接]           │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ▶ 音频设备                                              │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 麦克风      [下拉选择 ▾]              [🔄 刷新]    │  │
│  │ 系统音频    [下拉选择 ▾]                           │  │
│  │ 回退设备    [下拉选择 ▾]                           │  │
│  │ 输出设备    [下拉选择 ▾]                           │  │
│  │ FFmpeg 解码  [✓]                                  │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ▶ 翻译通道                                              │
│  ┌───────────────────────────────────────────────────┐  │
│  │ CH1 中文→英文   [开/关]   模式: s2s               │  │
│  │ CH2 英文→中文   [开/关]   模式: s2t               │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ▶ 字幕设置                                              │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 字号 [14]  透明度 [0.85]  背景 [#000] 文字 [#FFF] │  │
│  │ 历史条数 [1000]  时间戳 [否]                       │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  [保存配置]                                              │
├─────────────────────────────────────────────────────────┤
│  [⚙ 配置]  [📋 日志]                        底部 Tab    │
└─────────────────────────────────────────────────────────┘
```

**交互规则**：

- 运行中时配置面板置灰不可编辑，必须停止后才能改配置
- 音频设备下拉来自 `scan_devices` 实时扫描
- 保存配置 → `save_config` → 写入 config.yaml
- 启动 → 先自动 `load_config` 校验 → 通过后 `start`

### 页面 B：日志页

```
┌─────────────────────────────────────────────────────────┐
│  运行日志                         [刷新] [清空] [导出]   │
├─────────────────────────────────────────────────────────┤
│  级别: [全部▾]   通道: [全部] [CH1] [CH2] [SYS]  [搜索] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  14:32:01.123 [INFO]  [SYS]  翻译器已启动               │
│  14:32:01.456 [INFO]  [CH1]  麦克风已连接: "麦克风" #2   │
│  14:32:01.789 [INFO]  [CH2]  系统音频已连接: "立体声" #5 │
│  14:32:02.012 [INFO]  [SYS]  火山引擎已连接              │
│  14:32:05.234 [DEBUG] [CH1]  音频块 #1 1600B             │
│  14:32:10.789 [WARN]  [CH2]  音频静默 >3s               │
│  14:32:15.012 [ERROR] [CH1]  WebSocket 断连 code=1006   │
│  ...                                                    │
│  (自动滚底，新日志追加)                                   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [⚙ 配置]  [📋 日志]                        底部 Tab    │
└─────────────────────────────────────────────────────────┘
```

**日志颜色**：INFO=白, DEBUG=灰, WARN=黄, ERROR=红

### 独立窗口 C：字幕浮窗

```
屏幕底部居中，主窗口之外的独立窗口：

┌──────────────────────────────────────────────────────────────────┐
│  EN  I think we should discuss the quarterly results first.      │
│  ZH  我认为我们应该先讨论季度业绩。                                │
└──────────────────────────────────────────────────────────────────┘
```

**窗口属性**：

| 属性 | 值 | 说明 |
|------|---|------|
| `decorations` | false | 无标题栏/边框 |
| `transparent` | true | 背景半透明 |
| `always_on_top` | true | 置顶 |
| `skip_taskbar` | true | 不在任务栏显示 |
| 宽度 | 屏幕宽 70% | — |
| 高度 | 自适应 2-3 行 | — |
| 位置 | 屏幕底部居中，距底边 50px | — |

**字幕动态效果**：

- 新句进入 → 底部滑入（200ms CSS transition）
- 超过 2 句 → 最旧一句向上淡出
- 静默 >5s → 整体透明度降至 30%
- 新句再来 → 透明度恢复 85%
- EN 行：14px 浅灰 / ZH 行：16px 白色
- 拖拽移动：`window.startDragging()`
- 双击：切换字号（小/中/大）

---

## 六、Python 后端改造

### 改动范围（已完成）

**已改的**：

| 文件 | 改动 | 说明 |
|------|------|------|
| `desktop_backend/sidecar.py` | 重写 | 入口改为 WS server（`websockets` 库），三端点路由分发 + watchdog |
| `desktop_backend/services.py` | 新建（合并） | Config/Device/Health/Runtime 四个 Service 合并为一个文件 |
| `core/logging_utils.py` | 新增 | ChannelFormatter + WSLogHandler + ChannelLogger + setup_logging() |
| `main.py` | 改造 | 适配新日志系统，桌面模式跳过 Tkinter |

**不动的**：

| 文件 | 原因 |
|------|------|
| `core/volcengine_client.py` 等 | 翻译核心不动 |
| `gui/subtitle_window.py` | Tkinter 字幕保留给 CLI 模式 |
| `pb2/` | protobuf 不动 |

### RuntimeService 核心功能

**服务职责**：
- 包装 DualChannelTranslator 为可控服务
- 管理翻译器生命周期（启动/停止/状态查询）
- 维护运行状态机（stopped / starting / running / error）

**核心接口**：

| 方法 | 功能 | 返回 |
|------|------|------|
| `__init__(config_path)` | 初始化服务，加载配置路径 | - |
| `start()` | 启动翻译器，注入字幕回调函数 | 异步 |
| `stop()` | 停止翻译器，返回运行统计 | 统计数据字典 |
| `get_status()` | 查询当前运行状态 | 状态详情（运行中/通道状态/运行时长） |

**关键改造点**：
- 字幕输出重定向：从 Tkinter 窗口更新改为 WebSocket 回调推送
- 回调注入机制：通过 `subtitle_callback` 参数注入 WS 广播函数
- 桌面模式兼容：`subtitle_callback` 为 None 时回退到 Tkinter（CLI 模式）
- 翻译核心逻辑不变：仅改变输出方式，保留原有双通道翻译能力

---

## 七、日志系统设计

### 日志格式

```
{timestamp}.{ms} [{level:5}] [{channel:3}] [{module:8}] {message}
```

### 字段说明

| 字段 | 说明 | 值域 |
|------|------|------|
| `timestamp` | 毫秒精度 | `%Y-%m-%d %H:%M:%S.%f` |
| `level` | 日志级别 | `DEBUG / INFO / WARN / ERROR` |
| `channel` | 通道标识 | `SYS`(系统) / `CH1`(中→英) / `CH2`(英→中) |
| `module` | 模块来源 | `main / audio / volc / output / subtitle / config` |
| `message` | 主体内容 | 人类可读描述 |
| `context` | 关联信息 | session_id / 设备名 / 错误码 / 重试次数 |

### 实现组件

实现位置：`core/logging_utils.py`

**ChannelFormatter（通道格式器）**
- 功能：为日志记录注入通道标识字段
- 特性：自动补充缺失的 channel 字段，默认为 SYS
- 输出：符合统一格式规范的日志字符串

**WSLogHandler（WebSocket 日志处理器）**
- 功能：双通道日志输出（文件持久化 + WebSocket 实时推送）
- 特性：
  - 环形缓冲：保留最近 500 条日志供前端历史回放
  - 异步广播：非阻塞推送到所有 WS 客户端
  - 结构化输出：JSON 格式（时间戳/级别/通道/模块/消息）

**ChannelLogger（通道日志适配器）**
- 功能：为标准 Logger 绑定固定通道标识
- 特性：包装所有日志方法（info/debug/warning/error），自动注入 channel extra
- 使用：`ch1_log = ChannelLogger(logger, "CH1")` → `ch1_log.info("消息")`

### 日志关联信息示例

| 场景 | 日志内容 |
|------|---------|
| 设备连接 | `[CH1] [audio] 麦克风已连接: "麦克风 (Realtek)" idx=2 sr=16000` |
| 音频发送 | `[CH1] [audio] 音频块 #142 size=1600B queue_depth=3` |
| WS 发送 | `[CH1] [volc] → send_audio 1600B session=a3f8` |
| 文本接收 | `[CH1] [volc] ← text "Hello world" is_final=true latency=1.2s` |
| 音频接收 | `[CH1] [volc] ← audio 4096B opus session=a3f8` |
| 播放输出 | `[CH1] [output] 播放 4096B → "CABLE Input" queue_depth=1` |
| 字幕更新 | `[CH2] [subtitle] flush "我认为..." (en=42c zh=18c)` |
| 断连重连 | `[CH1] [volc] WebSocket 断连 code=1006 reason="EOF" \| 重连 #1` |
| 设备异常 | `[CH2] [audio] 音频静默 >3s device="立体声混音"` |
| 配置操作 | `[SYS] [config] 配置已保存 config.yaml (4 sections)` |

---

## 八、构建与打包

### 构建脚本 `scripts/build_bundle.ps1`（Windows PowerShell）

**脚本参数**：
- 无参数：完整构建流程（下载 Python + 安装依赖 + 打包 Tauri）
- `-SkipPython`：跳过 Python 下载（复用已有 bundle）
- `-BundleOnly`：仅准备 bundle 目录，不执行 Tauri 打包

**构建流程（5 步）**：

1. **准备 Embedded Python**
   - 下载 python-3.12.8-embed-amd64.zip
   - 解压到 `bundle/windows-x64/python/`
   - 重命名 `python.exe` → `rt-engine.exe`（避免与系统 Python 冲突）
   - 配置 `rt-engine._pth` 设置模块搜索路径（`../deps`, `../backend`, `../backend/realtime_translator`）

2. **安装 Python 依赖**
   - 使用系统 pip（embedded Python 无 pip）
   - 目标目录：`bundle/windows-x64/deps/`
   - 依赖来源：`requirements.txt`

3. **准备 FFmpeg 编解码器**
   - 优先从系统 PATH 复制 `ffmpeg.exe`
   - 不存在则在线下载静态构建版
   - 放置到 `bundle/windows-x64/python/`

4. **复制源码**
   - 目标：`bundle/windows-x64/backend/realtime_translator/`
   - 保持包结构：`core/`, `desktop_backend/`, `pb2/`, `gui/`, `main.py`
   - 排除：测试文件、缓存目录、开发配置

5. **Tauri 打包**
   - 动态注入 `resources` 路径到 `tauri.conf.json`（通过 `TAURI_CONFIG` 环境变量）
   - 执行 `pnpm tauri build`
   - 生成 NSIS/MSI 安装包

> **注意**：原设计为 bash 脚本，实际采用 PowerShell 以更好支持 Windows 开发环境。

### Tauri 打包配置

**资源打包策略**：
- 配置位置：`tauri.conf.json` 的 `bundle.resources` 字段
- 动态注入：构建时通过 `TAURI_CONFIG` 环境变量注入路径
- 资源内容：`bundle/windows-x64/**`（包含 python/backend/deps 三个目录）

**Sidecar 启动流程**（`src-tauri/src/lib.rs`）：
1. 定位资源目录（`resource_dir`）
2. 构建启动命令：`python/rt-engine.exe backend/sidecar.py --parent-pid {tauri_pid}`
3. 设置环境变量：`PYTHONPATH` 指向 `deps` 目录
4. 管道重定向：捕获 stdout（读取端口信息）
5. 读取就绪信号：解析 JSON 格式的 `{"ready": true, "port": 18923}`
6. 通知前端：通过 Tauri Event 发送端口号，触发 WebSocket 连接

---

## 九、进程管理

### 生命周期

```
┌─ 启动 ─────────────────────────────────────────────┐
│ Tauri 启动                                          │
│   → 检查残留进程（PID 文件），有则杀掉              │
│   → 拉起 rt-engine.exe --parent-pid {tauri_pid}    │
│   → 读 stdout: {"ready": true, "port": 18923}      │
│   → 前端连接 ws://127.0.0.1:18923                  │
│   → 写 PID 文件到 app_data/rt-engine.pid           │
└─────────────────────────────────────────────────────┘

┌─ 运行中 ────────────────────────────────────────────┐
│ Python 端心跳线程：                                  │
│   每 3 秒检查 parent_pid 是否存在                    │
│   不存在 → os._exit(1)                              │
│                                                     │
│ Tauri 端：                                          │
│   WS 连接断了 → 尝试重连 3 次 → 失败则重拉 sidecar  │
│                                                     │
│ 单实例保护：                                        │
│   Tauri: tauri-plugin-single-instance               │
│   Python: 启动时检查端口是否已占用                   │
└─────────────────────────────────────────────────────┘

┌─ 退出 ──────────────────────────────────────────────┐
│ 正常退出：Tauri close → WS 发 stop → Python 清理退出│
│ 异常退出：心跳检测 → Python 自杀 → 清理 PID 文件    │
│ 强杀场景：OS Job Object 回收子进程（Windows）       │
└─────────────────────────────────────────────────────┘
```

### 心跳机制

**实现位置**：`desktop_backend/sidecar.py`

**Watchdog 守护线程**：
- 启动时机：sidecar 进程启动时接收 `--parent-pid` 参数
- 检测间隔：每 3 秒检查一次父进程状态
- 检测方法：使用 `os.kill(pid, 0)` 探测进程存在性（不发送实际信号）
- 异常处理：捕获 `OSError` 表示父进程已消失
- 自毁机制：父进程不存在时调用 `os._exit(1)` 立即退出（跳过清理）

**线程属性**：
- 类型：daemon 守护线程（随主线程退出而终止）
- 优先级：后台运行，不阻塞 WebSocket 服务

---

## 十、实施路线

| 阶段 | 内容 | 依赖 | 估计范围 |
|------|------|------|---------|
| **P0** | 统一命名漂移（清理 main_v2.py / config_v2.yaml 残留引用） | 无 | 小 |
| **P1** | Python 日志系统改造（ChannelLogger + 格式统一） | 无 | 中 |
| **P2** | desktop_backend/sidecar.py 改造为 WS server | P1 | 中 |
| **P3** | RuntimeService 服务化封装（包装 DualChannelTranslator） | P2 | 中 |
| **P4** | 恢复/新建 src-tauri/tauri.conf.json + Rust 侧 sidecar 拉起 | P2 | 中 |
| **P5** | 前端配置页（折叠面板 + 启停控制） | P4 | 大 |
| **P6** | 前端日志页 | P4 | 中 |
| **P7** | 字幕浮窗（Tauri 多窗口 + 字幕动效） | P3 | 大 |
| **P8** | 构建脚本 build_bundle.sh + 打包验证 | P5-P7 | 中 |
| **P9** | macOS 适配 + 代码签名 | P8 | 中 |

**并行策略**：P0-P3 是纯 Python 端，可独立开发验证（`python sidecar.py --dev` 跑起来用浏览器 WS 客户端调试）。P4-P7 是前端 + Tauri 壳。两条线可以并行推进。

---

## 十一、开发期工作流

```bash
# 终端 1：直接跑 Python 后端（无需打包）
python desktop_backend/sidecar.py --dev --port 18923

# 终端 2：Tauri dev（前端 HMR + Tauri 壳）
pnpm tauri dev

# 改了 .py → 重启终端 1 即可，秒级生效
# 改了前端 → Vite HMR 自动刷新
```

---

## 十二、已决策事项与待办

### 已决策

| 项 | 决策结果 | 说明 |
|----|---------|------|
| UI 组件库 | 无第三方库，纯 CSS | 采用自定义暗色主题 + CSS 变量系统 + glassmorphism 设计 |
| WebSocket 库 | `websockets` | 已在依赖中，三端点架构（control/logs/subtitle） |
| config.yaml 路径 | `%APPDATA%/RealtimeTranslator/` | 桌面版采用用户目录，便于卸载后保留配置 |
| Python 打包方式 | Embedded Python + 源码 | 比 PyInstaller 启动快、调试方便、透明度高 |

### 待办事项

| 项 | 优先级 | 备注 |
|----|-------|------|
| 资源嵌入安装包问题 | P0 | NSIS/MSI 未包含 bundle 资源（78.8MB），需修复 |
| macOS 适配 | P1 | python-build-standalone 版本验证 + sounddevice 兼容性测试 |
| 代码签名与公证 | P1 | Windows Authenticode + macOS notarize |
| 多语言国际化 | P2 | UI 中英文切换支持 |
