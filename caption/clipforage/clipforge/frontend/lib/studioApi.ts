/**
 * ClipForge Upload Studio — Client API Driver
 *
 * Implements resumable chunk streaming, single-writer fencing negotiation,
 * concurrency limiting (<= 3 concurrent streams), range chunking (<= 10 MiB),
 * and transparent recovery of interrupted uploads.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export const CHUNK_SIZE_BYTES = 5 * 1024 * 1024; // 5 MiB chunks (<= 10 MiB limit)
export const MAX_CONCURRENT_UPLOADS = 3;

export interface StudioBatchResponse {
  id: string;
  idempotency_key: string;
  name: string | null;
  status: string;
  version: number;
  total_files: number;
  reserved_bytes: number;
  created_at?: string;
  updated_at?: string;
  active_video_id?: string | null;
  active_task_id?: string | null;
  worker_heartbeat?: string | null;
  processing_started_at?: string | null;
  processing_completed_at?: string | null;
  batch_error?: string | null;
  videos: StudioVideoResponse[];
}

export interface StudioVideoResponse {
  id: string;
  client_item_id: string | null;
  title: string;
  source_filename: string | null;
  file_size: number;
  total_bytes: number;
  uploaded_bytes: number;
  upload_status: string | null;
  queue_position: number | null;
  reservation_state: string;
  reserved_bytes: number;
  resolution?: string | null;
  duration?: number | null;
  local_path?: string | null;
  processing_status?: string | null;
  processing_progress?: number;
  processing_step?: string | null;
  processing_error?: string | null;
  processing_job_id?: string | null;
  processing_attempt?: number;
  processing_started_at?: string | null;
  processing_completed_at?: string | null;
}

export interface UploadStatusResponse {
  upload_id: string;
  batch_id: string | null;
  upload_status: string | null;
  uploaded_bytes: number;
  total_bytes: number;
  queue_position: number | null;
}

/**
 * Creates or retrieves an existing batch idempotently.
 */
export async function createStudioBatch(idempotencyKey: string, name?: string): Promise<StudioBatchResponse> {
  const res = await fetch(`${API_BASE}/api/studio/batches`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idempotency_key: idempotencyKey, name: name || undefined }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to create batch' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Fetches current batch status and video queue.
 */
export async function getStudioBatch(batchId: string): Promise<StudioBatchResponse> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to fetch batch' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Idempotently registers a video in a batch and reserves 1.5x storage.
 */
export async function initStudioVideo(
  batchId: string,
  item: {
    client_item_id: string;
    source_filename: string;
    file_size: number;
    resolution?: string | null;
    duration?: number | null;
  }
): Promise<StudioVideoResponse> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}/videos/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(item),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to init video' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Queries committed offset and status for an upload.
 */
export async function getUploadStatus(uploadId: string): Promise<UploadStatusResponse> {
  const res = await fetch(`${API_BASE}/api/studio/uploads/${uploadId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to get upload status' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Uploads a single byte chunk with Content-Range.
 */
export async function uploadChunk(
  uploadId: string,
  chunkBlob: Blob,
  start: number,
  end: number,
  total: number
): Promise<{ upload_id: string; uploaded_bytes: number; total_bytes: number; status: string }> {
  const res = await fetch(`${API_BASE}/api/studio/uploads/${uploadId}/chunk`, {
    method: 'PUT',
    headers: {
      'Content-Range': `bytes ${start}-${end}/${total}`,
      'Content-Type': 'application/octet-stream',
    },
    body: chunkBlob,
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    const error: Error & { status?: number; data?: unknown } = new Error(
      typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail || errData)
    );
    error.status = res.status;
    error.data = errData;
    throw error;
  }
  return res.json();
}

/**
 * Reorders batch items (0..N-1) using optimistic version check.
 */
export async function reorderStudioBatch(
  batchId: string,
  version: number,
  itemIds: string[]
): Promise<{ batch_id: string; version: number; reordered_count: number }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}/reorder`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version, item_ids: itemIds }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to reorder batch' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Retries a failed or interrupted upload.
 */
export async function retryStudioUpload(
  uploadId: string
): Promise<{ upload_id: string; uploaded_bytes: number; total_bytes: number; status: string }> {
  const res = await fetch(`${API_BASE}/api/studio/uploads/${uploadId}/retry`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to retry upload' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Cancels a video item and cleans its artifacts.
 */
export async function cancelStudioVideo(
  batchId: string,
  videoId: string
): Promise<{ cancelled: boolean; video_id: string }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}/videos/${videoId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to cancel video' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Deletes a batch and cleans its artifacts behind a barrier.
 */
export async function deleteStudioBatch(
  batchId: string
): Promise<{ deleted: boolean; batch_id: string }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to delete batch' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Idempotently starts sequential processing of all uploaded videos in a batch.
 */
export async function processStudioBatch(batchId: string): Promise<StudioBatchResponse> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}/process`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to start batch processing' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Requests cooperative cancellation of batch processing.
 */
export async function cancelStudioBatch(
  batchId: string
): Promise<{ cancelled?: boolean; cancellation_requested?: boolean; batch_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}/cancel`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to cancel batch' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Retries a failed video in the batch preserving original queue position.
 */
export async function retryStudioVideo(
  batchId: string,
  videoId: string
): Promise<{ retried: boolean; video_id: string; queue_position: number; status: string }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}/videos/${videoId}/retry`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to retry video' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Retries batch processing from the first failed item.
 */
export async function retryStudioBatch(
  batchId: string
): Promise<{ retried: boolean; batch_id: string; resumed_from_video_id?: string }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}/retry`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to retry batch' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Safely recovers a batch with a stale processing worker.
 */
export async function recoverStudioBatch(
  batchId: string
): Promise<{ recovered: boolean; batch_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}/recover`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to recover batch' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}


/**
 * Streams an entire file blob in chunks to the backend with single-writer fencing
 * and automatic offset recovery.
 */
export async function streamFileInChunks(
  uploadId: string,
  file: Blob | File,
  onProgress?: (uploadedBytes: number, totalBytes: number) => void
): Promise<void> {
  const total = file.size;

  // 1. Query initial server state to resume from exact committed offset
  const status = await getUploadStatus(uploadId);
  if (status.upload_status === 'uploaded') {
    onProgress?.(total, total);
    return;
  }

  let offset = status.uploaded_bytes;
  onProgress?.(offset, total);

  while (offset < total) {
    const chunkSize = Math.min(CHUNK_SIZE_BYTES, total - offset);
    const start = offset;
    const end = start + chunkSize - 1;
    const chunkBlob = file.slice(start, end + 1);

    let retries = 0;
    let committed = false;

    while (!committed && retries < 5) {
      try {
        const res = await uploadChunk(uploadId, chunkBlob, start, end, total);
        offset = res.uploaded_bytes;
        onProgress?.(offset, total);
        committed = true;
      } catch (err: unknown) {
        const error = err as { status?: number; data?: { detail?: { expected_offset?: number } } };
        // 429 Too Many Requests -> Backoff and retry
        if (error.status === 429) {
          retries++;
          await new Promise((resolve) => setTimeout(resolve, 1000 * retries));
          continue;
        }

        // 409 Conflict -> Offset mismatch or lease issue
        if (error.status === 409) {
          const expected = error.data?.detail?.expected_offset;
          if (typeof expected === 'number') {
            offset = expected;
            onProgress?.(offset, total);
            break; // Break inner retry loop to slice from new offset
          }
          // Re-query status
          const currentStatus = await getUploadStatus(uploadId);
          offset = currentStatus.uploaded_bytes;
          onProgress?.(offset, total);
          break;
        }

        retries++;
        if (retries >= 5) {
          throw err;
        }
        await new Promise((resolve) => setTimeout(resolve, 500 * retries));
      }
    }
  }
}

export interface StudioOutputClip {
  id: string;
  video_id: string;
  video_title: string;
  source_filename?: string | null;
  title: string;
  description?: string | null;
  duration: number;
  score: number;
  output_path?: string | null;
  thumbnail_path?: string | null;
  publish_status: string;
  publish_progress: number;
  publish_stage?: string | null;
  publish_attempt: number;
  publish_error?: string | null;
  youtube_short_id?: string | null;
  youtube_url?: string | null;
  published_at?: string | null;
  publish_started_at?: string | null;
}

export interface StudioBatchOutputsResponse {
  batch_id: string;
  total_outputs: number;
  outputs: StudioOutputClip[];
}

export async function getBatchOutputs(batchId: string): Promise<StudioBatchOutputsResponse> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${batchId}/outputs`);
  if (!res.ok) {
    throw new Error(`Failed to load batch outputs: HTTP ${res.status}`);
  }
  return res.json();
}
