import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
  
  // Navigate with reload to ensure fresh bundle
  await page.goto('http://localhost:3000/automation', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  // Click edit profile on the monitored channel
  const editBtn = page.locator('button:has-text("Edit Profile")').first();
  await editBtn.waitFor({ state: 'visible', timeout: 5000 });
  await editBtn.click();
  await page.waitForTimeout(1000);

  // Inspect modal
  const info = await page.evaluate(() => {
    const allH3 = Array.from(document.querySelectorAll('h3'));
    const modalHeading = allH3.find(h => h.textContent.includes('Default Profile for'));
    if (!modalHeading) return { error: 'Modal heading not found', h3s: allH3.map(h => h.textContent) };
    
    const modalEl = modalHeading.closest('.glass');
    const overlay = modalEl.parentElement;
    
    let curr = overlay;
    const chain = [];
    while (curr) {
      const cs = window.getComputedStyle(curr);
      chain.push({
        tag: curr.tagName,
        className: curr.className,
        position: cs.position,
        transform: cs.transform
      });
      curr = curr.parentElement;
    }

    return {
      windowSize: { width: window.innerWidth, height: window.innerHeight },
      overlayRect: {
        top: overlay.getBoundingClientRect().top,
        left: overlay.getBoundingClientRect().left,
        width: overlay.getBoundingClientRect().width,
        height: overlay.getBoundingClientRect().height
      },
      modalRect: {
        top: modalEl.getBoundingClientRect().top,
        left: modalEl.getBoundingClientRect().left,
        width: modalEl.getBoundingClientRect().width,
        height: modalEl.getBoundingClientRect().height,
        bottom: modalEl.getBoundingClientRect().bottom
      },
      chain
    };
  });

  console.log('MEASUREMENTS:', JSON.stringify(info, null, 2));
  
  // Take screenshot of the exact viewport (not beyond viewport)
  await page.screenshot({ path: 'test/modal_1366x768_verified.png', fullPage: false });
  
  // Also test 1440x900
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'test/modal_1440x900_verified.png', fullPage: false });

  // Also test 1920x1080
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'test/modal_1920x1080_verified.png', fullPage: false });

  await browser.close();
})();
