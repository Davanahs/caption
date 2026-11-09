import test from 'node:test';
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

test('DEF-API-01: Browser URL validation and modal parity for supported and rejected YouTube URL formats', async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto('http://localhost:3000/');
    const input = page.locator('input[placeholder*="youtube.com"]').first();
    const generateBtn = page.locator('button:has-text("Generate")').first();

    const supportedFormats = [
      { url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', id: 'dQw4w9WgXcQ' },
      { url: 'https://www.youtube.com/embed/dQw4w9WgXcQ', id: 'dQw4w9WgXcQ' },
      { url: 'https://www.youtube.com/shorts/dQw4w9WgXcQ', id: 'dQw4w9WgXcQ' },
      { url: 'https://www.youtube.com/v/dQw4w9WgXcQ', id: 'dQw4w9WgXcQ' },
      { url: 'https://www.youtube.com/live/dQw4w9WgXcQ', id: 'dQw4w9WgXcQ' },
      { url: 'https://youtu.be/dQw4w9WgXcQ', id: 'dQw4w9WgXcQ' },
    ];

    for (const { url, id } of supportedFormats) {
      await input.fill(url);
      const isEnabled = await generateBtn.isEnabled();
      assert.equal(isEnabled, true, `Generate button should be enabled for supported URL: ${url}`);

      // Open modal to verify thumbnail CDN binding and extracted ID
      await generateBtn.click();
      await page.waitForTimeout(400);

      const modalHeader = page.locator('text=Configure Your Clips');
      assert.equal(await modalHeader.isVisible(), true, `Modal should open for URL: ${url}`);

      const thumbnailImg = page.locator(`img[src*="${id}"]`).first();
      assert.equal(await thumbnailImg.isVisible(), true, `Modal should display thumbnail for ID ${id}`);

      // Close modal
      const cancelBtn = page.locator('div[role="dialog"] button:has-text("Cancel")');
      await cancelBtn.click();
      await page.waitForTimeout(300);
    }

    const rejectedFormats = [
      'https://vimeo.com/123456789',
      'https://tiktok.com/@user/video/123',
      'https://google.com',
      'not-a-valid-url',
    ];

    for (const url of rejectedFormats) {
      await input.fill(url);
      const isEnabled = await generateBtn.isEnabled();
      assert.equal(isEnabled, false, `Generate button should be disabled for rejected URL: ${url}`);

      const isInvalid = await input.getAttribute('aria-invalid');
      assert.equal(isInvalid, 'true', `Input should have aria-invalid="true" for: ${url}`);
    }
  } finally {
    await browser.close();
  }
});

