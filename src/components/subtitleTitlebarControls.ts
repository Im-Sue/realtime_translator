export type OverlayResizeMode = 'compact' | 'default';

export const DEFAULT_OVERLAY_HEIGHT = 300;
export const COMPACT_OVERLAY_HEIGHT = 150;

export interface OverlayResizeTarget {
  width: number;
  height: number;
}

export interface OverlayToggleMeta {
  label: '收起字幕' | '展开字幕';
  nextMode: OverlayResizeMode;
  nextExpanded: boolean;
}

export function buildOverlayResizeTarget(
  mode: OverlayResizeMode,
  innerWidthPhysical: number,
  scaleFactor: number,
): OverlayResizeTarget {
  const safeScaleFactor = scaleFactor > 0 ? scaleFactor : 1;
  const logicalWidth = innerWidthPhysical / safeScaleFactor;

  return {
    width: logicalWidth,
    height: mode === 'compact' ? COMPACT_OVERLAY_HEIGHT : DEFAULT_OVERLAY_HEIGHT,
  };
}

export function getOverlayToggleMeta(expanded: boolean): OverlayToggleMeta {
  if (expanded) {
    return {
      label: '收起字幕',
      nextMode: 'compact',
      nextExpanded: false,
    };
  }

  return {
    label: '展开字幕',
    nextMode: 'default',
    nextExpanded: true,
  };
}
