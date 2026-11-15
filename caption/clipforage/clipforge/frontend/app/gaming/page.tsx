'use client';

import React, { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import GamingSelectionModal, { GamingProcessingConfig } from '@/components/gaming/GamingSelectionModal';
import { submitYouTubeUrl, uploadVideoFile, extractYouTubeVideoId } from '@/lib/api';

export default function GamingStudioPage() {
  const router = useRouter();
  const [ingestMode, setIngestMode] = useState<'url' | 'upload'>('url');
  const [url, setUrl] = useState('');
  const [activeUrl, setActiveUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleLaunchUrl = () => {
    setError('');
    const target = url.trim() || activeUrl;
    if (!target) { setError('Please enter a YouTube video link'); return; }
    const ytId = extractYouTubeVideoId(target);
    if (!ytId) { setError('Invalid YouTube link. Please enter a valid YouTube video link'); return; }
    setSelectedFile(null);
    setActiveUrl(target);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError('');
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.match(/\.(mp4|mov|avi|mkv|webm)$/i)) {
        setError('Unsupported format. Please select an MP4, MOV, AVI, MKV, or WebM video file');
        return;
      }
      setSelectedFile(file);
      setUrl('');
      setActiveUrl('');
    }
  };

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    setError('');
    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (!file.name.match(/\.(mp4|mov|avi|mkv|webm)$/i)) {
        setError('Unsupported format. Please select an MP4, MOV, AVI, MKV, or WebM video file');
        return;
      }
      setSelectedFile(file);
      setUrl('');
      setActiveUrl('');
    }
  };

  const handleConfirm = async (config: GamingProcessingConfig) => {
    setIsSubmitting(true);
    setError('');
    try {
      let res: any;
      if (config.sourceType === 'file' && config.file) {
        res = await uploadVideoFile(config.file, {
          clipsCount: config.clipsCount || 3,
          targetDuration: config.targetDuration || 49,
          clipMode: config.clipMode || 'ai_highlights',
          reframeMode: 'gaming',
          gamingLayout: config.gamingLayout,
          destinationIds: config.destinationIds,
        });
      } else if (config.url) {
        res = await submitYouTubeUrl(config.url, {
          clipsCount: config.clipsCount || 3,
          targetDuration: config.targetDuration || 49,
          clipMode: config.clipMode || 'ai_highlights',
          reframeMode: 'gaming',
          gamingLayout: config.gamingLayout,
          destinationIds: config.destinationIds,
        });
      } else {
        throw new Error('No valid source provided');
      }

      if (res && res.job_id) {
        router.push('/');
      } else {
        setError(res?.detail || 'Failed to start gaming video processing');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to submit gaming video');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen py-8 px-4 sm:px-8 max-w-7xl mx-auto flex flex-col gap-6">

      {/* ══════════════════════════════════════════════════════
          HEADER + SOURCE INGESTION
      ══════════════════════════════════════════════════════ */}
      <div className="animate-fade-up">
        <div
          className="rounded-2xl p-6 sm:p-8 flex flex-col gap-6"
          style={{
            background: 'linear-gradient(135deg, #0f1017 0%, #0d0e14 100%)',
            border: '1px solid rgba(255,255,255,0.06)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
          }}
        >
          {/* ── Studio identity ── */}
          <div className="flex items-start justify-between gap-6 flex-wrap">
            <div className="flex items-center gap-4">
              {/* Icon */}
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl shrink-0"
                style={{
                  background: 'linear-gradient(135deg, rgba(79,70,229,0.2) 0%, rgba(16,185,129,0.1) 100%)',
                  border: '1px solid rgba(79,70,229,0.2)',
                  boxShadow: '0 8px 24px rgba(79,70,229,0.2)',
                }}
              >
                🎮
              </div>
              {/* Title */}
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
                    Dual-Region Gaming Studio
                  </h1>
                  <span
                    className="text-xs font-bold px-3 py-1 rounded-full"
                    style={{
                      background: 'rgba(16,185,129,0.1)',
                      color: '#10b981',
                      border: '1px solid rgba(16,185,129,0.2)',
                    }}
                  >
                    9:16 Shorts
                  </span>
                </div>
                <p className="text-sm mt-1" style={{ color: '#475569' }}>
                  Frame high-energy gameplay and facecam overlays into vertical shorts.
                </p>
              </div>
            </div>

            {/* Status badge */}
            <div
              className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold shrink-0 self-start"
              style={{
                background: 'rgba(16,185,129,0.06)',
                border: '1px solid rgba(16,185,129,0.15)',
                color: '#10b981',
              }}
            >
              <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: '#10b981' }} />
              Clean Gameplay Focus · Verified Codec Parity
            </div>
          </div>

          {/* ── Ingestion bar ── */}
          <div
            className="flex flex-col gap-5 pt-6"
            style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
          >
            {/* Source type selector */}
            <div className="flex items-center gap-4 flex-wrap">
              <div
                className="flex items-center rounded-2xl p-1.5 gap-1"
                style={{ background: '#0a0b10', border: '1px solid rgba(255,255,255,0.06)' }}
              >
                <button
                  id="gaming-tab-url-btn"
                  type="button"
                  onClick={() => { setIngestMode('url'); setError(''); }}
                  className="flex items-center gap-2.5 h-11 px-6 rounded-xl text-sm font-bold transition-all"
                  style={ingestMode === 'url'
                    ? { background: '#4f46e5', color: '#fff', boxShadow: '0 2px 12px rgba(79,70,229,0.5)' }
                    : { color: '#475569' }
                  }
                >
                  🔗 YouTube URL
                </button>
                <button
                  id="gaming-tab-upload-btn"
                  type="button"
                  onClick={() => { setIngestMode('upload'); setError(''); }}
                  className="flex items-center gap-2.5 h-11 px-6 rounded-xl text-sm font-bold transition-all"
                  style={ingestMode === 'upload'
                    ? { background: '#4f46e5', color: '#fff', boxShadow: '0 2px 12px rgba(79,70,229,0.5)' }
                    : { color: '#475569' }
                  }
                >
                  📁 Upload Local Video
                </button>
              </div>
              <span className="hidden sm:flex items-center gap-2 text-xs font-medium" style={{ color: '#1e293b' }}>
                <span className="w-2 h-2 rounded-full" style={{ background: '#10b981' }} />
                Dual-Region 9:16 Shorts Engine
              </span>
            </div>

            {/* Input area */}
            {ingestMode === 'url' ? (
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                <div className="relative flex-1">
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                    <span style={{ color: '#ef4444', fontSize: '16px' }}>▶</span>
                  </div>
                  <input
                    id="gaming-youtube-url-input"
                    className="w-full h-14 text-sm font-medium rounded-2xl focus:outline-none transition-all"
                    style={{
                      background: '#0a0b10',
                      border: '1px solid rgba(255,255,255,0.08)',
                      color: '#e2e8f0',
                      paddingLeft: '52px',
                      paddingRight: '16px',
                    }}
                    placeholder="Paste YouTube video link (e.g., https://www.youtube.com/watch?v=...)"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleLaunchUrl(); }}
                    onFocus={(e) => { e.currentTarget.style.borderColor = 'rgba(79,70,229,0.5)'; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; }}
                  />
                </div>
                <button
                  id="open-gaming-studio-url-btn"
                  type="button"
                  onClick={handleLaunchUrl}
                  className="flex items-center justify-center gap-2.5 h-14 px-8 rounded-2xl text-sm font-extrabold transition-all active:scale-[0.98] whitespace-nowrap w-full sm:w-auto"
                  style={{
                    background: 'linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)',
                    color: '#fff',
                    boxShadow: '0 4px 20px rgba(79,70,229,0.5)',
                  }}
                >
                  <span>⚡</span>
                  <span>Load Video</span>
                </button>
              </div>
            ) : (
              <div
                id="gaming-file-dropzone"
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current?.click()}
                className="w-full cursor-pointer rounded-2xl transition-all"
                style={{
                  minHeight: '100px',
                  padding: '20px 24px',
                  border: dragOver ? '2px solid #4f46e5' : '2px dashed rgba(255,255,255,0.1)',
                  background: dragOver ? 'rgba(79,70,229,0.08)' : 'rgba(255,255,255,0.02)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '16px',
                }}
              >
                <div className="flex items-center gap-4">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center text-xl shrink-0"
                    style={{ background: 'rgba(79,70,229,0.1)', border: '1px solid rgba(79,70,229,0.2)', color: '#818cf8' }}
                  >
                    📁
                  </div>
                  <div>
                    <div className="text-sm font-bold" style={{ color: '#e2e8f0' }}>
                      {selectedFile ? `Selected: ${selectedFile.name}` : 'Click or drop video file here'}
                    </div>
                    <p className="text-xs mt-1" style={{ color: '#374151' }}>
                      Supports MP4, MOV, MKV, AVI, WebM (Max 2GB)
                    </p>
                  </div>
                </div>
                <span
                  className="shrink-0 px-5 py-2.5 rounded-xl text-sm font-bold transition-all"
                  style={{
                    background: '#161820',
                    border: '1px solid rgba(255,255,255,0.08)',
                    color: '#94a3b8',
                  }}
                >
                  Browse
                </span>
                <input
                  ref={fileInputRef}
                  id="gaming-file-input"
                  type="file"
                  accept=".mp4,.mov,.avi,.mkv,.webm"
                  style={{ display: 'none' }}
                  onChange={handleFileChange}
                />
              </div>
            )}

            {/* Error */}
            {error && (
              <div
                id="gaming-error-banner"
                className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold"
                style={{
                  background: 'rgba(239,68,68,0.08)',
                  border: '1px solid rgba(239,68,68,0.2)',
                  color: '#f87171',
                }}
              >
                <span>⚠️</span>
                <span>{error}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════
          STUDIO WORKSPACE — inline gaming selection modal
      ══════════════════════════════════════════════════════ */}
      <GamingSelectionModal
        isOpen={true}
        isInline={true}
        initialUrl={activeUrl}
        initialFile={selectedFile}
        onConfirm={handleConfirm}
        isSubmitting={isSubmitting}
        errorMessage={error}
      />
    </div>
  );
}
