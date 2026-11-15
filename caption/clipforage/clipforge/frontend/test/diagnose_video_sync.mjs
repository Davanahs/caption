import { chromium } from 'playwright';

async function diagnoseVideoSync() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', (msg) => console.log('[BROWSER CONSOLE]', msg.type(), msg.text()));
  page.on('pageerror', (err) => console.error('[BROWSER PAGE ERROR]', err));

  await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle' });

  // Evaluate the video tag state
  const diag = await page.evaluate(async () => {
    const video = document.getElementById('gaming-source-video-player');
    const iframe = document.getElementById('gaming-youtube-preview-frame');
    const canvas = document.getElementById('gaming-composite-canvas');

    return {
      hasVideo: !!video,
      videoSrc: video ? video.getAttribute('src') : null,
      videoCurrentSrc: video ? video.currentSrc : null,
      videoReadyState: video ? video.readyState : null,
      videoNetworkState: video ? video.networkState : null,
      videoPaused: video ? video.paused : null,
      videoMuted: video ? video.muted : null,
      videoWidth: video ? video.videoWidth : null,
      videoHeight: video ? video.videoHeight : null,
      videoError: video && video.error ? { code: video.error.code, message: video.error.message } : null,
      hasIframe: !!iframe,
      iframeSrc: iframe ? iframe.getAttribute('src') : null,
      hasCanvas: !!canvas,
    };
  });

  console.log('[DIAGNOSTIC RESULT]', JSON.stringify(diag, null, 2));
  await browser.close();
}

diagnoseVideoSync().catch(console.error);

