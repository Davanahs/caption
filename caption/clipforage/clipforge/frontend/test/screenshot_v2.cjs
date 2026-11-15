const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('http://localhost:3000/gaming', { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ 
    path: 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/gaming_v2_full.png', 
    fullPage: true 
  });
  console.log('done');
  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
