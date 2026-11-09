import test from 'node:test';
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const APP_URL = process.env.APP_URL || 'http://localhost:3000/';

test('DEF-A11Y-01 & DEF-A11Y-02: Modal ARIA Dialog Roles & Focus Trap in Real Browser', async (t) => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 }
  });
  const page = await context.newPage();

  try {
    await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);

    // 1. Trigger ProcessVideoModal from dashboard
    const input = page.locator('input[placeholder*="youtube.com"]').first();
    const generateBtn = page.locator('button:has-text("Generate")').first();

    await input.fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    await generateBtn.click();
    await page.waitForTimeout(500);

    // 2. DEF-A11Y-01 Verification: ARIA dialog attributes
    const dialog = page.locator('div[role="dialog"]');
    assert.ok(await dialog.isVisible(), 'Modal container must have role="dialog" and be visible');

    const ariaModal = await dialog.getAttribute('aria-modal');
    assert.equal(ariaModal, 'true', 'Modal must have aria-modal="true"');

    const labelledBy = await dialog.getAttribute('aria-labelledby');
    assert.ok(labelledBy, 'Modal must have aria-labelledby');

    const titleEl = page.locator(`#${labelledBy}`);
    assert.ok(await titleEl.isVisible(), `Element with id="${labelledBy}" must be visible`);
    const titleText = await titleEl.innerText();
    assert.match(titleText, /Configure Your Clips/i, 'Title element must contain modal title');

    // 3. DEF-A11Y-02 Verification: Keyboard focus trap
    // Verify focused element is inside dialog
    const initialFocusedInDialog = await page.evaluate(() => {
      const active = document.activeElement;
      const modal = document.querySelector('div[role="dialog"]');
      return modal ? modal.contains(active) : false;
    });
    assert.ok(initialFocusedInDialog, 'Initial focus must be within the modal dialog');

    // Tab 10 times forward - must never escape the dialog
    for (let i = 0; i < 10; i++) {
      await page.keyboard.press('Tab');
      const focusedInside = await page.evaluate(() => {
        const active = document.activeElement;
        const modal = document.querySelector('div[role="dialog"]');
        return modal ? modal.contains(active) : false;
      });
      assert.ok(focusedInside, `Tab cycle step ${i} must remain inside modal dialog`);
    }

    // Shift+Tab 5 times backward - must remain inside dialog
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('Shift+Tab');
      const focusedInside = await page.evaluate(() => {
        const active = document.activeElement;
        const modal = document.querySelector('div[role="dialog"]');
        return modal ? modal.contains(active) : false;
      });
      assert.ok(focusedInside, `Shift+Tab step ${i} must remain inside modal dialog`);
    }

    // Escape closes modal
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);

    assert.equal(await dialog.isVisible(), false, 'Pressing Escape must close the dialog');
  } finally {
    await browser.close();
  }
});
