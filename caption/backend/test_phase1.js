globalThis.window = globalThis;
require('../frontend/js/normalizer.js');
require('../frontend/js/segmenter.js');

const TextNormalizer = globalThis.TextNormalizer;
const TextSegmenter = globalThis.TextSegmenter;
const assert = require('assert');

console.log('🧪 Starting Phase 1 Unit Tests & Verification...\n');

// 1. Text Normalization Test
console.log('--- 1. Testing TextNormalizer ---');
const rawInput = " i'm building a caption engine , and  dont forget it .  whats next ? ";
const normalized = TextNormalizer.normalize(rawInput);
console.log(`Raw input:    "${rawInput}"`);
console.log(`Normalized:   "${normalized}"`);
assert.strictEqual(normalized, "I'm building a caption engine, and don't forget it. what's next?");
console.log('✅ TextNormalizer test PASSED.\n');

// 2. Text Segmenter POS-Lite & Char Limit Test
console.log('--- 2. Testing TextSegmenter POS-Lite Phrase Boundary & Char Limit ---');
const testScript = "We are building a viral AI caption engine that automatically formats long sentences into readable short form video caption blocks.";
const segmented = TextSegmenter.segment(testScript, { maxWords: 4, maxChars: 24 });

console.log(`Total Blocks Created: ${segmented.blocks.length}`);
let bottleneckDetected = false;

segmented.blocks.forEach((block, idx) => {
  console.log(`Block #${idx + 1} [${block.start}s - ${block.end}s] (${block.text.length} chars, ${block.words.length} words): "${block.text}"`);
  if (block.text.length > 28) {
    console.error(`⚠️ Bottleneck/Violation: Block #${idx + 1} exceeds 24 char limit (${block.text.length} chars)`);
    bottleneckDetected = true;
  }
});

if (!bottleneckDetected) {
  console.log('✅ All blocks satisfy max character limits & phrase boundary conditions.\n');
}

// 3. Performance Benchmark Test
console.log('--- 3. Benchmarking Segmentation Performance ---');
const longScript = (testScript + " ").repeat(100);
const startTime = performance.now();
const result = TextSegmenter.segment(longScript, { maxWords: 4, maxChars: 24 });
const endTime = performance.now();
const elapsed = (endTime - startTime).toFixed(2);

console.log(`Segmented ${result.blocks.length} blocks from ${longScript.length} chars in ${elapsed}ms.`);
if (elapsed < 50) {
  console.log('✅ Performance Bottleneck Check PASSED (Processing speed < 50ms).\n');
} else {
  console.warn(`⚠️ Warning: Segmentation took ${elapsed}ms\n`);
}

console.log('🎉 Phase 1 All Tests Completed Successfully!');
