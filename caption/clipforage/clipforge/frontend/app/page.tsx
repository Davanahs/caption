'use client';
import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getStats,
  submitYouTubeUrl,
  submitBatchYouTubeUrls,
  uploadVideoFile,
  listJobs,
  getActiveJobs,
  getJobHistory,
  getJob,
  cancelJob,
  getJobStats,
  retryJob,
  type QueueStats,
} from '@/lib/api';
import LayoutThumbnailSelector from '@/components/LayoutThumbnailSelector';
import ProcessVideoModal, { ProcessVideoConfig } from '@/components/ProcessVideoModal';
import PodcastSelectionModal, { PodcastProcessingConfig } from '@/components/PodcastSelectionModal';

// WebSocket base — ws:// equivalent of API_BASE
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE = API_BASE.replace(/^http/, 'ws');

interface Stats { total_videos: number; total_clips: number; published_clips: number; active_channels: number; }
interface Job {
  id: string;
  video_id?: string | null;
  status: string;
  progress: number;
  current_step: string | null;
  source_url: string | null;
  source_title: string | null;
  error_message: string | null;
  created_at: string | null;
  created_at_ist?: string | null;
  updated_at: string | null;
  updated_at_ist?: string | null;
  thumbnail_url?: string | null;
  pipeline_started_at?: string | null;
  completed_at?: string | null;
  is_test?: boolean;
}

function formatISTDate(iso: string | null | undefined, istStr?: string | null): string {
  if (istStr) return istStr;
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    }).format(new Date(iso)) + ' IST';
  } catch {
    return iso;
  }
}

function formatCompactIST(iso: string | null | undefined, istStr?: string | null): string {
  if (istStr) {
    const parts = istStr.replace(' IST', '').split(', ');
    if (parts.length === 2) {
      const d = parts[0];
      const t = parts[1].replace(/:\d{2} /, ' ');
      const dShort = d.replace(/ \d{4}$/, '');
      return `${dShort}, ${t} IST`;
    }
    return istStr;
  }
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    }).format(new Date(iso)) + ' IST';
  } catch {
    return iso;
  }
}



const STAT_CARDS = [
  { key: 'total_videos',    label: 'Videos Processed', icon: '🎥', color: '#6366f1' },
  { key: 'total_clips',     label: 'Clips Generated',  icon: '✂️', color: '#8b5cf6' },
  { key: 'published_clips', label: 'Published Shorts', icon: '🚀', color: '#10b981' },
  { key: 'active_channels', label: 'Auto Channels',    icon: '📡', color: '#f59e0b' },
];

const PIPELINE_STEPS = [
  { key: 'pending',      label: 'Queued',             icon: '⏳' },
  { key: 'downloading',  label: 'Downloading video',  icon: '⬇️' },
  { key: 'validating',   label: 'Validating',         icon: '🔍' },
  { key: 'transcribing', label: 'Transcribing audio', icon: '🎤' },
  { key: 'analyzing',    label: 'AI scoring moments', icon: '🧠' },
  { key: 'selecting',    label: 'Selecting clips',    icon: '🎯' },
  { key: 'clipping_in_progress', label: 'Processing clips', icon: '✂️' },
  { key: 'completed',    label: 'Done!',              icon: '✅' },
  { key: 'completed_with_failures', label: 'Done (with errors)', icon: '⚠️' },
];

const STATUS_COLOR: Record<string, string> = {
  pending: '#f59e0b', downloading: '#6366f1', validating: '#3b82f6',
  transcribing: '#8b5cf6', analyzing: '#06b6d4', selecting: '#14b8a6',
  clipping_in_progress: '#ec4899', completed: '#10b981', 
  completed_with_failures: '#f59e0b', failed: '#ef4444', cancelled: '#94a3b8',
};

function shortTitle(job: Job): string {
  if (job.source_title) return job.source_title;
  if (job.source_url) {
    try { return new URL(job.source_url).hostname; } catch { return job.source_url.slice(0, 40); }
  }
  return 'Unknown video';
}

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

// ── Active Job Card ──────────────────────────────────────────────────────────
function ActiveJobCard({ job, onCancel }: { job: Job; onCancel: (id: string) => void }) {
  const stepIdx = PIPELINE_STEPS.findIndex(s => s.key === job.status);
  const color = STATUS_COLOR[job.status] || '#6366f1';
  const isTerminal = ['completed', 'completed_with_failures', 'failed', 'cancelled'].includes(job.status);

  return (
    <div style={{
      background: 'var(--bg-secondary)', border: `1px solid ${color}40`,
      borderRadius: 14, padding: '18px 20px', marginBottom: 14,
      boxShadow: `0 0 18px ${color}18`,
    }}>
      {/* Title row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 18 }}>
          {['completed', 'completed_with_failures'].includes(job.status) ? '✅' : job.status === 'failed' ? '❌' : job.status === 'cancelled' ? '⏹️' : '⚡'}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 13, fontWeight: 700,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {job.source_url ? (
              <a 
                href={job.source_url} 
                target="_blank" 
                rel="noopener noreferrer" 
                style={{ color: '#818cf8', textDecoration: 'none' }}
                onMouseEnter={e => { (e.currentTarget as HTMLAnchorElement).style.textDecoration = 'underline'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLAnchorElement).style.textDecoration = 'none'; }}
              >
                {shortTitle(job)} 🔗
              </a>
            ) : (
              <span style={{ color: 'var(--text-primary)' }}>{shortTitle(job)}</span>
            )}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, display: 'flex', gap: 6, alignItems: 'center' }}>
            <span>
              {job.status === 'cancelled'
                ? 'Cancelled by user'
                : job.status === 'completed'
                ? 'Completed successfully'
                : (job.current_step || job.status)}
            </span>
            {job.source_url && (
              <>
                <span>•</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    navigator.clipboard.writeText(job.source_url || '');
                    const btn = e.currentTarget as HTMLButtonElement;
                    btn.innerText = 'Copied!';
                    btn.style.color = '#10b981';
                    setTimeout(() => {
                      btn.innerText = 'Copy';
                      btn.style.color = 'inherit';
                    }, 1500);
                  }}
                  style={{
                    background: 'none', border: 'none', padding: 0,
                    color: 'var(--text-muted)', fontSize: 10, cursor: 'pointer',
                    textDecoration: 'underline',
                  }}
                >
                  Copy
                </button>
              </>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontSize: 11, fontWeight: 700, color, background: `${color}20`,
            borderRadius: 6, padding: '3px 8px', whiteSpace: 'nowrap',
          }}>
            {job.status === 'cancelled' ? 'Cancelled' :
             job.status === 'completed' ? 'Done' :
             job.status === 'failed' ? 'Failed' : `${job.progress}%`}
          </span>
          {/* Cancel button: only for non-terminal jobs */}
          {!isTerminal && (
            <button
              onClick={() => onCancel(job.id)}
              title="Cancel this job"
              style={{
                padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                cursor: 'pointer', border: '1px solid rgba(239,68,68,0.4)',
                background: 'rgba(239,68,68,0.1)', color: '#f87171',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.25)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.1)'; }}
            >✕ Cancel</button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ background: 'var(--border)', borderRadius: 99, height: 6, marginBottom: 14, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: job.status === 'completed' ? '100%' : `${job.progress}%`, borderRadius: 99,
          background: `linear-gradient(90deg, ${color}, ${color}cc)`,
          transition: 'width 0.5s ease',
          boxShadow: `0 0 8px ${color}80`,
        }} />
      </div>

      {/* Pipeline step pills */}
      {job.status === 'cancelled' ? (
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          fontSize: 11, padding: '4px 10px', borderRadius: 20,
          background: 'rgba(148,163,184,0.15)', border: '1px solid rgba(148,163,184,0.3)',
          color: '#94a3b8', fontWeight: 600
        }}>
          ⏹️ Processing stopped • Cancelled by user
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {PIPELINE_STEPS.map((step, i) => {
            const isCurrent = step.key === job.status;
            const isDone = stepIdx > i && !['failed', 'cancelled'].includes(job.status);
            return (
              <div key={step.key} style={{
                display: 'flex', alignItems: 'center', gap: 4,
                fontSize: 10, padding: '3px 8px', borderRadius: 20,
                background: isDone ? 'rgba(16,185,129,0.12)' : isCurrent ? `${color}20` : 'transparent',
                border: `1px solid ${isDone ? 'rgba(16,185,129,0.3)' : isCurrent ? `${color}50` : 'var(--border)'}`,
                color: isDone ? '#10b981' : isCurrent ? color : 'var(--text-muted)',
                fontWeight: isCurrent ? 700 : 400,
                transition: 'all 0.3s',
              }}>
                {isDone ? '✓' : step.icon} {step.label}
              </div>
            );
          })}
        </div>
      )}

      {job.status === 'failed' && job.error_message && (
        <div style={{
          marginTop: 12, padding: '8px 12px', borderRadius: 8,
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
          fontSize: 11, color: '#ef4444', fontFamily: 'monospace',
          maxHeight: 60, overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {job.error_message.split('\n')[0]}
        </div>
      )}
    </div>
  );
}

// ── Video Thumbnail Component ──────────────────────────────────────────────
function JobThumbnail({
  url,
  title,
  sourceUrl,
}: {
  url?: string | null;
  title: string;
  sourceUrl?: string | null;
}) {
  const [hasError, setHasError] = useState(false);
  const showPlaceholder = !url || hasError;

  return (
    <div
      style={{
        width: '100%',
        aspectRatio: '16 / 9',
        position: 'relative',
        background: '#090d16',
        overflow: 'hidden',
        borderTopLeftRadius: 12,
        borderTopRightRadius: 12,
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {!showPlaceholder ? (
        <img
          src={url}
          alt={title || 'Video thumbnail'}
          loading="lazy"
          onError={() => setHasError(true)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transition: 'transform 0.3s ease',
          }}
          className="thumbnail-img"
        />
      ) : (
        <div
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #111827 0%, #0b0f19 100%)',
            color: 'var(--text-muted)',
            padding: 12,
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: '50%',
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 20,
              marginBottom: 4,
            }}
          >
            🎬
          </div>
          <span style={{ fontSize: 11, fontWeight: 500, color: '#94a3b8' }}>
            No Thumbnail Preview
          </span>
          {sourceUrl && (
            <span style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
              {sourceUrl.includes('youtube.com') || sourceUrl.includes('youtu.be')
                ? 'YouTube Video'
                : 'Direct Media File'}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Recent Job Card (Responsive Grid) ───────────────────────────────────────
function RecentJobCard({
  job,
  onCancel,
  onRetry,
}: {
  job: Job;
  onCancel: (id: string) => void;
  onRetry: (id: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const color = STATUS_COLOR[job.status] || '#6366f1';
  const isTerminal = ['completed', 'completed_with_failures', 'failed', 'cancelled'].includes(job.status);

  const statusLabel =
    job.status === 'completed' ? 'DONE' :
    job.status === 'completed_with_failures' ? 'PARTIAL' :
    job.status === 'failed' ? 'FAILED' :
    job.status === 'cancelled' ? 'CANCELLED' :
    job.status === 'pending' ? 'QUEUED' :
    job.status.toUpperCase();

  const titleText = shortTitle(job);
  const isYouTube = job.source_url && (job.source_url.includes('youtube.com') || job.source_url.includes('youtu.be'));

  const handleCardClick = () => {
    if (job.source_url) {
      window.open(job.source_url, '_blank', 'noopener,noreferrer');
    }
  };

  const handleCopyLink = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (job.source_url) {
      navigator.clipboard.writeText(job.source_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    }
  };

  return (
    <div
      onClick={handleCardClick}
      className="recent-job-card"
      style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        cursor: job.source_url ? 'pointer' : 'default',
        boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
        position: 'relative',
      }}
    >
      {/* 16:9 Thumbnail with Overlay Badges */}
      <div style={{ position: 'relative', width: '100%' }}>
        <JobThumbnail url={job.thumbnail_url} title={titleText} sourceUrl={job.source_url} />

        {/* Top-Left Floating Status Pill */}
        <div
          style={{
            position: 'absolute',
            top: 8,
            left: 8,
            zIndex: 2,
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            color: color,
            background: 'rgba(15, 23, 42, 0.88)',
            border: `1px solid ${color}60`,
            borderRadius: 6,
            padding: '3px 7px',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <span>
            {job.status === 'completed' ? '●' :
             job.status === 'completed_with_failures' ? '▲' :
             job.status === 'failed' ? '✕' :
             job.status === 'cancelled' ? '■' : '▶'}
          </span>
          {statusLabel}
        </div>

        {/* Top-Right Source Badge / External Indicator */}
        {job.source_url && (
          <div
            style={{
              position: 'absolute',
              top: 8,
              right: 8,
              zIndex: 2,
              fontSize: 10,
              fontWeight: 600,
              background: 'rgba(15, 23, 42, 0.88)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: 6,
              padding: '3px 6px',
              color: '#e2e8f0',
              backdropFilter: 'blur(6px)',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
            title="Open original video"
          >
            {isYouTube ? (
              <span style={{ color: '#f87171' }}>▶ YouTube</span>
            ) : (
              <span>🔗 Link</span>
            )}
          </div>
        )}

        {/* Bottom-Right Progress / State Indicator */}
        <div
          style={{
            position: 'absolute',
            bottom: 8,
            right: 8,
            zIndex: 2,
            fontSize: 10,
            fontWeight: 700,
            background: 'rgba(15, 23, 42, 0.88)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 6,
            padding: '2px 6px',
            color: isTerminal ? '#cbd5e1' : '#818cf8',
            backdropFilter: 'blur(6px)',
          }}
        >
          {job.status === 'completed' ? '100%' :
           job.status === 'cancelled' ? 'Stopped' :
           job.status === 'failed' ? 'Failed' :
           `${job.progress}%`}
        </div>
      </div>

      {/* Card Content Body */}
      <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', flex: 1, gap: 8 }}>
        {/* Video Title (Clamped to 2 lines) */}
        <div>
          <h3
            title={job.source_title || titleText}
            style={{
              margin: 0,
              fontSize: 13,
              fontWeight: 600,
              lineHeight: 1.4,
              color: 'var(--text-primary)',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              minHeight: 36,
            }}
          >
            {titleText}
          </h3>
        </div>

        {/* Stage / Error Details */}
        <div style={{ fontSize: 11, minHeight: 18 }}>
          {job.status === 'failed' && job.error_message ? (
            <span
              style={{ color: '#ef4444', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
              title={job.error_message}
            >
              Error: {job.error_message.split('\n')[0]}
            </span>
          ) : job.status === 'cancelled' ? (
            <span style={{ color: '#94a3b8' }}>⏹️ Cancelled by user</span>
          ) : job.status === 'completed' ? (
            <span style={{ color: '#10b981' }}>✓ Completed successfully</span>
          ) : job.current_step && job.current_step.includes('in line') ? (
            <span style={{ color: '#f59e0b', fontWeight: 500 }}>
              ⏳ {job.current_step}
            </span>
          ) : (
            <span style={{ color: 'var(--text-muted)' }}>
              Stage: {job.current_step || job.status}
            </span>
          )}
        </div>

        {/* Active Progress Bar */}
        {!isTerminal && (
          <div style={{ width: '100%', background: 'var(--border)', borderRadius: 99, height: 4, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${job.progress}%`,
                borderRadius: 99,
                background: `linear-gradient(90deg, ${color}, ${color}cc)`,
                transition: 'width 0.4s ease',
              }}
            />
          </div>
        )}

        {/* Creation Timestamp in IST */}
        <div style={{ fontSize: 10, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: 4 }}>
          <span title={`Created at: ${job.created_at_ist || formatISTDate(job.created_at)}`}>
            📅 {formatCompactIST(job.created_at, job.created_at_ist)}
          </span>
          <span style={{ color: '#64748b' }}>
            {timeAgo(job.completed_at || job.updated_at || job.created_at)}
          </span>
        </div>

        {/* Action Controls Footer */}
        <div
          style={{
            borderTop: '1px solid var(--border)',
            paddingTop: 8,
            marginTop: 4,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 6,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Copy Link */}
          {job.source_url ? (
            <button
              onClick={handleCopyLink}
              title="Copy video link"
              style={{
                background: copied ? 'rgba(16,185,129,0.1)' : 'transparent',
                border: `1px solid ${copied ? 'rgba(16,185,129,0.4)' : 'var(--border)'}`,
                color: copied ? '#10b981' : 'var(--text-muted)',
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: 10,
                fontWeight: 600,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                transition: 'all 0.15s ease',
              }}
            >
              {copied ? '✓ Copied' : '🔗 Copy Link'}
            </button>
          ) : (
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Local</span>
          )}

          {/* Contextual Actions (Cancel / Retry) */}
          <div style={{ display: 'flex', gap: 6 }}>
            {!isTerminal ? (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onCancel(job.id);
                }}
                title="Cancel active job"
                style={{
                  padding: '4px 9px',
                  borderRadius: 6,
                  fontSize: 10,
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: '1px solid rgba(239,68,68,0.35)',
                  background: 'rgba(239,68,68,0.08)',
                  color: '#f87171',
                  transition: 'all 0.15s ease',
                }}
              >
                ✕ Cancel
              </button>
            ) : (job.status === 'failed' || job.status === 'cancelled') ? (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRetry(job.id);
                }}
                title="Retry this job"
                style={{
                  padding: '4px 9px',
                  borderRadius: 6,
                  fontSize: 10,
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: '1px solid rgba(99,102,241,0.35)',
                  background: 'rgba(99,102,241,0.1)',
                  color: '#818cf8',
                  transition: 'all 0.15s ease',
                }}
              >
                🔄 Retry
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [url, setUrl] = useState('');
  const [batchMode, setBatchMode] = useState(false);
  const [batchUrls, setBatchUrls] = useState('');
  const [queueStats, setQueueStats] = useState<QueueStats | null>(null);
  const [numClips, setNumClips] = useState<number | ''>('');
  const [customClips, setCustomClips] = useState('');
  const [clipsCount, setClipsCount] = useState(3);
  const [clipMode, setClipMode] = useState<'ai_highlights' | 'equal_split'>('ai_highlights');
  const [maxClipDuration, setMaxClipDuration] = useState<number>(49);
  const [showModal, setShowModal] = useState(false);
  const [showPodcastModal, setShowPodcastModal] = useState(false);
  const [isSubmittingPodcastModal, setIsSubmittingPodcastModal] = useState(false);
  const [podcastModalError, setPodcastModalError] = useState('');
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingUrl, setPendingUrl] = useState('');
  const [reframeMode, setReframeMode] = useState('blur');
  const [enableBroll, setEnableBroll] = useState(false);
  const [enableHook, setEnableHook] = useState(false);
  const [targetLanguage, setTargetLanguage] = useState('none');
  const [hookTitle, setHookTitle] = useState(true);
  const [activeJobs, setActiveJobs] = useState<Job[]>([]);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  // Map of jobId → WebSocket for active jobs
  const wsMapRef = useRef<Map<string, WebSocket>>(new Map());

  const refreshAll = useCallback(async () => {
    const [s, active, history, q] = await Promise.all([
      getStats().catch(() => null),
      getActiveJobs().catch(() => []),
      getJobHistory(24).catch(() => []),
      getJobStats().catch(() => null),
    ]);
    if (s) setStats(s);
    if (q) setQueueStats(q);
    setActiveJobs((active || []) as Job[]);
    const sortedHistory = [...((history || []) as Job[])].sort((a, b) => {
      const timeA = new Date(a.created_at || 0).getTime();
      const timeB = new Date(b.created_at || 0).getTime();
      if (timeB !== timeA) return timeB - timeA;
      return (b.id || '').localeCompare(a.id || '');
    });
    setRecentJobs(sortedHistory);
  }, []);

  const handleBatchSubmit = async () => {
    const rawList = batchUrls.split('\n').map(u => u.trim()).filter(Boolean);
    if (rawList.length === 0) return;
    setLoading(true); setError('');
    try {
      const res = await submitBatchYouTubeUrls(rawList, clipsCount);
      setBatchUrls('');
      refreshAll();
    } catch (e: any) {
      setError(e.message || 'Batch submission failed');
    }
    setLoading(false);
  };

  const handleManualRetry = async (jobId: string) => {
    try {
      await retryJob(jobId);
      refreshAll();
    } catch (e: any) {
      alert(`Retry failed: ${e.message}`);
    }
  };


  // Open a WebSocket for a given job, merging updates into activeJobs list
  const openJobWs = useCallback((jobId: string) => {
    if (wsMapRef.current.has(jobId)) return; // already connected
    const ws = new WebSocket(`${WS_BASE}/api/jobs/ws/${jobId}`);
    wsMapRef.current.set(jobId, ws);

    ws.onopen = () => setWsConnected(true);

    ws.onmessage = (evt) => {
      try {
        const updated: Job = JSON.parse(evt.data);
        // If job is terminal, close socket and refresh all to move it to recent history
        if (['completed', 'completed_with_failures', 'failed', 'cancelled'].includes(updated.status)) {
          ws.close();
          wsMapRef.current.delete(jobId);
          if (wsMapRef.current.size === 0) setWsConnected(false);
          refreshAll();
        } else {
          setActiveJobs(prev => {
            const exists = prev.some(j => j.id === updated.id);
            if (exists) {
              return prev.map(j => j.id === updated.id ? updated : j);
            }
            return [updated, ...prev];
          });
        }
      } catch { /* ignore parse errors */ }
    };

    ws.onerror = () => {
      ws.close();
      wsMapRef.current.delete(jobId);
      if (wsMapRef.current.size === 0) setWsConnected(false);
    };

    ws.onclose = () => {
      wsMapRef.current.delete(jobId);
      if (wsMapRef.current.size === 0) setWsConnected(false);
    };
  }, [refreshAll]);

  // Dynamic polling: fast (2s) if we have active jobs and NO websocket connection. Slow (10s) otherwise.
  useEffect(() => {
    setTimeout(refreshAll, 0);
    const hasActiveJobs = activeJobs.length > 0;
    const interval = (!wsConnected && hasActiveJobs) ? 2000 : 10000;
    
    pollRef.current = setInterval(refreshAll, interval);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [refreshAll, wsConnected, activeJobs.length]);

  // Clean up WebSockets on unmount
  useEffect(() => {
    const wsMap = wsMapRef.current;
    return () => {
      wsMap.forEach(ws => ws.close());
      wsMap.clear();
    };
  }, []);

  // Watch activeJobs list — open WebSocket for every non-terminal active job
  useEffect(() => {
    const terminal = ['completed', 'completed_with_failures', 'failed', 'cancelled'];
    activeJobs.forEach(job => {
      if (!terminal.includes(job.status)) {
        openJobWs(job.id);
      }
    });
  }, [activeJobs, openJobWs]);

  const queueCount = queueStats?.queue
    ? (queueStats.queue.active + queueStats.queue.pending)
    : activeJobs.length;

  const handleCancelJob = async (id: string) => {
    if (!confirm('Cancel this job? The video will stop processing.')) return;
    try {
      await cancelJob(id);
      setTimeout(refreshAll, 400);
    } catch (e: any) {
      alert(`Failed to cancel: ${e.message}`);
    }
  };

  const handleDeleteJob = async (id: string) => {
    if (!confirm('Delete this job record from the list?')) return;
    try {
      await cancelJob(id);
      setTimeout(refreshAll, 400);
    } catch (e: any) {
      alert(`Failed to delete: ${e.message}`);
    }
  };

  const [isPendingBatch, setIsPendingBatch] = useState(false);
  const [isSubmittingModal, setIsSubmittingModal] = useState(false);
  const [modalError, setModalError] = useState('');

  const extractYouTubeVideoId = (inputUrl: string): string | null => {
    if (!inputUrl || typeof inputUrl !== 'string') return null;
    const match = inputUrl.match(
      /(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/|live\/))([a-zA-Z0-9_-]{11})/
    );
    return match ? match[1] : null;
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showModal && !isSubmittingModal) {
        setShowModal(false);
        setPendingUrl('');
        setPendingFile(null);
        setIsPendingBatch(false);
        setModalError('');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showModal, isSubmittingModal]);

  // Open modal for URL submission
  const handleSubmitUrl = () => {
    if (!url.trim() || !extractYouTubeVideoId(url.trim())) return;
    setPendingUrl(url);
    setPendingFile(null);
    setIsPendingBatch(false);
    setModalError('');
    setShowModal(true);
  };

  // Open modal for Batch URLs submission
  const handleBatchOpenModal = () => {
    const rawList = batchUrls.split('\n').map(u => u.trim()).filter(Boolean);
    if (rawList.length === 0) return;
    setIsPendingBatch(true);
    setPendingUrl('');
    setPendingFile(null);
    setModalError('');
    setShowModal(true);
  };

  // Open modal for file upload
  const handleFileUpload = (file: File) => {
    if (!file) return;
    setPendingFile(file);
    setPendingUrl('');
    setIsPendingBatch(false);
    setModalError('');
    setShowModal(true);
  };

  // Actually dispatch after modal confirm
  const confirmAndProcess = async (config: ProcessVideoConfig) => {
    if (isSubmittingModal) return;

    // Sync dashboard state with chosen modal config
    if (config.clipsCount !== undefined) {
      setClipsCount(config.clipsCount);
    }
    setClipMode(config.clipMode);
    setMaxClipDuration(config.maxClipDuration);
    setReframeMode(config.reframeMode);
    setHookTitle(config.hookTitle);
    setEnableBroll(config.enableBroll);
    setEnableHook(config.enableHook);
    setTargetLanguage(config.targetLanguage);

    const computedClipsCount = config.clipMode === 'equal_split' ? undefined : config.clipsCount;
    const targetDuration = config.clipMode === 'equal_split' ? (config.targetDuration || config.maxClipDuration) : undefined;
    const segmentationStrategy = config.clipMode === 'equal_split' ? 'equal_splits' : undefined;
    setIsSubmittingModal(true);
    setLoading(true);
    setModalError('');
    setError('');

    try {
      if (isPendingBatch) {
        const rawList = batchUrls.split('\n').map(u => u.trim()).filter(Boolean);
        await submitBatchYouTubeUrls(
          rawList,
          computedClipsCount,
          config.maxClipDuration,
          config.clipMode,
          config.reframeMode,
          config.enableBroll,
          config.enableHook,
          config.targetLanguage,
          targetDuration,
          segmentationStrategy
        );
        setBatchUrls('');
        setIsPendingBatch(false);
        setShowModal(false);
        setPendingUrl('');
        setPendingFile(null);
        setTimeout(refreshAll, 800);
      } else if (pendingUrl) {
        const res = await submitYouTubeUrl(pendingUrl, {
          numClips: computedClipsCount,
          clipsCount: computedClipsCount,
          maxClipDuration: config.maxClipDuration,
          reframeMode: config.reframeMode,
          hookTitle: config.hookTitle,
          enableBroll: config.enableBroll,
          enableHook: config.enableHook,
          targetLanguage: config.targetLanguage,
          clipMode: config.clipMode,
          targetDuration: targetDuration,
          segmentationStrategy: segmentationStrategy,
        });
        if (res.job_id) {
          setUrl('');
          setShowModal(false);
          setPendingUrl('');
          setPendingFile(null);
          setTimeout(refreshAll, 800);
        } else {
          setModalError(res.detail || 'Failed to start processing');
          setError(res.detail || 'Failed to start processing');
        }
      } else if (pendingFile) {
        const res = await uploadVideoFile(
          pendingFile,
          computedClipsCount,
          config.reframeMode,
          config.hookTitle,
          config.enableBroll,
          config.enableHook,
          config.targetLanguage,
          config.maxClipDuration,
          config.clipMode,
          targetDuration,
          segmentationStrategy
        );
        if (res.job_id) {
          setShowModal(false);
          setPendingUrl('');
          setPendingFile(null);
          setTimeout(refreshAll, 800);
        } else {
          setModalError(res.detail || 'Failed to start processing');
          setError(res.detail || 'Failed to start processing');
        }
      }
    } catch (e: any) {
      const msg = e.message || 'Failed to connect to backend server';
      setModalError(msg);
      setError(msg);
    } finally {
      setIsSubmittingModal(false);
      setLoading(false);
    }
  };

  const confirmAndProcessPodcast = async (config: PodcastProcessingConfig) => {
    setIsSubmittingPodcastModal(true);
    setPodcastModalError('');
    setError('');

    try {
      const res = await submitYouTubeUrl(config.url, {
        numClips: config.clipsCount,
        clipsCount: config.clipsCount,
        maxClipDuration: config.targetDuration,
        targetDuration: config.targetDuration,
        clipMode: config.clipMode,
        reframeMode: config.composition === 'stacked' ? 'stacked_16_9' : 'center_crop',
        regions: config.regions,
        podcastComposition: config.composition,
        shotSchedule: config.shotSchedule,
      });

      if (res.job_id) {
        setShowPodcastModal(false);
        setUrl('');
        setPodcastModalError('');
        setTimeout(refreshAll, 800);
      } else {
        const msg = res.detail || 'Failed to start podcast processing';
        setPodcastModalError(msg);
        setError(msg);
      }
    } catch (e: any) {
      const msg = e.message || 'Failed to submit podcast video';
      setPodcastModalError(msg);
      setError(msg);
    } finally {
      setIsSubmittingPodcastModal(false);
    }
  };

  const handleFileDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }, []);

  return (
    <>
    <div className="animate-fade-up">
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, fontFamily: "'Space Grotesk', sans-serif", marginBottom: 6 }}>
          Welcome to <span className="gradient-text">ClipForge</span>
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 15 }}>
          AI-powered YouTube automation — paste a URL and watch the magic happen.
        </p>
      </div>

      {/* Stat Cards */}
      <div className="dashboard-stats-grid">
        {STAT_CARDS.map(card => (
          <div key={card.key} className="glass stat-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 12, fontWeight: 500, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {card.label}
                </div>
                <div style={{ fontSize: 32, fontWeight: 800, color: card.color, fontFamily: "'Space Grotesk', sans-serif" }}>
                  {stats ? (stats as any)[card.key] : <span className="skeleton" style={{ display: 'inline-block', width: 40, height: 32 }} />}
                </div>
              </div>
              <div style={{ fontSize: 28, opacity: 0.8 }}>{card.icon}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="dashboard-main-grid">
        {/* Input Section */}
        <div className="glass" style={{ padding: 28 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700 }}>🎬 Process Videos</h2>
            <div style={{ display: 'flex', gap: 6, background: 'var(--bg-secondary)', padding: 4, borderRadius: 8, border: '1px solid var(--border)', flexWrap: 'wrap' }}>
              <button
                onClick={() => setBatchMode(false)}
                style={{
                  padding: '4px 10px', borderRadius: 6, fontSize: 12, border: 'none', cursor: 'pointer',
                  background: !batchMode ? '#6366f1' : 'transparent', color: !batchMode ? '#fff' : 'var(--text-muted)',
                  fontWeight: !batchMode ? 600 : 400
                }}
              >
                Single URL
              </button>
              <button
                onClick={() => setBatchMode(true)}
                style={{
                  padding: '4px 10px', borderRadius: 6, fontSize: 12, border: 'none', cursor: 'pointer',
                  background: batchMode ? '#6366f1' : 'transparent', color: batchMode ? '#fff' : 'var(--text-muted)',
                  fontWeight: batchMode ? 600 : 400
                }}
              >
                Bulk / Batch
              </button>
              <button
                id="podcast-interview-mode-btn"
                onClick={() => setShowPodcastModal(true)}
                style={{
                  padding: '4px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                  background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.25), rgba(139, 92, 246, 0.25))',
                  color: '#93c5fd',
                  fontWeight: 600,
                  display: 'flex', alignItems: 'center', gap: 5,
                  border: '1px solid rgba(59, 130, 246, 0.4)',
                }}
              >
                <span>🎙️</span>
                <span>Podcast / Interview</span>
              </button>
            </div>
          </div>

          {!batchMode ? (
            <div style={{ marginBottom: 16 }}>
              <label htmlFor="dashboard-youtube-url" style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 8 }}>
                YouTube URL
              </label>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <input
                  id="dashboard-youtube-url"
                  className="input-field"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSubmitUrl()}
                  aria-invalid={url.trim().length > 0 && !extractYouTubeVideoId(url.trim())}
                  aria-describedby={url.trim().length > 0 && !extractYouTubeVideoId(url.trim()) ? "dashboard-youtube-url-error" : undefined}
                />
                <button
                  className="btn-primary"
                  onClick={handleSubmitUrl}
                  disabled={loading || !url.trim() || !extractYouTubeVideoId(url.trim())}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {loading ? '⏳' : '⚡ Generate'}
                </button>
              </div>
              <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <button
                  type="button"
                  id="podcast-quick-launch-link"
                  onClick={() => setShowPodcastModal(true)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#60a5fa',
                    fontSize: 12,
                    cursor: 'pointer',
                    padding: 0,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    textDecoration: 'underline',
                  }}
                >
                  <span>🎙️ Podcast or Interview? Draw & select speaker areas</span>
                </button>
              </div>
              {url.trim().length > 0 && !extractYouTubeVideoId(url.trim()) && (
                <p id="dashboard-youtube-url-error" role="alert" style={{ fontSize: 12, color: '#f87171', marginTop: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span>⚠️</span>
                  <span>Please enter a valid YouTube video or Shorts URL (e.g. https://www.youtube.com/watch?v=... or https://youtu.be/...)</span>
                </p>
              )}
            </div>
          ) : (
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 8 }}>
                Paste YouTube URLs (one per line)
              </label>
              <textarea
                className="input-field"
                rows={5}
                placeholder="https://www.youtube.com/watch?v=111&#10;https://www.youtube.com/watch?v=222&#10;https://www.youtube.com/watch?v=333"
                value={batchUrls}
                onChange={e => setBatchUrls(e.target.value)}
                style={{ fontFamily: 'monospace', fontSize: 12, resize: 'vertical' }}
              />
              <button
                className="btn-primary"
                onClick={handleBatchOpenModal}
                disabled={loading || !batchUrls.trim()}
                style={{ marginTop: 10, width: '100%' }}
              >
                {loading ? '⏳ Processing Batch...' : `⚙️ Configure & Submit Batch (${batchUrls.split('\n').filter(u => u.trim()).length} URLs)`}
              </button>
            </div>
          )}

          {/* ── Clips per Video count (Only shown for AI Highlights mode) ── */}
          {clipMode === 'ai_highlights' ? (
            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 8 }}>Clips per Video</label>
              <input
                type="number"
                min="1"
                max="10"
                className="input-field"
                value={clipsCount}
                onChange={e => setClipsCount(parseInt(e.target.value) || 3)}
                style={{ width: '100px' }}
              />
            </div>
          ) : (
            <div style={{
              marginBottom: 20, padding: '12px 14px', borderRadius: 10,
              background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
              color: '#a5b4fc', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8
            }}>
              <span>⚡</span>
              <span><strong>Equal Split Mode Active:</strong> Clip count is automatically computed to cover 100% of the video in max 49s Shorts clips.</span>
            </div>
          )}


          {/* ── Clip Generation Mode toggle ── */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 10 }}>
              Clip Generation Mode
            </label>
            <div style={{
              display: 'inline-flex', borderRadius: 10, overflow: 'hidden',
              border: '1px solid var(--border)', background: 'var(--bg-secondary)',
            }}>
              {(
                [['ai_highlights', '🧠 AI Highlights'], ['equal_split', '✂️ Equal Split']] as const
              ).map(([mode, label]) => (
                <button
                  key={mode}
                  onClick={() => setClipMode(mode)}
                  style={{
                    padding: '8px 18px', fontSize: 13, fontWeight: 600,
                    cursor: 'pointer', border: 'none', transition: 'all 0.15s',
                    background: clipMode === mode
                      ? 'linear-gradient(135deg,#6366f1,#8b5cf6)'
                      : 'transparent',
                    color: clipMode === mode ? '#fff' : 'var(--text-secondary)',
                    borderRight: mode === 'ai_highlights' ? '1px solid var(--border)' : 'none',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
              {clipMode === 'ai_highlights'
                ? 'AI detects and scores the most engaging viral moments.'
                : 'Divides the entire video into equal-duration clips (≤ 49s max limit) with 100% timeline coverage.'}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>OR</span>
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
          </div>

          {/* ── Layout Mode selector (Visual Thumbnail Selector) ── */}
          <div style={{ marginBottom: 24 }}>
            <LayoutThumbnailSelector
              value={reframeMode || 'blur'}
              onChange={val => setReframeMode(val)}
            />
          </div>

          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleFileDrop}
            onClick={() => document.getElementById('file-input')?.click()}
            style={{
              border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 12, padding: 32, textAlign: 'center',
              cursor: 'pointer', transition: 'all 0.2s',
              background: dragOver ? 'rgba(99,102,241,0.05)' : 'transparent',
            }}
          >
            <div style={{ fontSize: 36, marginBottom: 8 }}>📁</div>
            <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 4 }}>Drop MP4/MOV here or click to browse</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Max file size: 2GB</div>
            <input id="file-input" type="file" accept=".mp4,.mov,.avi,.mkv" style={{ display: 'none' }}
              onChange={e => { if (e.target.files?.[0]) handleFileUpload(e.target.files[0]); }} />
          </div>

          {error && (
            <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444', fontSize: 13 }}>
              ⚠️ {error}
            </div>
          )}
        </div>

        {/* Pipeline Status Panel */}
        <div className="glass" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 0 }}>
          {/* Header with queue badge */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700 }}>⚡ Pipeline Status</h2>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {wsConnected && (
                <span style={{
                  background: 'rgba(16,185,129,0.15)', color: '#10b981',
                  border: '1px solid rgba(16,185,129,0.35)',
                  borderRadius: 99, padding: '2px 9px', fontSize: 11, fontWeight: 600,
                }}>
                  ⚡ Live WS
                </span>
              )}
              {queueCount > 0 && (
                <span style={{
                  background: 'rgba(99,102,241,0.2)', color: '#818cf8',
                  border: '1px solid rgba(99,102,241,0.4)',
                  borderRadius: 99, padding: '3px 10px', fontSize: 12, fontWeight: 700,
                }}>
                  {queueCount} in queue
                </span>
              )}
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: queueCount > 0 ? '#10b981' : 'var(--text-muted)',
                boxShadow: queueCount > 0 ? '0 0 8px #10b981' : 'none',
                animation: queueCount > 0 ? 'pulse 2s infinite' : 'none',
              }} />
            </div>
          </div>

          {/* ── Queue Breakdown Pills ── */}
          {queueStats && queueStats.queue && (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(52px, 1fr))', gap: 6, marginBottom: 14, minWidth: 0,
              padding: 8, background: 'var(--bg-secondary)', borderRadius: 10, border: '1px solid var(--border)'
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>ACTIVE</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#6366f1' }}>{queueStats.queue.active}</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>PENDING</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#f59e0b' }}>{queueStats.queue.pending}</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>DONE</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#10b981' }}>{queueStats.queue.done}</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>FAILED</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#ef4444' }}>{queueStats.queue.failed}</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>CANCELLED</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#94a3b8' }}>{queueStats.queue.cancelled ?? 0}</div>
              </div>
            </div>
          )}

          {/* ── Last Failure Quick Retry Banner ── */}
          {queueStats?.last_failure && (
            <div style={{
              marginBottom: 14, padding: '10px 12px', borderRadius: 10,
              background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.25)',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center'
            }}>
              <div style={{ minWidth: 0, flex: 1, paddingRight: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#ef4444' }}>
                  ⚠️ Last Fail: {queueStats.last_failure.source_title?.slice(0, 30)}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {queueStats.last_failure.error}
                </div>
              </div>
              <button
                onClick={() => handleManualRetry(queueStats.last_failure!.job_id)}
                style={{
                  background: '#ef4444', color: '#fff', border: 'none', borderRadius: 6,
                  padding: '4px 10px', fontSize: 11, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap'
                }}
              >
                🔄 Retry
              </button>
            </div>
          )}


          {/* Active jobs */}
          <div style={{ flex: 1, overflowY: 'auto', maxHeight: 420 }}>
            {activeJobs.length > 0 ? (
              activeJobs.map(job => <ActiveJobCard key={job.id} job={job} onCancel={handleCancelJob} />)
            ) : (
              <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: 44, marginBottom: 12 }}>🎯</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>No active jobs</div>
                <div style={{ fontSize: 12 }}>Paste a YouTube URL or drop a file to start</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Jobs Section */}
      <div className="glass" style={{ padding: 24, marginTop: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>📋 Recent Jobs</h2>
            <span style={{
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--text-muted)',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              padding: '2px 8px',
              borderRadius: 12,
            }}>
              {recentJobs.length} {recentJobs.length === 1 ? 'job' : 'jobs'}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            <span>⚡ Sorted newest first</span>
            <button
              onClick={() => refreshAll()}
              style={{
                background: 'transparent',
                border: '1px solid var(--border)',
                color: 'var(--text-secondary)',
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: 11,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
              title="Refresh job history"
            >
              🔄 Refresh
            </button>
          </div>
        </div>

        {recentJobs.length > 0 ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 280px), 1fr))',
              gap: 16,
            }}
          >
            {recentJobs.map(job => (
              <RecentJobCard
                key={job.id}
                job={job}
                onCancel={handleCancelJob}
                onRetry={handleManualRetry}
              />
            ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '36px 16px', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 32, marginBottom: 10 }}>📭</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>
              No processing jobs recorded yet
            </div>
            <div style={{ fontSize: 13 }}>
              Enter a YouTube link or drop a video file above to generate your first Shorts.
            </div>
          </div>
        )}
      </div>
    </div>

      {/* ── Modernized YouTube Processing Configuration Modal ── */}
      <ProcessVideoModal
        isOpen={showModal}
        onClose={() => {
          if (!isSubmittingModal) {
            setShowModal(false);
            setPendingUrl('');
            setPendingFile(null);
            setIsPendingBatch(false);
            setModalError('');
          }
        }}
        onConfirm={confirmAndProcess}
        pendingUrl={pendingUrl}
        pendingFile={pendingFile}
        isPendingBatch={isPendingBatch}
        batchUrlsCount={batchUrls.split('\n').filter(u => u.trim()).length}
        initialClipsCount={clipsCount}
        initialClipMode={clipMode}
        initialDuration={maxClipDuration}
        initialLayout={reframeMode}
        initialHookTitle={hookTitle}
        initialEnableBroll={enableBroll}
        initialEnableHook={enableHook}
        initialTargetLanguage={targetLanguage}
        isSubmitting={isSubmittingModal}
        errorMessage={modalError}
      />

      {/* ── Dedicated Podcast & Interview Area Selection Modal ── */}
      <PodcastSelectionModal
        isOpen={showPodcastModal}
        onClose={() => {
          if (!isSubmittingPodcastModal) {
            setShowPodcastModal(false);
            setPodcastModalError('');
          }
        }}
        onConfirm={confirmAndProcessPodcast}
        initialUrl={url.trim()}
        isSubmitting={isSubmittingPodcastModal}
        errorMessage={podcastModalError}
      />
    </>
  );
}

