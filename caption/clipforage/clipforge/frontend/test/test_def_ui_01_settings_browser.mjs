import test from 'node:test';
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const APP_URL = process.env.APP_URL || 'http://localhost:3000/settings';

test('DEF-UI-01: Settings numeric validation and zero/negative rejection in real browser', async (t) => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 }
  });
  const page = await context.newPage();

  // Route interception using RegExp to match both relative and cross-origin localhost:8000
  await page.route(/.*\/api\/settings.*/, async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          YOUTUBE_CLIENT_ID: 'test_client_id_123',
          YOUTUBE_CLIENT_SECRET_SET: true,
          OPENROUTER_API_KEY_SET: true,
          OPENROUTER_MODEL: 'deepseek/deepseek-r1:free',
          GROQ_API_KEY_SET: true,
          GROQ_MODEL: 'whisper-large-v3-turbo',
          NVIDIA_API_KEY_SET: true,
          NVIDIA_MODEL: 'meta/llama-3.1-405b-instruct',
          WHISPER_MODEL: 'base',
          CLIPS_PER_VIDEO: 5,
          CHANNEL_CHECK_INTERVAL_MINUTES: 30,
          last_updated_at: '2026-11-04T12:00:00Z',
        }),
      });
    } else if (route.request().method() === 'PUT') {
      const postData = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...postData,
          status: 'success',
          last_updated_at: new Date().toISOString(),
        }),
      });
    } else {
      await route.continue();
    }
  });

  try {
    await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });

    // Wait until settings have loaded and Save button is enabled
    const saveBtn = page.locator('button:has-text("Save Settings")');
    await page.waitForSelector('button:has-text("Save Settings"):not([disabled])', { timeout: 10000 });

    const clipsInput = page.locator('#clips-limit');
    const intervalInput = page.locator('#channel-interval');

    assert.ok(await clipsInput.isVisible(), 'Clips limit input must be visible');
    assert.ok(await intervalInput.isVisible(), 'Channel interval input must be visible');

    // Verify initial values loaded from mock
    assert.equal(await clipsInput.inputValue(), '5', 'Initial clips limit should be 5');
    assert.equal(await intervalInput.inputValue(), '30', 'Initial interval should be 30');

    // Test 1: Enter 0 for clips limit -> Rejection without falsy coercion to 5
    await clipsInput.fill('0');
    await saveBtn.click();
    await page.waitForTimeout(300);

    const alertError = page.locator('[data-testid="alert-settings-error"]');
    assert.ok(await alertError.isVisible(), 'Error alert should be visible when 0 is entered');
    const errText0 = await alertError.innerText();
    assert.match(errText0, /between 1 and 20/i, 'Error message must specify between 1 and 20');
    assert.equal(await clipsInput.inputValue(), '0', 'Input must retain 0 and not be coerced to 5');

    // Test 2: Enter -1 for clips limit -> Rejection of negative numbers
    await clipsInput.fill('-1');
    await saveBtn.click();
    await page.waitForTimeout(300);

    assert.ok(await alertError.isVisible(), 'Error alert should be visible for -1');
    const errTextNeg = await alertError.innerText();
    assert.match(errTextNeg, /between 1 and 20/i, 'Error message must reject negative integer');
    assert.equal(await clipsInput.inputValue(), '-1', 'Input must retain -1');

    // Test 3: Enter 0 for channel interval -> Rejection
    await clipsInput.fill('5');
    await intervalInput.fill('0');
    await saveBtn.click();
    await page.waitForTimeout(300);

    assert.ok(await alertError.isVisible(), 'Error alert should be visible for interval 0');
    const errTextInt0 = await alertError.innerText();
    assert.match(errTextInt0, /between 5 and 1440/i, 'Error message must specify interval bounds 5 to 1440');
    assert.equal(await intervalInput.inputValue(), '0', 'Input must retain 0');

    // Test 4: Enter valid boundary values (e.g. clips=1, interval=5) -> Success
    await clipsInput.fill('1');
    await intervalInput.fill('5');
    await saveBtn.click();
    await page.waitForTimeout(400);

    const alertSuccess = page.locator('[data-testid="alert-settings-success"]');
    assert.ok(await alertSuccess.isVisible(), 'Success alert should be visible for valid boundary inputs');
  } finally {
    await browser.close();
  }
});
