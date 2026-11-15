import { chromium } from 'playwright';

async function checkCanvasPixels() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle' });

  const pixelCheck = await page.evaluate(async () => {
    const video = document.getElementById('gaming-source-video-player');
    const canvas = document.getElementById('gaming-composite-canvas');
    if (!video || !canvas) return { error: 'missing elements' };

    const ctx = canvas.getContext('2d');
    const p1 = ctx.getImageData(540, 960, 1, 1).data;

    // Seek video to 10 seconds and play
    video.currentTime = 10;
    await video.play();
    await new Promise((r) => setTimeout(r, 1000));

    const p2 = ctx.getImageData(540, 960, 1, 1).data;

    return {
      pixelAtStart: Array.from(p1),
      pixelAfterPlay: Array.from(p2),
      isSame: p1[0] === p2[0] && p1[1] === p2[1] && p1[2] === p2[2],
      videoTime: video.currentTime,
      videoPaused: video.paused,
    };
  });

  console.log('[PIXEL CHECK]', pixelCheck);
  await browser.close();
}

checkCanvasPixels().catch(console.error);

