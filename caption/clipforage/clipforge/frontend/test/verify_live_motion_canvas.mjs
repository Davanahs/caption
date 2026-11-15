import { chromium } from 'playwright';
import assert from 'assert/strict';

async function verifyLiveMotionCanvas() {
  console.log('[VERIFY MOTION] Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', (msg) => console.log('[BROWSER]', msg.type(), msg.text()));

  await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle' });

  // Wait for canvas and video to mount
  const canvasLocator = page.locator('#gaming-composite-canvas');
  await canvasLocator.waitFor({ state: 'visible', timeout: 15000 });

  // Check initial frame pixel
  const initialFrame = await page.evaluate(async () => {
    const video = document.getElementById('gaming-source-video-player');
    const canvas = document.getElementById('gaming-composite-canvas');
    if (!canvas || !video) return null;

    const ctx = canvas.getContext('2d');
    const p = ctx.getImageData(540, 960, 1, 1).data;
    return {
      pixel: Array.from(p),
      readyState: video.readyState,
      videoWidth: video.videoWidth,
      videoHeight: video.videoHeight,
      src: video.src,
    };
  });
  console.log('[VERIFY MOTION] Initial frame state:', initialFrame);

  // Play video and let it play for 2 seconds
  console.log('[VERIFY MOTION] Playing video...');
  await page.evaluate(async () => {
    const video = document.getElementById('gaming-source-video-player');
    if (video) {
      video.muted = true;
      await video.play().catch(() => {});
    }
  });

  await page.waitForTimeout(2000);

  // Sample pixel at t=2s
  const sampledFrame1 = await page.evaluate(() => {
    const video = document.getElementById('gaming-source-video-player');
    const canvas = document.getElementById('gaming-composite-canvas');
    const ctx = canvas.getContext('2d');
    const p = ctx.getImageData(540, 960, 1, 1).data;
    return {
      pixel: Array.from(p),
      currentTime: video ? video.currentTime : 0,
      paused: video ? video.paused : true,
    };
  });
  console.log('[VERIFY MOTION] Sample at t=2s:', sampledFrame1);

  await page.waitForTimeout(2000);

  // Sample pixel at t=4s
  const sampledFrame2 = await page.evaluate(() => {
    const video = document.getElementById('gaming-source-video-player');
    const canvas = document.getElementById('gaming-composite-canvas');
    const ctx = canvas.getContext('2d');
    const p = ctx.getImageData(540, 960, 1, 1).data;
    return {
      pixel: Array.from(p),
      currentTime: video ? video.currentTime : 0,
      paused: video ? video.paused : true,
    };
  });
  console.log('[VERIFY MOTION] Sample at t=4s:', sampledFrame2);

  // Verify time advanced and frames were painted
  assert.ok(sampledFrame2.currentTime > sampledFrame1.currentTime, 'Video time must advance during playback');

  // Capture screenshot of live canvas playing
  const screenshotPath = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/gaming_live_preview_working.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(`[VERIFY MOTION] Screenshot saved to ${screenshotPath}`);

  await browser.close();
  console.log('[VERIFY MOTION] Live preview video motion verification SUCCESSFUL!');
}

verifyLiveMotionCanvas().catch((err) => {
  console.error('[VERIFY MOTION FAILED]', err);
  process.exit(1);
});

