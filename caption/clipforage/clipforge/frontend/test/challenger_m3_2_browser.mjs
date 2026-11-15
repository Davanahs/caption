/**
 * challenger_m3_2_browser.mjs
 * ============================
 * Live Chromium Browser Empirical Stress Verification
 * Milestone M3: Dual-Region Gaming Layout
 */

import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';
import assert from 'assert/strict';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const STATE_FOLDER = path.resolve(__dirname, '../../../.agents/teamwork/challenger_m3_2');

if (!fs.existsSync(STATE_FOLDER)) {
  fs.mkdirSync(STATE_FOLDER, { recursive: true });
}

async function findClipforgeBaseUrl() {
  const portsToTry = [process.env.PORT, 3100, 3000].filter(Boolean);
  for (const port of portsToTry) {
    try {
      const url = `http://localhost:${port}/gaming`;
      const res = await fetch(url);
      if (res.ok) {
        return `http://localhost:${port}`;
      }
    } catch (_) {}
  }
  return 'http://localhost:3100';
}

async function runBrowserStress() {
  console.log('[CHALLENGER 2 BROWSER] Starting browser stress testing...');
  const BASE_URL = await findClipforgeBaseUrl();
  console.log(`[CHALLENGER 2 BROWSER] Target URL: ${BASE_URL}`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  try {
    // ── STAGE 1: Navigate to Gaming Studio ──
    console.log('[CHALLENGER 2 BROWSER] Navigating to /gaming...');
    await page.goto(`${BASE_URL}/gaming`, { waitUntil: 'networkidle', timeout: 30000 });

    const title = await page.textContent('h1');
    assert.ok(title.includes('Dual-Region Gaming Studio'), 'Studio title must match');

    // ── STAGE 2: Test Ingestion Mode Switching ──
    console.log('[CHALLENGER 2 BROWSER] Testing ingestion mode switcher toggling...');
    const urlTabBtn = page.locator('#gaming-tab-url-btn');
    const uploadTabBtn = page.locator('#gaming-tab-upload-btn');

    for (let i = 0; i < 5; i++) {
      await uploadTabBtn.click();
      await page.waitForSelector('#gaming-file-dropzone', { state: 'visible' });
      await urlTabBtn.click();
      await page.waitForSelector('#gaming-youtube-url-input', { state: 'visible' });
    }
    console.log('[CHALLENGER 2 BROWSER] Ingestion mode switching verified.');

    // ── STAGE 3: Launch Modal via YouTube URL ──
    console.log('[CHALLENGER 2 BROWSER] Launching GamingSelectionModal via YouTube URL...');
    const urlInput = page.locator('#gaming-youtube-url-input');
    await urlInput.fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');

    const openBtn = page.locator('#open-gaming-studio-url-btn');
    await openBtn.click();

    const modalDialog = page.locator('#gaming-selection-modal-dialog');
    await modalDialog.waitFor({ state: 'visible', timeout: 15000 });
    console.log('[CHALLENGER 2 BROWSER] Modal successfully mounted.');

    // ── STAGE 4: Stress-Test Tool Switching & ROI Handle Lifecycle ──
    console.log('[CHALLENGER 2 BROWSER] Stress testing Tool Switching & ROI Handles...');
    const gameplayToolBtn = page.locator('#select-gameplay-tool-btn');
    const facecamToolBtn = page.locator('#select-facecam-tool-btn');
    const gameplayRoiBox = page.locator('#gameplay-roi-box');
    const facecamRoiBox = page.locator('#facecam-roi-box');

    // Initial state: Gameplay active
    await page.waitForSelector('#gameplay-handle-nw', { state: 'visible' });
    const facecamHandleInitial = await page.$('#facecam-handle-nw');
    assert.equal(facecamHandleInitial, null, 'Facecam handles must not be rendered when gameplay tool is active');

    // Switch to Facecam tool
    await facecamToolBtn.click();
    await page.waitForSelector('#facecam-handle-nw', { state: 'visible' });
    const gameplayHandleAfter = await page.$('#gameplay-handle-nw');
    assert.equal(gameplayHandleAfter, null, 'Gameplay handles must not be rendered when facecam tool is active');

    // Switch back to Gameplay tool
    await gameplayToolBtn.click();
    await page.waitForSelector('#gameplay-handle-nw', { state: 'visible' });

    // Rapid tool switching (10 cycles)
    for (let i = 0; i < 10; i++) {
      await facecamToolBtn.click();
      await gameplayToolBtn.click();
    }
    await page.waitForSelector('#gameplay-handle-nw', { state: 'visible' });
    console.log('[CHALLENGER 2 BROWSER] Rapid tool switching verified.');

    // Cross-box activation: Click facecam box directly to switch tool
    console.log('[CHALLENGER 2 BROWSER] Testing direct ROI box click activation...');
    await facecamRoiBox.click({ position: { x: 20, y: 20 } });
    await page.waitForSelector('#facecam-handle-nw', { state: 'visible' });

    // Click gameplay box directly to switch tool
    await gameplayRoiBox.click({ position: { x: 20, y: 20 } });
    await page.waitForSelector('#gameplay-handle-nw', { state: 'visible' });
    console.log('[CHALLENGER 2 BROWSER] Cross-box activation verified.');

    // ── STAGE 5: Stress-Test Preset Transitions and Reset on Canvas ──
    console.log('[CHALLENGER 2 BROWSER] Stress testing placement presets and reset...');
    const pipOverlay = page.locator('#facecam-pip-overlay-box');
    await pipOverlay.waitFor({ state: 'visible' });

    const presetsMap = [
      { id: '#preset-btn-top-left', expectedLeft: '5%', expectedTop: '4%' },
      { id: '#preset-btn-bottom-left', expectedLeft: '5%', expectedTop: '74%' },
      { id: '#preset-btn-bottom-right', expectedLeft: '65%', expectedTop: '74%' },
      { id: '#preset-btn-top-right', expectedLeft: '65%', expectedTop: '4%' },
    ];

    for (const { id, expectedLeft, expectedTop } of presetsMap) {
      await page.locator(id).click();
      await page.waitForTimeout(100);

      const style = await pipOverlay.getAttribute('style');
      assert.ok(style.includes(`left: ${expectedLeft}`), `Style must contain left: ${expectedLeft}, got: ${style}`);
      assert.ok(style.includes(`top: ${expectedTop}`), `Style must contain top: ${expectedTop}, got: ${style}`);
    }

    // Drag overlay slightly to trigger 'custom'
    const pipBounds = await pipOverlay.boundingBox();
    if (pipBounds) {
      await page.mouse.move(pipBounds.x + 20, pipBounds.y + 20);
      await page.mouse.down();
      await page.mouse.move(pipBounds.x + 50, pipBounds.y + 40, { steps: 5 });
      await page.mouse.up();
      await page.waitForTimeout(100);

      const telemetryText = await page.textContent('#gaming-composite-canvas-container');
      assert.ok(telemetryText.includes('Placement: Custom'), 'Telemetry must indicate custom placement after drag');
    }

    // Click Reset
    const resetBtn = page.locator('#facecam-reset-btn');
    await resetBtn.click();
    await page.waitForTimeout(100);

    const resetStyle = await pipOverlay.getAttribute('style');
    assert.ok(resetStyle.includes('left: 65%'), `Reset style must restore left: 65%, got: ${resetStyle}`);
    assert.ok(resetStyle.includes('top: 4%'), `Reset style must restore top: 4%, got: ${resetStyle}`);
    console.log('[CHALLENGER 2 BROWSER] Presets and reset verified.');

    // ── STAGE 6: Stress-Test Timeline Precision Stepping ──
    console.log('[CHALLENGER 2 BROWSER] Testing timeline stepping controls...');
    const stepBackBtn = page.locator('#gaming-step-back-btn');
    const timestampDisplay = page.locator('#gaming-timestamp-display');

    for (let i = 0; i < 5; i++) {
      await stepBackBtn.click();
    }
    const timeText = await timestampDisplay.textContent();
    assert.ok(timeText.includes('00:00'), `Timestamp at start must remain non-negative, got: ${timeText}`);
    console.log('[CHALLENGER 2 BROWSER] Stepping controls verified.');

    // ── STAGE 7: Zero-Caption Live DOM Deep Scan ──
    console.log('[CHALLENGER 2 BROWSER] Running Zero-Caption live DOM deep scan...');
    const modalHtml = await modalDialog.innerHTML();
    const forbidden = [/caption/i, /subtitle/i, /subtitles/i, /drawtext/i];
    for (const pat of forbidden) {
      const match = modalHtml.match(pat);
      assert.equal(match, null, `Live DOM must not contain '${pat}': found "${match?.[0]}"`);
    }
    console.log('[CHALLENGER 2 BROWSER] Live DOM Zero-Caption audit passed.');

    // Save screenshot evidence
    const screenshotPath = path.join(STATE_FOLDER, 'challenger_m3_2_browser_verified.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`[CHALLENGER 2 BROWSER] Saved verification screenshot to: ${screenshotPath}`);

    console.log('[CHALLENGER 2 BROWSER SUCCESS] All browser stress tests passed with 100% verification!');
  } finally {
    await browser.close();
  }
}

runBrowserStress().catch((err) => {
  console.error('[CHALLENGER 2 BROWSER FAILED]', err);
  process.exit(1);
});
