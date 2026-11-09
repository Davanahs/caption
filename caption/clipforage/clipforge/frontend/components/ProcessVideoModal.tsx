'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
import LayoutThumbnailSelector, { resolveLayoutOptionId, LAYOUT_OPTIONS } from './LayoutThumbnailSelector';
import { useFocusTrap } from '@/lib/useFocusTrap';

export interface ProcessVideoConfig {
  clipsCount?: number;
  clipMode: 'ai_highlights' | 'equal_split';
  maxClipDuration: number;
  reframeMode: string;
  hookTitle: boolean;
  enableBroll: boolean;
  enableHook: boolean;
  targetLanguage: string;
  targetDuration?: number;
  segmentationStrategy?: string;
}

export interface ProcessVideoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (config: ProcessVideoConfig) => Promise<void> | void;
  pendingUrl?: string;
  pendingFile?: File | null;
  isPendingBatch?: boolean;
  batchUrlsCount?: number;
  sourceDuration?: number;
  initialClipsCount?: number;
  initialClipMode?: 'ai_highlights' | 'equal_split';
  initialDuration?: number;
  initialLayout?: string;
  initialHookTitle?: boolean;
  initialEnableBroll?: boolean;
  initialEnableHook?: boolean;
  initialTargetLanguage?: string;
  isSubmitting?: boolean;
  errorMessage?: string;
}

const DURATION_OPTIONS = [
  { value: 15, label: '15s' },
  { value: 30, label: '30s' },
  { value: 45, label: '45s' },
  { value: 49, label: '49s', badge: 'Optimal', badgeColor: '#818cf8', hint: 'Sweet spot for YouTube Shorts completion rate' },
  { value: 60, label: '60s', badge: 'Max', badgeColor: '#94a3b8' },
];

const LANGUAGE_OPTIONS = [
  { value: 'none', label: '🇺🇸 English (Original Audio)' },
  { value: 'es', label: '🇪🇸 Spanish (Español Dubbing)' },
  { value: 'hi', label: '🇮🇳 Hindi (हिंदी Dubbing)' },
  { value: 'de', label: '🇩🇪 German (Deutsch Dubbing)' },
  { value: 'ja', label: '🇯🇵 Japanese (日本語 Dubbing)' },
  { value: 'pt', label: '🇧🇷 Portuguese (Português Dubbing)' },
  { value: 'fr', label: '🇫🇷 French (Français Dubbing)' },
];

export function extractYouTubeId(url: string): string | null {
  if (!url || typeof url !== 'string') return null;
  const match = url.match(
    /(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/|live\/))([a-zA-Z0-9_-]{11})/
  );
  return match ? match[1] : null;
}

export default function ProcessVideoModal({
  isOpen,
  onClose,
  onConfirm,
  pendingUrl = '',
  pendingFile = null,
  isPendingBatch = false,
  batchUrlsCount = 0,
  sourceDuration,
  initialClipsCount = 5,
  initialClipMode = 'ai_highlights',
  initialDuration = 49,
  initialLayout = 'blur',
  initialHookTitle = true,
  initialEnableBroll = false,
  initialEnableHook = false,
  initialTargetLanguage = 'none',
  isSubmitting = false,
  errorMessage = '',
}: ProcessVideoModalProps) {
  // Local draft state
  const [clipsCount, setClipsCount] = useState<number>(initialClipsCount || 5);
  const [customClips, setCustomClips] = useState<string>('');
  const [clipMode, setClipMode] = useState<'ai_highlights' | 'equal_split'>(initialClipMode);
  const [maxClipDuration, setMaxClipDuration] = useState<number>(initialDuration);
  const [reframeMode, setReframeMode] = useState<string>(initialLayout);
  const [hookTitle, setHookTitle] = useState<boolean>(initialHookTitle);
  const [enableBroll, setEnableBroll] = useState<boolean>(initialEnableBroll);
  const [enableHook, setEnableHook] = useState<boolean>(initialEnableHook);
  const [targetLanguage, setTargetLanguage] = useState<string>(initialTargetLanguage);
  const [showEnhancements, setShowEnhancements] = useState<boolean>(false);
  const [thumbnailError, setThumbnailError] = useState<boolean>(false);

  const modalContainerRef = useRef<HTMLDivElement>(null);
  useFocusTrap(isOpen, modalContainerRef, onClose, isSubmitting);

  // Sync state when modal opens or initial values change
  useEffect(() => {
    if (isOpen) {
      setClipsCount(initialClipsCount || 5);
      setCustomClips('');
      setClipMode(initialClipMode);
      setMaxClipDuration(initialDuration);
      setReframeMode(initialLayout);
      setHookTitle(initialHookTitle);
      setEnableBroll(initialEnableBroll);
      setEnableHook(initialEnableHook);
      setTargetLanguage(initialTargetLanguage);
      setThumbnailError(false);
    }
  }, [
    isOpen,
    initialClipsCount,
    initialClipMode,
    initialDuration,
    initialLayout,
    initialHookTitle,
    initialEnableBroll,
    initialEnableHook,
    initialTargetLanguage,
  ]);

  // Handle ESC key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isSubmitting) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isSubmitting, onClose]);

  // Compute effective clip count
  const effectiveClipsCount = useMemo(() => {
    if (clipMode === 'equal_split') return undefined;
    if (customClips.trim() !== '') {
      const parsed = parseInt(customClips, 10);
      if (!isNaN(parsed) && parsed >= 1) return Math.min(parsed, 20);
    }
    return clipsCount;
  }, [clipMode, customClips, clipsCount]);

  // Compute layout display name
  const layoutDisplayName = useMemo(() => {
    const canonicalId = resolveLayoutOptionId(reframeMode);
    const matched = LAYOUT_OPTIONS.find((opt) => opt.id === canonicalId);
    return matched ? matched.name : reframeMode;
  }, [reframeMode]);

  // Compute count of enabled visual enhancements
  const visualEnhancementsCount = useMemo(() => {
    let count = 0;
    if (hookTitle) count++;
    if (enableBroll) count++;
    if (enableHook) count++;
    return count;
  }, [hookTitle, enableBroll, enableHook]);

  // Compute dynamic summary text
  const configurationSummary = useMemo(() => {
    const parts: string[] = [];
    if (clipMode === 'equal_split') {
      parts.push(`Equal Split · ≤${maxClipDuration}s max limit · Equal duration full coverage`);
    } else {
      parts.push(`${effectiveClipsCount || 5} clips`);
      parts.push(`Up to ${maxClipDuration}s`);
      parts.push('AI Highlights');
    }
    parts.push(`${layoutDisplayName} layout`);
    if (visualEnhancementsCount > 0) {
      parts.push(`${visualEnhancementsCount} visual enhancement${visualEnhancementsCount > 1 ? 's' : ''}`);
    } else {
      parts.push('No visual overlays');
    }
    if (targetLanguage && targetLanguage !== 'none') {
      const lang = LANGUAGE_OPTIONS.find((l) => l.value === targetLanguage);
      parts.push(lang ? lang.label.split(' ')[1] || lang.label : targetLanguage);
    } else {
      parts.push('Original Audio');
    }
    return parts.join(' · ');
  }, [clipMode, effectiveClipsCount, maxClipDuration, layoutDisplayName, visualEnhancementsCount, targetLanguage]);

  if (!isOpen) return null;

  const ytId = pendingUrl ? extractYouTubeId(pendingUrl) : null;
  const thumbnailUrl = ytId && !thumbnailError ? `https://img.youtube.com/vi/${ytId}/mqdefault.jpg` : null;

  const handleStartProcessing = () => {
    if (isSubmitting) return;
    onConfirm({
      clipsCount: clipMode === 'equal_split' ? undefined : (effectiveClipsCount || 5),
      clipMode,
      maxClipDuration,
      reframeMode,
      hookTitle,
      enableBroll,
      enableHook,
      targetLanguage,
      targetDuration: clipMode === 'equal_split' ? maxClipDuration : undefined,
      segmentationStrategy: clipMode === 'equal_split' ? 'equal_splits' : undefined,
    });
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="clip-modal-title"
      aria-describedby="clip-modal-description"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'rgba(5, 8, 16, 0.78)',
        backdropFilter: 'blur(10px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px 16px',
        animation: 'fadeInModal 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      <div
        ref={modalContainerRef}
        tabIndex={-1}
        className="modal-scroll"
        style={{
          background: 'linear-gradient(180deg, #0f1629 0%, #0b101f 100%)',
          border: '1px solid rgba(124, 108, 240, 0.25)',
          borderRadius: 20,
          width: '100%',
          maxWidth: 780,
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 24px 64px -12px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.05)',
          animation: 'scaleUpModal 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* ── Modal Header ── */}
        <div
          style={{
            padding: '24px 28px 20px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 16,
            background: 'rgba(15, 22, 41, 0.6)',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 16,
                  boxShadow: '0 4px 12px rgba(99, 102, 241, 0.35)',
                }}
              >
                ⚙️
              </div>
              <h2
                id="clip-modal-title"
                style={{
                  fontWeight: 700,
                  fontSize: 20,
                  color: '#ffffff',
                  fontFamily: "'Space Grotesk', sans-serif",
                  margin: 0,
                  letterSpacing: '-0.02em',
                }}
              >
                Configure Your Clips
              </h2>
            </div>
            <p id="clip-modal-description" style={{ fontSize: 13, color: '#94a3b8', margin: 0, lineHeight: 1.4 }}>
              Choose how many clips to create, set their format, and customize optional enhancements.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close dialog"
            style={{
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 8,
              width: 32,
              height: 32,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#94a3b8',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease',
              fontSize: 14,
            }}
            onMouseEnter={(e) => {
              if (!isSubmitting) {
                e.currentTarget.style.color = '#ffffff';
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)';
              }
            }}
            onMouseLeave={(e) => {
              if (!isSubmitting) {
                e.currentTarget.style.color = '#94a3b8';
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
              }
            }}
          >
            ✕
          </button>
        </div>

        {/* ── Scrollable Body ── */}
        <div
          style={{
            padding: '24px 28px',
            overflowY: 'auto',
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 28,
            scrollbarWidth: 'thin',
            scrollbarColor: 'rgba(124, 108, 240, 0.3) transparent',
          }}
        >
          {/* 1. Source Video Summary Card */}
          <div
            style={{
              background: 'rgba(14, 21, 38, 0.8)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 14,
              padding: 14,
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.03)',
            }}
          >
            {isPendingBatch ? (
              <div
                style={{
                  width: 96,
                  height: 54,
                  borderRadius: 8,
                  background: 'rgba(16, 185, 129, 0.12)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 24,
                  flexShrink: 0,
                }}
              >
                📦
              </div>
            ) : pendingFile ? (
              <div
                style={{
                  width: 96,
                  height: 54,
                  borderRadius: 8,
                  background: 'rgba(124, 108, 240, 0.12)',
                  border: '1px solid rgba(124, 108, 240, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 24,
                  flexShrink: 0,
                }}
              >
                📁
              </div>
            ) : thumbnailUrl ? (
              <div
                style={{
                  width: 96,
                  height: 54,
                  borderRadius: 8,
                  overflow: 'hidden',
                  background: '#090d16',
                  flexShrink: 0,
                  position: 'relative',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                }}
              >
                <img
                  src={thumbnailUrl}
                  alt="YouTube video thumbnail"
                  onError={() => setThumbnailError(true)}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              </div>
            ) : (
              <div
                style={{
                  width: 96,
                  height: 54,
                  borderRadius: 8,
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 22,
                  color: '#f87171',
                  flexShrink: 0,
                }}
              >
                ▶
              </div>
            )}

            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    padding: '2px 7px',
                    borderRadius: 4,
                    background: isPendingBatch
                      ? 'rgba(16, 185, 129, 0.18)'
                      : pendingFile
                      ? 'rgba(124, 108, 240, 0.18)'
                      : 'rgba(239, 68, 68, 0.18)',
                    color: isPendingBatch ? '#34d399' : pendingFile ? '#a5b4fc' : '#f87171',
                    border: `1px solid ${
                      isPendingBatch
                        ? 'rgba(16, 185, 129, 0.3)'
                        : pendingFile
                        ? 'rgba(124, 108, 240, 0.3)'
                        : 'rgba(239, 68, 68, 0.3)'
                    }`,
                  }}
                >
                  {isPendingBatch ? 'Batch Ingestion' : pendingFile ? 'Uploaded File' : 'YouTube Source'}
                </span>

                {ytId && (
                  <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
                    ID: {ytId}
                  </span>
                )}
              </div>

              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#f8fafc',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
                title={isPendingBatch ? `${batchUrlsCount} URLs in batch` : pendingFile ? pendingFile.name : pendingUrl}
              >
                {isPendingBatch
                  ? `${batchUrlsCount} YouTube videos in batch queue`
                  : pendingFile
                  ? `${pendingFile.name} (${(pendingFile.size / (1024 * 1024)).toFixed(1)} MB)`
                  : pendingUrl}
              </div>
            </div>
          </div>

          {/* 2. Generation Mode Selector */}
          <div>
            <div style={{ marginBottom: 10 }}>
              <label
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#e2e8f0',
                  display: 'block',
                  marginBottom: 3,
                }}
              >
                Clip Generation Mode
              </label>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>
                Choose how clips are discovered and cut from the source video.
              </p>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: 12,
              }}
            >
              {[
                {
                  id: 'ai_highlights',
                  title: '🧠 AI Highlights',
                  description: 'Find and score engaging viral moments automatically.',
                },
                {
                  id: 'equal_split',
                  title: '✂️ Equal Split',
                  description: 'Divide the source video into segments of similar length.',
                },
              ].map((mode) => {
                const isSelected = clipMode === mode.id;
                return (
                  <div
                    key={mode.id}
                    role="radio"
                    aria-checked={isSelected}
                    tabIndex={0}
                    onClick={() => setClipMode(mode.id as any)}
                    onKeyDown={(e) => {
                      if (e.key === ' ' || e.key === 'Enter') {
                        e.preventDefault();
                        setClipMode(mode.id as any);
                      }
                    }}
                    style={{
                      background: isSelected ? 'rgba(124, 108, 240, 0.12)' : 'rgba(14, 21, 38, 0.6)',
                      border: isSelected ? '2px solid #7c6cf0' : '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: 12,
                      padding: '14px 16px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected ? '0 0 16px rgba(124, 108, 240, 0.2)' : 'none',
                    }}
                  >
                    <div
                      style={{
                        fontSize: 14,
                        fontWeight: 600,
                        color: isSelected ? '#ffffff' : '#e2e8f0',
                        marginBottom: 4,
                      }}
                    >
                      {mode.title}
                    </div>
                    <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.4 }}>
                      {mode.description}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 3. Clip Count Section */}
          <div>
            <div style={{ marginBottom: 10 }}>
              <label
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#e2e8f0',
                  display: 'block',
                  marginBottom: 3,
                }}
              >
                How many clips?
              </label>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>
                {clipMode === 'ai_highlights'
                  ? 'Choose how many Shorts to generate from this video.'
                  : 'In Equal Split mode, clip count is calculated automatically from total duration.'}
              </p>
            </div>

            {clipMode === 'ai_highlights' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Presets Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
                  {[2, 3, 5, 8, 10].map((num) => {
                    const isSelected = clipsCount === num && customClips === '';
                    return (
                      <button
                        key={num}
                        type="button"
                        onClick={() => {
                          setClipsCount(num);
                          setCustomClips('');
                        }}
                        style={{
                          padding: '12px 0',
                          borderRadius: 10,
                          border: isSelected ? '2px solid #7c6cf0' : '1px solid rgba(255, 255, 255, 0.08)',
                          background: isSelected ? 'rgba(124, 108, 240, 0.2)' : 'rgba(14, 21, 38, 0.6)',
                          color: isSelected ? '#ffffff' : '#cbd5e1',
                          fontWeight: 700,
                          fontSize: 16,
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                          fontFamily: "'Space Grotesk', sans-serif",
                          boxShadow: isSelected ? '0 0 14px rgba(124, 108, 240, 0.25)' : 'none',
                        }}
                      >
                        {num}
                        {num === 5 && (
                          <div
                            style={{
                              fontSize: 9,
                              fontWeight: 600,
                              color: isSelected ? '#c7d2fe' : '#64748b',
                              marginTop: 2,
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em',
                            }}
                          >
                            Default
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Custom Number Input & Summary */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 16,
                    flexWrap: 'wrap',
                    paddingTop: 4,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 12, color: '#94a3b8' }}>Or custom (1–20):</span>
                    <input
                      type="number"
                      min={1}
                      max={20}
                      placeholder="e.g. 7"
                      value={customClips}
                      onChange={(e) => {
                        const val = e.target.value;
                        setCustomClips(val);
                      }}
                      style={{
                        width: 80,
                        padding: '6px 10px',
                        borderRadius: 8,
                        background: 'rgba(14, 21, 38, 0.8)',
                        border: customClips !== '' ? '2px solid #7c6cf0' : '1px solid rgba(255, 255, 255, 0.12)',
                        color: '#ffffff',
                        fontSize: 14,
                        fontWeight: 600,
                        textAlign: 'center',
                        outline: 'none',
                      }}
                    />
                  </div>

                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 500,
                      color: '#a5b4fc',
                      background: 'rgba(124, 108, 240, 0.1)',
                      border: '1px solid rgba(124, 108, 240, 0.25)',
                      padding: '4px 10px',
                      borderRadius: 6,
                    }}
                  >
                    ✨ {effectiveClipsCount || 5} clips will be generated
                  </div>
                </div>
              </div>
            ) : (
              <div
                style={{
                  padding: '16px 20px',
                  borderRadius: 12,
                  background: 'rgba(99, 102, 241, 0.08)',
                  border: '1px solid rgba(99, 102, 241, 0.25)',
                  color: '#e2e8f0',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 18 }}>✂️</span>
                    <span style={{ fontSize: 14, fontWeight: 700, color: '#c7d2fe' }}>
                      Equal Split — Full Source Coverage
                    </span>
                  </div>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      background: 'rgba(16, 185, 129, 0.15)',
                      color: '#34d399',
                      border: '1px solid rgba(16, 185, 129, 0.3)',
                      padding: '2px 8px',
                      borderRadius: 6,
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                    }}
                  >
                    100% Timeline Covered
                  </span>
                </div>

                <p style={{ fontSize: 12.5, color: '#94a3b8', margin: 0, lineHeight: 1.45 }}>
                  Divides the entire video into equal-duration segments (≤ {maxClipDuration}s max limit). Every clip has the exact same duration and 100% of footage is covered from 0:00 to the end.
                </p>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: 10,
                    paddingTop: 4,
                  }}
                >
                  <div
                    style={{
                      background: 'rgba(15, 23, 42, 0.6)',
                      borderRadius: 8,
                      padding: '8px 12px',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                    }}
                  >
                    <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
                      Source Duration
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc', marginTop: 2 }}>
                      {sourceDuration ? `${Math.floor(sourceDuration / 60)}:${String(Math.floor(sourceDuration % 60)).padStart(2, '0')}` : 'Auto-detected'}
                    </div>
                  </div>

                  <div
                    style={{
                      background: 'rgba(15, 23, 42, 0.6)',
                      borderRadius: 8,
                      padding: '8px 12px',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                    }}
                  >
                    <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
                      Maximum Clip Limit
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#a5b4fc', marginTop: 2 }}>
                      {maxClipDuration} seconds max
                    </div>
                  </div>

                  <div
                    style={{
                      background: 'rgba(15, 23, 42, 0.6)',
                      borderRadius: 8,
                      padding: '8px 12px',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                    }}
                  >
                    <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
                      Calculated Clip Count
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#38bdf8', marginTop: 2 }}>
                      {sourceDuration ? `${Math.ceil(sourceDuration / maxClipDuration)} equal clips` : 'Auto-calculated'}
                    </div>
                  </div>

                  <div
                    style={{
                      background: 'rgba(15, 23, 42, 0.6)',
                      borderRadius: 8,
                      padding: '8px 12px',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                    }}
                  >
                    <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
                      Coverage
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#10b981', marginTop: 2 }}>
                      Entire video (0:00 → End)
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 4. Clip Duration */}
          <div>
            <div style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <label
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: '#e2e8f0',
                    display: 'block',
                    marginBottom: 3,
                  }}
                >
                  {clipMode === 'equal_split' ? 'Maximum Clip Duration (Limit)' : 'Maximum Clip Duration'}
                </label>
                <span style={{ fontSize: 11, color: '#818cf8', fontWeight: 500 }}>
                  {clipMode === 'equal_split' ? 'Equal Slices (≤ Max Limit)' : '49s Recommended for Shorts'}
                </span>
              </div>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>
                {clipMode === 'equal_split'
                  ? 'Maximum permitted duration per generated clip. All clips will be equally sized and less than or equal to this limit.'
                  : 'Limit the maximum length of each generated clip.'}
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
              {DURATION_OPTIONS.map((opt) => {
                const isSelected = maxClipDuration === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setMaxClipDuration(opt.value)}
                    style={{
                      padding: '10px 0',
                      borderRadius: 10,
                      border: isSelected ? '2px solid #7c6cf0' : '1px solid rgba(255, 255, 255, 0.08)',
                      background: isSelected ? 'rgba(124, 108, 240, 0.2)' : 'rgba(14, 21, 38, 0.6)',
                      color: isSelected ? '#ffffff' : '#cbd5e1',
                      fontWeight: 700,
                      fontSize: 14,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected ? '0 0 12px rgba(124, 108, 240, 0.25)' : 'none',
                    }}
                  >
                    {opt.label}
                    {opt.badge && (
                      <div
                        style={{
                          fontSize: 9,
                          fontWeight: 600,
                          color: opt.badgeColor || '#a5b4fc',
                          marginTop: 2,
                          textTransform: 'uppercase',
                        }}
                      >
                        {opt.badge}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>

            {maxClipDuration === 49 && (
              <p style={{ fontSize: 11, color: '#94a3b8', marginTop: 6, fontStyle: 'italic' }}>
                💡 49s is the proven YouTube Shorts sweet spot — maximizes retention rate while avoiding the strict 60s platform cutoff.
              </p>
            )}
          </div>

          {/* 5. Video Layout Selector (Canonical Reused Component) */}
          <div>
            <div style={{ marginBottom: 12 }}>
              <label
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#e2e8f0',
                  display: 'block',
                  marginBottom: 3,
                }}
              >
                Video Layout
              </label>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>
                Choose how your footage will appear in the final vertical clip.
              </p>
            </div>

            <div
              style={{
                background: 'rgba(10, 15, 29, 0.5)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                borderRadius: 14,
                padding: '16px 14px 4px',
                maxHeight: 360,
                overflowY: 'auto',
                scrollbarWidth: 'thin',
                scrollbarColor: 'rgba(124, 108, 240, 0.3) transparent',
              }}
            >
              <LayoutThumbnailSelector
                value={reframeMode}
                onChange={(val) => setReframeMode(val)}
                title=""
                subtitle=""
                badge=""
              />
            </div>
          </div>

          {/* 6. Optional Enhancements (Collapsible Progressive Disclosure) */}
          <div
            style={{
              background: 'rgba(14, 21, 38, 0.6)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 14,
              overflow: 'hidden',
              transition: 'border-color 0.15s ease',
            }}
          >
            {/* Collapsible Accordion Header */}
            <button
              type="button"
              onClick={() => setShowEnhancements(!showEnhancements)}
              style={{
                width: '100%',
                padding: '16px 20px',
                background: 'transparent',
                border: 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 16 }}>✨</span>
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#ffffff' }}>
                    Optional Enhancements
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      padding: '2px 8px',
                      borderRadius: 4,
                      background:
                        visualEnhancementsCount > 0 || targetLanguage !== 'none'
                          ? 'rgba(124, 108, 240, 0.2)'
                          : 'rgba(255, 255, 255, 0.06)',
                      color:
                        visualEnhancementsCount > 0 || targetLanguage !== 'none'
                          ? '#a5b4fc'
                          : '#94a3b8',
                      fontWeight: 600,
                    }}
                  >
                    {visualEnhancementsCount} visual · {targetLanguage === 'none' ? 'Original Audio' : 'Dubbed'}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
                  Enable additional visual overlays, hooks, or multi-language audio dubbing.
                </div>
              </div>

              <div
                style={{
                  fontSize: 14,
                  color: '#94a3b8',
                  transform: showEnhancements ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s ease',
                }}
              >
                ▼
              </div>
            </button>

            {/* Collapsible Content */}
            {showEnhancements && (
              <div
                style={{
                  padding: '4px 20px 20px',
                  borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 18,
                }}
              >
                {/* Visual Enhancements Group */}
                <div style={{ paddingTop: 10 }}>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      color: '#64748b',
                      marginBottom: 10,
                    }}
                  >
                    Visual Overlays
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {/* Toggle: Hook Title */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        borderRadius: 10,
                        background: hookTitle ? 'rgba(245, 158, 11, 0.08)' : 'rgba(255, 255, 255, 0.02)',
                        border: hookTitle ? '1px solid rgba(245, 158, 11, 0.25)' : '1px solid rgba(255, 255, 255, 0.05)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ flex: 1, paddingRight: 12 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: hookTitle ? '#fbbf24' : '#e2e8f0' }}>
                          🎯 Hook Title Overlay
                        </div>
                        <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                          Burn high-contrast AI curiosity headline at the top of the clip.
                        </div>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={hookTitle}
                        onClick={() => setHookTitle(!hookTitle)}
                        style={{
                          width: 44,
                          height: 24,
                          borderRadius: 99,
                          border: 'none',
                          background: hookTitle ? '#f59e0b' : '#334155',
                          position: 'relative',
                          cursor: 'pointer',
                          transition: 'background-color 0.2s',
                          flexShrink: 0,
                        }}
                      >
                        <div
                          style={{
                            width: 18,
                            height: 18,
                            borderRadius: '50%',
                            background: '#ffffff',
                            position: 'absolute',
                            top: 3,
                            left: hookTitle ? 23 : 3,
                            transition: 'left 0.2s ease',
                          }}
                        />
                      </button>
                    </div>

                    {/* Toggle: AI B-Roll */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        borderRadius: 10,
                        background: enableBroll ? 'rgba(20, 184, 166, 0.08)' : 'rgba(255, 255, 255, 0.02)',
                        border: enableBroll ? '1px solid rgba(20, 184, 166, 0.25)' : '1px solid rgba(255, 255, 255, 0.05)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ flex: 1, paddingRight: 12 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: enableBroll ? '#2dd4bf' : '#e2e8f0' }}>
                          🎬 AI B-Roll Overlay
                        </div>
                        <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                          Insert contextual cutaway video footage matched to speech semantics.
                        </div>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={enableBroll}
                        onClick={() => setEnableBroll(!enableBroll)}
                        style={{
                          width: 44,
                          height: 24,
                          borderRadius: 99,
                          border: 'none',
                          background: enableBroll ? '#14b8a6' : '#334155',
                          position: 'relative',
                          cursor: 'pointer',
                          transition: 'background-color 0.2s',
                          flexShrink: 0,
                        }}
                      >
                        <div
                          style={{
                            width: 18,
                            height: 18,
                            borderRadius: '50%',
                            background: '#ffffff',
                            position: 'absolute',
                            top: 3,
                            left: enableBroll ? 23 : 3,
                            transition: 'left 0.2s ease',
                          }}
                        />
                      </button>
                    </div>

                    {/* Toggle: Kinetic Hook Intro */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        borderRadius: 10,
                        background: enableHook ? 'rgba(124, 108, 240, 0.08)' : 'rgba(255, 255, 255, 0.02)',
                        border: enableHook ? '1px solid rgba(124, 108, 240, 0.25)' : '1px solid rgba(255, 255, 255, 0.05)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ flex: 1, paddingRight: 12 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: enableHook ? '#a5b4fc' : '#e2e8f0' }}>
                          ⚡ AI Kinetic Hook Intro
                        </div>
                        <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                          Prepend animated 3-second kinetic hook to instantly stop viewer scrolling.
                        </div>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={enableHook}
                        onClick={() => setEnableHook(!enableHook)}
                        style={{
                          width: 44,
                          height: 24,
                          borderRadius: 99,
                          border: 'none',
                          background: enableHook ? '#7c6cf0' : '#334155',
                          position: 'relative',
                          cursor: 'pointer',
                          transition: 'background-color 0.2s',
                          flexShrink: 0,
                        }}
                      >
                        <div
                          style={{
                            width: 18,
                            height: 18,
                            borderRadius: '50%',
                            background: '#ffffff',
                            position: 'absolute',
                            top: 3,
                            left: enableHook ? 23 : 3,
                            transition: 'left 0.2s ease',
                          }}
                        />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Audio & Language Group */}
                <div>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      color: '#64748b',
                      marginBottom: 8,
                    }}
                  >
                    Audio & Language
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <label
                      htmlFor="target-language-select"
                      style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0' }}
                    >
                      AI Auto-Dubbing & Voice Translation
                    </label>
                    <p style={{ fontSize: 11, color: '#94a3b8', margin: '0 0 6px 0' }}>
                      Translate and dub video speech into international target languages.
                    </p>

                    <select
                      id="target-language-select"
                      value={targetLanguage}
                      onChange={(e) => setTargetLanguage(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '10px 14px',
                        borderRadius: 10,
                        border:
                          targetLanguage !== 'none'
                            ? '1px solid rgba(236, 72, 153, 0.4)'
                            : '1px solid rgba(255, 255, 255, 0.1)',
                        background:
                          targetLanguage !== 'none'
                            ? 'rgba(236, 72, 153, 0.1)'
                            : 'rgba(10, 15, 29, 0.7)',
                        color: targetLanguage !== 'none' ? '#f472b6' : '#f8fafc',
                        cursor: 'pointer',
                        fontSize: 13,
                        fontWeight: 600,
                        outline: 'none',
                      }}
                    >
                      {LANGUAGE_OPTIONS.map((lang) => (
                        <option
                          key={lang.value}
                          value={lang.value}
                          style={{ background: '#0e1526', color: '#ffffff' }}
                        >
                          {lang.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Fixed Footer & Dynamic Configuration Summary ── */}
        <div
          style={{
            padding: '16px 28px 20px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'rgba(10, 15, 29, 0.85)',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          {/* Live Dynamic Configuration Summary Badge */}
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 8,
              background: 'rgba(124, 108, 240, 0.08)',
              border: '1px solid rgba(124, 108, 240, 0.2)',
              fontSize: 12,
              color: '#c7d2fe',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            <span style={{ fontSize: 14 }}>⚡</span>
            <span style={{ fontWeight: 600, color: '#ffffff' }}>Plan:</span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {configurationSummary}
            </span>
          </div>

          {/* Submitting in-flight banner */}
          {isSubmitting && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 8,
                background: 'rgba(99, 102, 241, 0.15)',
                border: '1px solid rgba(99, 102, 241, 0.35)',
                fontSize: 12.5,
                color: '#c7d2fe',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <span className="spinner" style={{ width: 14, height: 14 }} />
              <span>Uploading and dispatching job to pipeline... Please keep this window open.</span>
            </div>
          )}

          {/* Error Message banner */}
          {errorMessage && !isSubmitting && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 8,
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                fontSize: 12.5,
                color: '#f87171',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span>⚠️</span>
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              type="button"
              disabled={isSubmitting}
              onClick={onClose}
              style={{
                flex: 1,
                padding: '12px 0',
                borderRadius: 10,
                border: '1px solid rgba(255, 255, 255, 0.1)',
                background: 'rgba(255, 255, 255, 0.04)',
                color: '#94a3b8',
                fontSize: 14,
                fontWeight: 600,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                opacity: isSubmitting ? 0.5 : 1,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) {
                  e.currentTarget.style.color = '#ffffff';
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isSubmitting) {
                  e.currentTarget.style.color = '#94a3b8';
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                }
              }}
            >
              Cancel
            </button>

            <button
              type="button"
              disabled={isSubmitting}
              onClick={handleStartProcessing}
              style={{
                flex: 2,
                padding: '12px 0',
                borderRadius: 10,
                border: 'none',
                background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                color: '#ffffff',
                fontSize: 14,
                fontWeight: 700,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                opacity: isSubmitting ? 0.7 : 1,
                transition: 'all 0.2s ease',
                boxShadow: '0 4px 18px rgba(99, 102, 241, 0.35)',
                fontFamily: "'Space Grotesk', sans-serif",
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) {
                  e.currentTarget.style.boxShadow = '0 6px 22px rgba(99, 102, 241, 0.55)';
                  e.currentTarget.style.transform = 'translateY(-1px)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isSubmitting) {
                  e.currentTarget.style.boxShadow = '0 4px 18px rgba(99, 102, 241, 0.35)';
                  e.currentTarget.style.transform = 'translateY(0)';
                }
              }}
            >
              {isSubmitting ? '⏳ Submitting...' : '⚡ Start Processing'}
            </button>
          </div>
        </div>
      </div>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        @keyframes fadeInModal {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scaleUpModal {
          from { opacity: 0; transform: translateY(20px) scale(0.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .modal-scroll::-webkit-scrollbar {
          width: 6px;
        }
        .modal-scroll::-webkit-scrollbar-track {
          background: rgba(0, 0, 0, 0.1);
        }
        .modal-scroll::-webkit-scrollbar-thumb {
          background: rgba(124, 108, 240, 0.3);
          border-radius: 99px;
        }
        .modal-scroll::-webkit-scrollbar-thumb:hover {
          background: rgba(124, 108, 240, 0.6);
        }
      `,
        }}
      />
    </div>
  );
}
