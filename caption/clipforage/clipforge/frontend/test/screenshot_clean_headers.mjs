import { chromium } from 'playwright';

async function capture() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log('Navigating to http://localhost:3001/gaming...');
  await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle' });

  const input = page.locator('#gaming-youtube-url-input');
  await input.fill('https://www.youtube.com/watch?v=OVgNvkHGOlE');
  const loadBtn = page.locator('#open-gaming-studio-url-btn');
  await loadBtn.click();

  await page.waitForTimeout(3000);

  const screenshotPath = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/gaming_headers_removed_layout.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log('[SCREENSHOT SAVED]', screenshotPath);

  await browser.close();
}

capture().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
