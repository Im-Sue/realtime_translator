# 桌面 UI 开发任务清单

> 作者：Sue
> GitHub：https://github.com/Im-Sue/
> TG：@Sue_muyu
> 创建日期：2026-03-26
> 最后更新：2026-03-29
> 关联设计文档：[desktop-ui-design.md](./desktop-ui-design.md)

---

## 进度总览（截至 2026-03-29）

| 阶段 | 任务数 | 已完成 | 进行中 | 待开始 | 完成率 |
|------|-------|-------|-------|-------|-------|
| P0 命名清理 | 2 | 2 | 0 | 0 | 100% |
| P1 日志系统 | 2 | 2 | 0 | 0 | 100% |
| P2 WebSocket Server | 4 | 4 | 0 | 0 | 100% |
| P3 Service 层 | 4 | 4 | 0 | 0 | 100% |
| P4 Tauri 壳 | 2 | 2 | 0 | 0 | 100% |
| P5 前端配置页 | 5 | 5 | 0 | 0 | 100% |
| P6 前端日志页 | 1 | 1 | 0 | 0 | 100% |
| P7 字幕浮窗 | 2 | 2 | 0 | 0 | 100% |
| P8 构建打包 | 2 | 1 | 1 | 0 | 50% ⚠️ |
| P9 跨平台 | 1 | 0 | 0 | 1 | 0% |
| **总计** | **25** | **23** | **1** | **1** | **92%** |

**关键里程碑**：
- ✅ Python 后端 WebSocket 服务化（P0-P3）
- ✅ Tauri 壳与前端 UI 实现（P4-P7）
- ⚠️ Windows 打包基本完成，资源嵌入待修复（P8-2）
- ⏳ macOS 适配未启动（P9）

---

## 任务依赖关系

```
P0-1 ─┐
P0-2 ─┤（无依赖，可立即执行）
P1-1 ─┼──→ P1-2 ──→ P3-2
      │
      ├──→ P2-1 ──→ P2-2 ──→ P3-1 ──→ P3-3
      │      │                          ↑
      │      ├──→ P2-3                P3-2
      │      ├──→ P2-4 ──→ P6-1
      │      ├──→ P4-1 ──→ P4-2 ──→ P5-1 ──→ P5-2
      │      │      │                   ├──→ P5-3
      │      │      └──→ P7-1           ├──→ P5-4
      │      │             ↓             ├──→ P5-5
      │      │           P7-2           └──→ P6-1
      │      │
      │      └──→ P8-1
      │
      └──→ P3-4
                    全部完成 ──→ P8-2 ──→ P9-1
```

**并行策略**：
- Python 线（P0→P1→P2→P3）和 Tauri/前端线（P4→P5→P6→P7）可并行推进
- P2-3（心跳）、P2-4（WS日志）、P8-1（构建脚本）可各自独立开发

---

## P0: 统一命名漂移

### P0-1: 清理 spec 文件中的 v2 引用
- **状态**: ✅ 已完成（2026-03-26）
- **改动文件**: `realtime_translator.spec`
- **内容**: `config_v2.yaml` → `config.yaml`，`main_v2.py` → `main.py`

### P0-2: 清理 scripts/ 中的 v2 引用
- **状态**: ✅ 已完成（2026-03-26）
- **改动文件**: `scripts/run.sh`，`scripts/healthcheck.sh`
- **内容**: 所有 `config_v2.yaml` → `config.yaml`，`main_v2.py` → `main.py`

---

## P1: Python 日志系统改造

### P1-1: 实现 ChannelLogger 日志适配器
- **状态**: ✅ 已完成（2026-03-26）
- **新增文件**: `core/logging_utils.py`
- **内容**:
  - `ChannelFormatter`: 注入 channel 字段的日志格式器
  - `WSLogHandler`: WS 推送 + 环形缓冲（500 条历史）
  - `ChannelLogger`: 通道适配器（SYS/CH1/CH2）
  - `setup_logging()`: 统一初始化（文件 + 控制台 + 可选 WS）
- **日志格式**: `{timestamp}.{ms} [{level}] [{channel}] [{module}] {message}`

### P1-2: 改造 main.py 使用新日志系统
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P1-1
- **改动文件**: `main.py`
- **内容**: 将 logger.info/debug/warning/error 替换为 sys_log/ch1_log/ch2_log，桌面模式下跳过 Tkinter 初始化

---

## P2: WebSocket Server 基础设施

### P2-1: 重写 sidecar.py 为 WebSocket server 入口
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P1-1
- **改动文件**: `desktop_backend/sidecar.py`
- **内容**: WS server 启动、端口分配、stdout 输出 ready 信号、--dev/--port/--parent-pid 参数

### P2-2: 实现 /ws/control 命令分发
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P2-1
- **内容**: 请求/响应协议 {id, cmd, payload} → {id, ok, data/error}，分发到各 Service

### P2-3: 实现心跳 watchdog 线程
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P2-1
- **内容**: 守护线程每 3s 检查 parent_pid，PID 文件管理

### P2-4: 实现 WSLogHandler 日志推送
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P1-1, P2-1
- **内容**: 绑定 WS 广播回调到 WSLogHandler，/ws/logs 端点推送 + 历史回放

---

## P3: RuntimeService 与字幕推送

### P3-1: 实现 RuntimeService 服务化封装
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P2-2
- **内容**: 包装 DualChannelTranslator，start/stop/get_status，状态机管理，回调注入

### P3-2: 改造 DualChannelTranslator 支持回调注入
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P1-2
- **内容**: 增加 subtitle_callback，_flush_ch2_buffer 中优先调用回调，桌面模式跳过 Tkinter

### P3-3: 实现 /ws/subtitle 字幕推送
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P3-1, P3-2
- **内容**: subtitle_callback → broadcast_subtitle_sync → WS 推送 {type, en, zh, is_final}

### P3-4: 适配 ConfigService / DeviceService / HealthService
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P2-2
- **内容**: 已有 service 适配到新 WS 协议，合并为 `desktop_backend/services.py`

---

## P4: Tauri 壳配置

### P4-1: 新建 src-tauri/tauri.conf.json
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P2-1
- **内容**: 主窗口 + 字幕浮窗配置、bundle resources、权限声明

### P4-2: 实现 Rust 侧 sidecar 拉起逻辑
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P4-1
- **内容**: `lib.rs` 中 launch_sidecar 命令，读 stdout 端口，event 通知前端，进程生命周期管理

---

## P5: 前端配置页

### P5-1: 前端 WebSocket 连接管理 hook
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P4-2
- **内容**: `useWebSocket.ts`，管理 control/logs/subtitle 三条连接，命令发送/响应匹配

### P5-2: 前端配置页 — 顶部状态栏 + 启停控制
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P5-1
- **内容**: `StatusBar.tsx`，运行指示灯、计时、启停按钮

### P5-3: 前端配置页 — 火山引擎凭据面板
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P5-1, P3-4
- **内容**: `ConfigPage.tsx` 火山引擎折叠面板，表单字段 + 测试连接

### P5-4: 前端配置页 — 音频设备面板
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P5-1, P3-4
- **内容**: `ConfigPage.tsx` 音频设备折叠面板，设备下拉 + 刷新 + FFmpeg 开关

### P5-5: 前端配置页 — 翻译通道 + 字幕设置面板
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P5-1
- **内容**: `ConfigPage.tsx` 通道开关 + 字幕设置折叠面板 + 保存按钮

---

## P6: 前端日志页

### P6-1: 前端日志页
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P5-1, P2-4
- **内容**: `LogPage.tsx`，订阅 /ws/logs，筛选/搜索/清空/导出，自动滚底

---

## P7: 字幕浮窗

### P7-1: 字幕浮窗 — Tauri 多窗口创建
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P4-1
- **内容**: `tauri.conf.json` 中 subtitle-overlay 窗口 transparent/alwaysOnTop/skipTaskbar

### P7-2: 字幕浮窗 — 字幕渲染与动效
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P7-1, P3-3
- **内容**: `SubtitleOverlay.tsx`，EN/ZH 双行，滑入淡出动效，5s 静默自动降低透明度，拖拽移动

---

## P8: 构建与打包

### P8-1: 编写构建脚本 build_bundle.ps1
- **状态**: ✅ 已完成（2026-03-27）
- **依赖**: P2-1
- **改动文件**: `scripts/build_bundle.ps1`
- **内容**: 5 步构建流程（Python 下载 + 依赖安装 + FFmpeg + 源码复制 + Tauri 打包）

### P8-2: 端到端打包验证（Windows）
- **状态**: ⚠️ 基本完成，存在遗留问题（2026-03-27）
- **依赖**: P5-2 ~ P7-2, P8-1 全部完成
- **产物**:
  - ✅ NSIS 安装包：`RealtimeTranslator_1.0.0_x64-setup.exe` (2.4MB)
  - ✅ MSI 安装包：`RealtimeTranslator_1.0.0_x64_en-US.msi` (3.6MB)
  - ✅ Bundle 目录：`bundle/windows-x64/` (78.8MB)
- **⚠️ 已知问题**:
  - **资源未嵌入安装包**：NSIS/MSI 大小仅 2-4MB，未包含 78.8MB 的 Python bundle
  - **可能原因**：`tauri.conf.json` 的 resources 动态注入机制未生效
  - **待修复方向**：
    1. 验证安装包内容（解压检查是否包含 python 目录）
    2. 尝试静态声明 resources（确保 bundle/ 非空后再 build）
    3. 检查 `TAURI_CONFIG` 环境变量是否正确传递
- **验证项**:
  - ✅ Python 语法检查
  - ✅ TypeScript 编译
  - ✅ Vite 生产构建
  - ✅ Cargo 检查
  - ❌ 安装包完整性（缺少资源文件）

---

## P9: 跨平台

### P9-1: macOS 适配 + 代码签名
- **状态**: ⏳ 待开始
- **依赖**: P8-2
- **内容**: python-build-standalone macOS 验证、codesign + notarize
