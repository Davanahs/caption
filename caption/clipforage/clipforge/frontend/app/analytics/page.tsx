'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  getPipelineSummary,
  getABTests,
  getChannelInsights,
  listClips,
  getVideoAnalytics,
  getSEOAnalysis,
  getOptimizationLog,
  setAutoOptimizeFlag,
  triggerOptimizer,
  getActiveTrackers,
  startTracker,
  cancelTracker,
  VideoAnalyticsResponse,
  SEOAnalysisResponse,
  OptimizationLogResponse,
  ActiveTracker,
} from '@/lib/api';

export default function AnalyticsPage() {
  // Aggregate states
  const [summary, setSummary] = useState<any>(null);
  const [abTests, setAbTests] = useState<any[]>([]);
  const [insights, setInsights] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState('');

  // Per-video analytics states
  const [clips, setClips] = useState<any[]>([]);
  const [selectedClipId, setSelectedClipId] = useState<string>('');
  const [videoAnalytics, setVideoAnalytics] = useState<VideoAnalyticsResponse | null>(null);
  const [seoAnalysis, setSeoAnalysis] = useState<SEOAnalysisResponse | null>(null);
  const [optLog, setOptLog] = useState<OptimizationLogResponse | null>(null);
  const [loadingPerVideo, setLoadingPerVideo] = useState<boolean>(false);
  const [perVideoError, setPerVideoError] = useState<string>('');
  const [isAutoOptimizing, setIsAutoOptimizing] = useState<boolean>(true);

  // Active trackers states
  const [activeTrackers, setActiveTrackers] = useState<ActiveTracker[]>([]);
  const [actionLoading, setActionLoading] = useState<string>('');
  const [actionMessage, setActionMessage] = useState<string>('');

  // Load Aggregate Telemetry & Clips List
  const loadAggregateData = useCallback(async () => {
    try {
      const [sum, ab, ins, clipsData, trackersData] = await Promise.all([
        getPipelineSummary().catch(() => null),
        getABTests().catch(() => []),
        getChannelInsights().catch(() => null),
        listClips().catch(() => []),
        getActiveTrackers().catch(() => ({ active_trackers: [] })),
      ]);
      if (sum) setSummary(sum);
      setAbTests(ab || []);
      if (ins) setInsights(ins);
      if (Array.isArray(clipsData)) {
        setClips(clipsData);
        // Default to first clip if none currently selected
        if (!selectedClipId && clipsData.length > 0) {
          setSelectedClipId(clipsData[0].id);
        }
      }
      if (trackersData && Array.isArray(trackersData.active_trackers)) {
        setActiveTrackers(trackersData.active_trackers);
      }
      setError('');
    } catch (err: any) {
      setError(err.message || 'Failed to load pipeline summary');
    } finally {
      setLoading(false);
    }
  }, [selectedClipId]);

  // Load Details for Selected Clip
  const loadClipAnalytics = useCallback(async (clipId: string) => {
    if (!clipId) return;
    setLoadingPerVideo(true);
    setPerVideoError('');
    try {
      const [analyticsData, seoData, logData] = await Promise.all([
        getVideoAnalytics(clipId).catch(() => null),
        getSEOAnalysis(clipId).catch(() => null),
        getOptimizationLog(clipId).catch(() => null),
      ]);
      setVideoAnalytics(analyticsData);
      setSeoAnalysis(seoData);
      setOptLog(logData);
    } catch (err: any) {
      setPerVideoError(err.message || 'Failed to fetch detailed metrics for this clip');
    } finally {
      setLoadingPerVideo(false);
    }
  }, []);

  // Trigger clip load whenever selectedClipId changes
  useEffect(() => {
    if (selectedClipId) {
      loadClipAnalytics(selectedClipId);
    }
  }, [selectedClipId, loadClipAnalytics]);

  // Initial mount & recurring polling interval (15s)
  useEffect(() => {
    const timer = setTimeout(loadAggregateData, 0);
    const interval = setInterval(loadAggregateData, 15000);
    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [loadAggregateData]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await loadAggregateData();
      if (selectedClipId) {
        await loadClipAnalytics(selectedClipId);
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  // Selected clip object helper
  const selectedClip = clips.find((c) => c.id === selectedClipId) || null;

  // Toggle Auto-Optimize Flag
  const handleToggleAutoOptimize = async () => {
    if (!selectedClipId) return;
    const targetState = !isAutoOptimizing;
    setActionLoading('toggling-auto-opt');
    setActionMessage('');
    try {
      const res = await setAutoOptimizeFlag(selectedClipId, targetState);
      setIsAutoOptimizing(targetState);
      setActionMessage(`✓ Auto-optimization ${targetState ? 'enabled' : 'disabled'}`);
      setTimeout(() => setActionMessage(''), 4000);
    } catch (err: any) {
      setActionMessage(`❌ Failed to update flag: ${err.message || 'Server error'}`);
    } finally {
      setActionLoading('');
    }
  };

  // Trigger Manual Optimization
  const handleTriggerOptimizer = async () => {
    if (!selectedClipId) return;
    setActionLoading('triggering-opt');
    setActionMessage('');
    try {
      const ytId = selectedClip?.youtube_short_id || '';
      const res = await triggerOptimizer(selectedClipId, ytId);
      setActionMessage(`✓ ${res.message || 'Optimization pass scheduled'}`);
      // Refresh optimization log & SEO
      await loadClipAnalytics(selectedClipId);
      setTimeout(() => setActionMessage(''), 5000);
    } catch (err: any) {
      setActionMessage(`❌ Optimization error: ${err.message || 'Check logs'}`);
    } finally {
      setActionLoading('');
    }
  };

  // Start Performance Tracking
  const handleStartTracker = async () => {
    if (!selectedClipId) return;
    setActionLoading('starting-tracker');
    setActionMessage('');
    try {
      const ytId = selectedClip?.youtube_short_id || '';
      const res = await startTracker(selectedClipId, ytId);
      setActionMessage(`✓ Tracking started (Task ID: ${res.task_id.slice(0, 8)}...)`);
      const trackersData = await getActiveTrackers().catch(() => ({ active_trackers: [] }));
      setActiveTrackers(trackersData.active_trackers || []);
      setTimeout(() => setActionMessage(''), 5000);
    } catch (err: any) {
      setActionMessage(`❌ Tracker error: ${err.message || 'Failed to start'}`);
    } finally {
      setActionLoading('');
    }
  };

  // Cancel Active Tracker
  const handleCancelTracker = async (taskId: string) => {
    setActionLoading(`cancelling-${taskId}`);
    try {
      await cancelTracker(taskId);
      setActiveTrackers((prev) => prev.filter((t) => t.task_id !== taskId));
      setActionMessage(`✓ Tracker ${taskId.slice(0, 8)}... cancelled`);
      setTimeout(() => setActionMessage(''), 4000);
    } catch (err: any) {
      setActionMessage(`❌ Failed to cancel tracker: ${err.message || 'Error'}`);
    } finally {
      setActionLoading('');
    }
  };

  return (
    <div className="animate-fade-up" style={{ maxWidth: 1240, margin: '0 auto', color: 'var(--text-primary)' }}>
      {/* Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0, letterSpacing: '-0.5px' }}>
            Pipeline & Video Analytics Dashboard
          </h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: 4, fontSize: 14 }}>
            Real-time telemetry, per-video performance tracking, SEO intelligence, and AI auto-optimization
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          aria-label="Refresh metrics data"
          data-testid="btn-refresh-metrics"
          className="btn-secondary"
          style={{
            padding: '10px 18px',
            borderRadius: 8,
            cursor: isRefreshing ? 'not-allowed' : 'pointer',
            fontWeight: 600,
            fontSize: 13,
            transition: 'all 0.2s',
            opacity: isRefreshing ? 0.6 : 1,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          {isRefreshing ? '⏳ Refreshing...' : '🔄 Refresh Metrics'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '14px 18px', backgroundColor: '#450a0a', border: '1px solid #991b1b', borderRadius: 8, color: '#fca5a5', marginBottom: 24 }}>
          ⚠️ {error}
        </div>
      )}

      {loading && !summary ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: '#64748b' }}>
          Loading pipeline telemetry...
        </div>
      ) : (
        <>
          {/* Top Aggregate Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))', gap: 20, marginBottom: 28 }}>
            {/* Card 1: Pipeline Health */}
            <div className="glass" style={{ borderRadius: 12, padding: 22 }}>
              <div style={{ fontSize: 13, color: '#38bdf8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                ⚡ Engine Performance
              </div>
              <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--text-primary)' }}>
                {summary?.pipeline?.successful_phases || 0}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                Successful Execution Phases
              </div>
              <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span style={{ color: 'var(--text-muted)' }}>Avg Phase Speed:</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{summary?.pipeline?.avg_phase_duration_ms || 0} ms</span>
              </div>
            </div>

            {/* Card 2: Auto-Optimizer */}
            <div className="glass" style={{ borderRadius: 12, padding: 22 }}>
              <div style={{ fontSize: 13, color: '#c084fc', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                🤖 AI Auto-Optimizer
              </div>
              <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--text-primary)' }}>
                {summary?.optimizer?.total_optimization_attempts || 0}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                Optimization Runs Completed
              </div>
              <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span style={{ color: 'var(--text-muted)' }}>Active Tracking Queue:</span>
                <span style={{ fontWeight: 600, color: '#34d399' }}>{summary?.tracking?.active_videos || activeTrackers.length} videos</span>
              </div>
            </div>

            {/* Card 3: A/B Experiments */}
            <div className="glass" style={{ borderRadius: 12, padding: 22 }}>
              <div style={{ fontSize: 13, color: '#fbbf24', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                🧪 A/B Title Experiments
              </div>
              <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--text-primary)' }}>
                {abTests.length}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                Active / Completed Title Tests
              </div>
              <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span style={{ color: 'var(--text-muted)' }}>Swapped for Lift:</span>
                <span style={{ fontWeight: 600, color: '#fbbf24' }}>
                  {abTests.filter((t) => t.status === 'swapped' || t.winner_variant === 'B').length}
                </span>
              </div>
            </div>

            {/* Card 4: SEO Health */}
            <div className="glass" style={{ borderRadius: 12, padding: 22 }}>
              <div style={{ fontSize: 13, color: '#34d399', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                📈 Overall SEO Intelligence
              </div>
              <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--text-primary)' }}>
                {summary?.seo?.avg_seo_score || 0}
                <span style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-secondary)', marginLeft: 4 }}>/ 100</span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                Average SEO Virality Score
              </div>
              <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span style={{ color: 'var(--text-muted)' }}>Avg CTR Score:</span>
                <span style={{ fontWeight: 600, color: '#38bdf8' }}>{summary?.seo?.avg_ctr_score || 0} / 100</span>
              </div>
            </div>
          </div>

          {/* ══════════════════════════════════════════════════════════════════════
              CF-DEF-005: Per-Video Performance & SEO Cards Drilldown Section
              ══════════════════════════════════════════════════════════════════════ */}
          <div className="glass" style={{ borderRadius: 14, padding: 26, marginBottom: 28, border: '1px solid rgba(56, 189, 248, 0.25)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: 19, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span>🎬</span> Per-Video Performance & SEO Intelligence
                </h2>
                <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0 0', fontSize: 13 }}>
                  Select any video clip to inspect view score trends, granular SEO keyword tags, and auto-optimization history
                </p>
              </div>

              {/* Clip Selector Dropdown */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', maxWidth: 420, minWidth: 0, flexWrap: 'wrap' }}>
                <label htmlFor="select-clip" style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 600, whiteSpace: 'nowrap' }}>
                  Target Clip:
                </label>
                <select
                  id="select-clip"
                  data-testid="select-video-analytics"
                  value={selectedClipId}
                  onChange={(e) => setSelectedClipId(e.target.value)}
                  style={{
                    flex: 1,
                    minWidth: 0,
                    width: '100%',
                    maxWidth: '100%',
                    padding: '9px 14px',
                    borderRadius: 8,
                    background: 'rgba(15, 23, 42, 0.7)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                    fontWeight: 500,
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {clips.length === 0 ? (
                    <option value="">No clips found</option>
                  ) : (
                    clips.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.title ? (c.title.length > 40 ? c.title.slice(0, 40) + '...' : c.title) : 'Untitled Clip'} ({c.duration ? `${c.duration.toFixed(0)}s` : '0s'})
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>

            {/* Action Feedback Banner */}
            {actionMessage && (
              <div style={{
                padding: '10px 16px',
                borderRadius: 8,
                background: actionMessage.startsWith('✓') ? 'rgba(52, 211, 153, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                border: `1px solid ${actionMessage.startsWith('✓') ? 'rgba(52, 211, 153, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
                color: actionMessage.startsWith('✓') ? '#34d399' : '#f87171',
                fontSize: 13,
                marginBottom: 18,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}>
                {actionMessage}
              </div>
            )}

            {perVideoError && (
              <div style={{ padding: '10px 16px', backgroundColor: '#450a0a', border: '1px solid #991b1b', borderRadius: 8, color: '#fca5a5', marginBottom: 18, fontSize: 13 }}>
                ⚠️ {perVideoError}
              </div>
            )}

            {/* Selected Clip Quick Info & Controls Bar */}
            {selectedClip && (
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 14,
                padding: '14px 18px',
                borderRadius: 10,
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.07)',
                marginBottom: 22,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>
                    {selectedClip.title || 'Untitled Clip'}
                  </div>
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 600,
                    background: selectedClip.publish_status === 'published' ? 'rgba(52, 211, 153, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                    color: selectedClip.publish_status === 'published' ? '#34d399' : '#94a3b8',
                    border: `1px solid ${selectedClip.publish_status === 'published' ? 'rgba(52, 211, 153, 0.3)' : 'rgba(148, 163, 184, 0.3)'}`,
                  }}>
                    {selectedClip.publish_status ? selectedClip.publish_status.toUpperCase() : 'DRAFT'}
                  </span>
                  {selectedClip.youtube_short_id && (
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      Short ID: <code style={{ color: '#38bdf8' }}>{selectedClip.youtube_short_id}</code>
                    </span>
                  )}
                </div>

                {/* Video Optimization Controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <button
                    onClick={handleToggleAutoOptimize}
                    disabled={actionLoading === 'toggling-auto-opt'}
                    data-testid="toggle-auto-optimize"
                    className="btn-secondary"
                    style={{
                      padding: '7px 14px',
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                      background: isAutoOptimizing ? 'rgba(52, 211, 153, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                      border: `1px solid ${isAutoOptimizing ? 'rgba(52, 211, 153, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
                      color: isAutoOptimizing ? '#34d399' : '#f87171',
                    }}
                  >
                    {actionLoading === 'toggling-auto-opt' ? 'Updating...' : isAutoOptimizing ? '🤖 Auto-Optimize: ON' : '⏸ Auto-Optimize: OFF'}
                  </button>

                  <button
                    onClick={handleTriggerOptimizer}
                    disabled={actionLoading === 'triggering-opt'}
                    data-testid="btn-trigger-optimize"
                    className="btn-secondary"
                    style={{
                      padding: '7px 14px',
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                      background: 'rgba(192, 132, 252, 0.15)',
                      border: '1px solid rgba(192, 132, 252, 0.4)',
                      color: '#c084fc',
                    }}
                  >
                    {actionLoading === 'triggering-opt' ? '⏳ Optimizing...' : '⚡ Optimize Now'}
                  </button>

                  <button
                    onClick={handleStartTracker}
                    disabled={actionLoading === 'starting-tracker'}
                    data-testid="btn-start-tracking"
                    className="btn-secondary"
                    style={{
                      padding: '7px 14px',
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                      background: 'rgba(56, 189, 248, 0.15)',
                      border: '1px solid rgba(56, 189, 248, 0.4)',
                      color: '#38bdf8',
                    }}
                  >
                    {actionLoading === 'starting-tracker' ? '⏳ Starting...' : '📡 Track Performance'}
                  </button>
                </div>
              </div>
            )}

            {/* Drilldown Subsections */}
            {loadingPerVideo ? (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#64748b', fontSize: 14 }}>
                Loading granular metrics for selected clip...
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))', gap: 20 }}>
                {/* 1. Video Performance Telemetry Card */}
                <div data-testid="card-video-performance" className="glass" style={{ borderRadius: 12, padding: 20, background: 'rgba(255, 255, 255, 0.02)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span>📊</span> Performance & Engagement
                    </h3>
                    {videoAnalytics?.trend && (
                      <span style={{
                        padding: '3px 8px',
                        borderRadius: 6,
                        fontSize: 11,
                        fontWeight: 700,
                        background: videoAnalytics.trend === 'up' ? 'rgba(52, 211, 153, 0.15)' : videoAnalytics.trend === 'down' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                        color: videoAnalytics.trend === 'up' ? '#34d399' : videoAnalytics.trend === 'down' ? '#f87171' : '#94a3b8',
                      }}>
                        {videoAnalytics.trend === 'up' ? '📈 TRENDING UP' : videoAnalytics.trend === 'down' ? '📉 TRENDING DOWN' : '➖ STABLE'}
                      </span>
                    )}
                  </div>

                  {/* VSI Score & Key Metrics */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 80px), 1fr))', gap: 12, marginBottom: 16 }}>
                    <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255, 255, 255, 0.03)', textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>View Score</div>
                      <div style={{ fontSize: 22, fontWeight: 800, color: '#38bdf8', marginTop: 4 }}>
                        {videoAnalytics?.latest_score != null ? Number(videoAnalytics.latest_score).toFixed(1) : (selectedClip?.score ? Number(selectedClip.score).toFixed(1) : '—')}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>0-10 VSI</div>
                    </div>

                    <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255, 255, 255, 0.03)', textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Views Logged</div>
                      <div style={{ fontSize: 22, fontWeight: 800, color: '#34d399', marginTop: 4 }}>
                        {videoAnalytics?.snapshots?.[0]?.view_count ?? 0}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Latest poll</div>
                    </div>

                    <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255, 255, 255, 0.03)', textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Likes / Comments</div>
                      <div style={{ fontSize: 22, fontWeight: 800, color: '#fbbf24', marginTop: 4 }}>
                        {videoAnalytics?.snapshots?.[0]?.like_count ?? 0} / {videoAnalytics?.snapshots?.[0]?.comment_count ?? 0}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Engagement</div>
                    </div>
                  </div>

                  {/* Historical Snapshot Log */}
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    Telemetry Snapshots ({videoAnalytics?.snapshots?.length || 0} polls)
                  </div>
                  {videoAnalytics?.snapshots && videoAnalytics.snapshots.length > 0 ? (
                    <div style={{ maxHeight: 150, overflowY: 'auto', fontSize: 12 }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                        <thead>
                          <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                            <th style={{ padding: '6px 8px' }}>Time</th>
                            <th style={{ padding: '6px 8px' }}>Views</th>
                            <th style={{ padding: '6px 8px' }}>Likes</th>
                            <th style={{ padding: '6px 8px' }}>Score</th>
                          </tr>
                        </thead>
                        <tbody>
                          {videoAnalytics.snapshots.map((s, idx) => (
                            <tr key={s.id || idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                              <td style={{ padding: '6px 8px', color: 'var(--text-muted)' }}>
                                {s.fetched_at ? new Date(s.fetched_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
                              </td>
                              <td style={{ padding: '6px 8px' }}>{s.view_count}</td>
                              <td style={{ padding: '6px 8px' }}>{s.like_count}</td>
                              <td style={{ padding: '6px 8px', fontWeight: 600, color: '#38bdf8' }}>
                                {s.view_score != null ? Number(s.view_score).toFixed(1) : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ padding: '16px 0', textAlign: 'center', color: '#64748b', fontSize: 12, fontStyle: 'italic' }}>
                      No live telemetry recorded yet. Start tracking to collect 12-hour YouTube poll stats.
                    </div>
                  )}
                </div>

                {/* 2. SEO Cards & Keyword Intelligence */}
                <div data-testid="card-seo-analysis" className="glass" style={{ borderRadius: 12, padding: 20, background: 'rgba(255, 255, 255, 0.02)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span>🎯</span> SEO Analysis & Recommendation Cards
                    </h3>
                    {seoAnalysis?.latest_seo_score != null && (
                      <span style={{
                        padding: '3px 8px',
                        borderRadius: 6,
                        fontSize: 12,
                        fontWeight: 800,
                        background: 'rgba(52, 211, 153, 0.15)',
                        color: '#34d399',
                        border: '1px solid rgba(52, 211, 153, 0.3)',
                      }}>
                        SEO: {seoAnalysis.latest_seo_score} / 100
                      </span>
                    )}
                  </div>

                  {/* CTR & Discoverability Badges */}
                  <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: 100, padding: 10, borderRadius: 8, background: 'rgba(255, 255, 255, 0.03)', textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>CTR Score</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: '#38bdf8', marginTop: 2 }}>
                        {seoAnalysis?.latest_ctr_score != null ? `${seoAnalysis.latest_ctr_score}%` : '—'}
                      </div>
                    </div>
                    <div style={{ flex: 1, minWidth: 100, padding: 10, borderRadius: 8, background: 'rgba(255, 255, 255, 0.03)', textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Discoverability</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: '#c084fc', marginTop: 2 }}>
                        {seoAnalysis?.snapshots?.[0]?.discoverability_score != null ? `${seoAnalysis.snapshots[0].discoverability_score}%` : '—'}
                      </div>
                    </div>
                  </div>

                  {/* Recommended Hashtags Chips */}
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#34d399', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>✨</span> Recommended Hashtags
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {seoAnalysis?.snapshots?.[0]?.recommended_hashtags && seoAnalysis.snapshots[0].recommended_hashtags.length > 0 ? (
                        seoAnalysis.snapshots[0].recommended_hashtags.map((tag, idx) => (
                          <span
                            key={idx}
                            data-testid={`chip-recommended-hashtag-${idx}`}
                            style={{
                              padding: '3px 8px',
                              borderRadius: 6,
                              fontSize: 11,
                              fontWeight: 600,
                              background: 'rgba(52, 211, 153, 0.1)',
                              border: '1px solid rgba(52, 211, 153, 0.25)',
                              color: '#34d399',
                            }}
                          >
                            {tag.startsWith('#') ? tag : `#${tag}`}
                          </span>
                        ))
                      ) : (
                        <span style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic' }}>
                          No high-priority recommendations yet
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Missing Keywords Chips */}
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#fbbf24', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>🔍</span> Missing Search Keywords
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {seoAnalysis?.snapshots?.[0]?.missing_keywords && seoAnalysis.snapshots[0].missing_keywords.length > 0 ? (
                        seoAnalysis.snapshots[0].missing_keywords.map((kw, idx) => (
                          <span
                            key={idx}
                            data-testid={`chip-missing-keyword-${idx}`}
                            style={{
                              padding: '3px 8px',
                              borderRadius: 6,
                              fontSize: 11,
                              fontWeight: 500,
                              background: 'rgba(251, 191, 36, 0.1)',
                              border: '1px solid rgba(251, 191, 36, 0.25)',
                              color: '#fbbf24',
                            }}
                          >
                            +{kw}
                          </span>
                        ))
                      ) : (
                        <span style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic' }}>
                          Keywords coverage optimal
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Weak Hashtags Warning Chips */}
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#f87171', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>⚠️</span> Weak / Saturated Hashtags
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {seoAnalysis?.snapshots?.[0]?.weak_hashtags && seoAnalysis.snapshots[0].weak_hashtags.length > 0 ? (
                        seoAnalysis.snapshots[0].weak_hashtags.map((tag, idx) => (
                          <span
                            key={idx}
                            data-testid={`chip-weak-hashtag-${idx}`}
                            style={{
                              padding: '3px 8px',
                              borderRadius: 6,
                              fontSize: 11,
                              fontWeight: 500,
                              background: 'rgba(248, 113, 113, 0.1)',
                              border: '1px solid rgba(248, 113, 113, 0.25)',
                              color: '#f87171',
                            }}
                          >
                            {tag.startsWith('#') ? tag : `#${tag}`}
                          </span>
                        ))
                      ) : (
                        <span style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic' }}>
                          Zero penalized hashtags detected
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* 3. Auto-Optimization History Card */}
                <div data-testid="card-optimization-log" className="glass" style={{ borderRadius: 12, padding: 20, background: 'rgba(255, 255, 255, 0.02)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span>🔄</span> Auto-Optimization Attempt History
                    </h3>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      Total Attempts: {optLog?.total_attempts || 0}
                    </span>
                  </div>

                  {optLog?.log && optLog.log.length > 0 ? (
                    <div style={{ maxHeight: 220, overflowY: 'auto', fontSize: 12 }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                        <thead>
                          <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                            <th style={{ padding: '6px 8px' }}>#</th>
                            <th style={{ padding: '6px 8px' }}>Generated Title</th>
                            <th style={{ padding: '6px 8px' }}>Score</th>
                            <th style={{ padding: '6px 8px' }}>Time</th>
                          </tr>
                        </thead>
                        <tbody>
                          {optLog.log.map((entry) => (
                            <tr key={entry.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                              <td style={{ padding: '8px', fontWeight: 600, color: '#c084fc' }}>
                                #{entry.attempt}
                              </td>
                              <td style={{ padding: '8px', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {entry.new_title || '—'}
                              </td>
                              <td style={{ padding: '8px', fontWeight: 600, color: '#38bdf8' }}>
                                {entry.view_score != null ? Number(entry.view_score).toFixed(1) : '—'}
                              </td>
                              <td style={{ padding: '8px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                                {entry.created_at ? new Date(entry.created_at).toLocaleDateString() : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ padding: '24px 0', textAlign: 'center', color: '#64748b', fontSize: 12, fontStyle: 'italic' }}>
                      No optimization attempts logged for this clip. Trigger optimization manually or via auto-schedule to improve metadata.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* ══════════════════════════════════════════════════════════════════════
              Active Performance Tracking Queue Table
              ══════════════════════════════════════════════════════════════════════ */}
          <div data-testid="table-active-trackers" className="glass" style={{ borderRadius: 14, padding: 24, marginBottom: 28 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <h3 style={{ fontSize: 17, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>📡</span> Active Video Performance Trackers
                </h3>
                <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0 0', fontSize: 13 }}>
                  Active background polling tasks querying YouTube API metrics every 12 hours
                </p>
              </div>
              <span style={{
                padding: '4px 10px',
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 700,
                background: 'rgba(56, 189, 248, 0.15)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.3)',
              }}>
                {activeTrackers.length} Active Tasks
              </span>
            </div>

            {activeTrackers.length > 0 ? (
              <div className="table-responsive-wrapper">
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                      <th style={{ padding: '10px 12px' }}>Task ID</th>
                      <th style={{ padding: '10px 12px' }}>Clip / Video ID</th>
                      <th style={{ padding: '10px 12px' }}>YouTube ID</th>
                      <th style={{ padding: '10px 12px' }}>Status</th>
                      <th style={{ padding: '10px 12px' }}>Attempts</th>
                      <th style={{ padding: '10px 12px' }}>Last Score</th>
                      <th style={{ padding: '10px 12px', textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeTrackers.map((tracker) => (
                      <tr key={tracker.task_id} style={{ borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '12px', fontFamily: 'monospace', fontSize: 12 }}>
                          {tracker.task_id.slice(0, 8)}...
                        </td>
                        <td style={{ padding: '12px' }}>
                          {tracker.clip_id ? `${tracker.clip_id.slice(0, 10)}...` : '—'}
                        </td>
                        <td style={{ padding: '12px' }}>
                          <code style={{ color: '#38bdf8' }}>{tracker.youtube_video_id || '—'}</code>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span style={{
                            padding: '3px 8px',
                            borderRadius: 6,
                            fontSize: 11,
                            fontWeight: 600,
                            background: 'rgba(52, 211, 153, 0.15)',
                            color: '#34d399',
                            border: '1px solid rgba(52, 211, 153, 0.3)',
                          }}>
                            {(tracker.status || 'ACTIVE').toUpperCase()}
                          </span>
                        </td>
                        <td style={{ padding: '12px' }}>
                          {tracker.optimization_attempts ?? 0}
                        </td>
                        <td style={{ padding: '12px', fontWeight: 600, color: '#fbbf24' }}>
                          {tracker.last_score != null ? Number(tracker.last_score).toFixed(1) : '—'}
                        </td>
                        <td style={{ padding: '12px', textAlign: 'right' }}>
                          <button
                            onClick={() => handleCancelTracker(tracker.task_id)}
                            disabled={actionLoading === `cancelling-${tracker.task_id}`}
                            data-testid={`btn-cancel-tracker-${tracker.task_id}`}
                            className="btn-secondary"
                            style={{
                              padding: '6px 12px',
                              borderRadius: 6,
                              fontSize: 12,
                              fontWeight: 600,
                              cursor: 'pointer',
                              background: 'rgba(239, 68, 68, 0.15)',
                              border: '1px solid rgba(239, 68, 68, 0.35)',
                              color: '#f87171',
                            }}
                          >
                            {actionLoading === `cancelling-${tracker.task_id}` ? 'Stopping...' : '⏹ Cancel Tracker'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '24px 0', textAlign: 'center', color: '#64748b', fontSize: 13 }}>
                No active performance tracking tasks in the queue. Start tracking on any published clip above.
              </div>
            )}
          </div>

          {/* Phase 14 — Reinforcement Learning Insights */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))', gap: 20, marginBottom: 28 }}>
            <div className="glass" style={{ borderRadius: 12, padding: 22 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: '#34d399', margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>🏆</span> Reinforcement Learning: Winning Patterns
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 14 }}>
                Top performing titles whose structural patterns are automatically prioritized in future prompt cycles:
              </p>
              {insights?.top_performing?.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {insights.top_performing.map((clip: any, idx: number) => (
                    <div key={idx} style={{ padding: '8px 12px', borderRadius: 8, background: 'rgba(52,211,153,0.06)', border: '1px solid rgba(52,211,153,0.2)', fontSize: 13, display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 500 }}>"{clip.title}"</span>
                      <span style={{ color: '#34d399', fontWeight: 700 }}>{(clip.analytics_view_score || 0).toFixed(1)} VSI</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  No historical winners recorded yet. Run pipeline tasks to populate memory.
                </div>
              )}
            </div>

            <div className="glass" style={{ borderRadius: 12, padding: 22 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: '#f87171', margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>⚠️</span> Negative Reinforcement: Underperforming Patterns
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 14 }}>
                Low-scoring title phrasing that the LLM is explicitly instructed to avoid:
              </p>
              {insights?.bottom_performing?.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {insights.bottom_performing.map((clip: any, idx: number) => (
                    <div key={idx} style={{ padding: '8px 12px', borderRadius: 8, background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.2)', fontSize: 13, display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 500 }}>"{clip.title}"</span>
                      <span style={{ color: '#f87171', fontWeight: 700 }}>{(clip.analytics_view_score || 0).toFixed(1)} VSI</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  No underperforming titles logged.
                </div>
              )}
            </div>
          </div>

          {/* Phase 14 — Active & Completed A/B Experiments Table */}
          <div className="glass" style={{ borderRadius: 12, padding: 22 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 16px 0' }}>
              🧪 Active & Completed Title A/B Tests
            </h3>

            {abTests.length > 0 ? (
              <div className="table-responsive-wrapper">
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                      <th style={{ padding: '10px 12px' }}>Status</th>
                      <th style={{ padding: '10px 12px' }}>Variant A (Curiosity)</th>
                      <th style={{ padding: '10px 12px' }}>Variant B (Direct Action)</th>
                      <th style={{ padding: '10px 12px' }}>Active</th>
                      <th style={{ padding: '10px 12px' }}>Score A vs B</th>
                    </tr>
                  </thead>
                  <tbody>
                    {abTests.map((exp: any) => (
                      <tr key={exp.id} style={{ borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '12px' }}>
                          <span style={{
                            padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                            background: exp.status === 'swapped' ? 'rgba(251,191,36,0.15)' : exp.status === 'completed' ? 'rgba(52,211,153,0.15)' : 'rgba(99,102,241,0.15)',
                            color: exp.status === 'swapped' ? '#fbbf24' : exp.status === 'completed' ? '#34d399' : '#818cf8',
                            border: `1px solid ${exp.status === 'swapped' ? 'rgba(251,191,36,0.3)' : exp.status === 'completed' ? 'rgba(52,211,153,0.3)' : 'rgba(99,102,241,0.3)'}`,
                          }}>
                            {exp.status.toUpperCase()}
                          </span>
                        </td>
                        <td style={{ padding: '12px', fontWeight: exp.active_variant === 'A' ? 700 : 400 }}>
                          {exp.variant_a_title}
                        </td>
                        <td style={{ padding: '12px', fontWeight: exp.active_variant === 'B' ? 700 : 400 }}>
                          {exp.variant_b_title}
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span style={{ fontWeight: 700, color: exp.active_variant === 'B' ? '#fbbf24' : '#38bdf8' }}>
                            Variant {exp.active_variant}
                          </span>
                        </td>
                        <td style={{ padding: '12px' }}>
                          {(exp.vsi_score_a || 0).toFixed(1)} vs {(exp.vsi_score_b || 0).toFixed(1)} VSI
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '32px 0', textAlign: 'center', color: '#64748b', fontSize: 13 }}>
                No active A/B title experiments yet. Trigger video processing or auto-optimization to start experiments automatically.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
