/**
 * 日志页 — 实时日志流 + 筛选/搜索/导出
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import type { LogEntry } from '../types/ipc';

interface LogPageProps {
  logs: LogEntry[];
  onClear: () => void;
}

const LEVELS = ['全部', 'INFO', 'DEBUG', 'WARNING', 'ERROR'] as const;
const CHANNELS = ['全部', 'SYS', 'CH1', 'CH2'] as const;

export function LogPage({ logs, onClear }: LogPageProps) {
  const [levelFilter, setLevelFilter] = useState<string>('全部');
  const [channelFilter, setChannelFilter] = useState<string>('全部');
  const [search, setSearch] = useState('');
  const listRef = useRef<HTMLDivElement>(null);
  const autoScroll = useRef(true);

  // 过滤
  const filtered = logs.filter(entry => {
    if (levelFilter !== '全部' && entry.level !== levelFilter) return false;
    if (channelFilter !== '全部' && entry.channel !== channelFilter) return false;
    if (search && !entry.msg.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  // 自动滚底
  useEffect(() => {
    if (autoScroll.current && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [filtered.length]);

  const handleScroll = useCallback(() => {
    if (!listRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    autoScroll.current = scrollHeight - scrollTop - clientHeight < 40;
  }, []);

  // 导出
  const handleExport = () => {
    const text = filtered.map(e =>
      `${e.ts} [${e.level.padEnd(5)}] [${e.channel}] ${e.msg}`
    ).join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page-content" style={{ display: 'flex', flexDirection: 'column' }}>
      {/* 工具栏 */}
      <div className="log-toolbar">
        <div className="log-filter-group">
          {LEVELS.map(lv => (
            <button
              key={lv}
              className={`log-filter-btn ${levelFilter === lv ? 'log-filter-btn--active' : ''}`}
              onClick={() => setLevelFilter(lv)}
            >
              {lv}
            </button>
          ))}
        </div>
        <div className="log-filter-group">
          {CHANNELS.map(ch => (
            <button
              key={ch}
              className={`log-filter-btn ${channelFilter === ch ? 'log-filter-btn--active' : ''}`}
              onClick={() => setChannelFilter(ch)}
            >
              {ch}
            </button>
          ))}
        </div>
        <input
          className="form-input log-search"
          placeholder="搜索日志..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button className="btn btn--ghost btn--sm" onClick={onClear}>清空</button>
        <button className="btn btn--ghost btn--sm" onClick={handleExport}>导出</button>
      </div>

      {/* 日志列表 */}
      <div className="log-list" ref={listRef} onScroll={handleScroll}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
            暂无日志
          </div>
        ) : (
          filtered.map((entry, i) => (
            <div className="log-entry" key={i}>
              <span className="log-entry__ts">{entry.ts}</span>
              <span className={`log-entry__level log-entry__level--${entry.level}`}>
                [{entry.level}]
              </span>
              <span className="log-entry__channel">[{entry.channel}]</span>
              <span className="log-entry__msg">{entry.msg}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
