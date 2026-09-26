globalThis.window = globalThis;
require('../frontend/js/normalizer.js');
require('../frontend/js/segmenter.js');
require('./server.js');

const assert = require('assert');
const http = require('http');

console.log('🧪 Starting Phase 5 Proofreading Pass & Timestamp Re-mapping Unit Tests...\n');

const rawBlocksWithErrors = [
  {
    id: 'block_001',
    text: 'THEIR GOING TO WIN',
    start: 0.0,
    end: 1.5,
    words: [
      { word: 'THEIR', start: 0.0, end: 0.35 },
      { word: 'GOING', start: 0.4, end: 0.75 },
      { word: 'TO', start: 0.8, end: 1.05 },
      { word: 'WIN', start: 1.1, end: 1.5 }
    ]
  }
];

setTimeout(() => {
  const postData = JSON.stringify({ blocks: rawBlocksWithErrors });

  const req = http.request({
    hostname: 'localhost',
    port: 5000,
    path: '/api/caption/proofread',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(postData)
    }
  }, (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      try {
        const response = JSON.parse(data);
        console.log(`\n--- Proofreading Response (Duration: ${response.durationMs}ms) ---`);
        assert.strictEqual(response.success, true);
        assert.ok(response.blocks && response.blocks.length > 0);

        const correctedBlock = response.blocks[0];
        console.log(`Original:  "THEIR GOING TO WIN"`);
        console.log(`Corrected: "${correctedBlock.text}"`);

        // Check timestamp bounds preservation
        const firstWordStart = correctedBlock.words[0].start;
        const lastWordEnd = correctedBlock.words[correctedBlock.words.length - 1].end;

        console.log(`Timestamp Bounds Preserved: [${firstWordStart}s - ${lastWordEnd}s] (Target: [0s - 1.5s])`);
        assert.strictEqual(firstWordStart, 0.0);
        assert.strictEqual(lastWordEnd, 1.5);

        console.log('\n✅ Phase 5 Proofreading Pass & Timestamp Re-mapping Test PASSED.');
        process.exit(0);
      } catch (e) {
        console.error('❌ Failed to parse response:', e.message, data);
        process.exit(1);
      }
    });
  });

  req.on('error', (e) => {
    console.error('❌ Request error:', e.message);
    process.exit(1);
  });

  req.write(postData);
  req.end();
}, 1000);
