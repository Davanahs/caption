import test from 'node:test';
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const APP_URL = process.env.APP_URL || 'http://localhost:3000/automation';

test('DEF-API-02: Scoring Mode Schema Parity in Real Browser', async (t) => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 }
  });
  const page = await context.newPage();

  try {
    await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);

    // Click 'Configure Default Profile' to expand drawer
    const configBtn = page.locator('button:has-text("Configure Default Profile")');
    if (await configBtn.isVisible()) {
      await configBtn.click();
      await page.waitForTimeout(500);
    }

    // Look for Scoring Mode select
    const scoringLabel = page.locator('label:has-text("Scoring Mode")');
    assert.ok(await scoringLabel.isVisible(), 'Scoring Mode label must be visible');

    const select = scoringLabel.locator('..').locator('select');
    assert.ok(await select.isVisible(), 'Scoring Mode select must be visible');

    const options = await select.locator('option').all();
    const optionValues = [];
    const optionTexts = [];
    for (const opt of options) {
      optionValues.push(await opt.getAttribute('value'));
      optionTexts.push(await opt.innerText());
    }

    // Verify option constraints
    assert.ok(optionValues.includes('ai'), 'Must include "ai" option');
    assert.ok(!optionValues.includes('heuristic'), 'Must NOT include legacy "heuristic" option');
    assert.equal(optionValues.length, 1, 'Scoring mode dropdown must have exactly 1 option ("ai")');
    assert.match(optionTexts[0], /AI Multimodal Scoring/i, 'Option label must indicate AI scoring');
  } finally {
    await browser.close();
  }
});
