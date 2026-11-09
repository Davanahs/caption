'use client';

import React, { useState, useMemo } from 'react';
import { thumbnailUrl } from '@/lib/api';

export interface VisualClipItem {
  id: string;
  title: string;
  source_title?: string | null;
  duration: number;
  score?: number | null;
  thumbnail_path?: string | null;
  publish_destination_id?: string | null;
  source_channel_name?: string | null;
}

export interface VisualClipPickerProps {
  clips: VisualClipItem[];
  selectedClipId: string | null;
  onSelectClip: (clipId: string) => void;
  selectedDestinationId?: string;
}

// Format duration as 00:32, 00:45, etc.
export function formatClipDuration(seconds?: number): string {
  if (seconds === undefined || seconds === null || isNaN(seconds)) return '00:00';
  const totalSec = Math.round(seconds);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Neutral placeholder when image is missing or errors
export function ThumbnailPlaceholder({ size = 64 }: { size?: number }) {
  return (
    <div
      data-testid="thumbnail-placeholder"
      style={{
        width: size,
        height: size,
        minWidth: size,
        minHeight: size,
        borderRadius: 8,
        background: '#151c2c',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-muted, #94a3b8)',
        fontSize: size >= 56 ? 22 : 16,
        userSelect: 'none',
        flexShrink: 0,
      }}
      title="No thumbnail available"
    >
      🎬
    </div>
  );
}

// Lazy-loaded square thumbnail with graceful placeholder fallback
export function SquareClipThumbnail({
  clipId,
  alt,
  size = 64,
  youtubeShortId,
}: {
  clipId: string;
  alt: string;
  size?: number;
  youtubeShortId?: string | null;
}) {
  const [hasError, setHasError] = useState(false);
  const [srcIndex, setSrcIndex] = useState(0);

  // Fallback sources: 1. Local clip thumbnail -> 2. YouTube Short thumbnail (if available)
  const candidateUrls: string[] = useMemo(() => {
    const urls = [thumbnailUrl(clipId)];
    if (youtubeShortId) {
      urls.push(`https://i.ytimg.com/vi/${youtubeShortId}/mqdefault.jpg`);
    }
    return urls;
  }, [clipId, youtubeShortId]);

  const currentSrc = candidateUrls[srcIndex];

  if (hasError || !currentSrc) {
    return <ThumbnailPlaceholder size={size} />;
  }

  return (
    <div
      style={{
        width: size,
        height: size,
        minWidth: size,
        minHeight: size,
        borderRadius: 8,
        overflow: 'hidden',
        background: '#0d1322',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        position: 'relative',
        flexShrink: 0,
      }}
    >
      <img
        src={currentSrc}
        alt={alt}
        loading="lazy"
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
        }}
        onError={() => {
          if (srcIndex + 1 < candidateUrls.length) {
            setSrcIndex(srcIndex + 1);
          } else {
            setHasError(true);
          }
        }}
      />
    </div>
  );
}

export default function VisualClipPicker({
  clips,
  selectedClipId,
  onSelectClip,
  selectedDestinationId = '',
}: VisualClipPickerProps) {
  const [searchQuery, setSearchQuery] = useState('');

  // Filter clips by title or source video title
  const filteredClips = useMemo(() => {
    if (!searchQuery.trim()) return clips;
    const q = searchQuery.toLowerCase().trim();
    return clips.filter(c =>
      (c.title && c.title.toLowerCase().includes(q)) ||
      (c.source_title && c.source_title.toLowerCase().includes(q)) ||
      (c.source_channel_name && c.source_channel_name.toLowerCase().includes(q))
    );
  }, [clips, searchQuery]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Search Input */}
      <div style={{ position: 'relative' }}>
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="🔍 Search clips by title or source..."
          data-testid="clip-picker-search"
          aria-label="Search clips by title or source video"
          style={{
            width: '100%',
            padding: '8px 30px 8px 10px',
            fontSize: 12,
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid var(--border, rgba(255,255,255,0.12))',
            borderRadius: 8,
            color: 'var(--text-primary, #fff)',
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => setSearchQuery('')}
            aria-label="Clear search"
            style={{
              position: 'absolute',
              right: 8,
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted, #94a3b8)',
              fontSize: 12,
              cursor: 'pointer',
              padding: 0,
            }}
          >
            ✕
          </button>
        )}
      </div>

      {/* Clip Count Summary */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: 'var(--text-muted, #94a3b8)' }}>
        <span>
          Showing {filteredClips.length} of {clips.length} clip{clips.length !== 1 ? 's' : ''}
        </span>
        {selectedClipId && (
          <span style={{ color: 'var(--accent, #7c6cf0)', fontWeight: 600 }}>
            1 clip selected
          </span>
        )}
      </div>

      {/* Scrollable Clips List */}
      <div
        role="listbox"
        aria-label="Choose clip to publish"
        style={{
          maxHeight: 420,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          paddingRight: 4,
        }}
      >
        {filteredClips.length === 0 ? (
          <div
            style={{
              textAlign: 'center',
              padding: '28px 12px',
              color: 'var(--text-muted, #94a3b8)',
              fontSize: 12,
              background: 'rgba(255,255,255,0.02)',
              borderRadius: 8,
              border: '1px dashed rgba(255,255,255,0.1)',
            }}
          >
            {searchQuery ? 'No clips match your search query.' : 'No generated clips available.'}
          </div>
        ) : (
          filteredClips.map(clip => {
            const isSelected = selectedClipId === clip.id;
            const isAssignedOther = !!(
              selectedDestinationId &&
              clip.publish_destination_id &&
              clip.publish_destination_id !== selectedDestinationId
            );

            return (
              <div
                key={clip.id}
                role="option"
                aria-selected={isSelected}
                tabIndex={isAssignedOther ? -1 : 0}
                data-testid={`clip-picker-option-${clip.id}`}
                onClick={() => {
                  if (!isAssignedOther) {
                    onSelectClip(clip.id);
                  }
                }}
                onKeyDown={e => {
                  if ((e.key === 'Enter' || e.key === ' ') && !isAssignedOther) {
                    e.preventDefault();
                    onSelectClip(clip.id);
                  }
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: 10,
                  borderRadius: 10,
                  background: isSelected
                    ? 'rgba(124, 108, 240, 0.14)'
                    : 'rgba(255, 255, 255, 0.02)',
                  border: isSelected
                    ? '2px solid var(--accent, #7c6cf0)'
                    : '1px solid var(--border, rgba(255, 255, 255, 0.08))',
                  boxShadow: isSelected
                    ? '0 0 16px rgba(124, 108, 240, 0.25)'
                    : 'none',
                  cursor: isAssignedOther ? 'not-allowed' : 'pointer',
                  opacity: isAssignedOther ? 0.45 : 1,
                  transition: 'all 0.15s ease',
                  position: 'relative',
                  outline: 'none',
                }}
                onMouseEnter={e => {
                  if (!isSelected && !isAssignedOther) {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                    e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.18)';
                  }
                }}
                onMouseLeave={e => {
                  if (!isSelected && !isAssignedOther) {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.02)';
                    e.currentTarget.style.borderColor = 'var(--border, rgba(255, 255, 255, 0.08))';
                  }
                }}
              >
                {/* 1:1 Square Thumbnail */}
                <SquareClipThumbnail
                  clipId={clip.id}
                  alt={clip.title}
                  size={64}
                />

                {/* Details Column */}
                <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {/* Clip Title */}
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: isSelected ? '#fff' : 'var(--text-primary, #e2e8f0)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                    title={clip.title}
                  >
                    {clip.title || 'Untitled Clip'}
                  </div>

                  {/* Source Video Title */}
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--text-muted, #94a3b8)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                    title={clip.source_title ? `Source: ${clip.source_title}` : 'Source video'}
                  >
                    Source: {clip.source_title || 'Original Video'}
                  </div>

                  {/* Duration and Score Row */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text-secondary, #cbd5e1)', marginTop: 2 }}>
                    {/* Duration badge */}
                    <span
                      style={{
                        background: 'rgba(255, 255, 255, 0.06)',
                        padding: '1px 6px',
                        borderRadius: 4,
                        fontSize: 10,
                        fontWeight: 600,
                        letterSpacing: '0.02em',
                      }}
                    >
                      ⏱ {formatClipDuration(clip.duration)}
                    </span>

                    {/* Score if available */}
                    {clip.score !== undefined && clip.score !== null && (
                      <span
                        style={{
                          color: clip.score >= 70 || clip.score >= 7 ? '#10b981' : 'var(--accent, #7c6cf0)',
                          fontWeight: 600,
                          fontSize: 10,
                        }}
                      >
                        ★ {Number(clip.score).toFixed(1)}
                      </span>
                    )}

                    {/* Source channel tag if available */}
                    {clip.source_channel_name && (
                      <span
                        style={{
                          fontSize: 10,
                          color: '#64748b',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          maxWidth: 80,
                        }}
                        title={clip.source_channel_name}
                      >
                        • {clip.source_channel_name}
                      </span>
                    )}
                  </div>

                  {/* Assigned to other destination channel warning */}
                  {isAssignedOther && (
                    <div style={{ fontSize: 10, color: '#f59e0b', marginTop: 2, fontWeight: 500 }}>
                      ⚠️ Assigned to another channel
                    </div>
                  )}
                </div>

                {/* Selection Radio Indicator */}
                <div
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: '50%',
                    border: isSelected
                      ? '2px solid var(--accent, #7c6cf0)'
                      : '2px solid rgba(255, 255, 255, 0.25)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: isSelected ? 'var(--accent, #7c6cf0)' : 'transparent',
                    flexShrink: 0,
                    transition: 'all 0.15s ease',
                  }}
                  aria-hidden="true"
                >
                  {isSelected && (
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: '#fff',
                      }}
                    />
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
