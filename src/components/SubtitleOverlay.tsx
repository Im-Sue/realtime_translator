/**
 * 字幕浮窗内容组件
 *
 * 渲染在独立的 subtitle-overlay 窗口中，
 * 显示 EN/ZH 双行字幕，支持拖拽和动效。
 */

import { useState, useEffect, useRef } from 'react';
import { LogicalSize } from '@tauri-apps/api/dpi';
import { getCurrentWindow } from '@tauri-apps/api/window';
import type { SubtitleEntry, SubtitleConfig } from '../types/ipc';
import {
  buildDisplayText,
  createSubtitleFlowState,
  reduceSubtitleFlow,
  type SubtitleFlowState,
} from './subtitleFlow';
import {
  buildOverlayResizeTarget,
  getOverlayToggleMeta,
} from './subtitleTitlebarControls';


const DEFAULT_SUBTITLE_CONFIG: SubtitleConfig = {
  font_size: 16,
  opacity: 0.85,
  text_color: '#FFFFFF',
};

/** 将 hex 颜色 + opacity 转为 rgba 字符串 */
function hexToRgba(hex: string, opacity: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

export function SubtitleOverlay() {
  const [wsPort, setWsPort] = useState<number | null>(null);
  const [idle, setIdle] = useState(true);
  const [expanded, setExpanded] = useState(true);
  const [config, setConfig] = useState<SubtitleConfig>(DEFAULT_SUBTITLE_CONFIG);
  const [flowState, setFlowState] = useState<SubtitleFlowState>(() => createSubtitleFlowState());
  const idleTimer = useRef<number | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // 从 URL 参数或 Tauri 事件获取端口
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const p = params.get('port');
    if (p) {
      setWsPort(Number(p));
      return;
    }

    // 监听 Tauri 事件
    const setupListener = async () => {
      try {
        const { listen } = await import('@tauri-apps/api/event');
        const unlisten = await listen<{ port: number }>('sidecar-ready', (ev) => {
          setWsPort(ev.payload.port);
        });
        return unlisten;
      } catch {
        // 非 Tauri 环境
      }
    };
    const p2 = setupListener();
    return () => { p2.then(fn => fn?.()); };
  }, []);

  // 连接字幕 WS
  useEffect(() => {
    if (!wsPort) return;

    const ws = new WebSocket(`ws://127.0.0.1:${wsPort}/ws/subtitle`);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);

        if (data.type === 'subtitle_config') {
          setConfig({
            font_size: data.font_size ?? DEFAULT_SUBTITLE_CONFIG.font_size,
            opacity: data.opacity ?? DEFAULT_SUBTITLE_CONFIG.opacity,
            text_color: data.text_color ?? DEFAULT_SUBTITLE_CONFIG.text_color,
          });
          return;
        }

        const entry: SubtitleEntry = data;
        setFlowState(prev => reduceSubtitleFlow(prev, entry, { now: Date.now() }));
        setIdle(false);

        // 静默超时
        if (idleTimer.current !== null) clearTimeout(idleTimer.current);
        idleTimer.current = window.setTimeout(() => setIdle(true), 5000);
      } catch { /* ignore */ }
    };

    return () => {
      ws.close();
      if (idleTimer.current !== null) clearTimeout(idleTimer.current);
    };
  }, [wsPort]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    container.scrollTo({
      top: container.scrollHeight,
      behavior: 'smooth',
    });
  }, [
    flowState.paragraphs,
    flowState.currentEn,
    flowState.currentZh,
    flowState.streamingEn,
    flowState.streamingZh,
  ]);

  const enStyle: React.CSSProperties = {
    fontSize: `${config.font_size - 2}px`,
    color: hexToRgba(config.text_color, 0.7),
  };

  const zhStyle: React.CSSProperties = {
    fontSize: `${config.font_size}px`,
    color: config.text_color,
  };
  const toggleMeta = getOverlayToggleMeta(expanded);

  const currentEnText = buildDisplayText(flowState.currentEn, '', true);
  const currentZhText = buildDisplayText(flowState.currentZh, '', false);
  const hasContent = Boolean(
    flowState.paragraphs.length
    || currentEnText
    || currentZhText
    || flowState.streamingEn
    || flowState.streamingZh,
  );

  const renderCurrentLine = (
    completed: string,
    streaming: string,
    isEnglish: boolean,
    className: string,
    style: React.CSSProperties,
  ) => {
    if (!completed && !streaming) {
      return null;
    }

    return (
      <div className={className} style={style}>
        {completed && <span>{completed}</span>}
        {streaming && (
          <span className="subtitle-line__tail subtitle-line--streaming">
            {isEnglish && completed ? ` ${streaming}` : streaming}
          </span>
        )}
      </div>
    );
  };

  const resizeOverlayWindow = async (mode: 'compact' | 'default') => {
    try {
      const currentWindow = getCurrentWindow();
      const [innerSize, scaleFactor] = await Promise.all([
        currentWindow.innerSize(),
        currentWindow.scaleFactor(),
      ]);
      const targetSize = buildOverlayResizeTarget(mode, innerSize.width, scaleFactor);
      await currentWindow.setSize(new LogicalSize(targetSize.width, targetSize.height));
    } catch {
      // 非 Tauri 环境或权限不足时静默失败，避免影响字幕显示。
    }
  };

  const toggleOverlayWindowHeight = async () => {
    await resizeOverlayWindow(toggleMeta.nextMode);
    setExpanded(toggleMeta.nextExpanded);
  };

  const hideOverlayWindow = async () => {
    try {
      await getCurrentWindow().hide();
    } catch {
      // 非 Tauri 环境或权限不足时静默失败，避免影响字幕显示。
    }
  };

  return (
    <div
      className={`subtitle-overlay ${idle ? 'subtitle-overlay--idle' : 'subtitle-overlay--active'}`}
    >
      <div className="subtitle-titlebar">
        <div
          className="subtitle-titlebar__drag"
          data-tauri-drag-region
          aria-hidden="true"
        />
        <div className="subtitle-titlebar__actions">
          <button
            type="button"
            className="subtitle-titlebar__button subtitle-titlebar__button--text"
            aria-label={toggleMeta.label}
            title={toggleMeta.label}
            onClick={() => void toggleOverlayWindowHeight()}
          >
            {toggleMeta.label}
          </button>
          <button
            type="button"
            className="subtitle-titlebar__button subtitle-titlebar__button--close"
            aria-label="Hide subtitle window"
            title="Hide subtitle window"
            onClick={() => void hideOverlayWindow()}
          >
            ×
          </button>
        </div>
      </div>
      <div
        className="subtitle-lines"
        ref={scrollRef}
      >
        {flowState.paragraphs.map((paragraph, index) => (
          <div className="subtitle-paragraph" key={`paragraph-${index}`}>
            {paragraph.en && <div className="subtitle-line subtitle-line--en" style={enStyle}>{paragraph.en}</div>}
            {paragraph.zh && <div className="subtitle-line subtitle-line--zh" style={zhStyle}>{paragraph.zh}</div>}
          </div>
        ))}

        {(currentEnText || currentZhText || flowState.streamingEn || flowState.streamingZh) && (
          <div className="subtitle-paragraph subtitle-paragraph--current">
            {renderCurrentLine(
              currentEnText,
              flowState.streamingEn,
              true,
              'subtitle-line subtitle-line--en',
              enStyle,
            )}
            {renderCurrentLine(
              currentZhText,
              flowState.streamingZh,
              false,
              'subtitle-line subtitle-line--zh',
              zhStyle,
            )}
          </div>
        )}

        {!hasContent && (
          <div className="subtitle-line subtitle-line--zh" style={{ ...zhStyle, opacity: 0.6 }}>
            等待字幕...
          </div>
        )}
      </div>
    </div>
  );
}
