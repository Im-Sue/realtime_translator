# Phase 2 技术规划 - 双向翻译系统 (耳机模式)

## 📊 执行摘要

**目标**: 实现中英文双向实时翻译，使用耳机隔离音频，简化架构设计

**核心策略**: 通过耳机提供物理层音频隔离，避免回声问题，无需复杂的冲突检测

**预计时间**: 2-3周

**版本号**: v2.0.0

---

## 🎯 设计决策：为什么选择耳机模式？

### 音频架构分析

#### 输出通道独立性 ✅

```
Channel 1 (用户→对方):
麦克风 → 火山引擎(zh→en) → VB-CABLE Input → Zoom → 对方

Channel 2 (对方→用户):
Zoom → 系统音频(立体声混音/CABLE Output) → 火山引擎(en→zh) → 字幕窗口
```

**关键理解**:
- VB-CABLE Input 和 扬声器/耳机 是**独立的输出通道** ❌ 不会冲突
- 数字音频路由层面**完全隔离** ✅

#### 回声问题的真正原因

**扬声器模式**:
```
对方说话 → Zoom → 扬声器播放 → 空气传播 → 麦克风捕获 ❌
→ 火山引擎翻译 → VB-CABLE → 对方听到回声
```

**耳机模式**:
```
对方说话 → Zoom → 耳机播放 → 用户耳朵(物理隔离) ✅
麦克风无法捕获耳机音频 → 无回声问题
```

### 物理 vs 软件解决方案

| 方案 | 复杂度 | 可靠性 | 延迟 | 用户体验 |
|------|--------|--------|------|----------|
| **耳机模式** (Phase 2) | ⭐ 低 | ⭐⭐⭐⭐⭐ 100% | 0ms | 舒适,自然 |
| **扬声器+VAD** (Phase 4) | ⭐⭐⭐⭐ 高 | ⭐⭐⭐ 95% | ~100ms | 需要调优 |

**决策**: Phase 2使用耳机模式，将扬声器模式推迟到Phase 4作为可选功能

---

## 🏗️ 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────┐
│      Realtime Translator v2.0 (耳机模式)             │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐              ┌─────────────────┐ │
│  │  Channel 1   │              │   Channel 2     │ │
│  │  麦克风捕获   │              │  系统音频捕获   │ │
│  │  (中文输入)  │              │  (英文输入)     │ │
│  └──────┬───────┘              └────────┬────────┘ │
│         │                               │          │
│         │ PCM 16kHz Mono               │          │
│         ↓                               ↓          │
│  ┌─────────────┐              ┌──────────────────┐ │
│  │ 火山引擎     │              │  火山引擎         │ │
│  │ s2s 翻译    │              │  s2t 翻译        │ │
│  │ zh → en     │              │  en → zh         │ │
│  └──────┬──────┘              └────────┬─────────┘ │
│         │                               │          │
│         ↓ Ogg Opus 24kHz                ↓ Text     │
│  ┌─────────────┐              ┌──────────────────┐ │
│  │ VB-CABLE    │              │  悬浮字幕窗口     │ │
│  │ Input       │              │  (Tkinter)       │ │
│  │ (给Zoom)    │              │  + 半透明        │ │
│  │             │              │  + 可拖动        │ │
│  │             │              │  + 置顶显示      │ │
│  └─────────────┘              └──────────────────┘ │
│                                                     │
│  🎧 用户使用耳机 → 物理隔离 → 无回声问题             │
└─────────────────────────────────────────────────────┘

物理音频流:
对方说话 → Zoom → 耳机 → 用户耳朵(隔离) ✅
用户说话 → 麦克风 → Zoom → 对方(无回声) ✅
```

### 核心特性

✅ **双通道独立并发**
- Channel 1: 麦克风 → 英文语音 (s2s模式)
- Channel 2: 系统音频 → 中文文本 (s2t模式)
- 无需相互协调或冲突检测

✅ **简化架构**
- 两个WebSocket连接完全独立
- 无需状态机管理
- 无需音频缓冲协调
- 无需VAD或音量检测

✅ **物理隔离优势**
- 耳机提供100%音频隔离
- 零延迟(相比软件检测)
- 零误检率
- 零配置成本

---

## 💻 核心组件

### 1. 系统音频捕获 (`core/system_audio_capture.py`)

**功能**: 捕获系统音频(立体声混音/CABLE Output)，用于接收对方的英文语音

**关键参数**:
- **设备**: 立体声混音 (首选) / CABLE Output (备选)
- **采样率**: 16kHz (火山引擎要求)
- **声道**: 单声道
- **块大小**: 1600 (100ms @ 16kHz)

**实现要点**:
```python
class SystemAudioCapturer:
    """
    系统音频捕获器
    捕获来自Zoom的对方英文语音
    """

    def __init__(self,
                 device_name: str = "立体声混音",
                 fallback_device: str = "CABLE Output",
                 sample_rate: int = 16000,
                 channels: int = 1,
                 chunk_size: int = 1600):
        """
        初始化系统音频捕获器

        Args:
            device_name: 主音频设备名称
            fallback_device: 降级设备名称
            sample_rate: 采样率 (Hz)
            channels: 声道数
            chunk_size: 音频块大小 (样本数)
        """
        self.device_name = device_name
        self.fallback_device = fallback_device
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        self.device_index = None
        self.stream = None
        self.audio_queue = queue.Queue()
        self.is_running = False

    def _find_device(self) -> int:
        """
        查找系统音频设备

        Returns:
            设备索引

        Raises:
            RuntimeError: 如果未找到任何可用设备
        """
        devices = sd.query_devices()

        # 1. 尝试找到主设备
        for i, device in enumerate(devices):
            if self.device_name in device['name'] and device['max_input_channels'] > 0:
                logger.info(f"✅ 找到系统音频设备: [{i}] {device['name']}")
                return i

        # 2. 尝试降级设备
        for i, device in enumerate(devices):
            if self.fallback_device in device['name'] and device['max_input_channels'] > 0:
                logger.warning(f"⚠️  使用降级设备: [{i}] {device['name']}")
                return i

        # 3. 抛出异常
        raise RuntimeError(
            f"未找到系统音频设备!\n"
            f"请确保已启用: {self.device_name} 或 {self.fallback_device}\n"
            f"Windows: 右键音量图标 → 声音 → 录制 → 启用'立体声混音'\n"
            f"或安装VB-CABLE: https://vb-audio.com/Cable/"
        )

    def start(self):
        """启动音频捕获"""
        self.device_index = self._find_device()
        self.is_running = True

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"系统音频状态: {status}")

            # 转换为字节流并放入队列
            audio_bytes = indata.tobytes()
            self.audio_queue.put(audio_bytes)

        self.stream = sd.InputStream(
            device=self.device_index,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=np.int16,
            blocksize=self.chunk_size,
            callback=audio_callback
        )

        self.stream.start()
        logger.info(f"🎤 系统音频捕获已启动")

    def get_chunk(self, timeout: float = None) -> bytes:
        """
        获取音频块

        Args:
            timeout: 超时时间(秒)

        Returns:
            音频字节流,如果超时则返回None
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        """停止音频捕获"""
        self.is_running = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            logger.info("🛑 系统音频捕获已停止")
```

**设备查找策略**:
1. **首选**: 立体声混音 (Stereo Mix) - Windows系统默认的混音设备
2. **降级**: CABLE Output - VB-CABLE的输出端(如果已安装)
3. **失败**: 提供清晰的配置指导

### 2. 悬浮字幕窗口 (`gui/subtitle_window.py`)

**功能**: 显示对方英文翻译成的中文字幕

**UI特性**:
- **窗口尺寸**: 800x100 (可配置)
- **位置**: 屏幕顶部居中(可拖动)
- **透明度**: 80% (可配置)
- **字体**: Microsoft YaHei, 24pt, 粗体
- **配色**: 黑色半透明背景 + 白色文字
- **行为**: 始终置顶,无边框

**交互功能**:
- **左键拖动**: 移动窗口位置
- **双击**: 切换字体大小 (24pt ↔ 32pt)
- **ESC键**: 隐藏/显示窗口

**实现要点**:
```python
import tkinter as tk
from tkinter import font
import threading

class SubtitleWindow:
    """
    悬浮字幕窗口
    显示对方英文翻译成的中文字幕
    """

    def __init__(self,
                 width: int = 800,
                 height: int = 100,
                 font_size: int = 24,
                 bg_color: str = "#000000",
                 text_color: str = "#FFFFFF",
                 opacity: float = 0.8,
                 position: str = "top_center"):
        """
        初始化字幕窗口

        Args:
            width: 窗口宽度
            height: 窗口高度
            font_size: 字体大小
            bg_color: 背景色(十六进制)
            text_color: 文字色(十六进制)
            opacity: 不透明度 (0.0-1.0)
            position: 位置 ("top_center", "bottom_center", "top_left", etc.)
        """
        self.width = width
        self.height = height
        self.font_size = font_size
        self.bg_color = bg_color
        self.text_color = text_color
        self.opacity = opacity
        self.position = position

        self.window = None
        self.label = None
        self.is_visible = True
        self.is_large_font = False

        # 拖动相关
        self.drag_x = 0
        self.drag_y = 0

    def create(self):
        """创建Tkinter窗口"""
        self.window = tk.Tk()
        self.window.title("字幕窗口")

        # 窗口设置
        self.window.geometry(f"{self.width}x{self.height}")
        self.window.configure(bg=self.bg_color)
        self.window.overrideredirect(True)  # 无边框
        self.window.attributes('-topmost', True)  # 置顶
        self.window.attributes('-alpha', self.opacity)  # 透明度

        # 计算位置
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()

        if self.position == "top_center":
            x = (screen_width - self.width) // 2
            y = 50
        elif self.position == "bottom_center":
            x = (screen_width - self.width) // 2
            y = screen_height - self.height - 100
        else:
            x = 100
            y = 100

        self.window.geometry(f"+{x}+{y}")

        # 创建字幕标签
        subtitle_font = font.Font(family="Microsoft YaHei", size=self.font_size, weight="bold")
        self.label = tk.Label(
            self.window,
            text="等待字幕...",
            font=subtitle_font,
            bg=self.bg_color,
            fg=self.text_color,
            wraplength=self.width - 20,
            justify="center"
        )
        self.label.pack(expand=True, fill='both', padx=10, pady=10)

        # 绑定事件
        self.window.bind('<Button-1>', self._start_drag)
        self.window.bind('<B1-Motion>', self._on_drag)
        self.window.bind('<Double-Button-1>', self._toggle_font_size)
        self.window.bind('<Escape>', self._toggle_visibility)

        logger.info(f"✅ 字幕窗口已创建: {self.width}x{self.height} @ ({x}, {y})")

    def _start_drag(self, event):
        """开始拖动"""
        self.drag_x = event.x
        self.drag_y = event.y

    def _on_drag(self, event):
        """拖动过程"""
        x = self.window.winfo_x() + event.x - self.drag_x
        y = self.window.winfo_y() + event.y - self.drag_y
        self.window.geometry(f"+{x}+{y}")

    def _toggle_font_size(self, event):
        """切换字体大小"""
        self.is_large_font = not self.is_large_font
        new_size = 32 if self.is_large_font else 24

        subtitle_font = font.Font(family="Microsoft YaHei", size=new_size, weight="bold")
        self.label.configure(font=subtitle_font)

        logger.info(f"🔤 字体大小切换: {new_size}pt")

    def _toggle_visibility(self, event):
        """切换可见性"""
        self.is_visible = not self.is_visible

        if self.is_visible:
            self.window.deiconify()
        else:
            self.window.withdraw()

        logger.info(f"👁️  字幕窗口: {'显示' if self.is_visible else '隐藏'}")

    def update_subtitle(self, text: str):
        """
        更新字幕文本

        Args:
            text: 字幕文本
        """
        if self.label:
            self.label.configure(text=text)

    def run(self):
        """运行窗口主循环"""
        self.window.mainloop()

    def destroy(self):
        """销毁窗口"""
        if self.window:
            self.window.destroy()
            logger.info("🛑 字幕窗口已关闭")
```

**线程安全考虑**:
- 字幕窗口在独立线程运行
- 使用 `window.after()` 进行线程安全的UI更新

### 3. 双通道翻译器 (`main_v2.py`)

**功能**: 管理双向翻译的主程序

**核心架构**:
```python
class DualChannelTranslator:
    """
    双通道实时翻译器 (耳机模式)

    Channel 1: 麦克风(中文) → VB-CABLE(英文) [s2s]
    Channel 2: 系统音频(英文) → 字幕窗口(中文) [s2t]
    """

    def __init__(self, config_path: str = "config.yaml"):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.is_running = False

        # 初始化组件
        self._init_components()

    def _init_components(self):
        """初始化所有组件"""

        # 1. 麦克风捕获 (复用Phase 1的AudioCapturer)
        self.mic_capturer = AudioCapturer(...)

        # 2. 系统音频捕获 (新组件)
        self.system_audio_capturer = SystemAudioCapturer(...)

        # 3. 音频播放器 (复用Phase 1的OggOpusPlayer)
        self.audio_player = OggOpusPlayer(...)

        # 4. 字幕窗口 (新组件)
        self.subtitle_window = SubtitleWindow(...)

        # 5. 两个火山引擎翻译客户端
        self.translator_zh_to_en = VolcengineTranslator(
            mode='s2s',
            source_language='zh',
            target_language='en'
        )

        self.translator_en_to_zh = VolcengineTranslator(
            mode='s2t',  # speech to text!
            source_language='en',
            target_language='zh'
        )

    async def start(self):
        """启动翻译器"""
        self.is_running = True

        # 1. 启动音频捕获
        self.mic_capturer.start()
        self.system_audio_capturer.start()

        # 2. 启动音频播放器
        self.audio_player.start()

        # 3. 启动字幕窗口(独立线程)
        subtitle_thread = threading.Thread(
            target=self.subtitle_window.run,
            daemon=True
        )
        subtitle_thread.start()

        # 4. 连接火山引擎
        await self.translator_zh_to_en.connect()
        await self.translator_zh_to_en.start_session()

        await self.translator_en_to_zh.connect()
        await self.translator_en_to_zh.start_session()

        # 5. 启动主循环
        await self._main_loop()

    async def _main_loop(self):
        """
        主循环 - 双通道并发执行

        无需冲突检测,两个通道完全独立!
        """

        async def channel1_loop():
            """
            Channel 1: 麦克风 → 英文语音
            """
            logger.info("📤 Channel 1 已启动: 中文 → 英文")

            # 发送音频任务
            async def send_audio():
                while self.is_running:
                    chunk = self.mic_capturer.get_chunk(timeout=0.1)
                    if chunk:
                        await self.translator_zh_to_en.send_audio(chunk)
                    await asyncio.sleep(0.01)

            # 接收结果任务
            async def receive_result():
                while self.is_running:
                    result = await self.translator_zh_to_en.receive_result()

                    if result and result.audio_data:
                        # 播放英文音频到VB-CABLE
                        self.audio_player.play(result.audio_data)
                        logger.info(f"🔊 英文音频: {len(result.audio_data)} bytes")

                    if result and result.text:
                        logger.info(f"📝 英文文本: {result.text}")

            await asyncio.gather(send_audio(), receive_result())

        async def channel2_loop():
            """
            Channel 2: 系统音频 → 中文字幕
            """
            logger.info("📤 Channel 2 已启动: 英文 → 中文")

            # 发送音频任务
            async def send_audio():
                while self.is_running:
                    chunk = self.system_audio_capturer.get_chunk(timeout=0.1)
                    if chunk:
                        await self.translator_en_to_zh.send_audio(chunk)
                    await asyncio.sleep(0.01)

            # 接收结果任务
            async def receive_result():
                while self.is_running:
                    result = await self.translator_en_to_zh.receive_result()

                    if result and result.text:
                        # 更新字幕窗口
                        self.subtitle_window.update_subtitle(result.text)
                        logger.info(f"📝 中文字幕: {result.text}")

            await asyncio.gather(send_audio(), receive_result())

        # 并发执行两个通道
        try:
            await asyncio.gather(
                channel1_loop(),
                channel2_loop()
            )
        except asyncio.CancelledError:
            logger.info("🛑 主循环被取消")

    async def stop(self):
        """停止翻译器"""
        logger.info("🛑 正在停止翻译器...")

        self.is_running = False

        # 停止音频捕获
        self.mic_capturer.stop()
        self.system_audio_capturer.stop()

        # 停止翻译客户端
        await self.translator_zh_to_en.close()
        await self.translator_en_to_zh.close()

        # 停止音频播放器
        self.audio_player.stop()

        # 关闭字幕窗口
        self.subtitle_window.destroy()

        logger.info("✅ 翻译器已停止")
```

**关键点**:
- ✅ **两个WebSocket连接**完全独立,无需协调
- ✅ **两个async循环**并发执行,互不干扰
- ✅ **简化的架构**,无状态机,无冲突检测
- ✅ **耳机物理隔离**保证无回声

---

## ⚙️ 配置文件更新

### `config.yaml` 新结构

```yaml
# 火山引擎配置
volcengine:
  ws_url: "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
  app_key: "你的app_key"
  access_key: "你的access_key"
  resource_id: "volc.service_type.10053"

# 音频配置
audio:
  # 麦克风配置 (用户说话)
  microphone:
    device: "麦克风"
    sample_rate: 16000
    channels: 1
    chunk_size: 1600  # 100ms @ 16kHz

  # 系统音频配置 (对方说话)
  system_audio:
    device: "立体声混音"  # 首选
    fallback_device: "CABLE Output"  # 备选
    sample_rate: 16000
    channels: 1
    chunk_size: 1600

  # VB-CABLE输出配置
  vbcable_output:
    device: "CABLE Input"
    sample_rate: 24000
    use_ffmpeg: true
    monitor_device: null  # 耳机模式不需要监听
    enable_monitor: false

# 翻译通道配置
channels:
  # Channel 1: 中文 → 英文 (语音)
  zh_to_en:
    mode: "s2s"  # speech to speech
    source_language: "zh"
    target_language: "en"
    enabled: true

  # Channel 2: 英文 → 中文 (文本)
  en_to_zh:
    mode: "s2t"  # speech to text
    source_language: "en"
    target_language: "zh"
    enabled: true

# 字幕窗口配置
subtitle_window:
  enabled: true
  width: 800
  height: 100
  font_size: 24
  bg_color: "#000000"
  text_color: "#FFFFFF"
  opacity: 0.8
  position: "top_center"

# 日志配置
logging:
  level: "INFO"
  file: "realtime_translator_v2.log"
  max_size: 10485760  # 10MB
  backup_count: 5

# 性能配置
performance:
  max_latency: 6.0  # 最大端到端延迟(秒)
  audio_queue_size: 100
  result_queue_size: 100
```

---

## 📅 实施计划

### Week 1: 核心组件开发

#### Day 1-2: 系统音频捕获
- [ ] 实现 `core/system_audio_capture.py`
- [ ] 实现 `SystemAudioCapturer` 类
- [ ] 测试立体声混音捕获
- [ ] 测试CABLE Output降级
- [ ] 验证音频质量 (16kHz Mono)
- [ ] 单元测试

#### Day 3-4: 悬浮字幕窗口
- [ ] 实现 `gui/subtitle_window.py`
- [ ] 实现 `SubtitleWindow` 类
- [ ] Tkinter界面开发
- [ ] 交互功能 (拖动, 双击, ESC)
- [ ] 线程安全测试
- [ ] UI测试

#### Day 5: 火山引擎 s2t 模式测试
- [ ] 测试 s2t 模式 (speech to text)
- [ ] 验证英文 → 中文翻译质量
- [ ] 测试文本输出格式
- [ ] 延迟测试

### Week 2: 集成和优化

#### Day 1-3: 双通道翻译器
- [ ] 创建 `main_v2.py`
- [ ] 实现 `DualChannelTranslator` 类
- [ ] 双WebSocket连接管理
- [ ] 双通道并发架构
- [ ] 字幕窗口集成
- [ ] 错误处理和重连

#### Day 4-5: 集成测试
- [ ] 端到端功能测试
- [ ] 双向翻译测试
- [ ] 延迟测试
- [ ] 稳定性测试 (2小时+)
- [ ] 性能测试 (CPU/内存)

### Week 3: 优化和发布

#### Day 1-2: 用户体验优化
- [ ] 字幕显示优化
- [ ] 日志完善
- [ ] 统计信息优化
- [ ] 配置文件验证

#### Day 3-4: 文档和测试
- [ ] 更新 README.md
- [ ] 编写 Phase 2 使用指南
- [ ] 创建测试脚本
- [ ] 录制演示视频

#### Day 5: v2.0.0 Release
- [ ] 代码审查
- [ ] 性能基准测试
- [ ] Release 打包
- [ ] 发布说明

---

## 🧪 测试策略

### 单元测试

```python
# tests/test_system_audio_capture.py
def test_system_audio_device_discovery():
    """测试系统音频设备发现"""
    capturer = SystemAudioCapturer()
    device_index = capturer._find_device()
    assert device_index >= 0

def test_system_audio_capture_quality():
    """测试音频捕获质量"""
    capturer = SystemAudioCapturer()
    capturer.start()
    chunk = capturer.get_chunk(timeout=1.0)
    assert chunk is not None
    assert len(chunk) == 1600 * 2  # 16-bit samples
    capturer.stop()

# tests/test_subtitle_window.py
def test_subtitle_window_creation():
    """测试字幕窗口创建"""
    window = SubtitleWindow()
    window.create()
    assert window.window is not None
    assert window.label is not None
    window.destroy()

def test_subtitle_text_update():
    """测试字幕文本更新"""
    window = SubtitleWindow()
    window.create()
    window.update_subtitle("测试字幕")
    assert window.label.cget("text") == "测试字幕"
    window.destroy()
```

### 集成测试

```python
# tests/test_dual_channel_integration.py
async def test_dual_channel_translation():
    """测试双通道翻译"""
    translator = DualChannelTranslator()

    # 启动翻译器
    start_task = asyncio.create_task(translator.start())

    # 运行30秒
    await asyncio.sleep(30)

    # 停止翻译器
    await translator.stop()

    # 验证统计
    assert translator.stats['zh_to_en_count'] > 0
    assert translator.stats['en_to_zh_count'] > 0

# tests/test_end_to_end.py
async def test_full_workflow_with_headphones():
    """测试完整工作流(耳机模式)"""
    # 1. 模拟用户说中文
    # 2. 验证英文输出到VB-CABLE
    # 3. 模拟系统音频(对方英文)
    # 4. 验证中文字幕显示
    pass
```

### 性能测试

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| CPU使用率 | <25% | 双通道运行30分钟,监控CPU |
| 内存使用 | <500MB | 长时间运行,监控内存 |
| 翻译延迟 | <6秒 | 端到端计时,发音到字幕 |
| 字幕刷新 | <200ms | GUI响应时间测试 |
| 稳定运行 | >2小时 | 压力测试,无崩溃 |

---

## 📊 成功指标

### 功能指标
- ✅ 双向翻译成功率 >90%
- ✅ 端到端延迟 <6秒
- ✅ 系统稳定运行 >2小时
- ✅ 字幕准确率 >85%

### 性能指标
- ✅ CPU占用 <25%
- ✅ 内存使用 <500MB
- ✅ 字幕更新延迟 <200ms
- ✅ 无音频丢失

### 用户体验指标
- ✅ 配置时间 <10分钟
- ✅ 学习成本 <15分钟 (比Phase 1简单,无需配置阈值)
- ✅ 用户满意度 >85%
- ✅ 错误率 <3%

---

## ⚠️ 风险评估

### 技术风险

| 风险 | 概率 | 影响 | 缓解策略 |
|------|------|------|---------|
| 立体声混音不可用 | 中 | 高 | 降级到CABLE Output,提供配置指南 |
| 双WebSocket不稳定 | 中 | 高 | 独立重连机制,错误恢复 |
| 字幕窗口卡顿 | 低 | 中 | 独立线程,异步更新,性能优化 |
| s2t模式翻译质量低 | 低 | 中 | 测试验证,必要时切换到s2s |
| 性能不足 | 低 | 中 | 优化音频处理,使用多线程 |

### 用户体验风险

| 风险 | 概率 | 影响 | 缓解策略 |
|------|------|------|---------|
| 用户不愿使用耳机 | 低 | 中 | 提供Phase 4扬声器模式选项 |
| 配置复杂 | 低 | 低 | 自动检测,一键配置,详细文档 |
| 学习成本高 | 低 | 低 | 详细文档,视频教程,简化UI |
| 延迟过高 | 低 | 高 | 优化处理流程,网络检测 |

---

## 📚 依赖和前置条件

### 软件依赖
- ✅ Python 3.8+
- ✅ 火山引擎 API 访问权限
- ✅ VB-CABLE (可选,用于Zoom集成)
- ✅ FFmpeg (用于音频解码)

### 硬件依赖
- ✅ 耳机/耳麦 (必需!)
- ✅ 麦克风 (可以是耳麦的麦克风)
- ✅ 稳定的网络连接

### 系统配置
- ✅ Windows 启用"立体声混音" (或安装VB-CABLE)
- ✅ Zoom 配置:
  - 麦克风: CABLE Output (VB-Audio Virtual Cable)
  - 扬声器: 默认扬声器/耳机

---

## 🎯 下一步行动

### 立即开始 (本周)
1. ✅ 完成 Phase 2 简化规划文档
2. 🎯 设置开发环境
3. 📋 创建详细任务清单
4. 🧪 准备测试环境

### 短期目标 (Week 1)
1. 实现 `SystemAudioCapturer`
2. 实现 `SubtitleWindow`
3. 测试火山引擎 s2t 模式

### 中期目标 (Week 2-3)
1. 实现 `DualChannelTranslator`
2. 集成测试
3. 发布 v2.0.0

---

## 📖 参考资料

### 技术文档
- [火山引擎同声传译2.0 API](https://www.volcengine.com/docs/6561/80816)
- [sounddevice 文档](https://python-sounddevice.readthedocs.io/)
- [Tkinter 教程](https://docs.python.org/3/library/tkinter.html)
- [asyncio 文档](https://docs.python.org/3/library/asyncio.html)

### 音频处理
- [Windows 立体声混音设置](https://support.microsoft.com/zh-cn/windows/windows-10-%E4%B8%AD%E7%9A%84%E5%BD%95%E9%9F%B3%E9%80%89%E9%A1%B9-b1189376-ae04-7dea-bc50-2c2a7c9a1ebb)
- [VB-CABLE 官方文档](https://vb-audio.com/Cable/index.htm)

---

**文档版本**: 2.0 (简化版 - 耳机模式)
**创建日期**: 2025-01-XX
**作者**: Claude Code + 用户协作
**状态**: ✅ 已批准,待实施
**Phase**: Phase 2 - 双向翻译 (耳机模式)
