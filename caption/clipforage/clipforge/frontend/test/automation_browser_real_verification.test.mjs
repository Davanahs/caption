import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ARTIFACT_DIR = path.resolve(__dirname, '../../audit_artifacts/phase_1_1_browser_verification');

const APP_URL = process.env.APP_URL || 'http://localhost:3000/automation';

test('Phase 1.1 Real Browser Verification: Multi-Video Selection & Dispatch (Scenarios A through E)', async (t) => {
  if (!fs.existsSync(ARTIFACT_DIR)) {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  }

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

  const capturedBatchRequests = [];

  const mockChannels = [
    {
      id: 'ch_alpha_101',
      channel_name: 'Channel Alpha',
      channel_url: 'https://youtube.com/@channelalpha',
      is_active: true,
      auto_clip: true,
      auto_publish: false,
      clips_generated: 12,
      processing_profile: {
        video_layout: 'fill_blur',
        min_clip_duration: 15,
        max_clip_duration: 30,
        clips_count: 3,
        duration_mode: 'adaptive',
        segmentation_strategy: 'hook_peak_fall',
        scoring_mode: 'ai'
      }
    },
    {
      id: 'ch_beta_202',
      channel_name: 'Channel Beta',
      channel_url: 'https://youtube.com/@channelbeta',
      is_active: true,
      auto_clip: true,
      auto_publish: false,
      clips_generated: 5,
      processing_profile: {
        video_layout: 'fill_blur',
        min_clip_duration: 15,
        max_clip_duration: 30,
        clips_count: 3,
        duration_mode: 'adaptive',
        segmentation_strategy: 'hook_peak_fall',
        scoring_mode: 'ai'
      }
    }
  ];

  const mockAlphaVideos = {
    total: 2,
    page: 1,
    limit: 8,
    has_more: false,
    items: [
      {
        id: 'vid_a1',
        title: 'Video A1 Alpha',
        url: 'https://youtube.com/watch?v=vid_a1',
        duration: 45,
        published_at: '2026-10-10',
        is_processed: false
      },
      {
        id: 'vid_a2',
        title: 'Video A2 Alpha',
        url: 'https://youtube.com/watch?v=vid_a2',
        duration: 55,
        published_at: '2026-10-11',
        is_processed: false
      }
    ]
  };

  const mockBetaVideos = {
    total: 1,
    page: 1,
    limit: 8,
    has_more: false,
    items: [
      {
        id: 'vid_b1',
        title: 'Video B1 Beta',
        url: 'https://youtube.com/watch?v=vid_b1',
        duration: 50,
        published_at: '2026-10-12',
        is_processed: false
      }
    ]
  };

  let batchResponseStrategy = 'all_queued';

  // Intercept all requests with url matching /api/
  await page.route(/.*\/api\/.*/, async (route) => {
    const req = route.request();
    const url = req.url();
    const method = req.method();

    if (url.includes('/api/channels') && !url.includes('/videos') && !url.includes('/process') && !url.includes('/decisions')) {
      if (method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockChannels)
        });
      }
    }

    if (url.includes('/api/publish/destinations')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    }

    if (url.includes('/api/channels/decisions/history')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    }

    if (url.includes('/api/channels/ch_alpha_101/videos')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAlphaVideos)
      });
    }

    if (url.includes('/api/channels/ch_beta_202/videos')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockBetaVideos)
      });
    }

    if (url.includes('/process-videos-batch')) {
      let postData = null;
      try {
        postData = JSON.parse(req.postData() || '[]');
      } catch (e) {
        postData = req.postData();
      }

      capturedBatchRequests.push({
        url,
        method,
        postData,
        timestamp: Date.now()
      });

      const vidsList = Array.isArray(postData) ? postData : (postData?.videos || []);

      if (batchResponseStrategy === 'all_queued') {
        const items = vidsList.map(v => ({
          video_id: v.video_id,
          status: 'queued',
          job_id: `job_${v.video_id}`
        }));
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_requested: vidsList.length,
            queued_count: vidsList.length,
            already_processing_count: 0,
            rejected_count: 0,
            items
          })
        });
      }

      if (batchResponseStrategy === 'channel_b_network_error') {
        if (url.includes('ch_beta_202')) {
          return route.abort('failed');
        }
        const items = vidsList.map(v => ({
          video_id: v.video_id,
          status: 'queued',
          job_id: `job_${v.video_id}`
        }));
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_requested: vidsList.length,
            queued_count: vidsList.length,
            already_processing_count: 0,
            rejected_count: 0,
            items
          })
        });
      }

      if (batchResponseStrategy === 'item_rejection') {
        const items = vidsList.map((v, idx) => {
          if (idx === 0) {
            return { video_id: v.video_id, status: 'queued', job_id: `job_${v.video_id}` };
          } else {
            return { video_id: v.video_id, status: 'rejected', error: 'Video duration exceeds Shorts limit' };
          }
        });
        const queuedCount = items.filter(i => i.status === 'queued').length;
        const rejectedCount = items.filter(i => i.status === 'rejected').length;
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_requested: vidsList.length,
            queued_count: queuedCount,
            already_processing_count: 0,
            rejected_count: rejectedCount,
            items
          })
        });
      }

      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_requested: vidsList.length, queued_count: vidsList.length, already_processing_count: 0, rejected_count: 0, items: [] })
      });
    }

    return route.continue();
  });

  await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });

  // Wait for channels to appear
  await page.locator('text=Channel Alpha').waitFor({ state: 'visible', timeout: 10000 });
  await page.locator('text=Channel Beta').waitFor({ state: 'visible', timeout: 10000 });

  // Expand channels
  const alphaCardInitial = page.locator('div').filter({ hasText: 'Channel Alpha' }).filter({ hasText: 'Discover Videos' }).last();
  await alphaCardInitial.getByRole('button', { name: /Discover Videos/i }).click();
  await page.locator('text=Video A1 Alpha').waitFor({ state: 'visible', timeout: 10000 });
  await page.locator('text=Video A2 Alpha').waitFor({ state: 'visible', timeout: 10000 });

  const betaCardInitial = page.locator('div').filter({ hasText: 'Channel Beta' }).filter({ hasText: 'Discover Videos' }).last();
  await betaCardInitial.getByRole('button', { name: /Discover Videos/i }).click();
  await page.locator('text=Video B1 Beta').waitFor({ state: 'visible', timeout: 10000 });

  // ── SCENARIO A ─────────────────────────────────────────────────────────────
  await t.test('Scenario A — Cross-Channel Global Selection and Isolated Dispatch', async () => {
    capturedBatchRequests.length = 0;
    batchResponseStrategy = 'all_queued';

    await page.locator('text=Video A1 Alpha').click();
    await page.locator('text=Video A2 Alpha').click();
    await page.locator('text=Video B1 Beta').click();

    const stickyBarText = page.getByText(/3 Videos Selected/i).first();
    await stickyBarText.waitFor({ state: 'visible', timeout: 5000 });

    const globalStartBtn = page.getByRole('button', { name: /Start Processing \(3\)/i });
    await globalStartBtn.click();

    await page.waitForFunction(() => {
      return document.body.innerText.includes('Successfully queued 3 videos');
    }, { timeout: 10000 });

    assert.equal(capturedBatchRequests.length, 2, 'Should issue exactly 2 batch requests (1 per channel)');
    const reqAlpha = capturedBatchRequests.find(r => r.url.includes('ch_alpha_101'));
    const reqBeta = capturedBatchRequests.find(r => r.url.includes('ch_beta_202'));
    assert.ok(reqAlpha, 'Alpha request must be captured');
    assert.ok(reqBeta, 'Beta request must be captured');

    const alphaVids = reqAlpha?.postData?.videos || reqAlpha?.postData || [];
    const betaVids = reqBeta?.postData?.videos || reqBeta?.postData || [];
    assert.equal(alphaVids.length, 2, 'Alpha should contain exactly 2 videos');
    assert.equal(betaVids.length, 1, 'Beta should contain exactly 1 video');
  });

  // ── SCENARIO B ─────────────────────────────────────────────────────────────
  await t.test('Scenario B — Channel-Scoped Processing with Cross-Channel Selection Preserved', async () => {
    capturedBatchRequests.length = 0;
    batchResponseStrategy = 'all_queued';

    await page.locator('text=Video A1 Alpha').click();
    await page.locator('text=Video A2 Alpha').click();
    await page.locator('text=Video B1 Beta').click();

    await page.getByText(/3 Videos Selected/i).waitFor({ state: 'visible', timeout: 5000 });

    const alphaCard = page.locator('div').filter({ hasText: 'Channel Alpha' }).filter({ hasText: '🎥 Discovered Videos' }).first();
    const alphaChannelAction = alphaCard.locator('div').filter({ hasText: '2 video(s) selected' }).first();
    await alphaChannelAction.waitFor({ state: 'visible', timeout: 5000 });

    const alphaStartBtn = alphaChannelAction.getByRole('button', { name: /Start Processing \(2\)/i });
    await alphaStartBtn.click();

    await page.waitForTimeout(800);
    assert.equal(capturedBatchRequests.length, 1, 'Should issue exactly 1 request to Channel Alpha');
    assert.ok(capturedBatchRequests[0].url.includes('ch_alpha_101'), 'URL must belong to Channel Alpha');

    await page.getByText(/1 Video Selected/i).waitFor({ state: 'visible', timeout: 5000 });
  });

  // ── SCENARIO C ─────────────────────────────────────────────────────────────
  await t.test('Scenario C — Partial Success & Error Recovery', async () => {
    // C1: Network Error
    const clearBtn = page.getByRole('button', { name: /Clear All/i });
    await clearBtn.click();

    await page.locator('text=Video A1 Alpha').click();
    await page.locator('text=Video B1 Beta').click();
    await page.getByText(/2 Videos Selected/i).waitFor({ state: 'visible', timeout: 5000 });

    capturedBatchRequests.length = 0;
    batchResponseStrategy = 'channel_b_network_error';

    const globalStartBtnC = page.getByRole('button', { name: /Start Processing \(2\)/i });
    await globalStartBtnC.click();

    await page.waitForFunction(() => {
      const text = document.body.innerText;
      return text.includes('Partial batch result') && text.includes('1 video(s) remain selected');
    }, { timeout: 10000 });

    // Retry
    capturedBatchRequests.length = 0;
    batchResponseStrategy = 'all_queued';

    const retryBtn = page.getByRole('button', { name: /Start Processing/i }).last();
    await retryBtn.click();

    await page.waitForFunction(() => {
      return document.body.innerText.includes('Successfully queued 1 video');
    }, { timeout: 10000 });

    assert.equal(capturedBatchRequests.length, 1, 'Retry must submit ONLY Channel Beta');
    assert.ok(capturedBatchRequests[0].url.includes('ch_beta_202'), 'Retry request must be for Beta');

    // C2: Item Rejection
    capturedBatchRequests.length = 0;
    batchResponseStrategy = 'item_rejection';

    await page.locator('text=Video A1 Alpha').click();
    await page.locator('text=Video A2 Alpha').click();
    await page.getByText(/2 Videos Selected/i).waitFor({ state: 'visible', timeout: 5000 });

    const globalStartBtnC2 = page.getByRole('button', { name: /Start Processing/i }).last();
    await globalStartBtnC2.click();

    await page.waitForFunction(() => {
      return document.body.innerText.includes('Video duration exceeds Shorts limit');
    }, { timeout: 10000 });

    await page.getByText(/1 Video Selected/i).waitFor({ state: 'visible', timeout: 5000 });
  });

  // ── SCENARIO D ─────────────────────────────────────────────────────────────
  await t.test('Scenario D — Deselection & Clear Selection', async () => {
    await page.locator('text=Video A1 Alpha').click();
    await page.getByText(/2 Videos Selected/i).waitFor({ state: 'visible', timeout: 5000 });

    // Deselect A1
    await page.locator('text=Video A1 Alpha').click();
    await page.waitForTimeout(200);

    await page.getByText(/1 Video Selected/i).waitFor({ state: 'visible', timeout: 5000 });

    // Clear All
    const clearBtnD = page.getByRole('button', { name: /Clear All/i });
    await clearBtnD.click();
    await page.waitForTimeout(300);

    const stickyCountD = await page.getByText(/\d+ Videos? Selected/i).count();
    assert.equal(stickyCountD, 0, 'Sticky action bar must be unmounted after Clear All');
  });

  // ── SCENARIO E ─────────────────────────────────────────────────────────────
  await t.test('Scenario E — Browser Diagnostics & Console Integrity', async () => {
    assert.equal(pageErrors.length, 0, `Page errors encountered: ${pageErrors.join(', ')}`);
    const severeErrors = consoleMessages.filter(
      m => m.type === 'error' && !m.text.includes('Failed to load resource') && !m.text.includes('net::ERR_FAILED')
    );
    assert.equal(severeErrors.length, 0, `Severe console errors encountered: ${severeErrors.map(e => e.text).join('; ')}`);
  });

  await context.close();
  await browser.close();
});
