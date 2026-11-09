'use client';
import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  listClips, deleteClip, downloadClipUrl, thumbnailUrl, publishNow, getClipMetadata,
  previewCleanup, executeCleanup, CleanupPreviewResponse, CleanupExecuteResponse,
  getBrollPlan, applyBrollPlan, BrollPlan,
  getSfxPlan, generateSfxPlan, applySfxPlan, SFXPlan,
  getHookPlan, generateHookPlan, applyHookPlan, HookPlan,
  getDubbingLanguages, getClipDubbing, triggerClipDubbing, getDubbingTaskStatus,
  DubbingLanguage, DubbingPlanItem,
  listClipVariants, downloadVariantUrl, ClipVariantItem
} from '@/lib/api';
import { RetentionHeatmap } from '@/components/RetentionHeatmap';
import { useFocusTrap } from '@/lib/useFocusTrap';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

const STATUS_COLORS: Record<string, string> = {
  draft: 'badge-muted', queued: 'badge-warning',
  published: 'badge-success', failed: 'badge-danger',
};

const SCORE_LABEL = (s: number) =>
  s >= 8.5 ? { label: '🔥 Viral', color: '#10b981' }
  : s >= 7  ? { label: '⚡ High',  color: '#f59e0b' }
  : s >= 5  ? { label: '👍 Good',  color: '#6366f1' }
  :           { label: '💤 Low',   color: '#6b7280' };

function ScoreRing({ score }: { score: number }) {
  const { color } = SCORE_LABEL(score);
  const boundedScore = Number(Number(score || 0).toFixed(1));
  return (
    <div
      role="meter"
      aria-label={`Viral moment score: ${boundedScore} out of 10`}
      aria-valuenow={boundedScore}
      aria-valuemin={0}
      aria-valuemax={10}
      className="score-ring"
      style={{ background: `${color}22`, border: `2px solid ${color}` }}
    >
      <span aria-hidden="true" style={{ fontSize: 11, fontWeight: 700, color }}>
        {boundedScore.toFixed(1)}
      </span>
    </div>
  );
}

function PreviewModal({ clip, onClose, onRestyled }: { clip: any; onClose: () => void; onRestyled?: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [meta, setMeta] = useState<any>(null);
  const [videoError, setVideoError] = useState(false);

  // Phase 2.1 & Phase 6.1: AI Creative Enhancements state
  const [enhancementTab, setEnhancementTab] = useState<'hook' | 'broll' | 'sfx' | 'dubbing'>('hook');
  const [hookPlan, setHookPlan] = useState<HookPlan | null>(null);
  const [brollPlan, setBrollPlan] = useState<BrollPlan | null>(null);
  const [sfxPlan, setSfxPlan] = useState<SFXPlan | null>(null);
  const [dubbingLanguages, setDubbingLanguages] = useState<DubbingLanguage[]>([]);
  const [dubbingPlans, setDubbingPlans] = useState<DubbingPlanItem[]>([]);
  const [selectedLanguage, setSelectedLanguage] = useState<string>('es');
  const [voiceProvider, setVoiceProvider] = useState<'edge_tts' | 'elevenlabs'>('edge_tts');
  const [cloneConsent, setCloneConsent] = useState(false);
  const [loadingDubbing, setLoadingDubbing] = useState(false);
  const [loadingEnhancement, setLoadingEnhancement] = useState(false);
  const [applyingEnhancement, setApplyingEnhancement] = useState(false);
  const [enhancementMessage, setEnhancementMessage] = useState<{ text: string; isError?: boolean } | null>(null);

  // Variant selector state
  const [variants, setVariants] = useState<ClipVariantItem[]>([]);
  const [selectedVariantId, setSelectedVariantId] = useState<string>('original');
  const [loadingVariants, setLoadingVariants] = useState<boolean>(false);

  const fetchVariants = () => {
    setLoadingVariants(true);
    listClipVariants(clip.id)
      .then((items) => {
        setVariants(items || []);
      })
      .catch(() => {})
      .finally(() => setLoadingVariants(false));
  };

  const modalContainerRef = useRef<HTMLDivElement>(null);
  useFocusTrap(true, modalContainerRef, onClose);

  useEffect(() => {
    fetchVariants();

    getClipMetadata(clip.id).then((d: any) => {
      if (d && d.title) setMeta(d);
    }).catch(() => {});

    // Only pre-fetch enhancement plans if the clip has rendered media
    const hasMedia = Boolean(clip.output_path && clip.output_path.trim() !== '');
    if (hasMedia) {
      // Pre-fetch existing hook plan if present
      getHookPlan(clip.id).then(p => {
        if (p && p.opportunities) setHookPlan(p);
      }).catch(() => {});

      // Pre-fetch existing sfx plan if present
      getSfxPlan(clip.id).then(p => {
        if (p && p.placements) setSfxPlan(p);
      }).catch(() => {});

      // Pre-fetch dubbing languages and existing plans
      getDubbingLanguages().then(res => {
        if (res && res.languages) setDubbingLanguages(res.languages);
      }).catch(() => {});

      getClipDubbing(clip.id).then(res => {
        if (res && res.plans) setDubbingPlans(res.plans);
      }).catch(() => {});
    }
  }, [clip.id, clip.output_path]);

  const handleTriggerDubbing = async () => {
    if (voiceProvider === 'elevenlabs' && !cloneConsent) {
      setEnhancementMessage({ text: '⚠️ Voice cloning requires explicit authorization consent.', isError: true });
      return;
    }
    setLoadingDubbing(true);
    setEnhancementMessage(null);
    try {
      const res = await triggerClipDubbing(clip.id, {
        clip_id: clip.id,
        target_language: selectedLanguage,
        voice_provider: voiceProvider,
        voice_id: 'default',
        is_voice_clone: voiceProvider === 'elevenlabs',
        authorization_granted: voiceProvider === 'elevenlabs' ? cloneConsent : false,
      });
      setEnhancementMessage({ text: `🌐 Dubbing dispatched (Task: ${res.task_id.slice(0, 8)}...) for ${selectedLanguage.toUpperCase()}! Synthesizing synchronized voice track...` });

      let attempts = 0;
      const timer = setInterval(async () => {
        attempts++;
        try {
          const statusRes = await getDubbingTaskStatus(res.task_id);
          if (statusRes.ready || statusRes.status === 'SUCCESS') {
            clearInterval(timer);
            setLoadingDubbing(false);
            setEnhancementMessage({ text: `🎉 Multi-language dubbing completed for ${selectedLanguage.toUpperCase()}!` });
            const updated = await getClipDubbing(clip.id);
            if (updated && updated.plans) setDubbingPlans(updated.plans);
            fetchVariants();
            if (onRestyled) onRestyled();
          } else if (statusRes.status === 'FAILURE') {
            clearInterval(timer);
            setLoadingDubbing(false);
            setEnhancementMessage({ text: `❌ Dubbing failed: ${statusRes.error || 'Speech timing or synthesis error'}`, isError: true });
          } else if (attempts >= 15) {
            clearInterval(timer);
            setLoadingDubbing(false);
            const updated = await getClipDubbing(clip.id);
            if (updated && updated.plans) setDubbingPlans(updated.plans);
          }
        } catch {
          if (attempts >= 15) {
            clearInterval(timer);
            setLoadingDubbing(false);
          }
        }
      }, 2000);
    } catch (err: any) {
      setLoadingDubbing(false);
      setEnhancementMessage({ text: err.message || 'Failed to dispatch dubbing task', isError: true });
    }
  };

  const handleGenerateHookPlan = async () => {
    setLoadingEnhancement(true);
    setEnhancementMessage(null);
    try {
      const res = await generateHookPlan(clip.id);
      setEnhancementMessage({ text: `Hook analysis started (Task: ${res.task_id.slice(0, 8)}...). Fetching opportunities...` });
      let attempts = 0;
      const timer = setInterval(async () => {
        attempts++;
        try {
          const p = await getHookPlan(clip.id);
          if (p && p.opportunities) {
            setHookPlan(p);
            clearInterval(timer);
            setLoadingEnhancement(false);
            setEnhancementMessage({ text: `✨ Hook plan ready with ${p.opportunities.length} detected opportunities!` });
          }
        } catch {
          if (attempts >= 6) {
            clearInterval(timer);
            setLoadingEnhancement(false);
          }
        }
      }, 1500);
    } catch (err: any) {
      setLoadingEnhancement(false);
      setEnhancementMessage({ text: err.message || 'Failed to trigger hook opportunity analysis', isError: true });
    }
  };

  const handleApplyHookPlan = async () => {
    if (!hookPlan) return;
    setApplyingEnhancement(true);
    setEnhancementMessage(null);
    try {
      const res = await applyHookPlan(clip.id, hookPlan);
      setEnhancementMessage({ text: `⚡ Hook overlay applied! Re-rendering task: ${res.task_id.slice(0, 8)}...` });
      if (onRestyled) onRestyled();
      setTimeout(fetchVariants, 3000);
    } catch (err: any) {
      setEnhancementMessage({ text: err.message || 'Failed to apply Hook overlay', isError: true });
    } finally {
      setApplyingEnhancement(false);
    }
  };

  const handleLoadBrollPlan = async () => {
    setLoadingEnhancement(true);
    setEnhancementMessage(null);
    try {
      const p = await getBrollPlan(clip.id);
      setBrollPlan(p);
      setEnhancementMessage({ text: `✨ B-Roll plan generated with ${p.placements?.length || 0} visual cutaways!` });
    } catch (err: any) {
      setEnhancementMessage({ text: err.message || 'Failed to generate B-roll plan', isError: true });
    } finally {
      setLoadingEnhancement(false);
    }
  };

  const handleApplyBrollPlan = async () => {
    if (!brollPlan) return;
    if (!brollPlan.placements || brollPlan.placements.length === 0) {
      setEnhancementMessage({ text: 'No B-roll placements found in plan. Clip was not modified.' });
      return;
    }
    setApplyingEnhancement(true);
    setEnhancementMessage(null);
    try {
      const res = await applyBrollPlan(clip.id, brollPlan);
      if (res.applied === false) {
        setEnhancementMessage({ text: res.message || 'No B-roll placements found in plan. Clip was not modified.' });
        return;
      }
      setEnhancementMessage({ text: `⚡ B-Roll cutaways applied! Compositing task: ${res.task_id ? res.task_id.slice(0, 8) : 'done'}...` });
      if (onRestyled) onRestyled();
      setTimeout(fetchVariants, 3000);
    } catch (err: any) {
      setEnhancementMessage({ text: err.message || 'Failed to apply B-roll plan', isError: true });
    } finally {
      setApplyingEnhancement(false);
    }
  };

  const handleLoadSfxPlan = async () => {
    setLoadingEnhancement(true);
    setEnhancementMessage(null);
    try {
      const p = await generateSfxPlan(clip.id);
      setSfxPlan(p);
      setEnhancementMessage({ text: `✨ SFX plan generated with ${p.placements?.length || 0} audio retention cues!` });
    } catch (err: any) {
      setEnhancementMessage({ text: err.message || 'Failed to generate SFX plan', isError: true });
    } finally {
      setLoadingEnhancement(false);
    }
  };

  const handleApplySfxPlan = async () => {
    if (!sfxPlan) return;
    if (!sfxPlan.placements || sfxPlan.placements.length === 0) {
      setEnhancementMessage({ text: 'No suitable sound-effect placements were found. The clip was not modified.' });
      return;
    }
    setApplyingEnhancement(true);
    setEnhancementMessage(null);
    try {
      const res = await applySfxPlan(clip.id, sfxPlan);
      if (res.applied === false) {
        setEnhancementMessage({ text: res.message || 'No suitable sound-effect placements were found. The clip was not modified.' });
        return;
      }
      setEnhancementMessage({ text: `⚡ Sound FX mixed! Audio rendering task: ${res.task_id ? res.task_id.slice(0, 8) : 'done'}...` });
      if (onRestyled) onRestyled();
      setTimeout(fetchVariants, 3000);
    } catch (err: any) {
      setEnhancementMessage({ text: err.message || 'Failed to apply SFX plan', isError: true });
    } finally {
      setApplyingEnhancement(false);
    }
  };


  const sl = SCORE_LABEL(clip.score);
  const selectedVariant = variants.find(v => v.variant_id === selectedVariantId);
  const activeVideoUrl = selectedVariantId === 'original'
    ? downloadClipUrl(clip.id)
    : downloadVariantUrl(clip.id, selectedVariantId);

  let attributionText = '';
  if (selectedVariant && selectedVariant.metadata) {
    const meta = selectedVariant.metadata;
    if (meta.creator_name) {
      attributionText = `Stock footage by ${meta.creator_name} on Pexels`;
    } else if (meta.attribution) {
      attributionText = meta.attribution;
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="preview-modal-title"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.88)', backdropFilter: 'blur(12px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '24px', overflowY: 'auto',
      }}
    >
      <div
        ref={modalContainerRef}
        tabIndex={-1}
        onClick={e => e.stopPropagation()}
        className="preview-modal-content"
        style={{
          display: 'flex', gap: 28, alignItems: 'center', justifyContent: 'center',
          maxWidth: '940px', width: '100%', maxHeight: '88vh',
          background: 'rgba(18, 18, 24, 0.95)', border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 24, padding: 24, boxShadow: '0 32px 80px rgba(0,0,0,0.9)',
          overflowY: 'auto',
        }}
      >
        {/* ── Responsive Phone Frame with Variant Selector ── */}
        <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', width: '320px' }}>
          {/* Variant Selector Pills */}
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12, justifyContent: 'center', width: '100%'
          }}>
            <button
              type="button"
              onClick={() => { setSelectedVariantId('original'); setVideoError(false); }}
              style={{
                fontSize: 11, fontWeight: 600, padding: '5px 10px', borderRadius: 12, border: 'none', cursor: 'pointer',
                background: selectedVariantId === 'original' ? '#6366f1' : 'rgba(255,255,255,0.08)',
                color: selectedVariantId === 'original' ? '#fff' : 'rgba(255,255,255,0.7)',
                boxShadow: selectedVariantId === 'original' ? '0 0 10px rgba(99,102,241,0.5)' : 'none',
                transition: 'all 0.15s ease'
              }}
            >
              🎬 Original
            </button>
            {variants.map(v => {
              const isSelected = selectedVariantId === v.variant_id;
              const icon = v.variant_type === 'hook' ? '🪝'
                : v.variant_type === 'broll' ? '📹'
                : v.variant_type.includes('sfx') ? '🔊'
                : v.variant_type.includes('dub') ? '🌐'
                : '⚡';
              return (
                <button
                  key={v.variant_id}
                  type="button"
                  onClick={() => { setSelectedVariantId(v.variant_id); setVideoError(false); }}
                  style={{
                    fontSize: 11, fontWeight: 600, padding: '5px 10px', borderRadius: 12, border: 'none', cursor: 'pointer',
                    background: isSelected ? '#6366f1' : 'rgba(255,255,255,0.08)',
                    color: isSelected ? '#fff' : 'rgba(255,255,255,0.7)',
                    boxShadow: isSelected ? '0 0 10px rgba(99,102,241,0.5)' : 'none',
                    transition: 'all 0.15s ease'
                  }}
                  title={v.created_at ? `Created: ${new Date(v.created_at).toLocaleTimeString()}` : undefined}
                >
                  {icon} {v.label}
                </button>
              );
            })}
          </div>

          <div style={{
            height: 'min(64vh, 520px)', aspectRatio: '9/16',
            background: '#000', borderRadius: 20,
            overflow: 'hidden',
            boxShadow: '0 20px 50px rgba(0,0,0,0.8)',
            border: '2px solid rgba(255,255,255,0.15)',
            position: 'relative',
          }}>
            {!videoError ? (
              <video
                key={activeVideoUrl}
                ref={videoRef}
                autoPlay controls
                style={{
                  width: '100%', height: '100%',
                  objectFit: 'contain',
                  background: '#000',
                  display: 'block',
                }}
                src={activeVideoUrl}
                onError={() => setVideoError(true)}
              />
            ) : (
              <div style={{
                width: '100%', height: '100%', display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,0.4)',
                textAlign: 'center', padding: 20
              }}>
                <div style={{ fontSize: 40, marginBottom: 12 }}>⚠️</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>Media Unavailable</div>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  {selectedVariantId === 'original' ? 'The original clip could not be loaded.' : `Variant '${selectedVariant?.label || selectedVariantId}' could not be loaded.`}
                </div>
              </div>
            )}
            {/* Notch indicator */}
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0,
              height: 22, background: 'rgba(0,0,0,0.65)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 9, color: 'rgba(255,255,255,0.6)', letterSpacing: 1,
              pointerEvents: 'none', userSelect: 'none',
            }}>📱 9:16 YOUTUBE SHORTS FORMAT</div>
          </div>

          {/* Active variant label & attribution */}
          <div style={{ marginTop: 8, textAlign: 'center', width: '100%' }}>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)' }}>
              Previewing: <span style={{ fontWeight: 700, color: '#a5b4fc' }}>{selectedVariant ? selectedVariant.label : 'Original Clip'}</span>
            </div>
            {attributionText && (
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)', marginTop: 2 }}>
                ℹ️ {attributionText}
              </div>
            )}
          </div>
        </div>

        {/* ── Sidebar details ── */}
        <div style={{ flex: 1, color: '#fff', minWidth: 260, maxHeight: '80vh', overflowY: 'auto' }}>
          <h3 id="preview-modal-title" style={{ fontSize: 18, fontWeight: 700, margin: 0, marginBottom: 6, fontFamily: "'Space Grotesk',sans-serif", wordBreak: 'break-word' }}>
            {clip.title}
          </h3>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginBottom: 16 }}>
            {clip.start_time?.toFixed(1)}s – {clip.end_time?.toFixed(1)}s &nbsp;·&nbsp; {Math.floor(clip.duration)}s clip
          </div>

          {/* Score */}
          <div style={{ background: 'rgba(255,255,255,0.06)', borderRadius: 12, padding: '12px 14px', marginBottom: 10 }}>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginBottom: 4 }}>VIRAL SCORE</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: sl.color }}>
                {clip.score.toFixed(1)}<span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)' }}>/10</span>
              </div>
              <span style={{ fontSize: 11, fontWeight: 600, color: sl.color }}>{sl.label}</span>
            </div>
          </div>

          {/* Status */}
          <div style={{ background: 'rgba(255,255,255,0.06)', borderRadius: 12, padding: '12px 14px', marginBottom: 10 }}>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginBottom: 4 }}>STATUS</div>
            <span className={`badge ${STATUS_COLORS[clip.publish_status] || 'badge-muted'}`}>{clip.publish_status}</span>
          </div>

          {/* Source */}
          {clip.source_title && (
            <div style={{ background: 'rgba(255,255,255,0.06)', borderRadius: 12, padding: '12px 14px', marginBottom: 10 }}>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginBottom: 4 }}>SOURCE VIDEO</div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)', lineHeight: 1.5, wordBreak: 'break-word' }}>{clip.source_title}</div>
            </div>
          )}


          {/* AI Generated Metadata */}
          {meta && (
            <div style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 12, padding: '12px 14px', marginBottom: 16 }}>
              <div style={{ fontSize: 10, color: 'var(--success)', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
                ✨ AI METADATA READY
              </div>
              
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.4)', marginBottom: 2 }}>TITLE</div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.85)', lineHeight: 1.4 }}>{meta.title}</div>
              </div>
              
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.4)', marginBottom: 2 }}>DESCRIPTION & TAGS</div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)', lineHeight: 1.4, maxHeight: 60, overflowY: 'auto' }}>
                  {meta.description}
                  {meta.hashtags && meta.hashtags.length > 0 && (
                    <div style={{ color: 'var(--accent)', marginTop: 4 }}>
                      {Array.isArray(meta.hashtags) ? meta.hashtags.join(' ') : meta.hashtags}
                    </div>
                  )}
                </div>
              </div>
              
              {meta.pinned_comment && (
                <div>
                  <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.4)', marginBottom: 2 }}>PINNED COMMENT</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)', fontStyle: 'italic' }}>&quot;{meta.pinned_comment}&quot;</div>
                </div>
              )}
            </div>
          )}

          {/* Retention Heatmap & AutoFix */}
          {clip.output_path && clip.output_path.trim() !== '' ? (
            <RetentionHeatmap clipId={clip.id} />
          ) : (
            <div style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: 12, padding: '14px', marginBottom: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,0.7)', marginBottom: 4 }}>
                Retention Heatmap & Creative Enhancements
              </div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>
                ⚠️ This clip has no rendered media file available. Retention analysis and creative enhancements require rendered media.
              </div>
            </div>
          )}

          {/* ── AI Creative Enhancements (Phase 2.1 - B-roll, SFX, Hooks) ── */}
          <div
            data-testid="ai-enhancements-panel"
            style={{
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 14,
              padding: 14,
              marginBottom: 16,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: 0.3, fontFamily: "'Space Grotesk',sans-serif" }}>
                  ✨ AI CREATIVE ENHANCEMENTS
                </span>
                <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: 'rgba(99,102,241,0.25)', color: '#a5b4fc', fontWeight: 600 }}>
                  PRO SUITE
                </span>
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 12, background: 'rgba(0,0,0,0.3)', padding: 3, borderRadius: 8 }}>
              <button
                type="button"
                data-testid="tab-hook"
                onClick={() => { setEnhancementTab('hook'); setEnhancementMessage(null); }}
                style={{
                  flex: 1, padding: '6px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  cursor: 'pointer', border: 'none', transition: 'all 0.15s ease',
                  background: enhancementTab === 'hook' ? 'rgba(99,102,241,0.4)' : 'transparent',
                  color: enhancementTab === 'hook' ? '#fff' : 'rgba(255,255,255,0.6)',
                }}
              >
                🎣 Hooks
              </button>
              <button
                type="button"
                data-testid="tab-broll"
                onClick={() => { setEnhancementTab('broll'); setEnhancementMessage(null); }}
                style={{
                  flex: 1, padding: '6px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  cursor: 'pointer', border: 'none', transition: 'all 0.15s ease',
                  background: enhancementTab === 'broll' ? 'rgba(56,189,248,0.4)' : 'transparent',
                  color: enhancementTab === 'broll' ? '#fff' : 'rgba(255,255,255,0.6)',
                }}
              >
                🎬 B-Roll
              </button>
              <button
                type="button"
                data-testid="tab-sfx"
                onClick={() => { setEnhancementTab('sfx'); setEnhancementMessage(null); }}
                style={{
                  flex: 1, padding: '6px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  cursor: 'pointer', border: 'none', transition: 'all 0.15s ease',
                  background: enhancementTab === 'sfx' ? 'rgba(234,179,8,0.4)' : 'transparent',
                  color: enhancementTab === 'sfx' ? '#fff' : 'rgba(255,255,255,0.6)',
                }}
              >
                🔊 SFX
              </button>
              <button
                type="button"
                data-testid="tab-dubbing"
                onClick={() => { setEnhancementTab('dubbing'); setEnhancementMessage(null); }}
                style={{
                  flex: 1, padding: '6px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  cursor: 'pointer', border: 'none', transition: 'all 0.15s ease',
                  background: enhancementTab === 'dubbing' ? 'rgba(168,85,247,0.4)' : 'transparent',
                  color: enhancementTab === 'dubbing' ? '#fff' : 'rgba(255,255,255,0.6)',
                }}
              >
                🌐 Dubbing
              </button>
            </div>

            {/* Status / Message Banner */}
            {enhancementMessage && (
              <div
                data-testid={enhancementMessage.isError ? "enhancement-error-banner" : "enhancement-status-banner"}
                style={{
                  padding: '8px 10px',
                  borderRadius: 8,
                  marginBottom: 10,
                  fontSize: 11,
                  lineHeight: 1.4,
                  background: enhancementMessage.isError ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.15)',
                  border: `1px solid ${enhancementMessage.isError ? 'rgba(239,68,68,0.35)' : 'rgba(16,185,129,0.35)'}`,
                  color: enhancementMessage.isError ? '#fca5a5' : '#86efac',
                }}
              >
                {enhancementMessage.text}
              </div>
            )}

            {/* Tab 1: Hooks */}
            {enhancementTab === 'hook' && (
              <div>
                {hookPlan ? (
                  <div>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
                      <span>OPPORTUNITIES DETECTED</span>
                      <span style={{ color: 'var(--accent)' }}>{hookPlan.opportunities?.length || 0} active</span>
                    </div>

                    {hookPlan.concepts && hookPlan.concepts.length > 0 && (
                      <div style={{ background: 'rgba(0,0,0,0.35)', borderRadius: 8, padding: 10, marginBottom: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontSize: 10, fontWeight: 700, color: '#c7d2fe', textTransform: 'uppercase' }}>
                            {hookPlan.concepts[0].hook_style || 'Curiosity Gap'}
                          </span>
                          <span style={{ fontSize: 9, color: '#38bdf8' }}>
                            {Math.round((hookPlan.concepts[0].confidence || 0.85) * 100)}% match
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: '#f3f4f6', fontStyle: 'italic', marginBottom: 6 }}>
                          &ldquo;{hookPlan.concepts[0].hook_text}&rdquo;
                        </div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.7)' }}>
                            ⏱️ {hookPlan.concepts[0].target_duration}s title overlay
                          </span>
                          <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: 'rgba(99,102,241,0.2)', color: '#a5b4fc' }}>
                            🔍 1.2x Kinetic Zoom
                          </span>
                          <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: 'rgba(16,185,129,0.2)', color: '#6ee7b7' }}>
                            🎙️ Voiceover Mix
                          </span>
                        </div>
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        type="button"
                        data-testid="btn-apply-hook"
                        onClick={handleApplyHookPlan}
                        disabled={applyingEnhancement || loadingEnhancement}
                        style={{
                          flex: 1.5, padding: '8px 12px', borderRadius: 8,
                          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                          color: '#fff', fontSize: 11, fontWeight: 700, border: 'none',
                          cursor: (applyingEnhancement || loadingEnhancement) ? 'not-allowed' : 'pointer',
                          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                          opacity: (applyingEnhancement || loadingEnhancement) ? 0.6 : 1,
                        }}
                      >
                        {applyingEnhancement ? '⏳ Applying...' : '⚡ Apply Hook Overlay'}
                      </button>
                      <button
                        type="button"
                        data-testid="btn-generate-hook"
                        onClick={handleGenerateHookPlan}
                        disabled={loadingEnhancement || applyingEnhancement}
                        style={{
                          flex: 1, padding: '8px 10px', borderRadius: 8,
                          background: 'rgba(255,255,255,0.06)',
                          border: '1px solid rgba(255,255,255,0.12)',
                          color: 'rgba(255,255,255,0.8)', fontSize: 11, fontWeight: 500,
                          cursor: (loadingEnhancement || applyingEnhancement) ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {loadingEnhancement ? '⏳...' : '🔄 Re-analyze'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', margin: 0, marginBottom: 10, lineHeight: 1.4 }}>
                      Detects the opening curiosity gap and prepares an engaging kinetic hook zoom with title card overlay.
                    </p>
                    <button
                      type="button"
                      data-testid="btn-generate-hook"
                      onClick={handleGenerateHookPlan}
                      disabled={loadingEnhancement}
                      style={{
                        width: '100%', padding: '8px 12px', borderRadius: 8,
                        background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
                        color: '#fff', fontSize: 11, fontWeight: 700, border: 'none',
                        cursor: loadingEnhancement ? 'not-allowed' : 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                        opacity: loadingEnhancement ? 0.6 : 1,
                      }}
                    >
                      {loadingEnhancement ? '⏳ Analyzing Opportunities...' : '✨ Analyze Hook Opportunities'}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: B-Roll */}
            {enhancementTab === 'broll' && (
              <div>
                {brollPlan ? (
                  <div>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
                      <span>CUTAWAY PLACEMENTS</span>
                      <span style={{ color: '#38bdf8' }}>{brollPlan.placements?.length || 0} cutaways</span>
                    </div>

                    <div style={{ maxHeight: 100, overflowY: 'auto', marginBottom: 10 }}>
                      {brollPlan.placements?.map((p, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            background: 'rgba(0,0,0,0.3)', padding: '6px 8px', borderRadius: 6,
                            marginBottom: 4, fontSize: 10, border: '1px solid rgba(255,255,255,0.05)',
                          }}
                        >
                          <span style={{ color: '#bae6fd', fontWeight: 600 }}>
                            {p.display_mode === 'full_cutaway' ? '🎬 Full Cutaway' : '🖼️ Picture-in-Picture'}
                          </span>
                          <span style={{ color: 'rgba(255,255,255,0.6)' }}>
                            {p.start_time.toFixed(1)}s – {p.end_time.toFixed(1)}s
                          </span>
                        </div>
                      ))}
                    </div>

                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        type="button"
                        data-testid="btn-apply-broll"
                        onClick={handleApplyBrollPlan}
                        disabled={applyingEnhancement || loadingEnhancement}
                        style={{
                          flex: 1.5, padding: '8px 12px', borderRadius: 8,
                          background: 'linear-gradient(135deg, #0284c7, #0369a1)',
                          color: '#fff', fontSize: 11, fontWeight: 700, border: 'none',
                          cursor: (applyingEnhancement || loadingEnhancement) ? 'not-allowed' : 'pointer',
                          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                          opacity: (applyingEnhancement || loadingEnhancement) ? 0.6 : 1,
                        }}
                      >
                        {applyingEnhancement ? '⏳ Applying...' : '⚡ Apply B-Roll to Clip'}
                      </button>
                      <button
                        type="button"
                        data-testid="btn-load-broll"
                        onClick={handleLoadBrollPlan}
                        disabled={loadingEnhancement || applyingEnhancement}
                        style={{
                          flex: 1, padding: '8px 10px', borderRadius: 8,
                          background: 'rgba(255,255,255,0.06)',
                          border: '1px solid rgba(255,255,255,0.12)',
                          color: 'rgba(255,255,255,0.8)', fontSize: 11, fontWeight: 500,
                          cursor: (loadingEnhancement || applyingEnhancement) ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {loadingEnhancement ? '⏳...' : '🔄 Re-plan'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', margin: 0, marginBottom: 10, lineHeight: 1.4 }}>
                      Automatically inserts relevant context cutaways or PiP video overlays synced to speech topics.
                    </p>
                    <button
                      type="button"
                      data-testid="btn-load-broll"
                      onClick={handleLoadBrollPlan}
                      disabled={loadingEnhancement}
                      style={{
                        width: '100%', padding: '8px 12px', borderRadius: 8,
                        background: 'linear-gradient(135deg, #0284c7, #2563eb)',
                        color: '#fff', fontSize: 11, fontWeight: 700, border: 'none',
                        cursor: loadingEnhancement ? 'not-allowed' : 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                        opacity: loadingEnhancement ? 0.6 : 1,
                      }}
                    >
                      {loadingEnhancement ? '⏳ Generating Plan...' : '✨ Preview B-Roll Plan'}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: Sound FX */}
            {enhancementTab === 'sfx' && (
              <div>
                {sfxPlan ? (
                  <div>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
                      <span>AUDIO CUES</span>
                      <span style={{ color: '#facc15' }}>{sfxPlan.placements?.length || 0} sounds</span>
                    </div>

                    <div style={{ maxHeight: 100, overflowY: 'auto', marginBottom: 10 }}>
                      {sfxPlan.placements?.map((p, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            background: 'rgba(0,0,0,0.3)', padding: '6px 8px', borderRadius: 6,
                            marginBottom: 4, fontSize: 10, border: '1px solid rgba(255,255,255,0.05)',
                          }}
                        >
                          <span style={{ color: '#fef08a', fontWeight: 600 }}>
                            🔊 {p.category.toUpperCase()}
                          </span>
                          <span style={{ color: 'rgba(255,255,255,0.6)' }}>
                            {p.start_time.toFixed(1)}s (ducking {p.ducking_enabled ? 'on' : 'off'})
                          </span>
                        </div>
                      ))}
                    </div>

                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        type="button"
                        data-testid="btn-apply-sfx"
                        onClick={handleApplySfxPlan}
                        disabled={applyingEnhancement || loadingEnhancement}
                        style={{
                          flex: 1.5, padding: '8px 12px', borderRadius: 8,
                          background: 'linear-gradient(135deg, #d97706, #b45309)',
                          color: '#fff', fontSize: 11, fontWeight: 700, border: 'none',
                          cursor: (applyingEnhancement || loadingEnhancement) ? 'not-allowed' : 'pointer',
                          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                          opacity: (applyingEnhancement || loadingEnhancement) ? 0.6 : 1,
                        }}
                      >
                        {applyingEnhancement ? '⏳ Applying...' : '⚡ Apply Sound FX to Clip'}
                      </button>
                      <button
                        type="button"
                        data-testid="btn-load-sfx"
                        onClick={handleLoadSfxPlan}
                        disabled={loadingEnhancement || applyingEnhancement}
                        style={{
                          flex: 1, padding: '8px 10px', borderRadius: 8,
                          background: 'rgba(255,255,255,0.06)',
                          border: '1px solid rgba(255,255,255,0.12)',
                          color: 'rgba(255,255,255,0.8)', fontSize: 11, fontWeight: 500,
                          cursor: (loadingEnhancement || applyingEnhancement) ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {loadingEnhancement ? '⏳...' : '🔄 Re-plan'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', margin: 0, marginBottom: 10, lineHeight: 1.4 }}>
                      Analyzes speech cadences and injects cinematic whooshes and impact sounds at retention drop-off points.
                    </p>
                    <button
                      type="button"
                      data-testid="btn-load-sfx"
                      onClick={handleLoadSfxPlan}
                      disabled={loadingEnhancement}
                      style={{
                        width: '100%', padding: '8px 12px', borderRadius: 8,
                        background: 'linear-gradient(135deg, #d97706, #ea580c)',
                        color: '#fff', fontSize: 11, fontWeight: 700, border: 'none',
                        cursor: loadingEnhancement ? 'not-allowed' : 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                        opacity: loadingEnhancement ? 0.6 : 1,
                      }}
                    >
                      {loadingEnhancement ? '⏳ Generating Plan...' : '✨ Preview SFX Plan'}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Tab 4: Multi-Language Dubbing (Phase 6.1 / CAP-001) */}
            {enhancementTab === 'dubbing' && (
              <div data-testid="panel-dubbing">
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>TARGET LANGUAGE</span>
                  <span style={{ color: '#c084fc', fontWeight: 600 }}>{dubbingPlans.length} dubbed tracks</span>
                </div>

                {/* Language Selectors */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginBottom: 10 }}>
                  {[
                    { code: 'es', label: 'Spanish', flag: '🇪🇸' },
                    { code: 'hi', label: 'Hindi', flag: '🇮🇳' },
                    { code: 'de', label: 'German', flag: '🇩🇪' },
                    { code: 'ja', label: 'Japanese', flag: '🇯🇵' },
                    { code: 'pt', label: 'Portuguese', flag: '🇧🇷' },
                    { code: 'fr', label: 'French', flag: '🇫🇷' },
                  ].map(l => (
                    <button
                      key={l.code}
                      type="button"
                      data-testid={`btn-lang-${l.code}`}
                      onClick={() => setSelectedLanguage(l.code)}
                      style={{
                        padding: '6px 4px',
                        borderRadius: 6,
                        fontSize: 10,
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 4,
                        border: selectedLanguage === l.code ? '1px solid #c084fc' : '1px solid rgba(255,255,255,0.08)',
                        background: selectedLanguage === l.code ? 'rgba(168,85,247,0.25)' : 'rgba(0,0,0,0.25)',
                        color: selectedLanguage === l.code ? '#fff' : 'rgba(255,255,255,0.7)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <span>{l.flag}</span>
                      <span>{l.label}</span>
                    </button>
                  ))}
                </div>

                {/* Voice Provider Options */}
                <div style={{ background: 'rgba(0,0,0,0.25)', padding: '8px 10px', borderRadius: 8, marginBottom: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', fontWeight: 600 }}>VOICE ENGINE</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        type="button"
                        data-testid="provider-edge-tts"
                        onClick={() => setVoiceProvider('edge_tts')}
                        style={{
                          fontSize: 9, padding: '3px 6px', borderRadius: 4, border: 'none', cursor: 'pointer',
                          background: voiceProvider === 'edge_tts' ? '#9333ea' : 'rgba(255,255,255,0.1)',
                          color: '#fff', fontWeight: 600
                        }}
                      >Edge Neural</button>
                      <button
                        type="button"
                        data-testid="provider-elevenlabs"
                        onClick={() => setVoiceProvider('elevenlabs')}
                        style={{
                          fontSize: 9, padding: '3px 6px', borderRadius: 4, border: 'none', cursor: 'pointer',
                          background: voiceProvider === 'elevenlabs' ? '#9333ea' : 'rgba(255,255,255,0.1)',
                          color: '#fff', fontWeight: 600
                        }}
                      >Voice Clone</button>
                    </div>
                  </div>

                  {voiceProvider === 'elevenlabs' && (
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: '#fbcfe8', cursor: 'pointer', marginTop: 4 }}>
                      <input
                        type="checkbox"
                        data-testid="input-voice-clone-consent"
                        checked={cloneConsent}
                        onChange={e => setCloneConsent(e.target.checked)}
                      />
                      <span>I authorize synthetic voice cloning for this clip</span>
                    </label>
                  )}
                </div>

                {/* Generate Button */}
                <button
                  type="button"
                  data-testid="btn-generate-dubbing"
                  onClick={handleTriggerDubbing}
                  disabled={loadingDubbing || (voiceProvider === 'elevenlabs' && !cloneConsent)}
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: 8,
                    background: (voiceProvider === 'elevenlabs' && !cloneConsent)
                      ? 'rgba(255,255,255,0.1)'
                      : 'linear-gradient(135deg, #9333ea, #c026d3)',
                    color: '#fff', fontSize: 11, fontWeight: 700, border: 'none',
                    cursor: (loadingDubbing || (voiceProvider === 'elevenlabs' && !cloneConsent)) ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                    opacity: loadingDubbing ? 0.7 : 1,
                    marginBottom: 10,
                  }}
                >
                  {loadingDubbing ? '⏳ Dubbing & Synchronizing...' : `🎙️ Generate ${selectedLanguage.toUpperCase()} Dubbed Audio`}
                </button>

                {/* Existing Dubbed Plans List */}
                {dubbingPlans.length > 0 && (
                  <div data-testid="list-dubbed-variants" style={{ maxHeight: 110, overflowY: 'auto' }}>
                    <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.5)', marginBottom: 4, fontWeight: 600 }}>
                      GENERATED DUBBED TRACKS
                    </div>
                    {dubbingPlans.map(plan => (
                      <div
                        key={plan.id}
                        data-testid={`card-dubbed-variant-${plan.id}`}
                        style={{
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          background: 'rgba(0,0,0,0.3)', padding: '6px 8px', borderRadius: 6,
                          marginBottom: 4, fontSize: 10, border: '1px solid rgba(255,255,255,0.05)',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span data-testid={`badge-dub-lang-${plan.id}`} style={{ fontWeight: 700, color: '#d8b4fe' }}>
                            🌐 {plan.target_language_name || plan.target_language.toUpperCase()}
                          </span>
                          <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.5)' }}>({plan.voice_provider})</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span
                            data-testid={`badge-dub-status-${plan.id}`}
                            style={{
                              fontSize: 9, padding: '2px 5px', borderRadius: 4, fontWeight: 600,
                              background: plan.status === 'completed' ? 'rgba(34,197,94,0.2)' : 'rgba(234,179,8,0.2)',
                              color: plan.status === 'completed' ? '#4ade80' : '#facc15',
                            }}
                          >
                            {plan.status}
                          </span>
                          {plan.variant_id && (
                            <a
                              href={downloadClipUrl(clip.id)}
                              download
                              data-testid={`btn-download-dubbed-${plan.id}`}
                              style={{
                                color: '#c084fc', textDecoration: 'none', fontSize: 11, cursor: 'pointer'
                              }}
                              title="Download Dubbed Video"
                            >
                              ⬇️
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
            <a href={downloadClipUrl(clip.id)} download
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                padding: '10px 14px', borderRadius: 10, background: 'rgba(99,102,241,0.18)',
                border: '1px solid rgba(99,102,241,0.4)', color: '#a5b4fc',
                fontWeight: 600, fontSize: 13, textDecoration: 'none',
              }}>⬇️ Download MP4</a>
            {clip.publish_status !== 'published' && (
              <a href={`/publish?clip=${clip.id}`}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  padding: '10px 14px', borderRadius: 10,
                  background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                  color: '#fff', fontWeight: 600, fontSize: 13, textDecoration: 'none',
                }}>🚀 Publish to YouTube Shorts</a>
            )}
            <button onClick={onClose}
              style={{
                padding: '8px 14px', borderRadius: 10, background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)',
                fontWeight: 500, fontSize: 12, cursor: 'pointer',
              }}>✕ Close</button>
          </div>
        </div>
      </div>
    </div>
  );
}


// ── Toolbar pill button ──────────────────────────────────────────────────────
function Pill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} style={{
      padding: '6px 14px', borderRadius: 20, border: '1px solid',
      fontSize: 12, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s',
      background: active ? 'rgba(99,102,241,0.18)' : 'transparent',
      borderColor: active ? 'var(--accent)' : 'var(--border)',
      color: active ? 'var(--accent)' : 'var(--text-secondary)',
    }}>{children}</button>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────
export default function ClipsPage() {
  const [clips, setClips]             = useState<any[]>([]);
  const [loading, setLoading]         = useState(true);
  const [filter, setFilter]           = useState<'all' | 'draft' | 'published'>('all');
  const [sortBy, setSortBy]           = useState<'score' | 'date' | 'duration'>('date');
  const [groupBySource, setGroupBySource] = useState(false);
  const [search, setSearch]           = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [imgErrors, setImgErrors]     = useState<Set<string>>(new Set());
  const [previewClip, setPreviewClip] = useState<any | null>(null);
  const [bulkActionRunning, setBulkActionRunning] = useState(false);
  const [bulkActionProgress, setBulkActionProgress] = useState<string | null>(null);
  
  const [cleanupPreview, setCleanupPreview] = useState<CleanupPreviewResponse | null>(null);
  const [cleanupResult, setCleanupResult] = useState<CleanupExecuteResponse | null>(null);
  const [cleanupError, setCleanupError] = useState<string | null>(null);
  const [cleaning, setCleaning] = useState(false);

  const handlePreviewCleanup = async () => {
    try {
      setCleaning(true);
      setCleanupError(null);
      setCleanupResult(null);
      const res = await previewCleanup(5.0);
      setCleanupPreview(res);
    } catch (e: any) {
      alert(`Failed to preview cleanup: ${e?.message || e}`);
    } finally {
      setCleaning(false);
    }
  };

  const handleExecuteCleanup = async () => {
    if (!cleanupPreview) return;
    const candidateIds = cleanupPreview.candidates.map(c => c.clip_id);
    if (candidateIds.length === 0) {
      alert('No eligible low-score candidates with physical files to clean up.');
      return;
    }
    if (!confirm(`Are you sure you want to clean up ${candidateIds.length} eligible clip(s) and reclaim ~${cleanupPreview.reclaimable_human}? This action safely stages files to quarantine before irreversible deletion.`)) {
      return;
    }
    try {
      setCleaning(true);
      setCleanupError(null);
      const res = await executeCleanup({
        preview_token: cleanupPreview.preview_token,
        candidate_clip_ids: candidateIds,
        purge_missing_media: false,
      });
      setCleanupResult(res);
      load();
    } catch (e: any) {
      setCleanupError(e?.message || 'Failed to execute cleanup');
    } finally {
      setCleaning(false);
    }
  };

  const parseUTC = (dateStr: string) => {
    if (!dateStr) return new Date(0);
    const cleanStr = (dateStr.endsWith('Z') || dateStr.includes('+') || (dateStr.slice(10).includes('-')))
      ? dateStr
      : dateStr + 'Z';
    return new Date(cleanStr);
  };

  const load = () => {
    setLoading(true);
    listClips()
      .then(data => { setClips(data); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this clip?')) return;
    await deleteClip(id);
    setClips(c => c.filter(x => x.id !== id));
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const handleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedIds.size === processed.length) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(processed.map(c => c.id)));
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0 || bulkActionRunning) return;
    if (!confirm(`Delete ${selectedIds.size} selected clip${selectedIds.size > 1 ? 's' : ''}? This action cannot be undone.`)) return;
    setBulkActionRunning(true);
    let count = 0;
    try {
      for (const id of Array.from(selectedIds)) {
        count++;
        setBulkActionProgress(`Deleting clip ${count} of ${selectedIds.size}...`);
        try {
          await deleteClip(id);
        } catch (err) {
          console.error('Bulk delete failed for', id, err);
        }
      }
      setClips(c => c.filter(x => !selectedIds.has(x.id)));
      setSelectedIds(new Set());
    } finally {
      setBulkActionRunning(false);
      setBulkActionProgress(null);
    }
  };

  const handleBulkPublish = async () => {
    if (selectedIds.size === 0 || bulkActionRunning) return;
    if (!confirm(`Publish ${selectedIds.size} selected clip${selectedIds.size > 1 ? 's' : ''}?`)) return;
    setBulkActionRunning(true);
    const failed: string[] = [];
    let count = 0;
    try {
      for (const id of Array.from(selectedIds)) {
        count++;
        setBulkActionProgress(`Publishing clip ${count} of ${selectedIds.size}...`);
        try {
          await publishNow({ clip_id: id });
        } catch (err) {
          failed.push(id);
        }
      }
      if (failed.length > 0) {
        alert(`${failed.length} clip${failed.length > 1 ? 's' : ''} failed to publish.`);
      }
      setSelectedIds(new Set());
      await load();
    } finally {
      setBulkActionRunning(false);
      setBulkActionProgress(null);
    }
  };

  // ── derived list ─────────────────────────────────────────────────────────
  let processed = [...clips];

  // 1. status filter
  if (filter !== 'all') processed = processed.filter(c => c.publish_status === filter);

  // 2. search
  if (search.trim()) {
    const q = search.toLowerCase();
    processed = processed.filter(c =>
      c.title?.toLowerCase().includes(q) ||
      c.source_title?.toLowerCase().includes(q)
    );
  }

  // 3. sort
  processed.sort((a, b) => {
    if (sortBy === 'score')    return b.score - a.score;
    if (sortBy === 'duration') return b.duration - a.duration;
    // date
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  // ── group by source video ─────────────────────────────────────────────────
  let grouped: Record<string, any[]> = {};
  if (!groupBySource) {
    grouped = { 'All Clips': processed };
  } else {
    grouped = processed.reduce<Record<string, any[]>>((acc, c) => {
      const key = c.source_title || 'Unknown Source';
      (acc[key] = acc[key] || []).push(c);
      return acc;
    }, {});
  }

  const formatDuration = (s: number) => `${Math.floor(s)}s`;
  const formatDate     = (s: string) => {
    if (!s) return '—';
    return new Date(s).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  };

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <>
      {previewClip && <PreviewModal clip={previewClip} onClose={() => setPreviewClip(null)} onRestyled={load} />}

      {cleanupPreview && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1100,
          background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 16
        }}>
          <div style={{
            background: '#16161f', padding: 28, borderRadius: 20,
            maxWidth: 540, width: '100%', border: '1px solid rgba(255,255,255,0.12)',
            boxShadow: '0 24px 60px rgba(0,0,0,0.8)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h2 style={{ fontSize: 20, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                🧹 Safe Storage Cleanup
              </h2>
              <button
                onClick={() => { setCleanupPreview(null); setCleanupResult(null); setCleanupError(null); }}
                className="btn-ghost"
                style={{ padding: '4px 10px', fontSize: 13, borderRadius: 8 }}
                disabled={cleaning}
              >✕</button>
            </div>

            {cleanupResult ? (
              <div>
                <div style={{
                  padding: 16, background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)',
                  borderRadius: 12, marginBottom: 20
                }}>
                  <div style={{ color: '#10b981', fontWeight: 700, fontSize: 15, marginBottom: 4 }}>
                    ✅ Storage Successfully Reclaimed!
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    Physical files were safely staged to quarantine and purged with durable journaling.
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
                  <div style={{ background: 'rgba(255,255,255,0.04)', padding: 12, borderRadius: 10 }}>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Confirmed Reclaimed</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#38bdf8' }}>{cleanupResult.summary.confirmed_reclaimed_human}</div>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.04)', padding: 12, borderRadius: 10 }}>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Files Purged</div>
                    <div style={{ fontSize: 18, fontWeight: 700 }}>{cleanupResult.summary.purged_physical_files}</div>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.04)', padding: 12, borderRadius: 10 }}>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Clip Records Deleted</div>
                    <div style={{ fontSize: 18, fontWeight: 700 }}>{cleanupResult.summary.deleted_clip_records}</div>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.04)', padding: 12, borderRadius: 10 }}>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Shared Files Retained</div>
                    <div style={{ fontSize: 18, fontWeight: 700 }}>{cleanupResult.summary.shared_files_retained}</div>
                  </div>
                </div>

                <button
                  onClick={() => { setCleanupPreview(null); setCleanupResult(null); }}
                  className="btn-primary"
                  style={{ width: '100%', padding: '10px 16px', fontSize: 14 }}
                >Done</button>
              </div>
            ) : (
              <div>
                <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 20 }}>
                  Prune unneeded draft clips with score &lt; 5.0 to recover disk space without impacting published videos.
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 18 }}>
                  <div style={{ background: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.25)', padding: 14, borderRadius: 12 }}>
                    <div style={{ fontSize: 11, color: '#38bdf8', fontWeight: 600 }}>Estimated Space Reclaim</div>
                    <div style={{ fontSize: 22, fontWeight: 800, color: '#38bdf8', marginTop: 4 }}>
                      {cleanupPreview.reclaimable_human}
                    </div>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', padding: 14, borderRadius: 12 }}>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>Eligible Candidates</div>
                    <div style={{ fontSize: 22, fontWeight: 800, marginTop: 4 }}>
                      {cleanupPreview.candidates.length}
                    </div>
                  </div>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', padding: 14, borderRadius: 12, marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Candidate Breakdown:</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
                    <span>Low Score Clips (&lt; 5.0 with physical media):</span>
                    <strong style={{ color: 'var(--text-primary)' }}>{cleanupPreview.counts.low_score}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-secondary)' }}>
                    <span>Unavailable Media (Retained by default):</span>
                    <strong style={{ color: 'var(--text-primary)' }}>{cleanupPreview.counts.unavailable}</strong>
                  </div>
                </div>

                <div style={{ background: 'rgba(99, 102, 241, 0.08)', border: '1px solid rgba(99, 102, 241, 0.25)', padding: 12, borderRadius: 10, marginBottom: 16 }}>
                  <div style={{ fontSize: 11, color: '#a5b4fc', fontWeight: 600, marginBottom: 4 }}>🛡️ Protection Active:</div>
                  <div style={{ fontSize: 11, color: '#c7d2fe', lineHeight: 1.5 }}>
                    {cleanupPreview.protected_counts.published} published · {cleanupPreview.protected_counts.high_score} high-score (≥5.0) · {cleanupPreview.protected_counts.active_jobs} active pipeline jobs · {cleanupPreview.protected_counts.active_reservations} reservations
                  </div>
                </div>

                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 20 }}>
                  🔒 Cryptographic preview token lease active (15-min). Operates via staged quarantine with deterministic crash-rollback protection.
                </div>

                {cleanupError && (
                  <div style={{ padding: 12, background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 10, color: '#ef4444', fontSize: 12, marginBottom: 16 }}>
                    ⚠️ {cleanupError}
                  </div>
                )}

                <div style={{ display: 'flex', gap: 12 }}>
                  <button
                    onClick={() => { setCleanupPreview(null); setCleanupError(null); }}
                    className="btn-ghost"
                    disabled={cleaning}
                    style={{ flex: 1, padding: '10px 14px' }}
                  >Cancel</button>
                  <button
                    onClick={handleExecuteCleanup}
                    className="btn-danger"
                    disabled={cleaning || cleanupPreview.candidates.length === 0}
                    style={{ flex: 1.4, padding: '10px 14px', fontWeight: 600 }}
                  >
                    {cleaning ? '⏳ Cleaning...' : `Confirm Cleanup (${cleanupPreview.candidates.length})`}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="animate-fade-up">
        {/* Header */}
      <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, fontFamily: "'Space Grotesk', sans-serif" }}>
            🎬 Clips Library
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>
            {clips.length} clips generated · AI-scored and ready to publish · 9:16 portrait format
          </p>
        </div>
        <button onClick={handlePreviewCleanup} className="btn-danger" style={{ padding: '8px 16px', fontSize: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
          {cleaning ? '⏳' : '🧹'} Safe Cleanup
        </button>
      </div>

      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center',
        marginBottom: 24,
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid var(--border)',
        borderRadius: 14, padding: '12px 16px',
      }}>
        {/* Search */}
        <div style={{ position: 'relative', flex: '1 1 200px', minWidth: 180 }}>
          <span style={{
            position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            fontSize: 14, color: 'var(--text-muted)', pointerEvents: 'none',
          }}>🔍</span>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by title or source…"
            style={{
              width: '100%', paddingLeft: 32, paddingRight: 12,
              height: 34, borderRadius: 8,
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)', fontSize: 13, outline: 'none',
              boxSizing: 'border-box',
            }}
          />
        </div>

        <div style={{ width: 1, height: 24, background: 'var(--border)' }} />

        {/* Status filter */}
        <div style={{ display: 'flex', gap: 6 }}>
          {(['all', 'draft', 'published'] as const).map(f => (
            <Pill key={f} active={filter === f} onClick={() => setFilter(f)}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Pill>
          ))}
        </div>

        <div style={{ width: 1, height: 24, background: 'var(--border)' }} />

        {/* Sort */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: 0.5 }}>SORT</span>
          {(['score', 'date', 'duration'] as const).map(s => (
            <Pill key={s} active={sortBy === s} onClick={() => setSortBy(s)}>
              {s === 'score' ? '⭐ Score' : s === 'date' ? '📅 Date' : '⏱ Duration'}
            </Pill>
          ))}
        </div>

        <div style={{ width: 1, height: 24, background: 'var(--border)' }} />

        {/* Group toggle */}
        <Pill active={groupBySource} onClick={() => setGroupBySource(v => !v)}>
          📁 Group by Source
        </Pill>

        {selectedIds.size > 0 ? (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {selectedIds.size} selected
            </span>
            {bulkActionProgress && (
              <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>
                ⏳ {bulkActionProgress}
              </span>
            )}
            <button
              onClick={handleBulkPublish}
              disabled={bulkActionRunning}
              className="btn-primary"
              style={{ padding: '8px 12px', fontSize: 12, opacity: bulkActionRunning ? 0.6 : 1 }}
            >
              {bulkActionRunning ? '...' : '🚀 Publish'}
            </button>
            <button
              onClick={handleBulkDelete}
              disabled={bulkActionRunning}
              className="btn-danger"
              style={{ padding: '8px 12px', fontSize: 12, opacity: bulkActionRunning ? 0.6 : 1 }}
            >
              {bulkActionRunning ? '...' : '🗑 Delete'}
            </button>
            <button
              onClick={() => setSelectedIds(new Set())}
              disabled={bulkActionRunning}
              className="btn-ghost"
              style={{ padding: '8px 12px', fontSize: 12 }}
            >
              ✕ Clear
            </button>
          </div>
        ) : (
          <button onClick={handleSelectAll} disabled={bulkActionRunning} className="btn-ghost" style={{ padding: '8px 12px', fontSize: 12 }}>
            {selectedIds.size === processed.length ? '☐' : '☑'} Select all
          </button>
        )}

        {/* Result count */}
        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
          {processed.length} clip{processed.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* ── Content ─────────────────────────────────────────────────────── */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16 }}>
          {[...Array(6)].map((_, i) => (
            <div key={i} className="clip-card" style={{ padding: 0 }}>
              <div className="skeleton" style={{ height: 200 }} />
              <div style={{ padding: 14 }}>
                <div className="skeleton" style={{ height: 14, marginBottom: 8, width: '80%' }} />
                <div className="skeleton" style={{ height: 12, width: '50%' }} />
              </div>
            </div>
          ))}
        </div>
      ) : processed.length === 0 ? (
        <div className="glass" style={{ padding: 60, textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>{search ? '🔍' : '✂️'}</div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>
            {search ? 'No clips match your search' : 'No clips yet'}
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
            {search ? 'Try a different keyword or clear the search.' : 'Process a video from the dashboard to generate clips.'}
          </p>
          {!search && <Link href="/" className="btn-primary">Go to Dashboard →</Link>}
          {search  && <button onClick={() => setSearch('')} className="btn-primary">Clear Search</button>}
        </div>
      ) : (
        Object.entries(grouped).map(([group, groupClips]) => (
          <div key={group} style={{ marginBottom: groupBySource ? 36 : 0 }}>
            {/* Group header — only show when grouping is on */}
            {groupBySource && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                marginBottom: 14,
              }}>
                <div style={{
                  fontSize: 13, fontWeight: 700, color: 'var(--text-primary)',
                  fontFamily: "'Space Grotesk', sans-serif",
                  maxWidth: 420, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  📁 {group}
                </div>
                <div style={{
                  fontSize: 11, color: 'var(--text-muted)',
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid var(--border)',
                  borderRadius: 20, padding: '2px 10px',
                }}>
                  {groupClips.length} clip{groupClips.length !== 1 ? 's' : ''}
                </div>
                <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
              </div>
            )}

            {/* Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16 }}>
              {groupClips.map(clip => {
                const sl = SCORE_LABEL(clip.score);
                return (
                  <div key={clip.id} className="clip-card" data-testid={`clip-card-${clip.id}`}>
                    {/* Thumbnail */}
                    <div
                      data-testid={`clip-thumbnail-${clip.id}`}
                      onClick={() => setPreviewClip(clip)}
                      style={{
                        position: 'relative', aspectRatio: '9 / 16',
                        background: 'var(--bg-secondary)',
                        overflow: 'hidden', cursor: 'pointer', maxHeight: 340,
                      }}
                    >
                      {!imgErrors.has(clip.id) ? (
                        <img
                          src={thumbnailUrl(clip.id)}
                          alt={clip.title}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          onError={() => setImgErrors(s => new Set([...s, clip.id]))}
                        />
                      ) : (
                        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                          <div style={{ fontSize: 32, marginBottom: 8 }}>⚠️</div>
                          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: 0.5 }}>MEDIA MISSING</div>
                        </div>
                      )}

                      {/* Play overlay */}
                      <div style={{
                        position: 'absolute', inset: 0,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        background: 'rgba(0,0,0,0)', transition: 'background 0.2s',
                      }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.4)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'rgba(0,0,0,0)')}
                      >
                        <div style={{
                          width: 52, height: 52, borderRadius: '50%',
                          background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)',
                          border: '2px solid rgba(255,255,255,0.4)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 20, transition: 'transform 0.15s',
                        }}>▶️</div>
                      </div>

                      {/* Overlay badges */}
                      <div style={{ position: 'absolute', top: 8, left: 8, zIndex: 5, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <label
                          onClick={e => e.stopPropagation()}
                          style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(0,0,0,0.6)', borderRadius: 999, padding: '4px 8px', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={selectedIds.has(clip.id)}
                            onChange={e => { e.stopPropagation(); handleSelect(clip.id); }}
                            style={{ width: 14, height: 14, accentColor: '#8b5cf6' }}
                          />
                          <ScoreRing score={clip.score} />
                        </label>
                        {clip.created_at && (Date.now() - parseUTC(clip.created_at).getTime()) < 3600000 && (
                          <span style={{
                            background: 'linear-gradient(135deg, #10b981, #059669)',
                            color: '#fff',
                            padding: '2px 8px',
                            borderRadius: 6,
                            fontSize: 9,
                            fontWeight: 800,
                            boxShadow: '0 2px 8px rgba(16, 185, 129, 0.4)',
                            letterSpacing: '0.05em',
                          }}>NEW</span>
                        )}
                      </div>
                      <div style={{ position: 'absolute', top: 8, right: 8 }}>
                        <span className="badge badge-muted" style={{ fontSize: 10 }}>
                          {formatDuration(clip.duration)}
                        </span>
                      </div>
                      {/* Score label ribbon */}
                      <div style={{
                        position: 'absolute', bottom: 36, left: 8,
                        background: `${sl.color}22`,
                        border: `1px solid ${sl.color}55`,
                        borderRadius: 20,
                        padding: '2px 8px', fontSize: 10, fontWeight: 700, color: sl.color,
                      }}>{sl.label}</div>
                      <div style={{ position: 'absolute', bottom: 8, left: 8 }}>
                        <span className={`badge ${STATUS_COLORS[clip.publish_status] || 'badge-muted'}`} style={{ fontSize: 10 }}>
                          {clip.publish_status}
                        </span>
                      </div>
                      <div style={{ position: 'absolute', bottom: 8, right: 8 }}>
                        <span className="badge badge-muted" style={{ fontSize: 10, background: 'rgba(0,0,0,0.6)' }}>9:16</span>
                      </div>
                    </div>

                    {/* Info */}
                    <div style={{ padding: '14px 16px' }}>
                      <h3
                        data-testid={`clip-title-${clip.id}`}
                        onClick={() => setPreviewClip(clip)}
                        style={{
                          fontSize: 13, fontWeight: 600, marginBottom: 2, lineHeight: 1.4,
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                          cursor: 'pointer',
                        }}>{clip.title}</h3>
                      {clip.source_title && !groupBySource && (
                        <p style={{
                          fontSize: 10, color: 'var(--text-muted)', marginBottom: 2,
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        }}>📁 {clip.source_title}</p>
                      )}
                      <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
                        {clip.start_time?.toFixed(1)}s – {clip.end_time?.toFixed(1)}s · {formatDate(clip.created_at)}
                      </p>

                      {/* Actions */}
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          onClick={() => setPreviewClip(clip)}
                          className="btn-ghost"
                          style={{ flex: 1, justifyContent: 'center', fontSize: 12, padding: '7px 8px' }}
                        >▶ Preview</button>
                        <a href={downloadClipUrl(clip.id)} download
                          className="btn-ghost"
                          style={{ flex: 1, justifyContent: 'center', fontSize: 12, padding: '7px 8px' }}>
                          ⬇️ Save
                        </a>
                        {clip.publish_status !== 'published' && (
                          <a href={`/publish?clip=${clip.id}`}
                            className="btn-primary"
                            style={{ flex: 1, justifyContent: 'center', fontSize: 12, padding: '7px 8px' }}>
                            🚀
                          </a>
                        )}
                        <button onClick={() => handleDelete(clip.id)} className="btn-danger" style={{ padding: '7px 10px', fontSize: 13 }}>🗑</button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))
      )}
      </div>
    </>
  );
}
