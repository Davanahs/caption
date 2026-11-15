import { chromium } from 'playwright';

async function captureResizedLayout() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle' });

  // Load Techno Gamerz video to show realistic context
  const input = page.locator('#gaming-youtube-url-input');
  await input.fill('https://www.youtube.com/watch?v=OVgNvkHGOlE');
  const loadBtn = page.locator('#open-gaming-studio-url-btn');
  await loadBtn.click();

  await page.waitForTimeout(3000);

  // Play video
  await page.evaluate(async () => {
    const video = document.getElementById('gaming-source-video-player');
    if (video) {
      video.muted = true;
      video.currentTime = 6.0;
      await video.play().catch(() => {});
    }
  });

  await page.waitForTimeout(2000);

  // Measure bounding boxes
  const layoutMetrics = await page.evaluate(() => {
    const videoContainer = document.getElementById('gaming-source-video-container');
    const canvas = document.getElementById('gaming-composite-canvas');
    const vRect = videoContainer ? videoContainer.getBoundingClientRect() : null;
    const cRect = canvas ? canvas.getBoundingClientRect() : null;
    const gap = (cRect && vRect) ? (cRect.left - vRect.right) : null;
    return {
      videoWidth: vRect?.width,
      videoHeight: vRect?.height,
      canvasWidth: cRect?.width,
      canvasHeight: cRect?.height,
      horizontalGapBetweenVideoAndCanvas: gap,
    };
  });
  console.log('[LAYOUT METRICS]', layoutMetrics);

  const screenshotPath = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/gaming_resized_spaced_layout.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log('[SCREENSHOT SAVED]', screenshotPath);

  await browser.close();
}

captureResizedLayout().catch(console.error);

