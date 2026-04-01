import {
  createSubtitleFlowState,
  reduceSubtitleFlow,
  buildDisplayText,
} from '../src/components/subtitleFlow';

function assertEqual<T>(actual: T, expected: T) {
  if (actual !== expected) {
    throw new Error(`Expected ${String(expected)}, got ${String(actual)}`);
  }
}

function testParagraphSplitAndHistoryTrim() {
  let state = createSubtitleFlowState();

  for (let index = 0; index < 101; index += 1) {
    state = reduceSubtitleFlow(
      state,
      { type: 'streaming', en: `Sentence ${index}`, zh: `第${index}句`, is_final: false },
      { now: index * 1000, paragraphCharLimit: 8, paragraphBreakMs: 5000, maxParagraphs: 100 },
    );
    state = reduceSubtitleFlow(
      state,
      { type: 'end', en: `Sentence ${index}`, zh: `第${index}句`, is_final: true },
      { now: index * 1000 + 1, paragraphCharLimit: 8, paragraphBreakMs: 5000, maxParagraphs: 100 },
    );
  }

  assertEqual(state.paragraphs.length, 100);
  assertEqual(state.paragraphs[0]?.en, 'Sentence 1');
  assertEqual(state.paragraphs[99]?.zh, '第100句');
}

function testStartCommitsPreviousStreamingAndGapCreatesNewParagraph() {
  let state = createSubtitleFlowState();

  state = reduceSubtitleFlow(
    state,
    { type: 'streaming', en: 'Hello', zh: '你好', is_final: false },
    { now: 1000 },
  );
  state = reduceSubtitleFlow(
    state,
    { type: 'end', en: 'Hello', zh: '你好', is_final: true },
    { now: 1200 },
  );
  state = reduceSubtitleFlow(
    state,
    { type: 'start', en: '', zh: '', is_final: false },
    { now: 7000, paragraphBreakMs: 5000 },
  );

  assertEqual(state.paragraphs.length, 1);
  assertEqual(state.paragraphs[0]?.en, 'Hello');
  assertEqual(state.paragraphs[0]?.zh, '你好');
  assertEqual(state.currentEn, '');
  assertEqual(state.streamingEn, '');
}

function testBuildDisplayTextHandlesEnglishSpacingAndChineseConcatenation() {
  assertEqual(buildDisplayText('How are', 'you', true), 'How are you');
  assertEqual(buildDisplayText('你好', '世界', false), '你好世界');
}

function run() {
  testParagraphSplitAndHistoryTrim();
  testStartCommitsPreviousStreamingAndGapCreatesNewParagraph();
  testBuildDisplayTextHandlesEnglishSpacingAndChineseConcatenation();
  console.log('subtitleFlow tests passed');
}

run();
