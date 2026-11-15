import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ARTIFACT_DIR = path.resolve('C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f');
const BASE_URL = process.env.BASE_URL || 'http://localhost:3001';

async function runBrowserVerification() {
  console.log('[BROWSER VERIFICATION] Starting comprehensive Chromium verification...');
  if (!fs.existsSync(ARTIFACT_DIR)) {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
  });
  const page = await context.newPage();

  // Mock API responses to guarantee rich, deterministic multi-destination UI state
  await page.route('**/api/youtube-channels**', async (route) => {
    if (route.request().method() === 'GET') {
      const url = route.request().url();
      if (url.includes('/outro/preview')) {
        await route.fulfill({
          status: 200,
          contentType: 'video/mp4',
          body: Buffer.from('fake-mp4-stream'),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'dest_alpha_01',
            youtube_channel_id: 'UC_PODCAST_SHORTS_001',
            channel_name: 'Podcast Shorts',
            channel_url: 'https://youtube.com/@podcastshorts',
            thumbnail_url: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=120',
            google_account_identity: 'creator@clipforge.io',
            upload_permission_status: 'granted',
            is_authorized: true,
            ready_for_publishing: true,
            has_outro: true,
            outro_status: 'configured',
            active_outro: {
              id: 'outro_v_01',
              channel_id: 'dest_alpha_01',
              outro_type: 'video',
              duration_seconds: 4.5,
              original_filename: 'brand_video_outro.mp4',
              file_size_bytes: 2450000,
              width: 1080,
              height: 1920,
              has_audio: true,
              version: 2,
              is_active: true,
              preview_url: '/api/youtube-channels/dest_alpha_01/outro/preview',
            },
          },
          {
            id: 'dest_beta_02',
            youtube_channel_id: 'UC_PODCAST_CLIPS_002',
            channel_name: 'Podcast Highlights',
            channel_url: 'https://youtube.com/@podcasthighlights',
            thumbnail_url: 'https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?w=120',
            google_account_identity: 'creator@clipforge.io',
            upload_permission_status: 'granted',
            is_authorized: true,
            ready_for_publishing: true,
            has_outro: true,
            outro_status: 'configured',
            active_outro: {
              id: 'outro_img_02',
              channel_id: 'dest_beta_02',
              outro_type: 'image',
              duration_seconds: 3.0,
              original_filename: 'ending_slate.png',
              file_size_bytes: 840000,
              width: 1080,
              height: 1920,
              has_audio: false,
              version: 1,
              is_active: true,
              preview_url: '/api/youtube-channels/dest_beta_02/outro/preview',
            },
          },
          {
            id: 'dest_gamma_03',
            youtube_channel_id: 'UC_GENERAL_003',
            channel_name: 'General Entertainment',
            channel_url: 'https://youtube.com/@generalent',
            thumbnail_url: 'https://images.unsplash.com/photo-1534447677768-be436bb09401?w=120',
            google_account_identity: 'creator@clipforge.io',
            upload_permission_status: 'granted',
            is_authorized: true,
            ready_for_publishing: true,
            has_outro: false,
            outro_status: 'none',
            active_outro: null,
          },
        ]),
      });
      return;
    }
    await route.continue();
  });

  await page.route('**/api/channels**', async (route) => {
    if (route.request().method() === 'GET') {
      const url = route.request().url();
      if (url.includes('/destinations')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            { id: 'dest_alpha_01', channel_name: 'Podcast Shorts', is_authorized: true, is_active: true },
            { id: 'dest_beta_02', channel_name: 'Podcast Highlights', is_authorized: true, is_active: true },
          ]),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'src_chan_101',
            channel_name: 'Huberman Lab Podcast',
            channel_url: 'https://youtube.com/@hubermanlab',
            thumbnail_url: 'https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=120',
            is_active: true,
            auto_clip: true,
            auto_publish: true,
            destination_channels: [
              { id: 'dest_alpha_01', channel_name: 'Podcast Shorts', is_active: true, is_authorized: true },
              { id: 'dest_beta_02', channel_name: 'Podcast Highlights', is_active: true, is_authorized: true },
              { id: 'dest_disconnected_09', channel_name: 'Old Channel (Revoked)', is_active: false, is_authorized: false },
            ],
          },
        ]),
      });
      return;
    }
    await route.continue();
  });

  await page.route('**/api/publish/**', async (route) => {
    const url = route.request().url();
    if (url.includes('/preview-info')) {
      const isBeta = url.includes('dest_beta_02');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          clip_id: 'c_test_demo_01',
          destination_id: isBeta ? 'dest_beta_02' : 'dest_alpha_01',
          destination_name: isBeta ? 'Podcast Highlights' : 'Podcast Shorts',
          base_duration: 52.0,
          total_duration: isBeta ? 55.0 : 56.5,
          exceeds_shorts_limit: false,
          has_outro: true,
          preview_url: `/api/publish/clips/c_test_demo_01/destinations/${isBeta ? 'dest_beta_02' : 'dest_alpha_01'}/preview`,
          outro: {
            outro_type: isBeta ? 'image' : 'video',
            duration_seconds: isBeta ? 3.0 : 4.5,
            filename: isBeta ? 'ending_slate.png' : 'brand_video_outro.mp4',
          },
        }),
      });
      return;
    }
    if (url.includes('/targets')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'pt_01',
            clip_id: 'c_test_demo_01',
            destination_id: 'dest_alpha_01',
            destination_name: 'Podcast Shorts',
            status: 'published',
            youtube_video_id: 'dQw4w9WgXcQ',
            privacy: 'private',
            retry_count: 0,
            has_outro: true,
            outro_type: 'video',
          },
          {
            id: 'pt_02',
            clip_id: 'c_test_demo_01',
            destination_id: 'dest_beta_02',
            destination_name: 'Podcast Highlights',
            status: 'failed',
            error_message: 'Upload stream chunk timeout (retriable)',
            privacy: 'private',
            retry_count: 1,
            has_outro: true,
            outro_type: 'image',
          },
          {
            id: 'pt_03',
            clip_id: 'c_test_demo_01',
            destination_id: 'dest_gamma_03',
            destination_name: 'General Entertainment',
            status: 'publishing',
            progress: 68,
            privacy: 'private',
            retry_count: 0,
            has_outro: false,
          },
        ]),
      });
      return;
    }
    await route.continue();
  });

  await page.route('**/api/clips**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 'c_test_demo_01',
              title: 'Mastering Dopamine for Focus and Motivation',
              duration: 52.0,
              status: 'ready',
              publish_targets: [
                { id: 'pt_01', destination_id: 'dest_alpha_01', destination_name: 'Podcast Shorts', status: 'published', youtube_video_id: 'dQw4w9WgXcQ' },
                { id: 'pt_02', destination_id: 'dest_beta_02', destination_name: 'Podcast Highlights', status: 'failed' },
                { id: 'pt_03', destination_id: 'dest_gamma_03', destination_name: 'General Entertainment', status: 'publishing' },
              ],
            },
          ],
          total: 1,
        }),
      });
      return;
    }
    await route.continue();
  });

  // 1. Verify YouTube Channels Page
  console.log('[1/5] Testing /youtube-channels...');
  await page.goto(`${BASE_URL}/youtube-channels`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const ytShotPath = path.join(ARTIFACT_DIR, 'e2e_browser_youtube_channels.png');
  await page.screenshot({ path: ytShotPath, fullPage: true });
  console.log(`Saved screenshot: ${ytShotPath}`);

  // 2. Verify Automation Page
  console.log('[2/5] Testing /automation...');
  await page.goto(`${BASE_URL}/automation`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const autoShotPath = path.join(ARTIFACT_DIR, 'e2e_browser_automation.png');
  await page.screenshot({ path: autoShotPath, fullPage: true });
  console.log(`Saved screenshot: ${autoShotPath}`);

  // 3. Verify Publish Page
  console.log('[3/5] Testing /publish...');
  await page.goto(`${BASE_URL}/publish`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const pubShotPath = path.join(ARTIFACT_DIR, 'e2e_browser_publish.png');
  await page.screenshot({ path: pubShotPath, fullPage: true });
  console.log(`Saved screenshot: ${pubShotPath}`);

  // 4. Verify Clips Page
  console.log('[4/5] Testing /clips...');
  await page.goto(`${BASE_URL}/clips`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const clipsShotPath = path.join(ARTIFACT_DIR, 'e2e_browser_clips.png');
  await page.screenshot({ path: clipsShotPath, fullPage: true });
  console.log(`Saved screenshot: ${clipsShotPath}`);

  // 5. Verify Main Page Intake Modal
  console.log('[5/5] Testing Main Page & Intake Modal...');
  await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  // Look for Process Video button
  const processBtn = await page.$('button:has-text("Process Video"), button:has-text("New Video"), button:has-text("Upload")');
  if (processBtn) {
    await processBtn.click();
    await page.waitForTimeout(600);
  }
  const intakeShotPath = path.join(ARTIFACT_DIR, 'e2e_browser_intake_modal.png');
  await page.screenshot({ path: intakeShotPath, fullPage: true });
  console.log(`Saved screenshot: ${intakeShotPath}`);

  await browser.close();
  console.log('[BROWSER VERIFICATION COMPLETE] All 5 screenshots captured successfully!');
}

runBrowserVerification().catch((err) => {
  console.error('[BROWSER VERIFICATION ERROR]:', err);
  process.exit(1);
});

