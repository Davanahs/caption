'use client';

import React, { useRef, useEffect, useState, useCallback } from 'react';
import {
  NormalizedRect,
  FacecamPreset,
  ResizeHandle,
  DEFAULT_CANVAS_WIDTH,
  DEFAULT_CANVAS_HEIGHT,
  MIN_ROI_SIZE,
  applyDrag,
  calculateResize,
  clampNormalizedRect,
  getFacecamPreset,
  getDefaultFacecamOutputRect,
  toEvenPixels,
  toCanvasOverlay,
  calculateGameplayFraming,
} from '@/lib/gamingCoordinates';

export interface GamingCompositeCanvasProps {
  /** Reference to the active source <video> element */
  videoRef?: React.RefObject<HTMLVideoElement | null>;
  /** Direct HTML5 <video> element instance (alternative to videoRef) */
  videoElement?: HTMLVideoElement | null;
  /** Normalized source ROI for Layer 1 gameplay */
  gameplayRoi: NormalizedRect;
  /** Normalized source ROI for Layer 2 facecam */
  facecamRoi: NormalizedRect;
  /** Current normalized canvas placement for facecam PiP overlay */
  facecamOutputRect: NormalizedRect;
  /** Current active preset or 'custom' if manually dragged/resized */
  facecamPlacement: FacecamPreset | 'custom';
  /** Callback fired when facecam overlay is dragged, resized, or preset selected */
  onFacecamOutputRectChange?: (rect: NormalizedRect, placement?: FacecamPreset | 'custom') => void;
  /** Callback fired when preset button is clicked */
  onFacecamPlacementChange?: (preset: FacecamPreset) => void;
  /** Dual-signature callback for placement and rect update */
  onPlacementChange?: (preset: FacecamPreset | 'custom', rect: NormalizedRect) => void;
  /** Callback fired when reset button is clicked */
  onResetFacecamOutput?: () => void;
  /** Callback fired when reset button is clicked (alternative name) */
  onResetFacecam?: () => void;
  /** Canvas width in virtual pixels (default 1080) */
  canvasWidth?: number;
  /** Canvas height in virtual pixels (default 1920) */
  canvasHeight?: number;
  /** Optional YouTube video ID to render frame preview on canvas */
  youtubeVideoId?: string | null;
  /** Source video natural width */
  videoWidth?: number;
  /** Source video natural height */
  videoHeight?: number;
  /** Whether the video is currently playing */
  isPlaying?: boolean;
  /** Optional container CSS class */
  className?: string;
  /** Whether to show preset buttons (default true) */
  showPresets?: boolean;
  /** Whether to show reset button (default true) */
  showReset?: boolean;
  /** Whether controls are disabled */
  disabled?: boolean;
}

export default function GamingCompositeCanvas({
  videoRef,
  videoElement,
  gameplayRoi,
  facecamRoi,
  facecamOutputRect,
  facecamPlacement,
  onFacecamOutputRectChange,
  onFacecamPlacementChange,
  onPlacementChange,
  onResetFacecamOutput,
  onResetFacecam,
  canvasWidth = DEFAULT_CANVAS_WIDTH,
  canvasHeight = DEFAULT_CANVAS_HEIGHT,
  youtubeVideoId = null,
  videoWidth,
  videoHeight,
  isPlaying = false,
  className = '',
  showPresets = true,
  showReset = true,
  disabled = false,
}: GamingCompositeCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Optional frame preview image for YouTube videos
  const ytImageRef = useRef<HTMLImageElement | null>(null);
  const [ytImageLoaded, setYtImageLoaded] = useState(false);

  useEffect(() => {
    if (!youtubeVideoId) {
      ytImageRef.current = null;
      setYtImageLoaded(false);
      return;
    }
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      ytImageRef.current = img;
      setYtImageLoaded(true);
    };
    img.onerror = () => {
      const fallbackImg = new Image();
      fallbackImg.crossOrigin = 'anonymous';
      fallbackImg.onload = () => {
        ytImageRef.current = fallbackImg;
        setYtImageLoaded(true);
      };
      fallbackImg.src = `https://img.youtube.com/vi/${youtubeVideoId}/hqdefault.jpg`;
    };
    img.src = `https://img.youtube.com/vi/${youtubeVideoId}/hqdefault.jpg`;
  }, [youtubeVideoId]);

  // Dragging state for Facecam PiP overlay
  const [dragState, setDragState] = useState<{
    type: 'move' | 'resize';
    handle?: ResizeHandle;
    startX: number;
    startY: number;
    initialRect: NormalizedRect;
  } | null>(null);

  // Helper to notify changes across both callback styles
  const notifyChange = useCallback(
    (nextRect: NormalizedRect, nextPlacement: FacecamPreset | 'custom') => {
      onFacecamOutputRectChange?.(nextRect, nextPlacement);
      onPlacementChange?.(nextPlacement, nextRect);
    },
    [onFacecamOutputRectChange, onPlacementChange]
  );

  // ── Core Frame Rendering Function ──
  const renderFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const activeVideo = (videoRef ? videoRef.current : videoElement) || null;
    const isVideoReady =
      activeVideo &&
      activeVideo.readyState >= 2 &&
      activeVideo.videoWidth > 0 &&
      activeVideo.videoHeight > 0;

    const sourceDrawable: CanvasImageSource | null = isVideoReady
      ? activeVideo
      : ytImageRef.current && ytImageLoaded
      ? ytImageRef.current
      : null;

    if (!sourceDrawable) {
      // High-contrast neutral background placeholder when video is not ready
      ctx.fillStyle = '#090d16';
      ctx.fillRect(0, 0, canvasWidth, canvasHeight);

      // Subtle 9:16 vertical guide
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 2;
      ctx.strokeRect(40, 40, canvasWidth - 80, canvasHeight - 80);

      // Informative text placeholder
      ctx.fillStyle = '#64748b';
      ctx.font = 'bold 36px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('9:16 Composite Canvas', canvasWidth / 2, canvasHeight / 2 - 20);
      ctx.font = '24px sans-serif';
      ctx.fillText('Awaiting video playback...', canvasWidth / 2, canvasHeight / 2 + 30);
      return;
    }

    const srcW = isVideoReady
      ? (activeVideo!.videoWidth || videoWidth || 1920)
      : (ytImageRef.current?.naturalWidth || 1920);
    const srcH = isVideoReady
      ? (activeVideo!.videoHeight || videoHeight || 1080)
      : (ytImageRef.current?.naturalHeight || 1080);

    // 1. Calculate Crops & Overlay Dest
    const gCrop = toEvenPixels(gameplayRoi, srcW, srcH);
    const fCrop = toEvenPixels(facecamRoi, srcW, srcH);
    const fDest = toCanvasOverlay(facecamOutputRect, canvasWidth, canvasHeight);

    // Calculate gameplay framing metadata for scale-to-fill
    const framing = calculateGameplayFraming(gCrop, canvasWidth, canvasHeight);
    const subCrop = framing.sourceSubCrop || gCrop;

    // 2. Clear canvas and configure high-quality bicubic interpolation
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';

    // 3. Layer 1: Gameplay Scale-to-Fill Framing
    // Draw gameplay crop filling 1080x1920 canvas without stretching
    ctx.drawImage(
      sourceDrawable,
      subCrop.x,
      subCrop.y,
      subCrop.w,
      subCrop.h,
      0,
      0,
      canvasWidth,
      canvasHeight
    );

    // 4. Layer 2: Facecam PiP Overlay (Bounded & Clipped)
    ctx.save();
    ctx.beginPath();
    ctx.rect(fDest.x, fDest.y, fDest.w, fDest.h);
    ctx.clip();
    ctx.drawImage(
      sourceDrawable,
      fCrop.x,
      fCrop.y,
      fCrop.w,
      fCrop.h,
      fDest.x,
      fDest.y,
      fDest.w,
      fDest.h
    );
    ctx.restore();
  }, [videoRef, videoElement, ytImageLoaded, gameplayRoi, facecamRoi, facecamOutputRect, canvasWidth, canvasHeight, videoWidth, videoHeight]);

  useEffect(() => {
    renderFrame();
  }, [ytImageLoaded, renderFrame]);

  // ── 60fps Playback & Scrubbing Sync Loop ──
  useEffect(() => {
    let animId: number | null = null;
    let rvfcId: number | null = null;
    let isMounted = true;

    const getActiveVideo = (): HTMLVideoElement | null => {
      return (videoElement || (videoRef ? videoRef.current : null) || null);
    };

    const loop = () => {
      if (!isMounted) return;
      renderFrame();

      const vid = getActiveVideo();
      const isVideoPlaying = (vid && !vid.paused && !vid.ended);
      if (isVideoPlaying || isPlaying) {
        if (vid && 'requestVideoFrameCallback' in vid && typeof (vid as any).requestVideoFrameCallback === 'function') {
          rvfcId = (vid as any).requestVideoFrameCallback(() => loop());
        } else {
          animId = requestAnimationFrame(loop);
        }
      }
    };

    // Render immediately on prop change
    renderFrame();

    const activeVideo = getActiveVideo();
    // Event listeners for scrubbing, seeking, and playback state changes
    if (activeVideo) {
      const handleSeekedOrTimeUpdate = () => renderFrame();
      const handlePlay = () => loop();

      activeVideo.addEventListener('seeked', handleSeekedOrTimeUpdate);
      activeVideo.addEventListener('timeupdate', handleSeekedOrTimeUpdate);
      activeVideo.addEventListener('play', handlePlay);
      activeVideo.addEventListener('pause', handleSeekedOrTimeUpdate);
      activeVideo.addEventListener('loadeddata', handleSeekedOrTimeUpdate);
      activeVideo.addEventListener('canplay', handleSeekedOrTimeUpdate);

      if (isPlaying || (!activeVideo.paused && !activeVideo.ended)) {
        loop();
      }

      return () => {
        isMounted = false;
        if (animId !== null) cancelAnimationFrame(animId);
        if (rvfcId !== null && 'cancelVideoFrameCallback' in activeVideo) {
          (activeVideo as any).cancelVideoFrameCallback(rvfcId);
        }
        activeVideo.removeEventListener('seeked', handleSeekedOrTimeUpdate);
        activeVideo.removeEventListener('timeupdate', handleSeekedOrTimeUpdate);
        activeVideo.removeEventListener('play', handlePlay);
        activeVideo.removeEventListener('pause', handleSeekedOrTimeUpdate);
        activeVideo.removeEventListener('loadeddata', handleSeekedOrTimeUpdate);
        activeVideo.removeEventListener('canplay', handleSeekedOrTimeUpdate);
      };
    } else if (isPlaying) {
      loop();
      return () => {
        isMounted = false;
        if (animId !== null) cancelAnimationFrame(animId);
      };
    }

    return () => {
      isMounted = false;
      if (animId !== null) cancelAnimationFrame(animId);
    };
  }, [videoRef, videoElement, isPlaying, renderFrame]);

  // ── Interactive Facecam Drag Handlers ──
  const handlePointerDown = (e: React.PointerEvent, type: 'move' | 'resize', handle?: ResizeHandle) => {
    if (disabled) return;
    e.preventDefault();
    e.stopPropagation();
    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    } catch (_) {}

    setDragState({
      type,
      handle,
      startX: e.clientX,
      startY: e.clientY,
      initialRect: { ...facecamOutputRect },
    });
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!dragState || !containerRef.current || disabled) return;
    const rect = containerRef.current.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const deltaX = (e.clientX - dragState.startX) / rect.width;
    const deltaY = (e.clientY - dragState.startY) / rect.height;

    if (dragState.type === 'move') {
      const nextRect = applyDrag(dragState.initialRect, deltaX, deltaY);
      notifyChange(nextRect, 'custom');
    } else if (dragState.type === 'resize' && dragState.handle) {
      const resized = calculateResize(dragState.initialRect, dragState.handle, deltaX, deltaY, MIN_ROI_SIZE);
      const clamped = clampNormalizedRect(resized, MIN_ROI_SIZE);
      notifyChange(clamped, 'custom');
    }
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (dragState) {
      try {
        (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
      } catch (_) {}
      setDragState(null);
    }
  };

  // ── Preset Selection ──
  const handleSelectPreset = (preset: FacecamPreset) => {
    if (disabled) return;
    const nextRect = getFacecamPreset(preset, facecamOutputRect.width, facecamOutputRect.height);
    notifyChange(nextRect, preset);
    onFacecamPlacementChange?.(preset);
  };

  // ── Reset Handler ──
  const handleReset = () => {
    if (disabled) return;
    const defaultRect = getDefaultFacecamOutputRect('top-right');
    notifyChange(defaultRect, 'top-right');
    onResetFacecamOutput?.();
    onResetFacecam?.();
  };

  // Presets definition
  const PRESET_BUTTONS: { key: FacecamPreset; label: string; icon: string }[] = [
    { key: 'top-left', label: 'Top-Left', icon: '↖' },
    { key: 'top-right', label: 'Top-Right', icon: '↗' },
    { key: 'bottom-left', label: 'Bottom-Left', icon: '↙' },
    { key: 'bottom-right', label: 'Bottom-Right', icon: '↘' },
  ];

  return (
    <div className={`flex flex-col gap-3 w-full ${className}`} id="gaming-composite-canvas-container">
      {/* ── Facecam Preset Controls: Compact 2×2 grid + Reset ── */}
      {showPresets && (
        <div
          className="flex items-center gap-2 p-2 rounded-2xl bg-slate-900/90 border border-slate-800/80 shadow-md"
          id="facecam-placement-presets"
        >
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 px-1 shrink-0">PiP:</span>
          {/* 2×2 grid of preset buttons */}
          <div className="grid grid-cols-2 gap-1 p-0.5 rounded-xl bg-slate-950/90 border border-slate-800/80 shadow-inner">
            {PRESET_BUTTONS.map(({ key, label, icon }) => {
              const isActive = facecamPlacement === key;
              return (
                <button
                  key={key}
                  type="button"
                  id={`preset-btn-${key}`}
                  onClick={() => handleSelectPreset(key)}
                  disabled={disabled}
                  aria-pressed={isActive}
                  title={label}
                  className={`h-8 px-2.5 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 border ${
                    isActive
                      ? 'bg-amber-500/25 text-amber-300 border-amber-500/60 shadow ring-1 ring-amber-400/40'
                      : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <span className="text-sm leading-none">{icon}</span>
                  <span className="hidden sm:inline text-[11px]">{label}</span>
                </button>
              );
            })}
          </div>

          {showReset && (
            <button
              type="button"
              id="facecam-reset-btn"
              onClick={handleReset}
              disabled={disabled}
              className="h-8 w-8 ml-auto rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/90 border border-slate-800/80 transition-all flex items-center justify-center shrink-0"
              title="Reset Facecam Placement to Default"
            >
              <span>↺</span>
            </button>
          )}
        </div>
      )}

      {/* ── 9:16 Canvas Monitor Viewport ── */}
      <div className="flex justify-center items-center w-full h-full py-1">
        <div
          ref={containerRef}
          id="composite-canvas-9-16-viewport"
          className="relative rounded-2xl overflow-hidden border border-slate-700/80 bg-black shadow-2xl shadow-black ring-1 ring-white/10 select-none"
          style={{
            maxHeight: '100%',
            maxWidth: '100%',
            height: '100%',
            aspectRatio: '9 / 16',
          }}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        >
          {/* Real-time HTML5 9:16 Canvas */}
          <canvas
            ref={canvasRef}
            id="gaming-composite-canvas"
            width={canvasWidth}
            height={canvasHeight}
            className="w-full h-full object-contain block pointer-events-none"
          />

          {/* Interactive Facecam PiP Overlay Box */}
          {Boolean(videoElement || (videoRef && videoRef.current) || youtubeVideoId) && (
            <div
              id="facecam-pip-overlay-box"
            tabIndex={disabled ? -1 : 0}
            role="region"
            aria-label="Facecam Picture-in-Picture overlay. Drag to reposition."
            onPointerDown={(e) => handlePointerDown(e, 'move')}
            style={{
              position: 'absolute',
              left: `${facecamOutputRect.x * 100}%`,
              top: `${facecamOutputRect.y * 100}%`,
              width: `${facecamOutputRect.width * 100}%`,
              height: `${facecamOutputRect.height * 100}%`,
              cursor: disabled ? 'default' : 'move',
              boxSizing: 'border-box',
            }}
            className="border-2 border-amber-400/90 rounded-sm shadow-xl group hover:border-amber-300 transition-[border-color]"
          >
            {/* PiP Badge Label */}
            <div className="absolute top-0 left-0 bg-amber-500 text-slate-950 font-bold text-[9px] px-1.5 py-0.5 rounded-br pointer-events-none tracking-tight uppercase shadow-sm">
              Facecam PiP
            </div>

            {/* 4 Corner Resize Handles */}
            {!disabled && (
              <>
                {/* Northwest (Top-Left) */}
                <div
                  id="handle-nw"
                  data-handle="nw"
                  role="button"
                  tabIndex={0}
                  aria-label="Resize facecam from top-left handle"
                  onPointerDown={(e) => handlePointerDown(e, 'resize', 'nw')}
                  className="absolute -top-1.5 -left-1.5 w-3 h-3 bg-white border-2 border-amber-500 rounded-sm cursor-nwse-resize shadow hover:scale-125 transition-transform"
                />
                {/* Northeast (Top-Right) */}
                <div
                  id="handle-ne"
                  data-handle="ne"
                  role="button"
                  tabIndex={0}
                  aria-label="Resize facecam from top-right handle"
                  onPointerDown={(e) => handlePointerDown(e, 'resize', 'ne')}
                  className="absolute -top-1.5 -right-1.5 w-3 h-3 bg-white border-2 border-amber-500 rounded-sm cursor-nesw-resize shadow hover:scale-125 transition-transform"
                />
                {/* Southeast (Bottom-Right) */}
                <div
                  id="handle-se"
                  data-handle="se"
                  role="button"
                  tabIndex={0}
                  aria-label="Resize facecam from bottom-right handle"
                  onPointerDown={(e) => handlePointerDown(e, 'resize', 'se')}
                  className="absolute -bottom-1.5 -right-1.5 w-3 h-3 bg-white border-2 border-amber-500 rounded-sm cursor-nwse-resize shadow hover:scale-125 transition-transform"
                />
                {/* Southwest (Bottom-Left) */}
                <div
                  id="handle-sw"
                  data-handle="sw"
                  role="button"
                  tabIndex={0}
                  aria-label="Resize facecam from bottom-left handle"
                  onPointerDown={(e) => handlePointerDown(e, 'resize', 'sw')}
                  className="absolute -bottom-1.5 -left-1.5 w-3 h-3 bg-white border-2 border-amber-500 rounded-sm cursor-nesw-resize shadow hover:scale-125 transition-transform"
                />
              </>
            )}
          </div>
          )}
        </div>
      </div>

      {/* Telemetry info bar */}
      <div className="flex items-center justify-between text-[11px] text-slate-400 px-3 py-1.5 font-mono bg-slate-900/60 rounded-xl border border-slate-800/60">
        <span>Output: 1080×1920 (9:16)</span>
        <span className="text-amber-400 font-sans font-medium">
          Placement: {facecamPlacement === 'custom' ? 'Custom' : facecamPlacement}
        </span>
      </div>
    </div>
  );
}
