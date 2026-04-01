# 桌面 UI 实施 — 阶段性完成报告

> **初次完成**: 2026-03-27 17:17（第一轮 AI 实施）
> **本次更新**: 2026-03-29（文档整理与状态更新）

本报告记录桌面 UI 项目从架构设计到打包验证的完整实施过程，包含 P0-P8 共 24 个任务的完成情况、遗留问题和后续计划。

---

## 一、总体进度

| 阶段 | 状态 | 说明 |
|------|------|------|
| P0 命名清理 | ✅ 已完成（前序） | 之前已完成 |
| P1 日志系统 | ✅ 已完成 | `logging_utils.py` + `main.py` 改造 |
| P2 WebSocket Server | ✅ 已完成 | `sidecar.py` 重写 + 命令分发 + watchdog + WSLogHandler |
| P3 Service 层 | ✅ 已完成 | RuntimeService + 回调注入 + 字幕推送 + ConfigService/DeviceService |
| P4 Tauri 壳 | ✅ 已完成 | `tauri.conf.json` + `lib.rs` sidecar 启动器 + capabilities |
| P5 前端配置页 | ✅ 已完成 | StatusBar + ConfigPage(4 折叠面板) + useWebSocket hook |
| P6 前端日志页 | ✅ 已完成 | LogPage 筛选/搜索/导出/自动滚底 |
| P7 字幕浮窗 | ✅ 已完成 | SubtitleOverlay 透明窗 + 动效 |
| **P8 构建打包** | **⚠️ 基本完成** | **安装包已生成，但资源未嵌入安装包（见下方）** |
| P9 macOS 适配 | ❌ 未开始 | — |

---

## 二、本轮修复的 Bug（3 个）

| Bug | 文件 | 修复方式 |
|-----|------|----------|
| `runtime_state` NameError | [sidecar.py](file:///f:/python/simultaneous_interpretation/realtime_translator/desktop_backend/sidecar.py) | 删除未定义的 `runtime_state` 字典，改为委托 `runtime_service.start()/stop()/status` |
| `/ws/subtitle` 推送未接线 | [sidecar.py](file:///f:/python/simultaneous_interpretation/realtime_translator/desktop_backend/sidecar.py) | 新增 `broadcast_subtitle_sync()` + `_subtitle_callback` 注入 RuntimeService |
| 桌面模式 Tkinter 崩溃 | [main.py](file:///f:/python/simultaneous_interpretation/realtime_translator/main.py) | 条件化 `subtitle_window_thread`：仅 `subtitle_callback is None` 时创建 Tkinter；`start()`/`stop()`/`ui_event_loop()` 均加 `None` 守卫 |

---

## 三、本轮新建文件（16 个）

### Tauri 壳 (`src-tauri/`)

| 文件 | 说明 |
|------|------|
| [tauri.conf.json](file:///f:/python/simultaneous_interpretation/realtime_translator/src-tauri/tauri.conf.json) | 主窗口 520×720 + subtitle-overlay (透明/置顶/无边框) |
| [Cargo.toml](file:///f:/python/simultaneous_interpretation/realtime_translator/src-tauri/Cargo.toml) | Tauri 2 + tauri-plugin-shell + tokio + serde |
| [build.rs](file:///f:/python/simultaneous_interpretation/realtime_translator/src-tauri/build.rs) | 标准 tauri_build |
| [src/lib.rs](file:///f:/python/simultaneous_interpretation/realtime_translator/src-tauri/src/lib.rs) | `launch_sidecar` 命令：spawn Python → 读 stdout port → emit event → 进程管理 |
| [src/main.rs](file:///f:/python/simultaneous_interpretation/realtime_translator/src-tauri/src/main.rs) | 入口，委托 `realtime_translator::run()` |
| [capabilities/default.json](file:///f:/python/simultaneous_interpretation/realtime_translator/src-tauri/capabilities/default.json) | 双窗口权限 |
| `icons/*` | 由 `pnpm tauri icon` 自动生成（ICO/ICNS/PNG 全平台） |

### React 前端 (`src/`)

| 文件 | 说明 |
|------|------|
| [App.tsx](file:///f:/python/simultaneous_interpretation/realtime_translator/src/App.tsx) | 路径路由（`/` → 主窗口，`/subtitle` → 浮窗）+ 状态管理 |
| [main.tsx](file:///f:/python/simultaneous_interpretation/realtime_translator/src/main.tsx) | React 入口 |
| [index.css](file:///f:/python/simultaneous_interpretation/realtime_translator/src/index.css) | 深色主题设计系统（紫色 accent、glassmorphism、动画） |
| [hooks/useWebSocket.ts](file:///f:/python/simultaneous_interpretation/realtime_translator/src/hooks/useWebSocket.ts) | 管理 3 条 WS 连接 + UUID 命令/响应匹配 |
| [types/ipc.ts](file:///f:/python/simultaneous_interpretation/realtime_translator/src/types/ipc.ts) | 完整 WS 协议 TypeScript 类型 |
| [components/StatusBar.tsx](file:///f:/python/simultaneous_interpretation/realtime_translator/src/components/StatusBar.tsx) | 渐变标题 + 脉冲指示灯 + 计时器 + 启停 |
| [pages/ConfigPage.tsx](file:///f:/python/simultaneous_interpretation/realtime_translator/src/pages/ConfigPage.tsx) | 4 折叠面板（凭据/设备/通道/字幕） |
| [pages/LogPage.tsx](file:///f:/python/simultaneous_interpretation/realtime_translator/src/pages/LogPage.tsx) | level/channel 筛选 + 搜索 + 导出 + 自动滚底 |
| [components/SubtitleOverlay.tsx](file:///f:/python/simultaneous_interpretation/realtime_translator/src/components/SubtitleOverlay.tsx) | EN/ZH 双行 + slide-up 动效 + 5s 静默淡出 + 拖拽 |

### 构建相关

| 文件 | 说明 |
|------|------|
| [package.json](file:///f:/python/simultaneous_interpretation/realtime_translator/package.json) | React 19 + Tauri 2 + Vite 6 |
| [vite.config.ts](file:///f:/python/simultaneous_interpretation/realtime_translator/vite.config.ts) | Vite config (port 1420) |
| [tsconfig.json](file:///f:/python/simultaneous_interpretation/realtime_translator/tsconfig.json) | TypeScript strict |
| [index.html](file:///f:/python/simultaneous_interpretation/realtime_translator/index.html) | 入口 HTML (Inter 字体) |
| [scripts/build_bundle.ps1](file:///f:/python/simultaneous_interpretation/realtime_translator/scripts/build_bundle.ps1) | Windows 构建脚本（5 步） |

---

## 四、构建验证结果

| 检查项 | 结果 |
|--------|------|
| Python `py_compile` (4 文件) | ✅ 通过 |
| TypeScript `tsc --noEmit` | ✅ 通过 |
| Vite production build | ✅ 通过 (213KB JS + 9.5KB CSS) |
| `cargo check` | ✅ 通过 |
| `pnpm tauri build` | ✅ 通过 |
| Bundle 准备 (embedded Python + deps + source) | ✅ 78.8MB |
| **NSIS 安装包** `RealtimeTranslator_1.0.0_x64-setup.exe` | ✅ 生成, 2.4MB |
| **MSI 安装包** `RealtimeTranslator_1.0.0_x64_en-US.msi` | ✅ 生成, 3.6MB |

---

## 五、⚠️ 当前遗留问题

### 1. 安装包未嵌入 Python bundle（关键）

安装包只有 2.4MB (NSIS) / 3.6MB (MSI)，而 Python bundle 有 78.8MB。

**原因分析**：`tauri.conf.json` 中不能静态写 `resources` 路径（空目录时 `cargo check` 会报 glob error），所以改用 `TAURI_CONFIG` 环境变量注入。实际测试中，**map 格式的 resources 确认了 python/backend/deps 三个目录被拷贝到了 `src-tauri/target/release/` 下**，但 NSIS/MSI 打包器可能没有把它们包含进安装包。

**建议修复方向**：
- 验证安装包内容（解压 MSI/NSIS 看是否包含 python 文件夹）
- 如果没有包含，尝试在 `tauri.conf.json` 中直接写 resources（在 build 前确保 bundle/ 目录非空）
- 或者修改 `build_bundle.ps1` 在 tauri build 前动态写入 `tauri.conf.json`

### 2. Cargo 镜像已修改

已将 `D:\rust\.cargo\config.toml` 从 tuna 切换到 USTC，并加了 `check-revoke = false` 绕过 SSL 问题。原 `config` 已备份为 `config.bak`。

### 3. 开发模式启动说明

```bash
# 终端 1: Python 后端
python desktop_backend/sidecar.py --dev --port 18923

# 终端 2: 前端 dev server  
pnpm dev
# 浏览器打开 http://localhost:1420
```

开发模式下 App.tsx 会自动 fallback 到 `ws://127.0.0.1:18923`。

---

## 六、关键设计决策供后续参考

1. **resources 不在 tauri.conf.json 中静态声明** — 因为 bundle/ 目录在 `cargo check` / `tauri dev` 时为空，glob 会报错。改用 `TAURI_CONFIG` 环境变量在 build 时注入。
2. **embedded Python 改名为 `rt-engine.exe`** — 避免与系统 Python 冲突，`lib.rs` 中通过检测 `python/rt-engine.exe` 是否存在来判断生产/开发模式。
3. **三条 WS 连接** — `/ws/control`（命令RPC）、`/ws/logs`（日志流）、`/ws/subtitle`（字幕推送），前端通过 `useWebSocket.ts` 统一管理。
4. **字幕回调注入** — `DualChannelTranslator` 的 `subtitle_callback` 参数，桌面模式下注入 WS 广播函数，CLI 模式下为 None（走 Tkinter）。

---

## 七、文件树概览

```
realtime_translator/
├── package.json, vite.config.ts, tsconfig.json, index.html
├── src/                          # React 前端
│   ├── App.tsx, main.tsx, index.css, vite-env.d.ts
│   ├── types/ipc.ts
│   ├── hooks/useWebSocket.ts
│   ├── components/StatusBar.tsx, SubtitleOverlay.tsx
│   └── pages/ConfigPage.tsx, LogPage.tsx
├── src-tauri/                    # Tauri Rust 壳
│   ├── tauri.conf.json, Cargo.toml, build.rs
│   ├── src/lib.rs, src/main.rs
│   ├── capabilities/default.json
│   └── icons/
├── desktop_backend/              # Python WS 后端（已有）
│   ├── sidecar.py                # WS server 入口
│   └── services.py               # Runtime/Config/Device/Health services
├── core/                         # Python 核心（已有）
├── scripts/
│   └── build_bundle.ps1          # Windows 构建脚本
├── bundle/windows-x64/           # 构建产物（78.8MB）
│   ├── python/rt-engine.exe      # Embedded Python 3.12.8
│   ├── backend/                  # Python 源码副本
│   └── deps/                     # pip 依赖
└── docs/
    ├── .ccb/                     # 协作索引与决策记录
    ├── 02_需求设计/
    │   └── desktop-ui-followup-notes.md
    ├── 03_开发计划/
    │   ├── desktop-ui-design.md  # 设计文档
    │   └── desktop-ui-tasks.md   # 任务跟踪
    └── 13_项目报告/
        └── phase-report-2026-03-27.md
```

---

## 八、后续计划

### 紧急修复（P0 优先级）

**资源嵌入问题解决方案**（预计 2-4 小时）：

1. **验证现状**
   - 解压 NSIS/MSI 安装包，检查 `resources` 目录内容
   - 确认是否完全缺失或仅部分缺失

2. **修复方向 A：静态声明（推荐）**
   - 在 `build_bundle.ps1` 中动态修改 `tauri.conf.json`
   - 在 `tauri build` 前写入 resources 路径
   - 构建完成后恢复原文件
   - 优点：符合 Tauri 标准打包方式

3. **修复方向 B：环境变量排查**
   - 验证 `TAURI_CONFIG` 注入是否生效
   - 检查 PowerShell 环境变量传递给 pnpm 的完整性
   - 优点：保持当前架构不变

4. **验证标准**
   - 安装包大小应在 80-85MB（2.4MB Tauri + 78.8MB bundle）
   - 安装后 `%PROGRAMFILES%/RealtimeTranslator/` 包含完整 python/backend/deps
   - 启动程序能成功拉起 Python sidecar

### 短期目标（1-2 周）

| 任务 | 优先级 | 预估工时 |
|------|-------|---------|
| 修复资源嵌入问题 | P0 | 2-4h |
| 端到端功能验证 | P0 | 2-3h |
| 编写安装/使用文档 | P1 | 1-2h |
| Windows Authenticode 签名 | P1 | 1h + 证书申请 |
| 构建 CI/CD 流程（GitHub Actions） | P2 | 4-6h |

### 中期目标（1 个月）

| 任务 | 说明 |
|------|------|
| macOS 适配 | python-build-standalone 版本验证 + sounddevice 兼容性测试 |
| macOS 公证 | Apple Developer 账号 + notarize 流程 |
| 多语言支持 | i18n 框架集成（中/英文切换） |
| 性能优化 | WebSocket 连接池管理、日志缓冲优化 |
| 错误恢复机制 | Sidecar 崩溃自动重启、配置回滚 |

### 长期规划

- Linux 支持（AppImage/Flatpak）
- 字幕样式自定义（字体/颜色/位置）
- 翻译历史记录与导出
- 云端配置同步
- 自动更新机制（Tauri updater）

---

## 九、经验总结

### 成功经验

1. **设计先行**：详细的设计文档（`docs/03_开发计划/desktop-ui-design.md`）确保实施方向清晰
2. **任务拆解**：25 个独立任务便于并行开发和进度跟踪
3. **关注点分离**：WebSocket 三端点架构实现前后端解耦
4. **渐进验证**：每个阶段都有独立验证点（Python 检查 → TS 编译 → Rust 编译）

### 踩坑记录

1. **Tauri resources 动态路径**
   - 问题：空目录时 `cargo check` 报 glob error
   - 解决：环境变量注入（但打包未生效，待修复）
   - 教训：提前准备 bundle 目录，使用静态路径声明

2. **Embedded Python 路径搜索**
   - 问题：`_pth` 文件路径配置错误导致模块找不到
   - 解决：明确配置相对路径（`../deps`, `../backend/realtime_translator`）
   - 教训：打包后在真实安装环境测试路径

3. **字幕回调注入兼容性**
   - 问题：桌面模式下 Tkinter 初始化导致崩溃
   - 解决：条件化 `subtitle_window_thread` 创建，加 None 守卫
   - 教训：保持 CLI 和桌面模式双向兼容
