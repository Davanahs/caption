import { chromium } from 'playwright';
import path from 'path';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  
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
  console.log(`[VerifyStudio] Navigating to ${baseUrl}/studio ...`);
  await page.goto(`${baseUrl}/studio`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  console.log('[VerifyStudio] Console errors recorded:', consoleErrors.length);
  if (consoleErrors.length > 0) {
    console.error('[VerifyStudio] Errors:', consoleErrors);
  }

  // Check if delete-batch-button is present and test clicking it
  const deleteBtn = await page.$('[data-testid="delete-batch-button"]');
  if (deleteBtn) {
    console.log('[VerifyStudio] Found delete-batch-button, clicking it...');
    await deleteBtn.click();
    await page.waitForTimeout(2000);
  } else {
    console.log('[VerifyStudio] Staging area clean / empty initial state.');
  }

  const screenshotPath = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/studio_verified_clean.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log('[VerifyStudio] Screenshot saved at:', screenshotPath);

  await browser.close();

  if (consoleErrors.length > 0) {
    console.error('[VerifyStudio] FAILED with console errors.');
    process.exit(1);
  } else {
    console.log('[VerifyStudio] SUCCESS: 0 console errors detected!');
  }
}

run().catch((err) => {
  console.error('[VerifyStudio] Fatal runner error:', err);
  process.exit(1);
});
