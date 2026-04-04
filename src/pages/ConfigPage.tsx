/**
 * 配置页 — 折叠面板布局
 */

import { useState, useEffect, useCallback } from 'react';
import type { AppConfig, DeviceScanResult, ControlCmd, ControlResponse } from '../types/ipc';

interface ConfigPageProps {
  running: boolean;
  sendCommand: (cmd: ControlCmd, payload?: Record<string, unknown>) => Promise<ControlResponse>;
}

// ─── 折叠面板 ──────────────────────────────────────────────

function CollapsePanel({
  title,
  icon,
  defaultOpen = false,
  children,
}: {
  title: string;
  icon: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="collapse-panel">
      <button className="collapse-panel__header" onClick={() => setOpen(!open)}>
        <span className="collapse-panel__title">
          <span>{icon}</span>
          <span>{title}</span>
        </span>
        <span className={`collapse-panel__arrow ${open ? 'collapse-panel__arrow--open' : ''}`}>
          ▶
        </span>
      </button>
      {open && <div className="collapse-panel__body">{children}</div>}
    </div>
  );
}

// ─── Toggle ────────────────────────────────────────────────

function Toggle({
  value,
  onChange,
  disabled,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      className={`toggle ${value ? 'toggle--on' : ''}`}
      onClick={() => onChange(!value)}
      disabled={disabled}
    >
      <span className="toggle__thumb" />
    </button>
  );
}

// ─── 配置页主体 ─────────────────────────────────────────────

export function ConfigPage({ running, sendCommand }: ConfigPageProps) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [devices, setDevices] = useState<DeviceScanResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const disabled = running;

  // 加载配置
  useEffect(() => {
    sendCommand('load_config').then(res => {
      if (res.ok && res.data) setConfig(res.data as unknown as AppConfig);
    }).catch(() => {});
  }, [sendCommand]);

  // 扫描设备
  const scanDevices = useCallback(async () => {
    const res = await sendCommand('scan_devices');
    if (res.ok && res.data) setDevices(res.data as unknown as DeviceScanResult);
  }, [sendCommand]);

  useEffect(() => { scanDevices(); }, [scanDevices]);

  // 保存配置
  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await sendCommand('save_config', { config });
    } finally {
      setSaving(false);
    }
  };

  // 测试连接
  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await sendCommand('test_connection');
      setTestResult(res.ok ? '✅ 连接成功' : `❌ ${res.error || '连接失败'}`);
    } catch (e) {
      setTestResult(`❌ ${e}`);
    } finally {
      setTesting(false);
    }
  };

  // 更新配置字段
  const updateField = (path: string, value: unknown) => {
    if (!config) return;
    const newConfig = JSON.parse(JSON.stringify(config));
    const parts = path.split('.');
    let obj = newConfig;
    for (let i = 0; i < parts.length - 1; i++) {
      obj = obj[parts[i]];
    }
    obj[parts[parts.length - 1]] = value;
    setConfig(newConfig);
  };

  if (!config) {
    return (
      <div className="connect-overlay">
        <div className="connect-overlay__spinner" />
        <span>加载配置中...</span>
      </div>
    );
  }

  return (
    <div className="page-content">
      {/* 火山引擎凭据 */}
      <CollapsePanel title="火山引擎凭据" icon="🔑" defaultOpen>
        <div className="form-row">
          <label className="form-label">WebSocket</label>
          <input
            className="form-input"
            value={config.volcengine?.ws_url || ''}
            onChange={e => updateField('volcengine.ws_url', e.target.value)}
            disabled={disabled}
            placeholder="wss://openspeech.bytedance.com/..."
          />
        </div>
        <div className="form-row">
          <label className="form-label">App Key</label>
          <input
            className="form-input"
            value={config.volcengine?.app_key || ''}
            onChange={e => updateField('volcengine.app_key', e.target.value)}
            disabled={disabled}
          />
        </div>
        <div className="form-row">
          <label className="form-label">Access Key</label>
          <input
            className="form-input"
            type="password"
            value={config.volcengine?.access_key || ''}
            onChange={e => updateField('volcengine.access_key', e.target.value)}
            disabled={disabled}
          />
        </div>
        <div className="form-row">
          <label className="form-label">Resource ID</label>
          <input
            className="form-input"
            value={config.volcengine?.resource_id || ''}
            onChange={e => updateField('volcengine.resource_id', e.target.value)}
            disabled={disabled}
          />
        </div>
        <div className="form-row" style={{ justifyContent: 'flex-end' }}>
          <button
            className="btn btn--ghost btn--sm"
            disabled={disabled || testing}
            onClick={handleTestConnection}
          >
            {testing ? '测试中...' : '测试连接'}
          </button>
          {testResult && <span style={{ fontSize: 12 }}>{testResult}</span>}
        </div>
      </CollapsePanel>

      {/* 音频设备 */}
      <CollapsePanel title="音频设备" icon="🎤">
        <div className="form-row">
          <label className="form-label">麦克风</label>
          <select
            className="form-select"
            value={config.audio?.microphone?.device || ''}
            onChange={e => updateField('audio.microphone.device', e.target.value)}
            disabled={disabled}
          >
            <option value="">选择设备...</option>
            {devices?.inputs?.map(d => (
              <option key={d.index} value={d.name}>{d.name}</option>
            ))}
          </select>
          <button className="btn btn--ghost btn--icon" onClick={scanDevices} disabled={disabled} title="刷新设备">
            🔄
          </button>
        </div>
        <div className="form-row">
          <label className="form-label">系统音频</label>
          <select
            className="form-select"
            value={config.audio?.system_audio?.device || ''}
            onChange={e => updateField('audio.system_audio.device', e.target.value)}
            disabled={disabled}
          >
            <option value="">选择设备...</option>
            {devices?.inputs?.map(d => (
              <option key={d.index} value={d.name}>{d.name}</option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label className="form-label">回退设备</label>
          <select
            className="form-select"
            value={config.audio?.system_audio?.fallback_device || ''}
            onChange={e => updateField('audio.system_audio.fallback_device', e.target.value)}
            disabled={disabled}
          >
            <option value="">选择设备...</option>
            {devices?.inputs?.map(d => (
              <option key={d.index} value={d.name}>{d.name}</option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label className="form-label">输出设备</label>
          <select
            className="form-select"
            value={config.audio?.vbcable_output?.device || ''}
            onChange={e => updateField('audio.vbcable_output.device', e.target.value)}
            disabled={disabled}
          >
            <option value="">选择设备...</option>
            {devices?.outputs?.map(d => (
              <option key={d.index} value={d.name}>{d.name}</option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label className="form-label">&nbsp;</label>
          <label className="form-checkbox">
            <input
              type="checkbox"
              checked={config.audio?.vbcable_output?.use_ffmpeg ?? true}
              onChange={e => updateField('audio.vbcable_output.use_ffmpeg', e.target.checked)}
              disabled={disabled}
            />
            FFmpeg 解码
          </label>
        </div>
        <div className="form-row">
          <label className="form-label">输出格式</label>
          <input
            className="form-input"
            value={config.audio?.vbcable_output?.target_format || 'pcm'}
            onChange={e => updateField('audio.vbcable_output.target_format', e.target.value)}
            disabled={disabled}
            placeholder="pcm"
          />
        </div>
        <div className="form-row">
          <label className="form-label">输出采样率</label>
          <input
            className="form-input"
            type="number"
            value={config.audio?.vbcable_output?.sample_rate ?? 48000}
            onChange={e => updateField('audio.vbcable_output.sample_rate', Number(e.target.value))}
            disabled={disabled}
            style={{ maxWidth: 120 }}
          />
          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
            CH1 PCM 直出建议保持 48000Hz
          </span>
        </div>
      </CollapsePanel>

      {/* 翻译通道 */}
      <CollapsePanel title="翻译通道" icon="🔄">
        <div className="form-row">
          <label className="form-label">CH1 中→英</label>
          <Toggle
            value={config.channels?.zh_to_en?.enabled ?? true}
            onChange={v => updateField('channels.zh_to_en.enabled', v)}
            disabled={disabled}
          />
          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
            模式: {config.channels?.zh_to_en?.mode || 's2s'}
          </span>
        </div>
        <div className="form-row">
          <label className="form-label">CH2 英→中</label>
          <Toggle
            value={config.channels?.en_to_zh?.enabled ?? true}
            onChange={v => updateField('channels.en_to_zh.enabled', v)}
            disabled={disabled}
          />
          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
            模式: {config.channels?.en_to_zh?.mode || 's2t'}
          </span>
        </div>
      </CollapsePanel>

      {/* 字幕设置 */}
      <CollapsePanel title="字幕设置" icon="💬">
        <div className="form-row">
          <label className="form-label">字号</label>
          <input
            className="form-input"
            type="number"
            value={config.subtitle_window?.font_size ?? 20}
            onChange={e => updateField('subtitle_window.font_size', Number(e.target.value))}
            disabled={disabled}
            style={{ maxWidth: 80 }}
          />
          <label className="form-label">透明度</label>
          <input
            className="form-input"
            type="number"
            step={0.05}
            min={0}
            max={1}
            value={config.subtitle_window?.opacity ?? 0.85}
            onChange={e => updateField('subtitle_window.opacity', Number(e.target.value))}
            disabled={disabled}
            style={{ maxWidth: 80 }}
          />
        </div>
        <div className="form-row">
          <label className="form-label">文字色</label>
          <input
            className="form-input"
            type="color"
            value={config.subtitle_window?.text_color || '#FFFFFF'}
            onChange={e => updateField('subtitle_window.text_color', e.target.value)}
            disabled={disabled}
            style={{ maxWidth: 60, padding: 2 }}
          />
        </div>
      </CollapsePanel>

      {/* 保存 */}
      <div className="save-bar">
        <button
          className="btn btn--primary"
          disabled={disabled || saving}
          onClick={handleSave}
        >
          {saving ? '保存中...' : '保存配置'}
        </button>
      </div>
    </div>
  );
}
