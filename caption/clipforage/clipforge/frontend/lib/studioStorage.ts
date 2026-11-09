/**
 * ClipForge Upload Studio — Client-Side Staging Storage (IndexedDB)
 *
 * Persists staged video metadata and file blobs locally in the browser.
 * Explicitly distinguishes:
 * 1. File Metadata (file_name, file_size, duration, resolution, etc.)
 * 2. Queue Ordering (strictly zero-indexed: 0..N-1)
 * 3. Media Availability (available vs missing_reselection_required vs quota_exceeded_evicted)
 * 4. Upload Status (staged, queued, uploading, uploaded, failed, cancelled)
 */

export type MediaAvailability = 
  | 'available' 
  | 'missing_reselection_required' 
  | 'quota_exceeded_evicted';

export type StagedUploadStatus = 
  | 'staged' 
  | 'queued' 
  | 'uploading' 
  | 'uploaded' 
  | 'failed' 
  | 'cancelled';

export interface StagedFileMetadata {
  file_name: string;
  file_size: number;
  mime_type: string;
  last_modified: number;
  duration?: number | null;
  resolution?: string | null;
}

export interface StagedVideoItem {
  id: string;
  queue_position: number; // Strictly zero-indexed: 0..N-1
  metadata: StagedFileMetadata;
  media_availability: MediaAvailability;
  upload_status: StagedUploadStatus;
  error_message?: string | null;
  storage_warning?: string | null;
  file_blob?: Blob | File | null;
  server_video_id?: string | null;
  batch_id?: string | null;
  uploaded_bytes?: number;
  processing_status?: string | null;
  processing_progress?: number;
  processing_step?: string | null;
  processing_error?: string | null;
}

export type StorageSimulationMode = 'none' | 'quota_blob_evict' | 'fatal_write_fail';

let currentSimulationMode: StorageSimulationMode = 'none';

/**
 * Diagnostic hook for testing quota and storage failure resilience.
 * Does not write junk to disk or corrupt the database.
 */
export function setStorageSimulationMode(mode: StorageSimulationMode): void {
  currentSimulationMode = mode;
}

export function getStorageSimulationMode(): StorageSimulationMode {
  return currentSimulationMode;
}

if (typeof window !== 'undefined') {
  (window as unknown as { __clipforgeStudio: unknown }).__clipforgeStudio = (window as unknown as { __clipforgeStudio: unknown }).__clipforgeStudio || {
    getQueue: () => loadStagedQueue(),
    setStorageSimulationMode,
    getStorageSimulationMode,
    saveStagedQueue,
    loadStagedQueue,
    reattachFileBlob,
    clearStagedQueue,
  };
}

const DB_NAME = 'ClipForgeStudioDB';
const DB_VERSION = 2; // Incremented for structured schema
const STORE_NAME = 'staged_videos';

function openStudioDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.indexedDB) {
      reject(new Error('IndexedDB is not supported in this environment.'));
      return;
    }

    const request = window.indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (db.objectStoreNames.contains(STORE_NAME)) {
        db.deleteObjectStore(STORE_NAME);
      }
      const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
      store.createIndex('queue_position', 'queue_position', { unique: false });
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('Failed to open IndexedDB.'));
  });
}

/**
 * Helper to persist items metadata-only in a dedicated transaction
 * when quota or clone constraints evict the binary blob.
 */
async function saveItemsMetadataOnly(db: IDBDatabase, items: StagedVideoItem[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction([STORE_NAME], 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const clearReq = store.clear();

    clearReq.onsuccess = () => {
      let pending = items.length;
      if (pending === 0) return resolve();

      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        const fallbackItem: StagedVideoItem = {
          ...item,
          queue_position: i,
          file_blob: null,
          media_availability: 'quota_exceeded_evicted',
          storage_warning: 'Browser storage quota exceeded. Video bytes evicted; metadata preserved. Reselection required.',
        };
        const putReq = store.put(fallbackItem);
        putReq.onsuccess = () => {
          pending--;
          if (pending === 0) resolve();
        };
        putReq.onerror = () => reject(putReq.error);
      }
    };

    clearReq.onerror = () => reject(clearReq.error);
    tx.onerror = () => reject(tx.error);
  });
}

/**
 * Persists the entire staged queue to IndexedDB.
 * Handles storage quota limits gracefully: if persisting file_blob fails due to
 * QuotaExceededError or clone constraints, the entry is saved with
 * media_availability = 'quota_exceeded_evicted' and storage_warning set,
 * ensuring file metadata and zero-indexed queue order are never lost.
 */
export async function saveStagedQueue(items: StagedVideoItem[]): Promise<void> {
  // 1. Controlled simulation check for testing
  if (currentSimulationMode === 'fatal_write_fail') {
    throw new Error('Simulated IndexedDB fatal write failure: Disk I/O error or quota limit on metadata.');
  }

  const db = await openStudioDB();

  // If simulating blob eviction, jump directly to metadata-only save
  if (currentSimulationMode === 'quota_blob_evict') {
    await saveItemsMetadataOnly(db, items);
    return;
  }

  return new Promise((resolve, reject) => {
    let hasAttemptedFallback = false;

    const doFallback = async () => {
      if (hasAttemptedFallback) return;
      hasAttemptedFallback = true;
      try {
        await saveItemsMetadataOnly(db, items);
        resolve();
      } catch (err) {
        reject(err);
      }
    };

    const tx = db.transaction([STORE_NAME], 'readwrite');
    const store = tx.objectStore(STORE_NAME);

    // Clear existing records first to guarantee clean contiguous state
    const clearReq = store.clear();

    clearReq.onsuccess = () => {
      let pendingPuts = items.length;
      if (pendingPuts === 0) {
        resolve();
        return;
      }

      for (let i = 0; i < items.length; i++) {
        // Enforce strict zero-indexed queue_position: 0..N-1
        const item: StagedVideoItem = {
          ...items[i],
          queue_position: i,
          // If blob is absent, ensure media_availability is not falsely marked 'available'
          media_availability: items[i].file_blob ? items[i].media_availability : (
            items[i].media_availability === 'quota_exceeded_evicted' 
              ? 'quota_exceeded_evicted' 
              : 'missing_reselection_required'
          ),
        };

        try {
          const putReq = store.put(item);
          putReq.onsuccess = () => {
            pendingPuts--;
            if (pendingPuts === 0) resolve();
          };
          putReq.onerror = (e) => {
            e.preventDefault();
            console.warn(`[StudioStorage] Quota or write error on item ${item.metadata.file_name}. Falling back to metadata-only.`);
            doFallback();
          };
        } catch {
          // Synchronous DOMException / Quota fallback
          doFallback();
          return;
        }
      }
    };

    clearReq.onerror = () => doFallback();
    tx.onerror = () => {
      // Transaction-level abort due to quota
      doFallback();
    };
  });
}

/**
 * Loads all staged queue items from IndexedDB sorted strictly by queue_position (0..N-1).
 * Detects missing blob data and verifies media availability.
 */
export async function loadStagedQueue(): Promise<StagedVideoItem[]> {
  const db = await openStudioDB();

  return new Promise((resolve, reject) => {
    const tx = db.transaction([STORE_NAME], 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const getAllReq = store.getAll();

    getAllReq.onsuccess = () => {
      const records = (getAllReq.result || []) as StagedVideoItem[];
      // Sort by internal zero-indexed queue_position
      records.sort((a, b) => (a.queue_position ?? 0) - (b.queue_position ?? 0));

      // Re-verify availability and re-normalize strictly 0..N-1
      const normalized: StagedVideoItem[] = records.map((rec, idx) => {
        const hasBlob = Boolean(rec.file_blob && rec.file_blob instanceof Blob);
        const mediaAvailability: MediaAvailability = hasBlob
          ? 'available'
          : (rec.media_availability === 'quota_exceeded_evicted' ? 'quota_exceeded_evicted' : 'missing_reselection_required');

        return {
          ...rec,
          queue_position: idx, // Guaranteed zero-indexed 0..N-1
          media_availability: mediaAvailability,
          storage_warning: !hasBlob
            ? (rec.storage_warning || 'Original file is unavailable in browser storage. Reselection required before upload.')
            : null,
        };
      });

      resolve(normalized);
    };

    getAllReq.onerror = () => reject(getAllReq.error);
    tx.onerror = () => reject(tx.error);
  });
}

/**
 * Attaches a reselected File to an existing staged queue item.
 * Preserves queue_position, id, and original user intent.
 * Enforces identity policy validation before marking available.
 */
export async function reattachFileBlob(
  id: string, 
  file: File,
  options?: { 
    allowNameMismatch?: boolean;
    probeMeta?: { duration: number | null; resolution: string | null };
  }
): Promise<StagedVideoItem[]> {
  const current = await loadStagedQueue();
  const index = current.findIndex(item => item.id === id);
  if (index === -1) {
    throw new Error(`Item ${id} not found in staged queue.`);
  }

  const existing = current[index];

  // 1. Supported video extension check
  const validExtensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm'];
  const hasValidExt = validExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
  if (!hasValidExt) {
    throw new Error(`Unsupported file type: '${file.name}' is not a supported video file (.mp4, .mov, .avi, .mkv, .webm).`);
  }

  // 2. Identity policy verification
  if (!options?.allowNameMismatch && file.name.toLowerCase() !== existing.metadata.file_name.toLowerCase()) {
    throw new Error(`Identity policy violation: Selected file '${file.name}' does not match expected staged video '${existing.metadata.file_name}'.`);
  }

  // 3. Validation passed: attach blob and preserve original ID & queue position
  const updatedItem: StagedVideoItem = {
    ...existing,
    file_blob: file,
    media_availability: 'available',
    storage_warning: null,
    metadata: {
      ...existing.metadata,
      file_name: file.name,
      file_size: file.size,
      mime_type: file.type || existing.metadata.mime_type,
      last_modified: file.lastModified,
      duration: options?.probeMeta?.duration !== undefined ? options.probeMeta.duration : existing.metadata.duration,
      resolution: options?.probeMeta?.resolution !== undefined ? options.probeMeta.resolution : existing.metadata.resolution,
    },
  };

  current[index] = updatedItem;
  await saveStagedQueue(current);
  return current;
}

/**
 * Clears all staged videos from IndexedDB.
 */
export async function clearStagedQueue(): Promise<void> {
  const db = await openStudioDB();

  return new Promise((resolve, reject) => {
    const tx = db.transaction([STORE_NAME], 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req = store.clear();

    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    tx.onerror = () => reject(tx.error);
  });
}

/**
 * Removes an item by ID from IndexedDB and re-compacts queue positions to contiguous 0..N-1.
 */
export async function removeStagedVideo(id: string): Promise<StagedVideoItem[]> {
  const current = await loadStagedQueue();
  const updated = current.filter(item => item.id !== id);
  // Re-normalize positions strictly 0..N-1
  const recompacted = updated.map((item, idx) => ({ ...item, queue_position: idx }));
  await saveStagedQueue(recompacted);
  return recompacted;
}
