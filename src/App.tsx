/**
 * 主应用组件
 *
 * 路由分发：
 *   /          → 主窗口（配置页 / 日志页左右分栏）
 *   /subtitle  → 字幕浮窗（独立窗口）
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { StatusBar } from './components/StatusBar';
import { SubtitleOverlay } from './components/SubtitleOverlay';
import { ConfigPage } from './pages/ConfigPage';
import { LogPage } from './pages/LogPage';
import type { RuntimeStatus, LogEntry, ControlCmd } from './types/ipc';

function MainWindow() {
  const [wsPort, setWsPort] = useState<number | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<RuntimeStatus>({
    running: false,
    ch1: 'idle',
    ch2: 'idle',
    uptime: 0,
  });
  const statusPolling = useRef<number>(null);

  // 日志回调
  const handleLog = useCallback((entry: LogEntry) => {
    setLogs(prev => {
      const next = [...prev, entry];
      return next.length > 5000 ? next.slice(-5000) : next;
    });
  }, []);

  // 状态变更推送
  const handleStateChange = useCallback((data: Record<string, unknown>) => {
    setStatus(prev => ({
      ...prev,
      running: (data.running as boolean) ?? prev.running,
      ch1: (data.ch1 as string) ?? prev.ch1,
      ch2: (data.ch2 as string) ?? prev.ch2,
      uptime: (data.uptime as number) ?? prev.uptime,
    }));
  }, []);

  const { state: wsState, sendCommand } = useWebSocket({
    port: wsPort,
    onLog: handleLog,
    onStateChange: handleStateChange,
  });

  // 尝试连接 Python sidecar
  useEffect(() => {
    // 方式 1: Tauri 拉起 sidecar 获取端口
    const tryTauri = async () => {
      try {
        const { invoke } = await import('@tauri-apps/api/core');
        const port = await invoke<number>('launch_sidecar');
        setWsPort(port);
      } catch {
        // 方式 2: 开发模式直连
        setWsPort(18923);
      }
    };
    tryTauri();
  }, []);

  // 定期查询状态
  useEffect(() => {
    if (wsState !== 'connected') return;

    const poll = async () => {
      try {
        const res = await sendCommand('status');
        if (res.ok && res.data) {
          setStatus(res.data as unknown as RuntimeStatus);
        }
      } catch { /* ignore */ }
    };
    poll();
    statusPolling.current = window.setInterval(poll, 3000);
    return () => { if (statusPolling.current) clearInterval(statusPolling.current); };
  }, [wsState, sendCommand]);

  // 命令发送
  const handleCommand = useCallback(async (cmd: ControlCmd) => {
    const res = await sendCommand(cmd);
    if (!res.ok) throw new Error(res.error || '命令失败');
    // 刷新状态
    const s = await sendCommand('status');
    if (s.ok && s.data) setStatus(s.data as unknown as RuntimeStatus);
  }, [sendCommand]);

  // 未连接显示
  if (wsState === 'disconnected' || wsState === 'connecting') {
    return (
      <div className="app-container">
        <div className="connect-overlay">
          <div className="connect-overlay__spinner" />
          <span>正在连接翻译引擎...</span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {wsPort ? `ws://127.0.0.1:${wsPort}` : '等待 sidecar 启动'}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <StatusBar
        status={status}
        wsConnected={wsState === 'connected'}
        onCommand={handleCommand}
      />

      <div className="main-layout">
        <div className="main-layout__left">
          <ConfigPage running={status.running} sendCommand={sendCommand} />
        </div>
        <div className="main-layout__right">
          <LogPage logs={logs} onClear={() => setLogs([])} />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  // 路由：根据 path 决定渲染主窗口还是字幕浮窗
  const path = window.location.pathname;

  if (path === '/subtitle') {
    return <SubtitleOverlay />;
  }

  return <MainWindow />;
}
