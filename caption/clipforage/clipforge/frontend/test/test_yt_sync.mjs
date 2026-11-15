import { chromium } from 'playwright';

async function testYouTubePostMessageSync() {
  const browser = await chromium.launch({ headless: false }); // headful to see
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', (msg) => console.log('[BROWSER CONSOLE]', msg.text()));

  await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle' });

  // Add listener for messages in the page
  await page.evaluate(() => {
    window.addEventListener('message', (e) => {
      console.log('[WINDOW MESSAGE RECEIVED]', typeof e.data === 'string' ? e.data.slice(0, 150) : JSON.stringify(e.data)?.slice(0, 150));
    });
  });

  // Check iframe contentWindow
  console.log('[TEST] Waiting 3 seconds...');
  await page.waitForTimeout(3000);

  // Send listening event to iframe
  await page.evaluate(() => {
    const iframe = document.getElementById('gaming-youtube-preview-frame');
    if (iframe && iframe.contentWindow) {
      console.log('[TEST] Posting listening event to iframe...');
      iframe.contentWindow.postMessage(JSON.stringify({ event: 'listening', id: 'gaming-youtube-preview-frame' }), '*');
    }
  });

  await page.waitForTimeout(4000);

  // Try to play YouTube video via postMessage
  console.log('[TEST] Sending playVideo command...');
  await page.evaluate(() => {
    const iframe = document.getElementById('gaming-youtube-preview-frame');
    if (iframe && iframe.contentWindow) {
      iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'playVideo', args: [] }), '*');
    }
  });

  await page.waitForTimeout(4000);

  const status = await page.evaluate(() => {
    const video = document.getElementById('gaming-source-video-player');
    return {
      currentTime: video ? video.currentTime : null,
      paused: video ? video.paused : null,
      readyState: video ? video.readyState : null,
    };
  });
  console.log('[TEST STATUS AFTER PLAY]', status);

  await browser.close();
}

testYouTubePostMessageSync().catch(console.error);

