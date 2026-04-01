/**
 * WebSocket 连接管理 Hook
 *
 * 管理 control / logs / subtitle 三条 WS 连接，
 * 提供命令发送和消息订阅接口。
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type {
  ControlCmd,
  ControlResponse,
  LogEntry,
  SubtitleEntry,
} from '../types/ipc';

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

interface UseWebSocketOptions {
  port: number | null;
  onLog?: (entry: LogEntry) => void;
  onSubtitle?: (entry: SubtitleEntry) => void;
  onStateChange?: (data: Record<string, unknown>) => void;
}

interface UseWebSocketReturn {
  state: ConnectionState;
  sendCommand: (cmd: ControlCmd, payload?: Record<string, unknown>) => Promise<ControlResponse>;
  disconnect: () => void;
}

export function useWebSocket({
  port,
  onLog,
  onSubtitle,
  onStateChange,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [state, setState] = useState<ConnectionState>('disconnected');

  const controlWs = useRef<WebSocket | null>(null);
  const logsWs = useRef<WebSocket | null>(null);
  const subtitleWs = useRef<WebSocket | null>(null);

  // 待处理的命令回调
  const pendingCmds = useRef<Map<string, {
    resolve: (v: ControlResponse) => void;
    reject: (e: Error) => void;
  }>>(new Map());

  // 存最新回调引用
  const onLogRef = useRef(onLog);
  const onSubtitleRef = useRef(onSubtitle);
  const onStateChangeRef = useRef(onStateChange);
  onLogRef.current = onLog;
  onSubtitleRef.current = onSubtitle;
  onStateChangeRef.current = onStateChange;

  const disconnect = useCallback(() => {
    [controlWs, logsWs, subtitleWs].forEach(ref => {
      if (ref.current) {
        ref.current.close();
        ref.current = null;
      }
    });
    setState('disconnected');
  }, []);

  // 连接 WS
  useEffect(() => {
    if (!port) return;

    setState('connecting');
    const base = `ws://127.0.0.1:${port}`;

    // Control WS
    const ctrl = new WebSocket(`${base}/ws/control`);
    ctrl.onopen = () => setState('connected');
    ctrl.onclose = () => setState('disconnected');
    ctrl.onerror = () => setState('error');
    ctrl.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as ControlResponse;
        if (msg.id && pendingCmds.current.has(msg.id)) {
          pendingCmds.current.get(msg.id)!.resolve(msg);
          pendingCmds.current.delete(msg.id);
        }
        // 状态变更推送
        if (msg.data && (msg.data as Record<string, unknown>).event === 'state_change') {
          onStateChangeRef.current?.(msg.data as Record<string, unknown>);
        }
      } catch { /* ignore */ }
    };
    controlWs.current = ctrl;

    // Logs WS
    const logs = new WebSocket(`${base}/ws/logs`);
    logs.onmessage = (ev) => {
      try {
        const entry = JSON.parse(ev.data) as LogEntry;
        onLogRef.current?.(entry);
      } catch { /* ignore */ }
    };
    logsWs.current = logs;

    // Subtitle WS
    const sub = new WebSocket(`${base}/ws/subtitle`);
    sub.onmessage = (ev) => {
      try {
        const entry = JSON.parse(ev.data) as SubtitleEntry;
        onSubtitleRef.current?.(entry);
      } catch { /* ignore */ }
    };
    subtitleWs.current = sub;

    return () => {
      ctrl.close();
      logs.close();
      sub.close();
    };
  }, [port]);

  // 发送命令
  const sendCommand = useCallback(
    (cmd: ControlCmd, payload: Record<string, unknown> = {}): Promise<ControlResponse> => {
      return new Promise((resolve, reject) => {
        if (!controlWs.current || controlWs.current.readyState !== WebSocket.OPEN) {
          reject(new Error('WebSocket 未连接'));
          return;
        }
        const id = crypto.randomUUID();
        pendingCmds.current.set(id, { resolve, reject });

        controlWs.current.send(JSON.stringify({ id, cmd, payload }));

        // 超时
        setTimeout(() => {
          if (pendingCmds.current.has(id)) {
            pendingCmds.current.get(id)!.reject(new Error(`命令 ${cmd} 超时`));
            pendingCmds.current.delete(id);
          }
        }, 30000);
      });
    },
    [],
  );

  return { state, sendCommand, disconnect };
}
