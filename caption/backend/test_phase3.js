globalThis.window = globalThis;
require('../frontend/js/normalizer.js');
require('../frontend/js/segmenter.js');

const assert = require('assert');

console.log('🧪 Starting Phase 3 Modular Style & Animation Engine Unit Tests...\n');

// Mock HTML5 Canvas context for node environment testing
class MockCanvasContext {
  constructor() {
    this.font = '';
    this.fillStyle = '';
    this.strokeStyle = '';
    this.lineWidth = 1;
    this.textAlign = 'center';
    this.textBaseline = 'middle';
    this.shadowColor = '';
    this.shadowBlur = 0;
  }
  measureText(text) {
    return { width: (text || '').length * 15 };
  }
  clearRect() {}
  fillRect() {}
  save() {}
  restore() {}
  translate() {}
  rotate() {}
  scale() {}
  beginPath() {}
  ellipse() {}
  fill() {}
  stroke() {}
  rect() {}
  arc() {}
  moveTo() {}
  lineTo() {}
  closePath() {}
  strokeText() {}
  fillText() {}
  clip() {}
}

const mockCanvas = {
  getContext: () => new MockCanvasContext(),
  width: 1080,
  height: 1920
};

// Require renderer
require('../frontend/js/renderer.js');
const RendererClass = globalThis.LightningComicRenderer;

assert.ok(RendererClass, 'LightningComicRenderer class should be defined');
const renderer = new RendererClass(mockCanvas, null);

console.log('--- 1. Testing Color Tag Palette Mapping ---');
assert.strictEqual(renderer.getWordHighlightColor({ word: '$10,000' }, 'money'), '#22C55E');
assert.strictEqual(renderer.getWordHighlightColor({ word: 'STOP' }, 'warning'), '#EF4444');
assert.strictEqual(renderer.getWordHighlightColor({ word: 'SECRET' }, 'highlight'), '#EAB308');
assert.strictEqual(renderer.getWordHighlightColor({ word: 'WHY' }, 'question'), '#3B82F6');
assert.strictEqual(renderer.getWordHighlightColor({ word: 'HELLO' }, 'neutral'), '#FFE600');
console.log('✅ Color Tag Palette Mapping test PASSED.\n');

console.log('--- 2. Testing Render Frame Execution with Phase 2 Director Annotations ---');
const sampleCaptionData = {
  version: '2.0',
  styleId: 'lightning-comic',
  layout: { x: 0.5, y: 0.52, scale: 1.0, rotation: -6 },
  blocks: [
    {
      id: 'block_001',
      text: 'MAKE $10,000 THIS MONTH',
      start: 0.0,
      end: 1.5,
      colorTag: 'money',
      emoji: '💰',
      sfx: 'cash',
      emphasisWords: ['$10,000'],
      words: [
        { word: 'MAKE', start: 0.0, end: 0.3, isEmphasis: false },
        { word: '$10,000', start: 0.35, end: 0.8, isEmphasis: true },
        { word: 'THIS', start: 0.85, end: 1.1, isEmphasis: false },
        { word: 'MONTH', start: 1.15, end: 1.5, isEmphasis: false }
      ]
    }
  ]
};

const boxMeta = renderer.render(sampleCaptionData, 0.5);
console.log('Render output bounding box metadata:', boxMeta);
assert.ok(boxMeta && boxMeta.widthPx > 0, 'Render output should return valid bounding box meta');
console.log('✅ Render Frame Execution test PASSED.\n');

console.log('🎉 Phase 3 Modular Style Engine Tests Completed Successfully!');
