import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const workspaceRoot = path.resolve(__dirname, '../../');

const APP_URL = process.env.APP_URL || 'http://localhost:3000/studio';
const API_BASE = process.env.API_BASE || 'http://localhost:8000';

test('ClipForge Upload Studio: Real Browser-Driven Upload E2E Gate', async (t) => {
  if (process.env.RUN_LIVE_E2E !== 'true') {
    t.skip('Skipped: RUN_LIVE_E2E=true environment flag is required to run live browser E2E tests against operational environment');
    return;
  }

  const tempDir = 'C:\\Users\\Chinmaygouda\\AppData\\Local\\Temp';
  const file1Path = path.join(tempDir, 'test_clip_alpha.mp4');
  const file2Path = path.join(tempDir, 'test_clip_beta.mp4');

  assert.ok(fs.existsSync(file1Path), `Missing ${file1Path}`);
  assert.ok(fs.existsSync(file2Path), `Missing ${file2Path}`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Network and console diagnostics loggers
  const consoleMessages = [];
  const networkEvents = [];
  const apiRequests = [];

  page.on('console', (msg) => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  page.on('request', (req) => {
    const url = req.url();
    if (url.includes('/api/studio')) {
      apiRequests.push({
        method: req.method(),
        url: url,
        headers: req.headers(),
      });
    }
  });

  page.on('response', (res) => {
    const url = res.url();
    if (url.includes('/api/studio')) {
      networkEvents.push({
        url: url,
        status: res.status(),
        ok: res.ok(),
      });
    }
  });

  page.on('dialog', (dialog) => dialog.accept());

  try {
    // -------------------------------------------------------------------------
    // 1. Open /studio and capture diagnostics
    // -------------------------------------------------------------------------
    await t.test('1. Open /studio and verify page load and backend connectivity', async () => {
      await page.goto(APP_URL);
      await page.waitForSelector('h1', { timeout: 10000 });

      // Clean starting state
      await page.evaluate(async () => {
        if (window.__clipforgeStudio) {
          await window.__clipforgeStudio.clearStagedQueue();
        }
      });
      await page.reload();
      await page.waitForSelector('h1', { timeout: 10000 });

      const heading = page.locator('h1');
      assert.equal(await heading.innerText(), 'Upload Studio');

      // Verify the honest deployment banner displays connected status
      await page.waitForFunction(
        () => {
          const el = document.querySelector('[data-testid="honest-deployment-banner"]');
          return el && el.textContent && el.textContent.includes('Upload Studio Phase 1B backend connected');
        },
        null,
        { timeout: 10000 }
      );
    });

    // -------------------------------------------------------------------------
    // 2. Stage two valid test videos in browser
    // -------------------------------------------------------------------------
    await t.test('2. Stage two valid test videos and verify queue rendering', async () => {
      const fileInput = page.locator('input[data-testid="studio-file-input"]');
      await fileInput.setInputFiles([file1Path, file2Path]);

      // Wait for queue items to render
      await page.waitForSelector('[data-testid="queue-ready-badge"]', { timeout: 5000 });

      const queueItems = page.locator('[data-testid^="staged-item-"]');
      const count = await queueItems.count();
      assert.equal(count, 2, `Expected 2 queue items, got ${count}`);

      // Verify filenames and formats rendered
      const itemTexts = await queueItems.allInnerTexts();
      assert.ok(itemTexts.some((t) => t.includes('test_clip_alpha.mp4')));
      assert.ok(itemTexts.some((t) => t.includes('test_clip_beta.mp4')));
    });

    // -------------------------------------------------------------------------
    // 3. Verify IndexedDB queue preservation
    // -------------------------------------------------------------------------
    await t.test('3. Verify IndexedDB queue items and order preservation', async () => {
      const idbQueue = await page.evaluate(async () => {
        return await window.__clipforgeStudio.getQueue();
      });
      assert.equal(idbQueue.length, 2);
      assert.equal(idbQueue[0].metadata.file_name, 'test_clip_alpha.mp4');
      assert.equal(idbQueue[1].metadata.file_name, 'test_clip_beta.mp4');
      assert.equal(idbQueue[0].media_availability, 'available');
      assert.equal(idbQueue[1].media_availability, 'available');
    });

    // -------------------------------------------------------------------------
    // 4. Click the real Upload Batch button
    // -------------------------------------------------------------------------
    let createdBatchId = null;
    await t.test('4. Click Upload Batch and confirm real browser chunk streaming', async () => {
      const uploadBtn = page.locator('[data-testid="upload-batch-button"]');
      assert.ok(await uploadBtn.isEnabled(), 'Upload Batch button must be enabled');

      // Click upload
      await uploadBtn.click();

      // Wait for batch ID to be assigned and uploads to complete
      await page.waitForFunction(
        () => {
          const q = window.__clipforgeStudio?.getQueue();
          return q && q.length === 2 && q.every((item) => item.upload_status === 'uploaded');
        },
        null,
        { timeout: 15000 }
      );

      createdBatchId = await page.evaluate(() => window.__clipforgeStudio.getCurrentBatchId());
      assert.ok(createdBatchId, 'Batch ID must be established on client');
      assert.ok(createdBatchId.startsWith('b_'), `Batch ID must start with b_, got ${createdBatchId}`);
    });

    // -------------------------------------------------------------------------
    // 5. Confirm browser requests to FastAPI backend for BOTH videos
    // -------------------------------------------------------------------------
    await t.test('5. Verify browser network requests to FastAPI backend', async () => {
      // Must have called POST /api/studio/batches
      const batchCreateReq = apiRequests.find((r) => r.method === 'POST' && r.url.endsWith('/batches'));
      assert.ok(batchCreateReq, 'Must have initiated POST /api/studio/batches');

      // Must have called POST /api/studio/batches/{id}/videos/init for BOTH items
      const initReqs = apiRequests.filter((r) => r.method === 'POST' && r.url.includes('/videos/init'));
      assert.equal(initReqs.length, 2, `Must have initialized both video items, got ${initReqs.length}`);

      // Must have called PUT /api/studio/uploads/{id}/chunk with Content-Range for BOTH items
      const chunkReqs = apiRequests.filter((r) => r.method === 'PUT' && r.url.includes('/chunk'));
      assert.ok(chunkReqs.length >= 2, `Expected at least 2 chunk requests, got ${chunkReqs.length}`);

      // Group chunk requests by video ID
      const chunkUrls = chunkReqs.map((r) => r.url);
      const uniqueChunkVideos = [...new Set(chunkUrls.map((u) => u.split('/uploads/')[1].split('/')[0]))];
      assert.equal(uniqueChunkVideos.length, 2, `Must have distinct chunk uploads for both videos, got: ${uniqueChunkVideos.join(', ')}`);

      console.log('--- NETWORK FORENSIC TRACE: BROWSER REQUESTS ---');
      for (const req of chunkReqs) {
        console.log(`[REQ] ${req.method} ${req.url} -> Content-Range: ${req.headers['content-range']}`);
      }

      for (const cr of chunkReqs) {
        assert.ok(cr.headers['content-range'], 'Chunk requests must carry Content-Range');
      }

      // Check all network responses were 200 or 201
      const studioResponses = networkEvents.filter((e) => e.url.includes('/api/studio/'));
      assert.ok(studioResponses.length >= 4, 'Must have received responses from backend');
      for (const res of studioResponses) {
        assert.ok(res.ok, `Expected 2xx status, got ${res.status} on ${res.url}`);
      }
    });

    // -------------------------------------------------------------------------
    // 6. Verify committed state, FFprobe media validation, and artifacts for BOTH videos
    // -------------------------------------------------------------------------
    await t.test('6. Verify committed server state and FFprobe media validation', async () => {
      const batchRes = await fetch(`${API_BASE}/api/studio/batches/${createdBatchId}`);
      assert.equal(batchRes.status, 200);
      const batchData = await batchRes.json();

      assert.equal(batchData.total_files, 2);
      assert.equal(batchData.videos.length, 2);

      console.log('\n--- PER-VIDEO FORENSIC VERIFICATION ---');
      const batchDiskDir = path.join(workspaceRoot, 'uploads', 'studio', 'batches', createdBatchId);
      assert.ok(fs.existsSync(batchDiskDir), `Physical batch directory must exist: ${batchDiskDir}`);

      let totalExpectedHeadroom = 0;

      for (const v of batchData.videos) {
        console.log(`\n[VIDEO RECORD] ID: ${v.id}`);
        console.log(`  Source Filename:   ${v.source_filename}`);
        console.log(`  Registered Size:   ${v.file_size} bytes`);
        console.log(`  Uploaded Bytes:    ${v.uploaded_bytes} bytes`);
        console.log(`  Upload Status:     ${v.upload_status}`);
        console.log(`  Reservation State: ${v.reservation_state}`);
        console.log(`  Reserved Bytes:    ${v.reserved_bytes} bytes`);
        console.log(`  Local Path:        ${v.local_path}`);

        // Assertions for each video
        assert.equal(v.upload_status, 'uploaded', `Video ${v.id} status must be uploaded`);
        assert.equal(v.uploaded_bytes, v.file_size, `Video ${v.id} committed offset must equal registered size`);
        assert.equal(v.reservation_state, 'headroom_only', `Video ${v.id} must be in headroom_only state`);
        assert.equal(v.reserved_bytes, Math.floor(v.file_size * 0.5), `Video ${v.id} headroom reservation must equal 50%`);
        assert.ok(v.local_path, `Video ${v.id} must have persisted local_path`);

        totalExpectedHeadroom += v.reserved_bytes;

        // Check physical host artifact
        const physicalFile = path.join(workspaceRoot, v.local_path.replace(/^\/app\//, ''));
        assert.ok(fs.existsSync(physicalFile), `Physical file must exist: ${physicalFile}`);
        assert.equal(fs.statSync(physicalFile).size, v.file_size, `Physical file size must match registered size`);

        // Execute FFprobe directly inside backend container
        const ffprobeCmd = `docker exec clipforge_backend ffprobe -v error -show_entries format=duration,format_name -show_streams -of json "${v.local_path}"`;
        const ffprobeOutput = execSync(ffprobeCmd, { encoding: 'utf-8' });
        const probeData = JSON.parse(ffprobeOutput);

        const duration = parseFloat(probeData.format?.duration || '0');
        const formatName = probeData.format?.format_name;
        const videoStream = probeData.streams?.find((s) => s.codec_type === 'video');

        console.log(`  FFprobe Format:    ${formatName} (duration=${duration}s)`);
        console.log(`  FFprobe Video:     codec=${videoStream?.codec_name}, ${videoStream?.width}x${videoStream?.height}`);

        assert.ok(duration > 0, `FFprobe duration must be positive, got ${duration}`);
        assert.ok(videoStream, `FFprobe must detect valid video stream`);
      }

      // Reconcile database coordinator reservation
      const coordCmd = `docker exec clipforge_postgres psql -U clipforge_user -d clipforge -t -c "SELECT reserved_bytes FROM storage_reservation_coordinators WHERE id = 'global';"`;
      const dbCoordBytes = parseInt(execSync(coordCmd, { encoding: 'utf-8' }).trim(), 10);

      console.log(`\n[RESERVATION RECONCILIATION]`);
      console.log(`  SUM(video.reserved_bytes): ${totalExpectedHeadroom}`);
      console.log(`  Coordinator reserved_bytes in DB: ${dbCoordBytes}`);
      assert.equal(dbCoordBytes, totalExpectedHeadroom, `Coordinator reservation must match exact sum of video headroom`);
    });

    // -------------------------------------------------------------------------
    // 7. Refresh browser and verify state persistence
    // -------------------------------------------------------------------------
    await t.test('7. Browser refresh preserves batch state and staged data', async () => {
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForSelector('[data-testid^="staged-item-"]', { timeout: 10000 });

      const queueAfter = await page.evaluate(async () => {
        return await window.__clipforgeStudio.getQueue();
      });
      assert.equal(queueAfter.length, 2);
      assert.equal(queueAfter[0].upload_status, 'uploaded');
      assert.equal(queueAfter[1].upload_status, 'uploaded');
      assert.ok(queueAfter[0].server_video_id, 'Must preserve server video ID 1');
      assert.ok(queueAfter[1].server_video_id, 'Must preserve server video ID 2');
    });

    // -------------------------------------------------------------------------
    // 8. Delete the disposable batch through the UI
    // -------------------------------------------------------------------------
    await t.test('8. Delete batch through the UI and verify server deletion', async () => {
      const deleteBtn = page.locator('[data-testid="delete-batch-button"]');
      await deleteBtn.waitFor({ state: 'visible', timeout: 5000 });
      await deleteBtn.click();

      // Wait for queue to become empty
      await page.waitForFunction(() => {
        const q = window.__clipforgeStudio?.getQueue();
        return !q || q.length === 0;
      }, null, { timeout: 10000 });

      // Verify batch no longer exists on server (404)
      const checkRes = await fetch(`${API_BASE}/api/studio/batches/${createdBatchId}`);
      assert.equal(checkRes.status, 404, 'Deleted batch must return 404');
    });

    // -------------------------------------------------------------------------
    // 9. Verify database state, physical files and reservation invariants
    // -------------------------------------------------------------------------
    await t.test('9. Verify physical cleanup, DB deletion, and reservation invariant', async () => {
      const batchDiskDir = path.join(workspaceRoot, 'uploads', 'studio', 'batches', createdBatchId);
      assert.ok(!fs.existsSync(batchDiskDir), `Batch directory must be unlinked: ${batchDiskDir}`);

      // Query database directly
      const psqlCmd = `docker exec clipforge_postgres psql -U clipforge_user -d clipforge -t -c "SELECT count(*) FROM upload_batches WHERE id = '${createdBatchId}'; SELECT count(*) FROM videos WHERE upload_batch_id = '${createdBatchId}'; SELECT reserved_bytes FROM storage_reservation_coordinators WHERE id = 'global';"`;
      const psqlOut = execSync(psqlCmd, { encoding: 'utf-8' }).trim().split(/\s+/);
      const batchCount = parseInt(psqlOut[0], 10);
      const videoCount = parseInt(psqlOut[1], 10);
      const coordReserved = parseInt(psqlOut[2], 10);

      console.log(`\n[POST-DELETION DATABASE STATE]`);
      console.log(`  Batches matching ${createdBatchId}: ${batchCount}`);
      console.log(`  Videos matching batch:             ${videoCount}`);
      console.log(`  Coordinator reserved_bytes:         ${coordReserved}`);

      assert.equal(batchCount, 0, 'Batch record must be completely deleted');
      assert.equal(videoCount, 0, 'Video records for batch must be completely deleted');
      assert.equal(coordReserved, 0, 'Coordinator reserved_bytes must return to exactly 0');
    });

    // -------------------------------------------------------------------------
    // 10. Confirm no sequential-processing or publishing task was dispatched
    // -------------------------------------------------------------------------
    await t.test('10. Confirm no sequential processing or publishing task was dispatched', async () => {
      // Verify via jobs API that no background jobs were spawned
      const jobsRes = await fetch(`${API_BASE}/api/jobs`);
      assert.equal(jobsRes.status, 200);
      const jobs = await jobsRes.json();
      const studioJobs = jobs.filter((j) => j.video_id && j.video_id.startsWith('v_'));
      assert.equal(studioJobs.length, 0, 'Zero jobs must have been queued for studio batch');

      // Check redis celery queue length
      const redisCmd = `docker exec clipforge_redis redis-cli llen celery`;
      const celeryQueueLen = parseInt(execSync(redisCmd, { encoding: 'utf-8' }).trim(), 10);
      console.log(`  Celery Queue Length: ${celeryQueueLen}`);
      assert.equal(celeryQueueLen, 0, 'Celery queue length must be 0');
    });

  } finally {
    await browser.close();
  }
});
