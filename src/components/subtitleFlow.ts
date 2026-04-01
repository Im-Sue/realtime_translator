import type { SubtitleEntry } from '../types/ipc';

export interface SubtitleParagraph {
  en: string;
  zh: string;
}

export interface SubtitleFlowState {
  paragraphs: SubtitleParagraph[];
  currentEn: string;
  currentZh: string;
  streamingEn: string;
  streamingZh: string;
  lastEventAt: number;
  lastEndAt: number;
}

export interface SubtitleFlowOptions {
  now?: number;
  paragraphCharLimit?: number;
  paragraphBreakMs?: number;
  maxParagraphs?: number;
}

const DEFAULT_PARAGRAPH_CHAR_LIMIT = 150;
const DEFAULT_PARAGRAPH_BREAK_MS = 5000;
const DEFAULT_MAX_PARAGRAPHS = 100;

export function createSubtitleFlowState(): SubtitleFlowState {
  return {
    paragraphs: [],
    currentEn: '',
    currentZh: '',
    streamingEn: '',
    streamingZh: '',
    lastEventAt: 0,
    lastEndAt: 0,
  };
}

function normalizeText(text: string, isEnglish: boolean): string {
  const trimmed = text.trim();
  if (!trimmed) {
    return '';
  }
  return isEnglish ? trimmed.replace(/\s+/g, ' ') : trimmed.replace(/\s+/g, '');
}

function appendCompletedText(base: string, addition: string, isEnglish: boolean): string {
  const next = normalizeText(addition, isEnglish);
  if (!next) {
    return base;
  }
  if (!base) {
    return next;
  }
  return isEnglish ? `${base} ${next}` : `${base}${next}`;
}

function trimParagraphs(paragraphs: SubtitleParagraph[], maxParagraphs: number): SubtitleParagraph[] {
  if (paragraphs.length <= maxParagraphs) {
    return paragraphs;
  }
  return paragraphs.slice(paragraphs.length - maxParagraphs);
}

function pushParagraph(state: SubtitleFlowState, maxParagraphs: number): SubtitleFlowState {
  if (!state.currentEn && !state.currentZh) {
    return state;
  }

  return {
    ...state,
    paragraphs: trimParagraphs(
      [...state.paragraphs, { en: state.currentEn, zh: state.currentZh }],
      maxParagraphs,
    ),
    currentEn: '',
    currentZh: '',
  };
}

function commitStreaming(state: SubtitleFlowState): SubtitleFlowState {
  return {
    ...state,
    currentEn: appendCompletedText(state.currentEn, state.streamingEn, true),
    currentZh: appendCompletedText(state.currentZh, state.streamingZh, false),
    streamingEn: '',
    streamingZh: '',
  };
}

function maybeSplitParagraph(
  state: SubtitleFlowState,
  paragraphCharLimit: number,
  maxParagraphs: number,
): SubtitleFlowState {
  const longestLength = Math.max(state.currentEn.length, state.currentZh.length);
  if (longestLength < paragraphCharLimit) {
    return state;
  }
  return pushParagraph(state, maxParagraphs);
}

export function buildDisplayText(base: string, streaming: string, isEnglish: boolean): string {
  const normalizedBase = normalizeText(base, isEnglish);
  const normalizedStreaming = normalizeText(streaming, isEnglish);

  if (!normalizedBase) {
    return normalizedStreaming;
  }
  if (!normalizedStreaming) {
    return normalizedBase;
  }
  return isEnglish ? `${normalizedBase} ${normalizedStreaming}` : `${normalizedBase}${normalizedStreaming}`;
}

export function reduceSubtitleFlow(
  prevState: SubtitleFlowState,
  entry: SubtitleEntry,
  options: SubtitleFlowOptions = {},
): SubtitleFlowState {
  const now = options.now ?? Date.now();
  const paragraphCharLimit = options.paragraphCharLimit ?? DEFAULT_PARAGRAPH_CHAR_LIMIT;
  const paragraphBreakMs = options.paragraphBreakMs ?? DEFAULT_PARAGRAPH_BREAK_MS;
  const maxParagraphs = options.maxParagraphs ?? DEFAULT_MAX_PARAGRAPHS;

  let state: SubtitleFlowState = {
    ...prevState,
    lastEventAt: now,
  };

  switch (entry.type) {
    case 'start': {
      state = commitStreaming(state);

      const hasCurrentParagraph = Boolean(state.currentEn || state.currentZh);
      const isLongGap = Boolean(state.lastEndAt) && (now - state.lastEndAt) > paragraphBreakMs;
      if (hasCurrentParagraph && isLongGap) {
        state = pushParagraph(state, maxParagraphs);
      }
      return state;
    }
    case 'streaming':
    case 'update':
      return {
        ...state,
        streamingEn: normalizeText(entry.en ?? '', true),
        streamingZh: normalizeText(entry.zh ?? '', false),
      };
    case 'end':
    case 'flush': {
      state = {
        ...commitStreaming({
          ...state,
          streamingEn: normalizeText(entry.en ?? state.streamingEn, true),
          streamingZh: normalizeText(entry.zh ?? state.streamingZh, false),
        }),
        lastEndAt: now,
      };
      return maybeSplitParagraph(state, paragraphCharLimit, maxParagraphs);
    }
    default:
      return state;
  }
}
