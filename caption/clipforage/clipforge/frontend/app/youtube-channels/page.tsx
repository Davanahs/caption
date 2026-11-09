'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  getYoutubeChannels,
  getYoutubeChannelStats,
  refreshYoutubeChannelStats,
  updateYoutubeChannelSettings,
  setPrimaryDefaultDestination,
  disconnectYoutubeChannel,
  getYoutubeOAuthUrl,
  connectYoutubeChannel,
  YouTubeChannelDestination,
  ChannelPublishingSettings,
} from '@/lib/api';

const CATEGORY_OPTIONS: { id: string; name: string }[] = [
  { id: '22', name: 'People & Blogs (22)' },
  { id: '24', name: 'Entertainment (24)' },
  { id: '20', name: 'Gaming (20)' },
  { id: '27', name: 'Education (27)' },
  { id: '28', name: 'Science & Technology (28)' },
  { id: '1', name: 'Film & Animation (1)' },
  { id: '10', name: 'Music (10)' },
  { id: '26', name: 'Howto & Style (26)' },
  { id: '17', name: 'Sports (17)' },
  { id: '25', name: 'News & Politics (25)' },
];

export default function YouTubeChannelsPage() {
  const [channels, setChannels] = useState<YouTubeChannelDestination[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Auto-polling and cooldown governance
  const [autoPoll, setAutoPoll] = useState<boolean>(false);
  const [cooldowns, setCooldowns] = useState<Record<string, number>>({});

  // Modals state
  const [connectModalOpen, setConnectModalOpen] = useState<boolean>(false);
  const [settingsModalChannel, setSettingsModalChannel] = useState<YouTubeChannelDestination | null>(null);
  const [disconnectModalChannel, setDisconnectModalChannel] = useState<YouTubeChannelDestination | null>(null);

  // Connect form state
  const [oauthUrl, setOauthUrl] = useState<string>('');
  const [oauthLoading, setOauthLoading] = useState<boolean>(false);
  const [manualCode, setManualCode] = useState<string>('');
  const [connectingManual, setConnectingManual] = useState<boolean>(false);

  // Settings form state
  const [settingsForm, setSettingsForm] = useState<ChannelPublishingSettings>({
    default_privacy: 'public',
    default_category: '22',
    default_tags: 'shorts, viral',
    default_license: 'youtube',
    default_made_for_kids: false,
    default_age_restricted: false,
    watermark_url: '',
    brand_color_primary: '#6366f1',
    brand_logo_position: 'top_right',
  });
  const [savingSettings, setSavingSettings] = useState<boolean>(false);

  // Copy feedback state
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const showToast = (type: 'success' | 'error', message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 5000);
  };

  const calculateCooldown = (fetchedAt?: string | null): number => {
    if (!fetchedAt) return 0;
    try {
      const d = new Date(fetchedAt.endsWith('Z') ? fetchedAt : fetchedAt + 'Z');
      const diffSec = Math.floor((Date.now() - d.getTime()) / 1000);
      return Math.max(0, 60 - diffSec);
    } catch {
      return 0;
    }
  };

  const loadChannels = async (showSpinner: boolean = true) => {
    if (showSpinner) setLoading(true);
    try {
      const data = await getYoutubeChannels();
      setChannels(data);
      const newCooldowns: Record<string, number> = {};
      data.forEach(ch => {
        newCooldowns[ch.id] = calculateCooldown(ch.cached_stats?.fetched_at);
      });
      setCooldowns(newCooldowns);
    } catch (err: any) {
      showToast('error', `Failed to load channels: ${err.message || 'Unknown error'}`);
    } finally {
      if (showSpinner) setLoading(false);
    }
  };

  useEffect(() => {
    loadChannels(true);
  }, []);

  // Cooldown countdown tick effect
  useEffect(() => {
    const timer = setInterval(() => {
      setCooldowns(prev => {
        let changed = false;
        const next = { ...prev };
        for (const [k, v] of Object.entries(next)) {
          if (v > 0) {
            next[k] = v - 1;
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Auto-polling interval (30s)
  useEffect(() => {
    if (!autoPoll) return;
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return;
      loadChannels(false);
    }, 30000);
    return () => clearInterval(interval);
  }, [autoPoll]);

  // Fetch OAuth URL when opening connect modal
  const handleOpenConnectModal = async () => {
    setConnectModalOpen(true);
    setManualCode('');
    setOauthLoading(true);
    try {
      const res = await getYoutubeOAuthUrl();
      setOauthUrl(res.oauth_url);
    } catch (err: any) {
      showToast('error', `Could not fetch OAuth URL: ${err.message}`);
    } finally {
      setOauthLoading(false);
    }
  };

  // Submit manual code
  const handleConnectManual = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualCode.trim()) return;
    setConnectingManual(true);
    try {
      const res = await connectYoutubeChannel(manualCode.trim());
      showToast('success', `Channel '${res.channel?.channel_name || 'YouTube Channel'}' connected successfully!`);
      setConnectModalOpen(false);
      await loadChannels();
    } catch (err: any) {
      showToast('error', `Connection failed: ${err.message}`);
    } finally {
      setConnectingManual(false);
    }
  };

  // Refresh stats with rate-limit cooldown governance
  const handleRefreshStats = async (channel: YouTubeChannelDestination, force: boolean = false) => {
    setRefreshingId(channel.id);
    try {
      const res = await refreshYoutubeChannelStats(channel.id, force);
      if (res.rate_limited) {
        showToast('success', res.message || `Served from cache (cooldown active: ${res.cooldown_remaining_seconds}s)`);
      } else {
        showToast('success', `Updated statistics for '${channel.channel_name}'`);
      }
      setChannels(prev =>
        prev.map(c => (c.id === channel.id ? { ...c, cached_stats: res.cached_stats } : c))
      );
      if (res.cooldown_remaining_seconds !== undefined) {
        setCooldowns(prev => ({ ...prev, [channel.id]: res.cooldown_remaining_seconds || 60 }));
      }
    } catch (err: any) {
      showToast('error', `Refresh failed: ${err.message}`);
      // Re-fetch to reflect stale status in DB if updated
      loadChannels(false);
    } finally {
      setRefreshingId(null);
    }
  };

  // Set default destination
  const handleSetDefault = async (channel: YouTubeChannelDestination) => {
    try {
      await setPrimaryDefaultDestination(channel.id);
      showToast('success', `'${channel.channel_name}' is now the primary default publishing destination.`);
      setChannels(prev =>
        prev.map(c => ({
          ...c,
          is_default_destination: c.id === channel.id,
        }))
      );
    } catch (err: any) {
      showToast('error', `Could not set default: ${err.message}`);
    }
  };

  // Open settings modal
  const handleOpenSettings = (channel: YouTubeChannelDestination) => {
    setSettingsModalChannel(channel);
    const existing = channel.publishing_settings || {};
    setSettingsForm({
      default_privacy: existing.default_privacy || 'public',
      default_category: existing.default_category || '22',
      default_tags: Array.isArray(existing.default_tags)
        ? existing.default_tags.join(', ')
        : existing.default_tags || '',
      default_license: existing.default_license || 'youtube',
      default_made_for_kids: Boolean(existing.default_made_for_kids),
      default_age_restricted: Boolean(existing.default_age_restricted),
      watermark_url: existing.watermark_url || '',
      brand_color_primary: existing.brand_color_primary || '#6366f1',
      brand_logo_position: existing.brand_logo_position || 'top_right',
    });
  };

  // Save settings
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settingsModalChannel) return;
    setSavingSettings(true);
    try {
      const res = await updateYoutubeChannelSettings(settingsModalChannel.id, settingsForm);
      showToast('success', `Saved publishing settings for '${settingsModalChannel.channel_name}'`);
      setChannels(prev =>
        prev.map(c =>
          c.id === settingsModalChannel.id
            ? { ...c, publishing_settings: res.publishing_settings }
            : c
        )
      );
      setSettingsModalChannel(null);
    } catch (err: any) {
      showToast('error', `Failed to save settings: ${err.message}`);
    } finally {
      setSavingSettings(false);
    }
  };

  // Disconnect channel
  const handleConfirmDisconnect = async () => {
    if (!disconnectModalChannel) return;
    try {
      await disconnectYoutubeChannel(disconnectModalChannel.id);
      showToast('success', `Channel '${disconnectModalChannel.channel_name}' has been disconnected.`);
      setDisconnectModalChannel(null);
      await loadChannels();
    } catch (err: any) {
      showToast('error', `Disconnect failed: ${err.message}`);
    }
  };

  const handleCopyId = (ytId: string) => {
    navigator.clipboard.writeText(ytId);
    setCopiedId(ytId);
    setTimeout(() => setCopiedId(null), 2500);
  };

  const formatNumber = (num?: number | null): string => {
    if (num === null || num === undefined) return '0';
    if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
    if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
    return num.toLocaleString();
  };

  return (
    <div style={{ minHeight: '100vh', background: '#0b0f19', color: '#f8fafc', padding: '32px 40px', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      {/* Toast Notification */}
      {toast && (
        <div style={{
          position: 'fixed',
          top: 24,
          right: 24,
          zIndex: 9999,
          padding: '14px 20px',
          borderRadius: 10,
          background: toast.type === 'success' ? '#064e3b' : '#7f1d1d',
          color: toast.type === 'success' ? '#6ee7b7' : '#fca5a5',
          border: `1px solid ${toast.type === 'success' ? '#059669' : '#dc2626'}`,
          boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          fontSize: '0.92rem',
          fontWeight: 500,
          animation: 'fadeIn 0.2s ease-out'
        }}>
          <span>{toast.type === 'success' ? '✓' : '⚠️'}</span>
          <span>{toast.message}</span>
        </div>
      )}

      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span style={{ fontSize: '1.8rem' }}>📺</span>
            <h1 style={{ fontSize: '2rem', fontWeight: 700, margin: 0, letterSpacing: '-0.02em', background: 'linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              My YouTube Channels
            </h1>
          </div>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: '1rem', maxWidth: 640 }}>
            Connect and manage the YouTube channels you can publish to from ClipForge. Configure defaults, view analytics, and isolate authorization credentials.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            data-testid="toggle-auto-refresh"
            onClick={() => setAutoPoll(prev => !prev)}
            style={{
              padding: '10px 16px',
              borderRadius: 8,
              background: autoPoll ? 'rgba(16, 185, 129, 0.2)' : 'rgba(30, 41, 59, 0.7)',
              color: autoPoll ? '#34d399' : '#cbd5e1',
              border: `1px solid ${autoPoll ? 'rgba(16, 185, 129, 0.4)' : 'rgba(255, 255, 255, 0.1)'}`,
              fontSize: '0.9rem',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
            title={autoPoll ? 'Auto-refresh polling active (every 30s)' : 'Click to enable auto-refresh polling (30s interval)'}
          >
            <span>{autoPoll ? '🟢' : '⏱'}</span>
            {autoPoll ? 'Auto-Refresh (30s): ON' : 'Auto-Refresh: OFF'}
          </button>

          <button
            data-testid="btn-sync-all-channels"
            onClick={() => loadChannels(false)}
            style={{
              padding: '10px 14px',
              borderRadius: 8,
              background: 'rgba(30, 41, 59, 0.7)',
              color: '#cbd5e1',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              fontSize: '0.9rem',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
            title="Fetch cached statuses across all channels"
          >
            🔄 Sync All
          </button>

          <Link
            href="/publish"
            data-testid="link-go-to-publish"
            style={{
              padding: '10px 16px',
              borderRadius: 8,
              background: 'rgba(30, 41, 59, 0.7)',
              color: '#cbd5e1',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              textDecoration: 'none',
              fontSize: '0.9rem',
              fontWeight: 500,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            🚀 Go to Publish
          </Link>

          <button
            data-testid="btn-open-connect-modal"
            onClick={handleOpenConnectModal}
            style={{
              padding: '10px 20px',
              borderRadius: 8,
              background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
              color: '#ffffff',
              border: 'none',
              fontWeight: 600,
              fontSize: '0.95rem',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              boxShadow: '0 4px 14px rgba(239, 68, 68, 0.35)',
              transition: 'transform 0.15s, box-shadow 0.15s',
            }}
            onMouseOver={(e) => (e.currentTarget.style.transform = 'translateY(-1px)')}
            onMouseOut={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
          >
            <span>+</span> Connect YouTube Channel
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300, color: '#94a3b8' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ width: 40, height: 40, border: '3px solid rgba(255,255,255,0.1)', borderTopColor: '#ef4444', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 16px' }} />
            <p>Loading connected YouTube channels...</p>
          </div>
        </div>
      ) : channels.length === 0 ? (
        /* Empty State */
        <div style={{
          background: 'rgba(19, 27, 46, 0.8)',
          border: '1px dashed rgba(255, 255, 255, 0.15)',
          borderRadius: 16,
          padding: '64px 32px',
          textAlign: 'center',
          maxWidth: 600,
          margin: '40px auto',
        }}>
          <div style={{ fontSize: '3.5rem', marginBottom: 16 }}>📹</div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 600, marginBottom: 8, color: '#f1f5f9' }}>
            No YouTube Channels Connected
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: 24 }}>
            Connect your YouTube channel using Google OAuth to enable direct, one-click YouTube Shorts publishing from ClipForge. Each channel maintains isolated credentials.
          </p>
          <button
            onClick={handleOpenConnectModal}
            style={{
              padding: '12px 24px',
              borderRadius: 8,
              background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
              color: '#ffffff',
              border: 'none',
              fontWeight: 600,
              fontSize: '1rem',
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(239, 68, 68, 0.4)',
            }}
          >
            + Connect Your First Channel
          </button>
        </div>
      ) : (
        /* Channels Cards Grid */
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 480px), 1fr))', gap: 24 }}>
          {channels.map((channel) => {
            const stats = channel.cached_stats;
            const settings = channel.publishing_settings || {};
            const isRefreshing = refreshingId === channel.id;
            const cooldownSec = cooldowns[channel.id] || 0;

            return (
              <div
                key={channel.id}
                data-testid={`card-channel-${channel.id}`}
                style={{
                  background: 'rgba(19, 27, 46, 0.85)',
                  backdropFilter: 'blur(12px)',
                  borderRadius: 16,
                  border: channel.is_default_destination
                    ? '1.5px solid rgba(239, 68, 68, 0.5)'
                    : '1px solid rgba(255, 255, 255, 0.08)',
                  boxShadow: channel.is_default_destination
                    ? '0 8px 30px rgba(239, 68, 68, 0.15)'
                    : '0 8px 25px rgba(0, 0, 0, 0.3)',
                  padding: 24,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 20,
                  transition: 'border-color 0.2s',
                }}
              >
                {/* Channel Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                    {channel.thumbnail_url ? (
                      <img
                        src={channel.thumbnail_url}
                        alt={channel.channel_name}
                        style={{
                          width: 58,
                          height: 58,
                          borderRadius: '50%',
                          objectFit: 'cover',
                          border: '2px solid rgba(255, 255, 255, 0.15)',
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          width: 58,
                          height: 58,
                          borderRadius: '50%',
                          background: 'linear-gradient(135deg, #334155 0%, #1e293b 100%)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '1.4rem',
                          fontWeight: 700,
                          color: '#f8fafc',
                          border: '2px solid rgba(255, 255, 255, 0.1)',
                        }}
                      >
                        {channel.channel_name.charAt(0).toUpperCase()}
                      </div>
                    )}

                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: '#ffffff' }}>
                          {channel.channel_name}
                        </h2>
                        {channel.is_default_destination && (
                          <span
                            data-testid={`badge-primary-default-${channel.id}`}
                            style={{
                              padding: '2px 8px',
                              borderRadius: 6,
                              background: 'rgba(239, 68, 68, 0.2)',
                              color: '#f87171',
                              border: '1px solid rgba(239, 68, 68, 0.4)',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              letterSpacing: '0.04em',
                              textTransform: 'uppercase',
                            }}
                          >
                            ★ Primary Default
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
                        <button
                          onClick={() => handleCopyId(channel.youtube_channel_id)}
                          title="Click to copy YouTube Channel ID"
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#94a3b8',
                            fontSize: '0.8rem',
                            fontFamily: 'monospace',
                            cursor: 'pointer',
                            padding: 0,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                          }}
                        >
                          <span>{channel.youtube_channel_id}</span>
                          <span style={{ fontSize: '0.75rem', color: copiedId === channel.youtube_channel_id ? '#10b981' : '#64748b' }}>
                            {copiedId === channel.youtube_channel_id ? '✓ Copied' : '📋'}
                          </span>
                        </button>

                        <a
                          href={`https://youtube.com/channel/${channel.youtube_channel_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: '#38bdf8', fontSize: '0.8rem', textDecoration: 'none' }}
                        >
                          View ↗
                        </a>
                      </div>
                    </div>
                  </div>

                  {/* Status Indicator */}
                  <div>
                    <span
                      data-testid={`badge-channel-status-${channel.id}`}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 20,
                        background:
                          channel.status === 'connected'
                            ? 'rgba(16, 185, 129, 0.15)'
                            : channel.status === 'disconnected'
                            ? 'rgba(148, 163, 184, 0.15)'
                            : 'rgba(245, 158, 11, 0.15)',
                        color:
                          channel.status === 'connected'
                            ? '#34d399'
                            : channel.status === 'disconnected'
                            ? '#94a3b8'
                            : '#fbbf24',
                        border: `1px solid ${
                          channel.status === 'connected'
                            ? 'rgba(16, 185, 129, 0.3)'
                            : channel.status === 'disconnected'
                            ? 'rgba(148, 163, 184, 0.3)'
                            : 'rgba(245, 158, 11, 0.3)'
                        }`,
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                      }}
                    >
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          background:
                            channel.status === 'connected'
                              ? '#10b981'
                              : channel.status === 'disconnected'
                              ? '#94a3b8'
                              : '#f59e0b',
                        }}
                      />
                      {channel.status === 'connected'
                        ? 'Connected'
                        : channel.status === 'disconnected'
                        ? 'Disconnected'
                        : 'Needs Re-auth'}
                    </span>
                  </div>
                </div>

                {/* Stale Cache Warning Banner */}
                {stats?.status === 'stale' && (
                  <div
                    data-testid={`banner-stale-stats-${channel.id}`}
                    style={{
                      background: 'rgba(245, 158, 11, 0.12)',
                      border: '1px solid rgba(245, 158, 11, 0.35)',
                      borderRadius: 8,
                      padding: '8px 12px',
                      color: '#fbbf24',
                      fontSize: '0.78rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                    }}
                  >
                    <span>⚠️</span>
                    <span>{stats.warning_metadata || 'Live refresh failed (YouTube API quota or network error). Displaying cached metrics.'}</span>
                  </div>
                )}

                {/* Statistics Grid */}
                <div
                  style={{
                    background: 'rgba(15, 23, 42, 0.65)',
                    borderRadius: 12,
                    padding: '16px',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                  }}
                >
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 80px), 1fr))',
                      gap: 12,
                      textAlign: 'center',
                    }}
                  >
                    <div data-testid={`stats-subscribers-${channel.id}`}>
                      <div style={{ color: '#94a3b8', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600, marginBottom: 2 }}>
                        Subscribers
                      </div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc' }}>
                        {stats?.subscriber_count !== null && stats?.subscriber_count !== undefined
                          ? formatNumber(stats.subscriber_count)
                          : 'Hidden'}
                      </div>
                    </div>

                    <div data-testid={`stats-views-${channel.id}`}>
                      <div style={{ color: '#94a3b8', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600, marginBottom: 2 }}>
                        Channel Views
                      </div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc' }}>
                        {formatNumber(stats?.view_count)}
                      </div>
                    </div>

                    <div data-testid={`stats-videos-${channel.id}`}>
                      <div style={{ color: '#94a3b8', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600, marginBottom: 2 }}>
                        Public Videos
                      </div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc' }}>
                        {formatNumber(stats?.video_count)}
                      </div>
                    </div>

                    <div data-testid={`stats-shorts-${channel.id}`} title="Shorts detected in recent uploads scan (duration <= 60s or #Shorts tag)">
                      <div style={{ color: '#94a3b8', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600, marginBottom: 2 }}>
                        Shorts Scanned
                      </div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#38bdf8' }}>
                        {formatNumber(stats?.shorts_count)}
                      </div>
                      <div style={{ fontSize: '0.62rem', color: '#64748b' }}>in recent scan</div>
                    </div>

                    <div data-testid={`stats-likes-${channel.id}`} title="Total likes summed across scanned recent uploads">
                      <div style={{ color: '#94a3b8', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600, marginBottom: 2 }}>
                        Likes (Scanned)
                      </div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f43f5e' }}>
                        {formatNumber(stats?.likes_count)}
                      </div>
                      <div style={{ fontSize: '0.62rem', color: '#64748b' }}>recent uploads</div>
                    </div>
                  </div>

                  {/* Freshness & Metadata */}
                  <div
                    style={{
                      marginTop: 12,
                      paddingTop: 10,
                      borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.74rem',
                      color: '#64748b',
                      flexWrap: 'wrap',
                      gap: 6,
                    }}
                  >
                    <span>
                      {stats?.fetched_at ? (
                        <>
                          🕒 Last fetched:{' '}
                          <span style={{ color: '#94a3b8' }}>
                            {new Date(stats.fetched_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>{' '}
                          ({stats.shorts_scan_coverage || 'live'})
                        </>
                      ) : (
                        'No cached statistics yet. Click Refresh below.'
                      )}
                    </span>

                    {stats?.warning_metadata && (
                      <span style={{ color: '#f59e0b', fontSize: '0.72rem' }} title={stats.warning_metadata}>
                        ℹ️ Scan bounded
                      </span>
                    )}
                  </div>
                </div>

                {/* Publishing Defaults Summary */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: '0.78rem' }}>
                  <span style={{ color: '#64748b', fontWeight: 600 }}>Defaults:</span>
                  <span style={{ padding: '2px 8px', borderRadius: 4, background: 'rgba(30, 41, 59, 0.8)', color: '#cbd5e1' }}>
                    🔒 {settings.default_privacy || 'public'}
                  </span>
                  <span style={{ padding: '2px 8px', borderRadius: 4, background: 'rgba(30, 41, 59, 0.8)', color: '#cbd5e1' }}>
                    📂 Category {settings.default_category || '22'}
                  </span>
                  <span style={{ padding: '2px 8px', borderRadius: 4, background: 'rgba(30, 41, 59, 0.8)', color: '#cbd5e1' }}>
                    🏷️ {settings.default_tags ? 'Tags Configured' : 'No Default Tags'}
                  </span>
                  {settings.brand_color_primary && (
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: 4,
                        background: 'rgba(30, 41, 59, 0.8)',
                        color: settings.brand_color_primary,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: settings.brand_color_primary }} />
                      Branding
                    </span>
                  )}
                </div>

                {/* Card Actions Footer */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    paddingTop: 14,
                    borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                    gap: 8,
                    flexWrap: 'wrap',
                  }}
                >
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button
                      data-testid={`btn-refresh-stats-${channel.id}`}
                      onClick={() => handleRefreshStats(channel, false)}
                      disabled={isRefreshing || cooldownSec > 0}
                      style={{
                        padding: '6px 12px',
                        borderRadius: 6,
                        background: cooldownSec > 0 ? 'rgba(30, 41, 59, 0.4)' : 'rgba(30, 41, 59, 0.7)',
                        color: cooldownSec > 0 ? '#94a3b8' : '#f8fafc',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        fontSize: '0.82rem',
                        fontWeight: 500,
                        cursor: isRefreshing || cooldownSec > 0 ? 'not-allowed' : 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                      }}
                      title={cooldownSec > 0 ? `Rate limit cooldown active: ${cooldownSec}s remaining` : 'Refresh YouTube stats'}
                    >
                      <span style={{ display: 'inline-block', animation: isRefreshing ? 'spin 1s linear infinite' : 'none' }}>
                        🔄
                      </span>
                      {isRefreshing ? 'Refreshing...' : cooldownSec > 0 ? `Cooldown (${cooldownSec}s)` : 'Refresh Stats'}
                    </button>

                    {cooldownSec > 0 && (
                      <button
                        data-testid={`btn-force-refresh-${channel.id}`}
                        onClick={() => handleRefreshStats(channel, true)}
                        disabled={isRefreshing}
                        style={{
                          padding: '6px 10px',
                          borderRadius: 6,
                          background: 'rgba(239, 68, 68, 0.15)',
                          color: '#fca5a5',
                          border: '1px solid rgba(239, 68, 68, 0.3)',
                          fontSize: '0.78rem',
                          fontWeight: 600,
                          cursor: isRefreshing ? 'not-allowed' : 'pointer',
                        }}
                        title="Bypass 60-second cooldown and query YouTube Data API immediately"
                      >
                        ⚡ Force
                      </button>
                    )}

                    <button
                      data-testid={`btn-settings-${channel.id}`}
                      onClick={() => handleOpenSettings(channel)}
                      style={{
                        padding: '6px 12px',
                        borderRadius: 6,
                        background: 'rgba(30, 41, 59, 0.7)',
                        color: '#f8fafc',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        fontSize: '0.82rem',
                        fontWeight: 500,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                      }}
                    >
                      ⚙️ Publishing Settings
                    </button>
                  </div>

                  <div style={{ display: 'flex', gap: 8 }}>
                    {!channel.is_default_destination && channel.is_active && (
                      <button
                        data-testid={`btn-set-default-${channel.id}`}
                        onClick={() => handleSetDefault(channel)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: 6,
                          background: 'rgba(245, 158, 11, 0.15)',
                          color: '#fbbf24',
                          border: '1px solid rgba(245, 158, 11, 0.3)',
                          fontSize: '0.82rem',
                          fontWeight: 500,
                          cursor: 'pointer',
                        }}
                      >
                        Set as Default
                      </button>
                    )}

                    <button
                      data-testid={`btn-disconnect-${channel.id}`}
                      onClick={() => setDisconnectModalChannel(channel)}
                      style={{
                        padding: '6px 12px',
                        borderRadius: 6,
                        background: 'rgba(239, 68, 68, 0.1)',
                        color: '#f87171',
                        border: '1px solid rgba(239, 68, 68, 0.25)',
                        fontSize: '0.82rem',
                        fontWeight: 500,
                        cursor: 'pointer',
                      }}
                    >
                      Disconnect
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Modal 1: Connect YouTube Channel ── */}
      {connectModalOpen && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: 20,
        }}>
          <div style={{
            background: '#131b2e',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: 16,
            maxWidth: 520,
            width: '100%',
            padding: 32,
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.6)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: '1.4rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                  Connect YouTube Channel
                </h2>
                <p style={{ color: '#94a3b8', fontSize: '0.88rem', margin: '4px 0 0' }}>
                  Authorize ClipForge to upload Shorts to your channel.
                </p>
              </div>
              <button
                onClick={() => setConnectModalOpen(false)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '1.2rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            {/* Quick Google Sign In */}
            <div style={{ marginBottom: 28 }}>
              {oauthLoading ? (
                <div style={{ textAlign: 'center', padding: 20, color: '#94a3b8' }}>Generating OAuth link...</div>
              ) : oauthUrl ? (
                <a
                  href={oauthUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 12,
                    background: '#ffffff',
                    color: '#0f172a',
                    padding: '14px 20px',
                    borderRadius: 10,
                    textDecoration: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
                    transition: 'transform 0.1s',
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.transform = 'translateY(-1px)')}
                  onMouseOut={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"/>
                    <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.34 24 12 24z"/>
                    <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 10.03 0 12s.45 3.82 1.25 5.42l4.03-3.15z"/>
                    <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.34 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/>
                  </svg>
                  Sign in with Google
                </a>
              ) : (
                <div style={{ color: '#ef4444', fontSize: '0.88rem' }}>OAuth not configured. Enter details below.</div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '20px 0', color: '#64748b', fontSize: '0.82rem' }}>
              <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.1)' }} />
              <span>OR ENTER AUTHORIZATION REDIRECT</span>
              <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.1)' }} />
            </div>

            {/* Manual Form */}
            <form onSubmit={handleConnectManual}>
              <div style={{ marginBottom: 20 }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#cbd5e1', marginBottom: 6 }}>
                  Redirect URL or Authorization Code:
                </label>
                <textarea
                  value={manualCode}
                  onChange={(e) => setManualCode(e.target.value)}
                  placeholder="Paste http://localhost:8080/?code=4/0A... or the raw authorization code here"
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 8,
                    background: 'rgba(15, 23, 42, 0.7)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    color: '#f8fafc',
                    fontSize: '0.84rem',
                    fontFamily: 'monospace',
                    resize: 'vertical',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                <button
                  type="button"
                  onClick={() => setConnectModalOpen(false)}
                  style={{
                    padding: '10px 18px',
                    borderRadius: 8,
                    background: 'rgba(30, 41, 59, 0.8)',
                    color: '#cbd5e1',
                    border: 'none',
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={connectingManual || !manualCode.trim()}
                  style={{
                    padding: '10px 20px',
                    borderRadius: 8,
                    background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                    color: '#ffffff',
                    border: 'none',
                    fontWeight: 600,
                    cursor: connectingManual || !manualCode.trim() ? 'not-allowed' : 'pointer',
                    opacity: connectingManual || !manualCode.trim() ? 0.6 : 1,
                  }}
                >
                  {connectingManual ? 'Verifying...' : 'Verify & Connect'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal 2: Channel Publishing Settings ── */}
      {settingsModalChannel && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: 20,
        }}>
          <div style={{
            background: '#131b2e',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: 16,
            maxWidth: 600,
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: 32,
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.6)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: '1.35rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                  Publishing Settings
                </h2>
                <p style={{ color: '#94a3b8', fontSize: '0.86rem', margin: '4px 0 0' }}>
                  Default configuration for <strong>{settingsModalChannel.channel_name}</strong>
                </p>
              </div>
              <button
                onClick={() => setSettingsModalChannel(null)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '1.2rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {/* Privacy & Category Row */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#cbd5e1', marginBottom: 6 }}>
                    Default Privacy
                  </label>
                  <select
                    value={settingsForm.default_privacy}
                    onChange={(e) => setSettingsForm({ ...settingsForm, default_privacy: e.target.value as any })}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: 8,
                      background: 'rgba(15, 23, 42, 0.8)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#f8fafc',
                      fontSize: '0.88rem',
                    }}
                  >
                    <option value="public">Public</option>
                    <option value="unlisted">Unlisted</option>
                    <option value="private">Private</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#cbd5e1', marginBottom: 6 }}>
                    Default Category
                  </label>
                  <select
                    value={settingsForm.default_category}
                    onChange={(e) => setSettingsForm({ ...settingsForm, default_category: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: 8,
                      background: 'rgba(15, 23, 42, 0.8)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#f8fafc',
                      fontSize: '0.88rem',
                    }}
                  >
                    {CATEGORY_OPTIONS.map((cat) => (
                      <option key={cat.id} value={cat.id}>
                        {cat.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Tags */}
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#cbd5e1', marginBottom: 6 }}>
                  Default Tags (comma-separated)
                </label>
                <input
                  type="text"
                  value={settingsForm.default_tags as string}
                  onChange={(e) => setSettingsForm({ ...settingsForm, default_tags: e.target.value })}
                  placeholder="shorts, viral, podcast, highlights"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 8,
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#f8fafc',
                    fontSize: '0.88rem',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              {/* License & Kids */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#cbd5e1', marginBottom: 6 }}>
                    License
                  </label>
                  <select
                    value={settingsForm.default_license}
                    onChange={(e) => setSettingsForm({ ...settingsForm, default_license: e.target.value as any })}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: 8,
                      background: 'rgba(15, 23, 42, 0.8)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#f8fafc',
                      fontSize: '0.88rem',
                    }}
                  >
                    <option value="youtube">Standard YouTube License</option>
                    <option value="creative_commons">Creative Commons - Attribution</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', color: '#cbd5e1', fontSize: '0.86rem' }}>
                    <input
                      type="checkbox"
                      checked={settingsForm.default_made_for_kids}
                      onChange={(e) => setSettingsForm({ ...settingsForm, default_made_for_kids: e.target.checked })}
                      style={{ width: 16, height: 16 }}
                    />
                    Self-Declared Made for Kids
                  </label>
                </div>
              </div>

              {/* Branding Section */}
              <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: 16 }}>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc', marginBottom: 12 }}>
                  Branding Preferences
                </h3>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 14 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#cbd5e1', marginBottom: 6 }}>
                      Brand Primary Color
                    </label>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <input
                        type="color"
                        value={settingsForm.brand_color_primary || '#6366f1'}
                        onChange={(e) => setSettingsForm({ ...settingsForm, brand_color_primary: e.target.value })}
                        style={{ width: 38, height: 38, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'transparent' }}
                      />
                      <input
                        type="text"
                        value={settingsForm.brand_color_primary || ''}
                        onChange={(e) => setSettingsForm({ ...settingsForm, brand_color_primary: e.target.value })}
                        placeholder="#6366f1"
                        style={{
                          flex: 1,
                          padding: '8px 10px',
                          borderRadius: 6,
                          background: 'rgba(15, 23, 42, 0.8)',
                          border: '1px solid rgba(255, 255, 255, 0.15)',
                          color: '#f8fafc',
                          fontFamily: 'monospace',
                          fontSize: '0.84rem',
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#cbd5e1', marginBottom: 6 }}>
                      Logo Position
                    </label>
                    <select
                      value={settingsForm.brand_logo_position}
                      onChange={(e) => setSettingsForm({ ...settingsForm, brand_logo_position: e.target.value as any })}
                      style={{
                        width: '100%',
                        padding: '10px 12px',
                        borderRadius: 8,
                        background: 'rgba(15, 23, 42, 0.8)',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        color: '#f8fafc',
                        fontSize: '0.88rem',
                      }}
                    >
                      <option value="top_right">Top Right</option>
                      <option value="top_left">Top Left</option>
                      <option value="bottom_right">Bottom Right</option>
                      <option value="bottom_left">Bottom Left</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#cbd5e1', marginBottom: 6 }}>
                    Watermark Image URL
                  </label>
                  <input
                    type="url"
                    value={settingsForm.watermark_url || ''}
                    onChange={(e) => setSettingsForm({ ...settingsForm, watermark_url: e.target.value })}
                    placeholder="https://example.com/logo.png"
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: 8,
                      background: 'rgba(15, 23, 42, 0.8)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#f8fafc',
                      fontSize: '0.88rem',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 12 }}>
                <button
                  type="button"
                  onClick={() => setSettingsModalChannel(null)}
                  style={{
                    padding: '10px 18px',
                    borderRadius: 8,
                    background: 'rgba(30, 41, 59, 0.8)',
                    color: '#cbd5e1',
                    border: 'none',
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingSettings}
                  style={{
                    padding: '10px 22px',
                    borderRadius: 8,
                    background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                    color: '#ffffff',
                    border: 'none',
                    fontWeight: 600,
                    cursor: savingSettings ? 'not-allowed' : 'pointer',
                  }}
                >
                  {savingSettings ? 'Saving...' : 'Save Preferences'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal 3: Disconnect Confirmation ── */}
      {disconnectModalChannel && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: 20,
        }}>
          <div style={{
            background: '#131b2e',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: 16,
            maxWidth: 480,
            width: '100%',
            padding: 32,
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.6)',
          }}>
            <div style={{ fontSize: '2.5rem', marginBottom: 16 }}>⚠️</div>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 700, margin: 0, color: '#f8fafc', marginBottom: 8 }}>
              Disconnect {disconnectModalChannel.channel_name}?
            </h2>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', lineHeight: 1.6, marginBottom: 24 }}>
              Disconnecting will remove this channel as an eligible publishing destination. Your historical clips, rendered videos, jobs, and past publish records will remain safely preserved in ClipForge.
            </p>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
              <button
                onClick={() => setDisconnectModalChannel(null)}
                style={{
                  padding: '10px 18px',
                  borderRadius: 8,
                  background: 'rgba(30, 41, 59, 0.8)',
                  color: '#cbd5e1',
                  border: 'none',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDisconnect}
                style={{
                  padding: '10px 22px',
                  borderRadius: 8,
                  background: '#dc2626',
                  color: '#ffffff',
                  border: 'none',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Confirm Disconnect
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
