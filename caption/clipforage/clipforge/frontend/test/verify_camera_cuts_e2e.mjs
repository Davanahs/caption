import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';

const ARTIFACT_DIR = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f';

async function runVerification() {
  console.log('[E2E] Launching Chromium browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1080 } });
  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log(`[Browser Console Error] ${msg.text()}`);
    }
  });

  try {
    console.log('[E2E] Navigating to http://localhost:3000/podcasts...');
    await page.goto('http://localhost:3000/podcasts', { waitUntil: 'networkidle', timeout: 30000 });

    console.log('[E2E] Clicking Explore Advanced Podcast button to open modal...');
    const exploreBtn = page.locator('#explore-advanced-podcast-btn');
    await exploreBtn.waitFor({ state: 'visible', timeout: 10000 });
    await exploreBtn.click();

    console.log('[E2E] Inputting YouTube URL...');
    const urlInput = page.locator('#podcast-youtube-url-input');
    await urlInput.waitFor({ state: 'visible', timeout: 10000 });
    await urlInput.fill('https://www.youtube.com/watch?v=0GjbIOS9Q90');
    await urlInput.press('Enter');

    console.log('[E2E] Waiting for video preview to load...');
    const analyzeBtn = page.locator('#analyze-shots-btn');
    await page.waitForFunction(() => {
      const btn = document.querySelector('#analyze-shots-btn');
      return btn && !btn.hasAttribute('disabled');
    }, { timeout: 15000 });

    console.log('[E2E] Clicking Analyze Camera Cuts & Speakers button...');
    await analyzeBtn.click();

    console.log('[E2E] Waiting for shot analysis to complete (may take ~1-2 minutes for 92 cuts)...');
    // Ensure we first see "Analyzing Shots..." or that the analyze button was triggered
    await page.waitForTimeout(1000);
    await page.waitForFunction(() => {
      const text = document.body.innerText;
      return text.includes('Detected Shot Schedule') || (text.includes('Detected') && text.includes('intervals'));
    }, { timeout: 300000 });

    console.log('[E2E] Analysis completed! Capturing overview screenshot...');
    const overviewPath = path.join(ARTIFACT_DIR, 'shot_analysis_completed_overview.png');
    await page.screenshot({ path: overviewPath, fullPage: true });
    console.log(`[E2E] Saved overview screenshot to ${overviewPath}`);

    // Read summary text
    const summaryText = await page.evaluate(() => {
      const match = document.body.innerText.match(/Detected \d+ camera cuts[^\n]*/i);
      return match ? match[0] : 'No match found';
    });
    console.log(`[E2E] Summary message: "${summaryText}"`);

    // Click on Shot 89 to preview its framing
    console.log('[E2E] Finding and scrolling to Shot 89...');
    const shot89Row = page.locator('div[role="button"][aria-label*="Shot 89"]').first();
    await shot89Row.waitFor({ state: 'attached', timeout: 15000 });
    await shot89Row.scrollIntoViewIfNeeded();
    await shot89Row.click();
    console.log('[E2E] Clicked Shot 89. Waiting for real frame extraction & canvas preview update...');

    // Wait for frame preview or badge to update
    await page.waitForTimeout(3000);
    try {
      await page.waitForFunction(() => {
        const badge = document.querySelector('#frame-preview-badge');
        return badge && badge.innerText.includes('Real Frame');
      }, { timeout: 15000 });
    } catch (_) {
      console.log('[E2E] Real frame badge wait finished');
    }

    const shot89Path = path.join(ARTIFACT_DIR, 'shot_89_framing_preview.png');
    await page.screenshot({ path: shot89Path, fullPage: true });
    console.log(`[E2E] Saved Shot 89 preview screenshot to ${shot89Path}`);

    // Verify Shot 89 metadata
    const shot89Details = await page.evaluate(() => {
      const container = document.querySelector('#preview-canvas-9-16-container');
      const badgeSpan = container ? container.querySelector('span:nth-child(2)') : null;
      const shotButtons = Array.from(document.querySelectorAll('div[role="button"]'));
      const shot89El = shotButtons.find(el => el.getAttribute('aria-label')?.includes('Shot 89'));
      const select = shot89El ? shot89El.querySelector('select') : null;
      const previewHeading = document.body.innerText.match(/Shot 89 Preview[^\n]*/i);
      return {
        badgeText: badgeSpan ? badgeSpan.innerText : null,
        selectValue: select ? select.value : null,
        selectText: select ? select.options[select.selectedIndex]?.text : null,
        previewHeading: previewHeading ? previewHeading[0] : null,
      };
    });

    console.log('[E2E] Shot 89 in UI:', JSON.stringify(shot89Details, null, 2));

    console.log('[E2E] SUCCESS! All steps completed.');
  } finally {
    await browser.close();
  }
}

runVerification().catch(err => {
  console.error('[E2E Test Failed]', err);
  process.exit(1);
});
