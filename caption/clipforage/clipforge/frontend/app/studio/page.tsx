'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { 
  StagedVideoItem, 
  saveStagedQueue, 
  loadStagedQueue, 
  clearStagedQueue, 
  removeStagedVideo,
  reattachFileBlob,
  setStorageSimulationMode,
  getStorageSimulationMode
} from '@/lib/studioStorage';
import {
  createStudioBatch,
  getStudioBatch,
  initStudioVideo,
  streamFileInChunks,
  retryStudioUpload,
  deleteStudioBatch,
  processStudioBatch,
  cancelStudioBatch,
  retryStudioVideo,
  retryStudioBatch,
  getBatchOutputs,
  StudioOutputClip
} from '@/lib/studioApi';

function formatBytes(bytes: number): string {
  if (!bytes || isNaN(bytes) || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || isNaN(seconds)) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export default function UploadStudioPage() {
  const [queue, setQueue] = useState<StagedVideoItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [draggedItemId, setDraggedItemId] = useState<string | null>(null);
  const [dragOverItemId, setDragOverItemId] = useState<string | null>(null);
  const [showProcessModal, setShowProcessModal] = useState(false);
  const [announcement, setAnnouncement] = useState('');
  
  // Storage & Error Feedback States
  const [fileSelectionError, setFileSelectionError] = useState<string | null>(null);
  const [reselectError, setReselectError] = useState<string | null>(null);
  const [storageSyncStatus, setStorageSyncStatus] = useState<'synced' | 'saving' | 'memory_only_error'>('synced');
  const [storageErrorMessage, setStorageErrorMessage] = useState<string | null>(null);

  // Batch Upload Runtime States
  const [isUploadingBatch, setIsUploadingBatch] = useState(false);
  const uploadingRef = useRef(false);
  const [uploadBatchError, setUploadBatchError] = useState<string | null>(null);
  const [currentBatchId, setCurrentBatchId] = useState<string | null>(null);

  // Batch Processing Runtime States (Phase 2)
  const [isProcessingBatch, setIsProcessingBatch] = useState(false);
  const [batchProcessingStatus, setBatchProcessingStatus] = useState<string | null>(null);
  const [activeProcessingVideoId, setActiveProcessingVideoId] = useState<string | null>(null);
  const [batchProcessingError, setBatchProcessingError] = useState<string | null>(null);
  const [batchOutputs, setBatchOutputs] = useState<StudioOutputClip[]>([]);

  // Reselection tracking
  const [reselectTargetId, setReselectTargetId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const reselectInputRef = useRef<HTMLInputElement>(null);

  // Backend deployment probe state
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'not_deployed'>('checking');

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    fetch(`${apiBase}/api/health`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.status === 'ok') {
          setBackendStatus('connected');
        } else {
          setBackendStatus('not_deployed');
        }
      })
      .catch(() => {
        setBackendStatus('not_deployed');
      });
  }, []);

  // Poll batch status during active sequential processing
  useEffect(() => {
    if (!currentBatchId) return;
    if (batchProcessingStatus !== 'queued' && batchProcessingStatus !== 'processing' && batchProcessingStatus !== 'cancelling') {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const batchData = await getStudioBatch(currentBatchId);
        setBatchProcessingStatus(batchData.status);
        setActiveProcessingVideoId(batchData.active_video_id || null);
        setBatchProcessingError(batchData.batch_error || null);

        if (batchData.status === 'completed' || batchData.status === 'failed' || batchData.status === 'cancelled') {
          setIsProcessingBatch(false);
        }

        // Fetch generated outputs when completed or if any videos finished
        if (batchData.status === 'completed' || (batchData.videos && batchData.videos.some((v) => v.processing_status === 'completed'))) {
          getBatchOutputs(currentBatchId).then((res) => setBatchOutputs(res.outputs || [])).catch(() => {});
        }

        // Reconcile video item states from server
        setQueue((prevQueue) => {
          const updated = [...prevQueue];
          for (const serverV of batchData.videos) {
            const localItem = updated.find((it) => it.server_video_id === serverV.id || it.id === serverV.client_item_id);
            if (localItem) {
              localItem.processing_status = serverV.processing_status;
              localItem.processing_progress = serverV.processing_progress;
              localItem.processing_step = serverV.processing_step;
              localItem.processing_error = serverV.processing_error;
            }
          }
          return updated;
        });
      } catch (err) {
        console.error('[UploadStudio] Poll error:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [currentBatchId, batchProcessingStatus]);

  // Load existing staged queue from IndexedDB on initial mount
  useEffect(() => {
    let isMounted = true;
    loadStagedQueue()
      .then((items) => {
        if (isMounted) {
          setQueue(items);
          setIsLoading(false);
          setStorageSyncStatus('synced');
          const activeBatch = items.find((it) => it.batch_id)?.batch_id;
          if (activeBatch) {
            setCurrentBatchId(activeBatch);
            // Sync server batch state to preserve processing across page refresh
            getStudioBatch(activeBatch)
              .then((serverBatch) => {
                if (serverBatch) {
                  setBatchProcessingStatus(serverBatch.status);
                  setActiveProcessingVideoId(serverBatch.active_video_id || null);
                  setBatchProcessingError(serverBatch.batch_error || null);
                  if (serverBatch.status === 'queued' || serverBatch.status === 'processing') {
                    setIsProcessingBatch(true);
                  }
                  setQueue((prev) => {
                    const merged = [...prev];
                    for (const sv of serverBatch.videos) {
                      const item = merged.find((it) => it.server_video_id === sv.id || it.id === sv.client_item_id);
                      if (item) {
                        item.processing_status = sv.processing_status;
                        item.processing_progress = sv.processing_progress;
                        item.processing_step = sv.processing_step;
                        item.processing_error = sv.processing_error;
                        item.upload_status = (sv.upload_status as any) || item.upload_status;
                      }
                    }
                    return merged;
                  });

                  // Load outputs if completed videos exist
                  if (serverBatch.status === 'completed' || (serverBatch.videos && serverBatch.videos.some((sv: any) => sv.processing_status === 'completed'))) {
                    getBatchOutputs(activeBatch).then((res) => setBatchOutputs(res.outputs || [])).catch(() => {});
                  }
                }
              })
              .catch((e) => console.warn('[UploadStudio] Could not sync batch state on mount:', e));
          }
        }
      })
      .catch((err) => {
        console.error('[UploadStudio] Failed to load staged queue from IndexedDB:', err);
        if (isMounted) {
          setIsLoading(false);
          setStorageSyncStatus('memory_only_error');
          setStorageErrorMessage(err?.message || 'Failed to open local storage');
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Refs to ensure window harness always accesses latest state even right after reload
  const queueRef = useRef(queue);
  queueRef.current = queue;
  const storageSyncStatusRef = useRef(storageSyncStatus);
  storageSyncStatusRef.current = storageSyncStatus;
  const storageErrorMessageRef = useRef(storageErrorMessage);
  storageErrorMessageRef.current = storageErrorMessage;
  const isUploadingBatchRef = useRef(isUploadingBatch);
  isUploadingBatchRef.current = isUploadingBatch;
  const currentBatchIdRef = useRef(currentBatchId);
  currentBatchIdRef.current = currentBatchId;
  const isProcessingBatchRef = useRef(isProcessingBatch);
  isProcessingBatchRef.current = isProcessingBatch;
  const batchProcessingStatusRef = useRef(batchProcessingStatus);
  batchProcessingStatusRef.current = batchProcessingStatus;
  const activeProcessingVideoIdRef = useRef(activeProcessingVideoId);
  activeProcessingVideoIdRef.current = activeProcessingVideoId;

  // Expose diagnostic harness for automated test execution immediately
  if (typeof window !== 'undefined') {
    (window as unknown as { __clipforgeStudio: unknown }).__clipforgeStudio = {
      getQueue: () => (queueRef.current !== undefined ? queueRef.current : []),
      getStorageSyncStatus: () => storageSyncStatusRef.current,
      getStorageErrorMessage: () => storageErrorMessageRef.current,
      setStorageSimulationMode,
      getStorageSimulationMode,
      saveStagedQueue,
      loadStagedQueue,
      reattachFileBlob,
      clearStagedQueue,
      handleUploadBatch: () => handleUploadBatch(),
      handleClearQueue: () => handleClearQueue(),
      deleteBatch: async () => {
        if (currentBatchIdRef.current) {
          await deleteStudioBatch(currentBatchIdRef.current);
          currentBatchIdRef.current = null;
          await clearStagedQueue();
          setQueue([]);
        }
      },
      getIsUploadingBatch: () => isUploadingBatchRef.current,
      getCurrentBatchId: () => currentBatchIdRef.current,
      getIsProcessingBatch: () => isProcessingBatchRef.current,
      getBatchProcessingStatus: () => batchProcessingStatusRef.current,
      getActiveProcessingVideoId: () => activeProcessingVideoIdRef.current,
      handleProcessBatch: () => handleProcessBatch(),
      handleCancelBatchProcessing: () => handleCancelBatchProcessing(),
      handleRetryVideo: (id: string) => handleRetryVideo(id),
    };
  }

  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as unknown as { __clipforgeStudio: unknown }).__clipforgeStudio = {
        getQueue: () => (queueRef.current !== undefined ? queueRef.current : []),
        getStorageSyncStatus: () => storageSyncStatusRef.current,
        getStorageErrorMessage: () => storageErrorMessageRef.current,
        setStorageSimulationMode,
        getStorageSimulationMode,
        saveStagedQueue,
        loadStagedQueue,
        reattachFileBlob,
        clearStagedQueue,
        handleUploadBatch: () => handleUploadBatch(),
        handleClearQueue: () => handleClearQueue(),
        deleteBatch: async () => {
          if (currentBatchIdRef.current) {
            await deleteStudioBatch(currentBatchIdRef.current);
            currentBatchIdRef.current = null;
            await clearStagedQueue();
            setQueue([]);
          }
        },
        getIsUploadingBatch: () => isUploadingBatchRef.current,
        getCurrentBatchId: () => currentBatchIdRef.current,
        getIsProcessingBatch: () => isProcessingBatchRef.current,
        getBatchProcessingStatus: () => batchProcessingStatusRef.current,
        getActiveProcessingVideoId: () => activeProcessingVideoIdRef.current,
        handleProcessBatch: () => handleProcessBatch(),
        handleCancelBatchProcessing: () => handleCancelBatchProcessing(),
        handleRetryVideo: (id: string) => handleRetryVideo(id),
      };
    }
  }, [queue, storageSyncStatus, storageErrorMessage, isUploadingBatch, currentBatchId, isProcessingBatch, batchProcessingStatus, activeProcessingVideoId]);

  // Sync state mutations to IndexedDB
  const syncQueueToStorage = useCallback(async (newQueue: StagedVideoItem[]) => {
    setQueue(newQueue);
    setStorageSyncStatus('saving');
    try {
      await saveStagedQueue(newQueue);
      setStorageSyncStatus('synced');
      setStorageErrorMessage(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('[UploadStudio] Error saving queue to IndexedDB:', err);
      setStorageSyncStatus('memory_only_error');
      setStorageErrorMessage(msg || 'Storage write failed');
    }
  }, []);

  // Probe real video duration and resolution using hidden media element
  const probeVideoMetadata = (file: File): Promise<{ duration: number | null; resolution: string | null }> => {
    return new Promise((resolve) => {
      try {
        const video = document.createElement('video');
        video.preload = 'metadata';
        const objectUrl = URL.createObjectURL(file);
        video.src = objectUrl;

        video.onloadedmetadata = () => {
          URL.revokeObjectURL(objectUrl);
          const duration = video.duration && !isNaN(video.duration) ? video.duration : null;
          const resolution = video.videoWidth && video.videoHeight ? `${video.videoWidth}x${video.videoHeight}` : null;
          resolve({ duration, resolution });
        };

        video.onerror = () => {
          URL.revokeObjectURL(objectUrl);
          resolve({ duration: null, resolution: null });
        };

        // Timeout fallback after 3 seconds
        setTimeout(() => {
          URL.revokeObjectURL(objectUrl);
          resolve({ duration: null, resolution: null });
        }, 3000);
      } catch {
        resolve({ duration: null, resolution: null });
      }
    });
  };

  // Handle files selected via main file input or dropzone
  const handleFilesAdded = async (files: FileList | File[]) => {
    const rawFiles = Array.from(files);
    if (rawFiles.length === 0) return;

    // Check for 0-byte or corrupted unreadable files
    const emptyFiles = rawFiles.filter((f) => f.size === 0);
    if (emptyFiles.length > 0) {
      setFileSelectionError(`Unreadable file: '${emptyFiles.map((f) => f.name).join(', ')}' is 0 bytes (empty file) and cannot be decoded.`);
      return;
    }

    // Check for unsupported file formats
    const validExtensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm'];
    const unsupportedFiles = rawFiles.filter(
      (file) => !validExtensions.some((ext) => file.name.toLowerCase().endsWith(ext))
    );

    if (unsupportedFiles.length > 0) {
      setFileSelectionError(
        `Unsupported file format: '${unsupportedFiles.map((f) => f.name).join(', ')}'. Upload Studio only accepts video files (.mp4, .mov, .avi, .mkv, .webm).`
      );
      return;
    }

    // Clear any previous file selection errors
    setFileSelectionError(null);

    const validFiles = rawFiles.filter((file) =>
      validExtensions.some((ext) => file.name.toLowerCase().endsWith(ext))
    );

    const newItems: StagedVideoItem[] = [];
    const startIndex = queue.length;

    for (let i = 0; i < validFiles.length; i++) {
      const file = validFiles[i];
      const { duration, resolution } = await probeVideoMetadata(file);

      newItems.push({
        id: `vid_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
        queue_position: startIndex + i, // Strictly zero-indexed: 0..N-1
        metadata: {
          file_name: file.name,
          file_size: file.size,
          mime_type: file.type || 'video/mp4',
          last_modified: file.lastModified,
          duration,
          resolution,
        },
        media_availability: 'available',
        upload_status: 'staged',
        file_blob: file,
      });
    }

    const updatedQueue = [...queue, ...newItems].map((item, idx) => ({
      ...item,
      queue_position: idx, // Strictly contiguous 0..N-1
    }));

    await syncQueueToStorage(updatedQueue);
    setAnnouncement(`Added ${newItems.length} videos to queue. Total: ${updatedQueue.length}.`);
  };

  // Reordering: Drag and Drop Handlers
  const handleDragStart = (e: React.DragEvent, id: string) => {
    setDraggedItemId(id);
    e.dataTransfer.setData('text/plain', id);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, id: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (dragOverItemId !== id) {
      setDragOverItemId(id);
    }
  };

  const handleDrop = async (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    setDragOverItemId(null);
    const sourceId = draggedItemId || e.dataTransfer.getData('text/plain');
    setDraggedItemId(null);

    if (!sourceId || sourceId === targetId) return;

    const sourceIndex = queue.findIndex((item) => item.id === sourceId);
    const targetIndex = queue.findIndex((item) => item.id === targetId);
    if (sourceIndex === -1 || targetIndex === -1) return;

    const reordered = [...queue];
    const [movedItem] = reordered.splice(sourceIndex, 1);
    reordered.splice(targetIndex, 0, movedItem);

    // Contiguous re-indexing strictly 0..N-1
    const normalized = reordered.map((item, idx) => ({ ...item, queue_position: idx }));
    await syncQueueToStorage(normalized);
    setAnnouncement(`Moved ${movedItem.metadata.file_name} to position #${targetIndex + 1}.`);
  };

  // Accessible Keyboard Reordering
  const moveItem = async (index: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= queue.length) return;

    const reordered = [...queue];
    const [movedItem] = reordered.splice(index, 1);
    reordered.splice(targetIndex, 0, movedItem);

    const normalized = reordered.map((item, idx) => ({ ...item, queue_position: idx }));
    await syncQueueToStorage(normalized);
    setAnnouncement(`Moved ${movedItem.metadata.file_name} ${direction} to position #${targetIndex + 1}.`);
  };

  // Trigger file re-selection for evicted or missing items
  const triggerReselect = (id: string) => {
    setReselectTargetId(id);
    setReselectError(null);
    reselectInputRef.current?.click();
  };

  // Handle re-selected file binding with identity policy enforcement
  const handleReselectedFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    const targetId = reselectTargetId;
    e.target.value = '';
    setReselectTargetId(null);

    if (!file || !targetId) return;

    try {
      const probeMeta = await probeVideoMetadata(file);
      const updatedQueue = await reattachFileBlob(targetId, file, { probeMeta });
      setQueue(updatedQueue);
      setReselectError(null);
      setStorageSyncStatus('synced');
      setAnnouncement(`Successfully reselected ${file.name}. Item is now upload-ready.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('[UploadStudio] Reselection failed:', err);
      setReselectError(msg || 'Reselection failed: Identity policy or format validation error.');
      setAnnouncement(`Reselection rejected: ${msg}`);
    }
  };

  // Remove single item with contiguous gap compaction
  const handleRemoveItem = async (id: string) => {
    const itemToRemove = queue.find((item) => item.id === id);
    const updated = await removeStagedVideo(id);
    setQueue(updated);
    if (itemToRemove) {
      setAnnouncement(`Removed ${itemToRemove.metadata.file_name} from queue.`);
    }
  };

  // Clear entire queue
  const handleClearQueue = async () => {
    if (confirm('Clear all staged videos from the local queue?')) {
      if (currentBatchId) {
        try {
          await deleteStudioBatch(currentBatchId);
        } catch (err) {
          console.error('[UploadStudio] Failed to delete batch on server:', err);
        }
      }
      await clearStagedQueue();
      setQueue([]);
      setCurrentBatchId(null);
      setAnnouncement('Queue cleared.');
    }
  };

  // Upload Batch Handler
  const handleUploadBatch = async () => {
    if (!isBatchReady || queue.length === 0 || isUploadingBatch || uploadingRef.current) return;

    uploadingRef.current = true;
    setIsUploadingBatch(true);
    setUploadBatchError(null);
    setAnnouncement('Starting batch upload...');

    try {
      let idempotencyKey = typeof window !== 'undefined' ? localStorage.getItem('cf_studio_batch_idempotency_key') : null;
      if (!idempotencyKey) {
        idempotencyKey = 'cf_batch_' + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
        if (typeof window !== 'undefined') {
          localStorage.setItem('cf_studio_batch_idempotency_key', idempotencyKey);
        }
      }

      const batch = await createStudioBatch(idempotencyKey, `Studio Batch (${queue.length} files)`);
      setCurrentBatchId(batch.id);

      const updatedQueue = [...queue];
      for (let i = 0; i < updatedQueue.length; i++) {
        const item = updatedQueue[i];
        if (!item.server_video_id) {
          const initRes = await initStudioVideo(batch.id, {
            client_item_id: item.id,
            source_filename: item.metadata.file_name,
            file_size: item.metadata.file_size,
            resolution: item.metadata.resolution,
            duration: item.metadata.duration,
          });
          item.server_video_id = initRes.id;
          item.batch_id = batch.id;
          item.upload_status = 'queued';
        }
      }
      await syncQueueToStorage(updatedQueue);

      const queueToUpload = [...updatedQueue];

      // Sequential streaming per item prevents client concurrency collisions
      for (let i = 0; i < queueToUpload.length; i++) {
        const item = queueToUpload[i];
        if (!item || !item.file_blob || !item.server_video_id) continue;
        if (item.upload_status === 'uploaded') continue;

        item.upload_status = 'uploading';
        setQueue([...queueToUpload]);

        try {
          await streamFileInChunks(item.server_video_id, item.file_blob, (uploaded) => {
            item.uploaded_bytes = uploaded;
            setQueue([...queueToUpload]);
          });
          item.upload_status = 'uploaded';
          item.uploaded_bytes = item.metadata.file_size;
        } catch (err: unknown) {
          console.error(`Upload failed for ${item.metadata.file_name}:`, err);
          item.upload_status = 'failed';
          item.error_message = err instanceof Error ? err.message : String(err);
        }
        await syncQueueToStorage([...queueToUpload]);
      }

      const allSucceeded = queueToUpload.every((item) => item.upload_status === 'uploaded');
      if (allSucceeded) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('cf_studio_batch_idempotency_key');
        }
        setAnnouncement('All videos in batch successfully uploaded!');
      } else {
        setUploadBatchError('Some videos failed to upload. You can retry them.');
      }
    } catch (err: unknown) {
      console.error('Batch upload error:', err);
      setUploadBatchError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsUploadingBatch(false);
      uploadingRef.current = false;
    }
  };

  // Sequential Batch Processing Handlers (Phase 2)
  const handleProcessBatch = async () => {
    if (!currentBatchId) {
      setShowProcessModal(true);
      return;
    }
    const allUploaded = queue.length > 0 && queue.every((it) => it.upload_status === 'uploaded');
    if (!allUploaded) {
      setShowProcessModal(true);
      return;
    }

    setIsProcessingBatch(true);
    setBatchProcessingError(null);
    setAnnouncement('Starting sequential batch processing...');

    try {
      const res = await processStudioBatch(currentBatchId);
      setBatchProcessingStatus(res.status);
      setActiveProcessingVideoId(res.active_video_id || null);
      setAnnouncement('Batch processing started in preserved queue order.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('[UploadStudio] Failed to start batch processing:', err);
      setBatchProcessingError(msg);
      setIsProcessingBatch(false);
    }
  };

  const handleCancelBatchProcessing = async () => {
    if (!currentBatchId) return;
    try {
      setAnnouncement('Cancelling batch processing...');
      const res = await cancelStudioBatch(currentBatchId);
      setBatchProcessingStatus(res.status);
      if (res.status === 'cancelled') {
        setIsProcessingBatch(false);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('[UploadStudio] Failed to cancel batch processing:', err);
      setBatchProcessingError(msg);
    }
  };

  const handleRetryVideo = async (videoId: string) => {
    if (!currentBatchId) return;
    try {
      setAnnouncement('Retrying failed video...');
      await retryStudioVideo(currentBatchId, videoId);
      setIsProcessingBatch(true);
      setBatchProcessingStatus('processing');
      setBatchProcessingError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('[UploadStudio] Failed to retry video:', err);
      setBatchProcessingError(msg);
    }
  };

  // Calculations
  const totalBytes = queue.reduce((sum, item) => sum + (item.metadata?.file_size || 0), 0);
  const readyCount = queue.filter((item) => item.media_availability === 'available').length;
  const missingCount = queue.length - readyCount;
  const isBatchReady = queue.length > 0 && missingCount === 0;
  const allUploaded = queue.length > 0 && queue.every((item) => item.upload_status === 'uploaded');

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 24px', color: '#f8fafc' }}>
      {/* Screen Reader Live Region */}
      <div aria-live="polite" aria-atomic="true" className="sr-only" style={{ position: 'absolute', left: -9999, width: 1, height: 1, overflow: 'hidden' }}>
        {announcement}
      </div>

      {/* Hidden input for reselection */}
      <input
        type="file"
        ref={reselectInputRef}
        data-testid="reselect-file-input"
        accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm"
        style={{ display: 'none' }}
        onChange={handleReselectedFileChange}
      />

      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <span style={{ fontSize: 28 }}>🎞️</span>
          <h1 style={{ fontSize: 28, fontWeight: 800, margin: 0, fontFamily: "'Space Grotesk', sans-serif", letterSpacing: '-0.02em' }}>
            Upload Studio
          </h1>
          <span style={{ 
            fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 6,
            background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)', color: '#818cf8',
            letterSpacing: '0.05em', textTransform: 'uppercase'
          }}>
            Local Staging (v1.9 Preview)
          </span>
        </div>
        <p style={{ margin: 0, color: '#94a3b8', fontSize: 14 }}>
          Stage multiple video files, configure intentional creative ordering via drag-and-drop, and inspect real media metadata.
        </p>
      </div>

      {/* Critical Status Banner — MANDATORY HONEST REPORTING */}
      <div 
        data-testid="honest-deployment-banner"
        style={{
          marginBottom: 20,
          padding: '16px 20px',
          borderRadius: 12,
          background: backendStatus === 'connected'
            ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.08) 100%)'
            : 'linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(217, 119, 6, 0.08) 100%)',
          border: backendStatus === 'connected'
            ? '1px solid rgba(16, 185, 129, 0.35)'
            : '1px solid rgba(245, 158, 11, 0.35)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 14
        }}
      >
        <span style={{ fontSize: 24, lineHeight: 1 }}>{backendStatus === 'connected' ? '✅' : '⚠️'}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: backendStatus === 'connected' ? '#34d399' : '#fbbf24', marginBottom: 4 }}>
            {backendStatus === 'connected'
              ? 'Upload Studio Phase 1B backend connected. Resumable RFC 7233 chunk streaming and storage reservation active.'
              : 'Upload Studio batch backend is not deployed yet. Your queue is staged locally; videos have not been uploaded or processed.'}
          </div>
          <div style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.5 }}>
            {backendStatus === 'connected' ? (
              <span>
                FastAPI backend (<code style={{ background: 'rgba(0,0,0,0.3)', padding: '2px 5px', borderRadius: 4, color: '#a7f3d0' }}>/api/studio</code>) is online. Click &apos;Upload Batch&apos; to stream chunks directly to storage with single-writer fencing, FFprobe media validation, and storage reservation accounting.
              </span>
            ) : (
              <span>
                File selection, real media inspection, drag-and-drop reordering, and IndexedDB persistence across browser refreshes are fully functional. 
                Server-side RFC 7233 resumable chunk upload and sequential automated Celery processing will activate once backend Phase 4 (<code style={{ background: 'rgba(0,0,0,0.3)', padding: '2px 5px', borderRadius: 4, color: '#fef08a' }}>/api/studio</code>) is deployed.
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Memory-Only State Warning Banner (Test 5 requirement) */}
      {storageSyncStatus === 'memory_only_error' && (
        <div 
          data-testid="memory-only-banner"
          style={{
            marginBottom: 20,
            padding: '14px 18px',
            borderRadius: 12,
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            color: '#fca5a5',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}>
            <span style={{ fontSize: 18 }}>🚨</span>
            <div>
              <strong style={{ color: '#ef4444' }}>Memory-Only State:</strong> Storage write failed ({storageErrorMessage || 'quota or write failure'}). 
              Your staged queue is currently held in memory only and will not survive a browser refresh.
            </div>
          </div>
          <button
            type="button"
            onClick={() => syncQueueToStorage([...queue])}
            style={{
              padding: '6px 12px',
              borderRadius: 6,
              background: 'rgba(239, 68, 68, 0.2)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#fff',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Retry Save
          </button>
        </div>
      )}

      {/* File Selection Error Banner (Test 1 requirement) */}
      {fileSelectionError && (
        <div 
          data-testid="file-selection-error-banner"
          style={{
            marginBottom: 20,
            padding: '12px 16px',
            borderRadius: 10,
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#fca5a5',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            fontSize: 13
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>🛑</span>
            <span>{fileSelectionError}</span>
          </div>
          <button
            type="button"
            onClick={() => setFileSelectionError(null)}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#fca5a5',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: 14
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Reselection Error Banner (Test 4 requirement) */}
      {reselectError && (
        <div 
          data-testid="reselect-error-banner"
          style={{
            marginBottom: 20,
            padding: '12px 16px',
            borderRadius: 10,
            background: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.3)',
            color: '#fef08a',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            fontSize: 13
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>⚠️</span>
            <span>{reselectError}</span>
          </div>
          <button
            type="button"
            onClick={() => setReselectError(null)}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#fef08a',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: 14
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Dropzone Area */}
      <div
        data-testid="studio-dropzone"
        onDragOver={(e) => {
          e.preventDefault();
          setIsDraggingOver(true);
        }}
        onDragLeave={() => setIsDraggingOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDraggingOver(false);
          if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFilesAdded(e.dataTransfer.files);
          }
        }}
        style={{
          border: isDraggingOver ? '2px dashed #6366f1' : '2px dashed rgba(255, 255, 255, 0.15)',
          background: isDraggingOver ? 'rgba(99, 102, 241, 0.08)' : 'rgba(255, 255, 255, 0.02)',
          borderRadius: 16,
          padding: '40px 24px',
          textAlign: 'center',
          transition: 'all 0.2s ease',
          marginBottom: 32,
          cursor: 'pointer'
        }}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          type="file"
          ref={fileInputRef}
          data-testid="studio-file-input"
          multiple
          accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm"
          style={{ display: 'none' }}
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              handleFilesAdded(e.target.files);
            }
          }}
        />

        <div style={{ width: 48, height: 48, borderRadius: 12, background: 'rgba(99,102,241,0.15)', color: '#818cf8', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, margin: '0 auto 16px' }}>
          📤
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9', marginBottom: 6 }}>
          Drag & Drop Video Files Here or Click to Browse
        </div>
        <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 16 }}>
          Supports MP4, MOV, MKV, WEBM, AVI up to 2.0 GB per video. Select multiple files at once.
        </div>
        <button
          type="button"
          style={{
            padding: '9px 18px',
            borderRadius: 8,
            background: 'rgba(255, 255, 255, 0.08)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            color: '#f8fafc',
            fontWeight: 600,
            fontSize: 13,
            cursor: 'pointer',
            transition: 'background 0.2s'
          }}
          onClick={(e) => {
            e.stopPropagation();
            fileInputRef.current?.click();
          }}
        >
          Select Video Files
        </button>
      </div>

      {/* Queue Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, fontFamily: "'Space Grotesk', sans-serif" }}>
            Staged Queue ({queue.length})
          </h2>
          {queue.length > 0 && (
            <span style={{ fontSize: 13, color: '#94a3b8' }}>
              Total Volume: <strong style={{ color: '#cbd5e1' }}>{formatBytes(totalBytes)}</strong>
            </span>
          )}

          {/* Storage Sync Badge */}
          {storageSyncStatus === 'synced' && queue.length > 0 && (
            <span 
              data-testid="storage-persisted-badge"
              style={{
                fontSize: 11,
                fontWeight: 600,
                padding: '2px 8px',
                borderRadius: 6,
                background: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                color: '#34d399'
              }}
            >
              💾 Persisted in Storage
            </span>
          )}

          {storageSyncStatus === 'memory_only_error' && (
            <span 
              data-testid="storage-unpersisted-badge"
              style={{
                fontSize: 11,
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 6,
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                color: '#f87171'
              }}
            >
              ⚠️ Unpersisted (Memory Only)
            </span>
          )}

          {/* Readiness Indicator */}
          {missingCount > 0 ? (
            <span 
              data-testid="queue-missing-badge"
              style={{
                fontSize: 12,
                fontWeight: 600,
                padding: '2px 8px',
                borderRadius: 6,
                background: 'rgba(245, 158, 11, 0.15)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                color: '#fbbf24'
              }}
            >
              ⚠️ {missingCount} item{missingCount > 1 ? 's' : ''} require{missingCount === 1 ? 's' : ''} reselection
            </span>
          ) : queue.length > 0 ? (
            <span 
              data-testid="queue-ready-badge"
              style={{
                fontSize: 12,
                fontWeight: 600,
                padding: '2px 8px',
                borderRadius: 6,
                background: 'rgba(16, 185, 129, 0.12)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                color: '#34d399'
              }}
            >
              ✓ All {queue.length} files staged & ready
            </span>
          ) : null}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {queue.length > 0 && (
            <button
              type="button"
              data-testid="clear-queue-button"
              onClick={handleClearQueue}
              style={{
                padding: '7px 14px',
                borderRadius: 8,
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                color: '#f87171',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Clear Queue
            </button>
          )}

          {/* Upload Batch Button */}
          {queue.length > 0 && (
            <button
              type="button"
              data-testid="upload-batch-button"
              disabled={isUploadingBatch || !isBatchReady}
              onClick={handleUploadBatch}
              style={{
                padding: '9px 18px',
                borderRadius: 8,
                background: (isBatchReady && !isUploadingBatch) ? 'linear-gradient(135deg, #2563eb, #4f46e5)' : 'rgba(255,255,255,0.05)',
                border: 'none',
                color: (isBatchReady && !isUploadingBatch) ? '#fff' : '#64748b',
                fontSize: 13,
                fontWeight: 700,
                cursor: (isBatchReady && !isUploadingBatch) ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <span>{isUploadingBatch ? '⏳' : '☁️'}</span>
              <span>{isUploadingBatch ? 'Uploading...' : 'Upload Batch'}</span>
            </button>
          )}

          {/* Delete Batch Button (Server Batch) */}
          {currentBatchId && (
            <button
              type="button"
              data-testid="delete-batch-button"
              disabled={isUploadingBatch || isProcessingBatch || batchProcessingStatus === 'processing'}
              onClick={async () => {
                if (currentBatchId) {
                  try {
                    await deleteStudioBatch(currentBatchId);
                    setCurrentBatchId(null);
                    await clearStagedQueue();
                    setQueue([]);
                    setAnnouncement('Batch deleted from server and local queue cleared.');
                  } catch (err) {
                    console.error('[UploadStudio] Failed to delete batch:', err);
                  }
                }
              }}
              style={{
                padding: '9px 16px',
                borderRadius: 8,
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#f87171',
                fontSize: 13,
                fontWeight: 600,
                cursor: (isUploadingBatch || isProcessingBatch || batchProcessingStatus === 'processing') ? 'not-allowed' : 'pointer',
                opacity: (isUploadingBatch || isProcessingBatch || batchProcessingStatus === 'processing') ? 0.5 : 1,
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <span>🗑️</span>
              <span>Delete Batch</span>
            </button>
          )}

          {/* Cancel Processing Button (Phase 2) */}
          {(isProcessingBatch || batchProcessingStatus === 'processing' || batchProcessingStatus === 'cancelling') && (
            <button
              type="button"
              data-testid="cancel-batch-button"
              disabled={batchProcessingStatus === 'cancelling'}
              onClick={handleCancelBatchProcessing}
              style={{
                padding: '9px 16px',
                borderRadius: 8,
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#f87171',
                fontSize: 13,
                fontWeight: 600,
                cursor: batchProcessingStatus === 'cancelling' ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <span>⏹</span>
              <span>{batchProcessingStatus === 'cancelling' ? 'Cancelling...' : 'Cancel Processing'}</span>
            </button>
          )}

          <button
            type="button"
            data-testid="process-batch-button"
            disabled={!isBatchReady || isProcessingBatch || batchProcessingStatus === 'processing' || batchProcessingStatus === 'cancelling'}
            onClick={() => {
              if (allUploaded && currentBatchId) {
                handleProcessBatch();
              } else {
                setShowProcessModal(true);
              }
            }}
            title={
              queue.length === 0 
                ? 'Queue is empty' 
                : missingCount > 0 
                  ? `${missingCount} item(s) require file reselection before batch processing can begin.` 
                  : !allUploaded
                    ? 'Videos must be uploaded to server before batch processing can begin.'
                    : 'Process batch in sequential queue order'
            }
            style={{
              padding: '9px 20px',
              borderRadius: 8,
              background: (isBatchReady && !isProcessingBatch) ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'rgba(255,255,255,0.05)',
              border: 'none',
              color: (isBatchReady && !isProcessingBatch) ? '#fff' : '#64748b',
              fontSize: 14,
              fontWeight: 700,
              cursor: (isBatchReady && !isProcessingBatch) ? 'pointer' : 'not-allowed',
              boxShadow: (isBatchReady && !isProcessingBatch) ? '0 4px 12px rgba(99, 102, 241, 0.3)' : 'none',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              opacity: (isBatchReady && !isProcessingBatch) ? 1 : 0.6
            }}
          >
            <span>▶</span>
            <span>
              {isProcessingBatch || batchProcessingStatus === 'processing'
                ? `Processing Batch (${queue.filter((q) => q.processing_status === 'completed').length}/${queue.length})...`
                : 'Process Batch in Order'}
            </span>
          </button>
        </div>
      </div>

      {/* Queue List */}
      {isLoading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>
          Loading staged queue from IndexedDB...
        </div>
      ) : queue.length === 0 ? (
        <div 
          data-testid="empty-queue-message"
          style={{
            padding: '48px 24px',
            textAlign: 'center',
            borderRadius: 12,
            background: 'rgba(255, 255, 255, 0.015)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            color: '#64748b'
          }}
        >
          <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
          <div style={{ fontWeight: 600, fontSize: 15, color: '#94a3b8', marginBottom: 4 }}>No Videos in Queue</div>
          <div style={{ fontSize: 13 }}>Drop video files above to build your sequential processing queue.</div>
        </div>
      ) : (
        <div data-testid="staged-video-list" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {queue.map((item, index) => {
            const isDraggingThis = draggedItemId === item.id;
            const isOverThis = dragOverItemId === item.id;
            const isAvailable = item.media_availability === 'available';
            const isEvicted = item.media_availability === 'quota_exceeded_evicted';

            return (
              <div
                key={item.id}
                data-testid={`staged-item-${item.id}`}
                data-position={item.queue_position}
                data-availability={item.media_availability}
                draggable
                onDragStart={(e) => handleDragStart(e, item.id)}
                onDragOver={(e) => handleDragOver(e, item.id)}
                onDrop={(e) => handleDrop(e, item.id)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                  padding: '12px 16px',
                  borderRadius: 12,
                  background: isOverThis ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                  border: isOverThis 
                    ? '1px solid #6366f1' 
                    : !isAvailable 
                      ? '1px solid rgba(245, 158, 11, 0.35)' 
                      : '1px solid rgba(255, 255, 255, 0.07)',
                  opacity: isDraggingThis ? 0.4 : 1,
                  transition: 'all 0.15s ease',
                  cursor: 'grab'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  {/* Drag Handle & 1-Indexed Display Position (Internal: item.queue_position 0..N-1) */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div
                      title="Drag to reorder"
                      style={{
                        cursor: 'grab',
                        color: '#64748b',
                        fontSize: 16,
                        userSelect: 'none',
                        padding: '4px'
                      }}
                    >
                      ⋮⋮
                    </div>
                    <div 
                      data-testid={`item-display-number-${item.id}`}
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: 6,
                        background: 'rgba(99, 102, 241, 0.12)',
                        border: '1px solid rgba(99, 102, 241, 0.25)',
                        color: '#818cf8',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 12,
                        fontWeight: 700,
                        fontFamily: "'Space Grotesk', monospace"
                      }}
                    >
                      #{index + 1}
                    </div>
                  </div>

                  {/* File Metadata */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 14 }}>📹</span>
                      <span 
                        data-testid={`item-filename-${item.id}`}
                        style={{ 
                          fontWeight: 600, 
                          fontSize: 14, 
                          color: isAvailable ? '#f1f5f9' : '#fbbf24', 
                          overflow: 'hidden', 
                          textOverflow: 'ellipsis', 
                          whiteSpace: 'nowrap' 
                        }} 
                        title={item.metadata.file_name}
                      >
                        {item.metadata.file_name}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, color: '#94a3b8', flexWrap: 'wrap' }}>
                      <span data-testid={`item-filesize-${item.id}`}>{formatBytes(item.metadata.file_size)}</span>
                      {item.metadata.resolution && (
                        <span style={{ background: 'rgba(255,255,255,0.06)', padding: '1px 6px', borderRadius: 4, color: '#cbd5e1' }}>
                          {item.metadata.resolution}
                        </span>
                      )}
                      {item.metadata.duration && (
                        <span>⏱️ {formatDuration(item.metadata.duration)}</span>
                      )}
                    </div>
                  </div>

                  {/* Media Availability Badge */}
                  <div>
                    {isAvailable ? (
                      <span 
                        data-testid={`item-availability-badge-${item.id}`}
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          padding: '4px 10px',
                          borderRadius: 6,
                          background: 'rgba(16, 185, 129, 0.12)',
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          color: '#34d399',
                          letterSpacing: '0.03em'
                        }}
                      >
                        Staged (Ready)
                      </span>
                    ) : isEvicted ? (
                      <span 
                        data-testid={`item-availability-badge-${item.id}`}
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          padding: '4px 10px',
                          borderRadius: 6,
                          background: 'rgba(239, 68, 68, 0.12)',
                          border: '1px solid rgba(239, 68, 68, 0.3)',
                          color: '#f87171',
                          letterSpacing: '0.03em'
                        }}
                      >
                        Evicted (Quota Exceeded)
                      </span>
                    ) : (
                      <span 
                        data-testid={`item-availability-badge-${item.id}`}
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          padding: '4px 10px',
                          borderRadius: 6,
                          background: 'rgba(245, 158, 11, 0.12)',
                          border: '1px solid rgba(245, 158, 11, 0.3)',
                          color: '#fbbf24',
                          letterSpacing: '0.03em'
                        }}
                      >
                        File Unavailable
                      </span>
                    )}
                  </div>

                  {/* Accessible Reorder Controls */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <button
                      type="button"
                      disabled={index === 0}
                      onClick={() => moveItem(index, 'up')}
                      data-testid={`item-move-up-${item.id}`}
                      aria-label={`Move ${item.metadata.file_name} up in queue`}
                      style={{
                        background: 'rgba(255,255,255,0.05)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        color: index === 0 ? '#475569' : '#cbd5e1',
                        borderRadius: 4,
                        padding: '4px 8px',
                        cursor: index === 0 ? 'not-allowed' : 'pointer',
                        fontSize: 11
                      }}
                    >
                      ▲
                    </button>
                    <button
                      type="button"
                      disabled={index === queue.length - 1}
                      onClick={() => moveItem(index, 'down')}
                      data-testid={`item-move-down-${item.id}`}
                      aria-label={`Move ${item.metadata.file_name} down in queue`}
                      style={{
                        background: 'rgba(255,255,255,0.05)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        color: index === queue.length - 1 ? '#475569' : '#cbd5e1',
                        borderRadius: 4,
                        padding: '4px 8px',
                        cursor: index === queue.length - 1 ? 'not-allowed' : 'pointer',
                        fontSize: 11
                      }}
                    >
                      ▼
                    </button>
                  </div>

                  {/* Remove Button */}
                  <button
                    type="button"
                    onClick={() => handleRemoveItem(item.id)}
                    data-testid={`item-remove-${item.id}`}
                    aria-label={`Remove ${item.metadata.file_name} from queue`}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#64748b',
                      cursor: 'pointer',
                      fontSize: 16,
                      padding: '6px',
                      borderRadius: 4,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'color 0.2s'
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#ef4444')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#64748b')}
                  >
                    ✕
                  </button>
                </div>

                {/* In-Flight Upload Progress Bar */}
                {item.upload_status === 'uploading' && (
                  <div style={{ marginTop: 4, marginBottom: 4 }} data-testid={`item-upload-progress-${item.id}`}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                      <span style={{ color: '#818cf8' }}>Uploading chunks to server...</span>
                      <span>
                        {formatBytes(item.uploaded_bytes || 0)} / {formatBytes(item.metadata.file_size)} ({Math.round(((item.uploaded_bytes || 0) / (item.metadata.file_size || 1)) * 100)}%)
                      </span>
                    </div>
                    <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
                      <div 
                        style={{ 
                          height: '100%', 
                          width: `${Math.min(100, Math.round(((item.uploaded_bytes || 0) / (item.metadata.file_size || 1)) * 100))}%`, 
                          background: 'linear-gradient(90deg, #6366f1, #38bdf8)', 
                          transition: 'width 0.2s' 
                        }} 
                      />
                    </div>
                  </div>
                )}
                {item.upload_status === 'uploaded' && (
                  <div style={{ fontSize: 11, color: '#34d399', fontWeight: 600, marginTop: 2 }}>
                    ✓ Upload committed & media verified on server
                  </div>
                )}

                {/* Per-Video Sequential Processing Indicators (Phase 2) */}
                {item.processing_status === 'processing' && (
                  <div style={{ marginTop: 6, marginBottom: 4 }} data-testid={`item-processing-progress-${item.id}`}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                      <span style={{ color: '#a78bfa', fontWeight: 600 }}>
                        ⚙️ Processing ({item.processing_step || 'in pipeline'}): {item.processing_progress ?? 0}%
                      </span>
                      <span>{item.processing_progress ?? 0}%</span>
                    </div>
                    <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
                      <div 
                        style={{ 
                          height: '100%', 
                          width: `${Math.min(100, Math.max(0, item.processing_progress ?? 0))}%`, 
                          background: 'linear-gradient(90deg, #8b5cf6, #ec4899)', 
                          transition: 'width 0.3s ease' 
                        }} 
                      />
                    </div>
                  </div>
                )}

                {item.processing_status === 'completed' && (
                  <div 
                    data-testid={`item-processing-completed-badge-${item.id}`}
                    style={{ fontSize: 11, color: '#34d399', fontWeight: 600, marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}
                  >
                    <span>✓</span>
                    <span>Processing completed — clips generated</span>
                  </div>
                )}

                {item.processing_status === 'queued' && (
                  <div style={{ fontSize: 11, color: '#93c5fd', fontWeight: 600, marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>⏳</span>
                    <span>Queued for sequential processing</span>
                  </div>
                )}

                {item.processing_status === 'failed' && (
                  <div 
                    data-testid={`item-processing-failed-badge-${item.id}`}
                    style={{ 
                      marginTop: 6, 
                      padding: '8px 12px', 
                      borderRadius: 8, 
                      background: 'rgba(239, 68, 68, 0.1)', 
                      border: '1px solid rgba(239, 68, 68, 0.25)', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between', 
                      gap: 8 
                    }}
                  >
                    <div style={{ fontSize: 12, color: '#f87171' }}>
                      <strong>Processing failed:</strong> {item.processing_error || 'Internal pipeline error'}
                    </div>
                    <button
                      type="button"
                      data-testid={`item-retry-button-${item.id}`}
                      onClick={() => handleRetryVideo(item.server_video_id || item.id)}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 6,
                        background: 'rgba(239, 68, 68, 0.2)',
                        border: '1px solid rgba(239, 68, 68, 0.4)',
                        color: '#fca5a5',
                        fontSize: 11,
                        fontWeight: 600,
                        cursor: 'pointer',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      🔄 Retry
                    </button>
                  </div>
                )}

                {item.processing_status === 'cancelled' && (
                  <div style={{ fontSize: 11, color: '#94a3b8', fontStyle: 'italic', marginTop: 4 }}>
                    Processing cancelled
                  </div>
                )}

                {/* Storage Warning & Reselection Workflow */}
                {!isAvailable && (
                  <div 
                    data-testid={`item-reselect-notice-${item.id}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                      padding: '8px 12px',
                      borderRadius: 8,
                      background: isEvicted ? 'rgba(239, 68, 68, 0.08)' : 'rgba(245, 158, 11, 0.08)',
                      border: isEvicted ? '1px solid rgba(239, 68, 68, 0.2)' : '1px solid rgba(245, 158, 11, 0.2)',
                      fontSize: 12,
                      color: isEvicted ? '#fca5a5' : '#fef08a'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>⚠️</span>
                      <span>
                        {item.storage_warning || 'Original file is unavailable in browser storage. Reselection required before batch upload.'}
                      </span>
                    </div>

                    <button
                      type="button"
                      data-testid={`reselect-button-${item.id}`}
                      onClick={() => triggerReselect(item.id)}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 6,
                        background: 'rgba(255, 255, 255, 0.1)',
                        border: '1px solid rgba(255, 255, 255, 0.2)',
                        color: '#fff',
                        fontWeight: 600,
                        fontSize: 11,
                        cursor: 'pointer',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      Reselect File
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Phase 3 Generated Clips & Publishing Review */}
      {batchOutputs.length > 0 && (
        <div data-testid="studio-outputs-section" style={{ marginTop: 40, marginBottom: 40 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <div>
              <h2 style={{ fontSize: 20, fontWeight: 800, color: '#f8fafc', margin: 0 }}>
                🎬 Generated Video Clips ({batchOutputs.length})
              </h2>
              <p style={{ fontSize: 13, color: '#94a3b8', margin: '4px 0 0' }}>
                Review generated shorts outputs, configure publishing metadata, and publish to YouTube.
              </p>
            </div>
            <Link
              href="/publish"
              style={{
                padding: '8px 16px',
                borderRadius: 8,
                background: 'rgba(99, 102, 241, 0.15)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                color: '#818cf8',
                fontSize: 13,
                fontWeight: 600,
                textDecoration: 'none'
              }}
            >
              Open Publish Studio →
            </Link>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
            {batchOutputs.map((clip) => (
              <div
                key={clip.id}
                data-testid={`studio-output-card-${clip.id}`}
                style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 12,
                  padding: 16,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1, marginRight: 8 }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', marginBottom: 4 }}>
                      {clip.title}
                    </div>
                    <div style={{ fontSize: 12, color: '#94a3b8' }}>
                      {clip.video_title} • {clip.duration.toFixed(1)}s
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: 6,
                      background: clip.publish_status === 'published' ? 'rgba(16, 185, 129, 0.15)' : clip.publish_status === 'manual_review' ? 'rgba(245, 158, 11, 0.15)' : clip.publish_status === 'failed' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(99, 102, 241, 0.15)',
                      color: clip.publish_status === 'published' ? '#34d399' : clip.publish_status === 'manual_review' ? '#fbbf24' : clip.publish_status === 'failed' ? '#f87171' : '#818cf8',
                      textTransform: 'capitalize'
                    }}
                  >
                    {clip.publish_status.replace('_', ' ')}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: '#94a3b8' }}>
                  <span>Score: <strong style={{ color: '#818cf8' }}>{(clip.score || 0).toFixed(1)} ★</strong></span>
                  {clip.publish_progress > 0 && clip.publish_status !== 'published' && (
                    <span>Progress: {clip.publish_progress}%</span>
                  )}
                </div>

                <div style={{ marginTop: 'auto', paddingTop: 8, display: 'flex', gap: 8 }}>
                  <Link
                    href={`/publish?clip=${clip.id}`}
                    style={{
                      flex: 1,
                      padding: '8px 12px',
                      borderRadius: 6,
                      background: '#4f46e5',
                      color: '#fff',
                      fontSize: 12,
                      fontWeight: 600,
                      textAlign: 'center',
                      textDecoration: 'none'
                    }}
                  >
                    {clip.publish_status === 'published' ? 'Review Metadata' : 'Configure & Publish 🚀'}
                  </Link>

                  {clip.youtube_url && (
                    <a
                      href={clip.youtube_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        padding: '8px 12px',
                        borderRadius: 6,
                        background: 'rgba(255, 255, 255, 0.08)',
                        color: '#f1f5f9',
                        fontSize: 12,
                        fontWeight: 600,
                        textDecoration: 'none'
                      }}
                    >
                      YouTube ↗
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Backend Implementation Status Modal */}
      {showProcessModal && (
        <div 
          data-testid="honest-process-modal"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 20
          }}
        >
          <div style={{
            background: '#131826',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 16,
            maxWidth: 540,
            width: '100%',
            padding: 24,
            boxShadow: '0 20px 40px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <span style={{ fontSize: 24 }}>🛑</span>
              <h3 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                Backend Implementation Required
              </h3>
            </div>

            <p style={{ fontSize: 14, color: '#94a3b8', lineHeight: 1.6, marginBottom: 16 }}>
              Batch upload to server is required before sequential automated processing can begin via <code style={{ color: '#818cf8', background: 'rgba(99,102,241,0.1)', padding: '2px 6px', borderRadius: 4 }}>/api/studio/batches/{'{id}'}/process</code>.
            </p>

            <div style={{ background: 'rgba(0,0,0,0.25)', borderRadius: 8, padding: '12px 14px', marginBottom: 20, fontSize: 13, color: '#cbd5e1', lineHeight: 1.5 }}>
              <div style={{ fontWeight: 600, color: '#e2e8f0', marginBottom: 6 }}>Current Status:</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                <li>Your staged video queue ({queue.length} files) is durably saved in <strong>IndexedDB</strong>.</li>
                <li>Refreshing or returning to this page preserves your exact zero-indexed queue order.</li>
                <li>Backend Implementation Required: Click &apos;Upload Batch&apos; first to transfer media chunks to server before sequential processing.</li>
                <li>Zero fake progress bars or simulated batch job IDs are rendered.</li>
              </ul>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                data-testid="close-process-modal-button"
                onClick={() => setShowProcessModal(false)}
                style={{
                  padding: '9px 18px',
                  borderRadius: 8,
                  background: 'rgba(255,255,255,0.08)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  color: '#f8fafc',
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: 'pointer'
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
