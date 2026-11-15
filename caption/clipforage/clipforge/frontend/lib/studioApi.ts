/**
 * ClipForge Upload Studio — Client API Driver
 *
 * Implements resumable chunk streaming, single-writer fencing negotiation,
 * concurrency limiting (<= 3 concurrent streams), range chunking (<= 10 MiB),
 * and transparent recovery of interrupted uploads.
 */

import type { PublishTarget } from './api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export const CHUNK_SIZE_BYTES = 5 * 1024 * 1024; // 5 MiB chunks (<= 10 MiB limit)
export const MAX_CONCURRENT_UPLOADS = 3;

function formatStudioErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const obj = item as { msg?: unknown; message?: unknown; loc?: unknown };
          const msg = obj.msg ?? obj.message;
          const loc = Array.isArray(obj.loc) ? obj.loc.join('.') : '';
          if (typeof msg === 'string' && msg) {
            return loc ? `${loc}: ${msg}` : msg;
          }
          try {
            return JSON.stringify(item);
          } catch {
            return String(item);
          }
        }
        return String(item ?? '');
      })
      .filter(Boolean);
    if (parts.length > 0) {
      return parts.join('; ');
    }
  }
  if (detail && typeof detail === 'object') {
    const obj = detail as { message?: unknown; error?: unknown };
    if (typeof obj.message === 'string' && obj.message.trim()) return obj.message;
    if (typeof obj.error === 'string' && obj.error.trim()) return obj.error;
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

async function readStudioResponsePayload(res: Response): Promise<{ data: unknown; rawText: string }> {
  if (typeof (res as unknown as { text?: unknown }).text === 'function') {
    const rawText = await res.text();
    if (!rawText || !rawText.trim()) {
      return { data: null, rawText: '' };
    }
    try {
      return { data: JSON.parse(rawText), rawText };
    } catch {
      return { data: null, rawText };
    }
  }
  if (typeof (res as unknown as { json?: unknown }).json === 'function') {
    try {
      const data = await res.json();
      return { data, rawText: '' };
    } catch {
      return { data: null, rawText: '' };
    }
  }
  return { data: null, rawText: '' };
}

function buildStudioErrorMessage(res: Response, data: unknown, rawText: string, defaultMsg: string): string {
  const httpFallback = rawText.trim() || `${defaultMsg}: HTTP ${res.status}`;
  if (data && typeof data === 'object' && 'detail' in data) {
    return formatStudioErrorDetail((data as { detail: unknown }).detail, httpFallback) || httpFallback;
  }
  if (data !== null) {
    return formatStudioErrorDetail(data, httpFallback) || httpFallback;
  }
  return rawText.trim() || `${defaultMsg}: HTTP ${res.status}`;
}

export interface StudioCreateBatchOptions {
  destination_ids?: string[];
  reframe_mode?: string;
}

export interface StudioProcessBatchOptions {
  destination_ids?: string[];
  reframe_mode?: string;
  clip_mode?: string;
  clips_count?: number;
  max_clip_duration?: number;
}

export interface CreateBatchPayload extends StudioCreateBatchOptions {
  idempotency_key: string;
  name?: string;
}

export type ProcessBatchPayload = StudioProcessBatchOptions;

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
  config?: Record<string, any> | null;
  destination_ids?: string[];
  reframe_mode?: string | null;
  videos: StudioVideoResponse[];
}

export type StudioBatch = StudioBatchResponse;

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
export async function createStudioBatch(payload: CreateBatchPayload): Promise<StudioBatchResponse>;
export async function createStudioBatch(
  idempotencyKey: string,
  name?: string,
  options?: StudioCreateBatchOptions
): Promise<StudioBatchResponse>;
export async function createStudioBatch(
  idempotencyKeyOrPayload: string | CreateBatchPayload,
  name?: string,
  options?: StudioCreateBatchOptions
): Promise<StudioBatchResponse> {
  const payload: CreateBatchPayload =
    typeof idempotencyKeyOrPayload === 'string'
      ? {
          idempotency_key: idempotencyKeyOrPayload,
          ...(name ? { name } : {}),
          ...(options || {}),
        }
      : idempotencyKeyOrPayload;

  const bodyPayload: Record<string, unknown> = {
    idempotency_key: payload.idempotency_key,
  };
  if (payload.name) {
    bodyPayload.name = payload.name;
  }
  if (payload.destination_ids !== undefined) {
    bodyPayload.destination_ids = payload.destination_ids;
  }
  if (payload.reframe_mode) {
    bodyPayload.reframe_mode = payload.reframe_mode;
  }

  const res = await fetch(`${API_BASE}/api/studio/batches`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bodyPayload),
  });
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to create batch'));
  }
  return (data ?? {}) as StudioBatchResponse;
}

export const createBatch = createStudioBatch;

/**
 * Fetches current batch status and video queue.
 */
export async function getStudioBatch(batchId: string): Promise<StudioBatchResponse> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}`);
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to fetch batch'));
  }
  return (data ?? {}) as StudioBatchResponse;
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
  const res = await fetch(`${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}/videos/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(item),
  });
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to init video'));
  }
  return (data ?? {}) as StudioVideoResponse;
}

/**
 * Queries committed offset and status for an upload.
 */
export async function getUploadStatus(uploadId: string): Promise<UploadStatusResponse> {
  const res = await fetch(`${API_BASE}/api/studio/uploads/${encodeURIComponent(uploadId)}`);
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to get upload status'));
  }
  return (data ?? {}) as UploadStatusResponse;
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
  const res = await fetch(`${API_BASE}/api/studio/uploads/${encodeURIComponent(uploadId)}/chunk`, {
    method: 'PUT',
    headers: {
      'Content-Range': `bytes ${start}-${end}/${total}`,
      'Content-Type': 'application/octet-stream',
    },
    body: chunkBlob,
  });

  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    const errData =
      data && typeof data === 'object'
        ? data
        : { detail: rawText.trim() || `HTTP ${res.status}` };
    const msg = buildStudioErrorMessage(res, data, rawText, 'Failed to upload chunk');
    const error: Error & { status?: number; data?: unknown } = new Error(msg);
    error.status = res.status;
    error.data = errData;
    throw error;
  }
  return (data ?? {}) as { upload_id: string; uploaded_bytes: number; total_bytes: number; status: string };
}

/**
 * Reorders batch items (0..N-1) using optimistic version check.
 */
export async function reorderStudioBatch(
  batchId: string,
  version: number,
  itemIds: string[]
): Promise<{ batch_id: string; version: number; reordered_count: number }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}/reorder`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version, item_ids: itemIds }),
  });
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to reorder batch'));
  }
  return (data ?? {}) as { batch_id: string; version: number; reordered_count: number };
}

/**
 * Retries a failed or interrupted upload.
 */
export async function retryStudioUpload(
  uploadId: string
): Promise<{ upload_id: string; uploaded_bytes: number; total_bytes: number; status: string }> {
  const res = await fetch(`${API_BASE}/api/studio/uploads/${encodeURIComponent(uploadId)}/retry`, {
    method: 'POST',
  });
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to retry upload'));
  }
  return (data ?? {}) as { upload_id: string; uploaded_bytes: number; total_bytes: number; status: string };
}

/**
 * Cancels a video item and cleans its artifacts.
 */
export async function cancelStudioVideo(
  batchId: string,
  videoId: string
): Promise<{ cancelled: boolean; video_id: string }> {
  const res = await fetch(
    `${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}/videos/${encodeURIComponent(videoId)}`,
    { method: 'DELETE' }
  );
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to cancel video'));
  }
  return (data ?? {}) as { cancelled: boolean; video_id: string };
}

/**
 * Deletes a batch and cleans its artifacts behind a barrier.
 */
export async function deleteStudioBatch(
  batchId: string
): Promise<{ deleted: boolean; batch_id: string }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}`, {
    method: 'DELETE',
  });
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    if (res.status === 404) {
      // Idempotent: batch is already gone from server
      return { deleted: true, batch_id: batchId };
    }
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to delete batch'));
  }
  return (data ?? {}) as { deleted: boolean; batch_id: string };
}

/**
 * Idempotently starts sequential processing of all uploaded videos in a batch.
 */
export async function processStudioBatch(
  batchId: string,
  options?: StudioProcessBatchOptions
): Promise<StudioBatchResponse> {
  let cleanedBody: Record<string, unknown> | undefined;
  if (options) {
    const candidate: Record<string, unknown> = {};
    if (options.destination_ids !== undefined) {
      candidate.destination_ids = options.destination_ids;
    }
    if (options.reframe_mode) {
      candidate.reframe_mode = options.reframe_mode;
    }
    if (options.clip_mode) {
      candidate.clip_mode = options.clip_mode;
    }
    if (typeof options.clips_count === 'number' && Number.isFinite(options.clips_count)) {
      candidate.clips_count = options.clips_count;
    }
    if (typeof options.max_clip_duration === 'number' && Number.isFinite(options.max_clip_duration)) {
      candidate.max_clip_duration = options.max_clip_duration;
    }
    if (Object.keys(candidate).length > 0) {
      cleanedBody = candidate;
    }
  }

  const res = await fetch(`${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}/process`, {
    method: 'POST',
    ...(cleanedBody
      ? {
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(cleanedBody),
        }
      : {}),
  });
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to start batch processing'));
  }
  return (data ?? {}) as StudioBatchResponse;
}

export const processBatch = processStudioBatch;

/**
 * Requests cooperative cancellation of batch processing.
 */
export async function cancelStudioBatch(
  batchId: string
): Promise<{ cancelled?: boolean; cancellation_requested?: boolean; batch_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}/cancel`, {
    method: 'POST',
  });
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to cancel batch'));
  }
  return (data ?? {}) as { cancelled?: boolean; cancellation_requested?: boolean; batch_id: string; status: string };
}

/**
 * Retries a failed video in the batch preserving original queue position.
 */
export async function retryStudioVideo(
  batchId: string,
  videoId: string
): Promise<{ retried: boolean; video_id: string; queue_position: number; status: string }> {
  const res = await fetch(
    `${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}/videos/${encodeURIComponent(videoId)}/retry`,
    { method: 'POST' }
  );
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to retry video'));
  }
  return (data ?? {}) as { retried: boolean; video_id: string; queue_position: number; status: string };
}

/**
 * Retries batch processing from the first failed item.
 */
export async function retryStudioBatch(
  batchId: string
): Promise<{ retried: boolean; batch_id: string; resumed_from_video_id?: string }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}/retry`, {
    method: 'POST',
  });
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to retry batch'));
  }
  return (data ?? {}) as { retried: boolean; batch_id: string; resumed_from_video_id?: string };
}

/**
 * Safely recovers a batch with a stale processing worker.
 */
export async function recoverStudioBatch(
  batchId: string
): Promise<{ recovered: boolean; batch_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}/recover`, {
    method: 'POST',
  });
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to recover batch'));
  }
  return (data ?? {}) as { recovered: boolean; batch_id: string; status: string };
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

export type { PublishTarget };
export type StudioOutputTarget = PublishTarget;

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
  publish_destination_id?: string | null;
  destination_ids?: string[];
  targets?: PublishTarget[];
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
  const res = await fetch(`${API_BASE}/api/studio/batches/${encodeURIComponent(batchId)}/outputs`);
  const { data, rawText } = await readStudioResponsePayload(res);
  if (!res.ok) {
    throw new Error(buildStudioErrorMessage(res, data, rawText, 'Failed to load batch outputs'));
  }
  return (data ?? {}) as StudioBatchOutputsResponse;
}
