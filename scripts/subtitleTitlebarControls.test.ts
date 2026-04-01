import {
  buildOverlayResizeTarget,
  COMPACT_OVERLAY_HEIGHT,
  DEFAULT_OVERLAY_HEIGHT,
  getOverlayToggleMeta,
} from '../src/components/subtitleTitlebarControls';

function assertEqual<T>(actual: T, expected: T) {
  if (actual !== expected) {
    throw new Error(`Expected ${String(expected)}, got ${String(actual)}`);
  }
}

function testBuildOverlayResizeTargetPreservesLogicalWidth() {
  const target = buildOverlayResizeTarget('compact', 1500, 1.5);
  assertEqual(target.width, 1000);
  assertEqual(target.height, COMPACT_OVERLAY_HEIGHT);
}

function testBuildOverlayResizeTargetFallsBackToDefaultHeight() {
  const target = buildOverlayResizeTarget('default', 1000, 0);
  assertEqual(target.width, 1000);
  assertEqual(target.height, DEFAULT_OVERLAY_HEIGHT);
}

function testGetOverlayToggleMetaReturnsExpectedLabelAndMode() {
  const expandedMeta = getOverlayToggleMeta(true);
  assertEqual(expandedMeta.label, '收起字幕');
  assertEqual(expandedMeta.nextMode, 'compact');

  const collapsedMeta = getOverlayToggleMeta(false);
  assertEqual(collapsedMeta.label, '展开字幕');
  assertEqual(collapsedMeta.nextMode, 'default');
}

function run() {
  testBuildOverlayResizeTargetPreservesLogicalWidth();
  testBuildOverlayResizeTargetFallsBackToDefaultHeight();
  testGetOverlayToggleMetaReturnsExpectedLabelAndMode();
  console.log('subtitleTitlebarControls tests passed');
}

run();
