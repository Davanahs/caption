const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const artifactDir = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f';
  
  // Desktop full page
  const page1 = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page1.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {});
  await page1.waitForTimeout(2000);
  await page1.screenshot({ path: path.join(artifactDir, 'gaming_final_desktop.png'), fullPage: false });
  console.log('Desktop viewport screenshot saved');
  
  // Scroll and capture bottom section
  await page1.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page1.waitForTimeout(500);
  await page1.screenshot({ path: path.join(artifactDir, 'gaming_final_desktop_bottom.png'), fullPage: false });
  console.log('Desktop bottom screenshot saved');
  await page1.close();
  
  // 1280 desktop
  const page2 = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page2.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {});
  await page2.waitForTimeout(2000);
  await page2.screenshot({ path: path.join(artifactDir, 'gaming_final_1280.png'), fullPage: true });
  console.log('1280 screenshot saved');
  await page2.close();
  
  await browser.close();
  console.log('All screenshots done');
})().catch(err => { console.error(err.message); process.exit(1); });
