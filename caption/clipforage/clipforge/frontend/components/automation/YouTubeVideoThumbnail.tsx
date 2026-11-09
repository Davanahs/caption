'use client';

import React, { useState, useEffect } from 'react';

export interface YouTubeVideoThumbnailProps {
  videoId: string;
  title: string;
  thumbnailUrl?: string | null;
  duration?: number | null;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Formats duration in seconds into mm:ss or hh:mm:ss for thumbnail badge overlay.
 */
export function formatDurationTimestamp(seconds?: number | null): string | null {
  if (typeof seconds !== 'number' || isNaN(seconds) || seconds <= 0) {
    return null;
  }
  const totalSeconds = Math.round(seconds);
  const hrs = Math.floor(totalSeconds / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  const pad = (n: number) => n.toString().padStart(2, '0');

  if (hrs > 0) {
    return `${hrs}:${pad(mins)}:${pad(secs)}`;
  }
  return `${pad(mins)}:${pad(secs)}`;
}

/**
 * Resolves reliable candidate thumbnail URLs for a YouTube video.
 * Order of preference:
 * 1. Stored / discovered thumbnail URL (e.g. hq720_custom or maxresdefault)
 * 2. Medium quality YouTube thumbnail (mqdefault: 320x180, 16:9 standard)
 * 3. High quality YouTube thumbnail (hqdefault: 480x360)
 */
export function getYouTubeThumbnailCandidates(
  videoId: string,
  providedUrl?: string | null
): string[] {
  const candidates: string[] = [];

  if (providedUrl && providedUrl.trim().length > 0) {
    candidates.push(providedUrl.trim());
  }

  // If videoId is a realistic YouTube ID (not a synthetic test fixture), append standard ytimg URLs
  const cleanId = (videoId || '').trim();
  if (cleanId && !cleanId.startsWith('synth_') && !cleanId.startsWith('test_')) {
    const mq = `https://i.ytimg.com/vi/${cleanId}/mqdefault.jpg`;
    const hq = `https://i.ytimg.com/vi/${cleanId}/hqdefault.jpg`;

    if (!candidates.includes(mq)) candidates.push(mq);
    if (!candidates.includes(hq)) candidates.push(hq);
  }

  return candidates;
}

/**
 * Neutral 16:9 placeholder rendered while loading or when no thumbnail can be retrieved.
 */
export function YouTubeThumbnailPlaceholder({
  title,
  hasError = false,
}: {
  title: string;
  hasError?: boolean;
}) {
  return (
    <div
      role="img"
      aria-label={`Thumbnail placeholder for ${title}`}
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%)',
        color: 'var(--text-muted, #94a3b8)',
        userSelect: 'none',
      }}
    >
      <div
        style={{
          width: 38,
          height: 38,
          borderRadius: '50%',
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 16,
          boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
        }}
      >
        {hasError ? '🎬' : '▶'}
      </div>
      <span
        style={{
          fontSize: 10,
          fontWeight: 500,
          letterSpacing: '0.03em',
          textTransform: 'uppercase',
          opacity: 0.7,
        }}
      >
        {hasError ? 'Preview Unavailable' : 'YouTube Video'}
      </span>
    </div>
  );
}

/**
 * Production-ready 16:9 YouTube video thumbnail component.
 * Features:
 * - Strict 16:9 aspect ratio container with object-fit: cover
 * - Resilient fallback chain (provided URL -> mqdefault -> hqdefault -> placeholder)
 * - Prevents layout disruption on image load failures
 * - Duration overlay badge
 * - Lazy loading for viewport performance
 * - Stops click propagation so clicking the thumbnail does not trigger unintended actions
 */
export function YouTubeVideoThumbnail({
  videoId,
  title,
  thumbnailUrl,
  duration,
  className = '',
  style = {},
}: YouTubeVideoThumbnailProps) {
  const candidates = getYouTubeThumbnailCandidates(videoId, thumbnailUrl);
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Reset candidate index when video ID or thumbnail URL changes
  useEffect(() => {
    setCandidateIndex(0);
    setHasError(candidates.length === 0);
    setIsLoading(candidates.length > 0);
  }, [videoId, thumbnailUrl]);

  const currentSrc = candidates[candidateIndex];

  const handleImageError = () => {
    if (candidateIndex + 1 < candidates.length) {
      // Try next candidate in the fallback chain
      setCandidateIndex(prev => prev + 1);
    } else {
      // All candidates exhausted, render neutral placeholder
      setHasError(true);
      setIsLoading(false);
    }
  };

  const handleImageLoad = () => {
    setIsLoading(false);
    setHasError(false);
  };

  const durationBadge = formatDurationTimestamp(duration);

  return (
    <div
      className={`youtube-thumbnail-container ${className}`}
      onClick={(e) => {
        // Prevent thumbnail click from triggering accidental card selection/actions
        e.stopPropagation();
      }}
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '16 / 9',
        borderRadius: 8,
        overflow: 'hidden',
        background: 'linear-gradient(135deg, #161b26 0%, #0d111a 100%)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'default',
        ...style,
      }}
    >
      {/* Fallback Placeholder (shown when no URL or when all candidates fail) */}
      {(!currentSrc || hasError) ? (
        <YouTubeThumbnailPlaceholder title={title} hasError={hasError} />
      ) : (
        <>
          {/* Subtle loading shimmer placeholder while downloading */}
          {isLoading && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%)',
                zIndex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  border: '2px solid rgba(124, 108, 240, 0.3)',
                  borderTopColor: 'var(--accent, #7c6cf0)',
                  animation: 'spin 1s linear infinite',
                }}
              />
            </div>
          )}

          {/* Actual 16:9 Source Image */}
          <img
            src={currentSrc}
            alt={title ? `Thumbnail for ${title}` : 'YouTube Video Thumbnail'}
            loading="lazy"
            decoding="async"
            onLoad={handleImageLoad}
            onError={handleImageError}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              objectPosition: 'center',
              display: 'block',
              transition: 'transform 0.25s ease, opacity 0.2s ease',
              opacity: isLoading ? 0 : 1,
            }}
          />
        </>
      )}

      {/* Duration Badge Overlay in Bottom-Right Corner */}
      {durationBadge && !hasError && (
        <span
          style={{
            position: 'absolute',
            bottom: 6,
            right: 6,
            background: 'rgba(0, 0, 0, 0.82)',
            backdropFilter: 'blur(4px)',
            color: '#f8fafc',
            fontSize: 10,
            fontWeight: 700,
            padding: '2px 6px',
            borderRadius: 4,
            letterSpacing: '0.04em',
            lineHeight: 1.2,
            boxShadow: '0 2px 4px rgba(0,0,0,0.5)',
            zIndex: 2,
            pointerEvents: 'none',
          }}
        >
          {durationBadge}
        </span>
      )}
    </div>
  );
}
