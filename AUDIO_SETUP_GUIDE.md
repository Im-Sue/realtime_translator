# Phase 2 音频配置方案指南

本文档提供三种音频配置方案，解决双通道同声传译系统的音频路由问题。

---

## 📊 方案对比总览

| 方案 | 复杂度 | 额外软件 | 费用 | 音质 | 延迟 | 蓝牙支持 | 推荐指数 |
|------|--------|---------|------|------|------|---------|----------|
| **方案1：立体声混音** | ⭐ 最简单 | ❌ 不需要 | 免费 | ⭐⭐⭐⭐⭐ 最好 | <5ms | ❌ 不支持 | ⭐⭐⭐⭐⭐ |
| **方案2：双虚拟设备** | ⭐⭐ 中等 | ✅ 需要 | €15或免费试用 | ⭐⭐⭐⭐ 好 | <50ms | ✅ 支持 | ⭐⭐⭐⭐ |
| **方案3：VoiceMeeter** | ⭐⭐⭐⭐ 复杂 | ✅ 需要 | 免费 | ⭐⭐⭐ 中等 | <100ms | ✅ 支持 | ⭐⭐⭐ |

### 方案选择建议

```
使用有线耳机？
    │
    ├─ YES → 方案1（立体声混音）⭐⭐⭐⭐⭐ 强烈推荐！
    │         最简单、最稳定、音质最好
    │
    └─ NO（必须用蓝牙）
        │
        ├─ 愿意付费 €15？
        │   │
        │   ├─ YES → 方案2（VB-CABLE A+B）⭐⭐⭐⭐
        │   │
        │   └─ NO → 方案2（VB-CABLE + VB-CABLE Point 免费试用）⭐⭐⭐⭐
        │
        └─ 需要专业音频控制？
            │
            ├─ YES → 方案3（VoiceMeeter）⭐⭐⭐
            │
            └─ NO → 方案2 推荐 ⭐⭐⭐⭐
```

---

## 🥇 方案1：立体声混音方案（强烈推荐）

### 适用场景
- ✅ 使用有线耳机或有线音箱
- ✅ 电脑有 Realtek 声卡（或支持立体声混音的声卡）
- ✅ 追求最佳音质和最低延迟
- ✅ 希望配置最简单

### 核心原理

利用 Windows 内置的"立体声混音"功能捕获系统音频，无需额外软件。

```
【Channel 1: 你说话 → 对方听英文】
物理麦克风
    ↓
main_v2.py Channel 1 读取
    ↓
火山引擎翻译（中文→英文）
    ↓
CABLE Input (VB-CABLE)
    ↓
CABLE Output
    ↓
Zoom 麦克风
    ↓
对方听到英文 ✅

【Channel 2: 对方说话 → 你看中文字幕】
对方说英文
    ↓
Zoom 接收
    ↓
Zoom 扬声器输出到 Realtek 声卡
    ↓
    ├─→ 物理耳机（你听到英文）✅
    │
    └─→ 立体声混音（Realtek 内部捕获）
        ↓
    main_v2.py Channel 2 读取
        ↓
    火山引擎翻译（英文→中文）
        ↓
    字幕窗口显示中文 ✅
```

---

### 配置步骤（总共5步，3分钟完成）

#### 第1步：启用立体声混音 ⏱️ 1分钟

```
1. 右键任务栏"音量"图标 → 点击"声音"

2. 切换到"录制"标签

3. 在空白处右键 → 勾选"显示已禁用的设备"

4. 找到"立体声混音"或"立体声混音 Realtek(R) Audio"
   （如果看不到，说明声卡不支持，需要用方案2）

5. 右键"立体声混音" → 点击"启用"

6. （可选）右键"立体声混音" → "设为默认设备"

7. 点击"应用"
```

#### 第2步：配置 Windows 默认音频设备 ⏱️ 1分钟

**播放设备（默认）**：
```
1. 右键"音量"图标 → "声音"

2. "播放"标签 → 找到你的物理耳机/音箱：
   - "Realtek HD Audio output"
   - "Speakers (Realtek HD Audio output)"
   - 或你的耳机名称

3. 右键该设备 → "设为默认设备"

4. 右键该设备 → "设为默认通信设备"

5. 点击"应用"
```

**录制设备（默认）**：
```
1. 切换到"录制"标签

2. 找到"CABLE Output (VB-Audio Virtual Cable)"

3. 右键 → "设为默认设备"

4. 右键 → "设为默认通信设备"

5. 点击"应用"→"确定"
```

#### 第3步：配置 Zoom 音频 ⏱️ 30秒

```
1. 打开 Zoom → 设置 → 音频

2. 麦克风：选择 "CABLE Output (VB-Audio Virtual Cable)"

3. 扬声器：选择 "Realtek HD Audio output"（或你的物理耳机）

4. 其他设置：
   ✅ 勾选"自动调整麦克风音量"
   ❌ 取消"回声消除"（使用耳机不需要）
   ❌ 取消"背景噪音抑制"（可能影响翻译音质）

5. 点击"确定"
```

#### 第4步：验证立体声混音 ⏱️ 30秒

```
1. 播放一段音乐或 YouTube 视频

2. 右键"音量"图标 → "声音" → "录制"标签

3. 观察"立体声混音 Realtek(R) Audio"

4. 应该看到绿色音量条随音乐波动 ✅

如果没有波动：
- 检查立体声混音是否已启用
- 检查播放设备是否是 Realtek 声卡
- 尝试提高音乐音量
- 如果还是不行，说明立体声混音不可用，需改用方案2
```

#### 第5步：config_v2.yaml 配置（已完成）✅

配置文件已正确设置：

```yaml
audio:
  # 麦克风配置（用户说话）
  microphone:
    device: "麦克风"  # 你的物理麦克风设备

  # 系统音频配置（对方说话）
  system_audio:
    device: "立体声混音"  # Windows 立体声混音
    fallback_device: "Microsoft 声音映射器 - Input"

  # VB-CABLE输出配置（给Zoom的英文音频）
  vbcable_output:
    device: "CABLE Input"  # VB-CABLE
```

#### 第6步：运行测试 ⏱️ 10秒

```bash
cd F:\python\simultaneous_interpretation\realtime_translator
python main_v2.py
```

**预期日志**：
```
✅ 麦克风捕获器已初始化
✅ 系统音频捕获器已初始化 (设备: 立体声混音)
✅ 音频播放器已初始化 (设备: CABLE Input)
✅ 字幕窗口已初始化
✅ Channel 1 翻译器: 中文 → 英文 (s2s)
✅ Channel 2 翻译器: 英文 → 中文 (s2t)
🔊 开始翻译...
```

---

### 配置清单（快速检查）

| 设置项 | 正确配置 | 检查状态 |
|--------|---------|---------|
| Windows 播放设备（默认） | Realtek HD Audio output | ⬜ |
| Windows 录制设备（默认） | CABLE Output | ⬜ |
| 立体声混音 | 已启用 | ⬜ |
| 立体声混音有波动 | 播放音乐时有绿色波动 | ⬜ |
| Zoom 麦克风 | CABLE Output | ⬜ |
| Zoom 扬声器 | Realtek HD Audio output | ⬜ |
| config_v2.yaml | device: "立体声混音" | ✅ |

---

### 测试流程

#### 测试 Channel 1（你说话 → 英文）

```
1. 启动 main_v2.py
2. 对着物理麦克风说中文："你好，测试"
3. 观察程序日志：
   [Channel 1] 捕获到音频块
   [Channel 1] 翻译结果: Hello, test
4. Zoom 应该把英文发送给对方
```

#### 测试 Channel 2（对方说话 → 中文字幕）

```
1. 播放英文视频/音乐，或让对方说英文
2. 你的耳机应该能听到英文 ✅
3. 观察程序日志：
   [Channel 2] 捕获到系统音频块
   [Channel 2] 翻译结果: [中文字幕]
4. 字幕窗口应该显示中文 ✅
```

---

### 优点总结

✅ **配置最简单**：只需5个步骤，3分钟完成
✅ **不需要额外软件**：Windows 内置功能
✅ **音质最好**：直接从声卡硬件捕获，无损音质
✅ **延迟最低**：<5ms 硬件级延迟
✅ **最稳定**：没有额外软件层，减少故障点
✅ **完全免费**：无需购买额外软件

---

### 缺点总结

❌ **不支持蓝牙**：立体声混音只能捕获同一声卡的输出，无法捕获蓝牙音频
❌ **需要 Realtek 声卡**：部分电脑可能不支持立体声混音功能

---

### 故障排除

#### 问题1：找不到"立体声混音"

**可能原因**：
- 声卡驱动未安装或过时
- 声卡不支持立体声混音功能

**解决方法**：
1. 更新 Realtek 声卡驱动
2. 如果还是找不到，说明硬件不支持，改用方案2

---

#### 问题2：立体声混音没有波动

**可能原因**：
- 播放设备不是 Realtek 声卡
- 立体声混音音量被静音
- 音频输出到其他设备（如蓝牙）

**解决方法**：
1. 确认 Windows 播放设备是 Realtek 声卡
2. 右键"立体声混音"→"属性"→"级别"→检查音量
3. 关闭蓝牙，使用有线耳机

---

#### 问题3：程序日志显示"找不到设备"

**可能原因**：
- 设备名称不匹配
- 设备未启用

**解决方法**：
```bash
# 运行以下命令查看所有音频设备名称
cd F:\python\simultaneous_interpretation\realtime_translator
python -c "import sounddevice as sd; print(sd.query_devices())"

# 找到立体声混音的确切名称，更新到 config_v2.yaml
```

---

## 🥈 方案2：双虚拟设备方案

### 适用场景
- ✅ 需要使用蓝牙耳机/音箱
- ✅ 立体声混音不可用或不稳定
- ✅ 可以接受轻微音质损失和延迟

### 核心原理

使用两个独立的虚拟音频设备，实现 Channel 1 和 Channel 2 的完全隔离。

```
CABLE-A: 用于 Channel 1（你的翻译音频）
CABLE-B: 用于 Channel 2（对方的音频）
```

---

### 软件选择

#### 选项A：VB-CABLE A+B（推荐，付费）

- **费用**：€15 一次性付费
- **下载**：https://vb-audio.com/Cable/
- **内容**：3个虚拟音频设备（CABLE, CABLE-A, CABLE-B）
- **优点**：稳定、官方支持、终身使用

#### 选项B：VB-CABLE + VB-CABLE Point（免费试用）

- **费用**：免费试用（可捐赠）
- **下载**：
  - VB-CABLE：https://vb-audio.com/Cable/
  - VB-CABLE Point：https://vb-audio.com/Cable/
- **内容**：2个虚拟设备
- **优点**：完全免费
- **注意**：VB-CABLE Point 是免费试用版

---

### 配置步骤

#### 第1步：安装虚拟音频设备

```
1. 下载并安装 VB-CABLE A+B
   或 VB-CABLE + VB-CABLE Point

2. 运行安装程序

3. 重启电脑（必须！）

4. 重启后验证设备：
   右键"音量"→"声音"→"播放/录制"
   应该看到：
   - CABLE Input / CABLE Output
   - CABLE-B Input / CABLE-B Output
   或
   - VB-CABLE Point Input / VB-CABLE Point Output
```

#### 第2步：配置 Windows 音频设备

**播放设备（默认）**：
```
设备：CABLE-B Input（或 VB-CABLE Point Input）
操作：右键"设为默认设备"+ "设为默认通信设备"
```

**录制设备（默认）**：
```
设备：CABLE Output (VB-Audio Virtual Cable)
操作：右键"设为默认设备"+ "设为默认通信设备"
```

#### 第3步：配置 Zoom 音频

```
麦克风：CABLE Output (VB-Audio Virtual Cable)
扬声器：CABLE-B Input（或 VB-CABLE Point Input）
```

#### 第4步：设置 Windows 监听（重要！）

```
1. 右键"音量"→"声音"→"录制"标签

2. 找到"CABLE-B Output"（或"VB-CABLE Point Output"）

3. 右键"属性"

4. 切换到"侦听"标签

5. ✅ 勾选"侦听此设备"

6. "通过此设备播放"→ 选择你的蓝牙音箱/耳机

7. 点击"应用"→"确定"
```

**作用**：让你能听到对方说话的声音

#### 第5步：修改 config_v2.yaml

```yaml
audio:
  # 麦克风配置（用户说话）
  microphone:
    device: "麦克风"  # 你的物理麦克风

  # 系统音频配置（对方说话）
  system_audio:
    device: "CABLE-B Output"  # 或 "VB-CABLE Point Output"
    fallback_device: "CABLE Output"

  # VB-CABLE输出配置（给Zoom的英文音频）
  vbcable_output:
    device: "CABLE Input"  # 保持不变
```

#### 第6步：运行测试

```bash
python main_v2.py
```

---

### 音频流向图

```
【Channel 1: 你说话 → 对方听英文】
物理麦克风
    ↓
main_v2.py Channel 1
    ↓
CABLE Input (CABLE-A)
    ↓
CABLE Output
    ↓
Zoom 麦克风
    ↓
对方听到英文 ✅

【Channel 2: 对方说话 → 你看中文字幕】
对方说英文
    ↓
Zoom 接收
    ↓
Zoom 扬声器输出到 CABLE-B Input
    ↓
CABLE-B Output
    ├─→ Windows 监听 → 蓝牙音箱（你听到）✅
    │
    └─→ main_v2.py Channel 2
        ↓
    字幕窗口显示中文 ✅
```

---

### 优点总结

✅ **支持蓝牙**：通过 Windows 监听功能
✅ **完全隔离**：两个独立虚拟设备，无回声风险
✅ **灵活性高**：不依赖物理声卡功能
✅ **稳定可靠**：比 VoiceMeeter 简单稳定

---

### 缺点总结

❌ **需要额外软件**：付费 €15 或免费试用
❌ **配置稍复杂**：需要设置 Windows 监听
❌ **轻微延迟**：<50ms 软件处理延迟
❌ **音质略差**：经过虚拟设备处理

---

## 🥉 方案3：VoiceMeeter 方案（复杂，不推荐）

### 适用场景
- ⚠️ 需要专业级音频控制
- ⚠️ 有多个音频源需要混音
- ⚠️ 愿意学习复杂的音频路由

### 为什么不推荐？

1. **配置复杂**：需要理解混音器概念和多通道路由
2. **学习曲线陡峭**：需要配置 Hardware Input、Virtual Input、A1/A2/B1/B2 路由
3. **容易出错**：配置项太多，容易导致音频路由错误
4. **资源占用**：混音器持续运行占用 CPU/内存
5. **过度设计**：对于双通道翻译来说功能过剩

### 如果确实需要使用

请参考之前提供的详细 VoiceMeeter 配置步骤，或选择更简单的方案1/方案2。

---

## 📋 快速参考清单

### 方案1（立体声混音）配置清单

| 步骤 | 配置项 | 设置值 |
|------|--------|--------|
| 1 | 立体声混音 | 启用 |
| 2 | Windows 播放设备 | Realtek HD Audio output |
| 3 | Windows 录制设备 | CABLE Output |
| 4 | Zoom 麦克风 | CABLE Output |
| 5 | Zoom 扬声器 | Realtek HD Audio output |
| 6 | config_v2.yaml | device: "立体声混音" |

### 方案2（双虚拟设备）配置清单

| 步骤 | 配置项 | 设置值 |
|------|--------|--------|
| 1 | 安装软件 | VB-CABLE A+B 或 Point |
| 2 | Windows 播放设备 | CABLE-B Input |
| 3 | Windows 录制设备 | CABLE Output |
| 4 | Zoom 麦克风 | CABLE Output |
| 5 | Zoom 扬声器 | CABLE-B Input |
| 6 | Windows 监听 | CABLE-B Output → 蓝牙音箱 |
| 7 | config_v2.yaml | device: "CABLE-B Output" |

---

## 🔧 通用故障排除

### 问题：程序日志显示"找不到设备"

**解决方法**：
```bash
# 1. 查看所有音频设备
cd F:\python\simultaneous_interpretation\realtime_translator
python -c "import sounddevice as sd; print(sd.query_devices())"

# 2. 找到对应设备的确切名称

# 3. 更新 config_v2.yaml 中的设备名称
```

---

### 问题：Channel 1 工作但 Channel 2 不工作

**可能原因**：
- 系统音频捕获设备配置错误
- 设备未启用或被静音

**解决方法**：
1. 播放音乐测试系统音频捕获设备
2. 检查 Windows 录制设备中对应设备是否有波动
3. 检查 config_v2.yaml 中 system_audio.device 配置

---

### 问题：对方听到回声

**可能原因**：
- Channel 1 和 Channel 2 使用了相同设备
- 音频路由冲突

**解决方法**：
1. 确认方案1：Zoom 扬声器 = Realtek（物理设备）
2. 确认方案2：Zoom 扬声器 = CABLE-B Input（独立虚拟设备）
3. 检查 Zoom 是否开启了"回声消除"（应该关闭）

---

### 问题：字幕窗口不显示

**可能原因**：
- Channel 2 没有捕获到音频
- 火山引擎 API 配置错误

**解决方法**：
1. 检查程序日志是否有 [Channel 2] 相关输出
2. 验证火山引擎 API 密钥是否正确
3. 测试播放英文视频，观察日志

---

## 📞 技术支持

如果遇到问题无法解决：

1. 检查日志文件：`realtime_translator_v2.log`
2. 运行测试脚本：`python test_phase2_components.py`
3. 查看详细设备信息：`python -c "import sounddevice as sd; print(sd.query_devices())"`

---

## 📚 相关文档

- `PHASE2_IMPLEMENTATION.md` - Phase 2 实施文档
- `PHASE2_PLANNING.md` - Phase 2 技术规划
- `README.md` - 项目总体文档
- `config_v2.yaml` - Phase 2 配置文件

---

**文档版本**：v1.0
**最后更新**：2025-01-01
**适用版本**：Phase 2 v2.0
