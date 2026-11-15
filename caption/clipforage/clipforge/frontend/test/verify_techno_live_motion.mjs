import { chromium } from 'playwright';
import assert from 'assert/strict';

async function verifyTechnoLiveMotion() {
  console.log('[TECHNO TEST] Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', (msg) => console.log('[BROWSER]', msg.type(), msg.text()));

  await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle' });

  // Enter Techno Gamerz URL
  const input = page.locator('#gaming-youtube-url-input');
  await input.fill('https://www.youtube.com/watch?v=OVgNvkHGOlE');
  const loadBtn = page.locator('#open-gaming-studio-url-btn');
  await loadBtn.click();

  // Wait for video element to update src to Techno Gamerz stream
  await page.waitForTimeout(3000);

  const videoSrc = await page.evaluate(() => {
    const video = document.getElementById('gaming-source-video-player');
    return video?.src;
  });
  console.log('[TECHNO TEST] Video src:', videoSrc);
  assert.ok(videoSrc.includes('OVgNvkHGOlE'), 'Video element must have Techno Gamerz stream src');

  // Play video
  console.log('[TECHNO TEST] Starting video playback...');
  await page.evaluate(async () => {
    const video = document.getElementById('gaming-source-video-player');
    if (video) {
      video.muted = true;
      video.currentTime = 5.0; // Seek into the action
      await video.play().catch(() => {});
    }
  });

  await page.waitForTimeout(2000);

  const frame1 = await page.evaluate(() => {
    const video = document.getElementById('gaming-source-video-player');
    const canvas = document.getElementById('gaming-composite-canvas');
    const ctx = canvas.getContext('2d');
    const p = ctx.getImageData(540, 960, 1, 1).data;
    return {
      pixel: Array.from(p),
      currentTime: video?.currentTime,
      paused: video?.paused,
    };
  });
  console.log('[TECHNO TEST] Frame 1 (t~7s):', frame1);

  await page.waitForTimeout(2000);

  const frame2 = await page.evaluate(() => {
    const video = document.getElementById('gaming-source-video-player');
    const canvas = document.getElementById('gaming-composite-canvas');
    const ctx = canvas.getContext('2d');
    const p = ctx.getImageData(540, 960, 1, 1).data;
    return {
      pixel: Array.from(p),
      currentTime: video?.currentTime,
      paused: video?.paused,
    };
  });
  console.log('[TECHNO TEST] Frame 2 (t~9s):', frame2);

  assert.ok(frame2.currentTime > frame1.currentTime, 'Techno video time must advance');

  const screenshotPath = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/gaming_techno_live_motion.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(`[TECHNO TEST] Screenshot saved to ${screenshotPath}`);

  await browser.close();
  console.log('[TECHNO TEST] Techno Gamerz live motion verification PASSED!');
}

verifyTechnoLiveMotion().catch((err) => {
  console.error('[TECHNO TEST FAILED]', err);
  process.exit(1);
});

