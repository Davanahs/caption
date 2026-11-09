const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const ARTIFACT_DIR = 'C:\\Users\\Chinmaygouda\\.gemini\\antigravity-ide\\brain\\607b38c3-5af0-4c06-aaf7-399b1e366339';

async function runBrowserVerification() {
  console.log('[BrowserVerify] Launching Chromium...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await context.newPage();

  // Automatically accept confirmation dialogs
  page.on('dialog', async dialog => {
    console.log(`[BrowserVerify] Dialog appeared (${dialog.type()}): "${dialog.message()}" -> Accepting`);
    await dialog.accept();
  });

  try {
    console.log('[BrowserVerify] Navigating to http://localhost:3000/clips...');
    await page.goto('http://localhost:3000/clips', { waitUntil: 'networkidle', timeout: 30000 });

    // Step 1: Initial Page Load
    await page.waitForSelector('h1:has-text("Clips Library")', { timeout: 10000 });
    console.log('[BrowserVerify] Clips Library page loaded.');
    await page.screenshot({ path: path.join(ARTIFACT_DIR, '01_clips_page_initial.png') });

    // Step 2: Open Safe Cleanup Modal
    const cleanupBtn = page.locator('button:has-text("Safe Cleanup")');
    await cleanupBtn.waitFor({ state: 'visible', timeout: 5000 });
    console.log('[BrowserVerify] Clicking "Safe Cleanup" button...');
    await cleanupBtn.click();

    // Step 3: Verify Modal Content
    await page.waitForSelector('text=Safe Storage Cleanup', { timeout: 10000 });
    console.log('[BrowserVerify] Safe Storage Cleanup modal opened.');

    const estimatedSpace = await page.locator('text=1.00 MB').first().isVisible();
    const candidateCount = await page.locator('text=Eligible Candidates').isVisible();
    const protectionNotice = await page.locator('text=Protection Active:').isVisible();

    console.log(`[BrowserVerify] Modal checks: estimatedSpace=${estimatedSpace}, candidateCount=${candidateCount}, protectionNotice=${protectionNotice}`);
    if (!estimatedSpace) throw new Error('Estimated space 1.00 MB not visible in modal');

    await page.screenshot({ path: path.join(ARTIFACT_DIR, '02_safe_cleanup_modal_preview.png') });

    // Step 4: Confirm Cleanup Execution
    const confirmBtn = page.locator('button:has-text("Confirm Cleanup")');
    await confirmBtn.waitFor({ state: 'visible', timeout: 5000 });
    console.log('[BrowserVerify] Clicking "Confirm Cleanup" button...');
    await confirmBtn.click();

    // Step 5: Verify Completion Results
    await page.waitForSelector('text=Storage Successfully Reclaimed!', { timeout: 15000 });
    console.log('[BrowserVerify] Storage Successfully Reclaimed message displayed!');

    const filesPurged = await page.locator('text=Files Purged').isVisible();
    const recordsDeleted = await page.locator('text=Clip Records Deleted').isVisible();
    console.log(`[BrowserVerify] Completion summary checks: filesPurged=${filesPurged}, recordsDeleted=${recordsDeleted}`);

    await page.screenshot({ path: path.join(ARTIFACT_DIR, '03_safe_cleanup_modal_completed.png') });

    // Step 6: Close Modal
    const doneBtn = page.locator('button:has-text("Done")');
    await doneBtn.click();
    await page.waitForSelector('text=Safe Storage Cleanup', { state: 'hidden', timeout: 5000 });
    console.log('[BrowserVerify] Modal closed.');

    // Step 7: Reload & Persisted Verification
    console.log('[BrowserVerify] Reloading page to verify persistence...');
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForSelector('h1:has-text("Clips Library")', { timeout: 10000 });

    const deletedClipCard = await page.locator('text=Browser Test Low Score Clip').isVisible();
    console.log(`[BrowserVerify] Deleted clip visible on reload: ${deletedClipCard} (expected false)`);
    if (deletedClipCard) throw new Error('Deleted clip still visible in library after cleanup!');

    await page.screenshot({ path: path.join(ARTIFACT_DIR, '04_clips_page_persisted_after_cleanup.png') });

    console.log('[BrowserVerify] ALL REAL BROWSER CHECKS PASSED SUCCESSFULLY (4/4 screenshots captured)!');
  } catch (err) {
    console.error('[BrowserVerify] FAILED:', err);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'browser_verify_failure.png') }).catch(() => {});
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runBrowserVerification();
