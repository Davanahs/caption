import { chromium } from 'playwright';

async function capture() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log('Navigating to http://localhost:3001...');
  await page.goto('http://localhost:3001', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);

  const screenshotPath = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/pipeline_status_failed_cancelled.png';
  await page.screenshot({ path: screenshotPath });
  console.log('[SCREENSHOT SAVED]', screenshotPath);

  await browser.close();
}

capture().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
