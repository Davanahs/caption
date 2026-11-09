import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const workspaceRoot = path.resolve(__dirname, '../../');

const API_BASE = process.env.API_BASE || 'http://localhost:8000';

test('ClipForge Phase 1B: Live Backend API Driver End-to-End Verification', async (t) => {
  if (process.env.RUN_LIVE_E2E !== 'true') {
    t.skip('Skipped: RUN_LIVE_E2E=true environment flag is required to run live backend E2E tests against operational environment');
    return;
  }

  const tempDir = 'C:\\Users\\Chinmaygouda\\AppData\\Local\\Temp';
  const file1Path = path.join(tempDir, 'test_clip_alpha.mp4');
  const file2Path = path.join(tempDir, 'test_clip_beta.mp4');

  assert.ok(fs.existsSync(file1Path), 'Missing test_clip_alpha.mp4');
  assert.ok(fs.existsSync(file2Path), 'Missing test_clip_beta.mp4');

  const file1Stat = fs.statSync(file1Path);
  const file2Stat = fs.statSync(file2Path);

  let batchId = null;
  let video1Id = null;
  let video2Id = null;

  // 1. Create Batch
  await t.test('1. Create Upload Batch with idempotency key', async () => {
    const key = `e2e_batch_${Date.now()}`;
    const res = await fetch(`${API_BASE}/api/studio/batches`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idempotency_key: key, name: 'Live E2E Verification Batch' }),
    });
    assert.equal(res.status, 201, `Expected 201 Created, got ${res.status}`);
    const data = await res.json();
    assert.ok(data.id, 'Batch must have an id');
    assert.equal(data.status, 'staging');
    assert.equal(data.version, 1);
    assert.equal(data.total_files, 0);
    assert.equal(data.reserved_bytes, 0);
    batchId = data.id;
  });

  // 2. Initialize Video Items (1.5x Reservation)
  await t.test('2. Initialize Video 1 and Video 2 with 1.5x Storage Reservation', async () => {
    // Video 1
    const res1 = await fetch(`${API_BASE}/api/studio/batches/${batchId}/videos/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_item_id: 'client_item_alpha',
        source_filename: 'test_clip_alpha.mp4',
        file_size: file1Stat.size,
      }),
    });
    assert.equal(res1.status, 201);
    const data1 = await res1.json();
    video1Id = data1.id;
    assert.equal(data1.reserved_bytes, Math.floor(file1Stat.size * 1.5));
    assert.equal(data1.reservation_state, 'initial');
    assert.equal(data1.upload_status, 'queued');
    assert.equal(data1.queue_position, 0);

    // Video 2
    const res2 = await fetch(`${API_BASE}/api/studio/batches/${batchId}/videos/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_item_id: 'client_item_beta',
        source_filename: 'test_clip_beta.mp4',
        file_size: file2Stat.size,
      }),
    });
    assert.equal(res2.status, 201);
    const data2 = await res2.json();
    video2Id = data2.id;
    assert.equal(data2.reserved_bytes, Math.floor(file2Stat.size * 1.5));
    assert.equal(data2.queue_position, 1);
  });

  // 3. Upload Chunks via PUT /api/studio/uploads/{id}/chunk
  await t.test('3. Upload Video 1 in Chunks with Content-Range RFC 7233 and FFprobe validation', async () => {
    const fileBuffer = fs.readFileSync(file1Path);
    const totalBytes = fileBuffer.length;
    const chunkSize = 2048; // small chunks to test multiple chunks
    let offset = 0;

    while (offset < totalBytes) {
      const end = Math.min(offset + chunkSize, totalBytes);
      const chunk = fileBuffer.subarray(offset, end);

      const res = await fetch(`${API_BASE}/api/studio/uploads/${video1Id}/chunk`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/octet-stream',
          'Content-Range': `bytes ${offset}-${end - 1}/${totalBytes}`,
        },
        body: chunk,
      });

      assert.equal(res.status, 200, `Expected 200 on chunk upload, got ${res.status}`);
      const chunkData = await res.json();
      assert.equal(chunkData.uploaded_bytes, end);
      offset = end;
    }

    // Verify video status after completion
    const statusRes = await fetch(`${API_BASE}/api/studio/uploads/${video1Id}`);
    assert.equal(statusRes.status, 200);
    const statusData = await statusRes.json();
    assert.equal(statusData.uploaded_bytes, totalBytes);
    assert.equal(statusData.upload_status, 'uploaded');
  });

  // 4. Reorder Queue with Optimistic Locking
  await t.test('4. Reorder Queue with Optimistic Version Locking', async () => {
    const batchBefore = await fetch(`${API_BASE}/api/studio/batches/${batchId}`).then(r => r.json());
    const version = batchBefore.version;

    // Swap positions: [video2Id, video1Id]
    const reorderRes = await fetch(`${API_BASE}/api/studio/batches/${batchId}/reorder`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        version: version,
        item_ids: [video2Id, video1Id],
      }),
    });
    assert.equal(reorderRes.status, 200);
    const reorderData = await reorderRes.json();
    assert.equal(reorderData.version, version + 1);

    // Verify batch query returns reordered videos
    const batchAfter = await fetch(`${API_BASE}/api/studio/batches/${batchId}`).then(r => r.json());
    assert.equal(batchAfter.videos[0].id, video2Id);
    assert.equal(batchAfter.videos[0].queue_position, 0);
    assert.equal(batchAfter.videos[1].id, video1Id);
    assert.equal(batchAfter.videos[1].queue_position, 1);
  });

  // 5. Delete Batch and Verify Complete Physical and DB Cleanup
  await t.test('5. Delete Batch with Physical Cleanup and Reservation Release', async () => {
    const delRes = await fetch(`${API_BASE}/api/studio/batches/${batchId}`, {
      method: 'DELETE',
    });
    assert.equal(delRes.status, 200);
    const delData = await delRes.json();
    assert.equal(delData.deleted, true);
    assert.equal(delData.batch_id, batchId);
    assert.equal(delData.directory_cleaned, true);

    // Verify batch no longer exists (404)
    const checkRes = await fetch(`${API_BASE}/api/studio/batches/${batchId}`);
    assert.equal(checkRes.status, 404);
  });
});
