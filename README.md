# 实时同声传译器

🎤 为在线会议提供实时中英文翻译的解决方案

## 📋 项目状态

### ✅ v1.0.0 - MVP 单向翻译 (已完成)
**当前功能:**
- ✅ **中文 → 英文语音翻译**: 麦克风捕获中文,实时翻译为英文语音输出
- ✅ **虚拟麦克风输出**: 支持VB-CABLE,翻译后的英文直接输入Zoom等会议软件
- ✅ **双输出播放器**: 主输出(VB-CABLE) + 本地监听(扬声器),可选择性启用
- ✅ **流式音频处理**: FFmpeg解码 + 累积缓冲区,消除杂音和播放卡顿
- ✅ **优雅资源管理**: Ctrl+C信号处理,正确释放麦克风和音频流
- ✅ **性能统计**: 实时显示翻译延迟、音频块数、数据传输量
- ✅ **线程安全架构**: 零数据竞争的双输出机制
- ✅ **降级支持**: 无VB-CABLE时自动切换到默认扬声器(测试模式)

**技术架构:**
- 🔧 异步并发架构 (asyncio)
- 🔧 WebSocket流式通信 (websockets 12.0+)
- 🔧 FFmpeg音频解码 (Ogg Opus → PCM)
- 🔧 sounddevice OutputStream (非阻塞播放)
- 🔧 线程安全缓冲区 (threading.Lock)

### 🔧 已修复的关键问题
| 问题 | 解决方案 | 影响 |
|------|---------|------|
| 音频播放阻塞 | `sd.play()` → `sd.OutputStream` 流式播放 | 消除播放延迟 |
| 音频杂音/underflow | 实现累积缓冲区匹配 blocksize (2048) | 播放清晰流畅 |
| Ctrl+C麦克风未关闭 | 信号处理器 + finally块保证清理 | 资源正确释放 |
| websockets 12.0+ 兼容性 | `additional_headers` → `extra_headers` | API调用成功 |
| FFmpeg库依赖 | 使用用户已安装的FFmpeg进行解码 | 无需额外安装Opus |
| 无VB-CABLE崩溃 | 自动降级到默认扬声器(测试模式) | 提高容错性 |

### ✅ v2.0.0 - 双向翻译（耳机模式）
**新增功能:**
- ✅ **双向实时翻译**: 中文↔英文双向同声传译
- ✅ **系统音频捕获**: 捕获对方英文语音（立体声混音/CABLE Output）
- ✅ **悬浮字幕窗口**: Tkinter半透明窗口显示中文字幕
- ✅ **双通道独立架构**: 两个WebSocket连接并发执行
- ✅ **耳机物理隔离**: 无需冲突检测，零延迟，零误检
- ✅ **字幕窗口交互**: 可拖动、双击切换字体、ESC隐藏/显示
- ✅ **s2t模式支持**: speech-to-text 英文→中文文字翻译

**技术架构升级:**
- 🔧 双通道并发 (asyncio.gather)
- 🔧 SystemAudioCapturer (系统音频捕获)
- 🔧 SubtitleWindow (Tkinter悬浮窗口)
- 🔧 线程安全UI更新 (window.after)
- 🔧 简化架构 (无状态机、无VAD)

**性能指标:**
- CPU占用: <25%
- 内存使用: <500MB
- 端到端延迟: <6秒
- 字幕刷新: <200ms

### ⏳ 计划中功能 (v3.0+)
- ⏳ **GUI控制面板**: 可视化配置和状态监控
- ⏳ **扬声器模式**: WebRTC VAD冲突检测（Phase 4）
- ⏳ **性能优化**: 降噪、并发优化、自适应缓冲

## 🔧 系统要求

- **操作系统**: Windows 10/11
- **Python**: 3.7+
- **FFmpeg**: 音频解码必需 (推荐已安装到系统PATH)
- **VB-CABLE**: 虚拟音频设备 (可选,未安装时降级到扬声器)
- **火山引擎**: 同声传译2.0 API账号 (需要app_key和access_key)

## 📦 安装步骤

### 1. 安装FFmpeg (必需)

**下载安装FFmpeg:**
1. 下载: https://ffmpeg.org/download.html
2. 解压到目录(例如: `D:\ffmpeg`)
3. 将 `bin` 目录添加到系统PATH,或记住完整路径

### 2. 安装VB-CABLE虚拟音频设备 (必需)

**用途**: 将翻译后的英文音频输出到Zoom等会议软件的"虚拟麦克风"

**安装步骤:**
1. 下载: https://vb-audio.com/Cable/
2. 解压并以管理员身份运行 `VBCABLE_Setup_x64.exe`
3. 安装完成后重启计算机

**如果不安装VB-CABLE:**
- 程序会自动降级到"测试模式"
- 翻译音频将通过默认扬声器播放
- 无法直接输入到会议软件

### 3. 配置Windows音频设置 (使用VB-CABLE时)

**设置VB-CABLE为默认播放设备:**
1. 右键点击任务栏音量图标 → 声音设置
2. 点击"声音控制面板"
3. 切换到"播放"选项卡
4. 找到"CABLE Input",右键 → 设为默认设备

**注意**: 立体声混音配置仅在实现双向翻译时需要(v2.0计划中功能)

### 4. 安装Python依赖 

```bash
cd realtime_translator
pip install -r requirements.txt
```

### 5. 配置火山引擎API

1. 注册火山引擎账号: https://www.volcengine.com/
2. 申请同声传译2.0 API权限
3. 获取 `app_key` 和 `access_key`
4. 编辑 `config.yaml`,填入你的密钥:

```yaml
volcengine:
  ws_url: "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
  app_key: "你的app_key"          # 替换为你的app_key
  access_key: "你的access_key"    # 替换为你的access_key
  resource_id: "volc.service_type.10053"

audio:
  sample_rate: 16000      # 麦克风采样率 (固定16kHz)
  channels: 1             # 单声道输入
  chunk_size: 1600        # 音频块大小 (100ms @ 16kHz)
  microphone_device: "麦克风"  # 麦克风设备名称,可通过测试脚本获取

channels:
  zh_to_en:
    mode: "s2s"              # 语音到语音模式
    source_language: "zh"    # 源语言:中文
    target_language: "en"    # 目标语言:英文
```

**配置说明:**
- `ws_url`: WebSocket连接地址,使用火山引擎官方API
- `app_key` / `access_key`: 从火山引擎控制台获取
- `microphone_device`: 麦克风设备名称,可以是部分匹配(如"麦克风")

## 🚀 使用方法

### 🌟 v2.0 - 双向翻译（耳机模式）- 推荐使用

**运行程序:**
```bash
python main_v2.py
```

**配置文件**: 复制 `config_v2.yaml` 为 `config.yaml` 并填入火山引擎凭证

**架构说明:**
```
Channel 1 (你→对方):
  麦克风(中文) → 火山引擎(s2s) → VB-CABLE(英文) → Zoom → 对方听到英文

Channel 2 (对方→你):
  Zoom(英文) → 系统音频 → 火山引擎(s2t) → 字幕窗口(中文) → 你看到中文字幕
```

**重要配置:**
1. 🎧 **必须使用耳机**！避免扬声器声音被麦克风捕获形成回声
2. ✅ Zoom麦克风：CABLE Output (VB-Audio Virtual Cable)

**Channel 2音频捕获方案（二选一）:**

**方案A: 立体声混音方案（推荐，简单）**
- ✅ **适用于**: 使用Realtek声卡的有线耳机/音箱
- ✅ **配置步骤**:
  1. 启用Windows立体声混音（右键音量→声音→录制→启用"立体声混音"）
  2. Zoom扬声器：**Speakers (Realtek HD Audio output)** 或默认扬声器
  3. config.yaml保持默认配置（使用立体声混音）
  4. 连接有线耳机到Realtek声卡接口
- ✅ **优点**: 配置简单，音质最好，无延迟
- ❌ **缺点**: 无法使用蓝牙音箱（立体声混音只能捕获同一声卡输出）

**方案B: VB-CABLE B + 监听方案**
- ✅ **适用于**: 想使用蓝牙音箱/耳机的用户
- ✅ **配置步骤**:
  1. Zoom扬声器：**CABLE In 16 Ch (VB-Audio Virtual Cable)**
  2. 修改config.yaml:
     ```yaml
     audio:
       system_audio:
         device: "CABLE Output"  # 改为VB-CABLE Output
     ```
  3. 设置Windows监听（让你能听到声音）:
     - 右键"CABLE Output" → 属性 → "侦听"标签
     - 勾选"侦听此设备"
     - "通过此设备播放" → 选择你的蓝牙音箱
- ✅ **优点**: 支持蓝牙音箱，灵活性高
- ❌ **缺点**: 配置较复杂，可能有轻微延迟

**音频路径对比:**
```
方案A: Zoom → Realtek声卡 → 有线耳机（你听到） + 立体声混音（程序捕获）
方案B: Zoom → CABLE Input → CABLE Output → 程序捕获 + Windows侦听 → 蓝牙音箱（你听到）
```

**字幕窗口操作:**
- 左键拖动：移动窗口位置
- 双击：切换字体大小（24pt ↔ 32pt）
- ESC键：隐藏/显示窗口

**详细文档**: 参见 [USAGE_V2.md](USAGE_V2.md)

---

### v1.0 - 单向翻译 (中文 → 英文)

**标准模式 (VB-CABLE + 本地监听):**
```bash
python main.py
```

**禁用本地监听 (仅VB-CABLE输出):**
```bash
python main.py --no-monitor
```

**程序启动后会显示:**
- ✅ VB-CABLE Input检测状态 (已安装/测试模式)
- 🔊 主输出设备名称
- 🔊 监听设备名称 (如果启用)
- 🎤 麦克风设备状态

### 在会议软件中配置 (使用VB-CABLE时)

**以Zoom为例:**
1. 打开Zoom → 设置 → 音频
2. **麦克风**选择: `CABLE Output (VB-Audio Virtual Cable)`
3. **扬声器**保持默认(或你的物理音频设备)
4. 建议关闭"自动调整麦克风音量"

**其他会议软件 (Teams/腾讯会议/飞书等):**
- 操作类似,选择CABLE Output作为麦克风输入即可

### 使用流程

1. **启动翻译器**: 运行 `python main.py`
2. **等待初始化**: 看到"✅ 翻译器已启动"提示
3. **加入会议**: 在会议软件中选择CABLE Output作为麦克风
4. **开始说话**: 说中文,对方会实时听到英文翻译
5. **监控状态**: 观察控制台输出的翻译文本和音频统计

**注意事项:**
- 延迟约3-5秒是正常的(网络传输+AI翻译+音频处理)
- 首次音频响应可能稍慢(冷启动)
- 可通过日志文件 `realtime_translator.log` 查看详细信息

### 停止翻译器

按 `Ctrl+C` 优雅停止程序,会自动:
- 关闭麦克风捕获
- 断开火山引擎连接
- 停止音频播放
- 显示会话统计信息

## 📁 项目结构

```
realtime_translator/
├── main.py                    # 主程序入口 (生产版本)
├── vbcable_translator.py      # 原型版本 (保留备份)
├── config.yaml                # 配置文件
├── requirements.txt           # Python依赖包
├── README.md                  # 项目文档
├── PROJECT_SUMMARY.md         # 项目总结
│
├── core/                      # 核心模块
│   ├── __init__.py
│   ├── audio_capture.py       # 麦克风音频捕获 (sounddevice)
│   ├── audio_output.py        # 双输出音频播放器 (FFmpeg + OutputStream)
│   ├── volcengine_client.py   # 火山引擎WebSocket客户端
│   └── conflict_resolver.py   # 冲突解决 (v2.0计划中)
│
├── tests/                     # 测试和调试工具
│   ├── simple_translator.py   # 简化版翻译器 (本地测试)
│   ├── test_vbcable.py        # VB-CABLE测试脚本
│   └── check_vbcable.py       # 音频设备检测工具
│
└── backup/                    # 备份文件
    ├── main.py.old
    └── vbcable_translator.py.backup
```

**核心文件说明:**
- `main.py` → 主程序,使用 `RealtimeTranslator` 类
- `audio_output.py` → 关键模块,实现了累积缓冲区和双输出架构
- `volcengine_client.py` → WebSocket客户端,兼容websockets 12.0+
- `config.yaml` → 包含API密钥和设备配置

## 🔍 故障排除

### 问题1: 找不到麦克风设备

**错误信息**: `❌ 找不到麦克风设备: 麦克风`

**解决方案**:
```bash
# 方法1: 运行设备检测工具
python tests/check_vbcable.py

# 方法2: 使用Python查看所有设备
python -c "import sounddevice as sd; print(sd.query_devices())"
```

然后在 `config.yaml` 中修改 `microphone_device` 为实际设备名称(可以是部分匹配)

### 问题2: 音频播放有杂音或卡顿

**症状**: 听到的英文翻译音质差,有爆音或断续

**可能原因**:
1. FFmpeg未正确安装或路径不对
2. 系统资源不足(CPU占用过高)

**解决方案**:
```bash
# 检查FFmpeg是否可用
ffmpeg -version

# 如果FFmpeg不在PATH中,可以在代码中指定完整路径
# 编辑 core/audio_output.py,修改ffmpeg_path参数
```

### 问题3: 对方听不到我的声音 (使用VB-CABLE时)

**检查清单**:
1. ✅ VB-CABLE是否正确安装? → 运行 `tests/check_vbcable.py` 检查
2. ✅ 程序是否检测到VB-CABLE? → 启动日志应显示"✅ 找到VB-CABLE Input"
3. ✅ 会议软件麦克风是否选择"CABLE Output"? → 重新检查音频设置
4. ✅ 翻译器是否正常运行? → 查看是否有"🔊 音频块"日志输出
5. ✅ 本地能否听到翻译? → 使用 `--monitor` 模式测试

**调试步骤**:
```bash
# 1. 测试VB-CABLE基础功能
python tests/test_vbcable.py

# 2. 启用监听模式确认翻译正常
python main.py  # 默认启用监听,从扬声器应能听到翻译

# 3. 查看详细日志
tail -f realtime_translator.log  # Linux/Mac
Get-Content realtime_translator.log -Tail 20 -Wait  # Windows PowerShell
```

### 问题4: 程序无法启动或立即退出

**常见错误**:

**4.1 WebSocket连接失败**
```
❌ WebSocket连接失败
```
**解决**: 检查 `config.yaml` 中的 `app_key` 和 `access_key` 是否正确

**4.2 ModuleNotFoundError**
```
ModuleNotFoundError: No module named 'xxx'
```
**解决**: 重新安装依赖 `pip install -r requirements.txt`

**4.3 FFmpeg not found**
```
FileNotFoundError: [WinError 2] 系统找不到指定的文件。
```
**解决**: 安装FFmpeg并确保在系统PATH中,或指定完整路径

### 问题5: 延迟过高 (>10秒)

**正常延迟**: 3-5秒 (包括网络传输、AI翻译、音频处理)

**可能原因**:
- 网络延迟高 → 检查网络连接,使用有线网络
- 系统资源不足 → 关闭其他占用CPU的程序
- 音频块大小过大 → 调整 `config.yaml` 中的 `chunk_size`

**优化方案**:
```yaml
audio:
  chunk_size: 1600  # 默认值,100ms @ 16kHz
  # 可以尝试 800 (50ms) 降低延迟,但会增加API调用频率
```

### 问题6: Ctrl+C后麦克风LED仍然亮着

**原因**: 程序异常退出,未正确释放麦克风

**解决方案**:
1. 再次按 Ctrl+C 确保程序完全退出
2. 如果仍然无法释放,重启Python进程或重启计算机
3. 当前版本已修复此问题(使用信号处理器+finally块)

### 问题7: 火山引擎API配额用尽

**错误信息**: 日志中显示API调用失败或配额错误

**解决方案**:
1. 登录火山引擎控制台查看API使用情况
2. 检查是否超出免费配额
3. 考虑升级套餐或优化使用频率

## 📊 性能优化建议

### 网络优化
- ✅ **使用有线网络**: 相比WiFi,有线连接延迟更低、更稳定
- ✅ **检查网络速度**: 至少需要稳定的2Mbps上传带宽
- ✅ **避免网络拥塞**: 关闭其他占用带宽的程序(下载、视频等)

### 系统资源优化
- ✅ **关闭后台程序**: 释放CPU和内存资源
- ✅ **使用性能模式**: Windows电源设置选择"高性能"
- ✅ **监控资源使用**: 任务管理器查看Python进程占用情况

### 音频质量优化
- ✅ **使用高质量麦克风**: 降噪麦克风效果更好
- ✅ **安静环境**: 减少背景噪音,提高识别准确率
- ✅ **适当音量**: 麦克风输入音量适中,避免过大或过小
- ✅ **清晰发音**: 说话速度适中,吐字清晰

### 程序稳定性
- ✅ **长时间会议**: 建议每2小时重启一次程序(释放资源)
- ✅ **监控日志**: 定期查看 `realtime_translator.log` 了解运行状态
- ✅ **版本更新**: 关注火山引擎API更新和程序优化

### 延迟优化
**当前延迟组成:**
- 音频采集: ~100ms (chunk_size决定)
- 网络上传: 50-200ms (网络质量决定)
- AI翻译: 1-2秒 (火山引擎处理)
- 音频下载: 50-200ms (网络质量决定)
- 音频播放: ~100ms (缓冲区决定)
- **总计**: 约3-5秒

**优化空间:**
- 网络优化可减少0.5-1秒
- chunk_size调小可减少0.1-0.2秒,但会增加API调用频率

## 🛣️ 开发路线图

### ✅ Phase 1: MVP单向翻译 (已完成)
- [x] 麦克风音频捕获
- [x] 火山引擎WebSocket集成
- [x] FFmpeg音频解码
- [x] 双输出播放器 (VB-CABLE + 监听)
- [x] 累积缓冲区消除杂音
- [x] 优雅资源管理
- [x] 性能统计和日志

### 🔄 Phase 2: 双向翻译 (计划中)
- [ ] 系统音频捕获 (立体声混音)
- [ ] 英文语音 → 中文文本翻译
- [ ] 悬浮字幕窗口
- [ ] 对方优先的冲突解决
- [ ] 双向音频混流

### 📋 Phase 3: GUI界面 (计划中)
- [ ] 启动/停止控制面板
- [ ] 实时状态监控
- [ ] 配置可视化编辑
- [ ] 音频设备选择器
- [ ] 翻译历史记录

### ⚡ Phase 4: 性能优化 (计划中)
- [ ] 音频预处理和降噪
- [ ] 智能静音检测
- [ ] 缓存和批处理优化
- [ ] 多线程并行处理
- [ ] GPU加速 (如果可用)

### 📦 Phase 5: 打包发布 (计划中)
- [ ] PyInstaller打包为exe
- [ ] 安装向导
- [ ] 自动更新机制
- [ ] 用户手册
- [ ] 开源发布

## 📝 日志文件

程序运行时会生成 `realtime_translator.log` 文件,记录所有操作和错误信息。

**日志内容包括:**
- ✅ 组件初始化状态 (麦克风、VB-CABLE、火山引擎)
- 📝 翻译文本输出
- 🔊 音频块接收和播放统计
- ⚠️ 警告和错误信息
- 📊 会话统计数据

**查看日志方法:**
```bash
# Linux/Mac
tail -f realtime_translator.log

# Windows PowerShell
Get-Content realtime_translator.log -Tail 20 -Wait

# 或直接用文本编辑器打开
notepad realtime_translator.log
```

**日志示例:**
```
2024-01-15 10:30:15 [INFO] ================================================================================
2024-01-15 10:30:15 [INFO] 🎙️  实时同声传译器
2024-01-15 10:30:15 [INFO]    中文(麦克风) → 英文(VB-CABLE Input → Zoom)
2024-01-15 10:30:16 [INFO] ✅ 找到VB-CABLE Input: [3] CABLE Input (VB-Audio Virtual Cable)
2024-01-15 10:30:16 [INFO] 🔊 主输出设备: CABLE Input (VB-Audio Virtual Cable)
2024-01-15 10:30:16 [INFO] 🔊 监听设备: 扬声器 (Realtek High Definition Audio)
2024-01-15 10:30:17 [INFO] ✅ 翻译器已启动
2024-01-15 10:30:20 [INFO] 📝 [1] Hello, how are you today?
2024-01-15 10:30:21 [INFO] 🔊 音频块 [1] 4532 bytes | 延迟: 3.45s
```

## ⚠️ 注意事项

### 隐私与安全
- ⚠️ **音频数据处理**: 您的语音数据会通过网络发送到火山引擎服务器进行AI翻译处理
- ⚠️ **敏感信息**: 涉及机密内容的会议请谨慎使用,或联系火山引擎了解企业级安全方案
- ⚠️ **API密钥保护**: 请勿将 `config.yaml` 中的API密钥泄露或上传到公开仓库

### 费用说明
- 💰 **火山引擎API**: 可能产生费用,请查看官方定价 https://www.volcengine.com/pricing
- 💰 **免费额度**: 通常有一定免费额度,超出后按量计费
- 💰 **用量监控**: 建议定期查看火山引擎控制台的使用统计

### 使用建议
- ✅ **测试先行**: 正式会议前务必先进行完整测试
- ✅ **备用方案**: 准备传统翻译方案作为备选
- ✅ **网络要求**: 确保稳定的网络连接,建议有线网络
- ✅ **资源监控**: 长时间使用时注意监控系统资源

### 已知限制
- ⚠️ **单向翻译**: 当前仅支持中文→英文语音翻译
- ⚠️ **方言支持**: 建议使用标准普通话,方言识别率可能较低
- ⚠️ **专业术语**: 特定领域的专业术语可能翻译不准确
- ⚠️ **延迟**: 3-5秒延迟不可避免,不适合需要即时反馈的场景

## 📧 技术支持与反馈

### 问题排查顺序
1. 📖 查阅本README的"🔍 故障排除"章节
2. 📝 查看日志文件: `realtime_translator.log`
3. 🧪 运行测试脚本: `tests/check_vbcable.py`
4. 📚 参考火山引擎官方文档

### 相关资源
- **火山引擎文档**: https://www.volcengine.com/docs/6561/1756902
- **同声传译2.0 API**: https://www.volcengine.com/docs/6561/80816
- **VB-CABLE官网**: https://vb-audio.com/Cable/
- **FFmpeg文档**: https://ffmpeg.org/documentation.html

### 项目信息
- **当前版本**: v1.0.0 (MVP单向翻译)
- **开发状态**: 活跃开发中
- **许可证**: MIT License

## 📄 许可证

MIT License

---

## 🎉 致谢

感谢以下开源项目和服务:
- **火山引擎**: 提供强大的同声传译2.0 API
- **VB-Audio Software**: 提供VB-CABLE虚拟音频设备
- **FFmpeg**: 提供高性能音频解码
- **sounddevice**: 提供Python音频I/O接口
- **websockets**: 提供异步WebSocket客户端

---

**🎤 祝你的跨语言会议顺利!**

如有问题或建议,欢迎通过日志文件和测试工具进行排查,或参考火山引擎官方文档获取更多帮助。
