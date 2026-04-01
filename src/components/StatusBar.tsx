/**
 * 顶部状态栏 + 启停按钮
 */

import { useEffect, useState, useRef, useCallback } from 'react';
import type { RuntimeStatus, ControlCmd } from '../types/ipc';

interface StatusBarProps {
  status: RuntimeStatus;
  wsConnected: boolean;
  onCommand: (cmd: ControlCmd) => Promise<void>;
}

export function StatusBar({ status, wsConnected, onCommand }: StatusBarProps) {
  const [loading, setLoading] = useState(false);
  const [uptime, setUptime] = useState(0);
  const [subtitleVisible, setSubtitleVisible] = useState(false);
  const timer = useRef<number>(null);

  // 字幕窗口显示/隐藏（通过 Rust command 操作，最可靠）
  const toggleSubtitle = useCallback(async () => {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const visible = await invoke<boolean>('toggle_subtitle');
      setSubtitleVisible(visible);
    } catch (e) {
      console.error('[subtitle toggle]', e);
    }
  }, []);

  // 运行计时器
  useEffect(() => {
    if (status.running) {
      setUptime(status.uptime);
      timer.current = window.setInterval(() => {
        setUptime(t => t + 1);
      }, 1000);
    } else {
      setUptime(0);
      if (timer.current) clearInterval(timer.current);
    }
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [status.running, status.uptime]);

  const formatTime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
  };

  const handleToggle = async () => {
    setLoading(true);
    try {
      await onCommand(status.running ? 'stop' : 'start');
    } finally {
      setLoading(false);
    }
  };

  const dotClass = !wsConnected
    ? ''
    : status.running
    ? 'status-indicator__dot--running'
    : '';

  const label = !wsConnected
    ? '未连接'
    : status.running
    ? '运行中'
    : '已停止';

  return (
    <div className="status-bar">
      <div className="status-bar__left">
        <span className="status-bar__title">实时同传</span>
        <div className="status-indicator">
          <span className={`status-indicator__dot ${dotClass}`} />
          <span>{label}</span>
        </div>
      </div>
      <div className="status-bar__right">
        {status.running && (
          <span className="status-bar__timer">{formatTime(uptime)}</span>
        )}
        <button
          className="btn btn--ghost"
          onClick={toggleSubtitle}
        >
          {subtitleVisible ? '隐藏字幕' : '显示字幕'}
        </button>
        <button
          className={`btn ${status.running ? 'btn--danger' : 'btn--success'}`}
          disabled={!wsConnected || loading}
          onClick={handleToggle}
        >
          {loading ? '...' : status.running ? '■ 停止' : '▶ 启动'}
        </button>
      </div>
    </div>
  );
}
