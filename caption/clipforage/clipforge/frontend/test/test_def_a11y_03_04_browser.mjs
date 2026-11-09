import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const APP_URL = process.env.APP_URL || 'http://localhost:3000/';

test('DEF-A11Y-03 & DEF-A11Y-04: ScoreRing Semantics & Dashboard Dynamic aria-invalid in Real Browser', async (t) => {
  // Unit check for ScoreRing
  await t.test('1. DEF-A11Y-03: ScoreRing in clips/page.tsx has role="meter", aria-valuenow, aria-valuemin, aria-valuemax', () => {
    const clipsPagePath = path.resolve(__dirname, '../app/clips/page.tsx');
    assert.ok(fs.existsSync(clipsPagePath), 'clips/page.tsx must exist');
    const clipsSource = fs.readFileSync(clipsPagePath, 'utf8');

    assert.ok(clipsSource.includes('role="meter"'), 'ScoreRing must have role="meter"');
    assert.ok(clipsSource.includes('aria-label='), 'ScoreRing must have aria-label');
    assert.ok(clipsSource.includes('aria-valuenow={boundedScore}'), 'ScoreRing must have dynamic aria-valuenow');
    assert.ok(clipsSource.includes('aria-valuemin={0}'), 'ScoreRing must have aria-valuemin={0}');
    assert.ok(clipsSource.includes('aria-valuemax={10}'), 'ScoreRing must have aria-valuemax={10}');
    assert.ok(clipsSource.includes('aria-hidden="true"'), 'Inner score text should be aria-hidden');
  });

  // Browser check for DEF-A11Y-04
  await t.test('2. DEF-A11Y-04: Dashboard URL input dynamically updates aria-invalid and aria-describedby', async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1400, height: 900 }
    });
    const page = await context.newPage();

    try {
      await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(500);

      const urlInput = page.locator('#dashboard-youtube-url');
      assert.ok(await urlInput.isVisible(), 'Dashboard URL input must be visible');

      // State A: Empty input -> aria-invalid false / omitted
      const initialAriaInvalid = await urlInput.getAttribute('aria-invalid');
      assert.equal(initialAriaInvalid, 'false', 'Initial empty input should not have aria-invalid="true"');

      // State B: Invalid URL -> aria-invalid="true", aria-describedby points to error
      await urlInput.fill('https://vimeo.com/invalid-video');
      await page.waitForTimeout(200);

      const invalidAria = await urlInput.getAttribute('aria-invalid');
      assert.equal(invalidAria, 'true', 'Invalid URL must trigger aria-invalid="true"');

      const describedBy = await urlInput.getAttribute('aria-describedby');
      assert.equal(describedBy, 'dashboard-youtube-url-error', 'aria-describedby must match error alert element ID');

      const errorAlert = page.locator('#dashboard-youtube-url-error');
      assert.ok(await errorAlert.isVisible(), 'Error alert element must be visible when invalid');
      const errorText = await errorAlert.innerText();
      assert.match(errorText, /valid YouTube video/i, 'Error message must describe valid formats');

      // State C: Valid URL -> aria-invalid="false", error alert disappears
      await urlInput.fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
      await page.waitForTimeout(200);

      const validAria = await urlInput.getAttribute('aria-invalid');
      assert.equal(validAria, 'false', 'Valid YouTube URL must set aria-invalid="false"');
      assert.equal(await errorAlert.isVisible(), false, 'Error alert must be hidden when input is valid');
    } finally {
      await browser.close();
    }
  });
});
