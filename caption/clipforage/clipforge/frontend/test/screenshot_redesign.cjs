const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const artifactDir = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f';
  
  const viewports = [
    { name: 'desktop_1440', width: 1440, height: 900 },
    { name: 'desktop_1280', width: 1280, height: 800 },
    { name: 'tablet_768', width: 768, height: 1024 },
  ];

  for (const vp of viewports) {
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
    await page.goto('http://localhost:3001/gaming', { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(artifactDir, `gaming_redesign_${vp.name}.png`), fullPage: true });
    console.log(`Screenshot saved: gaming_redesign_${vp.name}.png`);
    await page.close();
  }
  
  await browser.close();
  console.log('Done');
})().catch(err => { console.error(err.message); process.exit(1); });
