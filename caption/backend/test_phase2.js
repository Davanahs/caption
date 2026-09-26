globalThis.window = globalThis;
require('../frontend/js/normalizer.js');
require('../frontend/js/segmenter.js');
require('./server.js');

const TextNormalizer = globalThis.TextNormalizer;
const TextSegmenter = globalThis.TextSegmenter;
const assert = require('assert');
const http = require('http');

console.log('🧪 Starting Phase 2 Unit Tests & LLM Caption Director Pass Verification...\n');

const rawScript = "Make $10,000 this month with this secret AI shortcut. Stop doing it manually and scale your revenue fast!";
const normalized = TextNormalizer.normalize(rawScript);
const segmented = TextSegmenter.segment(normalized, { maxWords: 4, maxChars: 24 });

console.log(`Generated ${segmented.blocks.length} initial blocks for Director Pass testing.`);

setTimeout(() => {
  const postData = JSON.stringify({ blocks: segmented.blocks });

  const req = http.request({
    hostname: 'localhost',
    port: 5000,
    path: '/api/caption/director-pass',
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
        console.log(`\n--- Director Pass Response (Duration: ${response.durationMs}ms) ---`);
        assert.strictEqual(response.success, true);
        assert.ok(response.blocks && response.blocks.length > 0);

        response.blocks.forEach((b, idx) => {
          console.log(`Block #${idx + 1}: "${b.text}"`);
          console.log(`  └─ colorTag: "${b.colorTag}" | emoji: "${b.emoji || 'none'}" | sfx: "${b.sfx || 'none'}" | emphasisWords: [${(b.emphasisWords || []).join(', ')}]`);
        });

        console.log('\n✅ Phase 2 LLM Caption Director Pass Test PASSED.');
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
