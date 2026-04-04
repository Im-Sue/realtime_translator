/**
 * 前后端 WebSocket 消息类型定义
 */

// ─── Control 命令 ─────────────────────────────────────────

export type ControlCmd =
  | 'load_config'
  | 'save_config'
  | 'scan_devices'
  | 'test_connection'
  | 'env_check'
  | 'start'
  | 'stop'
  | 'status';

export interface ControlRequest {
  id: string;
  cmd: ControlCmd;
  payload: Record<string, unknown>;
}

export interface ControlResponse {
  id: string;
  ok: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

// ─── 配置 ────────────────────────────────────────────────

export interface VolcengineConfig {
  ws_url: string;
  app_key: string;
  access_key: string;
  resource_id: string;
}

export interface AudioConfig {
  microphone: {
    device: string;
    sample_rate: number;
    channels: number;
    chunk_size: number;
  };
  system_audio: {
    device: string;
    fallback_device: string;
    sample_rate: number;
    channels: number;
    chunk_size: number;
  };
  vbcable_output: {
    device: string;
    sample_rate: number;
    target_format: string;
    use_ffmpeg: boolean;
    monitor_device: string | null;
    enable_monitor: boolean;
  };
}

export interface ChannelConfig {
  enabled: boolean;
  mode: string;
  source_language: string;
  target_language: string;
}

export interface SubtitleConfig {
  font_size: number;
  opacity: number;
  text_color: string;
}

export interface SubtitleConfigMessage extends SubtitleConfig {
  type: 'subtitle_config';
}

export interface AppConfig {
  volcengine: VolcengineConfig;
  audio: AudioConfig;
  channels: {
    zh_to_en: ChannelConfig;
    en_to_zh: ChannelConfig;
  };
  subtitle_window: SubtitleConfig;
}

// ─── 设备 ────────────────────────────────────────────────

export interface AudioDevice {
  index: number;
  name: string;
  hostapi: string;
  max_input_channels: number;
  max_output_channels: number;
  default_samplerate: number;
}

export interface DeviceScanResult {
  inputs: AudioDevice[];
  outputs: AudioDevice[];
  error?: string;
}

// ─── 运行状态 ─────────────────────────────────────────────

export interface RuntimeStatus {
  running: boolean;
  ch1: string;
  ch2: string;
  uptime: number;
}

// ─── 日志 ────────────────────────────────────────────────

export interface LogEntry {
  ts: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  channel: 'SYS' | 'CH1' | 'CH2';
  module: string;
  msg: string;
}

// ─── 字幕 ────────────────────────────────────────────────

export interface SubtitleEntry {
  type: 'start' | 'streaming' | 'end' | 'update' | 'flush';
  en: string;
  zh: string;
  is_final: boolean;
}
