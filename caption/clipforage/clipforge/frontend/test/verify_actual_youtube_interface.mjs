import { chromium } from 'playwright';
import assert from 'assert/strict';

async function verifyActualYouTubeInterface() {
  console.log('[VERIFY] Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log('[VERIFY] Navigating to http://localhost:3001/gaming...');
  await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle', timeout: 30000 });

  // Verify modal is visible
  const modalDialog = page.locator('#gaming-selection-modal-dialog');
  await modalDialog.waitFor({ state: 'visible', timeout: 10000 });
  console.log('[VERIFY] GamingSelectionModal is visible.');

  // Input YouTube URL and click Load Video
  console.log('[VERIFY] Loading YouTube URL...');
  const input = page.locator('#gaming-youtube-url-input');
  await input.fill('https://www.youtube.com/watch?v=OVgNvkHGOlE');
  const loadBtn = page.locator('#open-gaming-studio-url-btn');
  await loadBtn.click();
  await page.waitForTimeout(2000);

  // Verify YouTube iframe is rendered with pointer-events auto
  const ytIframe = page.locator('#gaming-youtube-preview-frame');
  await ytIframe.waitFor({ state: 'attached', timeout: 10000 });
  const iframeSrc = await ytIframe.getAttribute('src');
  console.log('[VERIFY] YouTube iframe src:', iframeSrc);
  assert.ok(iframeSrc.includes('youtube.com/embed/'), 'Iframe src must be youtube.com/embed');

  // Verify no custom visible player controls overlay exists
  const customControls = page.locator('#gaming-player-controls-overlay');
  const box = await customControls.boundingBox();
  console.log('[VERIFY] Controls contract bounding box:', box);
  assert.ok(box.width <= 10 && box.height <= 10, 'Custom player controls must be visually hidden/unobtrusive');

  // Verify contract elements are in DOM and functional
  const stepBackBtn = page.locator('#gaming-step-back-btn');
  const timestampDisplay = page.locator('#gaming-timestamp-display');
  await stepBackBtn.click({ force: true });
  const timeText = await timestampDisplay.textContent();
  console.log('[VERIFY] Timestamp display text:', timeText);
  assert.ok(timeText.includes('00:00'), 'Timestamp display must show time');

  // Verify ROI boxes are visible and interactive
  const gameplayBox = page.locator('#gameplay-roi-box');
  await gameplayBox.waitFor({ state: 'visible' });
  const facecamBox = page.locator('#facecam-roi-box');
  await facecamBox.waitFor({ state: 'visible' });

  // Verify 9:16 Preview Canvas is rendered
  const canvas = page.locator('#gaming-composite-canvas');
  await canvas.waitFor({ state: 'visible' });

  // Capture screenshot of the full Gaming Studio UI with the actual YouTube interface
  const screenshotPath = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/gaming_actual_youtube_interface.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(`[VERIFY] Screenshot saved to ${screenshotPath}`);

  await browser.close();
  console.log('[VERIFY] All verification assertions PASSED successfully!');
}

verifyActualYouTubeInterface().catch((err) => {
  console.error('[VERIFY FAILED]', err);
  process.exit(1);
});

