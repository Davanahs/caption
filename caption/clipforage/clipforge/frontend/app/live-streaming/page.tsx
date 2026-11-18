'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import {
  validateLiveStreamUrl,
  startLiveStreamMonitoring,
  getLiveStreamJobs,
  getLiveStreamJobDetails,
  stopLiveStreamMonitoring,
  resumeLiveStreamMonitoring,
  checkLiveStreamNow,
  deleteLiveStreamJob,
  type LiveStreamValidation,
  type LiveStreamJobSummary,
  type LiveStreamJobDetails,
  type LiveStreamClipItem,
} from '@/lib/api';

const PIPELINE_STAGES = [
  { id: 1, label: 'Inspection', icon: '📡', desc: 'Syncing live metadata' },
  { id: 2, label: 'Capture', icon: '📥', desc: 'Downloading footage slice' },
  { id: 3, label: 'Transcribe', icon: '🎙️', desc: 'Whisper speech-to-text' },
  { id: 4, label: 'Highlights', icon: '🤖', desc: 'AI viral moment detection' },
  { id: 5, label: '9:16 Shorts', icon: '🎬', desc: 'Vertical reframing (1080x1920)' },
  { id: 6, label: 'Library Ready', icon: '✅', desc: 'Saved & ready to publish' },
];

function getActiveStageIndex(step: string = '', status: string = ''): number {
  if (status === 'completed') return 6;
  const s = (step || '').toLowerCase();
  if (s.includes('rendering') || s.includes('vertical')) return 5;
  if (s.includes('analyzing') || s.includes('highlights') || s.includes('viral')) return 4;
  if (s.includes('transcribing') || s.includes('speech') || s.includes('audio')) return 3;
  if (s.includes('downloading') || s.includes('footage')) return 2;
  if (s.includes('inspecting') || s.includes('starting')) return 1;
  if (s.includes('waiting') || status === 'waiting') return 6;
  return 1;
}

function formatSeconds(sec: number): string {
  if (!sec || isNaN(sec) || sec <= 0) return '00:00';
  const total = Math.floor(sec);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) {
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function formatRelativeTime(isoString?: string | null): string {
  if (!isoString) return '—';
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffSec = Math.floor((date.getTime() - now.getTime()) / 1000);

    if (diffSec > 0) {
      if (diffSec < 60) return `in ${diffSec}s`;
      const min = Math.ceil(diffSec / 60);
      return `in ~${min}m`;
    }

    const pastSec = Math.abs(diffSec);
    if (pastSec < 60) return `${pastSec}s ago`;
    const pastMin = Math.floor(pastSec / 60);
    if (pastMin < 60) return `${pastMin}m ago`;
    const hours = Math.floor(pastMin / 60);
    return `${hours}h ago`;
  } catch {
    return isoString;
  }
}

export default function LiveStreamingPage() {
  // Input & validation state
  const [url, setUrl] = useState('');
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState<LiveStreamValidation | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Settings state
  const [clipCountPreset, setClipCountPreset] = useState<'5' | '10' | '15' | '20' | 'custom'>('10');
  const [customClipCount, setCustomClipCount] = useState('10');
  const [distributionMode, setDistributionMode] = useState<'ai_highlights' | 'equal_split'>('ai_highlights');
  const [starting, setStarting] = useState(false);

  // Monitoring active job state
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobDetails, setJobDetails] = useState<LiveStreamJobDetails | null>(null);
  const [allJobs, setAllJobs] = useState<LiveStreamJobSummary[]>([]);
  const [loadingDetails, setLoadingDetails] = useState(false);

  // Stop confirmation modal
  const [showStopModal, setShowStopModal] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [triggeringCheck, setTriggeringCheck] = useState(false);

  // Preview video modal
  const [previewClip, setPreviewClip] = useState<LiveStreamClipItem | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const handleCheckNow = async () => {
    if (!activeJobId) return;
    setTriggeringCheck(true);
    try {
      await checkLiveStreamNow(activeJobId);
      await fetchJobDetails(activeJobId);
      await refreshJobsList();
    } catch (e: any) {
      console.warn('Failed to trigger check now:', e);
    } finally {
      setTriggeringCheck(false);
    }
  };

  // Load all jobs on initial mount
  const refreshJobsList = useCallback(async () => {
    try {
      const res = await getLiveStreamJobs();
      setAllJobs(res.items || []);
      // If no activeJobId is selected, auto-select the first monitoring/processing job
      if (!activeJobId && res.items && res.items.length > 0) {
        const activeOne = res.items.find(j => ['monitoring', 'processing', 'waiting'].includes(j.status));
        if (activeOne) {
          setActiveJobId(activeOne.id);
        } else {
          setActiveJobId(res.items[0].id);
        }
      }
    } catch (e: any) {
      console.warn('Failed to load livestream jobs:', e);
    }
  }, [activeJobId]);

  useEffect(() => {
    refreshJobsList();
  }, [refreshJobsList]);

  // Fetch active job details
  const fetchJobDetails = useCallback(async (jobId: string) => {
    try {
      const details = await getLiveStreamJobDetails(jobId);
      setJobDetails(details);
    } catch (e: any) {
      console.warn('Failed to fetch job details:', e);
    }
  }, []);

  useEffect(() => {
    if (!activeJobId) {
      setJobDetails(null);
      return;
    }
    fetchJobDetails(activeJobId);

    // Auto-polling when viewing a job
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    const isRunning = jobDetails?.status === 'processing' || jobDetails?.status === 'monitoring';
    const interval = isRunning ? 2000 : 5000;

    pollIntervalRef.current = setInterval(() => {
      fetchJobDetails(activeJobId);
      refreshJobsList();
    }, interval);

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [activeJobId, jobDetails?.status, fetchJobDetails, refreshJobsList]);

  // Validate URL on click or paste
  const handleValidateUrl = async () => {
    const trimmed = url.trim();
    if (!trimmed) {
      setValidationError('Please enter a YouTube livestream URL.');
      setValidation(null);
      return;
    }

    setValidating(true);
    setValidationError(null);
    setValidation(null);

    try {
      const res = await validateLiveStreamUrl(trimmed);
      setValidation(res);
      if (res.is_already_monitored && res.existing_job_id) {
        setActiveJobId(res.existing_job_id);
      }
    } catch (e: any) {
      setValidationError(e.message || 'Failed to validate livestream URL.');
    } finally {
      setValidating(false);
    }
  };

  // Start monitoring
  const handleStartMonitoring = async () => {
    if (!validation || !validation.valid) return;

    const count = clipCountPreset === 'custom' ? parseInt(customClipCount, 10) || 10 : parseInt(clipCountPreset, 10);
    setStarting(true);

    try {
      const res = await startLiveStreamMonitoring({
        youtube_url: url.trim(),
        clip_count: count,
        clip_generation_mode: distributionMode,
      });

      setActiveJobId(res.job_id);
      setUrl('');
      setValidation(null);
      await refreshJobsList();
      await fetchJobDetails(res.job_id);
    } catch (e: any) {
      alert(`Could not start live monitoring: ${e.message}`);
    } finally {
      setStarting(false);
    }
  };

  // Stop monitoring
  const handleConfirmStop = async () => {
    if (!activeJobId) return;
    setStopping(true);
    try {
      await stopLiveStreamMonitoring(activeJobId);
      setShowStopModal(false);
      await fetchJobDetails(activeJobId);
      await refreshJobsList();
    } catch (e: any) {
      alert(`Failed to stop monitoring: ${e.message}`);
    } finally {
      setStopping(false);
    }
  };

  // Resume monitoring
  const handleResume = async (jobId: string) => {
    setResuming(true);
    try {
      await resumeLiveStreamMonitoring(jobId);
      await fetchJobDetails(jobId);
      await refreshJobsList();
    } catch (e: any) {
      alert(`Failed to resume monitoring: ${e.message}`);
    } finally {
      setResuming(false);
    }
  };

  // Calculate timeline percentages
  const totalDur = Math.max(jobDetails?.total_duration || 0, jobDetails?.processed_until || 0, 1);
  const processedSec = jobDetails?.processed_until || 0;
  const processedPercent = Math.min(100, Math.max(0, (processedSec / totalDur) * 100));

  const isJobActive = jobDetails && ['monitoring', 'processing', 'waiting'].includes(jobDetails.status);
  const isJobStopped = jobDetails?.status === 'stopped';
  const isJobCompleted = jobDetails?.status === 'completed';

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '24px 20px 80px' }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 12,
              background: 'linear-gradient(135deg, #ef4444, #8b5cf6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 22,
              boxShadow: '0 0 20px rgba(239, 68, 68, 0.4)',
            }}
          >
            📡
          </div>
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 700, color: '#f8fafc', margin: 0, letterSpacing: '-0.02em' }}>
              Live Streaming Studio
            </h1>
            <p style={{ fontSize: 14, color: '#94a3b8', margin: '4px 0 0' }}>
              Submit a YouTube livestream once. ClipForge will automatically monitor, capture, and generate viral 9:16 shorts as the stream progresses.
            </p>
          </div>
        </div>
      </div>

      {/* Grid: Submission & Settings */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 24, marginBottom: 32 }}>
        {/* Left Column: URL Input & Validation */}
        <div
          style={{
            background: 'rgba(18, 22, 38, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 16,
            padding: 24,
            backdropFilter: 'blur(16px)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <span style={{ fontSize: 18 }}>🔴</span>
            <h2 style={{ fontSize: 17, fontWeight: 600, color: '#f1f5f9', margin: 0 }}>
              Live Stream URL Submission
            </h2>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 8 }}>
              YouTube Livestream Link
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                type="text"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  setValidationError(null);
                }}
                onKeyDown={(e) => e.key === 'Enter' && handleValidateUrl()}
                placeholder="https://www.youtube.com/live/... or watch?v=..."
                style={{
                  flex: 1,
                  background: 'rgba(0, 0, 0, 0.35)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: 10,
                  padding: '10px 14px',
                  color: '#fff',
                  fontSize: 14,
                  outline: 'none',
                }}
              />
              <button
                type="button"
                onClick={handleValidateUrl}
                disabled={validating || !url.trim()}
                style={{
                  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  border: 'none',
                  borderRadius: 10,
                  padding: '0 18px',
                  color: '#fff',
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: validating || !url.trim() ? 'not-allowed' : 'pointer',
                  opacity: validating || !url.trim() ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  whiteSpace: 'nowrap',
                }}
              >
                {validating ? (
                  <>
                    <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>⏳</span>
                    Checking...
                  </>
                ) : (
                  'Validate'
                )}
              </button>
            </div>
          </div>

          {/* Validation Error Message */}
          {validationError && (
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: 10,
                padding: '12px 14px',
                color: '#fca5a5',
                fontSize: 13,
                marginBottom: 16,
              }}
            >
              ⚠️ {validationError}
            </div>
          )}

          {/* Stream Detection Result Card */}
          {validation && (
            <div
              style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 12,
                padding: 16,
                marginBottom: 16,
              }}
            >
              <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                {validation.thumbnail_url ? (
                  <div style={{ position: 'relative', width: 110, height: 68, borderRadius: 8, overflow: 'hidden', flexShrink: 0 }}>
                    <img
                      src={validation.thumbnail_url}
                      alt={validation.title}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                    {validation.is_live && (
                      <span
                        style={{
                          position: 'absolute',
                          top: 4,
                          left: 4,
                          background: '#ef4444',
                          color: '#fff',
                          fontSize: 9,
                          fontWeight: 700,
                          padding: '2px 5px',
                          borderRadius: 4,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4,
                        }}
                      >
                        <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#fff' }} />
                        LIVE
                      </span>
                    )}
                  </div>
                ) : null}

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        padding: '2px 8px',
                        borderRadius: 6,
                        textTransform: 'uppercase',
                        background: validation.is_live
                          ? 'rgba(239, 68, 68, 0.2)'
                          : validation.live_status === 'is_upcoming'
                          ? 'rgba(245, 158, 11, 0.2)'
                          : 'rgba(148, 163, 184, 0.2)',
                        color: validation.is_live
                          ? '#f87171'
                          : validation.live_status === 'is_upcoming'
                          ? '#fbbf24'
                          : '#94a3b8',
                      }}
                    >
                      {validation.is_live
                        ? '🔴 Live Now'
                        : validation.live_status === 'is_upcoming'
                        ? '⏳ Upcoming'
                        : validation.live_status === 'was_live'
                        ? '⚪ Past Livestream'
                        : 'Uploaded Video'}
                    </span>
                    {validation.channel_name && (
                      <span style={{ fontSize: 12, color: '#94a3b8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {validation.channel_name}
                      </span>
                    )}
                  </div>
                  <h3
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      color: '#f8fafc',
                      margin: 0,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                    title={validation.title}
                  >
                    {validation.title}
                  </h3>
                  <p style={{ fontSize: 12, color: '#cbd5e1', margin: '6px 0 0' }}>
                    {validation.message}
                  </p>
                </div>
              </div>

              {/* Duplicate Alert */}
              {validation.is_already_monitored && validation.existing_job_id && (
                <div
                  style={{
                    marginTop: 12,
                    padding: '8px 12px',
                    borderRadius: 8,
                    background: 'rgba(99, 102, 241, 0.15)',
                    border: '1px solid rgba(99, 102, 241, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <span style={{ fontSize: 12, color: '#c7d2fe' }}>
                    Monitoring job already active for this stream.
                  </span>
                  <button
                    type="button"
                    onClick={() => setActiveJobId(validation.existing_job_id!)}
                    style={{
                      background: '#6366f1',
                      border: 'none',
                      color: '#fff',
                      fontSize: 11,
                      fontWeight: 600,
                      padding: '4px 10px',
                      borderRadius: 6,
                      cursor: 'pointer',
                    }}
                  >
                    View Job
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Quick instructions */}
          <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
            💡 Tip: Livestreams are sampled automatically from the start, and new footage is processed every 20 minutes without reprocessing old segments.
          </div>
        </div>

        {/* Right Column: Clip Generation Settings */}
        <div
          style={{
            background: 'rgba(18, 22, 38, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 16,
            padding: 24,
            backdropFilter: 'blur(16px)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <span style={{ fontSize: 18 }}>⚙️</span>
              <h2 style={{ fontSize: 17, fontWeight: 600, color: '#f1f5f9', margin: 0 }}>
                Clip Generation Settings
              </h2>
            </div>

            {/* A. Number of Clips */}
            <div style={{ marginBottom: 18 }}>
              <label style={{ display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 8 }}>
                Target Number of Clips
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {(['5', '10', '15', '20'] as const).map((count) => (
                  <button
                    key={count}
                    type="button"
                    onClick={() => setClipCountPreset(count)}
                    style={{
                      background: clipCountPreset === count ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.04)',
                      border: clipCountPreset === count ? '1px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: 8,
                      padding: '6px 14px',
                      color: clipCountPreset === count ? '#a5b4fc' : '#cbd5e1',
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                  >
                    {count} Clips {count === '10' ? '✨' : ''}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setClipCountPreset('custom')}
                  style={{
                    background: clipCountPreset === 'custom' ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.04)',
                    border: clipCountPreset === 'custom' ? '1px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: 8,
                    padding: '6px 14px',
                    color: clipCountPreset === 'custom' ? '#a5b4fc' : '#cbd5e1',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Custom
                </button>
              </div>

              {clipCountPreset === 'custom' && (
                <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    value={customClipCount}
                    onChange={(e) => setCustomClipCount(e.target.value)}
                    style={{
                      width: 100,
                      background: 'rgba(0,0,0,0.3)',
                      border: '1px solid rgba(255,255,255,0.15)',
                      borderRadius: 8,
                      padding: '6px 10px',
                      color: '#fff',
                      fontSize: 13,
                    }}
                  />
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>clips (1 - 50)</span>
                </div>
              )}
            </div>

            {/* B. Equal Distribution Mode */}
            <div style={{ marginBottom: 18 }}>
              <label style={{ display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 8 }}>
                Selection Strategy
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div
                  onClick={() => setDistributionMode('ai_highlights')}
                  style={{
                    background: distributionMode === 'ai_highlights' ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                    border: distributionMode === 'ai_highlights' ? '1px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: 10,
                    padding: 12,
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 14 }}>⚡</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>
                      AI Highlights
                    </span>
                    <span style={{ fontSize: 10, background: '#6366f1', color: '#fff', padding: '1px 5px', borderRadius: 4 }}>
                      Recommended
                    </span>
                  </div>
                  <p style={{ fontSize: 11, color: '#94a3b8', margin: 0, lineHeight: 1.4 }}>
                    Prioritizes high energy, humor, and viral engagement moments.
                  </p>
                </div>

                <div
                  onClick={() => setDistributionMode('equal_split')}
                  style={{
                    background: distributionMode === 'equal_split' ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                    border: distributionMode === 'equal_split' ? '1px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: 10,
                    padding: 12,
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 14 }}>⏱️</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>
                      Evenly Distributed
                    </span>
                  </div>
                  <p style={{ fontSize: 11, color: '#94a3b8', margin: 0, lineHeight: 1.4 }}>
                    Spreads highlights across the full stream footage timeline.
                  </p>
                </div>
              </div>
            </div>

            {/* C. Video Aspect Ratio Badge */}
            <div
              style={{
                background: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                borderRadius: 10,
                padding: '10px 14px',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                marginBottom: 20,
              }}
            >
              <span style={{ fontSize: 18 }}>📱</span>
              <div style={{ fontSize: 12, color: '#6ee7b7', lineHeight: 1.4 }}>
                <strong>9:16 Vertical Shorts Format (1080×1920)</strong>
                <br />
                Automatically converts 16:9 gameplay and speakers with smart reframing without stretching.
              </div>
            </div>
          </div>

          {/* Start Monitoring Button */}
          <button
            type="button"
            onClick={handleStartMonitoring}
            disabled={starting || !validation || !validation.valid || validation.is_already_monitored || (!validation.is_live && validation.live_status !== 'is_live')}
            style={{
              width: '100%',
              background: 'linear-gradient(135deg, #ef4444, #8b5cf6)',
              border: 'none',
              borderRadius: 12,
              padding: '14px',
              color: '#fff',
              fontSize: 15,
              fontWeight: 700,
              cursor: starting || !validation || !validation.valid || validation.is_already_monitored || (!validation.is_live && validation.live_status !== 'is_live') ? 'not-allowed' : 'pointer',
              opacity: starting || !validation || !validation.valid || validation.is_already_monitored || (!validation.is_live && validation.live_status !== 'is_live') ? 0.5 : 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              boxShadow: '0 4px 20px rgba(239, 68, 68, 0.3)',
              transition: 'all 0.2s',
            }}
          >
            {starting ? (
              <>
                <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>⏳</span>
                Starting Live Monitoring Pipeline...
              </>
            ) : (
              <>
                <span>📡</span>
                Start Live Stream Monitoring
              </>
            )}
          </button>
        </div>
      </div>

      {/* Progress Monitoring Dashboard */}
      {jobDetails && (
        <div
          style={{
            background: 'rgba(18, 22, 38, 0.9)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 16,
            padding: 24,
            marginBottom: 32,
            backdropFilter: 'blur(20px)',
          }}
        >
          {/* Dashboard Header */}
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              {jobDetails.thumbnail_url && (
                <img
                  src={jobDetails.thumbnail_url}
                  alt={jobDetails.video_title}
                  style={{ width: 68, height: 42, borderRadius: 8, objectFit: 'cover' }}
                />
              )}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  {/* Status Badge */}
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '3px 10px',
                      borderRadius: 6,
                      textTransform: 'uppercase',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      background: isJobActive
                        ? 'rgba(239, 68, 68, 0.2)'
                        : isJobCompleted
                        ? 'rgba(16, 185, 129, 0.2)'
                        : 'rgba(148, 163, 184, 0.2)',
                      color: isJobActive
                        ? '#f87171'
                        : isJobCompleted
                        ? '#34d399'
                        : '#94a3b8',
                    }}
                  >
                    {isJobActive && (
                      <span
                        style={{
                          width: 7,
                          height: 7,
                          borderRadius: '50%',
                          background: '#ef4444',
                          animation: 'pulse 1.5s infinite',
                        }}
                      />
                    )}
                    {jobDetails.status.toUpperCase()}
                  </span>
                  <span style={{ fontSize: 13, color: '#94a3b8' }}>
                    {jobDetails.channel_name || 'YouTube Stream'}
                  </span>
                </div>
                <h2 style={{ fontSize: 18, fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                  {jobDetails.video_title}
                </h2>
              </div>
            </div>

            {/* Actions: Stop / Resume / Clips Library */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {isJobActive && (
                <button
                  type="button"
                  onClick={() => setShowStopModal(true)}
                  style={{
                    background: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    color: '#f87171',
                    borderRadius: 8,
                    padding: '8px 16px',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  ⏹️ Stop Monitoring
                </button>
              )}

              {isJobStopped && (
                <button
                  type="button"
                  onClick={() => handleResume(jobDetails.id)}
                  disabled={resuming}
                  style={{
                    background: 'linear-gradient(135deg, #10b981, #059669)',
                    border: 'none',
                    color: '#fff',
                    borderRadius: 8,
                    padding: '8px 16px',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: resuming ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  ▶️ Resume Monitoring
                </button>
              )}

              {jobDetails.status === 'waiting' && !isJobStopped && (
                <button
                  type="button"
                  onClick={handleCheckNow}
                  disabled={triggeringCheck}
                  style={{
                    background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                    border: 'none',
                    color: '#fff',
                    borderRadius: 8,
                    padding: '8px 16px',
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: triggeringCheck ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    boxShadow: '0 2px 8px rgba(59, 130, 246, 0.3)',
                  }}
                >
                  {triggeringCheck ? '⏳ Triggering...' : '⚡ Process Next Footage Now'}
                </button>
              )}

              <Link
                href="/clips"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#cbd5e1',
                  borderRadius: 8,
                  padding: '8px 16px',
                  fontSize: 13,
                  fontWeight: 600,
                  textDecoration: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                🎬 View Clips Library
              </Link>
            </div>
          </div>

          {/* Visual Timeline Progress Bar */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
              <span>Already Processed: <strong style={{ color: '#a5b4fc' }}>{formatSeconds(jobDetails.processed_until)}</strong></span>
              <span>Total Available Footage: <strong style={{ color: '#f8fafc' }}>{formatSeconds(jobDetails.total_duration)}</strong></span>
            </div>

            <div
              style={{
                height: 12,
                borderRadius: 6,
                background: 'rgba(0, 0, 0, 0.5)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: `${processedPercent}%`,
                  height: '100%',
                  background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
                  borderRadius: 6,
                  transition: 'width 0.4s ease',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#64748b', marginTop: 4 }}>
              <span>00:00:00 (Stream Start)</span>
              <span>Checkpoint: {formatSeconds(jobDetails.processed_until)}</span>
              <span>Stream Live Edge</span>
            </div>
          </div>

          {/* Active Processing Stage Stepper & Live Status Ticker */}
          <div
            style={{
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 12,
              padding: '16px 20px',
              marginBottom: 20,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span
                  style={{
                    display: 'inline-block',
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: isJobActive ? '#10b981' : '#64748b',
                    boxShadow: isJobActive ? '0 0 8px #10b981' : 'none',
                  }}
                />
                <span style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Live Pipeline Steps & Real-Time Status
                </span>
                {isJobActive && (
                  <span
                    style={{
                      fontSize: 11,
                      color: '#a5b4fc',
                      background: 'rgba(99, 102, 241, 0.15)',
                      padding: '2px 8px',
                      borderRadius: 12,
                      border: '1px solid rgba(99, 102, 241, 0.3)',
                    }}
                  >
                    Live Auto-Polling (2s)
                  </span>
                )}
              </div>

              {jobDetails.next_check_at && isJobActive && jobDetails.status === 'waiting' && (
                <span style={{ fontSize: 12, color: '#f59e0b', fontWeight: 600 }}>
                  Next automatic check: {formatRelativeTime(jobDetails.next_check_at)}
                </span>
              )}
            </div>

            {/* Current Step Banner with Status */}
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 8,
                background: isJobActive ? 'rgba(99, 102, 241, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                border: isJobActive ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid rgba(255, 255, 255, 0.06)',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                marginBottom: 16,
              }}
            >
              <span style={{ fontSize: 18 }}>
                {jobDetails.status === 'processing' ? '⚙️' : jobDetails.status === 'waiting' ? '⏳' : isJobCompleted ? '✅' : '⏹️'}
              </span>
              <span style={{ fontSize: 14, color: '#e2e8f0', fontWeight: 600 }}>
                {jobDetails.current_step || 'Monitoring stream status...'}
              </span>
            </div>

            {/* 6 Step Progress Stepper Pills */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
              {PIPELINE_STAGES.map((stg) => {
                const activeIdx = getActiveStageIndex(jobDetails.current_step, jobDetails.status);
                const isCompleted = activeIdx > stg.id || (stg.id === 6 && jobDetails.clips_generated_count > 0);
                const isCurrent = activeIdx === stg.id && jobDetails.status === 'processing';
                return (
                  <div
                    key={stg.id}
                    style={{
                      background: isCurrent
                        ? 'rgba(99, 102, 241, 0.18)'
                        : isCompleted
                        ? 'rgba(16, 185, 129, 0.08)'
                        : 'rgba(255, 255, 255, 0.02)',
                      border: isCurrent
                        ? '1px solid #818cf8'
                        : isCompleted
                        ? '1px solid rgba(16, 185, 129, 0.3)'
                        : '1px solid rgba(255, 255, 255, 0.05)',
                      borderRadius: 8,
                      padding: '8px 10px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 2,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 13 }}>{stg.icon}</span>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: isCurrent ? '#a5b4fc' : isCompleted ? '#34d399' : '#64748b',
                        }}
                      >
                        {isCompleted ? '✓ Done' : isCurrent ? '● Active' : `Step ${stg.id}`}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: isCurrent ? '#fff' : isCompleted ? '#e2e8f0' : '#94a3b8' }}>
                      {stg.label}
                    </div>
                    <div style={{ fontSize: 10, color: '#64748b' }}>
                      {stg.desc}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Stats Metrics Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
            <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>CLIPS GENERATED</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#a5b4fc' }}>
                {jobDetails.clips_generated_count} <span style={{ fontSize: 13, color: '#64748b' }}>/ {jobDetails.clips_count}</span>
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>CHECKPOINT SECONDS</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#f8fafc' }}>
                {formatSeconds(jobDetails.processed_until)}
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>CHECK INTERVAL</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#f8fafc' }}>
                {jobDetails.monitoring_interval_minutes}m
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>DISTRIBUTION MODE</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#cbd5e1', textTransform: 'capitalize' }}>
                {jobDetails.clip_generation_mode === 'equal_split' ? 'Evenly Distributed' : 'AI Highlights'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Generated Clips in Current Session */}
      {jobDetails && jobDetails.clips && jobDetails.clips.length > 0 && (
        <div style={{ marginBottom: 40 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: '#f8fafc', margin: 0 }}>
              Generated 9:16 Shorts ({jobDetails.clips.length})
            </h2>
            <Link
              href="/clips"
              style={{ color: '#a5b4fc', fontSize: 13, textDecoration: 'none', fontWeight: 600 }}
            >
              Manage in Clips Library →
            </Link>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
              gap: 20,
            }}
          >
            {jobDetails.clips.map((clip) => (
              <div
                key={clip.id}
                style={{
                  background: 'rgba(18, 22, 38, 0.85)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 14,
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                {/* 9:16 Vertical Thumbnail Preview */}
                <div
                  style={{
                    position: 'relative',
                    aspectRatio: '9/16',
                    background: '#000',
                    overflow: 'hidden',
                  }}
                >
                  {clip.thumbnail_path ? (
                    <img
                      src={`/api/clips/${clip.id}/thumbnail`}
                      alt={clip.title}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  ) : (
                    <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
                      🎬
                    </div>
                  )}

                  {/* Viral Score Badge */}
                  <span
                    style={{
                      position: 'absolute',
                      top: 10,
                      right: 10,
                      background: 'rgba(0, 0, 0, 0.75)',
                      backdropFilter: 'blur(8px)',
                      color: '#fbbf24',
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: 6,
                      border: '1px solid rgba(251, 191, 36, 0.4)',
                    }}
                  >
                    ★ {clip.score?.toFixed(1) || '8.5'}
                  </span>

                  {/* Timestamp & Duration Badge */}
                  <span
                    style={{
                      position: 'absolute',
                      bottom: 10,
                      left: 10,
                      background: 'rgba(0, 0, 0, 0.75)',
                      color: '#f8fafc',
                      fontSize: 11,
                      fontWeight: 600,
                      padding: '2px 6px',
                      borderRadius: 4,
                    }}
                  >
                    {formatSeconds(clip.duration)}
                  </span>
                </div>

                <div style={{ padding: 14, flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <div>
                    <h4
                      style={{
                        fontSize: 14,
                        fontWeight: 600,
                        color: '#f8fafc',
                        margin: '0 0 4px',
                        lineHeight: 1.3,
                      }}
                    >
                      {clip.title}
                    </h4>
                    <p style={{ fontSize: 11, color: '#94a3b8', margin: 0 }}>
                      Stream range: {formatSeconds(clip.start_time)} - {formatSeconds(clip.end_time)}
                    </p>
                  </div>

                  <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                    <button
                      type="button"
                      onClick={() => setPreviewClip(clip)}
                      style={{
                        flex: 1,
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid rgba(255, 255, 255, 0.12)',
                        borderRadius: 8,
                        padding: '6px',
                        color: '#fff',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      ▶ Preview
                    </button>
                    <Link
                      href={`/publish?clip=${clip.id}`}
                      style={{
                        flex: 1,
                        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                        border: 'none',
                        borderRadius: 8,
                        padding: '6px',
                        color: '#fff',
                        fontSize: 12,
                        fontWeight: 600,
                        textDecoration: 'none',
                        textAlign: 'center',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      🚀 Publish
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Monitoring History Table */}
      {allJobs.length > 0 && (
        <div
          style={{
            background: 'rgba(18, 22, 38, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 16,
            padding: 24,
            backdropFilter: 'blur(16px)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, color: '#f8fafc', margin: 0 }}>
              Live Monitoring History & Sessions
            </h3>
            <span style={{ fontSize: 12, color: '#64748b' }}>
              {allJobs.length} session{allJobs.length !== 1 ? 's' : ''}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {allJobs.map((j) => (
              <div
                key={j.id}
                onClick={() => setActiveJobId(j.id)}
                style={{
                  background: activeJobId === j.id ? 'rgba(99, 102, 241, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                  border: activeJobId === j.id ? '1px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.06)',
                  borderRadius: 10,
                  padding: '12px 16px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  {j.thumbnail_url && (
                    <img
                      src={j.thumbnail_url}
                      alt={j.video_title}
                      style={{ width: 44, height: 28, borderRadius: 4, objectFit: 'cover' }}
                    />
                  )}
                  <div>
                    <h4 style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc', margin: '0 0 2px' }}>
                      {j.video_title}
                    </h4>
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>
                      {j.channel_name || 'YouTube Stream'} • Processed: {formatSeconds(j.processed_until)}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: 12, color: '#a5b4fc', fontWeight: 600 }}>
                    {j.clips_generated} clips
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: 4,
                      textTransform: 'uppercase',
                      background: ['monitoring', 'processing', 'waiting'].includes(j.status)
                        ? 'rgba(239, 68, 68, 0.2)'
                        : j.status === 'completed'
                        ? 'rgba(16, 185, 129, 0.2)'
                        : 'rgba(148, 163, 184, 0.2)',
                      color: ['monitoring', 'processing', 'waiting'].includes(j.status)
                        ? '#f87171'
                        : j.status === 'completed'
                        ? '#34d399'
                        : '#94a3b8',
                    }}
                  >
                    {j.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stop Monitoring Confirmation Modal */}
      {showStopModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 20,
            backdropFilter: 'blur(8px)',
          }}
        >
          <div
            style={{
              background: '#121626',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: 16,
              padding: 24,
              maxWidth: 440,
              width: '100%',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <span style={{ fontSize: 22 }}>⚠️</span>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                Stop Monitoring Livestream?
              </h3>
            </div>
            <p style={{ fontSize: 14, color: '#cbd5e1', lineHeight: 1.5, marginBottom: 20 }}>
              This will pause future 20-minute checks. All clips generated so far and the current timestamp checkpoint will be safely preserved. You can resume monitoring anytime.
            </p>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setShowStopModal(false)}
                style={{
                  background: 'rgba(255, 255, 255, 0.08)',
                  border: 'none',
                  borderRadius: 8,
                  padding: '10px 16px',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmStop}
                disabled={stopping}
                style={{
                  background: '#ef4444',
                  border: 'none',
                  borderRadius: 8,
                  padding: '10px 18px',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: stopping ? 'not-allowed' : 'pointer',
                }}
              >
                {stopping ? 'Stopping...' : 'Yes, Stop Monitoring'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Clip Preview Modal */}
      {previewClip && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.85)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 20,
            backdropFilter: 'blur(10px)',
          }}
          onClick={() => setPreviewClip(null)}
        >
          <div
            style={{
              background: '#121626',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 16,
              padding: 20,
              maxWidth: 420,
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: '#f8fafc', margin: 0 }}>
                {previewClip.title}
              </h3>
              <button
                type="button"
                onClick={() => setPreviewClip(null)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: 18, cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <div style={{ width: '100%', aspectRatio: '9/16', background: '#000', borderRadius: 12, overflow: 'hidden' }}>
              <video
                src={`/api/clips/${previewClip.id}/download`}
                controls
                autoPlay
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
