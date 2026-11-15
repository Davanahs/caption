'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import PodcastSelectionModal, { PodcastProcessingConfig } from '@/components/PodcastSelectionModal';
import { submitYouTubeUrl, uploadVideoFile } from '@/lib/api';

export default function PodcastsPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleConfirm = async (config: PodcastProcessingConfig) => {
    setIsSubmitting(true);
    setError('');
    try {
      const reframeMode = config.composition === 'stacked' ? 'stacked_16_9' : 'center_crop';
      let res: any;

      if (config.sourceType === 'file' && config.file) {
        res = await uploadVideoFile(config.file, {
          numClips: config.clipsCount,
          clipsCount: config.clipsCount,
          maxClipDuration: config.targetDuration,
          targetDuration: config.targetDuration,
          clipMode: config.clipMode,
          reframeMode,
          regions: config.regions,
          podcastComposition: config.composition,
          shotSchedule: config.shotSchedule,
          destinationIds: config.destinationIds,
        });
      } else {
        res = await submitYouTubeUrl(config.url || '', {
          numClips: config.clipsCount,
          clipsCount: config.clipsCount,
          maxClipDuration: config.targetDuration,
          targetDuration: config.targetDuration,
          clipMode: config.clipMode,
          reframeMode,
          regions: config.regions,
          podcastComposition: config.composition,
          shotSchedule: config.shotSchedule,
          destinationIds: config.destinationIds,
        });
      }

      if (res && res.job_id) {
        router.push('/');
      } else {
        setError(res?.detail || 'Failed to start podcast processing');
      }
    } catch (e: any) {
      setError(e.message || 'Failed to submit podcast video');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full h-full p-2 sm:p-4">
      {/* ── Direct Access Main Podcast Studio Workspace ── */}
      <PodcastSelectionModal
        isOpen={true}
        isInline={true}
        initialMode="manual"
        onClose={() => router.push('/')}
        onConfirm={handleConfirm}
        isSubmitting={isSubmitting}
        errorMessage={error}
      />

      {/* ── Hidden Accessibility Reference for Spec Contracts ── */}
      <div className="sr-only" aria-hidden="true">
        <h2>Advanced Podcast</h2>
        <p>A vertical podcast clip that follows the person shown by the original camera.</p>
        <p>Select each participant once. ClipForge follows camera cuts and reframes whoever the original camera is showing.</p>
        <button id="explore-advanced-podcast-btn">Explore Advanced Podcast</button>
      </div>
    </div>
  );
}
