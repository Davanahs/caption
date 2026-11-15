import { chromium } from 'playwright';
import assert from 'assert';

const BASE_URL = 'http://localhost:3001/gaming';

async function verifyLiveStreamCanvasSync() {
  console.log('[Live Stream Verification] Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error') console.error('  [Browser Error]', msg.text());
  });

  try {
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(500);

    // Enter YouTube URL & Launch Studio
    console.log('[Live Stream Verification] Entering YouTube URL...');
    const urlInput = page.locator('#gaming-youtube-url-input');
    await urlInput.fill('https://www.youtube.com/watch?v=0GjbIOS9Q90');
    const openBtn = page.locator('#open-gaming-studio-url-btn');
    await openBtn.click();

    // Wait for modal & source video player
    console.log('[Live Stream Verification] Waiting for modal & HTML5 video player...');
    await page.waitForSelector('#gaming-selection-modal-dialog', { state: 'visible' });
    const videoPlayer = page.locator('#gaming-source-video-player');
    await videoPlayer.waitFor({ state: 'attached', timeout: 15000 });

    const playerSrc = await videoPlayer.getAttribute('src');
    console.log('  Video player src:', playerSrc);
    assert.ok(playerSrc?.includes('/api/videos/preview-stream'), 'Video player must point to preview-stream proxy');

    // Wait for video to load metadata
    console.log('[Live Stream Verification] Waiting for video metadata...');
    await page.waitForFunction(() => {
      const v = document.querySelector('#gaming-source-video-player');
      return v && v.readyState >= 1;
    }, { timeout: 15000 });

    const readyState = await videoPlayer.evaluate(v => v.readyState);
    const duration = await videoPlayer.evaluate(v => v.duration);
    console.log(`  Video readyState: ${readyState}, duration: ${duration}s`);
    assert.ok(readyState >= 1, 'Video readyState must be >= 1 (metadata loaded)');
    assert.ok(duration > 0, 'Video duration must be > 0');

    // Verify Canvas element
    const canvas = page.locator('#gaming-composite-canvas');
    await canvas.waitFor({ state: 'visible', timeout: 10000 });
    console.log('[Live Stream Verification] 9:16 Composite Canvas mounted.');

    // Click backdrop to start playback
    console.log('[Live Stream Verification] Clicking video backdrop to start playback...');
    const videoContainer = page.locator('#gaming-source-video-container');
    const containerBox = await videoContainer.boundingBox();
    assert.ok(containerBox, 'Container bounding box must exist');

    await page.mouse.click(containerBox.x + 50, containerBox.y + containerBox.height / 2);
    await page.waitForTimeout(1000);

    // Verify video is playing
    const isPlaying = await videoPlayer.evaluate(v => !v.paused && !v.ended);
    console.log(`  Video isPlaying: ${isPlaying}`);
    assert.ok(isPlaying, 'HTML5 video must be playing after click');

    // Sample canvas pixel data while playing
    const canvasHasData = await canvas.evaluate(c => {
      const ctx = c.getContext('2d');
      if (!ctx) return false;
      const pixel = ctx.getImageData(c.width / 2, c.height / 2, 1, 1).data;
      // Check that canvas is drawn (not completely transparent)
      return pixel[3] > 0;
    });
    console.log(`  Canvas is rendering video frames: ${canvasHasData}`);
    assert.ok(canvasHasData, 'Canvas must contain rendered video frame data');

    // Drag gameplay ROI box while video continues playing
    console.log('[Live Stream Verification] Dragging gameplay ROI while video is playing...');
    const gpBox = page.locator('#gameplay-roi-box');
    const gpBounding = await gpBox.boundingBox();
    assert.ok(gpBounding, 'Gameplay box bounding rect must exist');

    const startX = gpBounding.x + gpBounding.width / 2;
    const startY = gpBounding.y + gpBounding.height / 2;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX - 60, startY, { steps: 5 });
    await page.mouse.up();
    await page.waitForTimeout(500);

    // Verify video is STILL playing after drag!
    const stillPlaying = await videoPlayer.evaluate(v => !v.paused && !v.ended);
    console.log(`  Video still playing after drag: ${stillPlaying}`);
    assert.ok(stillPlaying, 'Video must continue playing during and after drag');

    // Take screenshot of live playback & 9:16 preview in action
    await page.screenshot({ path: 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/gaming_live_stream_verified.png' });
    console.log('✅ Live YouTube streaming & 9:16 Canvas verification PASSED with 100% success!');
  } finally {
    await browser.close();
  }
}

verifyLiveStreamCanvasSync().catch(err => {
  console.error('❌ Verification failed:', err);
  process.exit(1);
});

