const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

function formatApiErrorDetail(detail: unknown, fallback: string): string {
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

async function readResponsePayload(res: Response): Promise<{ data: unknown; rawText: string }> {
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

async function parseFormSubmitResponse(res: Response): Promise<any> {
  const { data, rawText } = await readResponsePayload(res);
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    if (obj.detail !== undefined && typeof obj.detail !== 'string') {
      return { ...obj, detail: formatApiErrorDetail(obj.detail, `HTTP ${res.status}`) };
    }
    return data;
  }
  if (!res.ok) {
    return { detail: rawText.trim() || `HTTP ${res.status}` };
  }
  return {};
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  const { data, rawText } = await readResponsePayload(res);
  if (!res.ok) {
    const fallback = rawText.trim() || `HTTP ${res.status}`;
    const msg =
      data && typeof data === 'object' && 'detail' in data
        ? formatApiErrorDetail((data as { detail: unknown }).detail, fallback)
        : formatApiErrorDetail(data, fallback);
    throw new Error(msg || `HTTP ${res.status}`);
  }
  if (data === null) {
    return {} as T;
  }
  return data as T;
}

// ── Stats ────────────────────────────────────────────────────────────
export const getStats = () => request<{
  total_videos: number; total_clips: number;
  published_clips: number; active_channels: number;
}>('/api/stats');

export function extractYouTubeVideoId(inputUrl: string): string | null {
  if (!inputUrl || typeof inputUrl !== 'string') return null;
  const match = inputUrl.match(
    /(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/|live\/))([a-zA-Z0-9_-]{11})/
  );
  return match ? match[1] : null;
}

export function getVideoFrameUrl(videoId: string, timestamp: number, shotId?: number): string {
  const params = new URLSearchParams();
  params.set('timestamp', timestamp.toFixed(3));
  if (shotId !== undefined && shotId !== null) {
    params.set('shot_id', shotId.toString());
  }
  return `${API_BASE}/api/videos/${encodeURIComponent(videoId)}/frame?${params.toString()}`;
}

// ── Videos ───────────────────────────────────────────────────────────
import type { GamingLayoutConfig } from './gamingCoordinates';
export type { GamingLayoutConfig };

export interface PodcastRegion {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  color?: string;
}

export interface SubmitYouTubeOptions {
  numClips?: number;
  clipsCount?: number;
  reframeMode?: string;
  hookTitle?: boolean;
  enableBroll?: boolean;
  enableHook?: boolean;
  targetLanguage?: string;
  maxClipDuration?: number;
  publishDestinationId?: string;
  destinationIds?: string[];
  targetDuration?: number;
  segmentationStrategy?: string;
  channelId?: string;
  auto_clip?: boolean;
  clipMode?: string;
  regions?: PodcastRegion[];
  podcastComposition?: string;
  shotSchedule?: any[];
  gamingLayout?: GamingLayoutConfig | string;
}

export interface UploadVideoOptions {
  numClips?: number;
  clipsCount?: number;
  reframeMode?: string;
  hookTitle?: boolean;
  enableBroll?: boolean;
  enableHook?: boolean;
  targetLanguage?: string;
  maxClipDuration?: number;
  publishDestinationId?: string;
  destinationIds?: string[];
  targetDuration?: number;
  segmentationStrategy?: string;
  clipMode?: string;
  regions?: PodcastRegion[];
  podcastComposition?: string;
  shotSchedule?: any[];
  gamingLayout?: GamingLayoutConfig | string;
}

export function submitYouTubeUrl(
  url: string,
  numClipsOrOptions?: number | SubmitYouTubeOptions,
  reframeMode?: string,
  hookTitle?: boolean,
  enableBroll?: boolean,
  enableHook?: boolean,
  targetLanguage?: string,
  maxClipDuration?: number,
  publishDestinationId?: string,
  destinationIds?: string[],
  targetDuration?: number,
  segmentationStrategy?: string,
  channelId?: string,
  clipMode?: string
): Promise<any> {
  const form = new FormData();
  form.append('url', url);

  if (typeof numClipsOrOptions === 'object' && numClipsOrOptions !== null) {
    const opts = numClipsOrOptions;
    if (opts.numClips !== undefined && opts.clipsCount !== undefined) {
      form.append('num_clips', opts.numClips.toString());
      form.append('clips_count', opts.clipsCount.toString());
    } else if (opts.numClips !== undefined) {
      form.append('num_clips', opts.numClips.toString());
      form.append('clips_count', opts.numClips.toString());
    } else if (opts.clipsCount !== undefined) {
      form.append('num_clips', opts.clipsCount.toString());
      form.append('clips_count', opts.clipsCount.toString());
    }
    if (opts.maxClipDuration !== undefined && opts.maxClipDuration !== null) form.append('max_clip_duration', opts.maxClipDuration.toString());
    if (opts.reframeMode !== undefined) form.append('reframe_mode', opts.reframeMode);
    if (opts.hookTitle !== undefined) form.append('hook_title', opts.hookTitle ? 'true' : 'false');
    if (opts.enableBroll !== undefined) form.append('enable_broll', opts.enableBroll ? 'true' : 'false');
    if (opts.enableHook !== undefined) form.append('enable_hook', opts.enableHook ? 'true' : 'false');
    if (opts.targetLanguage) form.append('target_language', opts.targetLanguage);
    if (opts.clipMode) form.append('clip_mode', opts.clipMode);
    if (opts.publishDestinationId) form.append('publish_destination_id', opts.publishDestinationId);
    if (opts.destinationIds !== undefined && opts.destinationIds !== null) form.append('destination_ids', JSON.stringify(opts.destinationIds));
    if (opts.targetDuration !== undefined && opts.targetDuration !== null) form.append('target_duration', opts.targetDuration.toString());
    if (opts.segmentationStrategy) form.append('segmentation_strategy', opts.segmentationStrategy);
    if (opts.channelId) form.append('channel_id', opts.channelId);
    if (opts.auto_clip !== undefined) form.append('auto_clip', opts.auto_clip ? 'true' : 'false');
    if (opts.regions !== undefined && opts.regions.length > 0) form.append('regions', JSON.stringify(opts.regions));
    if (opts.podcastComposition) form.append('podcast_composition', opts.podcastComposition);
    if (opts.shotSchedule !== undefined && opts.shotSchedule.length > 0) form.append('shot_schedule', JSON.stringify(opts.shotSchedule));
    if (opts.gamingLayout !== undefined) {
      const serialized = typeof opts.gamingLayout === 'string'
        ? opts.gamingLayout
        : JSON.stringify(opts.gamingLayout);
      form.append('gaming_layout', serialized);
    }
  } else {
    if (numClipsOrOptions !== undefined && numClipsOrOptions !== null) {
      form.append('num_clips', numClipsOrOptions.toString());
      form.append('clips_count', numClipsOrOptions.toString());
    }
    if (maxClipDuration !== undefined && maxClipDuration !== null) form.append('max_clip_duration', maxClipDuration.toString());
    if (reframeMode !== undefined) form.append('reframe_mode', reframeMode);
    if (hookTitle !== undefined) form.append('hook_title', hookTitle ? 'true' : 'false');
    if (enableBroll !== undefined) form.append('enable_broll', enableBroll ? 'true' : 'false');
    if (enableHook !== undefined) form.append('enable_hook', enableHook ? 'true' : 'false');
    if (targetLanguage) form.append('target_language', targetLanguage);
    if (clipMode) form.append('clip_mode', clipMode);
    if (publishDestinationId) form.append('publish_destination_id', publishDestinationId);
    if (destinationIds !== undefined && destinationIds !== null) form.append('destination_ids', JSON.stringify(destinationIds));
    if (targetDuration !== undefined && targetDuration !== null) form.append('target_duration', targetDuration.toString());
    if (segmentationStrategy) form.append('segmentation_strategy', segmentationStrategy);
    if (channelId) form.append('channel_id', channelId);
  }

  return fetch(`${API_BASE}/api/videos/url`, { method: 'POST', body: form }).then(parseFormSubmitResponse);
}

export const processYouTubeUrl = submitYouTubeUrl;

export interface PodcastAnalysisStatusResponse {
  status: 'processing' | 'success' | 'failed';
  progress?: number;
  stage?: string;
  message?: string;
  result?: any;
  error?: string;
}

export interface PodcastShotAnalysisResponse {
  status: string;
  video_id: string;
  ref_timestamp: number;
  total_shots: number;
  review_needed_count: number;
  shots: Array<{
    shot_id: number;
    start_time: number;
    end_time: number;
    duration: number;
    active_track_id: string;
    confidence: number;
    review_needed: boolean;
    crop_rect: { x: number; y: number; w: number; h: number; norm_x: number; norm_y: number; norm_w: number; norm_h: number };
    fallback_policy: string;
  }>;
}

export async function getPodcastAnalysisStatus(taskId: string, signal?: AbortSignal): Promise<PodcastAnalysisStatusResponse> {
  const res = await fetch(`${API_BASE}/api/videos/podcast/analysis-status/${encodeURIComponent(taskId)}`, { signal });
  const { data, rawText } = await readResponsePayload(res);
  if (!res.ok) {
    const fallback = rawText.trim() || 'Failed to query analysis status';
    const msg =
      data && typeof data === 'object' && 'detail' in data
        ? formatApiErrorDetail((data as { detail: unknown }).detail, fallback)
        : fallback;
    throw new Error(msg || 'Failed to query analysis status');
  }
  return (data ?? {}) as PodcastAnalysisStatusResponse;
}

export async function analyzePodcastShots(
  url: string,
  regions: PodcastRegion[],
  refTimestamp: number = 0.0,
  onProgress?: (stage: string, progress: number) => void,
  composition?: string,
  signal?: AbortSignal,
  timeoutMs: number = 180000
): Promise<PodcastShotAnalysisResponse> {
  if (signal?.aborted) {
    throw new DOMException('Analysis polling aborted by user or component unmount', 'AbortError');
  }

  const form = new FormData();
  form.append('url', url);
  form.append('regions', JSON.stringify(regions));
  form.append('ref_timestamp', refTimestamp.toString());
  if (composition) {
    form.append('composition', composition);
  }
  form.append('async_mode', 'true');
  const res = await fetch(`${API_BASE}/api/videos/podcast/analyze-shots`, {
    method: 'POST',
    body: form,
    signal,
  });
  const { data, rawText } = await readResponsePayload(res);
  if (!res.ok) {
    const fallback = rawText.trim() || 'Failed to analyze podcast shots';
    const msg =
      data && typeof data === 'object' && 'detail' in data
        ? formatApiErrorDetail((data as { detail: unknown }).detail, fallback)
        : fallback;
    throw new Error(msg || 'Failed to analyze podcast shots');
  }

  const payload = (data && typeof data === 'object' ? data : {}) as {
    status?: string;
    task_id?: string;
  };

  // If backend processed asynchronously in Celery queue, poll until complete or wall-clock deadline
  if (payload.status === 'queued' && payload.task_id) {
    const taskId = payload.task_id;
    const startTime = Date.now();
    const pollIntervalMs = 1200;

    while (Date.now() - startTime < timeoutMs) {
      if (signal?.aborted) {
        throw new DOMException('Analysis polling aborted by user or component unmount', 'AbortError');
      }

      // Interruptible delay: resolves after pollIntervalMs or rejects immediately upon abort signal
      await new Promise<void>((resolve, reject) => {
        if (signal?.aborted) {
          return reject(new DOMException('Analysis polling aborted by user or component unmount', 'AbortError'));
        }
        const onAbort = () => {
          clearTimeout(timer);
          reject(new DOMException('Analysis polling aborted by user or component unmount', 'AbortError'));
        };
        const timer = setTimeout(() => {
          if (signal) {
            signal.removeEventListener('abort', onAbort);
          }
          resolve();
        }, pollIntervalMs);

        if (signal) {
          signal.addEventListener('abort', onAbort, { once: true });
        }
      });

      if (Date.now() - startTime >= timeoutMs) {
        break;
      }

      const statusRes = await getPodcastAnalysisStatus(taskId, signal);
      if (statusRes.status === 'processing') {
        if (onProgress) {
          onProgress(statusRes.stage || 'analyzing', statusRes.progress || 20);
        }
      } else if (statusRes.status === 'success' && statusRes.result) {
        return statusRes.result;
      } else if (statusRes.status === 'failed') {
        throw new Error(statusRes.error || 'Shot analysis failed in worker');
      }
    }
    throw new Error(`Shot analysis timed out in background worker after ${Math.round(timeoutMs / 1000)} seconds`);
  }

  return payload as PodcastShotAnalysisResponse;
}

export const uploadVideoFile = (
  file: File,
  numClipsOrOptions?: number | UploadVideoOptions,
  reframeMode?: string,
  hookTitle?: boolean,
  enableBroll?: boolean,
  enableHook?: boolean,
  targetLanguage?: string,
  maxClipDuration?: number,
  clipMode?: string,
  targetDuration?: number,
  segmentationStrategy?: string,
  destinationIds?: string[],
  publishDestinationId?: string
) => {
  const form = new FormData();
  form.append('file', file);

  if (typeof numClipsOrOptions === 'object' && numClipsOrOptions !== null) {
    const opts = numClipsOrOptions;
    if (opts.numClips !== undefined && opts.clipsCount !== undefined) {
      form.append('num_clips', opts.numClips.toString());
      form.append('clips_count', opts.clipsCount.toString());
    } else if (opts.numClips !== undefined) {
      form.append('num_clips', opts.numClips.toString());
      form.append('clips_count', opts.numClips.toString());
    } else if (opts.clipsCount !== undefined) {
      form.append('num_clips', opts.clipsCount.toString());
      form.append('clips_count', opts.clipsCount.toString());
    }
    if (opts.maxClipDuration !== undefined && opts.maxClipDuration !== null) form.append('max_clip_duration', opts.maxClipDuration.toString());
    if (opts.reframeMode !== undefined) form.append('reframe_mode', opts.reframeMode);
    if (opts.hookTitle !== undefined) form.append('hook_title', opts.hookTitle ? 'true' : 'false');
    form.append('enable_broll', opts.enableBroll ? 'true' : 'false');
    form.append('enable_hook', opts.enableHook ? 'true' : 'false');
    if (opts.targetLanguage) form.append('target_language', opts.targetLanguage);
    if (opts.clipMode) form.append('clip_mode', opts.clipMode);
    if (opts.publishDestinationId) form.append('publish_destination_id', opts.publishDestinationId);
    if (opts.destinationIds !== undefined && opts.destinationIds !== null) form.append('destination_ids', JSON.stringify(opts.destinationIds));
    if (opts.targetDuration !== undefined && opts.targetDuration !== null) form.append('target_duration', opts.targetDuration.toString());
    if (opts.segmentationStrategy) form.append('segmentation_strategy', opts.segmentationStrategy);
    if (opts.regions !== undefined && opts.regions.length > 0) {
      form.append('regions', JSON.stringify(opts.regions));
    }
    if (opts.podcastComposition) {
      form.append('podcast_composition', opts.podcastComposition);
    }
    if (opts.shotSchedule !== undefined && opts.shotSchedule.length > 0) {
      form.append('shot_schedule', JSON.stringify(opts.shotSchedule));
    }
    if (opts.gamingLayout !== undefined) {
      const serialized = typeof opts.gamingLayout === 'string'
        ? opts.gamingLayout
        : JSON.stringify(opts.gamingLayout);
      form.append('gaming_layout', serialized);
    }
  } else {
    if (numClipsOrOptions !== undefined && numClipsOrOptions !== null) {
      form.append('num_clips', numClipsOrOptions.toString());
      form.append('clips_count', numClipsOrOptions.toString());
    }
    if (maxClipDuration !== undefined && maxClipDuration !== null) {
      form.append('max_clip_duration', maxClipDuration.toString());
    }
    if (reframeMode !== undefined) {
      form.append('reframe_mode', reframeMode);
    }
    if (hookTitle !== undefined) {
      form.append('hook_title', hookTitle ? 'true' : 'false');
    }
    form.append('enable_broll', enableBroll ? 'true' : 'false');
    form.append('enable_hook', enableHook ? 'true' : 'false');
    if (targetLanguage) {
      form.append('target_language', targetLanguage);
    }
    if (clipMode) {
      form.append('clip_mode', clipMode);
    }
    if (publishDestinationId) {
      form.append('publish_destination_id', publishDestinationId);
    }
    if (destinationIds !== undefined && destinationIds !== null) {
      form.append('destination_ids', JSON.stringify(destinationIds));
    }
    if (targetDuration !== undefined && targetDuration !== null) {
      form.append('target_duration', targetDuration.toString());
    }
    if (segmentationStrategy) {
      form.append('segmentation_strategy', segmentationStrategy);
    }
  }
  return fetch(`${API_BASE}/api/videos/upload`, { method: 'POST', body: form }).then(parseFormSubmitResponse);
};

export const uploadVideo = uploadVideoFile;
export const uploadRawVideo = uploadVideoFile;

export const submitGamingUrl = (
  url: string,
  layout: GamingLayoutConfig,
  options?: Omit<SubmitYouTubeOptions, 'gamingLayout' | 'reframeMode'>
) =>
  submitYouTubeUrl(url, {
    ...options,
    reframeMode: 'gaming',
    gamingLayout: layout,
  });

export const submitGamingUpload = (
  file: File,
  layout: GamingLayoutConfig,
  options?: Omit<UploadVideoOptions, 'gamingLayout' | 'reframeMode'>
) =>
  uploadVideoFile(file, {
    ...options,
    reframeMode: 'gaming',
    gamingLayout: layout,
  });

export interface BatchYouTubeOptions {
  numClips?: number;
  clipsCount?: number;
  maxClipDuration?: number;
  clipMode?: string;
  reframeMode?: string;
  enableBroll?: boolean;
  enableHook?: boolean;
  targetLanguage?: string;
  targetDuration?: number;
  segmentationStrategy?: string;
  destinationIds?: string[];
  publishDestinationId?: string;
}

export const submitBatchYouTubeUrls = (
  urls: string[],
  clipsCountOrOptions?: number | BatchYouTubeOptions,
  maxClipDuration?: number,
  clipMode?: string,
  reframeMode?: string,
  enableBroll?: boolean,
  enableHook?: boolean,
  targetLanguage?: string,
  targetDuration?: number,
  segmentationStrategy?: string,
  destinationIds?: string[],
  publishDestinationId?: string
) => {
  if (typeof clipsCountOrOptions === 'object' && clipsCountOrOptions !== null) {
    const opts = clipsCountOrOptions;
    return request<any>('/api/videos/batch', {
      method: 'POST',
      body: JSON.stringify({
        urls,
        clips_count: opts.clipsCount ?? opts.numClips,
        max_clip_duration: opts.maxClipDuration ?? 49,
        clip_mode: opts.clipMode || 'ai_highlights',
        reframe_mode: opts.reframeMode || undefined,
        enable_broll: opts.enableBroll ?? false,
        enable_hook: opts.enableHook ?? false,
        target_language: opts.targetLanguage ?? 'none',
        target_duration: opts.targetDuration,
        segmentation_strategy: opts.segmentationStrategy,
        ...(opts.publishDestinationId ? { publish_destination_id: opts.publishDestinationId } : {}),
        ...(opts.destinationIds !== undefined && opts.destinationIds !== null ? { destination_ids: opts.destinationIds } : {}),
      }),
    });
  }

  return request<any>('/api/videos/batch', {
    method: 'POST',
    body: JSON.stringify({
      urls,
      clips_count: clipsCountOrOptions,
      max_clip_duration: maxClipDuration ?? 49,
      clip_mode: clipMode || 'ai_highlights',
      reframe_mode: reframeMode || undefined,
      enable_broll: enableBroll ?? false,
      enable_hook: enableHook ?? false,
      target_language: targetLanguage ?? 'none',
      target_duration: targetDuration,
      segmentation_strategy: segmentationStrategy,
      ...(publishDestinationId ? { publish_destination_id: publishDestinationId } : {}),
      ...(destinationIds !== undefined && destinationIds !== null ? { destination_ids: destinationIds } : {}),
    }),
  });
};

export const processBatchUrls = submitBatchYouTubeUrls;

export const listVideos = () => request<any[]>('/api/videos/');

// ── Clips ─────────────────────────────────────────────────────────────
export interface Clip {
  id: string;
  video_id: string;
  title: string;
  description?: string | null;
  duration: number;
  score: number;
  start_time?: number;
  end_time?: number;
  thumbnail_path?: string | null;
  output_path?: string | null;
  status?: string;
  metadata_status?: string;
  publish_status: string;
  publish_stage?: string | null;
  publish_progress?: number;
  publish_attempt?: number;
  publish_error?: string | null;
  publish_task_id?: string | null;
  publish_destination_id?: string | null;
  destination_ids?: string[];
  targets?: PublishTarget[];
  youtube_short_id?: string | null;
  youtube_url?: string | null;
  scheduled_at?: string | null;
  published_at?: string | null;
  publish_started_at?: string | null;
  publish_completed_at?: string | null;
  privacy?: string;
  tags?: string;
  category?: string;
  license?: string;
  made_for_kids?: boolean;
  age_restricted?: boolean;
  pinned_comment?: string | null;
  created_at?: string | null;
  source_title?: string | null;
  source_url?: string | null;
  channel_id?: string | null;
  source_channel_name?: string | null;
  [key: string]: any;
}

export const listClips = (params?: { video_id?: string; channel_id?: string; destination_id?: string; from_date?: string; to_date?: string }) => {
  const cleanParams = params
    ? (Object.fromEntries(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
      ) as Record<string, string>)
    : {};
  const q = new URLSearchParams(cleanParams).toString();
  return request<Clip[]>(`/api/clips${q ? '?' + q : ''}`);
};
export const getClip = (id: string) => request<Clip>(`/api/clips/${encodeURIComponent(id)}`);
export const updateClip = (id: string, data: any) => request(`/api/clips/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(data) });
export const deleteClip = (id: string) => request(`/api/clips/${encodeURIComponent(id)}`, { method: 'DELETE' });

export interface CleanupCandidate {
  clip_id: string;
  title: string;
  score: number | null;
  category: string;
  output_path: string | null;
  size_bytes: number;
}

export interface CleanupCounts {
  low_score: number;
  unavailable: number;
  total_unique: number;
}

export interface CleanupProtectedCounts {
  published: number;
  high_score: number;
  active_jobs: number;
  active_reservations: number;
}

export interface CleanupPreviewResponse {
  preview_token: string;
  preview_id: string;
  expires_at: number;
  counts: CleanupCounts;
  reclaimable_bytes: number;
  reclaimable_human: string;
  candidates: CleanupCandidate[];
  protected_counts: CleanupProtectedCounts;
}

export interface CleanupExecuteRequest {
  preview_token: string;
  candidate_clip_ids: string[];
  purge_missing_media?: boolean;
}

export interface CleanupSummary {
  requested_count: number;
  deleted_clip_records: number;
  purged_physical_files: number;
  shared_files_retained: number;
  skipped_count: number;
  failed_count: number;
  confirmed_reclaimed_bytes: number;
  confirmed_reclaimed_human: string;
}

export interface CleanupExecuteResponse {
  status: string;
  summary: CleanupSummary;
  deleted_clip_ids: string[];
  skipped_candidates: Array<{ clip_id: string; reason: string }>;
  retained_shared_files: string[];
  recovery_pending: string[];
}

export const previewCleanup = (scoreThreshold: number = 5.0) =>
  request<CleanupPreviewResponse>(`/api/clips/cleanup/preview?score_threshold=${encodeURIComponent(String(scoreThreshold))}`);

export const executeCleanup = (data: CleanupExecuteRequest) =>
  request<CleanupExecuteResponse>('/api/clips/cleanup/execute', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const downloadClipUrl = (id: string) => `${API_BASE}/api/clips/${id}/download`;
export const downloadVariantUrl = (clipId: string, variantId: string) => `${API_BASE}/api/clips/${clipId}/variants/${variantId}/download`;
export const thumbnailUrl = (id: string) => `${API_BASE}/api/clips/${id}/thumbnail`;
export const getClipMetadata = (id: string) => request<any>(`/api/clips/${encodeURIComponent(id)}/metadata`);

// ── AI Enhancements (Phase 2.1 - B-roll, SFX, Hooks) ──────────────────────
export interface BrollPlacement {
  asset_id: string;
  opportunity_id: string;
  start_time: number;
  end_time: number;
  display_mode: 'full_cutaway' | 'pip_top' | 'pip_bottom' | 'background';
  scale_mode?: string;
  fade_duration?: number;
  confidence: number;
  w?: number;
  h?: number;
  x?: number;
  y?: number;
}

export interface BrollPlan {
  clip_id: string;
  source_clip_version?: string;
  planner_version?: string;
  analysis_version?: string | null;
  placements: BrollPlacement[];
  plan_hash?: string | null;
  generated_timestamp?: number | null;
}

export interface SFXPlacement {
  asset_id: string;
  category: string;
  start_time: number;
  end_time: number;
  gain: number;
  fade_in?: number;
  fade_out?: number;
  ducking_enabled: boolean;
  ducking_target_gain: number;
  confidence: number;
  reason: string;
}

export interface SFXPlan {
  clip_id: string;
  placements: SFXPlacement[];
  pack_id?: string | null;
  planner_version?: string;
}

export interface HookOpportunity {
  id: string;
  clip_id: string;
  start_time: number;
  end_time: number;
  opportunity_type: string;
  source_text?: string | null;
  hook_objective: string;
  confidence: number;
  reason: string;
  priority: number;
}

export interface HookConcept {
  opportunity_id: string;
  hook_style: string;
  hook_text: string;
  target_duration: number;
  delivery_mode: string;
  confidence: number;
  planner_version: string;
}

export interface HookPlan {
  clip_id: string;
  planner_version: string;
  source_analysis_version?: string | null;
  plan_hash?: string | null;
  opportunities: HookOpportunity[];
  concepts: HookConcept[];
  voiceover_plan?: any;
  visual_interventions?: any[];
}

export const getBrollPlan = (clipId: string) =>
  request<BrollPlan>(`/api/clips/${encodeURIComponent(clipId)}/broll-plan`);

export const applyBrollPlan = (clipId: string, plan: BrollPlan) =>
  request<{ applied?: boolean; message: string; task_id?: string; clip_id: string }>(`/api/clips/${encodeURIComponent(clipId)}/broll-apply`, {
    method: 'POST',
    body: JSON.stringify(plan),
  });

export const getSfxPlan = (clipId: string) =>
  request<SFXPlan>(`/api/clips/${encodeURIComponent(clipId)}/sfx-plan`);

export const generateSfxPlan = (clipId: string) =>
  request<SFXPlan>(`/api/clips/${encodeURIComponent(clipId)}/sfx-plan`, { method: 'POST' });

export const applySfxPlan = (clipId: string, plan: SFXPlan) =>
  request<{ applied?: boolean; message: string; task_id?: string; clip_id: string }>(`/api/clips/${encodeURIComponent(clipId)}/sfx-apply`, {
    method: 'POST',
    body: JSON.stringify(plan),
  });

export const getHookPlan = (clipId: string) =>
  request<HookPlan>(`/api/clips/${encodeURIComponent(clipId)}/hook`);

export const generateHookPlan = (clipId: string) =>
  request<{ message: string; task_id: string; clip_id: string }>(`/api/clips/${encodeURIComponent(clipId)}/hook/plan`, {
    method: 'POST',
  });

export const applyHookPlan = (clipId: string, plan: HookPlan) =>
  request<{ message: string; task_id: string; clip_id: string }>(`/api/clips/${encodeURIComponent(clipId)}/hook/apply`, {
    method: 'POST',
    body: JSON.stringify(plan),
  });

export const getClipRetention = (clipId: string) =>
  request<{ clip_id: string; overall_score: number; risks: any[] }>(`/api/clips/${encodeURIComponent(clipId)}/retention`);

export const applyAutofix = (clipId: string) =>
  request<{ message: string; clip_id: string; interventions: number; variant_id?: string }>(`/api/clips/${encodeURIComponent(clipId)}/autofix`, {
    method: 'POST',
  });

export interface ClipVariantItem {
  variant_id: string;
  variant_type: string;
  label: string;
  status: string;
  created_at: string | null;
  download_url: string;
  metadata: Record<string, any>;
}

export const listClipVariants = (clipId: string) =>
  request<ClipVariantItem[]>(`/api/clips/${encodeURIComponent(clipId)}/variants`);

// ── Jobs ──────────────────────────────────────────────────────────────
export interface QueueStats {
  queue: {
    total: number;
    active: number;
    pending: number;
    done: number;
    failed: number;
    cancelled: number;
  };
  last_failure?: {
    job_id: string;
    source_title: string;
    error: string;
    failed_at: string;
  } | null;
}

export interface Job {
  id: string;
  video_id?: string | null;
  source_url: string | null;
  source_title: string | null;
  status: string;
  progress: number;
  current_step: string | null;
  error_message: string | null;
  celery_task_id?: string | null;
  config?: Record<string, any>;
  pipeline_started_at?: string | null;
  completed_at?: string | null;
  is_test?: boolean;
  thumbnail_url?: string | null;
  created_at: string | null;
  created_at_ist?: string | null;
  updated_at: string | null;
  updated_at_ist?: string | null;
}

export const getJob = (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}`);
export const listJobs = (params?: { filter_type?: 'active' | 'history'; limit?: number; include_test?: boolean }) => {
  const searchParams = new URLSearchParams();
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && String(v) !== '') {
        searchParams.set(k, String(v));
      }
    }
  }
  const q = searchParams.toString();
  return request<Job[]>(`/api/jobs/${q ? '?' + q : ''}`);
};
export const getActiveJobs = () => request<Job[]>('/api/jobs/active');
export const getJobHistory = (limit: number = 24) => request<Job[]>(`/api/jobs/history?limit=${encodeURIComponent(String(limit))}`);
export const cancelJob = (id: string) => request<any>(`/api/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' });
export const cancelAllFailedJobs = (includeTest: boolean = false) =>
  request<{ message: string; cancelled_count: number }>(`/api/jobs/cancel-all-failed${includeTest ? '?include_test=true' : ''}`, { method: 'POST' });
export const getJobStats = (includeTest: boolean = false) =>
  request<QueueStats>(`/api/jobs/stats${includeTest ? '?include_test=true' : ''}`);
export const retryJob = (id: string) => request<any>(`/api/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' });


// ── Channels & Decisions ──────────────────────────────────────────
export interface ChannelProcessingProfile {
  duration_mode?: 'adaptive' | 'fixed';
  target_duration?: number;
  min_clip_duration?: number;
  max_clip_duration?: number;
  clips_count?: number;
  video_layout?: 
    | 'fill_blur' 
    | 'fit_black' 
    | 'center_crop' 
    | 'blur_background' 
    | 'creative_transform'
    | string;
  segmentation_strategy?: 'hook_peak_fall' | 'equal_splits';
  scoring_mode?: 'ai';
}

export interface VideoDecision {
  id: string;
  channel_id: string;
  channel_name: string;
  youtube_id: string;
  video_title: string;
  youtube_url: string;
  thumbnail_url?: string | null;
  status: 'awaiting_settings' | 'customizing' | 'resolved_defaults' | 'resolved_custom' | 'cancelled';
  decision_deadline?: string | null;
  remaining_seconds: number;
  channel_profile_snapshot?: ChannelProcessingProfile | null;
  overrides?: Record<string, any> | null;
  lease_token?: string;
  created_at?: string;
  created_at_ist?: string;
}

export interface DecisionHistoryItem {
  id: string;
  channel_id: string;
  channel_name: string;
  youtube_id: string;
  video_title: string;
  is_generated_short?: boolean;
  generated_short_id?: string | null;
  generated_short_url?: string | null;
  generated_short_title?: string | null;
  source_video_title?: string;
  source_youtube_id?: string;
  source_youtube_url?: string;
  youtube_url: string;
  thumbnail_url?: string | null;
  status: string;
  resolved_at?: string | null;
  resolved_at_ist?: string | null;
  overrides?: Record<string, any> | null;
  job_id?: string | null;
  job_status?: string | null;
  job_error?: string | null;
  error_message?: string | null;
  current_step?: string | null;
  pipeline_started_at?: string | null;
  pipeline_started_at_ist?: string | null;
  completed_at?: string | null;
  completed_at_ist?: string | null;
  created_at?: string | null;
  created_at_ist?: string | null;
}

export interface PaginatedVideosResponse {
  channel_id: string;
  channel_name: string;
  items: Array<{
    id: string;
    title: string;
    thumbnail: string | null;
    duration: number | null;
    url: string;
    is_processed: boolean;
    is_generated_short?: boolean;
    parent_source_id?: string | null;
    parent_source_title?: string | null;
    generated_short_title?: string | null;
    published_at: string | null;
    view_count?: number | null;
    decision_id: string | null;
    decision_status: string | null;
    decision_deadline: string | null;
    job_id: string | null;
    job_status?: string | null;
    job_error?: string | null;
  }>;
  page: number;
  page_size: number;
  has_more: boolean;
  sort?: string;
  scan_scope?: number | null;
}

export interface ChannelMappedOutroSummary {
  id: string;
  channel_id: string;
  outro_type: 'video' | 'image';
  duration_seconds: number;
  original_filename?: string | null;
  width?: number | null;
  height?: number | null;
  fps?: number | null;
  has_audio?: boolean;
  version: number;
  is_active: boolean;
  preview_url: string;
}

export interface ChannelMappedDestination {
  id: string;
  youtube_channel_id: string;
  channel_name: string;
  thumbnail_url?: string | null;
  is_active: boolean;
  is_authorized: boolean;
  status: 'connected' | 'needs_reauth' | 'disconnected';
  ready_for_publishing: boolean;
  has_outro: boolean;
  outro_status: 'configured' | 'none';
  active_outro: ChannelMappedOutroSummary | null;
  warning: string | null;
  expires_at?: string | null;
}

export interface ChannelDestinationsResponse {
  channel_id: string;
  channel_name: string;
  auto_publish: boolean;
  publish_destination_id: string | null;
  destination_channel_ids: string[];
  destinations: ChannelMappedDestination[];
  active_destinations_count: number;
  disconnected_destinations_count: number;
}

export interface MonitoredChannel {
  id: string;
  channel_name: string;
  channel_url: string;
  youtube_channel_id: string;
  thumbnail_url?: string | null;
  is_active: boolean;
  auto_clip: boolean;
  auto_publish: boolean;
  publish_destination_id?: string | null;
  destination_channel_ids?: string[];
  destinations?: ChannelMappedDestination[];
  active_destinations_count?: number;
  disconnected_destinations_count?: number;
  processing_profile?: ChannelProcessingProfile | null;
  last_checked_at?: string | null;
  last_checked_at_ist?: string | null;
  clips_generated?: number;
  created_at?: string | null;
  [key: string]: any;
}

export type Channel = MonitoredChannel;

export interface UpdateChannelRequest {
  auto_clip?: boolean;
  auto_publish?: boolean;
  is_active?: boolean;
  publish_destination_id?: string | null;
  destination_channel_ids?: string[];
  processing_profile?: ChannelProcessingProfile;
  [key: string]: any;
}

export const listChannels = () => request<MonitoredChannel[]>('/api/channels/');

export const addChannel = (data: {
  channel_url: string;
  auto_clip: boolean;
  auto_publish: boolean;
  publish_destination_id?: string;
  destination_channel_ids?: string[];
  processing_profile?: ChannelProcessingProfile;
}) =>
  request<{
    message: string;
    channel_name: string;
    id: string;
    publish_destination_id: string | null;
    destination_channel_ids: string[];
    destinations: ChannelMappedDestination[];
    processing_profile?: ChannelProcessingProfile | null;
  }>('/api/channels/', { method: 'POST', body: JSON.stringify(data) });

export const updateChannel = (id: string, data: UpdateChannelRequest) =>
  request<{
    message: string;
    processing_profile?: ChannelProcessingProfile | null;
    auto_clip: boolean;
    auto_publish: boolean;
    publish_destination_id: string | null;
    destination_channel_ids: string[];
    destinations: ChannelMappedDestination[];
    [key: string]: any;
  }>(`/api/channels/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(data) });

export const getChannelDestinations = (channelId: string) =>
  request<ChannelDestinationsResponse>(`/api/channels/${encodeURIComponent(channelId)}/destinations`);

export const updateChannelDestinations = (channelId: string, destinationChannelIds: string[]) =>
  request<{
    message: string;
    channel_id: string;
    auto_publish: boolean;
    publish_destination_id: string | null;
    destination_channel_ids: string[];
    destinations: ChannelMappedDestination[];
  }>(`/api/channels/${encodeURIComponent(channelId)}/destinations`, {
    method: 'PUT',
    body: JSON.stringify({ destination_channel_ids: destinationChannelIds }),
  });

export const deleteChannel = (id: string) =>
  request<any>(`/api/channels/${encodeURIComponent(id)}`, { method: 'DELETE' });

export const checkChannelNow = (id: string) =>
  request<any>(`/api/channels/${encodeURIComponent(id)}/check-now`, { method: 'POST' });

export const getChannelRecentVideos = (id: string) =>
  request<{ channel_name: string; videos: any[] }>(`/api/channels/${encodeURIComponent(id)}/videos`);

export const getChannelVideos = (
  channelId: string,
  page: number = 1,
  pageSize: number = 8,
  sort: string = 'latest',
  scanDepth: number = 50
) => {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort,
    scan_depth: String(scanDepth),
  });
  return request<PaginatedVideosResponse>(`/api/channels/${encodeURIComponent(channelId)}/videos?${params.toString()}`);
};

export const processChannelVideo = (
  channelId: string,
  video: { video_id: string; video_title?: string; video_url: string },
  overrides?: ChannelProcessingProfile
) =>
  request<any>(`/api/channels/${encodeURIComponent(channelId)}/process-video`, {
    method: 'POST',
    body: JSON.stringify({
      video_id: video.video_id,
      video_title: video.video_title,
      video_url: video.video_url,
      overrides: overrides || null,
    }),
  });

export interface ProcessVideoItemResult {
  video_id: string;
  video_title: string;
  status: 'queued' | 'already_processing' | 'rejected' | 'failed';
  job_id?: string;
  decision_id?: string;
  error?: string;
}

export interface BatchProcessVideosResponse {
  total_requested: number;
  queued_count: number;
  already_processing_count: number;
  rejected_count: number;
  items: ProcessVideoItemResult[];
}

export const processChannelVideosBatch = (
  channelId: string,
  videos: Array<{ video_id: string; video_title?: string; video_url: string; overrides?: ChannelProcessingProfile }>,
  overrides?: ChannelProcessingProfile
) =>
  request<BatchProcessVideosResponse>(`/api/channels/${encodeURIComponent(channelId)}/process-videos-batch`, {
    method: 'POST',
    body: JSON.stringify({
      videos,
      overrides: overrides || null,
    }),
  });

export type HistoricalSelectionMode = 'latest' | 'most_viewed' | 'uploaded_since' | 'new_only';

export interface HistoricalCandidateItem {
  id: string;
  title: string;
  url: string;
  thumbnail: string | null;
  duration: number | null;
  published_at: string | null;
  view_count: number | null;
  is_processed: boolean;
  is_generated_short?: boolean;
  parent_source_id?: string | null;
  parent_source_title?: string | null;
  processing_status: string;
  publication_status: string;
  selected_for_queue: boolean;
  decision_id?: string | null;
  job_id?: string | null;
}

export interface HistoricalPreviewResponse {
  channel_id: string;
  channel_name: string;
  mode: HistoricalSelectionMode;
  requested_count: number;
  since_date: string | null;
  total_discovered: number;
  eligible_found: number;
  already_processed: number;
  will_queue: number;
  destination_channel_name: string;
  destination_channel_names?: string[];
  destination_channel_ids?: string[];
  effective_privacy: string;
  has_view_counts: boolean;
  candidate_scope?: {
    scanned_count: number;
    search_depth_limit: number;
    scope_type: 'exhaustive' | 'bounded';
    description: string;
  };
  limitations: string[];
  message?: string;
  items: HistoricalCandidateItem[];
}

export interface HistoricalProcessResponse {
  channel_id: string;
  channel_name: string;
  mode: HistoricalSelectionMode;
  message?: string;
  total_selected: number;
  queued_count: number;
  already_processing_count: number;
  results: Array<{
    video_id: string;
    title: string;
    status: 'queued' | 'already_processing' | 'failed';
    job_id?: string;
    decision_id?: string;
    error?: string;
  }>;
}

export const getHistoricalPreview = (
  channelId: string,
  params: {
    mode: HistoricalSelectionMode;
    count?: number;
    since_date?: string | null;
    max_search_depth?: number;
  }
) =>
  request<HistoricalPreviewResponse>(`/api/channels/${encodeURIComponent(channelId)}/historical-preview`, {
    method: 'POST',
    body: JSON.stringify(params),
  });

export const processHistoricalBatch = (
  channelId: string,
  params: {
    mode: HistoricalSelectionMode;
    video_ids: string[];
    overrides?: ChannelProcessingProfile | null;
  }
) =>
  request<HistoricalProcessResponse>(`/api/channels/${encodeURIComponent(channelId)}/historical-process`, {
    method: 'POST',
    body: JSON.stringify(params),
  });

export const getPendingDecisions = () =>
  request<VideoDecision[]>('/api/channels/decisions/pending');

export const applyDefaultsDecision = (decisionId: string) =>
  request<any>(`/api/channels/decisions/${encodeURIComponent(decisionId)}/apply-defaults`, { method: 'POST' });

export const customizeDecision = (
  decisionId: string,
  body?: { lease_token?: string; force?: boolean },
  channelId?: string
) =>
  request<any>(`/api/channels/decisions/${encodeURIComponent(decisionId)}/customize${channelId ? `?channel_id=${encodeURIComponent(channelId)}` : ''}`, {
    method: 'POST',
    body: body ? JSON.stringify(body) : undefined,
  });

export const saveAndProcessDecision = (
  decisionId: string,
  overrides: ChannelProcessingProfile,
  options?: { lease_token?: string; expected_status?: string; channelId?: string }
) =>
  request<any>(`/api/channels/decisions/${encodeURIComponent(decisionId)}/save-and-process${options?.channelId ? `?channel_id=${encodeURIComponent(options.channelId)}` : ''}`, {
    method: 'POST',
    body: JSON.stringify({
      overrides,
      lease_token: options?.lease_token,
      expected_status: options?.expected_status,
    }),
  });

export const cancelDecision = (decisionId: string) =>
  request<any>(`/api/channels/decisions/${encodeURIComponent(decisionId)}/cancel`, { method: 'POST' });

export const getDecisionHistory = (limit: number = 50) =>
  request<DecisionHistoryItem[]>(`/api/channels/decisions/history?limit=${encodeURIComponent(String(limit))}`);

// ── Publish ───────────────────────────────────────────────────────────
export const getAuthStatus = () => request<{ authenticated: boolean; oauth_url?: string }>('/api/publish/auth-status');

export const submitOAuthCode = (codeOrUrl: string) => {
  // Normalize URL by ensuring it has ? before query parameters
  let normalizedInput = codeOrUrl.trim();
  
  // Fix URLs missing ? character (e.g., http://localhost:8080/state=... → http://localhost:8080/?state=...)
  if (normalizedInput.includes('http') && !normalizedInput.includes('?') && normalizedInput.includes('=')) {
    // Find the first = and insert ? before it
    const slashIndex = normalizedInput.lastIndexOf('/');
    const eqIndex = normalizedInput.indexOf('=');
    if (slashIndex < eqIndex) {
      normalizedInput = normalizedInput.substring(0, slashIndex + 1) + '?' + normalizedInput.substring(slashIndex + 1);
    }
  }
  
  // Support both full redirect URL and plain authorization code
  const payload = normalizedInput.includes('code=') 
    ? { redirect_url: normalizedInput }
    : { code: normalizedInput };
  return request<{ authenticated: boolean }>('/api/publish/oauth-callback', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
};

export interface PublishOutroSummary {
  id: string;
  outro_type: 'video' | 'image';
  duration_seconds: number;
  version: number;
  original_filename: string | null;
  preview_url: string | null;
}

export interface PublishDestination {
  id: string;
  youtube_channel_id: string;
  channel_name: string;
  channel_url: string;
  thumbnail_url: string | null;
  is_default_destination: boolean;
  default_destination_expires_at: string | null;
  is_active: boolean;
  is_authorized: boolean;
  status: 'connected' | 'needs_reauth' | 'disconnected';
  ready_for_publishing: boolean;
  active_outro_id: string | null;
  has_outro: boolean;
  outro: PublishOutroSummary | null;
}

export interface PublishTarget {
  id: string;
  clip_id?: string;
  destination_id: string;
  destination_name?: string;
  channel_name?: string | null;
  destination_youtube_channel_id?: string | null;
  youtube_channel_id?: string | null;
  destination_thumbnail_url?: string | null;
  thumbnail_url?: string | null;
  is_active?: boolean;
  status: string;
  publish_stage: string | null;
  publish_progress: number;
  youtube_video_id: string | null;
  youtube_url: string | null;
  error_message: string | null;
  retry_count?: number;
  privacy?: string;
  scheduled_at?: string | null;
  published_at?: string | null;
  publish_started_at?: string | null;
  publish_completed_at?: string | null;
  rendered_video_path: string | null;
  artifact_storage_key?: string | null;
  outro_applied_id?: string | null;
  outro_applied_version?: number | null;
  has_outro: boolean;
  outro_type?: 'video' | 'image' | string | null;
  outro_duration?: number | null;
  active_outro?: PublishOutroSummary | null;
  preview_url: string;
  preview_info_url?: string;
}

export interface ClipDestinationPreviewInfo {
  clip_id: string;
  destination_id: string;
  destination_name: string;
  is_active: boolean;
  has_outro: boolean;
  outro_file_missing: boolean;
  base_file_missing: boolean;
  preview_error: string | null;
  outro: (PublishOutroSummary & { width?: number | null; height?: number | null }) | null;
  base_duration: number;
  outro_duration: number;
  combined_duration: number;
  exceeds_shorts_limit: boolean;
  variant_ready: boolean;
  stale_variant: boolean;
  storage_key: string;
  preview_url: string;
}

export interface ClipTargetsResponse {
  clip_id: string;
  publish_status: string;
  publish_destination_id: string | null;
  destination_ids: string[];
  targets: PublishTarget[];
}

export const getDestinations = (includeTest: boolean = false) =>
  request<PublishDestination[]>(`/api/publish/destinations${includeTest ? '?include_test=true' : ''}`);
export const listPublishDestinations = getDestinations;

export const setDefaultDestination = (channel_id: string, expires_in_hours: number | null) =>
  request<{ message: string }>('/api/publish/destinations/default', {
    method: 'POST',
    body: JSON.stringify({ channel_id, expires_in_hours }),
  });

export const getChannelInfo = () => request<any>('/api/publish/channel-info');

export interface PublishRequest {
  clip_id: string;
  destination_channel_id?: string | null;
  destination_ids?: string[];
  title?: string;
  description?: string;
  /** @default 'private' */
  privacy?: 'private' | 'unlisted' | 'public' | string;
  made_for_kids?: boolean;
  age_restricted?: boolean;
  tags?: string;
  category?: string;
  license?: string;
  scheduled_at?: string;
}

export type SchedulePublishRequest = PublishRequest & {
  scheduled_at: string;
};

export const publishNow = (data: PublishRequest) =>
  request<any>('/api/publish/publish-now', {
    method: 'POST',
    body: JSON.stringify({ ...data, privacy: data.privacy || 'private' }),
  });

export const schedulePublish = (data: SchedulePublishRequest) =>
  request<any>('/api/publish/schedule', {
    method: 'POST',
    body: JSON.stringify({ ...data, privacy: data.privacy || 'private' }),
  });
export const scheduleClip = schedulePublish;

export interface PublishQueueItem {
  id: string;
  title: string;
  publish_status: string;
  publish_stage?: string | null;
  publish_progress?: number;
  publish_error?: string | null;
  publish_attempt?: number;
  scheduled_at?: string | null;
  published_at?: string | null;
  publish_started_at?: string | null;
  youtube_short_id?: string | null;
  youtube_url?: string | null;
  publish_destination_id?: string | null;
  destination_ids?: string[];
  targets?: PublishTarget[];
  privacy?: string;
  thumbnail_path?: string | null;
}

export const getPublishQueue = (statusFilter?: string) =>
  request<PublishQueueItem[]>(`/api/publish/queue${statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : ''}`);

export interface PublishStatusResponse {
  clip_id: string;
  publish_status: string;
  publish_progress: number;
  publish_stage: string | null;
  publish_attempt: number;
  publish_error: string | null;
  youtube_short_id: string | null;
  youtube_url: string | null;
  published_at: string | null;
  publish_started_at: string | null;
  publish_task_id?: string | null;
  idempotency_key?: string | null;
  targets?: PublishTarget[];
}

export const getPublishStatus = (clipId: string) =>
  request<PublishStatusResponse>(`/api/publish/status/${encodeURIComponent(clipId)}`);

export const retryPublish = (clipId: string, force: boolean = false) =>
  request<any>(`/api/publish/clips/${encodeURIComponent(clipId)}/retry`, {
    method: 'POST',
    body: JSON.stringify({ force }),
  });

export const cancelPublish = (clipId: string) =>
  request<any>(`/api/publish/clips/${encodeURIComponent(clipId)}/cancel`, {
    method: 'POST',
  });

export const getClipTargets = (clipId: string) =>
  request<ClipTargetsResponse>(`/api/publish/clips/${encodeURIComponent(clipId)}/targets`);

export const updateClipDestinations = (clipId: string, destinationIds: string[]) =>
  request<{
    status: string;
    clip_id: string;
    destination_ids: string[];
    targets: PublishTarget[];
  }>(`/api/publish/clips/${encodeURIComponent(clipId)}/destinations`, {
    method: 'PUT',
    body: JSON.stringify({ destination_ids: destinationIds }),
  });

export const retryPublishTarget = (targetId: string, force: boolean = false) =>
  request<{
    status: string;
    target_id: string;
    clip_id: string;
    destination_id: string;
    task_id?: string | null;
    target?: PublishTarget | null;
    message: string;
  }>(`/api/publish/targets/${encodeURIComponent(targetId)}/retry`, {
    method: 'POST',
    body: JSON.stringify({ force }),
  });

export const cancelPublishTarget = (targetId: string) =>
  request<{
    status: string;
    target_id: string;
    clip_id: string;
    message: string;
  }>(`/api/publish/targets/${encodeURIComponent(targetId)}/cancel`, {
    method: 'POST',
  });

export const getClipDestinationPreviewInfo = (clipId: string, destinationId: string) =>
  request<ClipDestinationPreviewInfo>(
    `/api/publish/clips/${encodeURIComponent(clipId)}/destinations/${encodeURIComponent(destinationId)}/preview-info`
  );

export const getClipDestinationPreviewUrl = (
  clipId: string,
  destinationId: string,
  options?: { force?: boolean; cacheBust?: string | number }
): string => {
  const params = new URLSearchParams();
  if (options?.force) {
    params.set('force', 'true');
  }
  if (options?.cacheBust !== undefined && options?.cacheBust !== null && options?.cacheBust !== '') {
    params.set('v', String(options.cacheBust));
  }
  const qs = params.toString();
  return `${API_BASE}/api/publish/clips/${encodeURIComponent(clipId)}/destinations/${encodeURIComponent(destinationId)}/preview${qs ? `?${qs}` : ''}`;
};

// ── Metadata Editor (Phase 3.2 / C-06) ──────────────────────────────
export interface ClipPublishMetadata {
  id: string;
  video_id: string;
  title: string;
  description: string;
  tags: string[];
  category: string;
  license: string;
  privacy: string;
  made_for_kids: boolean;
  age_restricted: boolean;
  pinned_comment?: string;
  publish_destination_id?: string | null;
  scheduled_at?: string | null;
  publish_status?: string;
  duration?: number;
  metadata_status?: string;
}

export interface UpdateClipPublishMetadataRequest {
  title?: string;
  description?: string;
  tags?: string[] | string;
  category?: string;
  license?: string;
  privacy?: string;
  made_for_kids?: boolean;
  age_restricted?: boolean;
  pinned_comment?: string;
  publish_destination_id?: string | null;
}

export const getClipPublishMetadata = (clipId: string) =>
  request<ClipPublishMetadata>(`/api/publish/clips/${encodeURIComponent(clipId)}/metadata`);

export const updateClipPublishMetadata = (clipId: string, data: UpdateClipPublishMetadataRequest) =>
  request<{ status: string; message: string; metadata: ClipPublishMetadata }>(`/api/publish/clips/${encodeURIComponent(clipId)}/metadata`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

// ── Analytics (Phase 4 & Phase 14 A/B & Insights) ────────────────────────
export interface VideoAnalyticsSnapshot {
  id: number;
  view_count: number;
  like_count: number;
  comment_count: number;
  view_score: number | null;
  fetched_at: string | null;
}

export interface VideoAnalyticsResponse {
  video_id: string;
  latest_score: number | null;
  trend: 'up' | 'down' | 'stable';
  total_polls: number;
  snapshots: VideoAnalyticsSnapshot[];
}

export interface SEOSnapshot {
  clip_id: string;
  seo_score: number;
  ctr_score: number;
  discoverability_score: number;
  missing_keywords: string[];
  recommended_hashtags: string[];
  weak_hashtags: string[];
  created_at: string | null;
  title: string;
  tags: string[];
  hashtags: string[];
  view_score_at_optimization: number;
}

export interface SEOAnalysisResponse {
  video_id: string;
  total_snapshots: number;
  latest_seo_score: number | null;
  latest_ctr_score: number | null;
  snapshots: SEOSnapshot[];
}

export interface OptimizationLogEntry {
  id: number;
  attempt: number;
  new_title: string | null;
  view_score: number | null;
  created_at: string | null;
}

export interface OptimizationLogResponse {
  video_id: string;
  total_attempts: number;
  log: OptimizationLogEntry[];
}

export interface ActiveTracker {
  task_id: string;
  done: boolean;
  clip_id?: string;
  youtube_video_id?: string;
  uploaded_at?: string | null;
  next_check_at?: string | null;
  optimization_attempts?: number;
  last_score?: number | null;
  status?: string;
}

export interface ActiveTrackersResponse {
  active_trackers: ActiveTracker[];
}

export const getPipelineSummary = () => request<any>('/api/analytics/summary');
export const getSEOAnalysis = (videoId: string) => request<SEOAnalysisResponse>(`/api/analytics/seo/${encodeURIComponent(videoId)}`);
export const getVideoAnalytics = (videoId: string) => request<VideoAnalyticsResponse>(`/api/analytics/${encodeURIComponent(videoId)}`);
export const getOptimizationLog = (videoId: string) => request<OptimizationLogResponse>(`/api/analytics/optimize/${encodeURIComponent(videoId)}/log`);
export const setAutoOptimizeFlag = (videoId: string, autoOptimize: boolean) =>
  request<{ target_id?: string; video_id: string; auto_optimize: boolean; message: string }>(
    `/api/analytics/optimize/${encodeURIComponent(videoId)}/flag?auto_optimize=${encodeURIComponent(String(autoOptimize))}`,
    { method: 'PATCH' }
  );
export const triggerOptimizer = (videoId: string, youtubeVideoId?: string) =>
  request<{ status: string; video_id: string; youtube_video_id: string; message: string }>(
    `/api/analytics/optimize/${encodeURIComponent(videoId)}`,
    {
      method: 'POST',
      body: JSON.stringify({ youtube_video_id: youtubeVideoId || '' }),
    }
  );
export const getActiveTrackers = () => request<ActiveTrackersResponse>('/api/analytics/active');
export const startTracker = (videoId: string, youtubeVideoId?: string) =>
  request<{ status: string; task_id: string; video_id: string; youtube_video_id: string; message: string }>(
    `/api/analytics/track/${encodeURIComponent(videoId)}`,
    {
      method: 'POST',
      body: JSON.stringify({ youtube_video_id: youtubeVideoId || '' }),
    }
  );
export const cancelTracker = (taskId: string) =>
  request<{ status: string; task_id: string }>(`/api/analytics/cancel/${encodeURIComponent(taskId)}`, {
    method: 'POST',
  });
export const getABTests = () => request<any[]>('/api/analytics/ab-tests');
export const getChannelInsights = () => request<any>('/api/analytics/insights');

// ── My YouTube Channels Management & Outros ──────────────────────────
export interface OutroMetadata {
  id: string;
  channel_id: string;
  file_path: string;
  original_filename: string | null;
  file_size_bytes: number | null;
  mime_type?: string | null;
  file_size?: number | null;
  outro_type: 'video' | 'image';
  duration_seconds: number;
  width: number | null;
  height: number | null;
  fps: number | null;
  has_audio: boolean;
  version: number;
  is_active: boolean;
  preview_url: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface OutroResponse {
  status: string;
  channel_id: string;
  outro: OutroMetadata;
}

export interface OutroUploadResponse {
  status: string;
  message: string;
  channel_id: string;
  outro: OutroMetadata;
}

export interface OutroDeleteResponse {
  status: string;
  channel_id: string;
  message: string;
}

export interface ChannelPublishingSettings {
  /** @default 'private' */
  default_privacy?: 'public' | 'unlisted' | 'private';
  default_category?: string;
  default_tags?: string | string[];
  default_license?: 'youtube' | 'creative_commons';
  default_made_for_kids?: boolean;
  default_age_restricted?: boolean;
  watermark_url?: string | null;
  brand_color_primary?: string | null;
  brand_logo_position?: 'top_right' | 'top_left' | 'bottom_right' | 'bottom_left';
}

export interface ChannelCachedStats {
  subscriber_count: number | null;
  video_count: number;
  view_count: number;
  shorts_count: number;
  shorts_scan_coverage: string;
  shorts_classification_method: string;
  likes_count: number | null;
  likes_scope: string;
  fetched_at: string;
  status: string;
  warning_metadata?: string | null;
}

export interface YouTubeChannelDestination {
  id: string;
  youtube_channel_id: string;
  channel_name: string;
  channel_url: string;
  thumbnail_url: string | null;
  google_account_identity?: string | null;
  is_destination: boolean;
  is_default_destination: boolean;
  is_active: boolean;
  is_authorized: boolean;
  upload_permission_status?: 'granted' | 'missing_scope' | 'missing' | 'expired' | 'revoked' | string;
  status: 'connected' | 'needs_reauth' | 'disconnected';
  ready_for_publishing?: boolean;
  has_outro?: boolean;
  outro_status?: 'configured' | 'none';
  active_outro?: OutroMetadata | null;
  mapped_sources_count?: number;
  last_successful_upload?: string | null;
  last_publishing_error?: string | null;
  last_publishing_error_at?: string | null;
  publishing_settings?: ChannelPublishingSettings | null;
  cached_stats?: ChannelCachedStats | null;
  is_test?: boolean;
  created_at?: string | null;
}

export type YouTubeChannel = YouTubeChannelDestination;
export type DestinationChannel = YouTubeChannelDestination;

export interface RefreshChannelStatsResponse {
  status: string;
  rate_limited?: boolean;
  cooldown_remaining_seconds?: number;
  message?: string;
  channel_id: string;
  youtube_channel_id: string;
  cached_stats: ChannelCachedStats;
}

export interface ChannelStatsResponse {
  channel_id: string;
  youtube_channel_id: string;
  channel_name: string;
  status: 'connected' | 'needs_reauth' | 'disconnected';
  is_authorized: boolean;
  is_default_destination: boolean;
  cached_stats?: ChannelCachedStats | null;
  cooldown_remaining_seconds: number;
  can_refresh: boolean;
}

export const getYoutubeChannels = (includeTest: boolean = false) =>
  request<YouTubeChannelDestination[]>(`/api/youtube-channels${includeTest ? '?include_test=true' : ''}`);

export const getYoutubeChannelStats = (channelId: string) =>
  request<ChannelStatsResponse>(`/api/youtube-channels/${encodeURIComponent(channelId)}/stats`);

export const refreshYoutubeChannelStats = (channelId: string, force: boolean = false) =>
  request<RefreshChannelStatsResponse>(
    `/api/youtube-channels/${encodeURIComponent(channelId)}/refresh${force ? '?force=true' : ''}`,
    { method: 'POST' }
  );

export const updateYoutubeChannelSettings = (channelId: string, settings: Partial<ChannelPublishingSettings>) => {
  const payload: Partial<ChannelPublishingSettings> = { ...settings };
  if ('default_privacy' in payload && !payload.default_privacy) {
    payload.default_privacy = 'private';
  }
  return request<{ status: string; channel_id: string; youtube_channel_id: string; publishing_settings: ChannelPublishingSettings }>(
    `/api/youtube-channels/${encodeURIComponent(channelId)}/settings`,
    { method: 'PATCH', body: JSON.stringify(payload) }
  );
};
export const updateYouTubeChannel = updateYoutubeChannelSettings;

export const setPrimaryDefaultDestination = (channelId: string) =>
  request<{ status: string; default_channel_id: string; is_default_destination: boolean }>(
    `/api/youtube-channels/${encodeURIComponent(channelId)}/set-default`,
    { method: 'POST' }
  );

export const disconnectYoutubeChannel = (channelId: string) =>
  request<{ status: string; channel_id: string; is_active: boolean; message: string }>(
    `/api/youtube-channels/${encodeURIComponent(channelId)}/disconnect`,
    { method: 'POST' }
  );

export const deleteYoutubeChannel = (channelId: string) =>
  request<{ status: string; channel_id: string; youtube_channel_id: string; channel_name: string; message: string }>(
    `/api/youtube-channels/${encodeURIComponent(channelId)}`,
    { method: 'DELETE' }
  );

export const getYoutubeOAuthUrl = () =>
  request<{ oauth_url: string; state: string }>('/api/youtube-channels/oauth-url');

export const connectYoutubeChannel = (codeOrUrl: string, state?: string) => {
  let normalizedInput = codeOrUrl.trim();
  if (normalizedInput.includes('http') && !normalizedInput.includes('?') && normalizedInput.includes('=')) {
    const slashIndex = normalizedInput.lastIndexOf('/');
    const eqIndex = normalizedInput.indexOf('=');
    if (slashIndex < eqIndex) {
      normalizedInput = normalizedInput.substring(0, slashIndex + 1) + '?' + normalizedInput.substring(slashIndex + 1);
    }
  }
  const payload: { redirect_url?: string; code?: string; state?: string } = normalizedInput.includes('code=')
    ? { redirect_url: normalizedInput }
    : { code: normalizedInput };
  if (state) {
    payload.state = state;
  }
  return request<{
    status: string;
    channel: Partial<YouTubeChannelDestination> & {
      id: string;
      youtube_channel_id: string;
      channel_name: string;
    };
  }>('/api/youtube-channels/connect', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
};
export const connectYouTubeChannel = connectYoutubeChannel;

export async function uploadChannelOutro(
  channelId: string,
  file: File,
  outroType: 'video' | 'image',
  durationSeconds?: number | null
): Promise<OutroUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('outro_type', outroType);
  if (typeof durationSeconds === 'number' && Number.isFinite(durationSeconds)) {
    form.append('duration_seconds', durationSeconds.toString());
  }

  const res = await fetch(`${API_BASE}/api/youtube-channels/${encodeURIComponent(channelId)}/outro`, {
    method: 'POST',
    body: form,
  });
  const { data, rawText } = await readResponsePayload(res);
  if (!res.ok) {
    const fallback = rawText.trim() || `HTTP ${res.status}`;
    const msg =
      data && typeof data === 'object' && 'detail' in data
        ? formatApiErrorDetail((data as { detail: unknown }).detail, fallback)
        : formatApiErrorDetail(data, fallback);
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return (data ?? {}) as OutroUploadResponse;
}

export const getChannelOutro = (channelId: string) =>
  request<OutroResponse>(`/api/youtube-channels/${encodeURIComponent(channelId)}/outro`);

export const updateChannelOutroDuration = (channelId: string, durationSeconds: number) =>
  request<OutroResponse>(`/api/youtube-channels/${encodeURIComponent(channelId)}/outro`, {
    method: 'PATCH',
    body: JSON.stringify({ duration_seconds: durationSeconds }),
  });

export const deleteChannelOutro = (channelId: string) =>
  request<OutroDeleteResponse>(`/api/youtube-channels/${encodeURIComponent(channelId)}/outro`, {
    method: 'DELETE',
  });

export const getChannelOutroPreviewUrl = (channelId: string, cacheBust?: string | number): string => {
  const base = `${API_BASE}/api/youtube-channels/${encodeURIComponent(channelId)}/outro/preview`;
  if (cacheBust !== undefined && cacheBust !== null && cacheBust !== '') {
    return `${base}?v=${encodeURIComponent(String(cacheBust))}`;
  }
  return base;
};

// ── System Settings API (Phase 5.1 / C-09: REQ-GAP-001) ─────────────────────
export interface SystemSettings {
  YOUTUBE_CLIENT_ID: string;
  YOUTUBE_CLIENT_SECRET_SET: boolean;
  YOUTUBE_CLIENT_SECRET_MASKED: string;
  OPENROUTER_API_KEY_SET?: boolean;
  OPENROUTER_API_KEY_MASKED?: string;
  OPENROUTER_MODEL?: string;
  GROQ_API_KEY_SET?: boolean;
  GROQ_API_KEY_MASKED?: string;
  GROQ_MODEL?: string;
  NVIDIA_API_KEY_SET?: boolean;
  NVIDIA_API_KEY_MASKED?: string;
  NVIDIA_MODEL?: string;
  WHISPER_MODEL: string;
  CLIPS_PER_VIDEO: number;
  CHANNEL_CHECK_INTERVAL_MINUTES: number;
  PUBLISH_MODE: string;
  SCORING_MODE: string;
  REFRAME_MODE: string;
  CONTENT_ID_BYPASS: boolean;
  last_updated_at?: string | null;
}

export interface SettingsUpdateRequest {
  YOUTUBE_CLIENT_ID?: string;
  YOUTUBE_CLIENT_SECRET?: string;
  OPENROUTER_API_KEY?: string;
  OPENROUTER_MODEL?: string;
  GROQ_API_KEY?: string;
  GROQ_MODEL?: string;
  NVIDIA_API_KEY?: string;
  NVIDIA_MODEL?: string;
  WHISPER_MODEL?: string;
  CLIPS_PER_VIDEO?: number;
  CHANNEL_CHECK_INTERVAL_MINUTES?: number;
  REFRAME_MODE?: string;
  CONTENT_ID_BYPASS?: boolean;
}

export const getSystemSettings = () => request<SystemSettings>('/api/settings');

export const updateSystemSettings = (data: SettingsUpdateRequest) =>
  request<SystemSettings>('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  });

// ── Multi-Language Dubbing (Phase 6.1 / CAP-001) ──────────────────────────

export interface DubbingLanguage {
  code: string;
  name: string;
  native_name: string;
  default_voice: string;
  voice_provider: string;
}

export interface DubbingLanguagesResponse {
  languages: DubbingLanguage[];
}

export interface DubbingPlanItem {
  id: string;
  plan_id: string;
  target_language: string;
  target_language_name: string;
  voice_provider: string;
  voice_id: string;
  is_voice_clone: boolean;
  status: string;
  error_message?: string | null;
  created_at?: string | null;
  variant_id?: string | null;
  variant_status?: string | null;
}

export interface ClipDubbingResponse {
  clip_id: string;
  plans: DubbingPlanItem[];
}

export interface DubbingTriggerRequest {
  clip_id: string;
  target_language: string;
  voice_provider?: string;
  voice_id?: string;
  is_voice_clone?: boolean;
  authorization_granted?: boolean;
  plan_version?: string;
}

export interface DubbingTriggerResponse {
  message: string;
  task_id: string;
  clip_id: string;
  target_language: string;
  status: string;
}

export interface DubbingTaskStatusResponse {
  task_id: string;
  status: string;
  ready: boolean;
  result?: any;
  error?: string;
}

export const getDubbingLanguages = () =>
  request<DubbingLanguagesResponse>('/api/dubbing/languages');

export const getClipDubbing = (clipId: string) =>
  request<ClipDubbingResponse>(`/api/dubbing/${encodeURIComponent(clipId)}`);

export const triggerClipDubbing = (clipId: string, data: DubbingTriggerRequest) =>
  request<DubbingTriggerResponse>(`/api/dubbing/${encodeURIComponent(clipId)}`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
export const getDubbingTaskStatus = (taskId: string) =>
  request<DubbingTaskStatusResponse>(`/api/dubbing/tasks/${encodeURIComponent(taskId)}`);

export interface SourceSeoMetadataResponse {
  source_video_id: string;
  primary_category: string;
  youtube_category_id: string;
  secondary_topics: string[];
  seo_tags: string[];
  description_hashtags: string[];
  summary: string;
  source_title: string;
  source_youtube_id: string;
  source_youtube_url: string;
  is_ai_generated: boolean;
  analyzed_at: string;
}

export const getVideoSeoMetadata = (videoId: string) =>
  request<SourceSeoMetadataResponse>(`/api/videos/${encodeURIComponent(videoId)}/seo-metadata`);

export const refreshVideoSeoMetadata = (videoId: string) =>
  request<SourceSeoMetadataResponse>(`/api/videos/${encodeURIComponent(videoId)}/seo-metadata/refresh`, {
    method: 'POST',
  });

// ── Live Streaming API ───────────────────────────────────────────────────────
export interface LiveStreamValidation {
  valid: boolean;
  youtube_id: string;
  title: string;
  thumbnail_url?: string | null;
  channel_name?: string | null;
  channel_id?: string | null;
  is_live: boolean;
  live_status: string; // 'is_live' | 'is_upcoming' | 'was_live' | 'not_live'
  duration: number;
  is_already_monitored: boolean;
  existing_job_id?: string | null;
  message: string;
}

export interface LiveStreamJobSummary {
  id: string;
  video_id?: string | null;
  youtube_url: string;
  youtube_id: string;
  video_title: string;
  thumbnail_url?: string | null;
  channel_name?: string | null;
  status: string; // 'monitoring' | 'processing' | 'waiting' | 'completed' | 'stopped' | 'failed'
  live_status: string;
  current_step?: string | null;
  total_duration: number;
  processed_until: number;
  clips_count: number;
  clip_generation_mode: string;
  monitoring_interval_minutes: number;
  next_check_at?: string | null;
  last_processed_at?: string | null;
  stop_requested?: boolean;
  error_message?: string | null;
  created_at?: string | null;
  clips_generated: number;
  segments_count?: number;
}

export interface LiveStreamSegmentItem {
  id: string;
  segment_index: number;
  start_time: number;
  end_time: number;
  duration: number;
  clips_generated: number;
  status: string;
  created_at?: string | null;
}

export interface LiveStreamClipItem {
  id: string;
  video_id: string;
  title: string;
  description?: string | null;
  start_time: number;
  end_time: number;
  duration: number;
  score: number;
  output_path?: string | null;
  thumbnail_path?: string | null;
  status: string;
  publish_status: string;
  created_at?: string | null;
}

export interface LiveStreamJobDetails extends LiveStreamJobSummary {
  segments: LiveStreamSegmentItem[];
  clips: LiveStreamClipItem[];
  clips_generated_count: number;
}

export const validateLiveStreamUrl = (url: string) =>
  request<LiveStreamValidation>('/api/livestream/validate', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });

export const startLiveStreamMonitoring = (data: {
  youtube_url: string;
  clip_count: number;
  clip_generation_mode: string;
}) =>
  request<{ success: boolean; job_id: string; video_id: string; title: string; status: string; message: string }>(
    '/api/livestream/start',
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  );

export const getLiveStreamJobs = () =>
  request<{ items: LiveStreamJobSummary[]; total: number }>('/api/livestream/jobs');

export const getActiveLiveStreamJobs = () =>
  request<{ active_jobs: LiveStreamJobSummary[]; count: number }>('/api/livestream/active');

export const getLiveStreamJobDetails = (jobId: string) =>
  request<LiveStreamJobDetails>(`/api/livestream/${encodeURIComponent(jobId)}`);

export const stopLiveStreamMonitoring = (jobId: string) =>
  request<{ success: boolean; job_id: string; status: string; message: string }>(
    `/api/livestream/${encodeURIComponent(jobId)}/stop`,
    { method: 'POST' }
  );

export const resumeLiveStreamMonitoring = (jobId: string) =>
  request<{ success: boolean; job_id: string; status: string; message: string }>(
    `/api/livestream/${encodeURIComponent(jobId)}/resume`,
    { method: 'POST' }
  );

export const checkLiveStreamNow = (jobId: string) =>
  request<{ success: boolean; job_id: string; status: string; message: string }>(
    `/api/livestream/${encodeURIComponent(jobId)}/check-now`,
    { method: 'POST' }
  );

export const deleteLiveStreamJob = (jobId: string) =>
  request<{ success: boolean; message: string }>(
    `/api/livestream/${encodeURIComponent(jobId)}`,
    { method: 'DELETE' }
  );



