import { chromium } from 'playwright';

async function testTechnoVideo() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', (msg) => console.log('[BROWSER]', msg.type(), msg.text()));

  await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle' });

  // Load Techno Gamerz video
  console.log('[TEST] Entering Techno Gamerz URL...');
  const input = page.locator('#gaming-youtube-url-input');
  await input.fill('https://www.youtube.com/watch?v=OVgNvkHGOlE');
  const loadBtn = page.locator('#open-gaming-studio-url-btn');
  await loadBtn.click();

  await page.waitForTimeout(3000);

  // Check state
  const state = await page.evaluate(async () => {
    const video = document.getElementById('gaming-source-video-player');
    const iframe = document.getElementById('gaming-youtube-preview-frame');
    return {
      videoSrc: video ? video.getAttribute('src') : null,
      videoReadyState: video ? video.readyState : null,
      videoPaused: video ? video.paused : null,
      videoCurrentTime: video ? video.currentTime : null,
      videoWidth: video ? video.videoWidth : null,
      videoHeight: video ? video.videoHeight : null,
      iframeSrc: iframe ? iframe.getAttribute('src') : null,
    };
  });
  console.log('[TEST STATE BEFORE PLAY]', state);

  // Play YouTube iframe via postMessage command
  await page.evaluate(() => {
    const iframe = document.getElementById('gaming-youtube-preview-frame');
    if (iframe && iframe.contentWindow) {
      iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'playVideo', args: [] }), '*');
    }
  });

  await page.waitForTimeout(3000);

  const stateAfter = await page.evaluate(() => {
    const video = document.getElementById('gaming-source-video-player');
    return {
      videoReadyState: video ? video.readyState : null,
      videoPaused: video ? video.paused : null,
      videoCurrentTime: video ? video.currentTime : null,
    };
  });
  console.log('[TEST STATE AFTER PLAY]', stateAfter);

  await browser.close();
}

testTechnoVideo().catch(console.error);

