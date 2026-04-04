# Channel 1 英文音频流畅度问题排查方案

> **日期**: 2026-04-01，更新于 2026-04-03
> **状态**: 阶段性验证通过
> **问题**: 中文语音→英文音频链路，对方听到的英文语音不够流畅，存在卡顿/断续
> **分析者**: Claude + Codex 联合分析

---

## 1. 问题描述

用户反馈：在 Channel 1（中文→英文）链路中，对方通过 Zoom 听到的英文语音不够流畅，有卡顿/断断续续的感觉。

初始假设方向：
1. 火山引擎返回的英文音频本身是否流畅？
2. 输出给对方的英文音频在解码、编码、推流过程中是否流畅？

---

## 2. 完整链路缓冲层级图

```
麦克风(16kHz PCM, 100ms chunks)
  → AudioCapturer.audio_queue
  → asyncio send_audio() → WebSocket
  → 火山引擎(ASR→翻译→TTS, s2s模式)
  → WebSocket recv → TranslateResponse(Ogg Opus 24kHz, 离散块)
  → audio_player.play() → FFmpeg stdin pipe
  → FFmpeg Ogg demux → Opus decode → resample 24k→48k
  → FFmpeg stdout pipe
  → _read_pcm_output线程 → _pcm_queue(1920B/次=10ms)
  → audio_callback(sounddevice, blocksize=2048=42.7ms)
  → audio_buffer(np.concatenate拼接)
  → PortAudio → VB-CABLE → Zoom → 对方
```

从"服务器返回字节"到"Zoom 对方听到"，中间经过约 **12 层缓冲/转换**，任何一层的时序抖动都会向下游传导。

---

## 3. 已有直接证据

从历史日志中发现了 **`output underflow`** 记录（日志行 L1466, L2136, L2149），说明播放端确实在"饿死"——数据供应不上，sounddevice 被迫输出静音。这不是主观感受，是实打实的数据断流。

同时，Ogg 块到达时间呈明显**突发模式**：常见 100ms/200ms 间隔夹杂 10ms 连发，对"零预缓冲"播放非常不友好。

---

## 4. 排查节点（按可能性从高到低）

### P1: asyncio 事件循环阻塞（最大嫌疑）

**问题**: `channel1_loop` 和 `channel2_loop` 共享同一个 asyncio 事件循环（`main.py:609`），但内部存在多处同步阻塞：
- `get_chunk(timeout=0.1)` 是阻塞调用（`main.py:476, 536`）
- `audio_player.play()` 内部做 `stdin.write` + `flush` + `time.sleep(0.01)`（`audio_output.py:567-571`）
- 这些阻塞会延迟 `receive_result()`，导致音频到达变成"攒一批再处理"

**排查方法**:
- 在 `play()` 调用前后加时间戳日志，测量每次调用耗时
- 在 `receive_result()` 前后加时间戳，测量接收间隔
- **A/B 测试**: 禁用 Channel 2，只跑 Channel 1，如果变流畅则确认是事件循环竞争

**涉及文件**:
- `main.py:476, 520, 536, 609`
- `core/audio_output.py:567-571`

---

### P2: 零预缓冲 + 零抖动缓冲（架构缺陷）

**问题**: 当前设计是"来一块播一块"，完全没有 jitter buffer。火山引擎返回的音频是**句级离散块**（TTSSentenceStart → 多个 TTSResponse → TTSSentenceEnd），到达间隔不均匀（日志显示 10ms~200ms 不等的突发模式）。sounddevice 每次回调要 42.7ms 数据，供应不上就输出静音。

**排查方法**:
- 在 `audio_callback` 中记录每次回调的 buffer 深度（`len(audio_buffer)`）
- 统计 underflow 次数和时间点
- 与服务器音频块到达时间做相关性分析

**涉及文件**:
- `core/audio_output.py:282-339`（audio_callback）
- `core/audio_output.py:381`（blocksize=2048）

---

### P3: 实时回调中的内存分配（性能隐患）

**问题**: `audio_callback`（`audio_output.py:282`）中用 `np.concatenate` 拼接缓冲区，每次都重新分配内存并复制整个数组。这在实时音频回调中是禁忌——可能触发 GC 暂停，把上游的轻微抖动放大成听感卡顿。

**排查方法**:
- 在回调中测量执行时间（`time.perf_counter`），如果接近或超过 42.7ms 回调周期则确认
- 观察回调耗时是否有尖峰

**涉及文件**:
- `core/audio_output.py:300`（np.concatenate）

---

### P4: FFmpeg 流式解码特性

**问题**:
- `bufsize=0` 只关闭了 Python 侧的 stdio 缓冲，FFmpeg 自身的 Ogg demux/Opus decode/resampler 仍有内部缓冲
- Ogg 是页式容器，需要先解析 header 才能出 PCM，每个句子开头可能有额外延迟
- 如果每个句子是独立的 Ogg 逻辑流（新 BOS/EOS），持久 FFmpeg 进程可能需要重新同步

**排查方法**:
- 记录每个句子首字节到首个 PCM 输出的延迟
- 检查每个音频块的前 16-32 字节（hex），看是否以 `OggS` / `OpusHead` 开头
- 监控 FFmpeg stderr 是否有 demux 告警

**涉及文件**:
- `core/audio_output.py:423-465`（FFmpeg 进程配置）
- `core/audio_output.py:482-500`（PCM 读取线程）

---

### P5: PCM 读取粒度不匹配

**问题**: `_read_pcm_output` 每次读 1920 字节（10ms @48kHz），而回调要 42.7ms，需要 4-5 次 queue.get 才能填满一次回调。粒度本身不算错，但增加了队列交互频率。

**排查方法**: 记录 `_pcm_queue` 深度变化

**涉及文件**:
- `core/audio_output.py:489`

---

### P6: Channel 2 对 Channel 1 的干扰

**问题**: Channel 2 的 `get_chunk(timeout=0.1)` 也在同一事件循环中阻塞，可能延迟 Channel 1 的音频接收。

**排查方法**: 禁用 Channel 2 做对比测试

**涉及文件**:
- `main.py:536`

---

### P7: VB-CABLE / Zoom 下游缓冲

**问题**: 可能存在，但优先级最低——因为 app 侧已经在 underflow 了，问题在音频到达 VB-CABLE 之前就已经发生。

**排查方法**: 排除上游问题后，用本地扬声器直接输出 vs VB-CABLE 做 A/B

---

## 5. 火山引擎 s2s 音频特征分析

火山引擎"同声传译 2.0"的 s2s 模式返回音频特征：

- **协议**: 基于 WebSocket 的消息级传输，非连续 PCM 流
- **句级边界**: `TTSSentenceStart` → 多个 `TTSResponse`(含 audio_data) → `TTSSentenceEnd`
- **格式**: Ogg Opus 容器，24kHz
- **到达模式**: 突发式，句内块间隔不均匀（10ms~200ms）
- **结论**: 服务端返回的音频本身是离散的句级 TTS 合成结果，不是平滑的连续流。这是正常行为，但需要客户端做平滑处理。

---

## 6. 调试日志方案

| 位置 | 文件:行号 | 记录内容 |
|------|----------|---------|
| WebSocket recv 后 | `volcengine_client.py:343` | event, sequence, audio_bytes, delta_recv_ms |
| play() 前后 | `main.py:520` | play_call_start_ms, play_call_end_ms, cost_ms |
| FFmpeg write | `audio_output.py:567` | stdin_write_cost_ms, flush_cost_ms |
| PCM read | `audio_output.py:489` | pcm_bytes, delta_read_ms, queue_depth |
| audio_callback | `audio_output.py:282` | buffer_depth_before, buffer_depth_after, callback_cost_ms, underflow_count |
| send_audio 循环 | `main.py:473, 533` | get_chunk_wait_ms, chunk_bytes, send_cost_ms |
| 事件循环心跳 | main loop | 期望唤醒 vs 实际唤醒时间（量化 loop lag） |

---

## 7. 推荐排查顺序

```
Step 1: 加调试日志（上表所有位置）→ 跑一轮实际通话录音
Step 2: 分析日志，确认 underflow 时间点与上游哪个环节的延迟相关
Step 3: A/B 测试（禁用 Channel 2）→ 确认事件循环竞争影响
Step 4: 根据 Step 2/3 结果确定修复方向
```

---

## 8. 根因判断

**最可能的根因不是单一节点，而是三者叠加**：

1. **asyncio 事件循环被同步调用阻塞** → 音频接收变成批量处理
2. **火山引擎返回音频本身是突发式的**（句级 TTS）→ 到达时序不均匀
3. **播放端零预缓冲 + 回调内内存分配** → 无法平滑抖动

这三个问题互相放大：**上游抖动 x 无缓冲平滑 x 回调延迟 = 听感卡顿**。

---

## 9. 端到端缓冲层级详细映射

```
火山引擎内部 ASR/MT/TTS 缓冲
  → WebSocket frame
  → websockets recv buffer
  → receive_result()
  → self.audio_player.play()
  → FFmpeg stdin pipe
  → FFmpeg Ogg demux buffer
  → FFmpeg decoder / resampler buffer
  → FFmpeg stdout pipe
  → _pcm_queue
  → audio_buffer (sounddevice callback 内)
  → PortAudio / sounddevice output buffer
  → VB-CABLE driver buffer
  → Zoom input buffer
```

---

## 10. 后续跟进

- [x] Step 1: 实施调试日志方案
- [x] Step 2: 收集多轮实际通话日志并分析
- [x] Step 3: 完成 PCM 直出 + 新播放内核的第一轮实施
- [x] Step 4: 完成大缓冲修复并验证主观流畅度提升
- [ ] Step 5: 收敛剩余 rebuffer / 首音延迟问题
- [ ] Step 6: 针对上游空窗做进一步优化

---

## 11. 2026-04-03 阶段性结论

可以认为 **本次“基本实施”已经成功**，但还没有达到“完全收敛”的状态。

成功的判断依据：

1. **PCM 直出链路已跑通**
   - 当前 CH1 已不再经过 FFmpeg 解码与重采样。
   - 实际运行配置显示 `target_format=pcm`、`target_rate=48000Hz`。

2. **“缓冲过小导致大量丢音”这一主问题已解决**
   - 新日志中 `dropped=0` 持续成立。
   - 说明扩大环形缓冲区后，句级突发音频不再被播放器主动丢弃。

3. **主观流畅度已明显提升**
   - 用户实测反馈“修复后流畅性有很大改善”。
   - 这与日志结论一致：旧问题是“音频写入后被缓冲区吞掉”，新版本已消除这一失真源。

因此，本次实施可以定义为：

- **阶段一目标已达成**：从“输出侧吞音频”切换为“输出侧基本忠实播放收到的音频”。
- **剩余问题已收敛到更上游**：当前主要瓶颈不再是本地缓冲容量，而是服务端音频回包的空窗和播放器应对策略。

---

## 12. 经验沉淀

### 12.1 不要把“低延迟”误写成“极小缓冲”

最初 500ms 环形缓冲看起来更“实时”，但与火山 s2s 的**句级突发**模式不匹配。  
当服务端一次吐出 1-5 秒音频时，小缓冲不是低延迟，而是**确定性丢音**。

经验：

- 面向“流式句级 TTS”场景，缓冲区容量必须按**服务端突发规模**设计，而不是只按 callback 周期设计。
- 优先保证“先完整接住，再平滑播出”，再做延迟优化。

### 12.2 先消除确定性数据丢失，再优化时序抖动

旧问题里，`dropped_samples` 是决定性根因。  
如果音频已经在本地环节被丢掉，再调 `prefill`、`resume`、`blocksize` 都只是修补症状。

经验：

- 优化顺序应是：  
  `先保真 -> 再平滑 -> 最后降延迟`

### 12.3 诊断指标必须区分“写入成功”与“真实播出”

新增的两类诊断日志非常关键：

- `CH1上游诊断`：告诉我们服务端到底给了多少音频
- `CH1播放诊断`：告诉我们本地到底播了多少音频

只有把“收到多少”和“播出多少”分开记录，才能看出：

- 是上游没给音频
- 还是本地播放器吞掉音频
- 还是设备路由层有问题

### 12.4 当前 CH1 不再是“播放器吞音”，而是“上游空窗 + 本地保守 rebuffer”

2026-04-03 的日志表明：

- `dropped=0`
- `已写 ≈ 已播`
- 但 `underflow/rebuffer` 仍在增长

这说明本地输出链路已基本保真，残余问题来自：

- 服务端音频回包存在秒级空窗
- 本地在空窗期间只能静音等待

---

## 13. 最新日志证据摘要（2026-04-03）

### 13.1 已解决的问题

- 输出设备命中正确的用户目标设备：`CABLE In 16 Ch`
- PCM 直出已生效：目标格式 `pcm`，目标采样率 `48000Hz`
- 缓冲不再溢出：`dropped=0`

### 13.2 剩余问题

日志显示仍有明显的**秒级上游空窗**：

- `00:40:17`：`间隔=2232.4ms`
- `00:40:22`：`间隔=3874.7ms`

对应播放器状态：

- 缓冲从 `134.7ms / 234.7ms` 快速耗尽
- 随后进入 `REBUFFERING`

说明当前的卡顿已不再是“本地丢音”，而是：

```text
服务端长时间没有新音频
  -> 本地缓冲被放空
  -> callback 只能补静音
  -> 进入 rebuffer
```

### 13.3 仍需关注的两个指标

1. **首次音频延迟仍偏高**
   - 当前日志：`首次音频延迟 = 14.94 秒`
   - 这说明首句出音仍然偏慢，问题不在播放器容量，而更接近上游分句/VAD/服务端出音策略。

2. **输出设备默认采样率与目标采样率不一致**
   - 设备默认：`44100Hz`
   - 目标输出：`48000Hz`
   - 当前没有证据表明它是主因，但仍可能带来设备侧隐式重采样。

---

## 14. 下一阶段优化方向

### 14.1 优先级 P1：把“上游空窗”观测做准

当前日志里的 `间隔` 字段记录的是“最近两个音频包之间的到达间隔”，  
但当长时间没有新包时，它会停留在上一次的值，无法准确描述“已经多久没有新音频”。

建议新增：

- `stale_ms = 当前时间 - last_audio_time`
- `连续无新包时长`
- 最近 N 次空窗分布（P50 / P95 / Max）

目标：

- 判断真正的主因是否为服务端 2-4 秒级静默空窗
- 避免被“最近一次小间隔”误导

### 14.2 优先级 P1：让 jitter buffer 阈值从固定值改为自适应

当前播放器已不丢音，但仍因空窗频繁 `rebuffer`。  
问题不在总容量，而在恢复播放门槛仍偏保守/固定。

建议方向：

- `prefill_ms` / `resume_watermark_ms` 改为配置项
- 增加“保守模式”与“标准模式”
- 后续根据最近空窗分布，动态调整恢复门槛

预期收益：

- 降低 `rebuffer`
- 提高连续性
- 代价是增加少量播放延迟

### 14.3 优先级 P2：单独拆出“首音延迟”问题

当前首音延迟约 `15 秒`，明显偏大。  
这已经超出本地播放缓冲的解释范围，更像上游策略问题。

建议单独排查：

- 火山 s2s 首句是否等待较长分句/VAD
- 当前输入 chunk / 句边界策略是否过于保守
- 首句文本与首句音频出现时间差

### 14.4 优先级 P3：评估 44.1k 与 48k 设备匹配

当前目标输出是 `48kHz`，而设备默认是 `44.1kHz`。  
在主链路稳定后，可做一次 A/B：

- `48k` 输出
- `44.1k` 输出

比较：

- 主观流畅度
- `underflow/rebuffer`
- Zoom 端听感

---

## 15. 当前结论

截至 **2026-04-03**，CH1 音频流畅度优化已经完成了**最关键的一步**：

- 从“本地播放链路吞音频”修复为“本地播放链路基本保真”

后续优化的重点应从“扩大桶”转向：

- **更准确地观测上游空窗**
- **更聪明地调节 jitter buffer**
- **单独攻克首音延迟**

---

*本报告由 Claude + Codex 联合分析生成，基于代码静态分析和历史日志证据。*
