import { chromium } from 'playwright';

async function checkListeners() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle' });

  const result = await page.evaluate(() => {
    const video = document.getElementById('gaming-source-video-player');
    const canvas = document.getElementById('gaming-composite-canvas');
    return {
      hasVideo: !!video,
      hasCanvas: !!canvas,
      videoReadyState: video?.readyState,
    };
  });
  console.log('[LISTENERS CHECK]', result);

  await browser.close();
}

checkListeners().catch(console.error);

