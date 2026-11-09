import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const AUDIT_DIR = path.resolve(__dirname, '../../audit_artifacts/phase_2_1_verification');
const BRAIN_DIR = 'C:/Users/Chinmaygouda/.gemini/antigravity-ide/brain/607b38c3-5af0-4c06-aaf7-399b1e366339';

const CLIPS_URL = process.env.CLIPS_URL || 'http://localhost:3000/clips';

test('Phase 2.1 Real Browser End-to-End Verification: Clip Preview AI Enhancements (Hooks, B-Roll, SFX)', async (t) => {
  if (process.env.RUN_LIVE_E2E !== 'true') {
    t.skip('Skipped: RUN_LIVE_E2E=true environment flag is required to run live browser verification tests');
    return;
  }

  if (!fs.existsSync(AUDIT_DIR)) {
    fs.mkdirSync(AUDIT_DIR, { recursive: true });
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 950 }
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  page.on('pageerror', (err) => {
    consoleErrors.push(err.toString());
  });

  try {
    // ── STAGE 1: Navigate to Clips Page ──
    console.log('[Browser Test] Navigating to /clips...');
    await page.goto(CLIPS_URL, { waitUntil: 'networkidle', timeout: 30000 });

    // Wait for clips to render
    await page.waitForSelector('text=Clips Library', { timeout: 15000 });

    // Find our test clip card
    const clipTitle = page.locator('[data-testid="clip-title-p21_browser_clip_1"]').first();
    await clipTitle.waitFor({ timeout: 10000 });
    console.log('[Browser Test] Found Phase 2.1 test clip card.');

    // ── STAGE 2: Open Preview Modal ──
    await clipTitle.click();
    const modal = page.locator('[role="dialog"]');
    await modal.waitFor({ timeout: 10000 });
    console.log('[Browser Test] Opened Preview Modal.');

    // Verify AI Enhancements Panel exists
    const panel = page.locator('[data-testid="ai-enhancements-panel"]');
    await panel.waitFor({ timeout: 10000 });
    assert.ok(await panel.isVisible(), 'AI Enhancements Panel must be visible');

    // ── STAGE 3: Test Hook Tab & Generation ──
    const tabHook = page.locator('[data-testid="tab-hook"]');
    await tabHook.click();
    console.log('[Browser Test] Selected Hooks Tab.');

    const btnGenerateHook = page.locator('[data-testid="btn-generate-hook"]').first();
    if (await btnGenerateHook.isVisible()) {
      await btnGenerateHook.click();
      console.log('[Browser Test] Clicked Analyze Hook Opportunities.');
      // Wait for opportunities / banner to update
      await page.waitForTimeout(3000);
    }

    const hookScreenshotPath = path.join(AUDIT_DIR, '01_preview_modal_ai_enhancements_hook.png');
    await page.screenshot({ path: hookScreenshotPath, fullPage: false });
    if (fs.existsSync(BRAIN_DIR)) {
      fs.copyFileSync(hookScreenshotPath, path.join(BRAIN_DIR, '01_preview_modal_ai_enhancements_hook.png'));
    }
    console.log(`[Browser Test] Captured Screenshot 1: ${hookScreenshotPath}`);

    // ── STAGE 4: Test B-Roll Tab & Generation ──
    const tabBroll = page.locator('[data-testid="tab-broll"]');
    await tabBroll.click();
    console.log('[Browser Test] Selected B-Roll Tab.');

    const btnLoadBroll = page.locator('[data-testid="btn-load-broll"]').first();
    await btnLoadBroll.waitFor({ timeout: 5000 });
    await btnLoadBroll.click();
    console.log('[Browser Test] Clicked Generate B-Roll Plan.');

    // Wait for cutaways list or apply button
    const btnApplyBroll = page.locator('[data-testid="btn-apply-broll"]');
    await btnApplyBroll.waitFor({ timeout: 10000 });
    assert.ok(await btnApplyBroll.isVisible(), 'Apply B-Roll button must appear after plan generation');

    const brollScreenshotPath = path.join(AUDIT_DIR, '02_preview_modal_ai_enhancements_broll.png');
    await page.screenshot({ path: brollScreenshotPath, fullPage: false });
    if (fs.existsSync(BRAIN_DIR)) {
      fs.copyFileSync(brollScreenshotPath, path.join(BRAIN_DIR, '02_preview_modal_ai_enhancements_broll.png'));
    }
    console.log(`[Browser Test] Captured Screenshot 2: ${brollScreenshotPath}`);

    // ── STAGE 5: Test Sound FX Tab & Generation ──
    const tabSfx = page.locator('[data-testid="tab-sfx"]');
    await tabSfx.click();
    console.log('[Browser Test] Selected Sound FX Tab.');

    const btnLoadSfx = page.locator('[data-testid="btn-load-sfx"]').first();
    await btnLoadSfx.waitFor({ timeout: 5000 });
    await btnLoadSfx.click();
    console.log('[Browser Test] Clicked Generate SFX Plan.');

    // Wait for SFX cues list or apply button
    const btnApplySfx = page.locator('[data-testid="btn-apply-sfx"]');
    await btnApplySfx.waitFor({ timeout: 10000 });
    assert.ok(await btnApplySfx.isVisible(), 'Apply Sound FX button must appear after plan generation');

    const sfxScreenshotPath = path.join(AUDIT_DIR, '03_preview_modal_ai_enhancements_sfx.png');
    await page.screenshot({ path: sfxScreenshotPath, fullPage: false });
    if (fs.existsSync(BRAIN_DIR)) {
      fs.copyFileSync(sfxScreenshotPath, path.join(BRAIN_DIR, '03_preview_modal_ai_enhancements_sfx.png'));
    }
    console.log(`[Browser Test] Captured Screenshot 3: ${sfxScreenshotPath}`);

    // ── STAGE 6: Apply Sound FX Plan ──
    await btnApplySfx.click();
    console.log('[Browser Test] Clicked Apply Sound FX.');

    const statusBanner = page.locator('[data-testid="enhancement-status-banner"]');
    await statusBanner.waitFor({ timeout: 10000 });
    const bannerText = await statusBanner.innerText();
    console.log(`[Browser Test] Enhancement Status Banner: ${bannerText}`);
    assert.ok(bannerText.includes('Sound FX mixed') || bannerText.includes('task'), 'Status banner must confirm dispatch');

    const appliedScreenshotPath = path.join(AUDIT_DIR, '04_preview_modal_ai_enhancement_applied.png');
    await page.screenshot({ path: appliedScreenshotPath, fullPage: false });
    if (fs.existsSync(BRAIN_DIR)) {
      fs.copyFileSync(appliedScreenshotPath, path.join(BRAIN_DIR, '04_preview_modal_ai_enhancement_applied.png'));
    }
    console.log(`[Browser Test] Captured Screenshot 4: ${appliedScreenshotPath}`);

    // Check for critical browser errors
    const fatalErrors = consoleErrors.filter(e => !e.includes('favicon') && !e.includes('download') && !e.includes('404'));
    assert.equal(fatalErrors.length, 0, `Expected 0 fatal browser errors, got: ${JSON.stringify(fatalErrors)}`);
    console.log('✅ Real browser end-to-end verification passed with 0 fatal errors.');

  } finally {
    await browser.close();
  }
});
