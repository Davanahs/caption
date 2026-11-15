import { chromium } from 'playwright';
import assert from 'assert/strict';

async function verifyUploadStudioChannelLock() {
  console.log('[VERIFY LOCK] Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log('[VERIFY LOCK] Navigating to http://localhost:3001/studio...');
  await page.goto('http://localhost:3001/studio', { waitUntil: 'networkidle', timeout: 30000 });

  // 1. Initial State: Channel selector is present and unlocked
  const destinationBar = page.locator('text=Multi-Destination Routing');
  await destinationBar.waitFor({ state: 'visible', timeout: 10000 });
  console.log('[VERIFY LOCK] Destination routing bar is visible.');

  // Check if lock badge is NOT present initially
  const lockBadge = page.locator('[data-testid="locked-channel-badge"]');
  const countBefore = await lockBadge.count();
  assert.strictEqual(countBefore, 0, 'Locked channel badge must not be visible before processing starts');

  // Check that destination checkboxes are selectable
  const checkboxes = page.locator('input[type="checkbox"]');
  const totalCheckboxes = await checkboxes.count();
  console.log(`[VERIFY LOCK] Found ${totalCheckboxes} destination checkboxes.`);

  if (totalCheckboxes > 0) {
    const firstCheckbox = checkboxes.first();
    const isDisabledBefore = await firstCheckbox.isDisabled();
    assert.strictEqual(isDisabledBefore, false, 'Checkbox must be enabled initially');

    // Click the first checkbox to select it
    await firstCheckbox.check();
    const isChecked = await firstCheckbox.isChecked();
    assert.strictEqual(isChecked, true, 'First checkbox should now be checked');
    console.log('[VERIFY LOCK] Checked destination channel successfully.');
  }

  // 2. Simulate processing state to verify lock behavior
  console.log('[VERIFY LOCK] Activating processing state...');
  await page.evaluate(() => {
    const studio = window.__clipforgeStudio;
    if (studio && studio.setBatchProcessingStatusForTest) {
      studio.setBatchProcessingStatusForTest('processing');
    }
  });

  await page.waitForTimeout(500);

  // 3. Verify locked badge is now visible
  const countAfter = await lockBadge.count();
  assert.strictEqual(countAfter, 1, 'Locked channel badge must be visible when batch status is processing');
  const badgeText = await lockBadge.innerText();
  console.log(`[VERIFY LOCK] Locked badge rendered: "${badgeText}"`);
  assert.ok(badgeText.includes('Channels Locked'), 'Badge must include "Channels Locked"');

  // 4. Verify all checkboxes are now disabled
  for (let i = 0; i < totalCheckboxes; i++) {
    const cb = checkboxes.nth(i);
    const isDisabled = await cb.isDisabled();
    assert.strictEqual(isDisabled, true, `Checkbox ${i} must be disabled while processing`);
  }
  console.log('[VERIFY LOCK] All checkboxes are strictly disabled (locked).');

  // 5. Verify locked label on selected channel
  const lockedLabel = page.locator('text=🔒 Locked');
  const lockedLabelCount = await lockedLabel.count();
  assert.ok(lockedLabelCount >= 1, 'Selected channel must show 🔒 Locked label');
  console.log('[VERIFY LOCK] Selected channel displays "🔒 Locked".');

  // Take screenshot of the locked destination routing area
  const screenshotPath = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/upload_studio_destination_locking_verified.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(`[VERIFY LOCK] Screenshot saved to ${screenshotPath}`);

  await browser.close();
  console.log('[VERIFY LOCK] SUCCESS: All assertions passed!');
}

verifyUploadStudioChannelLock().catch(err => {
  console.error('[VERIFY LOCK FAILED]', err);
  process.exit(1);
});
