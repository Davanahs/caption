'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  PodcastRegion,
  REGION_COLORS,
  createDefaultPodcastRegions,
  clampNormalizedRect,
  displayToNormalized,
  normalizedToDisplay,
  getOutputPreviewGeometry,
} from '@/lib/podcastCoordinates';
import { extractYouTubeVideoId, analyzePodcastShots, getVideoFrameUrl, getDestinations, PublishDestination } from '@/lib/api';
import { useFocusTrap } from '@/lib/useFocusTrap';

export interface PodcastProcessingConfig {
  sourceType?: 'url' | 'file';
  url: string;
  file?: File | null;
  regions: PodcastRegion[];
  composition: 'camera_following' | 'visibility_driven' | 'stacked' | 'single_region' | 'advanced_podcast' | 'fixed_two_person';
  targetDuration: number;
  clipMode: 'ai_highlights' | 'equal_split';
  clipsCount: number;
  shotSchedule?: any[];
  destinationIds?: string[];
}

export interface PodcastSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (config: PodcastProcessingConfig) => Promise<void> | void;
  initialUrl?: string;
  initialFile?: File | null;
  initialMode?: 'manual' | 'advanced' | 'camera_following' | 'visibility_driven';
  isSubmitting?: boolean;
  errorMessage?: string;
  isInline?: boolean;
}

export default function PodcastSelectionModal({
  isOpen,
  onClose,
  onConfirm,
  initialUrl = '',
  initialFile = null,
  initialMode = 'manual',
  isSubmitting = false,
  errorMessage = '',
  isInline = false,
}: PodcastSelectionModalProps) {
  // ── 2-Feature Podcast Studio State ──
  // Feature 1: 'camera_following' (Standard Continuous Camera Follower)
  // Feature 2: 'visibility_driven' (AI Smart Director with Dynamic Cuts)
  const [selectedFeature, setSelectedFeature] = useState<'camera_following' | 'visibility_driven'>(
    initialMode === 'advanced' || initialMode === 'visibility_driven' ? 'visibility_driven' : 'camera_following'
  );
  const [isAnalyzingShots, setIsAnalyzingShots] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState<string>('');
  const [shotSchedule, setShotSchedule] = useState<any[]>([]);
  const [selectedShotId, setSelectedShotId] = useState<number | null>(null);
  const [isScheduleExpanded, setIsScheduleExpanded] = useState<boolean>(false);

  // ── Timestamp-Accurate Source Frame Preview State ──
  const [extractedFrameUrl, setExtractedFrameUrl] = useState<string | null>(null);
  const [isFrameLoading, setIsFrameLoading] = useState<boolean>(false);
  const [frameError, setFrameError] = useState<string | null>(null);
  const [frameTimestamp, setFrameTimestamp] = useState<number | null>(null);
  const frameCacheRef = useRef<Map<string, string>>(new Map());
  const frameAbortRef = useRef<AbortController | null>(null);
  const frameRequestSeqRef = useRef<number>(0);

  // ── Intake & Source State (YouTube URL or Local System Storage) ──
  const [sourceType, setSourceType] = useState<'url' | 'file'>(initialFile ? 'file' : 'url');
  const [selectedFile, setSelectedFile] = useState<File | null>(initialFile || null);
  const [localVideoUrl, setLocalVideoUrl] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [urlInput, setUrlInput] = useState<string>(initialUrl);
  const [loadedUrl, setLoadedUrl] = useState<string>('');
  const [videoId, setVideoId] = useState<string | null>(null);
  const [videoTitle, setVideoTitle] = useState<string>('Podcast / Interview Video');
  const [urlError, setUrlError] = useState<string | null>(null);
  const [previewLoaded, setPreviewLoaded] = useState<boolean>(false);

  // ── Mode & Area Selection State ──
  // 'edit' mode enables drawing and handle manipulation on overlay; 'playback' allows direct player interaction
  const [interactionMode, setInteractionMode] = useState<'edit' | 'playback'>('edit');
  const [regions, setRegions] = useState<PodcastRegion[]>([]);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);

  // ── Clip Settings State ──
  const [clipDuration, setClipDuration] = useState<number>(30); // 30s recommended
  const [clipStyle, setClipStyle] = useState<'ai_highlights' | 'equal_split'>('ai_highlights');
  const [clipsCount, setClipsCount] = useState<number>(3);
  const [localError, setLocalError] = useState<string>('');
  const nextIdRef = useRef<number>(1);

  // ── Destination Selection State ──
  const [destinations, setDestinations] = useState<PublishDestination[]>([]);
  const [selectedDestinationIds, setSelectedDestinationIds] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    getDestinations()
      .then((dests) => {
        if (!cancelled && Array.isArray(dests)) {
          setDestinations(dests);
        }
      })
      .catch((err) => console.error('Failed to load destinations in Podcast modal:', err));
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Canonical Output Preview Geometry (Live 9:16 Mirror) ──
  const outputPreviewGeom = useMemo(() => {
    if (selectedFeature === 'visibility_driven') {
      if (shotSchedule.length > 0 && selectedShotId !== null) {
        const activeShot = shotSchedule.find(s => s.shot_id === selectedShotId);
        if (activeShot) {
          const track = String(activeShot.override_track_id || activeShot.active_track_id || '').toLowerCase();
          const comp = String(activeShot.composition || '').toUpperCase();

          // Override track ID has highest precedence when determining layout
          if (track === 'area-1' || track === 'speaker_1' || track === 'speaker_a') {
            return getOutputPreviewGeometry('a_only', regions, 1080, 1920, 1920, 1080, undefined, activeShot);
          } else if (track === 'area-2' || track === 'speaker_2' || track === 'speaker_b') {
            return getOutputPreviewGeometry('b_only', regions, 1080, 1920, 1920, 1080, undefined, activeShot);
          } else if (track === 'two_shot' || track === 'both_participants' || track === 'both' || track === 'side_by_side') {
            return getOutputPreviewGeometry('side_by_side', regions, 1080, 1920, 1920, 1080, undefined, activeShot);
          } else if (comp === 'A_ONLY') {
            return getOutputPreviewGeometry('a_only', regions, 1080, 1920, 1920, 1080, undefined, activeShot);
          } else if (comp === 'B_ONLY') {
            return getOutputPreviewGeometry('b_only', regions, 1080, 1920, 1920, 1080, undefined, activeShot);
          } else if (comp === 'SIDE_BY_SIDE') {
            return getOutputPreviewGeometry('side_by_side', regions, 1080, 1920, 1920, 1080, undefined, activeShot);
          } else if (comp === 'UNKNOWN_REVIEW' || activeShot.review_needed || track === 'unassigned') {
            return getOutputPreviewGeometry('unknown_review', regions, 1080, 1920, 1920, 1080, undefined, activeShot);
          }
        }
      }
      // Pre-analysis default: A+B side-by-side
      return getOutputPreviewGeometry('side_by_side', regions, 1080, 1920, 1920, 1080);
    }
    // Feature 1: camera_following (Standard Podcast Continuous Camera Follower)
    return getOutputPreviewGeometry('single_region', regions, 1080, 1920, 1920, 1080);
  }, [selectedFeature, regions, shotSchedule, selectedShotId]);

  // ── Interaction & Dragging Refs ──
  const videoContainerRef = useRef<HTMLDivElement>(null);
  const [dragState, setDragState] = useState<{
    type: 'move' | 'resize' | 'draw';
    regionId?: string;
    handle?: string; // 'nw', 'ne', 'se', 'sw'
    startX: number;
    startY: number;
    initialRect?: { x: number; y: number; width: number; height: number };
  } | null>(null);

  // ── Async Polling Cancellation & Session Refs ──
  const abortControllerRef = useRef<AbortController | null>(null);
  const analysisSessionRef = useRef<number>(0);

  // Abort any pending background polling and revoke frame & local video URLs when component unmounts
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      if (frameAbortRef.current) {
        frameAbortRef.current.abort();
        frameAbortRef.current = null;
      }
      if (localVideoUrl) {
        try {
          URL.revokeObjectURL(localVideoUrl);
        } catch (_) {}
      }
      frameCacheRef.current.forEach((objUrl) => {
        try {
          URL.revokeObjectURL(objUrl);
        } catch (_) {}
      });
      frameCacheRef.current.clear();
    };
  }, [localVideoUrl]);

  // ── Timestamp-Accurate Source Frame Extraction Effect ──
  useEffect(() => {
    if (!videoId || shotSchedule.length === 0 || selectedShotId === null) {
      const resetTimer = setTimeout(() => {
        setExtractedFrameUrl(null);
        setFrameTimestamp(null);
        setFrameError(null);
      }, 0);
      return () => clearTimeout(resetTimer);
    }

    const activeShot = shotSchedule.find(s => s.shot_id === selectedShotId);
    if (!activeShot) return;

    const targetTs = (Number(activeShot.start_time) + Number(activeShot.end_time)) / 2.0;
    const cacheKey = `${videoId}_${selectedShotId}_${targetTs.toFixed(2)}`;

    // Client-side cache hit
    if (frameCacheRef.current.has(cacheKey)) {
      const cached = frameCacheRef.current.get(cacheKey)!;
      const hitTimer = setTimeout(() => {
        setExtractedFrameUrl(cached);
        setFrameTimestamp(targetTs);
        setFrameError(null);
        setIsFrameLoading(false);
      }, 0);
      return () => clearTimeout(hitTimer);
    }

    // Cancel in-flight frame request to prevent race conditions
    if (frameAbortRef.current) {
      frameAbortRef.current.abort();
    }
    const controller = new AbortController();
    frameAbortRef.current = controller;
    const currentSeq = ++frameRequestSeqRef.current;

    const startTimer = setTimeout(() => {
      setIsFrameLoading(true);
      setFrameError(null);
    }, 0);

    const frameUrl = getVideoFrameUrl(videoId, targetTs, selectedShotId);

    fetch(frameUrl, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const blob = await res.blob();
        return URL.createObjectURL(blob);
      })
      .then((objUrl) => {
        if (frameRequestSeqRef.current === currentSeq && !controller.signal.aborted) {
          frameCacheRef.current.set(cacheKey, objUrl);
          setExtractedFrameUrl(objUrl);
          setFrameTimestamp(targetTs);
          setIsFrameLoading(false);
          setFrameError(null);
        }
      })
      .catch((err) => {
        if (err.name === 'AbortError' || controller.signal.aborted) {
          return;
        }
        if (frameRequestSeqRef.current === currentSeq) {
          setIsFrameLoading(false);
          setFrameError(err.message || 'Frame extraction unavailable');
          setExtractedFrameUrl(null);
        }
      });

    return () => {
      clearTimeout(startTimer);
      controller.abort();
    };
  }, [videoId, selectedShotId, shotSchedule]);

  // Handle local video selection from system storage
  const handleSelectLocalFile = useCallback((file: File) => {
    if (!file) return;
    setLocalVideoUrl(prevUrl => {
      if (prevUrl) {
        try { URL.revokeObjectURL(prevUrl); } catch (_) {}
      }
      return URL.createObjectURL(file);
    });
    setSelectedFile(file);
    setSourceType('file');
    setLoadedUrl('');
    setVideoId(null);
    setVideoTitle(file.name);
    setPreviewLoaded(true);
    setUrlError(null);
    setLocalError('');

    // Reset or populate default 2-speaker regions when loading video
    if (regions.length === 0) {
      const defaults = createDefaultPodcastRegions();
      setRegions(defaults);
      setSelectedRegionId(defaults[0].id);
    }
  }, [regions.length]);

  const handleFileDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleSelectLocalFile(e.dataTransfer.files[0]);
    }
  }, [handleSelectLocalFile]);

  // Handle URL loading and preview initialization (hoisted above useEffect)
  const handleLoadPreview = (rawUrl?: string) => {
    const targetUrl = (rawUrl !== undefined ? rawUrl : urlInput).trim();
    setUrlError(null);
    setLocalError('');

    if (!targetUrl) {
      setUrlError('Please enter a YouTube video URL.');
      return;
    }

    const id = extractYouTubeVideoId(targetUrl);
    if (!id) {
      setUrlError('Invalid YouTube URL. Please provide a valid youtube.com or youtu.be link.');
      setVideoId(null);
      setPreviewLoaded(false);
      return;
    }

    setLocalVideoUrl(prevUrl => {
      if (prevUrl) {
        try { URL.revokeObjectURL(prevUrl); } catch (_) {}
      }
      return null;
    });
    setSelectedFile(null);
    setSourceType('url');
    setVideoId(id);
    setLoadedUrl(targetUrl);
    setPreviewLoaded(true);
    setVideoTitle(`YouTube Video (${id})`);

    // Reset or populate default 2-speaker regions when loading a new video
    if (regions.length === 0) {
      const defaults = createDefaultPodcastRegions();
      setRegions(defaults);
      setSelectedRegionId(defaults[0].id);
    }
  };

  // Synchronize initial file or URL and workflow mode
  useEffect(() => {
    const syncTimer = setTimeout(() => {
      if (isOpen) {
        setLocalError('');
        if (initialMode) {
          setSelectedFeature(initialMode === 'advanced' || initialMode === 'visibility_driven' ? 'visibility_driven' : 'camera_following');
        }
        if (initialFile) {
          handleSelectLocalFile(initialFile);
        } else if (initialUrl && initialUrl !== loadedUrl) {
          setUrlInput(initialUrl);
          handleLoadPreview(initialUrl);
        } else if (!videoId && !localVideoUrl) {
          // If empty, reset
          setRegions(createDefaultPodcastRegions());
        }
      }
    }, 0);
    return () => clearTimeout(syncTimer);
  }, [isOpen, initialFile, initialUrl, initialMode, loadedUrl, videoId, localVideoUrl, handleSelectLocalFile]);

  // ── Keyboard Focus Trap & Accessibility Management ──
  const modalContainerRef = useRef<HTMLDivElement>(null);
  useFocusTrap(isOpen && !isInline, modalContainerRef, onClose, isSubmitting);

  // ── Area Manipulation Helpers ──
  const handleAddArea = () => {
    const newIndex = regions.length + 1;
    const color = REGION_COLORS[(newIndex - 1) % REGION_COLORS.length];
    const newRegion: PodcastRegion = {
      id: `area-${nextIdRef.current++}`,
      label: `Area ${newIndex} (Speaker ${newIndex})`,
      x: Math.min(0.7, 0.1 + (newIndex - 1) * 0.2),
      y: 0.15,
      width: 0.35,
      height: 0.70,
      color,
    };
    const updated = [...regions, newRegion];
    setRegions(updated);
    setSelectedRegionId(newRegion.id);
    setInteractionMode('edit');
  };

  const handleRemoveArea = (id: string) => {
    const updated = regions.filter(r => r.id !== id);
    setRegions(updated);
    if (selectedRegionId === id) {
      setSelectedRegionId(updated.length > 0 ? updated[0].id : null);
    }
  };

  const handleUpdateLabel = (id: string, newLabel: string) => {
    setRegions(prev =>
      prev.map(r => (r.id === id ? { ...r, label: newLabel } : r))
    );
  };

  const handleClearAreas = () => {
    if (regions.length === 0) return;
    if (window.confirm('Clear all defined speaker areas?')) {
      setRegions([]);
      setSelectedRegionId(null);
    }
  };

  // ── Drag & Resize Pointer Events ──
  const handlePointerDown = (
    e: React.PointerEvent<HTMLDivElement>,
    action: 'move' | 'resize' | 'draw',
    regionId?: string,
    handle?: string
  ) => {
    if (interactionMode !== 'edit' || !videoContainerRef.current) return;
    e.stopPropagation();
    e.preventDefault();

    const rect = videoContainerRef.current.getBoundingClientRect();
    const norm = displayToNormalized(e.clientX, e.clientY, rect);

    if (action === 'draw') {
      const newId = `area-${nextIdRef.current++}`;
      const color = REGION_COLORS[regions.length % REGION_COLORS.length];
      const newRegion: PodcastRegion = {
        id: newId,
        label: `Area ${regions.length + 1}`,
        x: norm.x,
        y: norm.y,
        width: 0.05,
        height: 0.05,
        color,
      };
      setRegions(prev => [...prev, newRegion]);
      setSelectedRegionId(newId);
      setDragState({
        type: 'draw',
        regionId: newId,
        startX: norm.x,
        startY: norm.y,
        initialRect: { ...newRegion },
      });
    } else if (regionId) {
      setSelectedRegionId(regionId);
      const target = regions.find(r => r.id === regionId);
      if (target) {
        setDragState({
          type: action,
          regionId,
          handle,
          startX: norm.x,
          startY: norm.y,
          initialRect: { ...target },
        });
      }
    }
  };

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragState || !videoContainerRef.current) return;
      e.preventDefault();

      const rect = videoContainerRef.current.getBoundingClientRect();
      const norm = displayToNormalized(e.clientX, e.clientY, rect);
      const dx = norm.x - dragState.startX;
      const dy = norm.y - dragState.startY;
      const initial = dragState.initialRect;
      if (!initial) return;

      if (dragState.type === 'move' && dragState.regionId) {
        const nextX = initial.x + dx;
        const nextY = initial.y + dy;
        const clamped = clampNormalizedRect({
          x: nextX,
          y: nextY,
          width: initial.width,
          height: initial.height,
        });

        setRegions(prev =>
          prev.map(r => (r.id === dragState.regionId ? { ...r, ...clamped } : r))
        );
      } else if (dragState.type === 'resize' && dragState.regionId && dragState.handle) {
        let { x, y, width, height } = initial;
        const h = dragState.handle;

        if (h.includes('e')) {
          width = initial.width + dx;
        }
        if (h.includes('s')) {
          height = initial.height + dy;
        }
        if (h.includes('w')) {
          x = initial.x + dx;
          width = initial.width - dx;
        }
        if (h.includes('n')) {
          y = initial.y + dy;
          height = initial.height - dy;
        }

        const clamped = clampNormalizedRect({ x, y, width, height });
        setRegions(prev =>
          prev.map(r => (r.id === dragState.regionId ? { ...r, ...clamped } : r))
        );
      } else if (dragState.type === 'draw' && dragState.regionId) {
        const startX = dragState.startX;
        const startY = dragState.startY;
        const x = Math.min(startX, norm.x);
        const y = Math.min(startY, norm.y);
        const width = Math.abs(norm.x - startX);
        const height = Math.abs(norm.y - startY);

        const clamped = clampNormalizedRect({ x, y, width, height });
        setRegions(prev =>
          prev.map(r => (r.id === dragState.regionId ? { ...r, ...clamped } : r))
        );
      }
    },
    [dragState]
  );

  const handlePointerUp = useCallback(() => {
    setDragState(null);
  }, []);

  // ── Shot Analysis Handlers ──
  const handleCancelAnalysis = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsAnalyzingShots(false);
    setAnalysisStatus('Analysis cancelled by user.');
  }, []);

  const handleCloseModal = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    onClose();
  }, [onClose]);

  const handleAnalyzeShots = async () => {
    if (sourceType === 'file') {
      setLocalError('Shot pre-analysis is designed for YouTube URLs. For local files, AI Smart Director will process dynamic cuts automatically during clip generation.');
      return;
    }
    if (!loadedUrl) {
      setLocalError('Please load a video URL preview first.');
      return;
    }
    if (regions.length === 0) {
      setLocalError('Please define at least one participant reference area.');
      return;
    }

    // Abort any existing in-flight analysis session
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const currentSessionId = ++analysisSessionRef.current;

    setIsAnalyzingShots(true);
    setAnalysisStatus('Detecting camera cuts and matching participant identities...');
    setLocalError('');

    try {
      const data = await analyzePodcastShots(
        loadedUrl,
        regions,
        0.0,
        (stage, progress) => {
          if (analysisSessionRef.current === currentSessionId && !controller.signal.aborted) {
            setAnalysisStatus(`Analyzing video shots... (${stage} ${progress}%)`);
          }
        },
        'visibility_driven',
        controller.signal,
        600000 // 600-second (10-minute) wall-clock deadline for long-form podcasts
      );

      // Prevent stale task responses from updating a closed or superseded UI session
      if (analysisSessionRef.current !== currentSessionId || controller.signal.aborted) {
        return;
      }

      if (data && data.shots && data.shots.length > 0) {
        setShotSchedule(data.shots);
        setSelectedShotId(data.shots[0].shot_id);
        setIsScheduleExpanded(false);
        const reviewCount = data.review_needed_count || 0;
        if (reviewCount > 0) {
          setAnalysisStatus(`✓ Detected ${data.total_shots} camera cuts (${reviewCount} require review below)`);
        } else {
          setAnalysisStatus(`✓ Successfully analyzed ${data.total_shots} camera cuts. All shots matched!`);
        }
      } else {
        throw new Error('No shot segments returned');
      }
    } catch (err: any) {
      // Distinguish polling cancellation from actual Celery task failures
      if (err?.name === 'AbortError' || controller.signal.aborted) {
        if (analysisSessionRef.current === currentSessionId) {
          setAnalysisStatus('Analysis cancelled.');
        }
        return;
      }

      // Ignore errors from stale or superseded sessions
      if (analysisSessionRef.current !== currentSessionId) {
        return;
      }

      console.error('Backend shot analysis failed:', err);
      const errMsg = err?.message || 'Shot analysis failed. Please check the regions and retry.';
      setLocalError(`Shot analysis failed: ${errMsg}`);
      setAnalysisStatus('');
      setShotSchedule([]);
    } finally {
      if (analysisSessionRef.current === currentSessionId) {
        setIsAnalyzingShots(false);
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
      }
    }
  };

  const handleOverrideShot = (shotId: number, newTrackId: string) => {
    setShotSchedule(prev =>
      prev.map(s => {
        if (s.shot_id !== shotId) return s;
        let newComp = s.composition;
        const lower = newTrackId.toLowerCase();
        const faceCrop = s.face_crop || (s.crop_rect?.norm_w ? s.crop_rect : null);
        let updatedCrop = s.crop_rect;

        if (lower === 'area-1' || lower === 'speaker_1' || lower === 'speaker_a') {
          newComp = 'A_ONLY';
          if (faceCrop) updatedCrop = faceCrop;
        } else if (lower === 'area-2' || lower === 'speaker_2' || lower === 'speaker_b') {
          newComp = 'B_ONLY';
          if (faceCrop) updatedCrop = faceCrop;
        } else if (lower === 'two_shot' || lower === 'both_participants' || lower === 'side_by_side' || lower === 'both') {
          newComp = 'SIDE_BY_SIDE';
        } else if (lower === 'unassigned') {
          newComp = 'UNKNOWN_REVIEW';
        }
        return {
          ...s,
          active_track_id: newTrackId,
          override_track_id: newTrackId,
          composition: newComp,
          crop_rect: updatedCrop,
          crop_a: (newComp === 'A_ONLY' && faceCrop) ? faceCrop : s.crop_a,
          crop_b: (newComp === 'B_ONLY' && faceCrop) ? faceCrop : s.crop_b,
          review_needed: false,
        };
      })
    );
  };

  // ── Form Submission ──
  const handleSubmit = async () => {
    if (sourceType === 'file') {
      if (!selectedFile) {
        setLocalError('Please select a video file from your system storage.');
        return;
      }
    } else {
      if (!videoId || !loadedUrl) {
        setLocalError('Please load a valid YouTube video preview first.');
        return;
      }
    }
    if (regions.length === 0) {
      setLocalError('Please select at least one speaker area on the video frame.');
      return;
    }

    setLocalError('');
    await onConfirm({
      sourceType,
      url: loadedUrl || '',
      file: selectedFile,
      regions,
      composition: selectedFeature,
      targetDuration: clipDuration,
      clipMode: clipStyle,
      clipsCount,
      shotSchedule: selectedFeature === 'visibility_driven' && shotSchedule.length > 0 ? shotSchedule : undefined,
      destinationIds: selectedDestinationIds.length > 0 ? selectedDestinationIds : undefined,
    });
  };

  if (!isOpen) return null;

  const studioContent = (
    <div
      ref={modalContainerRef}
      tabIndex={-1}
      role={isInline ? 'region' : 'dialog'}
      aria-modal={isInline ? undefined : 'true'}
      aria-labelledby="podcast-modal-title"
      aria-describedby="podcast-modal-description"
      className="glass"
      style={{
        width: '100%',
        maxWidth: isInline ? '100%' : '1240px',
        height: isInline ? 'calc(100vh - 48px)' : 'min(94vh, 900px)',
        minHeight: isInline ? '680px' : undefined,
        maxHeight: isInline ? 'calc(100vh - 48px)' : '94vh',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#0f172a',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        borderRadius: '16px',
        boxShadow: isInline ? '0 10px 30px rgba(0, 0, 0, 0.5)' : '0 25px 60px -15px rgba(0, 0, 0, 0.85)',
        overflow: 'hidden',
        color: '#f8fafc',
        fontFamily: "'Inter', -apple-system, sans-serif",
        position: 'relative',
      }}
    >
        {/* ── Top Header ── */}
        <div
          style={{
            padding: '14px 24px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(to right, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.98))',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '18px',
              }}
            >
              🎙️
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2
                  id="podcast-modal-title"
                  style={{
                    fontSize: '18px',
                    fontWeight: 700,
                    margin: 0,
                    letterSpacing: '-0.02em',
                  }}
                >
                  🎙️ Podcast & Interview Studio
                </h2>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    padding: '2px 8px',
                    borderRadius: '12px',
                    background: selectedFeature === 'visibility_driven' ? 'rgba(139, 92, 246, 0.25)' : 'rgba(59, 130, 246, 0.2)',
                    color: selectedFeature === 'visibility_driven' ? '#c4b5fd' : '#93c5fd',
                    border: selectedFeature === 'visibility_driven' ? '1px solid rgba(139, 92, 246, 0.35)' : '1px solid rgba(59, 130, 246, 0.3)',
                  }}
                >
                  {selectedFeature === 'visibility_driven' ? 'AI Smart Director (Dynamic Cuts)' : 'Standard (Continuous Camera Follower)'}
                </span>
              </div>
              <p id="podcast-modal-description" style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                Choose between Standard Camera Follower or AI Smart Director to generate viral 9:16 vertical clips.
              </p>
            </div>
          </div>

          <button
            onClick={handleCloseModal}
            aria-label="Close dialog"
            disabled={isSubmitting}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              fontSize: '20px',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
            onMouseLeave={e => (e.currentTarget.style.color = '#94a3b8')}
          >
            ✕
          </button>
        </div>

        {/* ── Main Workspace Body (2 Columns) ── */}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            display: 'grid',
            gridTemplateColumns: '1fr 380px',
            gap: '24px',
            padding: '16px 24px',
            overflowY: 'auto',
          }}
        >
          {/* ──── Left Column: Video Preview & Area Selection Canvas ──── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Mode Switch & Controls Bar */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  type="button"
                  onClick={() => setInteractionMode('edit')}
                  style={{
                    padding: '6px 14px',
                    fontSize: '12px',
                    fontWeight: 600,
                    borderRadius: '6px',
                    border: '1px solid',
                    borderColor:
                      interactionMode === 'edit'
                        ? '#3b82f6'
                        : 'rgba(255, 255, 255, 0.1)',
                    background:
                      interactionMode === 'edit'
                        ? 'rgba(59, 130, 246, 0.25)'
                        : 'rgba(255, 255, 255, 0.05)',
                    color: interactionMode === 'edit' ? '#fff' : '#94a3b8',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <span>✂️</span>
                  <span>Select & Adjust Areas ({regions.length})</span>
                </button>

                <button
                  type="button"
                  onClick={() => setInteractionMode('playback')}
                  style={{
                    padding: '6px 14px',
                    fontSize: '12px',
                    fontWeight: 600,
                    borderRadius: '6px',
                    border: '1px solid',
                    borderColor:
                      interactionMode === 'playback'
                        ? '#10b981'
                        : 'rgba(255, 255, 255, 0.1)',
                    background:
                      interactionMode === 'playback'
                        ? 'rgba(16, 185, 129, 0.25)'
                        : 'rgba(255, 255, 255, 0.05)',
                    color: interactionMode === 'playback' ? '#fff' : '#94a3b8',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <span>▶️</span>
                  <span>Watch & Play Video</span>
                </button>
              </div>

              {regions.length > 0 && (
                <button
                  type="button"
                  onClick={handleClearAreas}
                  style={{
                    padding: '4px 10px',
                    fontSize: '11px',
                    color: '#f87171',
                    background: 'transparent',
                    border: '1px solid rgba(248, 113, 113, 0.2)',
                    borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                >
                  Clear Areas
                </button>
              )}
            </div>

            {/* 16:9 Video & Selection Canvas Container */}
            <div
              ref={videoContainerRef}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              style={{
                position: 'relative',
                width: '100%',
                aspectRatio: '16 / 9',
                maxHeight: '400px',
                backgroundColor: '#000',
                borderRadius: '10px',
                overflow: 'hidden',
                boxShadow: '0 10px 30px rgba(0, 0, 0, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                userSelect: 'none',
                touchAction: 'none',
              }}
            >
              {videoId || localVideoUrl ? (
                <>
                  {/* Local Video or YouTube Embedded Player */}
                  {localVideoUrl ? (
                    <video
                      ref={localVideoRef}
                      src={localVideoUrl}
                      controls={interactionMode === 'playback'}
                      playsInline
                      style={{
                        position: 'absolute',
                        inset: 0,
                        width: '100%',
                        height: '100%',
                        objectFit: 'contain',
                        pointerEvents: interactionMode === 'playback' ? 'auto' : 'none',
                      }}
                    />
                  ) : videoId ? (
                    <iframe
                      src={`https://www.youtube-nocookie.com/embed/${videoId}?enablejsapi=1&rel=0&modestbranding=1`}
                      title="Podcast Video Preview"
                      style={{
                        position: 'absolute',
                        inset: 0,
                        width: '100%',
                        height: '100%',
                        border: 'none',
                        pointerEvents: interactionMode === 'playback' ? 'auto' : 'none',
                      }}
                      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                      allowFullScreen
                    />
                  ) : null}

                  {/* Interactive Area Selection Overlay (Active during edit mode) */}
                  {interactionMode === 'edit' && (
                    <div
                      onPointerDown={e => {
                        // Drawing new area when clicking background
                        if (e.target === e.currentTarget) {
                          handlePointerDown(e, 'draw');
                        }
                      }}
                      style={{
                        position: 'absolute',
                        inset: 0,
                        cursor: 'crosshair',
                        zIndex: 10,
                      }}
                    >
                      {/* Render Each Selected Bounding Box */}
                      {regions.map((region) => {
                        const isSelected = region.id === selectedRegionId;

                        return (
                          <div
                            key={region.id}
                            onPointerDown={e => handlePointerDown(e, 'move', region.id)}
                            style={{
                              position: 'absolute',
                              left: `${region.x * 100}%`,
                              top: `${region.y * 100}%`,
                              width: `${region.width * 100}%`,
                              height: `${region.height * 100}%`,
                              border: `2px solid ${region.color}`,
                              backgroundColor: `${region.color}20`,
                              boxShadow: isSelected
                                ? `0 0 12px ${region.color}`
                                : 'none',
                              cursor: 'move',
                              zIndex: isSelected ? 20 : 15,
                              boxSizing: 'border-box',
                            }}
                          >
                            {/* Region Label Badge */}
                            <div
                              style={{
                                position: 'absolute',
                                top: '-26px',
                                left: '-2px',
                                backgroundColor: region.color,
                                color: '#fff',
                                fontSize: '11px',
                                fontWeight: 600,
                                padding: '2px 8px',
                                borderRadius: '4px 4px 0 0',
                                whiteSpace: 'nowrap',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                pointerEvents: 'none',
                              }}
                            >
                              <span>{region.label}</span>
                            </div>

                            {/* Resize Handles (Corners and Edges) */}
                            {isSelected && (
                              <>
                                {/* NW Handle */}
                                <div
                                  onPointerDown={e => handlePointerDown(e, 'resize', region.id, 'nw')}
                                  style={{
                                    position: 'absolute',
                                    top: '-5px',
                                    left: '-5px',
                                    width: '10px',
                                    height: '10px',
                                    backgroundColor: '#fff',
                                    border: `2px solid ${region.color}`,
                                    borderRadius: '50%',
                                    cursor: 'nwse-resize',
                                  }}
                                />
                                {/* NE Handle */}
                                <div
                                  onPointerDown={e => handlePointerDown(e, 'resize', region.id, 'ne')}
                                  style={{
                                    position: 'absolute',
                                    top: '-5px',
                                    right: '-5px',
                                    width: '10px',
                                    height: '10px',
                                    backgroundColor: '#fff',
                                    border: `2px solid ${region.color}`,
                                    borderRadius: '50%',
                                    cursor: 'nesw-resize',
                                  }}
                                />
                                {/* SW Handle */}
                                <div
                                  onPointerDown={e => handlePointerDown(e, 'resize', region.id, 'sw')}
                                  style={{
                                    position: 'absolute',
                                    bottom: '-5px',
                                    left: '-5px',
                                    width: '10px',
                                    height: '10px',
                                    backgroundColor: '#fff',
                                    border: `2px solid ${region.color}`,
                                    borderRadius: '50%',
                                    cursor: 'nesw-resize',
                                  }}
                                />
                                {/* SE Handle */}
                                <div
                                  onPointerDown={e => handlePointerDown(e, 'resize', region.id, 'se')}
                                  style={{
                                    position: 'absolute',
                                    bottom: '-5px',
                                    right: '-5px',
                                    width: '10px',
                                    height: '10px',
                                    backgroundColor: '#fff',
                                    border: `2px solid ${region.color}`,
                                    borderRadius: '50%',
                                    cursor: 'nwse-resize',
                                  }}
                                />
                              </>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              ) : (
                /* Empty / No Video State */
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#64748b',
                    gap: '12px',
                    padding: '24px',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: '38px' }}>{sourceType === 'file' ? '📁' : '📺'}</div>
                  <div style={{ fontSize: '15px', fontWeight: 600, color: '#94a3b8' }}>
                    {sourceType === 'file'
                      ? 'Upload a video from system storage on the right to load preview'
                      : 'Paste a YouTube link on the right to load video preview'}
                  </div>
                  <div style={{ fontSize: '12px', maxWidth: '380px' }}>
                    Once loaded, you can play the video, pause at any interview frame, and draw or adjust speaker regions.
                  </div>
                </div>
              )}
            </div>

            {/* ── Output Preview — Final 9:16 Composition (Live Geometry Mirror) ── */}
            <div
              id="output-preview-final-9-16"
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                padding: '14px 18px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.7))',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '15px' }}>📱</span>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#f8fafc', letterSpacing: '-0.01em' }}>
                    Output Preview — Final 9:16 Composition
                  </div>
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 600,
                      padding: '2px 6px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(59, 130, 246, 0.2)',
                      color: '#93c5fd',
                      border: '1px solid rgba(59, 130, 246, 0.35)',
                    }}
                  >
                    {selectedFeature === 'visibility_driven'
                      ? shotSchedule.length > 0 && selectedShotId !== null
                        ? `Shot ${selectedShotId} Preview — ${
                            outputPreviewGeom.composition === 'side_by_side'
                              ? 'Side-by-Side (A+B)'
                              : outputPreviewGeom.composition === 'single_region'
                              ? outputPreviewGeom.panels[0]?.speakerLabel
                              : 'Composition'
                          }`
                        : 'Initial Preview — Side-by-Side (A + B)'
                      : 'Standard • Continuous Camera Follower (9:16)'}
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                  <div style={{ fontSize: '11px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981' }} />
                    <span>1080 × 1920 (9:16 Canvas)</span>
                  </div>
                  {/* Truthful Frame Preview Status Badge */}
                  <div id="frame-preview-status-badge">
                    {extractedFrameUrl && frameTimestamp !== null ? (
                      <span
                        id="frame-preview-badge"
                        style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: 'rgba(16, 185, 129, 0.2)',
                          color: '#34d399',
                          border: '1px solid rgba(16, 185, 129, 0.4)',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <span>📸</span>
                        <span>Real Frame @ {frameTimestamp.toFixed(1)}s (Shot {selectedShotId})</span>
                      </span>
                    ) : isFrameLoading ? (
                      <span
                        id="frame-preview-badge"
                        style={{
                          fontSize: '10px',
                          fontWeight: 600,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: 'rgba(99, 102, 241, 0.2)',
                          color: '#a5b4fc',
                          border: '1px solid rgba(99, 102, 241, 0.4)',
                        }}
                      >
                        ⏳ Fetching Shot Frame...
                      </span>
                    ) : frameError ? (
                      <span
                        id="frame-preview-badge"
                        style={{
                          fontSize: '10px',
                          fontWeight: 600,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: 'rgba(245, 158, 11, 0.15)',
                          color: '#fbbf24',
                          border: '1px solid rgba(245, 158, 11, 0.35)',
                        }}
                      >
                        ⚠️ Thumbnail / Geometry Fallback
                      </span>
                    ) : (
                      <span
                        id="frame-preview-badge"
                        style={{
                          fontSize: '10px',
                          fontWeight: 600,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: 'rgba(148, 163, 184, 0.12)',
                          color: '#94a3b8',
                          border: '1px solid rgba(148, 163, 184, 0.25)',
                        }}
                      >
                        ℹ️ Generic Thumbnail Preview
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Responsive Layout: 9:16 Preview Screen + Telemetry Details */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'row',
                  gap: '20px',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}
              >
                {/* Fixed 9:16 Vertical Monitor Container */}
                <div
                  id="preview-canvas-9-16-container"
                  className={outputPreviewGeom.composition === 'side_by_side' ? 'flex-row' : 'flex-col'}
                  style={{
                    width: '144px',
                    height: '256px',
                    borderRadius: '8px',
                    backgroundColor: '#000',
                    border: '1.5px solid rgba(255, 255, 255, 0.25)',
                    boxShadow: '0 12px 28px rgba(0, 0, 0, 0.75)',
                    display: 'flex',
                    flexDirection: outputPreviewGeom.composition === 'side_by_side' ? 'row' : 'column',
                    overflow: 'hidden',
                    position: 'relative',
                    flexShrink: 0,
                  }}
                >
                  {outputPreviewGeom.panels.map((p, pIdx) => {
                    const isSideBySide = outputPreviewGeom.composition === 'side_by_side';
                    const isStacked = outputPreviewGeom.composition === 'stacked';
                    const isTop = pIdx === 0 && isStacked;
                    const isBottom = pIdx === 1 && isStacked;
                    const pWidthPx = isSideBySide ? 72 : 144;
                    const pHeightPx = isStacked ? 128 : 256;
                    const pRatioW = pWidthPx / p.panelWidth;
                    const pRatioH = pHeightPx / p.panelHeight;
                    const scaledDispW = p.framing.scaledW * pRatioW;
                    const scaledDispH = p.framing.scaledH * pRatioH;
                    const padDispX = p.framing.padX * pRatioW;
                    const padDispY = p.framing.padY * pRatioH;

                    const thumbW = p.region.width > 0 ? scaledDispW / p.region.width : pWidthPx;
                    const thumbH = p.region.height > 0 ? scaledDispH / p.region.height : pHeightPx;
                    const thumbLeft = padDispX - (p.region.x * thumbW);
                    const thumbTop = padDispY - (p.region.y * thumbH);

                    return (
                      <div
                        key={p.panelId}
                        style={{
                          height: `${pHeightPx}px`,
                          width: `${pWidthPx}px`,
                          position: 'relative',
                          overflow: 'hidden',
                          backgroundColor: '#050810',
                          borderBottom: isTop ? '1px dashed rgba(255, 255, 255, 0.35)' : 'none',
                          borderRight: isSideBySide && pIdx === 0 ? '1px dashed rgba(255, 255, 255, 0.35)' : 'none',
                        }}
                      >
                        {/* Video Frame / Thumbnail Content */}
                        {extractedFrameUrl ? (
                          <img
                            src={extractedFrameUrl}
                            alt={`${p.speakerLabel} (Real Frame @ ${frameTimestamp?.toFixed(1)}s)`}
                            data-frame-tier="real_source_frame"
                            data-frame-timestamp={frameTimestamp}
                            style={{
                              position: 'absolute',
                              left: `${thumbLeft}px`,
                              top: `${thumbTop}px`,
                              width: `${thumbW}px`,
                              height: `${thumbH}px`,
                              maxWidth: 'none',
                              pointerEvents: 'none',
                            }}
                          />
                        ) : videoId ? (
                          <img
                            src={`https://img.youtube.com/vi/${videoId}/hqdefault.jpg`}
                            alt={`${p.speakerLabel} (Generic Thumbnail Fallback)`}
                            data-frame-tier="thumbnail_fallback"
                            style={{
                              position: 'absolute',
                              left: `${thumbLeft}px`,
                              top: `${thumbTop}px`,
                              width: `${thumbW}px`,
                              height: `${thumbH}px`,
                              maxWidth: 'none',
                              pointerEvents: 'none',
                            }}
                          />
                        ) : (
                          /* High-contrast framing grid placeholder when no video loaded */
                          <div
                            style={{
                              position: 'absolute',
                              left: `${padDispX}px`,
                              top: `${padDispY}px`,
                              width: `${scaledDispW}px`,
                              height: `${scaledDispH}px`,
                              backgroundColor: `${p.color}25`,
                              border: `1px solid ${p.color}80`,
                              display: 'flex',
                              flexDirection: 'column',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: p.color,
                            }}
                          >
                            <span style={{ fontSize: '18px' }}>👤</span>
                          </div>
                        )}

                        {/* Pillarbox Padding Overlays (if crop narrower than panel) */}
                        {padDispX > 1 && (
                          <>
                            <div style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: `${padDispX}px`, backgroundColor: 'rgba(0, 0, 0, 0.85)', borderRight: '1px solid rgba(255, 255, 255, 0.1)' }} />
                            <div style={{ position: 'absolute', top: 0, bottom: 0, right: 0, width: `${padDispX}px`, backgroundColor: 'rgba(0, 0, 0, 0.85)', borderLeft: '1px solid rgba(255, 255, 255, 0.1)' }} />
                          </>
                        )}

                        {/* Letterbox Padding Overlays (if crop wider than panel) */}
                        {padDispY > 1 && (
                          <>
                            <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: `${padDispY}px`, backgroundColor: 'rgba(0, 0, 0, 0.85)', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }} />
                            <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: `${padDispY}px`, backgroundColor: 'rgba(0, 0, 0, 0.85)', borderTop: '1px solid rgba(255, 255, 255, 0.1)' }} />
                          </>
                        )}

                        {/* Safe Headroom Guideline (12% from top of panel) */}
                        <div
                          style={{
                            position: 'absolute',
                            left: `${padDispX}px`,
                            right: `${padDispX}px`,
                            top: `${Math.max(padDispY, 14)}px`,
                            borderTop: '1px dotted rgba(56, 189, 248, 0.65)',
                            pointerEvents: 'none',
                          }}
                        />

                        {/* Panel Badge */}
                        <div
                          style={{
                            position: 'absolute',
                            top: '4px',
                            left: '4px',
                            backgroundColor: 'rgba(15, 23, 42, 0.85)',
                            color: '#f8fafc',
                            fontSize: '9px',
                            fontWeight: 700,
                            padding: '2px 6px',
                            borderRadius: '4px',
                            border: `1px solid ${p.color}`,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.5)',
                            zIndex: 5,
                          }}
                        >
                          <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: p.color }} />
                          <span>
                            {p.speakerLabel
                              ? p.speakerLabel
                              : isSideBySide
                              ? (pIdx === 0 ? 'Speaker A' : 'Speaker B')
                              : (p.panelId?.includes('speaker-b') ? 'Area 2 (Speaker 2)' : (isTop ? 'Speaker 1' : isBottom ? 'Speaker 2' : 'Area 1 (Speaker 1)'))}
                          </span>
                        </div>

                        {/* Resolution Label */}
                        <div
                          style={{
                            position: 'absolute',
                            bottom: '4px',
                            right: '4px',
                            backgroundColor: 'rgba(0, 0, 0, 0.75)',
                            color: '#94a3b8',
                            fontSize: '8px',
                            fontWeight: 600,
                            padding: '1px 4px',
                            borderRadius: '3px',
                            zIndex: 5,
                          }}
                        >
                          {p.panelWidth}×{p.panelHeight}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Telemetry and Explanation Column */}
                <div style={{ flex: 1, minWidth: '240px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9' }}>
                    {selectedFeature === 'visibility_driven'
                      ? selectedShotId !== null
                        ? `Camera-Following Preview (9:16) — Previewing Shot: ${selectedShotId}`
                        : 'Camera-Following Preview (9:16) — Side-by-Side (A + B)'
                      : 'Camera-Following Preview (9:16) — Continuous Camera Follower'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', lineHeight: 1.45 }}>
                    {selectedFeature === 'visibility_driven'
                      ? shotSchedule.length > 0 && selectedShotId !== null
                        ? `Shot ${selectedShotId} detected framing: Layout switches dynamically based on detected participant visibility (A-only, B-only, Side-by-Side, or safe fallback). Single continuous 9:16 vertical view reframes the active participant.`
                        : 'Initial two-person composition. Shows A+B side-by-side prior to analysis. After visual analysis, the layout changes between A-only, B-only, and A+B according to detected participant visibility. Single continuous 9:16 vertical view reframes the active participant.'
                      : 'Continuous camera follower keeps speakers centered and follows conversation smoothly without sudden shot cuts. Single continuous 9:16 vertical view reframes the active participant.'}
                  </div>
                  {/* Compatibility reference: Selected Areas Preview - Both speaker areas will be cropped and stacked */}

                  {/* Panel-by-panel Framing Telemetry */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '2px' }}>
                    {outputPreviewGeom.panels.map((p) => (
                      <div
                        key={p.panelId}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          backgroundColor: 'rgba(255, 255, 255, 0.04)',
                          border: `1px solid ${p.color}40`,
                          fontSize: '11px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: p.color }} />
                          <span style={{ fontWeight: 600, color: '#e2e8f0' }}>{p.speakerLabel}:</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#cbd5e1' }}>
                          <span>Scale: {p.framing.scaleFactor}x</span>
                          <span>•</span>
                          <span>Fit: {p.framing.padX > 0 ? `Pad ${p.framing.padX}px L/R` : `Pad ${p.framing.padY}px T/B`}</span>
                          <span>•</span>
                          <span style={{ color: '#34d399', fontWeight: 600 }}>✓ 100% visible</span>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Warning Callout if Region is Tight */}
                  {outputPreviewGeom.overallWarning && (
                    <div
                      id="output-preview-tight-warning"
                      style={{
                        padding: '6px 10px',
                        borderRadius: '6px',
                        backgroundColor: 'rgba(245, 158, 11, 0.15)',
                        border: '1px solid rgba(245, 158, 11, 0.35)',
                        color: '#fbbf24',
                        fontSize: '11px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <span>⚠️</span>
                      <span><strong>Framing Notice:</strong> {outputPreviewGeom.overallWarning}</span>
                    </div>
                  )}

                  <div style={{ fontSize: '10px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span>ℹ️ Preview uses YouTube thumbnail or geometric placeholder approximation. Final render calculates exact pixel boundaries from video frames.</span>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Shot Cuts & Participant Visibility Analysis (Feature 2: AI Smart Director) ── */}
            {selectedFeature === 'visibility_driven' && (
              <div
                style={{
                  padding: '16px',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(15, 23, 42, 0.85)',
                  border: '1px solid rgba(139, 92, 246, 0.3)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '16px' }}>⚡</span>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: '#f8fafc' }}>
                      AI Smart Director: Camera Cuts & Speaker Analysis
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {isAnalyzingShots && (
                      <button
                        id="cancel-analyze-shots-btn"
                        type="button"
                        onClick={handleCancelAnalysis}
                        style={{
                          padding: '6px 12px',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                          background: 'rgba(239, 68, 68, 0.2)',
                          color: '#fca5a5',
                          border: '1px solid rgba(239, 68, 68, 0.4)',
                          borderRadius: '6px',
                        }}
                      >
                        ✕ Cancel
                      </button>
                    )}
                    <button
                      id="analyze-shots-btn"
                      type="button"
                      onClick={handleAnalyzeShots}
                      disabled={isAnalyzingShots || !videoId}
                      className="btn-primary"
                      style={{
                        padding: '6px 14px',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: isAnalyzingShots || !videoId ? 'not-allowed' : 'pointer',
                        background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
                      }}
                    >
                      {isAnalyzingShots ? '⏳ Analyzing Shots...' : '⚡ Analyze Camera Cuts & Speakers'}
                    </button>
                  </div>
                </div>

                {analysisStatus && (
                  <div
                    style={{
                      padding: '8px 12px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontWeight: 600,
                      backgroundColor: analysisStatus.includes('✓') ? 'rgba(16, 185, 129, 0.15)' : 'rgba(99, 102, 241, 0.15)',
                      color: analysisStatus.includes('✓') ? '#34d399' : '#a5b4fc',
                      border: analysisStatus.includes('✓') ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(99, 102, 241, 0.3)',
                    }}
                  >
                    {analysisStatus}
                  </div>
                )}

                {/* Shot Timeline / Collapsible Schedule Accordion */}
                {shotSchedule.length > 0 && (() => {
                  const countA = shotSchedule.filter(s => {
                    const t = (s.override_track_id || s.active_track_id || '').toLowerCase();
                    return t === 'area-1' || t === 'speaker_1' || t === 'speaker_a' || s.composition === 'A_ONLY';
                  }).length;
                  const countB = shotSchedule.filter(s => {
                    const t = (s.override_track_id || s.active_track_id || '').toLowerCase();
                    return t === 'area-2' || t === 'speaker_2' || t === 'speaker_b' || s.composition === 'B_ONLY';
                  }).length;
                  const countTwoShot = shotSchedule.filter(s => {
                    const t = (s.override_track_id || s.active_track_id || '').toLowerCase();
                    return t === 'two_shot' || t === 'both_participants' || t === 'both' || t === 'side_by_side' || s.composition === 'SIDE_BY_SIDE';
                  }).length;
                  const countReview = shotSchedule.filter(s => s.review_needed).length;

                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {/* Summary Pill & Accordion Toggle */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '10px 14px',
                          borderRadius: '8px',
                          backgroundColor: 'rgba(30, 41, 59, 0.8)',
                          border: '1px solid rgba(148, 163, 184, 0.25)',
                          flexWrap: 'wrap',
                          gap: '8px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                          <span
                            style={{
                              fontSize: '12px',
                              fontWeight: 700,
                              color: '#34d399',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            ✓ {shotSchedule.length} Camera Cuts Detected
                          </span>
                          <span style={{ fontSize: '11px', color: '#94a3b8' }}>•</span>
                          <span style={{ fontSize: '11px', color: '#cbd5e1' }}>
                            Speaker A: <strong style={{ color: '#93c5fd' }}>{countA}</strong>
                          </span>
                          <span style={{ fontSize: '11px', color: '#94a3b8' }}>•</span>
                          <span style={{ fontSize: '11px', color: '#cbd5e1' }}>
                            Speaker B: <strong style={{ color: '#c4b5fd' }}>{countB}</strong>
                          </span>
                          <span style={{ fontSize: '11px', color: '#94a3b8' }}>•</span>
                          <span style={{ fontSize: '11px', color: '#cbd5e1' }}>
                            Side-by-Side: <strong style={{ color: '#fde047' }}>{countTwoShot}</strong>
                          </span>
                          {countReview > 0 && (
                            <span
                              style={{
                                fontSize: '10px',
                                fontWeight: 700,
                                padding: '2px 6px',
                                borderRadius: '4px',
                                backgroundColor: 'rgba(245, 158, 11, 0.2)',
                                color: '#fbbf24',
                              }}
                            >
                              ⚠️ {countReview} Review Needed
                            </span>
                          )}
                        </div>

                        <button
                          type="button"
                          id="toggle-shot-schedule-btn"
                          onClick={() => setIsScheduleExpanded(prev => !prev)}
                          style={{
                            padding: '4px 10px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontWeight: 600,
                            backgroundColor: 'rgba(99, 102, 241, 0.2)',
                            color: '#c7d2fe',
                            border: '1px solid rgba(99, 102, 241, 0.35)',
                            cursor: 'pointer',
                          }}
                        >
                          {isScheduleExpanded ? '▲ Hide Shot Schedule' : `▼ View / Customize Cuts (${shotSchedule.length})`}
                        </button>
                      </div>

                      {/* Collapsible Content */}
                      {isScheduleExpanded && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div style={{ fontSize: '12px', fontWeight: 700, color: '#cbd5e1' }}>
                              Detected Shot Schedule ({shotSchedule.length} intervals):
                            </div>
                            <div style={{ fontSize: '11px', color: '#818cf8' }}>
                              💡 Click a shot below to preview its framing
                            </div>
                          </div>
                          <div style={{ maxHeight: '180px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            {shotSchedule.map((shot, sIdx) => {
                              const targetTrack = regions.find(r => r.id === shot.active_track_id);
                              const isSelected = selectedShotId === shot.shot_id;
                              return (
                                <div
                                  key={shot.shot_id || sIdx}
                                  role="button"
                                  tabIndex={0}
                                  aria-selected={isSelected}
                                  aria-label={`Select Shot ${shot.shot_id} (${shot.start_time.toFixed(1)}s to ${shot.end_time.toFixed(1)}s)`}
                                  onClick={() => setSelectedShotId(shot.shot_id)}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                      e.preventDefault();
                                      setSelectedShotId(shot.shot_id);
                                    }
                                  }}
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: '8px 12px',
                                    borderRadius: '8px',
                                    backgroundColor: isSelected ? 'rgba(99, 102, 241, 0.25)' : 'rgba(30, 41, 59, 0.7)',
                                    border: isSelected
                                      ? '1.5px solid #6366f1'
                                      : (shot.review_needed ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)'),
                                    fontSize: '12px',
                                    gap: '8px',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s ease',
                                    outline: isSelected ? '2px solid rgba(99, 102, 241, 0.5)' : 'none',
                                  }}
                                >
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <span style={{ fontWeight: 700, color: '#93c5fd' }}>
                                      Shot {shot.shot_id}: {shot.start_time.toFixed(1)}s - {shot.end_time.toFixed(1)}s
                                    </span>
                                    <span style={{ color: '#64748b', fontSize: '11px' }}>
                                      ({shot.duration.toFixed(1)}s)
                                    </span>
                                  </div>

                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    {shot.review_needed && (
                                      <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24', fontWeight: 700 }}>
                                        ⚠️ Review Needed
                                      </span>
                                    )}
                                    <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                                      Conf: {Math.round(shot.confidence * 100)}%
                                    </span>
                                    {/* Override selector */}
                                    <select
                                      value={
                                        shot.override_track_id ||
                                        (shot.active_track_id === 'both' || shot.active_track_id === 'both_participants' ? 'two_shot' : shot.active_track_id)
                                      }
                                      onChange={(e) => handleOverrideShot(shot.shot_id, e.target.value)}
                                      style={{
                                        padding: '4px 8px',
                                        borderRadius: '6px',
                                        fontSize: '11px',
                                        backgroundColor: '#1e293b',
                                        color: '#f8fafc',
                                        border: '1px solid rgba(148, 163, 184, 0.3)',
                                        cursor: 'pointer',
                                      }}
                                    >
                                      {regions.map(r => (
                                        <option key={r.id} value={r.id}>{r.label}</option>
                                      ))}
                                      <option value="two_shot">Two-Shot (Side-by-Side)</option>
                                      <option value="unassigned">Unassigned (Safe fallback)</option>
                                    </select>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
            )}
          </div>

          {/* ──── Right Column: Configuration & Controls Sidebar ──── */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              borderLeft: '1px solid rgba(255, 255, 255, 0.08)',
              paddingLeft: '20px',
            }}
          >
            {/* Step 1: Paste YouTube Link */}
            <div>
              <div style={{ fontSize: '14px', fontWeight: 700, marginBottom: '8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>1. Paste YouTube Link</span>
                <span style={{ fontSize: '11px', color: '#818cf8', fontWeight: 600 }}>Source Mode</span>
              </div>

              {/* Source Mode Toggle: YouTube Link vs System Storage */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  background: 'rgba(15, 23, 42, 0.8)',
                  borderRadius: '10px',
                  padding: '3px',
                  gap: '4px',
                  marginBottom: '10px',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <button
                  id="podcast-tab-url-btn"
                  type="button"
                  onClick={() => { setSourceType('url'); setLocalError(''); }}
                  style={{
                    flex: 1,
                    padding: '7px 10px',
                    borderRadius: '7px',
                    fontSize: '12px',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    background: sourceType === 'url' ? '#4f46e5' : 'transparent',
                    color: sourceType === 'url' ? '#ffffff' : '#94a3b8',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                  }}
                >
                  <span>🔗 YouTube URL</span>
                </button>
                <button
                  id="podcast-tab-file-btn"
                  type="button"
                  onClick={() => { setSourceType('file'); setLocalError(''); }}
                  style={{
                    flex: 1,
                    padding: '7px 10px',
                    borderRadius: '7px',
                    fontSize: '12px',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    background: sourceType === 'file' ? '#4f46e5' : 'transparent',
                    color: sourceType === 'file' ? '#ffffff' : '#94a3b8',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                  }}
                >
                  <span>📁 System Storage</span>
                </button>
              </div>

              {sourceType === 'url' ? (
                <>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <input
                      id="podcast-youtube-url-input"
                      type="text"
                      placeholder="https://www.youtube.com/watch?v=..."
                      value={urlInput}
                      onChange={e => {
                        setUrlInput(e.target.value);
                        if (urlError) setUrlError(null);
                      }}
                      onKeyDown={e => e.key === 'Enter' && handleLoadPreview()}
                      aria-label="YouTube Video Link"
                      aria-invalid={!!urlError}
                      aria-describedby={urlError ? "podcast-url-error-msg" : undefined}
                      style={{
                        flex: 1,
                        backgroundColor: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        color: '#fff',
                        fontSize: '12px',
                        outline: 'none',
                      }}
                    />
                    <button
                      id="load-podcast-url-btn"
                      type="button"
                      onClick={() => handleLoadPreview()}
                      style={{
                        padding: '8px 12px',
                        backgroundColor: '#3b82f6',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      Load
                    </button>
                  </div>

                  {urlError && (
                    <div
                      id="podcast-url-error-msg"
                      role="alert"
                      style={{ fontSize: '11px', color: '#f87171', marginTop: '6px' }}
                    >
                      {urlError}
                    </div>
                  )}
                </>
              ) : (
                /* System Storage Dropzone & File Selection */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <input
                    ref={fileInputRef}
                    id="podcast-file-input"
                    type="file"
                    accept="video/mp4,video/quicktime,video/webm,video/x-matroska,video/*"
                    style={{ display: 'none' }}
                    onChange={e => {
                      if (e.target.files && e.target.files[0]) {
                        handleSelectLocalFile(e.target.files[0]);
                      }
                    }}
                  />

                  {selectedFile ? (
                    <div
                      id="podcast-selected-file-info"
                      style={{
                        padding: '10px 12px',
                        borderRadius: '8px',
                        background: 'rgba(79, 70, 229, 0.15)',
                        border: '1px solid rgba(99, 102, 241, 0.4)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                        <span style={{ fontSize: '18px' }}>🎬</span>
                        <div style={{ overflow: 'hidden' }}>
                          <div
                            style={{
                              fontSize: '12px',
                              fontWeight: 700,
                              color: '#c7d2fe',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              maxWidth: '170px',
                            }}
                          >
                            {selectedFile.name}
                          </div>
                          <div style={{ fontSize: '10px', color: '#94a3b8' }}>
                            {(selectedFile.size / (1024 * 1024)).toFixed(1)} MB · Ready for clipping
                          </div>
                        </div>
                      </div>
                      <button
                        type="button"
                        id="podcast-reselect-file-btn"
                        onClick={() => fileInputRef.current?.click()}
                        style={{
                          fontSize: '11px',
                          padding: '4px 8px',
                          borderRadius: '6px',
                          background: 'rgba(255, 255, 255, 0.08)',
                          border: '1px solid rgba(255, 255, 255, 0.2)',
                          color: '#e2e8f0',
                          cursor: 'pointer',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        Change
                      </button>
                    </div>
                  ) : (
                    <div
                      id="podcast-file-dropzone"
                      onDragOver={e => { e.preventDefault(); setIsDragOver(true); }}
                      onDragLeave={() => setIsDragOver(false)}
                      onDrop={handleFileDrop}
                      onClick={() => fileInputRef.current?.click()}
                      style={{
                        padding: '16px',
                        borderRadius: '8px',
                        border: isDragOver ? '2px solid #6366f1' : '2px dashed rgba(255, 255, 255, 0.2)',
                        background: isDragOver ? 'rgba(79, 70, 229, 0.12)' : 'rgba(0, 0, 0, 0.25)',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        textAlign: 'center',
                        gap: '6px',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <span style={{ fontSize: '24px' }}>📁</span>
                      <div style={{ fontSize: '12px', fontWeight: 600, color: '#e2e8f0' }}>
                        Drop video here or click to browse
                      </div>
                      <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                        Supports MP4, MOV, MKV, WEBM from storage
                      </div>
                      <button
                        type="button"
                        id="podcast-browse-file-btn"
                        style={{
                          marginTop: '4px',
                          padding: '6px 14px',
                          borderRadius: '6px',
                          background: 'linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)',
                          border: 'none',
                          color: '#fff',
                          fontSize: '11px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        Select Video File
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Video metadata card when loaded */}
              {sourceType === 'url' && videoId && (
                <div
                  style={{
                    marginTop: '10px',
                    padding: '8px',
                    borderRadius: '6px',
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                  }}
                >
                  <img
                    src={`https://img.youtube.com/vi/${videoId}/mqdefault.jpg`}
                    alt="YouTube thumbnail preview"
                    style={{
                      width: '56px',
                      height: '32px',
                      objectFit: 'cover',
                      borderRadius: '4px',
                    }}
                  />
                  <div style={{ overflow: 'hidden' }}>
                    <div
                      style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        color: '#f1f5f9',
                        textOverflow: 'ellipsis',
                        overflow: 'hidden',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {videoTitle}
                    </div>
                    <div style={{ fontSize: '10px', color: '#10b981' }}>
                      ● Preview Loaded & Ready
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Step 2: Select Areas for Clipping */}
            <div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '8px',
                }}
              >
                <div style={{ fontSize: '14px', fontWeight: 700 }}>
                  2. Select Areas for Clipping
                </div>
                <span style={{ fontSize: '11px', color: '#64748b' }}>
                  ({regions.length} selected)
                </span>
              </div>
              <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '10px' }}>
                Choose which people/areas to include in your clips:
              </div>

              {/* Area List Cards */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '160px', overflowY: 'auto' }}>
                {regions.map((region, idx) => {
                  const isSelected = region.id === selectedRegionId;
                  return (
                    <div
                      key={region.id}
                      onClick={() => {
                        setSelectedRegionId(region.id);
                        setInteractionMode('edit');
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        background: isSelected
                          ? 'rgba(59, 130, 246, 0.15)'
                          : 'rgba(255, 255, 255, 0.03)',
                        border: `1px solid ${
                          isSelected ? region.color : 'rgba(255, 255, 255, 0.08)'
                        }`,
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div
                          style={{
                            width: '10px',
                            height: '10px',
                            borderRadius: '50%',
                            backgroundColor: region.color,
                          }}
                        />
                        <input
                          type="text"
                          value={region.label}
                          onChange={e => handleUpdateLabel(region.id, e.target.value)}
                          onClick={e => e.stopPropagation()}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#fff',
                            fontSize: '12px',
                            fontWeight: 600,
                            outline: 'none',
                            width: '140px',
                          }}
                        />
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <button
                          type="button"
                          onClick={e => {
                            e.stopPropagation();
                            setSelectedRegionId(region.id);
                            setInteractionMode('edit');
                          }}
                          style={{
                            padding: '3px 8px',
                            fontSize: '10px',
                            backgroundColor: 'rgba(255, 255, 255, 0.08)',
                            color: '#e2e8f0',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                          }}
                        >
                          Adjust
                        </button>
                        <button
                          type="button"
                          onClick={e => {
                            e.stopPropagation();
                            handleRemoveArea(region.id);
                          }}
                          aria-label={`Delete ${region.label}`}
                          style={{
                            padding: '3px 6px',
                            fontSize: '11px',
                            backgroundColor: 'transparent',
                            color: '#ef4444',
                            border: 'none',
                            cursor: 'pointer',
                          }}
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Add Area & Outer Boundary Buttons */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={handleAddArea}
                  style={{
                    width: '100%',
                    padding: '8px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px dashed rgba(255, 255, 255, 0.2)',
                    borderRadius: '6px',
                    color: '#93c5fd',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                  }}
                >
                  <span>+</span>
                  <span>Add Another Area</span>
                </button>

              </div>
            </div>

            {/* Step 3: Clip Settings */}
            <div>
              <div style={{ fontSize: '14px', fontWeight: 700, marginBottom: '10px' }}>
                3. Clip Settings
              </div>

              {/* ── 2-Option Layout Feature Selector ── */}
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '11px', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>
                  Podcast Layout Feature
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
                  <button
                    id="feature-standard-camera-following-btn"
                    type="button"
                    onClick={() => {
                      setSelectedFeature('camera_following');
                      setSelectedShotId(null);
                    }}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '8px',
                      border: selectedFeature === 'camera_following' ? '2px solid #3b82f6' : '1px solid rgba(255, 255, 255, 0.12)',
                      backgroundColor: selectedFeature === 'camera_following' ? 'rgba(59, 130, 246, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                      color: '#fff',
                      cursor: 'pointer',
                      textAlign: 'left',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ fontSize: '12px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px', color: selectedFeature === 'camera_following' ? '#93c5fd' : '#f8fafc' }}>
                      <span>📱</span>
                      <span>Standard</span>
                    </div>
                    <div style={{ fontSize: '10px', color: '#94a3b8', lineHeight: 1.3 }}>
                      Continuous Camera Follower
                    </div>
                  </button>

                  <button
                    id="feature-ai-smart-director-btn"
                    type="button"
                    onClick={() => {
                      setSelectedFeature('visibility_driven');
                    }}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '8px',
                      border: selectedFeature === 'visibility_driven' ? '2px solid #8b5cf6' : '1px solid rgba(255, 255, 255, 0.12)',
                      backgroundColor: selectedFeature === 'visibility_driven' ? 'rgba(139, 92, 246, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                      color: '#fff',
                      cursor: 'pointer',
                      textAlign: 'left',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ fontSize: '12px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px', color: selectedFeature === 'visibility_driven' ? '#c4b5fd' : '#f8fafc' }}>
                      <span>⚡</span>
                      <span>AI Smart Director</span>
                    </div>
                    <div style={{ fontSize: '10px', color: '#cbd5e1', lineHeight: 1.3 }}>
                      Dynamic Cuts (A / B / Side-by-Side)
                    </div>
                  </button>
                </div>

                {/* Compatibility select for legacy/automated test contracts */}
                <select
                  id="podcast-layout-mode-select"
                  aria-hidden="true"
                  value={selectedFeature}
                  onChange={(e) => setSelectedFeature(e.target.value as any)}
                  style={{ display: 'none' }}
                >
                  <option value="camera_following">Standard (Continuous Camera Follower)</option>
                  <option value="visibility_driven">AI Smart Director (Dynamic Cuts: A / B / Side-by-Side)</option>
                  {/* Stacked Split (2 Speakers) [9:16] */}
                </select>

                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: selectedFeature === 'visibility_driven' ? 'rgba(139, 92, 246, 0.15)' : 'rgba(59, 130, 246, 0.15)',
                    border: selectedFeature === 'visibility_driven' ? '1px solid rgba(139, 92, 246, 0.3)' : '1px solid rgba(59, 130, 246, 0.3)',
                    color: selectedFeature === 'visibility_driven' ? '#c4b5fd' : '#93c5fd',
                    fontSize: '11px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <span>{selectedFeature === 'visibility_driven' ? '⚡' : '🎬'}</span>
                  <span>
                    {selectedFeature === 'visibility_driven'
                      ? 'AI Smart Director: Dynamically cuts between Speaker A close-up, Speaker B close-up, and Side-by-Side (with blurred live backdrop).'
                      : 'Standard: Smooth continuous 9:16 vertical view keeps speakers centered without sudden cuts. Instant generate.'}
                  </span>
                </div>
              </div>

              {/* Duration Dropdown */}
              <div style={{ marginBottom: '10px' }}>
                <label style={{ fontSize: '11px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>
                  Clip Duration
                </label>
                <select
                  value={clipDuration}
                  onChange={e => setClipDuration(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                >
                  <option value={15} style={{ background: '#0f172a' }}>15s</option>
                  <option value={30} style={{ background: '#0f172a' }}>30s (Recommended)</option>
                  <option value={45} style={{ background: '#0f172a' }}>45s</option>
                  <option value={49} style={{ background: '#0f172a' }}>49s (Optimal Shorts)</option>
                  <option value={60} style={{ background: '#0f172a' }}>60s</option>
                </select>
              </div>

              {/* Style Dropdown */}
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '11px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>
                  Processing Style
                </label>
                <select
                  value={clipStyle}
                  onChange={e => setClipStyle(e.target.value as any)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                >
                  <option value="ai_highlights" style={{ background: '#0f172a' }}>
                    Auto (AI Highlights)
                  </option>
                  <option value="equal_split" style={{ background: '#0f172a' }}>
                    Equal Split (Full Coverage)
                  </option>
                </select>
              </div>

              {/* Publish Destinations Selector */}
              <div style={{ marginBottom: '16px' }}>
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '11px',
                    fontWeight: 600,
                    color: '#94a3b8',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    marginBottom: '6px',
                  }}
                >
                  <span>Publish Destinations</span>
                  <span style={{ color: selectedDestinationIds.length > 0 ? '#818cf8' : '#64748b', fontSize: '10px' }}>
                    {selectedDestinationIds.length === 0 ? 'No destination' : `${selectedDestinationIds.length} selected`}
                  </span>
                </label>
                {destinations.length === 0 ? (
                  <p style={{ fontSize: '11px', color: '#64748b', margin: 0, fontStyle: 'italic' }}>No channels connected</p>
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      maxHeight: '120px',
                      overflowY: 'auto',
                      padding: '4px',
                      borderRadius: '6px',
                      background: 'rgba(15, 23, 42, 0.6)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                    }}
                  >
                    {destinations.map((d) => {
                      const isChecked = selectedDestinationIds.includes(d.id);
                      return (
                        <label
                          key={d.id}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            padding: '4px 8px',
                            borderRadius: '4px',
                            background: isChecked ? 'rgba(79, 70, 229, 0.15)' : 'transparent',
                            cursor: 'pointer',
                            fontSize: '11px',
                            color: '#e2e8f0',
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {
                              setSelectedDestinationIds((prev) =>
                                isChecked ? prev.filter((id) => id !== d.id) : [...prev, d.id]
                              );
                            }}
                            style={{ accentColor: '#4f46e5' }}
                          />
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {d.channel_name || 'Channel'}
                          </span>
                          <span style={{ fontSize: '9px', color: d.has_outro ? '#34d399' : '#64748b' }}>
                            {d.has_outro ? `${d.outro?.outro_type === 'video' ? '🎬' : '🖼️'} ${d.outro?.duration_seconds || 5}s` : 'None'}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Error Display */}
              {(localError || errorMessage) && (
                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#f87171',
                    fontSize: '11px',
                    marginBottom: '12px',
                  }}
                >
                  {localError || errorMessage}
                </div>
              )}

              {/* Generate Clips CTA */}
              <button
                id={selectedFeature === 'visibility_driven' ? 'generate-advanced-clips-btn' : 'generate-clips-btn'}
                type="button"
                onClick={handleSubmit}
                disabled={isSubmitting || (sourceType === 'file' ? !selectedFile : !videoId) || regions.length === 0}
                style={{
                  width: '100%',
                  padding: '12px',
                  borderRadius: '8px',
                  background:
                    isSubmitting || (sourceType === 'file' ? !selectedFile : !videoId) || regions.length === 0
                      ? 'rgba(59, 130, 246, 0.4)'
                      : selectedFeature === 'visibility_driven'
                      ? 'linear-gradient(135deg, #4f46e5, #7c3aed)'
                      : 'linear-gradient(135deg, #2563eb, #3b82f6)',
                  color: '#fff',
                  fontSize: '14px',
                  fontWeight: 700,
                  border: 'none',
                  cursor:
                    isSubmitting || (sourceType === 'file' ? !selectedFile : !videoId) || regions.length === 0
                      ? 'not-allowed'
                      : 'pointer',
                  boxShadow: selectedFeature === 'visibility_driven' ? '0 4px 14px rgba(99, 102, 241, 0.4)' : '0 4px 14px rgba(37, 99, 235, 0.4)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                {isSubmitting ? (
                  <span>⏳ Creating Podcast Clips...</span>
                ) : selectedFeature === 'visibility_driven' ? (
                  <span>⚡ Generate Advanced Clips</span>
                ) : (
                  <span>⚡ Generate Clips</span>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* ── Bottom 5-Step Workflow Breadcrumb ── */}
        <div
          style={{
            padding: '8px 24px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            display: 'grid',
            gridTemplateColumns: 'repeat(5, 1fr)',
            gap: '12px',
            flexShrink: 0,
          }}
        >
          {[
            {
              num: 1,
              title: '1. Paste YouTube Link',
              desc: 'Paste the link to your podcast or interview video.',
              icon: '🔗',
            },
            {
              num: 2,
              title: '2. Watch & Select Areas',
              desc: 'Play video in popup and select the areas (e.g., speakers) to include.',
              icon: '▶️',
            },
            {
              num: 3,
              title: '3. Set Clip Options',
              desc: 'Choose duration, style, and composition.',
              icon: '⚙️',
            },
            {
              num: 4,
              title: '4. AI Processing',
              desc: 'Our pipeline finds the best moments using your selected areas.',
              icon: '✨',
            },
            {
              num: 5,
              title: '5. Get Your Clips',
              desc: 'Receive ready-to-publish vertical clips with only chosen areas.',
              icon: '✅',
            },
          ].map(step => (
            <div
              key={step.num}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
              }}
            >
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: '#93c5fd',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <span>{step.icon}</span>
                <span>{step.title}</span>
              </div>
              <div style={{ fontSize: '10px', color: '#64748b', lineHeight: 1.25 }}>
                {step.desc}
              </div>
            </div>
          ))}
        </div>
      </div>
  );

  if (isInline) {
    return studioContent;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="podcast-modal-title"
      aria-describedby="podcast-modal-description"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(5, 8, 16, 0.85)',
        backdropFilter: 'blur(10px)',
        padding: '16px',
        overflow: 'hidden',
      }}
    >
      {studioContent}
    </div>
  );
}
