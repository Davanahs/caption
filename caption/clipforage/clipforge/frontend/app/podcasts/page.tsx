'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import PodcastSelectionModal, { PodcastProcessingConfig } from '@/components/PodcastSelectionModal';
import { submitYouTubeUrl } from '@/lib/api';

export default function PodcastsPage() {
  const router = useRouter();
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'manual' | 'advanced'>('manual');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleConfirm = async (config: PodcastProcessingConfig) => {
    setIsSubmitting(true);
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
        setModalOpen(false);
        router.push('/');
      } else {
        setError(res.detail || 'Failed to start podcast processing');
      }
    } catch (e: any) {
      setError(e.message || 'Failed to submit podcast video');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="animate-fade-up" style={{ minHeight: '80vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '24px 16px' }}>
        {/* ── Main Studio Card ── */}
        <div className="glass" style={{ padding: '36px', maxWidth: '640px', width: '100%', textAlign: 'center', borderRadius: '16px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🎙️</div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, marginBottom: '8px' }}>
            Podcast & Interview Area Selection
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: 1.5, marginBottom: '24px' }}>
            Interactive video preview and custom bounding box framing for multi-speaker podcasts, talks, and interviews.
          </p>

          <button
            onClick={() => {
              setModalMode('manual');
              setModalOpen(true);
            }}
            className="btn-primary"
            style={{ padding: '12px 28px', fontSize: '14px', fontWeight: 700 }}
          >
            Open Podcast Selection Studio
          </button>
        </div>

        {/* ── Secondary Advanced Podcast Card ── */}
        <div
          id="advanced-podcast-card"
          style={{
            marginTop: '24px',
            maxWidth: '640px',
            width: '100%',
            padding: '20px 24px',
            borderRadius: '14px',
            background: 'rgba(30, 41, 59, 0.75)',
            border: '1px solid rgba(148, 163, 184, 0.2)',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            textAlign: 'left',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '18px' }}>🎬</span>
              <span style={{ fontSize: '16px', fontWeight: 800, color: '#f8fafc' }}>Advanced Podcast</span>
              <span style={{ fontSize: '11px', fontWeight: 700, padding: '2px 8px', borderRadius: '12px', background: 'rgba(99, 102, 241, 0.25)', color: '#a5b4fc', border: '1px solid rgba(99, 102, 241, 0.35)' }}>
                Camera Following
              </span>
            </div>
            <button
              id="explore-advanced-podcast-btn"
              onClick={() => {
                setModalMode('advanced');
                setModalOpen(true);
              }}
              className="btn-secondary"
              style={{
                padding: '8px 16px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                backgroundColor: 'rgba(51, 65, 85, 0.8)',
                border: '1px solid rgba(148, 163, 184, 0.3)',
                borderRadius: '8px',
                color: '#e2e8f0',
                maxWidth: '100%',
              }}
            >
              Explore Advanced Podcast
            </button>
          </div>
          <p style={{ margin: 0, fontSize: '13px', color: '#cbd5e1', fontWeight: 600 }}>
            A vertical podcast clip that follows the person shown by the original camera.
          </p>
          <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8', lineHeight: 1.4 }}>
            Select each participant once. ClipForge follows camera cuts and reframes whoever the original camera is showing.
          </p>
        </div>
      </div>

      {/* ── Dedicated Podcast Selection Modal (Decoupled from animate-fade-up) ── */}
      <PodcastSelectionModal
        isOpen={modalOpen}
        initialMode={modalMode}
        onClose={() => setModalOpen(false)}
        onConfirm={handleConfirm}
        isSubmitting={isSubmitting}
        errorMessage={error}
      />
    </>
  );
}
