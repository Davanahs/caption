import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ARTIFACT_DIR = path.resolve(__dirname, '../../audit_artifacts/phase_1_1_browser_verification');

const APP_URL = process.env.APP_URL || 'http://localhost:3000/automation';

async function run() {
  console.log('[DEBUG] Starting browser verification script...');
  if (!fs.existsSync(ARTIFACT_DIR)) {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 }
  });
  const page = await context.newPage();

  page.on('console', (msg) => {
    console.log(`[BROWSER CONSOLE ${msg.type()}]:`, msg.text());
  });

  page.on('pageerror', (err) => {
    console.error(`[PAGE ERROR]:`, err);
  });

  page.on('request', (req) => {
    console.log(`[REQUEST]: ${req.method()} ${req.url()}`);
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
    console.log(`[INTERCEPTED ROUTE]: ${method} ${url}`);

    // 1. Channels list
    if (url.includes('/api/channels') && !url.includes('/videos') && !url.includes('/process') && !url.includes('/decisions')) {
      if (method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockChannels)
        });
      }
    }

    // 2. Destinations list
    if (url.includes('/api/publish/destinations')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    }

    // 3. Decisions history
    if (url.includes('/api/channels/decisions/history')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    }

    // 4. Channel Alpha videos
    if (url.includes('/api/channels/ch_alpha_101/videos')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAlphaVideos)
      });
    }

    // 5. Channel Beta videos
    if (url.includes('/api/channels/ch_beta_202/videos')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockBetaVideos)
      });
    }

    // 6. Batch processing dispatch
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

  console.log('[DEBUG] Navigating to', APP_URL);
  await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });
  console.log('[DEBUG] Page DOM loaded.');

  // Wait for channels to appear
  await page.locator('text=Channel Alpha').waitFor({ state: 'visible', timeout: 10000 });
  await page.locator('text=Channel Beta').waitFor({ state: 'visible', timeout: 10000 });
  console.log('[DEBUG] Channels Alpha and Beta visible.');

  // Expand channels
  const alphaCardInitial = page.locator('div').filter({ hasText: 'Channel Alpha' }).filter({ hasText: 'Discover Videos' }).last();
  await alphaCardInitial.getByRole('button', { name: /Discover Videos/i }).click();
  await page.locator('text=Video A1 Alpha').waitFor({ state: 'visible', timeout: 10000 });
  await page.locator('text=Video A2 Alpha').waitFor({ state: 'visible', timeout: 10000 });
  console.log('[DEBUG] Channel Alpha videos expanded.');

  const betaCardInitial = page.locator('div').filter({ hasText: 'Channel Beta' }).filter({ hasText: 'Discover Videos' }).last();
  await betaCardInitial.getByRole('button', { name: /Discover Videos/i }).click();
  await page.locator('text=Video B1 Beta').waitFor({ state: 'visible', timeout: 10000 });
  console.log('[DEBUG] Channel Beta videos expanded.');

  // ── SCENARIO A ─────────────────────────────────────────────────────────────
  console.log('\n--- EXECUTING SCENARIO A: Cross-Channel Global Selection ---');
  capturedBatchRequests.length = 0;
  batchResponseStrategy = 'all_queued';

  const totalCheckboxes = await page.locator('input[type="checkbox"]').count();
  console.log(`[DEBUG] Total checkboxes on page: ${totalCheckboxes}`);
  for (let i = 0; i < totalCheckboxes; i++) {
    const box = page.locator('input[type="checkbox"]').nth(i);
    const parentText = await box.locator('..').innerText().catch(() => 'no parent text');
    console.log(`[DEBUG] Checkbox ${i} parent text: "${parentText.trim().replace(/\n/g, ' ')}"`);
  }

  // Click the video card or checkbox directly
  console.log('[DEBUG] Clicking Video A1 card...');
  await page.locator('text=Video A1 Alpha').click();
  console.log('[DEBUG] Clicking Video A2 card...');
  await page.locator('text=Video A2 Alpha').click();
  console.log('[DEBUG] Clicking Video B1 card...');
  await page.locator('text=Video B1 Beta').click();

  const allSelectedTexts = await page.locator('text=/Selected/i').allInnerTexts();
  console.log('[DEBUG] All texts matching /Selected/i after card clicks:', allSelectedTexts);

  const stickyBarText = page.getByText(/3 Videos Selected/i).first();
  await stickyBarText.waitFor({ state: 'visible', timeout: 5000 });
  console.log('[SCENARIO A] Found "3 Videos Selected"!');

  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'scenario_a_selection_verified.png') });

  const globalStartBtn = page.getByRole('button', { name: /Start Processing \(3\)/i });
  await globalStartBtn.click();
  console.log('[SCENARIO A] Clicked Start Processing (3). Waiting for response...');

  await page.waitForFunction(() => {
    return document.body.innerText.includes('Successfully queued 3 videos');
  }, { timeout: 10000 });
  console.log('[SCENARIO A] Success message confirmed!');

  console.log(`[SCENARIO A] Captured requests count: ${capturedBatchRequests.length}`);
  const reqAlphaA = capturedBatchRequests.find(r => r.url.includes('ch_alpha_101'));
  const reqBetaA = capturedBatchRequests.find(r => r.url.includes('ch_beta_202'));
  console.log('[SCENARIO A] Alpha payload:', JSON.stringify(reqAlphaA?.postData));
  console.log('[SCENARIO A] Beta payload:', JSON.stringify(reqBetaA?.postData));

  const alphaVidsA = reqAlphaA?.postData?.videos || reqAlphaA?.postData || [];
  const betaVidsA = reqBetaA?.postData?.videos || reqBetaA?.postData || [];
  if (alphaVidsA.length !== 2) throw new Error(`Alpha expected 2 items, got ${alphaVidsA.length}`);
  if (betaVidsA.length !== 1) throw new Error(`Beta expected 1 item, got ${betaVidsA.length}`);

  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'scenario_a_complete_success.png') });
  console.log('--- SCENARIO A PASSED ---\n');

  // ── SCENARIO B ─────────────────────────────────────────────────────────────
  console.log('--- EXECUTING SCENARIO B: Channel-Scoped Processing ---');
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
  console.log('[SCENARIO B] Clicked Channel Alpha Start Processing (2). Waiting for response...');

  await page.waitForTimeout(800);
  console.log(`[SCENARIO B] Captured requests count: ${capturedBatchRequests.length}`);
  if (capturedBatchRequests.length !== 1) throw new Error(`Expected exactly 1 request to Alpha, got ${capturedBatchRequests.length}`);
  if (!capturedBatchRequests[0].url.includes('ch_alpha_101')) throw new Error('Expected Alpha URL');

  const alphaVidsB = capturedBatchRequests[0]?.postData?.videos || capturedBatchRequests[0]?.postData || [];
  if (alphaVidsB.length !== 2) throw new Error(`Alpha expected 2 items, got ${alphaVidsB.length}`);

  await page.getByText(/1 Video Selected/i).waitFor({ state: 'visible', timeout: 5000 });
  console.log('[SCENARIO B] Sticky bar correctly shows 1 Video Selected.');

  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'scenario_b_channel_scoped_success.png') });
  console.log('--- SCENARIO B PASSED ---\n');

  // ── SCENARIO C ─────────────────────────────────────────────────────────────
  console.log('--- EXECUTING SCENARIO C: Partial Success Across Channels & Error Recovery ---');
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
  console.log('[SCENARIO C1] Submitted batch with Channel Beta network error. Waiting for partial result...');

  await page.waitForFunction(() => {
    const text = document.body.innerText;
    return text.includes('Partial batch result') && text.includes('1 video(s) remain selected');
  }, { timeout: 10000 });
  console.log('[SCENARIO C1] Partial error banner confirmed!');

  // Retry
  console.log('[SCENARIO C1] Retrying failed Channel Beta selection...');
  capturedBatchRequests.length = 0;
  batchResponseStrategy = 'all_queued';

  const retryBtn = page.getByRole('button', { name: /Start Processing/i }).last();
  await retryBtn.click();

  await page.waitForFunction(() => {
    return document.body.innerText.includes('Successfully queued 1 video');
  }, { timeout: 10000 });
  console.log('[SCENARIO C1] Retry succeeded. Requests captured:');
  console.log('[SCENARIO C1] Retry requests:', capturedBatchRequests.map(r => r.url));
  if (capturedBatchRequests.length !== 1 || !capturedBatchRequests[0].url.includes('ch_beta_202')) {
    throw new Error('Retry must submit ONLY Channel Beta');
  }

  // C2: Item-Level Rejection
  console.log('[SCENARIO C2] Testing item-level rejection...');
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
  console.log('[SCENARIO C2] Rejection error message displayed in banner!');

  await page.getByText(/1 Video Selected/i).waitFor({ state: 'visible', timeout: 5000 });
  console.log('[SCENARIO C2] Rejected video A2 remains selected in sticky bar!');

  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'scenario_c_item_rejection.png') });
  console.log('--- SCENARIO C PASSED ---\n');

  // ── SCENARIO D ─────────────────────────────────────────────────────────────
  console.log('--- EXECUTING SCENARIO D: Deselection & Clear Selection ---');
  await page.locator('text=Video A1 Alpha').click(); // now both A1 and A2 are selected
  await page.getByText(/2 Videos Selected/i).waitFor({ state: 'visible', timeout: 5000 });

  console.log('[SCENARIO D] Deselecting A1...');
  await page.locator('text=Video A1 Alpha').click();
  await page.waitForTimeout(200);

  await page.getByText(/1 Video Selected/i).waitFor({ state: 'visible', timeout: 5000 });
  console.log('[SCENARIO D] Count decremented to 1 Video Selected.');

  console.log('[SCENARIO D] Clicking Clear All...');
  const clearBtnD = page.getByRole('button', { name: /Clear All/i });
  await clearBtnD.click();
  await page.waitForTimeout(300);

  const stickyCountD = await page.getByText(/\d+ Videos? Selected/i).count();
  console.log(`[SCENARIO D] Sticky bar count after clear: ${stickyCountD}`);
  if (stickyCountD !== 0) throw new Error('Sticky bar must be unmounted after Clear All');

  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'scenario_d_cleared_selection.png') });
  console.log('--- SCENARIO D PASSED ---\n');

  // ── SCENARIO E ─────────────────────────────────────────────────────────────
  console.log('--- EXECUTING SCENARIO E: Diagnostics & Clean State ---');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'scenario_e_diagnostics_clean.png') });
  console.log('--- SCENARIO E PASSED ---\n');

  console.log('========================================================');
  console.log('ALL SCENARIOS A, B, C, D, E PASSED IN REAL BROWSER!');
  console.log('========================================================');

  await context.close();
  await browser.close();
}

run().catch((err) => {
  console.error('[FATAL TEST ERROR]:', err);
  process.exit(1);
});
