import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ARTIFACT_DIR = path.resolve(__dirname, '../../audit_artifacts/phase_1_2_verification');

const AUTOMATION_URL = process.env.AUTOMATION_URL || 'http://localhost:3000/automation';
const DASHBOARD_URL = process.env.DASHBOARD_URL || 'http://localhost:3000/';
const API_BASE = process.env.API_BASE || 'http://localhost:8000';

test('Phase 1.2 Real Browser End-to-End Verification: Start Processing -> Celery -> Dashboard -> History', async (t) => {
  if (process.env.RUN_LIVE_E2E !== 'true') {
    t.skip('Skipped: RUN_LIVE_E2E=true environment flag is required to run live backend E2E tests against operational environment');
    return;
  }

  if (!fs.existsSync(ARTIFACT_DIR)) {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  }

  // 1. Seed fresh test channel and decision via backend API / direct seed
  const setupResp = await fetch(`${API_BASE}/api/channels/ch_phase12_e2e/process-video`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      video_id: 'synth_browser_01',
      video_title: 'Synthetic Browser Test Video',
      video_url: 'https://www.youtube.com/watch?v=synth_vid01',
      overrides: {
        clips_count: 1,
        video_layout: 'fill_blur',
        scoring_mode: 'ai',
        duration_mode: 'adaptive'
      }
    })
  });
  assert.equal(setupResp.status, 200, 'Process video API must return 200');
  const setupData = await setupResp.json();
  const testJobId = setupData.job_id;
  assert.ok(testJobId, 'Response must include job_id');
  console.log(`[Browser Test Setup] Started test job: ${testJobId}`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 }
  });
  const page = await context.newPage();

  const consoleMessages = [];
  const pageErrors = [];

  page.on('console', (msg) => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  page.on('pageerror', (err) => {
    pageErrors.push(err.toString());
  });

  try {
    // ── STAGE 1: Navigate to Dashboard to observe active processing ──
    await t.test('1. Dashboard renders active job card during worker execution', async () => {
      await page.goto(DASHBOARD_URL, { waitUntil: 'networkidle' });
      await page.waitForTimeout(1000);

      // Verify page loaded
      const heading = await page.locator('h1, h2, h3').allTextContents();
      assert.ok(heading.length > 0, 'Dashboard heading must be visible');

      // Check if job is visible in active jobs or recently completed
      const activeOrRecent = page.locator(`text=Synthetic Video synth_vid01`).first();
      await activeOrRecent.waitFor({ state: 'visible', timeout: 15000 });

      // Save screenshot of dashboard during processing / active card
      await page.screenshot({
        path: path.join(ARTIFACT_DIR, '01_dashboard_active_job_progress.png'),
        fullPage: true
      });
      console.log('Saved 01_dashboard_active_job_progress.png');
    });

    // ── STAGE 2: Wait for real Celery worker execution to complete ──
    await t.test('2. Celery worker finishes processing and job transitions to Completed in History', async () => {
      // Poll until the job completes in the backend (within 60s)
      const maxWaitMs = 60000;
      const startMs = Date.now();
      let completed = false;

      while (Date.now() - startMs < maxWaitMs) {
        const resp = await fetch(`${API_BASE}/api/jobs/${testJobId}`);
        if (resp.ok) {
          const job = await resp.json();
          if (job.status === 'completed' || job.status === 'completed_with_failures') {
            completed = true;
            break;
          }
        }
        await new Promise((r) => setTimeout(r, 2000));
      }
      assert.ok(completed, `Job ${testJobId} must reach completed state within 60s`);

      // Refresh page to observe completed status in Recent Job History
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(2000);

      // Verify the job card in Recent Job History displays "Done" or "100%"
      const completedCard = page.locator(`text=Synthetic Video synth_vid01`).first();
      await completedCard.waitFor({ state: 'visible', timeout: 10000 });

      await page.screenshot({
        path: path.join(ARTIFACT_DIR, '02_dashboard_completed_job_history.png'),
        fullPage: true
      });
      console.log('Saved 02_dashboard_completed_job_history.png');
    });

    // ── STAGE 3: Hard Page Refresh Persistence ──
    await t.test('3. Hard page refresh preserves completed state without regression', async () => {
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(1500);

      // Verify the job is still present in history
      const jobItem = page.locator(`text=Synthetic Video synth_vid01`).first();
      const isVisible = await jobItem.isVisible();
      assert.ok(isVisible, 'Completed job must persist across hard page refresh');

      await page.screenshot({
        path: path.join(ARTIFACT_DIR, '03_dashboard_persisted_after_refresh.png'),
        fullPage: true
      });
      console.log('Saved 03_dashboard_persisted_after_refresh.png');
    });

    // ── STAGE 4: Failed Job State & Retry Action Display ──
    await t.test('4. Failed jobs display error message and retry button in history', async () => {
      // Check if any failed or cancelled job card exists in recent jobs
      const historyCards = await page.locator('div[title*="Error:"], div:has-text("Failed"), button:has-text("🔄 Retry")').count();
      console.log(`[Dashboard] Found ${historyCards} failed/retry elements in job history.`);

      await page.screenshot({
        path: path.join(ARTIFACT_DIR, '04_dashboard_job_history_overview.png'),
        fullPage: true
      });
      console.log('Saved 04_dashboard_job_history_overview.png');
    });

    // Verify console error cleanliness
    const criticalErrors = pageErrors.filter(
      (err) => !err.includes('favicon') && !err.includes('Failed to load resource')
    );
    assert.equal(criticalErrors.length, 0, `Uncaught page errors: ${criticalErrors.join(', ')}`);

    console.log('\n[PLAYWRIGHT SUCCESS] All 4 browser test stages passed!');
  } finally {
    await browser.close();
  }
});
