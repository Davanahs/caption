globalThis.window = globalThis;
require('../frontend/js/normalizer.js');
require('../frontend/js/segmenter.js');
require('./server.js');

const assert = require('assert');
const http = require('http');

console.log('🧪 Starting Phase 4 Audio Cleanup & Silence Trimming Unit Tests...\n');

// Sample blocks with filler words ("um", "uh", "like") and silence gaps
const sampleAudioBlocks = [
  {
    id: 'block_001',
    text: 'UM WE ARE BUILDING',
    start: 0.0,
    end: 1.2,
    words: [
      { word: 'UM', start: 0.0, end: 0.3 },
      { word: 'WE', start: 0.35, end: 0.6 },
      { word: 'ARE', start: 0.65, end: 0.9 },
      { word: 'BUILDING', start: 0.95, end: 1.2 }
    ]
  },
  {
    id: 'block_002',
    text: 'UH A CAPTION ENGINE',
    start: 2.0, // Silence gap of 0.8s between block_001 (1.2s) and block_002 (2.0s)
    end: 3.2,
    words: [
      { word: 'UH', start: 2.0, end: 2.3 },
      { word: 'A', start: 2.35, end: 2.5 },
      { word: 'CAPTION', start: 2.55, end: 2.85 },
      { word: 'ENGINE', start: 2.9, end: 3.2 }
    ]
  }
];

setTimeout(() => {
  const postData = JSON.stringify({
    blocks: sampleAudioBlocks,
    silenceThreshold: 0.5,
    removeFillers: true
  });

  const req = http.request({
    hostname: 'localhost',
    port: 5000,
    path: '/api/caption/cleanup-audio',
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
        console.log('--- Audio Cleanup Response ---');
        console.log(`Fillers Removed: ${response.fillersRemovedCount}`);
        console.log(`Time Saved: ${response.totalTimeSavedSeconds}s`);
        console.log(`Silence Gaps Detected: ${response.silenceCuts.length}`);
        
        assert.strictEqual(response.success, true);
        assert.strictEqual(response.fillersRemovedCount, 2);
        assert.strictEqual(response.silenceCuts.length, 1);
        assert.ok(response.blocks[0].text.startsWith('WE ARE BUILDING'));

        console.log('\nCleaned Blocks Preview:');
        response.blocks.forEach(b => {
          console.log(`  └─ [${b.start}s - ${b.end}s]: "${b.text}"`);
        });

        console.log('\n✅ Phase 4 Audio Cleanup & Silence Trimming Test PASSED.');
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
