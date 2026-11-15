import { chromium } from 'playwright';
import path from 'path';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });
  page.on('pageerror', (err) => {
    consoleErrors.push(err.toString());
  });

  const baseUrl = process.env.BASE_URL || 'http://localhost:3000';
  console.log(`[VerifyPodcastStorage] Navigating to ${baseUrl}/podcasts ...`);
  await page.goto(`${baseUrl}/podcasts`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // 1. Verify tabs exist
  const urlTab = await page.$('#podcast-tab-url-btn');
  const fileTab = await page.$('#podcast-tab-file-btn');
  if (!urlTab || !fileTab) {
    throw new Error('Source mode toggle tabs (#podcast-tab-url-btn, #podcast-tab-file-btn) not found!');
  }
  console.log('[VerifyPodcastStorage] Found both YouTube URL and System Storage tabs.');

  // 2. Click System Storage tab
  console.log('[VerifyPodcastStorage] Clicking System Storage tab...');
  await fileTab.click();
  await page.waitForTimeout(1000);

  // 3. Verify System Storage dropzone is displayed
  const dropzone = await page.$('#podcast-file-dropzone');
  const browseBtn = await page.$('#podcast-browse-file-btn');
  if (!dropzone || !browseBtn) {
    throw new Error('System Storage dropzone or browse button not rendered!');
  }
  console.log('[VerifyPodcastStorage] Successfully displayed System Storage dropzone and browse button.');

  // 4. Capture screenshot of System Storage tab
  const screenshotPath = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/podcast_system_storage_verified.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log('[VerifyPodcastStorage] Screenshot saved at:', screenshotPath);

  // 5. Click back to YouTube tab and check URL input
  console.log('[VerifyPodcastStorage] Switching back to YouTube URL tab...');
  await urlTab.click();
  await page.waitForTimeout(500);
  const urlInput = await page.$('#podcast-youtube-url-input');
  if (!urlInput) {
    throw new Error('YouTube URL input not found after switching back!');
  }
  console.log('[VerifyPodcastStorage] YouTube URL tab switched smoothly.');

  // 6. Switch back to System Storage tab for final state
  await fileTab.click();
  await page.waitForTimeout(500);

  await browser.close();

  console.log('[VerifyPodcastStorage] Console errors recorded:', consoleErrors.length);
  if (consoleErrors.length > 0) {
    console.error('[VerifyPodcastStorage] Errors:', consoleErrors);
    process.exit(1);
  } else {
    console.log('[VerifyPodcastStorage] SUCCESS: 0 console errors detected!');
  }
}

run().catch((err) => {
  console.error('[VerifyPodcastStorage] FAILED:', err);
  process.exit(1);
});

