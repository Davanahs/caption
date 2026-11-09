import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const workspaceRoot = path.resolve(__dirname, '../../../');

const video1Path = path.join(workspaceRoot, 'Quick Singing Lesson_ Doremi Magic.mp4');
const video2Path = path.join(workspaceRoot, 'Quick Singing Lesson_ Doremi Magic_blur.mp4');
const video3Path = path.join(workspaceRoot, 'Quick Singing Lesson_ Doremi Magic_padded_blur.mp4');
const unsupportedFilePath = path.join(workspaceRoot, 'package-lock.json');

const APP_URL = process.env.APP_URL || 'http://localhost:3000/studio';

test('Audit 29: Upload Studio Functional Verification Suite', async (t) => {
  // Ensure video files exist
  assert.ok(fs.existsSync(video1Path), `Missing test video 1: ${video1Path}`);
  assert.ok(fs.existsSync(video2Path), `Missing test video 2: ${video2Path}`);
  assert.ok(fs.existsSync(video3Path), `Missing test video 3: ${video3Path}`);
  assert.ok(fs.existsSync(unsupportedFilePath), `Missing unsupported file: ${unsupportedFilePath}`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto(APP_URL, { waitUntil: 'networkidle' });

    // Step 0: Ensure starting from clean state
    await page.evaluate(async () => {
      const h = window.__clipforgeStudio;
      if (h) await h.clearStagedQueue();
    });
    await page.reload({ waitUntil: 'networkidle' });

    // -------------------------------------------------------------------------
    // TEST 1 — Real file selection & Error handling for unsupported files
    // -------------------------------------------------------------------------
    await t.test('Test 1: Real file selection and unsupported file rejection', async () => {
      // 1.1 Test unsupported file rejection
      const fileInput = page.locator('input[data-testid="studio-file-input"]');
      await fileInput.setInputFiles([unsupportedFilePath]);
      
      const errorBanner = page.locator('[data-testid="file-selection-error-banner"]');
      await errorBanner.waitFor({ state: 'visible', timeout: 5000 });
      const errorText = await errorBanner.innerText();
      assert.ok(
        errorText.includes('Unsupported file format') && errorText.includes('package-lock.json'),
        `Expected explicit unsupported file error, got: ${errorText}`
      );

      // Verify queue remains empty after rejected file
      const emptyMsg = page.locator('[data-testid="empty-queue-message"]');
      assert.ok(await emptyMsg.isVisible(), 'Queue should remain empty when invalid files are supplied');

      // Dismiss error
      await errorBanner.locator('button').click();

      // 1.2 Select three real video files
      await fileInput.setInputFiles([video1Path, video2Path, video3Path]);

      // Wait for all 3 items to render in queue
      await page.waitForSelector('[data-testid="staged-video-list"]', { timeout: 10000 });
      const items = page.locator('[data-testid^="staged-item-"]');
      assert.strictEqual(await items.count(), 3, 'Expected exactly 3 staged videos');

      // Verify metadata and zero-indexed positions via client harness
      const queueData = await page.evaluate(() => window.__clipforgeStudio.getQueue());
      assert.strictEqual(queueData.length, 3);
      assert.strictEqual(queueData[0].queue_position, 0, 'Item 0 must have queue_position 0');
      assert.strictEqual(queueData[1].queue_position, 1, 'Item 1 must have queue_position 1');
      assert.strictEqual(queueData[2].queue_position, 2, 'Item 2 must have queue_position 2');

      // Verify file metadata recorded
      assert.strictEqual(queueData[0].metadata.file_name, path.basename(video1Path));
      assert.strictEqual(queueData[1].metadata.file_name, path.basename(video2Path));
      assert.strictEqual(queueData[2].metadata.file_name, path.basename(video3Path));
      assert.ok(queueData[0].metadata.file_size > 0, 'File 1 size must be positive');
      assert.ok(queueData[1].metadata.file_size > 0, 'File 2 size must be positive');
      assert.ok(queueData[2].metadata.file_size > 0, 'File 3 size must be positive');

      // Verify media availability
      assert.strictEqual(queueData[0].media_availability, 'available');
      assert.strictEqual(queueData[1].media_availability, 'available');
      assert.strictEqual(queueData[2].media_availability, 'available');

      // Verify human-friendly display numbers (#1, #2, #3)
      const num1 = await page.locator(`[data-testid="item-display-number-${queueData[0].id}"]`).innerText();
      const num2 = await page.locator(`[data-testid="item-display-number-${queueData[1].id}"]`).innerText();
      const num3 = await page.locator(`[data-testid="item-display-number-${queueData[2].id}"]`).innerText();
      assert.strictEqual(num1.trim(), '#1');
      assert.strictEqual(num2.trim(), '#2');
      assert.strictEqual(num3.trim(), '#3');
    });

    // -------------------------------------------------------------------------
    // TEST 2 — Queue ordering and removal
    // -------------------------------------------------------------------------
    await t.test('Test 2: Reordering and middle-item removal with contiguous zero-indexed positions', async () => {
      let queueData = await page.evaluate(() => window.__clipforgeStudio.getQueue());
      const item0Id = queueData[0].id;
      const item1Id = queueData[1].id;
      const item2Id = queueData[2].id;

      // Move item 1 down (swapping item 1 and item 2) using keyboard accessible control
      const moveDownBtn = page.locator(`[data-testid="item-move-down-${item1Id}"]`);
      await moveDownBtn.click();

      // Check reordered state
      queueData = await page.evaluate(() => window.__clipforgeStudio.getQueue());
      assert.strictEqual(queueData[0].id, item0Id, 'Position 0 should remain item 0');
      assert.strictEqual(queueData[1].id, item2Id, 'Position 1 should now be item 2');
      assert.strictEqual(queueData[2].id, item1Id, 'Position 2 should now be item 1');
      assert.strictEqual(queueData[0].queue_position, 0);
      assert.strictEqual(queueData[1].queue_position, 1);
      assert.strictEqual(queueData[2].queue_position, 2);

      // Remove middle item (which is now item2Id)
      const removeBtn = page.locator(`[data-testid="item-remove-${item2Id}"]`);
      await removeBtn.click();

      // Wait for item to detach and queue to update to 2 items
      await page.locator(`[data-testid="staged-item-${item2Id}"]`).waitFor({ state: 'detached', timeout: 5000 });
      await page.waitForFunction(() => window.__clipforgeStudio.getQueue().length === 2, { timeout: 5000 });

      // Verify remaining count and contiguous positions
      queueData = await page.evaluate(() => window.__clipforgeStudio.getQueue());
      assert.strictEqual(queueData.length, 2, 'Queue should have 2 items remaining');
      assert.strictEqual(queueData[0].id, item0Id);
      assert.strictEqual(queueData[1].id, item1Id);
      assert.strictEqual(queueData[0].queue_position, 0, 'Internal index must be 0');
      assert.strictEqual(queueData[1].queue_position, 1, 'Internal index must be 1');

      // Check display numbers updated to #1 and #2
      const disp1 = await page.locator(`[data-testid="item-display-number-${item0Id}"]`).innerText();
      const disp2 = await page.locator(`[data-testid="item-display-number-${item1Id}"]`).innerText();
      assert.strictEqual(disp1.trim(), '#1');
      assert.strictEqual(disp2.trim(), '#2');
    });

    // -------------------------------------------------------------------------
    // TEST 3 — Refresh and restoration
    // -------------------------------------------------------------------------
    await t.test('Test 3: Browser refresh restores metadata, ordering, and verifies Blob persistence', async () => {
      const beforeRefresh = await page.evaluate(() => window.__clipforgeStudio.getQueue());
      
      // Perform full browser refresh
      await page.reload({ waitUntil: 'networkidle' });

      const afterRefresh = await page.evaluate(() => window.__clipforgeStudio.getQueue());
      assert.strictEqual(afterRefresh.length, beforeRefresh.length, 'Queue length must be preserved across refresh');
      assert.strictEqual(afterRefresh[0].id, beforeRefresh[0].id);
      assert.strictEqual(afterRefresh[1].id, beforeRefresh[1].id);
      assert.strictEqual(afterRefresh[0].queue_position, 0);
      assert.strictEqual(afterRefresh[1].queue_position, 1);
      assert.strictEqual(afterRefresh[0].metadata.file_name, beforeRefresh[0].metadata.file_name);
      assert.strictEqual(afterRefresh[1].metadata.file_name, beforeRefresh[1].metadata.file_name);

      // Verify Blob data was restored and media availability is explicitly verified
      assert.strictEqual(afterRefresh[0].media_availability, 'available');
      assert.strictEqual(afterRefresh[1].media_availability, 'available');
    });

    // -------------------------------------------------------------------------
    // TEST 4 — Reselection recovery with identity policy enforcement
    // -------------------------------------------------------------------------
    await t.test('Test 4: Reselection recovery with strict identity policy validation', async () => {
      // Intentionally evict media from item 0 to simulate missing media
      const queueData = await page.evaluate(() => window.__clipforgeStudio.getQueue());
      const targetId = queueData[0].id;
      const expectedFileName = queueData[0].metadata.file_name;

      await page.evaluate(async (id) => {
        const q = await window.__clipforgeStudio.loadStagedQueue();
        const target = q.find((i) => i.id === id);
        if (target) {
          target.file_blob = null;
          target.media_availability = 'missing_reselection_required';
          target.storage_warning = 'Original file unavailable. Reselection required.';
          await window.__clipforgeStudio.saveStagedQueue(q);
        }
      }, targetId);

      // Reload page to observe missing state
      await page.reload({ waitUntil: 'networkidle' });

      // Check badge shows missing state
      const badge = page.locator(`[data-testid="item-availability-badge-${targetId}"]`);
      assert.ok(
        (await badge.innerText()).includes('File Unavailable'),
        'Item must display unavailable badge'
      );

      // Check process batch button is disabled
      const processBtn = page.locator('[data-testid="process-batch-button"]');
      assert.ok(await processBtn.isDisabled(), 'Process batch button must be disabled when media is missing');

      // 4.1 Test identity policy violation: user selects the wrong video file
      const wrongVideoPath = video3Path; // Different filename from expectedFileName
      const reselectInput = page.locator('input[data-testid="reselect-file-input"]');
      
      // Trigger reselect button to set target
      await page.locator(`[data-testid="reselect-button-${targetId}"]`).click();
      await reselectInput.setInputFiles([wrongVideoPath]);

      // Check explicit reselect error banner appeared
      const reselectErrorBanner = page.locator('[data-testid="reselect-error-banner"]');
      await reselectErrorBanner.waitFor({ state: 'visible', timeout: 5000 });
      const errText = await reselectErrorBanner.innerText();
      assert.ok(
        errText.includes('Identity policy violation'),
        `Expected identity policy error, got: ${errText}`
      );

      // Confirm item is STILL unavailable
      let currentQueue = await page.evaluate(() => window.__clipforgeStudio.getQueue());
      assert.strictEqual(
        currentQueue[0].media_availability,
        'missing_reselection_required',
        'Item must NOT become available when identity policy fails'
      );

      // 4.2 Test correct file reselection: user selects the exact matching file
      const correctVideoPath = path.join(workspaceRoot, expectedFileName);
      await page.locator(`[data-testid="reselect-button-${targetId}"]`).click();
      await reselectInput.setInputFiles([correctVideoPath]);

      // Wait for item to recover to available state
      await page.waitForFunction((id) => {
        const q = window.__clipforgeStudio.getQueue();
        const item = q.find((i) => i.id === id);
        return item && item.media_availability === 'available';
      }, targetId, { timeout: 5000 });

      currentQueue = await page.evaluate(() => window.__clipforgeStudio.getQueue());
      assert.strictEqual(currentQueue[0].id, targetId, 'Item ID must be preserved');
      assert.strictEqual(currentQueue[0].queue_position, 0, 'Queue position must be preserved');
      assert.strictEqual(currentQueue[0].media_availability, 'available', 'Item must now be available');
    });

    // -------------------------------------------------------------------------
    // TEST 5 — IndexedDB quota eviction and fatal write failure handling
    // -------------------------------------------------------------------------
    await t.test('Test 5: Storage quota eviction and memory-only state distinction', async () => {
      // 5.1 Simulate Quota Exceeded during save (Blobs evicted, metadata preserved)
      await page.evaluate(async () => {
        window.__clipforgeStudio.setStorageSimulationMode('quota_blob_evict');
        const q = window.__clipforgeStudio.getQueue();
        await window.__clipforgeStudio.saveStagedQueue(q);
        window.__clipforgeStudio.setStorageSimulationMode('none');
      });

      // Reload to verify persisted state after quota eviction
      await page.reload({ waitUntil: 'networkidle' });
      let queueData = await page.evaluate(() => window.__clipforgeStudio.getQueue());

      assert.strictEqual(queueData[0].media_availability, 'quota_exceeded_evicted');
      assert.ok(queueData[0].storage_warning.includes('Browser storage quota exceeded'));
      assert.strictEqual(queueData[0].file_blob, null);
      
      // Batch button must remain disabled because files are evicted
      const processBtn = page.locator('[data-testid="process-batch-button"]');
      assert.ok(await processBtn.isDisabled(), 'Batch button must be disabled when files are evicted');

      // 5.2 Simulate Fatal Metadata Write Failure (Distinguish memory-only state)
      await page.evaluate(() => {
        window.__clipforgeStudio.setStorageSimulationMode('fatal_write_fail');
      });

      // Trigger a queue reorder which attempts to persist
      const moveDownBtn = page.locator(`[data-testid="item-move-down-${queueData[0].id}"]`);
      await moveDownBtn.click();

      // Verify that memory-only banner is displayed
      const memoryOnlyBanner = page.locator('[data-testid="memory-only-banner"]');
      await memoryOnlyBanner.waitFor({ state: 'visible', timeout: 5000 });
      const bannerText = await memoryOnlyBanner.innerText();
      assert.ok(
        bannerText.includes('Memory-Only State') && bannerText.includes('failed'),
        `Expected memory-only failure banner, got: ${bannerText}`
      );

      const statusBadge = page.locator('[data-testid="storage-unpersisted-badge"]');
      assert.ok(await statusBadge.isVisible(), 'Unpersisted status badge should be visible');

      // Reset simulation mode
      await page.evaluate(() => {
        window.__clipforgeStudio.setStorageSimulationMode('none');
      });
    });

    // -------------------------------------------------------------------------
    // TEST 6 — Honest processing state (Zero fabricated jobs/uploads)
    // -------------------------------------------------------------------------
    await t.test('Test 6: Honest processing state and backend non-deployment reporting', async () => {
      // Verify prominent banner
      const banner = page.locator('[data-testid="honest-deployment-banner"]');
      assert.ok(await banner.isVisible());
      const bannerText = await banner.innerText();
      assert.ok(
        bannerText.includes('Upload Studio batch backend is not deployed yet') ||
        bannerText.includes('Upload Studio Phase 1B backend connected'),
        'Page must state batch backend status honestly'
      );

      // Re-attach videos to make batch button active to test modal honest reporting
      await page.evaluate(async () => {
        await window.__clipforgeStudio.clearStagedQueue();
      });
      await page.reload({ waitUntil: 'networkidle' });

      // Add one real video
      const fileInput = page.locator('input[data-testid="studio-file-input"]');
      await fileInput.setInputFiles([video1Path]);
      await page.waitForSelector('[data-testid="queue-ready-badge"]', { timeout: 5000 });

      // Click Process Batch button
      const processBtn = page.locator('[data-testid="process-batch-button"]');
      assert.ok(await processBtn.isEnabled(), 'Process button should be enabled when video is ready');
      await processBtn.click();

      // Check modal
      const modal = page.locator('[data-testid="honest-process-modal"]');
      await modal.waitFor({ state: 'visible', timeout: 5000 });
      const modalText = await modal.innerText();
      assert.ok(
        modalText.includes('Backend Implementation Required') &&
        modalText.includes('/api/studio/batches') &&
        modalText.includes('Zero fake progress bars'),
        `Modal must honestly describe backend state: ${modalText}`
      );

      // Close modal
      await page.locator('[data-testid="close-process-modal-button"]').click();
      await modal.waitFor({ state: 'hidden', timeout: 3000 });
    });

  } finally {
    await browser.close();
  }
});
