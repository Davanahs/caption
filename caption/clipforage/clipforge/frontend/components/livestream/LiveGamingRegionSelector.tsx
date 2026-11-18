'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  NormalizedRect,
  FacecamPreset,
  ResizeHandle,
  MIN_ROI_SIZE,
  applyDrag,
  calculateResize,
  clampNormalizedRect,
  calculateRenderOffsets,
  getDefaultGameplayRoi,
  getDefaultFacecamRoi,
  getDefaultFacecamOutputRect,
} from '@/lib/gamingCoordinates';
import { autoDetectLiveStreamFacecam } from '@/lib/api';
import GamingCompositeCanvas from '@/components/gaming/GamingCompositeCanvas';

const handleCursorMap: Record<ResizeHandle, string> = {
  nw: 'nwse-resize',
  ne: 'nesw-resize',
  se: 'nwse-resize',
  sw: 'nesw-resize',
  n: 'ns-resize',
  s: 'ns-resize',
  e: 'ew-resize',
  w: 'ew-resize',
};

export interface LiveGamingRegionSelectorProps {
  youtubeUrl?: string;
  youtubeVideoId: string | null;
  thumbnailUrl?: string | null;
  gameplayRoi: NormalizedRect;
  facecamRoi: NormalizedRect;
  facecamPlacement: FacecamPreset | 'custom';
  facecamOutputRect: NormalizedRect;
  onChangeGameplayRoi: (rect: NormalizedRect) => void;
  onChangeFacecamRoi: (rect: NormalizedRect) => void;
  onChangePlacement: (preset: FacecamPreset, rect: NormalizedRect) => void;
  onResetBoxes: () => void;
  onStartMonitoring?: () => void;
  isStarting?: boolean;
  canStart?: boolean;
  startLabel?: string;
}

export default function LiveGamingRegionSelector({
  youtubeUrl,
  youtubeVideoId,
  thumbnailUrl,
  gameplayRoi,
  facecamRoi,
  facecamPlacement,
  facecamOutputRect,
  onChangeGameplayRoi,
  onChangeFacecamRoi,
  onChangePlacement,
  onResetBoxes,
  onStartMonitoring,
  isStarting = false,
  canStart = false,
  startLabel,
}: LiveGamingRegionSelectorProps) {
  const [activeTool, setActiveTool] = useState<'gameplay' | 'facecam'>('gameplay');
  const [aspectLock, setAspectLock] = useState<'free' | '9:16'>('free');
  const [isDetecting, setIsDetecting] = useState(false);
  const [detectMsg, setDetectMsg] = useState<string | null>(null);

  const handleAutoDetect = async () => {
    const target = youtubeUrl || (youtubeVideoId ? `https://www.youtube.com/watch?v=${youtubeVideoId}` : '');
    if (!target) return;
    setIsDetecting(true);
    setDetectMsg(null);
    try {
      const res = await autoDetectLiveStreamFacecam(target);
      if (res && res.success) {
        if (res.facecam_roi) onChangeFacecamRoi(res.facecam_roi);
        if (res.gameplay_roi) onChangeGameplayRoi(res.gameplay_roi);
        if (res.facecam_placement) {
          const newRect = getDefaultFacecamOutputRect(res.facecam_placement);
          onChangePlacement(res.facecam_placement, newRect);
        }
        setDetectMsg(res.message || 'Streamer facecam detected successfully!');
        setTimeout(() => setDetectMsg(null), 4500);
      }
    } catch (err: any) {
      setDetectMsg('Auto-detection: ' + (err.message || 'Default facecam applied'));
      setTimeout(() => setDetectMsg(null), 4500);
    } finally {
      setIsDetecting(false);
    }
  };
  const [dragState, setDragState] = useState<{
    roiType: 'gameplay' | 'facecam';
    opType: 'move' | 'resize';
    handle?: ResizeHandle;
    startX: number;
    startY: number;
    initialRect: NormalizedRect;
  } | null>(null);

  const videoContainerRef = useRef<HTMLDivElement>(null);
  const justDraggedRef = useRef<boolean>(false);

  // Standard video aspect ratio assumed 16:9 for livestreams
  const videoDimensions = { width: 1920, height: 1080 };

  // Pointer down on ROI box or handle
  const handleRoiPointerDown = (
    e: React.PointerEvent,
    roiType: 'gameplay' | 'facecam',
    opType: 'move' | 'resize',
    handle?: ResizeHandle
  ) => {
    e.preventDefault();
    e.stopPropagation();
    setActiveTool(roiType);
    const initialRect = roiType === 'gameplay' ? { ...gameplayRoi } : { ...facecamRoi };
    setDragState({ roiType, opType, handle, startX: e.clientX, startY: e.clientY, initialRect });
  };

  // Window drag listeners
  useEffect(() => {
    if (!dragState) return;

    const handlePointerMove = (e: PointerEvent) => {
      if (!videoContainerRef.current) return;
      justDraggedRef.current = true;
      const containerRect = videoContainerRef.current.getBoundingClientRect();
      if (containerRect.width <= 0 || containerRect.height <= 0) return;

      const offsets = calculateRenderOffsets(
        containerRect.width,
        containerRect.height,
        videoDimensions.width,
        videoDimensions.height
      );
      if (offsets.renderWidth <= 0 || offsets.renderHeight <= 0) return;

      const deltaNormX = (e.clientX - dragState.startX) / offsets.renderWidth;
      const deltaNormY = (e.clientY - dragState.startY) / offsets.renderHeight;

      let updatedRect: NormalizedRect;
      if (dragState.opType === 'move') {
        updatedRect = applyDrag(dragState.initialRect, deltaNormX, deltaNormY);
      } else if (dragState.opType === 'resize' && dragState.handle) {
        let resized = calculateResize(
          dragState.initialRect,
          dragState.handle,
          deltaNormX,
          deltaNormY,
          MIN_ROI_SIZE
        );

        // If aspectLock is strictly '9:16' and it is gameplay, apply aspect ratio lock
        if (dragState.roiType === 'gameplay' && aspectLock === '9:16') {
          const normAspect = (9 / 16) * (videoDimensions.height / videoDimensions.width);
          const { x: x0, y: y0, width: w0, height: h0 } = dragState.initialRect;
          const h = dragState.handle;
          let w = resized.width;
          let ht = resized.height;
          switch (h) {
            case 'se': {
              ht = Math.min(ht, (1.0 - x0) / normAspect, 1.0 - y0);
              w = ht * normAspect;
              resized = { x: x0, y: y0, width: w, height: ht };
              break;
            }
            case 'ne': {
              w = Math.min(w, 1.0 - x0);
              ht = w / normAspect;
              let nY = y0 + h0 - ht;
              if (nY < 0) {
                nY = 0;
                ht = y0 + h0;
                w = ht * normAspect;
              }
              resized = { x: x0, y: nY, width: w, height: ht };
              break;
            }
            case 'sw': {
              ht = Math.min(ht, 1.0 - y0);
              w = ht * normAspect;
              let nX = x0 + w0 - w;
              if (nX < 0) {
                nX = 0;
                w = x0 + w0;
                ht = w / normAspect;
              }
              resized = { x: nX, y: y0, width: w, height: ht };
              break;
            }
            case 'nw': {
              w = Math.min(w, x0 + w0);
              ht = w / normAspect;
              let nY2 = y0 + h0 - ht;
              let nX2 = x0 + w0 - w;
              if (nY2 < 0) {
                nY2 = 0;
                ht = y0 + h0;
                w = ht * normAspect;
                nX2 = x0 + w0 - w;
              }
              resized = { x: nX2, y: nY2, width: w, height: ht };
              break;
            }
            case 'n': {
              w = ht * normAspect;
              const cX = x0 + w0 / 2;
              const nX3 = Math.max(0, Math.min(1 - w, cX - w / 2));
              resized = { x: nX3, y: resized.y, width: w, height: ht };
              break;
            }
            case 's': {
              w = ht * normAspect;
              const cX2 = x0 + w0 / 2;
              const nX4 = Math.max(0, Math.min(1 - w, cX2 - w / 2));
              resized = { x: nX4, y: y0, width: w, height: ht };
              break;
            }
            case 'w': {
              ht = w / normAspect;
              const cY = y0 + h0 / 2;
              const nY3 = Math.max(0, Math.min(1 - ht, cY - ht / 2));
              resized = { x: resized.x, y: nY3, width: w, height: ht };
              break;
            }
            case 'e': {
              ht = w / normAspect;
              const cY2 = y0 + h0 / 2;
              const nY4 = Math.max(0, Math.min(1 - ht, cY2 - ht / 2));
              resized = { x: x0, y: nY4, width: w, height: ht };
              break;
            }
          }
        }
        updatedRect = clampNormalizedRect(resized, MIN_ROI_SIZE);
      } else {
        return;
      }

      if (dragState.roiType === 'gameplay') {
        onChangeGameplayRoi(updatedRect);
      } else {
        onChangeFacecamRoi(updatedRect);
      }
    };

    const handlePointerUp = () => {
      setDragState(null);
      setTimeout(() => {
        justDraggedRef.current = false;
      }, 100);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    window.addEventListener('pointercancel', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      window.removeEventListener('pointercancel', handlePointerUp);
    };
  }, [dragState, videoDimensions, aspectLock, onChangeGameplayRoi, onChangeFacecamRoi]);

  // Corner & Edge handle generator
  const renderHandles = (roiType: 'gameplay' | 'facecam', color: string) => {
    const isBoxActive = activeTool === roiType;
    if (!isBoxActive) return null;

    const cornerHandles: { handle: ResizeHandle; style: React.CSSProperties }[] = [
      { handle: 'nw', style: { top: -6, left: -6, width: 12, height: 12, borderRadius: 2 } },
      { handle: 'ne', style: { top: -6, right: -6, width: 12, height: 12, borderRadius: 2 } },
      { handle: 'sw', style: { bottom: -6, left: -6, width: 12, height: 12, borderRadius: 2 } },
      { handle: 'se', style: { bottom: -6, right: -6, width: 12, height: 12, borderRadius: 2 } },
    ];

    const edgeHandles: { handle: ResizeHandle; style: React.CSSProperties }[] = [
      { handle: 'n', style: { top: -5, left: 'calc(50% - 15px)', width: 30, height: 9, borderRadius: 3 } },
      { handle: 's', style: { bottom: -5, left: 'calc(50% - 15px)', width: 30, height: 9, borderRadius: 3 } },
      { handle: 'w', style: { left: -5, top: 'calc(50% - 15px)', width: 9, height: 30, borderRadius: 3 } },
      { handle: 'e', style: { right: -5, top: 'calc(50% - 15px)', width: 9, height: 30, borderRadius: 3 } },
    ];

    return (
      <>
        {cornerHandles.map(({ handle, style }) => (
          <div
            key={handle}
            onPointerDown={(e) => handleRoiPointerDown(e, roiType, 'resize', handle)}
            style={{
              position: 'absolute',
              background: '#fff',
              border: `2px solid ${color}`,
              cursor: handleCursorMap[handle],
              pointerEvents: 'auto',
              boxShadow: '0 2px 8px rgba(0,0,0,0.6)',
              zIndex: 35,
              ...style,
            }}
          />
        ))}
        {edgeHandles.map(({ handle, style }) => (
          <div
            key={handle}
            onPointerDown={(e) => handleRoiPointerDown(e, roiType, 'resize', handle)}
            style={{
              position: 'absolute',
              background: color,
              border: '1px solid #fff',
              cursor: handleCursorMap[handle],
              pointerEvents: 'auto',
              boxShadow: '0 2px 8px rgba(0,0,0,0.6)',
              opacity: 0.9,
              zIndex: 34,
              ...style,
            }}
          />
        ))}
      </>
    );
  };

  return (
    <div
      style={{
        background: 'rgba(15, 17, 26, 0.95)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: 16,
        padding: 24,
        marginBottom: 32,
        boxShadow: '0 12px 40px rgba(0, 0, 0, 0.5)',
      }}
    >
      {/* Header & Tool switcher */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
          marginBottom: 20,
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          paddingBottom: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 10,
              background: 'linear-gradient(135deg, #10b981, #6366f1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 20,
            }}
          >
            🎮
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                Dual-Region Gaming Setup (Gameplay & Streamer ROI)
              </h2>
              <span
                style={{
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#10b981',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '2px 8px',
                  borderRadius: 12,
                }}
              >
                9:16 Gaming PiP
              </span>
            </div>
            <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0' }}>
              Drag the green box over gameplay action, and the amber box over the streamer&apos;s facecam. Both will be cleanly composited into YouTube Shorts.
            </p>
          </div>
        </div>

        {/* Action buttons & Start Clipping button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          {/* Box 1 (Gameplay) Tool Button */}
          <button
            type="button"
            onClick={() => setActiveTool('gameplay')}
            style={{
              background: activeTool === 'gameplay' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.04)',
              border: activeTool === 'gameplay' ? '1px solid #10b981' : '1px solid rgba(255, 255, 255, 0.08)',
              color: activeTool === 'gameplay' ? '#34d399' : '#94a3b8',
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span style={{ width: 10, height: 10, borderRadius: 2, background: '#10b981' }} />
            Box 1: Gameplay ({aspectLock === 'free' ? 'Custom' : '9:16'}) • {Math.round(gameplayRoi.width * 1920)}×{Math.round(gameplayRoi.height * 1080)}
          </button>

          {/* Aspect Ratio Lock Toggle */}
          <button
            type="button"
            onClick={() => setAspectLock((prev) => (prev === 'free' ? '9:16' : 'free'))}
            title={aspectLock === 'free' ? 'Currently Free Custom Resize. Click to lock 9:16 ratio.' : 'Currently Locked 9:16. Click for Free Custom Resize.'}
            style={{
              background: aspectLock === 'free' ? 'rgba(99, 102, 241, 0.2)' : 'rgba(255, 255, 255, 0.04)',
              border: aspectLock === 'free' ? '1px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.08)',
              color: aspectLock === 'free' ? '#a5b4fc' : '#94a3b8',
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span>{aspectLock === 'free' ? '🔓 Free Custom' : '🔒 9:16 Lock'}</span>
          </button>

          {/* Box 2 (Facecam) Tool Button */}
          <button
            type="button"
            onClick={() => setActiveTool('facecam')}
            style={{
              background: activeTool === 'facecam' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(255, 255, 255, 0.04)',
              border: activeTool === 'facecam' ? '1px solid #f59e0b' : '1px solid rgba(255, 255, 255, 0.08)',
              color: activeTool === 'facecam' ? '#fbbf24' : '#94a3b8',
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span style={{ width: 10, height: 10, borderRadius: 2, background: '#f59e0b' }} />
            Box 2: Facecam • {Math.round(facecamRoi.width * 1920)}×{Math.round(facecamRoi.height * 1080)}
          </button>

          {/* AI Auto-Detect Streamer Facecam */}
          <button
            type="button"
            onClick={handleAutoDetect}
            disabled={isDetecting || (!youtubeVideoId && !youtubeUrl)}
            title="Automatically detect streamer facecam and position ROI box using OpenCV / MediaPipe"
            style={{
              background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.25) 0%, rgba(99, 102, 241, 0.25) 100%)',
              border: '1px solid #a855f7',
              color: '#e9d5ff',
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 700,
              cursor: isDetecting || (!youtubeVideoId && !youtubeUrl) ? 'not-allowed' : 'pointer',
              opacity: (!youtubeVideoId && !youtubeUrl) ? 0.5 : 1,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              boxShadow: '0 2px 10px rgba(168, 85, 247, 0.25)',
              transition: 'all 0.2s',
            }}
          >
            {isDetecting ? (
              <>
                <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>⏳</span>
                Detecting Facecam...
              </>
            ) : (
              <>
                <span>✨</span>
                Auto-Detect Facecam (AI)
              </>
            )}
          </button>

          {/* Reset button */}
          <button
            type="button"
            onClick={onResetBoxes}
            style={{
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              color: '#94a3b8',
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            ↺ Reset
          </button>

          {/* Direct Start Action Button */}
          {onStartMonitoring && (
            <button
              type="button"
              onClick={onStartMonitoring}
              disabled={!canStart || isStarting}
              style={{
                background: canStart
                  ? 'linear-gradient(135deg, #ef4444 0%, #8b5cf6 100%)'
                  : 'rgba(255, 255, 255, 0.08)',
                border: 'none',
                borderRadius: 8,
                padding: '7px 16px',
                color: '#fff',
                fontSize: 13,
                fontWeight: 700,
                cursor: canStart && !isStarting ? 'pointer' : 'not-allowed',
                opacity: canStart && !isStarting ? 1 : 0.45,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                boxShadow: canStart ? '0 4px 16px rgba(239, 68, 68, 0.4)' : 'none',
                transition: 'all 0.2s',
              }}
            >
              {isStarting ? (
                <>⏳ Starting Pipeline...</>
              ) : (
                <>⚡ {startLabel || 'Start Monitoring & Clipping'}</>
              )}
            </button>
          )}
        </div>
      </div>

      {/* AI Detection Notification */}
      {detectMsg && (
        <div
          style={{
            background: 'rgba(168, 85, 247, 0.15)',
            border: '1px solid rgba(168, 85, 247, 0.35)',
            color: '#e9d5ff',
            borderRadius: 8,
            padding: '8px 14px',
            fontSize: 12,
            fontWeight: 600,
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span>✨</span>
          <span>{detectMsg}</span>
        </div>
      )}

      {/* Main Studio Grid: Left (16:9 interactive boxes) + Right (9:16 composite canvas preview) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(320px, 1fr) 280px',
          gap: 24,
          alignItems: 'start',
        }}
      >
        {/* Left: 16:9 Source Video Region Selector */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div
            ref={videoContainerRef}
            style={{
              position: 'relative',
              width: '100%',
              aspectRatio: '16/9',
              background: '#070810',
              borderRadius: 12,
              overflow: 'hidden',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              boxShadow: '0 8px 30px rgba(0, 0, 0, 0.6)',
              userSelect: 'none',
            }}
          >
            {/* Background Stream Visual (Iframe or Thumbnail or Placeholder) */}
            {youtubeVideoId ? (
              <iframe
                src={`https://www.youtube.com/embed/${youtubeVideoId}?enablejsapi=1&rel=0&playsinline=1`}
                title="Livestream Source Preview"
                style={{
                  position: 'absolute',
                  inset: 0,
                  width: '100%',
                  height: '100%',
                  border: 'none',
                  pointerEvents: dragState ? 'none' : 'auto',
                }}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              />
            ) : thumbnailUrl ? (
              <img
                src={thumbnailUrl}
                alt="Stream Preview"
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            ) : (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                }}
              >
                <span style={{ fontSize: 48, opacity: 0.3 }}>🎮</span>
                <span style={{ fontSize: 13, color: '#64748b' }}>
                  Paste and validate a YouTube Livestream link above to inspect video frames
                </span>
              </div>
            )}

            {/* Drag shield overlay while dragging */}
            {dragState && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  zIndex: 25,
                  cursor: dragState.opType === 'move' ? 'move' : 'crosshair',
                  pointerEvents: 'auto',
                }}
              />
            )}

            {/* ── Overlaid Interactive Bounding Boxes ── */}
            <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 20 }}>
              {/* Box 1: Gameplay ROI (Emerald) */}
              <div
                onPointerDown={(e) => handleRoiPointerDown(e, 'gameplay', 'move')}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveTool('gameplay');
                }}
                style={{
                  position: 'absolute',
                  left: `${gameplayRoi.x * 100}%`,
                  top: `${gameplayRoi.y * 100}%`,
                  width: `${gameplayRoi.width * 100}%`,
                  height: `${gameplayRoi.height * 100}%`,
                  boxSizing: 'border-box',
                  border: activeTool === 'gameplay' ? '2px solid #10b981' : '2px dashed rgba(16, 185, 129, 0.6)',
                  background: 'rgba(16, 185, 129, 0.12)',
                  boxShadow: activeTool === 'gameplay' ? '0 0 16px rgba(16, 185, 129, 0.3)' : 'none',
                  cursor: 'move',
                  pointerEvents: 'auto',
                  borderRadius: 4,
                }}
              >
                {/* Badge */}
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    background: '#10b981',
                    color: '#fff',
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '2px 7px',
                    borderBottomRightRadius: 4,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <span>🎮 Box 1: Gameplay</span>
                  <span style={{ background: 'rgba(0,0,0,0.3)', padding: '1px 5px', borderRadius: 3, fontFamily: 'monospace' }}>
                    {Math.round(gameplayRoi.width * 1920)}×{Math.round(gameplayRoi.height * 1080)}
                  </span>
                </div>

                {/* 8 Resize Handles: 4 corners + 4 edges */}
                {renderHandles('gameplay', '#10b981')}
              </div>

              {/* Box 2: Facecam / Streamer ROI (Amber) */}
              <div
                onPointerDown={(e) => handleRoiPointerDown(e, 'facecam', 'move')}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveTool('facecam');
                }}
                style={{
                  position: 'absolute',
                  left: `${facecamRoi.x * 100}%`,
                  top: `${facecamRoi.y * 100}%`,
                  width: `${facecamRoi.width * 100}%`,
                  height: `${facecamRoi.height * 100}%`,
                  boxSizing: 'border-box',
                  border: activeTool === 'facecam' ? '2px solid #f59e0b' : '2px dashed rgba(245, 158, 11, 0.6)',
                  background: 'rgba(245, 158, 11, 0.14)',
                  boxShadow: activeTool === 'facecam' ? '0 0 16px rgba(245, 158, 11, 0.3)' : 'none',
                  cursor: 'move',
                  pointerEvents: 'auto',
                  borderRadius: 4,
                }}
              >
                {/* Badge */}
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    background: '#f59e0b',
                    color: '#fff',
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '2px 7px',
                    borderBottomRightRadius: 4,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <span>👤 Box 2: Facecam</span>
                  <span style={{ background: 'rgba(0,0,0,0.3)', padding: '1px 5px', borderRadius: 3, fontFamily: 'monospace' }}>
                    {Math.round(facecamRoi.width * 1920)}×{Math.round(facecamRoi.height * 1080)}
                  </span>
                </div>

                {/* 8 Resize Handles: 4 corners + 4 edges */}
                {renderHandles('facecam', '#f59e0b')}
              </div>
            </div>
          </div>

          {/* Quick instructions & Coordinates indicator */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 11,
              color: '#64748b',
              padding: '0 4px',
            }}
          >
            <span>
              💡 Drag to move. Drag any corner/edge to customly resize.
            </span>
            <span style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <span>
                🎮 Box 1: <strong style={{ color: '#34d399' }}>{Math.round(gameplayRoi.width * 1920)}×{Math.round(gameplayRoi.height * 1080)} px</strong>
              </span>
              <span>•</span>
              <span>
                👤 Box 2: <strong style={{ color: '#fbbf24' }}>{Math.round(facecamRoi.width * 1920)}×{Math.round(facecamRoi.height * 1080)} px</strong>
              </span>
            </span>
          </div>
        </div>

        {/* Right: 9:16 Composite Canvas Preview & Overlay Placement */}
        <div
          style={{
            background: '#070810',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 12,
            padding: 16,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <div style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>9:16 Shorts Preview</span>
            <span style={{ fontSize: 10, color: '#10b981', fontWeight: 600 }}>1080×1920</span>
          </div>

          {/* Canvas Component */}
          <div
            style={{
              width: 180,
              height: 320,
              borderRadius: 8,
              overflow: 'hidden',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.8)',
            }}
          >
            <GamingCompositeCanvas
              gameplayRoi={gameplayRoi}
              facecamRoi={facecamRoi}
              facecamOutputRect={facecamOutputRect}
              facecamPlacement={facecamPlacement}
              youtubeVideoId={youtubeVideoId}
              showPresets={false}
              showReset={false}
              onFacecamOutputRectChange={(rect, preset) => {
                if (preset && preset !== 'custom') {
                  onChangePlacement(preset, rect);
                }
              }}
            />
          </div>

          {/* Facecam Placement Presets */}
          <div style={{ width: '100%' }}>
            <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 6, fontWeight: 600 }}>
              Facecam Position Preset
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {(['top-left', 'top-right', 'bottom-left', 'bottom-right'] as FacecamPreset[]).map((preset) => {
                const isSelected = facecamPlacement === preset;
                const labels: Record<FacecamPreset, string> = {
                  'top-left': '↖ Top Left',
                  'top-right': '↗ Top Right',
                  'bottom-left': '↙ Bottom Left',
                  'bottom-right': '↘ Bottom Right',
                };
                return (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => {
                      const newRect = getDefaultFacecamOutputRect(preset);
                      onChangePlacement(preset, newRect);
                    }}
                    style={{
                      background: isSelected ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.04)',
                      border: isSelected ? '1px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: 6,
                      padding: '5px 8px',
                      color: isSelected ? '#a5b4fc' : '#cbd5e1',
                      fontSize: 11,
                      fontWeight: 600,
                      cursor: 'pointer',
                      textAlign: 'center',
                    }}
                  >
                    {labels[preset]}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Start Clipping Action Button directly under Preview */}
          {onStartMonitoring && (
            <button
              type="button"
              onClick={onStartMonitoring}
              disabled={!canStart || isStarting}
              style={{
                width: '100%',
                marginTop: 4,
                background: canStart
                  ? 'linear-gradient(135deg, #10b981 0%, #6366f1 100%)'
                  : 'rgba(255, 255, 255, 0.08)',
                border: 'none',
                borderRadius: 10,
                padding: '12px 14px',
                color: '#fff',
                fontSize: 13,
                fontWeight: 700,
                cursor: canStart && !isStarting ? 'pointer' : 'not-allowed',
                opacity: canStart && !isStarting ? 1 : 0.45,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                boxShadow: canStart ? '0 4px 16px rgba(16, 185, 129, 0.35)' : 'none',
                transition: 'all 0.2s',
              }}
            >
              {isStarting ? (
                <>⏳ Starting...</>
              ) : (
                <>⚡ Start Clipping Now</>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
