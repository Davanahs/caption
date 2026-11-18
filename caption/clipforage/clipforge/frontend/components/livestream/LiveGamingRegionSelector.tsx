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
}

export default function LiveGamingRegionSelector({
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
}: LiveGamingRegionSelectorProps) {
  const [activeTool, setActiveTool] = useState<'gameplay' | 'facecam'>('gameplay');
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

  // Video aspect ratio assumed standard 16:9 for livestreams
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

        // For gameplay, lock to 9:16 vertical ratio
        if (dragState.roiType === 'gameplay') {
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
  }, [dragState, videoDimensions, onChangeGameplayRoi, onChangeFacecamRoi]);

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

        {/* Action buttons */}
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
            Box 1: Gameplay (9:16)
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
            Box 2: Facecam PiP
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
            ↺ Reset Boxes
          </button>
        </div>
      </div>

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
                    padding: '2px 6px',
                    borderBottomRightRadius: 4,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  🎮 Gameplay (9:16)
                </div>

                {/* Resize Handles */}
                {(['nw', 'ne', 'se', 'sw'] as ResizeHandle[]).map((handle) => (
                  <div
                    key={handle}
                    onPointerDown={(e) => handleRoiPointerDown(e, 'gameplay', 'resize', handle)}
                    style={{
                      position: 'absolute',
                      width: 10,
                      height: 10,
                      background: '#fff',
                      border: '2px solid #10b981',
                      borderRadius: 2,
                      cursor: handleCursorMap[handle],
                      pointerEvents: 'auto',
                      top: handle.includes('n') ? -5 : undefined,
                      bottom: handle.includes('s') ? -5 : undefined,
                      left: handle.includes('w') ? -5 : undefined,
                      right: handle.includes('e') ? -5 : undefined,
                      display: activeTool === 'gameplay' ? 'block' : 'none',
                    }}
                  />
                ))}
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
                    padding: '2px 6px',
                    borderBottomRightRadius: 4,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  👤 Streamer Facecam
                </div>

                {/* Resize Handles */}
                {(['nw', 'ne', 'se', 'sw'] as ResizeHandle[]).map((handle) => (
                  <div
                    key={handle}
                    onPointerDown={(e) => handleRoiPointerDown(e, 'facecam', 'resize', handle)}
                    style={{
                      position: 'absolute',
                      width: 10,
                      height: 10,
                      background: '#fff',
                      border: '2px solid #f59e0b',
                      borderRadius: 2,
                      cursor: handleCursorMap[handle],
                      pointerEvents: 'auto',
                      top: handle.includes('n') ? -5 : undefined,
                      bottom: handle.includes('s') ? -5 : undefined,
                      left: handle.includes('w') ? -5 : undefined,
                      right: handle.includes('e') ? -5 : undefined,
                      display: activeTool === 'facecam' ? 'block' : 'none',
                    }}
                  />
                ))}
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
              💡 Click on any box to select it. Drag to move, or drag corner handles to resize.
            </span>
            <span>
              Active: <strong style={{ color: activeTool === 'gameplay' ? '#34d399' : '#fbbf24' }}>
                {activeTool === 'gameplay' ? 'Box 1: Gameplay' : 'Box 2: Facecam'}
              </strong>
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
        </div>
      </div>
    </div>
  );
}
