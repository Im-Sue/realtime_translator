# 更新日志

## v0.1.2 (2025-10-31) - 重大Bug修复

### 🐛 Bug修复
- **[关键]** 修复主循环自动退出问题
  - 重构为并发发送/接收模式
  - 分离音频发送和结果接收为独立任务
  - 修复WebSocket缓冲区阻塞问题
  - 详见: `BUGFIX_main_loop.md`

- **[关键]** 修复WebSocket API兼容性问题
  - 适配websockets 12.0+ 新API
  - 修复`response.headers` → `response_headers`
  - 详见: `BUGFIX_websockets.md`

### ✨ 改进
- 优化异步并发性能
- 改进错误处理和日志记录
- 添加详细的调试日志
- 改进程序退出逻辑

### 📝 文档
- 新增: `BUGFIX_websockets.md` - WebSocket兼容性修复说明
- 新增: `BUGFIX_main_loop.md` - 主循环修复说明
- 新增: `install_opus.bat` - Opus解码器安装脚本
- 新增: `CHANGELOG.md` - 本更新日志

### ⚠️ 已知问题
- FFmpeg音频解码可能失败(需要安装opuslib)
- 日志中文显示乱码(不影响功能)
- 仅支持单向翻译(中→英)

---

## v0.1.1 (2025-10-31) - WebSocket修复

### 🐛 Bug修复
- 修复websockets 12.0+ API兼容性

---

## v0.1.0 (2025-10-31) - 初始版本

### ✨ 功能
- ✅ 实时音频捕获(麦克风)
- ✅ 火山引擎同声传译API集成
- ✅ 中文 → 英文语音翻译
- ✅ 虚拟麦克风输出(VB-CABLE)
- ✅ 异步高性能架构
- ✅ 完善的错误处理和日志

### 📦 模块
- `core/audio_capture.py` - 音频捕获
- `core/audio_output.py` - 音频输出
- `core/volcengine_client.py` - API客户端
- `core/conflict_resolver.py` - 冲突解决
- `main.py` - 主程序

### 📝 文档
- `README.md` - 完整使用文档
- `QUICKSTART.md` - 快速启动指南
- `IMPLEMENTATION_SUMMARY.md` - 技术实现总结
- `test_setup.py` - 环境检测脚本

### 🎯 限制
- Phase 1 MVP版本
- 仅支持单向翻译(中→英)
- 无GUI界面
- 无字幕显示

---

## 📋 下一版本计划 (v0.2.0)

### Phase 2: 双向翻译
- [ ] 添加系统音频捕获(对方英文)
- [ ] 实现英文 → 中文翻译通道
- [ ] 命令行字幕显示
- [ ] 集成对方优先冲突解决器
- [ ] 双通道并发管理

### 优化
- [ ] 安装opuslib解决音频解码问题
- [ ] 优化日志中文显示
- [ ] 降低延迟(<2秒)
- [ ] 内存和CPU优化

---

## 🔮 未来规划

### v0.3.0 - GUI界面
- tkinter控制面板
- PyQt5悬浮字幕窗口
- 状态监控和统计
- 实时性能显示

### v0.4.0 - 优化完善
- 性能优化(<2秒延迟)
- 长时间运行稳定性
- 网络断线重连
- 配置界面

### v1.0.0 - 正式版本
- PyInstaller打包
- 一键安装程序
- 自动环境配置
- 用户手册和视频教程

---

## 📞 反馈与支持

遇到问题?
1. 查看对应的BUGFIX文档
2. 检查日志文件: `translator.log`
3. 运行环境检测: `python test_setup.py`
4. 提交Issue(如果适用)

---

**当前版本**: v0.1.2
**发布日期**: 2025-10-31
**状态**: ✅ Phase 1 (MVP) 完成,可正常使用
