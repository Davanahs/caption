'use client';
import { useState, useEffect } from 'react';
import { getSystemSettings, updateSystemSettings, SystemSettings } from '@/lib/api';
import { validateNumericSettings } from '@/lib/settingsValidation';

const SECRET_MASK = '••••••••';

export default function SettingsPage() {
  const [env, setEnv] = useState<any>({
    YOUTUBE_CLIENT_ID: '',
    YOUTUBE_CLIENT_SECRET: '',
    OPENROUTER_API_KEY: '',
    OPENROUTER_MODEL: 'deepseek/deepseek-r1:free',
    GROQ_API_KEY: '',
    GROQ_MODEL: 'whisper-large-v3-turbo',
    NVIDIA_API_KEY: '',
    NVIDIA_MODEL: 'meta/llama-3.1-405b-instruct',
    WHISPER_MODEL: 'base',
    CLIPS_PER_VIDEO: 5,
    CHANNEL_CHECK_INTERVAL_MINUTES: 30,
  });
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setFetching(true);

    getSystemSettings()
      .then((settings: SystemSettings) => {
        if (!isMounted) return;
        setEnv({
          YOUTUBE_CLIENT_ID: settings.YOUTUBE_CLIENT_ID || '',
          YOUTUBE_CLIENT_SECRET: settings.YOUTUBE_CLIENT_SECRET_SET ? SECRET_MASK : '',
          OPENROUTER_API_KEY: settings.OPENROUTER_API_KEY_SET ? SECRET_MASK : '',
          OPENROUTER_MODEL: settings.OPENROUTER_MODEL || 'deepseek/deepseek-r1:free',
          GROQ_API_KEY: settings.GROQ_API_KEY_SET ? SECRET_MASK : '',
          GROQ_MODEL: settings.GROQ_MODEL || 'whisper-large-v3-turbo',
          NVIDIA_API_KEY: settings.NVIDIA_API_KEY_SET ? SECRET_MASK : '',
          NVIDIA_MODEL: settings.NVIDIA_MODEL || 'meta/llama-3.1-405b-instruct',
          WHISPER_MODEL: settings.WHISPER_MODEL || 'base',
          CLIPS_PER_VIDEO: settings.CLIPS_PER_VIDEO ?? 5,
          CHANNEL_CHECK_INTERVAL_MINUTES: settings.CHANNEL_CHECK_INTERVAL_MINUTES ?? 30,
        });
        if (settings.last_updated_at) {
          setLastUpdated(settings.last_updated_at);
        }
        try {
          localStorage.setItem('clipforge_settings', JSON.stringify(settings));
        } catch {
          // ignore localStorage errors
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        // Graceful offline fallback to localStorage
        try {
          const cached = localStorage.getItem('clipforge_settings');
          if (cached) {
            const parsed = JSON.parse(cached);
            setEnv((prev: any) => ({ ...prev, ...parsed }));
          }
        } catch {
          // ignore parse errors
        }
      })
      .finally(() => {
        if (isMounted) setFetching(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSave = async () => {
    setLoading(true);
    setError('');
    setMsg('');

    const val = validateNumericSettings(env.CLIPS_PER_VIDEO, env.CHANNEL_CHECK_INTERVAL_MINUTES);
    if (val.clipsError || val.intervalError) {
      const errMsg = [val.clipsError, val.intervalError].filter(Boolean).join(' ');
      setError(errMsg);
      setLoading(false);
      return;
    }

    try {
      const payload: any = {
        YOUTUBE_CLIENT_ID: env.YOUTUBE_CLIENT_ID,
        OPENROUTER_MODEL: env.OPENROUTER_MODEL,
        GROQ_MODEL: env.GROQ_MODEL,
        NVIDIA_MODEL: env.NVIDIA_MODEL,
        WHISPER_MODEL: env.WHISPER_MODEL,
        CLIPS_PER_VIDEO: val.parsedClips!,
        CHANNEL_CHECK_INTERVAL_MINUTES: val.parsedInterval!,
      };

      // Only send secrets if user changed them from the mask
      if (env.YOUTUBE_CLIENT_SECRET && env.YOUTUBE_CLIENT_SECRET !== SECRET_MASK) {
        payload.YOUTUBE_CLIENT_SECRET = env.YOUTUBE_CLIENT_SECRET;
      }
      if (env.OPENROUTER_API_KEY && env.OPENROUTER_API_KEY !== SECRET_MASK) {
        payload.OPENROUTER_API_KEY = env.OPENROUTER_API_KEY;
      }
      if (env.GROQ_API_KEY && env.GROQ_API_KEY !== SECRET_MASK) {
        payload.GROQ_API_KEY = env.GROQ_API_KEY;
      }
      if (env.NVIDIA_API_KEY && env.NVIDIA_API_KEY !== SECRET_MASK) {
        payload.NVIDIA_API_KEY = env.NVIDIA_API_KEY;
      }

      const updated = await updateSystemSettings(payload);

      setEnv((prev: any) => ({
        ...prev,
        YOUTUBE_CLIENT_ID: updated.YOUTUBE_CLIENT_ID || '',
        YOUTUBE_CLIENT_SECRET: updated.YOUTUBE_CLIENT_SECRET_SET ? SECRET_MASK : '',
        OPENROUTER_API_KEY: updated.OPENROUTER_API_KEY_SET ? SECRET_MASK : '',
        OPENROUTER_MODEL: updated.OPENROUTER_MODEL || 'deepseek/deepseek-r1:free',
        GROQ_API_KEY: updated.GROQ_API_KEY_SET ? SECRET_MASK : '',
        GROQ_MODEL: updated.GROQ_MODEL || 'whisper-large-v3-turbo',
        NVIDIA_API_KEY: updated.NVIDIA_API_KEY_SET ? SECRET_MASK : '',
        NVIDIA_MODEL: updated.NVIDIA_MODEL || 'meta/llama-3.1-405b-instruct',
        WHISPER_MODEL: updated.WHISPER_MODEL,
        CLIPS_PER_VIDEO: updated.CLIPS_PER_VIDEO,
        CHANNEL_CHECK_INTERVAL_MINUTES: updated.CHANNEL_CHECK_INTERVAL_MINUTES,
      }));

      if (updated.last_updated_at) {
        setLastUpdated(updated.last_updated_at);
      }

      try {
        localStorage.setItem('clipforge_settings', JSON.stringify(updated));
      } catch {
        // ignore storage errors
      }

      setMsg('✅ Settings successfully saved to backend and synchronized!');
    } catch (err: any) {
      // Local fallback on backend error
      try {
        localStorage.setItem('clipforge_settings', JSON.stringify(env));
        setMsg('⚠️ Backend sync unavailable. Settings saved to local browser cache.');
      } catch {
        setError(err?.message || 'Failed to save settings');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-fade-up">
      <div className="page-header">
        <h1 className="page-title">
          <span>⚙️</span> Settings & Configuration
        </h1>
        <p className="page-subtitle">
          Manage your AI models, YouTube API credentials, and clipping pipeline limits
        </p>
      </div>

      <div className="settings-page-grid">
        {/* Settings Form */}
        <div className="glass" style={{ padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>⚙️ System Settings</h2>
            {lastUpdated && (
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                Synced: {new Date(lastUpdated).toLocaleTimeString()}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* YouTube Keys */}
            <div style={{ padding: 16, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--accent)' }}>📡 YouTube Data API v3 Credentials</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <label htmlFor="yt-client-id" style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>Client ID</label>
                  <input
                    id="yt-client-id"
                    data-testid="input-yt-client-id"
                    className="input-field"
                    type="text"
                    value={env.YOUTUBE_CLIENT_ID}
                    onChange={e => setEnv({ ...env, YOUTUBE_CLIENT_ID: e.target.value })}
                    placeholder="Your OAuth Client ID"
                  />
                </div>
                <div>
                  <label htmlFor="yt-client-secret" style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>Client Secret</label>
                  <input
                    id="yt-client-secret"
                    data-testid="input-yt-client-secret"
                    className="input-field"
                    type="password"
                    value={env.YOUTUBE_CLIENT_SECRET}
                    onChange={e => setEnv({ ...env, YOUTUBE_CLIENT_SECRET: e.target.value })}
                    placeholder="••••••••"
                  />
                </div>
              </div>
            </div>

            {/* Cloud AI Providers */}
            <div style={{ padding: 16, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0, color: 'var(--accent)' }}>☁️ Cloud AI Providers (OpenRouter / Groq / Nvidia NIM)</h3>
                <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 6, background: 'rgba(52, 211, 153, 0.1)', color: '#10b981', border: '1px solid rgba(52, 211, 153, 0.2)' }}>
                  High-Concurrency Cloud AI
                </span>
              </div>

              <div style={{ marginBottom: 14, padding: 10, borderRadius: 8, background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.2)', fontSize: 12, color: 'var(--text-secondary)' }}>
                ⚡ <strong>Cloud AI Architecture:</strong> All moment detection, viral scoring, and fast audio transcription execute via scalable cloud API providers.
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* OpenRouter */}
                <div>
                  <label htmlFor="openrouter-key" style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                    OpenRouter API Key
                  </label>
                  <input
                    id="openrouter-key"
                    data-testid="input-openrouter-key"
                    className="input-field"
                    type="password"
                    value={env.OPENROUTER_API_KEY}
                    onChange={e => setEnv({ ...env, OPENROUTER_API_KEY: e.target.value })}
                    placeholder="sk-or-v1-••••••••"
                  />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <label htmlFor="openrouter-model" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      Active OpenRouter Model
                    </label>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {[
                        { label: 'DeepSeek R1', val: 'deepseek/deepseek-r1:free' },
                        { label: 'Gemini 2.0 Flash', val: 'google/gemini-2.0-flash-exp:free' },
                        { label: 'Llama 3.3 70B', val: 'meta-llama/llama-3.3-70b-instruct:free' },
                        { label: 'Qwen 2.5 72B', val: 'qwen/qwen-2.5-72b-instruct:free' },
                      ].map(preset => (
                        <button
                          key={preset.val}
                          type="button"
                          onClick={() => setEnv({ ...env, OPENROUTER_MODEL: preset.val })}
                          style={{
                            fontSize: 10,
                            padding: '2px 8px',
                            borderRadius: 4,
                            cursor: 'pointer',
                            background: env.OPENROUTER_MODEL === preset.val ? 'var(--accent)' : 'var(--bg-tertiary)',
                            color: env.OPENROUTER_MODEL === preset.val ? '#fff' : 'var(--text-secondary)',
                            border: '1px solid var(--border)',
                          }}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <input
                    id="openrouter-model"
                    data-testid="input-openrouter-model"
                    className="input-field"
                    value={env.OPENROUTER_MODEL}
                    onChange={e => setEnv({ ...env, OPENROUTER_MODEL: e.target.value })}
                    placeholder="deepseek/deepseek-r1:free"
                  />
                </div>

                {/* Groq Cloud Audio */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
                  <div>
                    <label htmlFor="groq-key" style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                      Groq Cloud API Key (Fast Transcription)
                    </label>
                    <input
                      id="groq-key"
                      data-testid="input-groq-key"
                      className="input-field"
                      type="password"
                      value={env.GROQ_API_KEY}
                      onChange={e => setEnv({ ...env, GROQ_API_KEY: e.target.value })}
                      placeholder="gsk_••••••••"
                    />
                  </div>
                  <div>
                    <label htmlFor="groq-model" style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                      Groq Whisper Model
                    </label>
                    <input
                      id="groq-model"
                      data-testid="input-groq-model"
                      className="input-field"
                      value={env.GROQ_MODEL}
                      onChange={e => setEnv({ ...env, GROQ_MODEL: e.target.value })}
                      placeholder="whisper-large-v3-turbo"
                    />
                  </div>
                </div>

                {/* Nvidia NIM Optional */}
                <div>
                  <label htmlFor="nvidia-key" style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                    Nvidia NIM API Key (Optional Fallback)
                  </label>
                  <input
                    id="nvidia-key"
                    data-testid="input-nvidia-key"
                    className="input-field"
                    type="password"
                    value={env.NVIDIA_API_KEY}
                    onChange={e => setEnv({ ...env, NVIDIA_API_KEY: e.target.value })}
                    placeholder="nvapi-••••••••"
                  />
                </div>
              </div>
            </div>

            {/* Pipeline Configuration */}
            <div style={{ padding: 16, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--accent)' }}>⚙️ Pipeline Configurations</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                <div>
                  <label htmlFor="whisper-model" style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>Whisper Model</label>
                  <select
                    id="whisper-model"
                    data-testid="select-whisper-model"
                    className="input-field"
                    value={env.WHISPER_MODEL}
                    onChange={e => setEnv({ ...env, WHISPER_MODEL: e.target.value })}
                  >
                    <option value="tiny">Tiny (Fastest)</option>
                    <option value="base">Base (Balanced)</option>
                    <option value="small">Small</option>
                    <option value="medium">Medium</option>
                    <option value="large">Large (Slowest)</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="clips-limit" style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                    Clips Limit per Video (1 - 20)
                  </label>
                  <input
                    id="clips-limit"
                    data-testid="input-clips-limit"
                    type="number"
                    min={1}
                    max={20}
                    className="input-field"
                    value={env.CLIPS_PER_VIDEO ?? ''}
                    onChange={e => setEnv({ ...env, CLIPS_PER_VIDEO: e.target.value })}
                  />
                </div>
                <div>
                  <label htmlFor="channel-interval" style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                    Channel Check Interval (5 - 1440 min)
                  </label>
                  <input
                    id="channel-interval"
                    data-testid="input-channel-interval"
                    type="number"
                    min={5}
                    max={1440}
                    className="input-field"
                    value={env.CHANNEL_CHECK_INTERVAL_MINUTES ?? ''}
                    onChange={e => setEnv({ ...env, CHANNEL_CHECK_INTERVAL_MINUTES: e.target.value })}
                  />
                </div>
              </div>
            </div>

            <button
              className="btn-primary"
              data-testid="btn-save-settings"
              onClick={handleSave}
              disabled={loading || fetching}
              style={{ justifyContent: 'center' }}
            >
              {loading ? '⏳ Saving to Backend...' : '💾 Save Settings'}
            </button>

            {msg && (
              <div
                role="status"
                data-testid="alert-settings-success"
                style={{ padding: 12, background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)', color: 'var(--success)', borderRadius: 8, fontSize: 13 }}
              >
                {msg}
              </div>
            )}
            {error && (
              <div
                role="alert"
                data-testid="alert-settings-error"
                style={{ padding: 12, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: 'var(--danger)', borderRadius: 8, fontSize: 13 }}
              >
                ⚠️ {error}
              </div>
            )}
          </div>
        </div>

        {/* Documentation Sidebar */}
        <div className="glass" style={{ padding: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>📖 Setup Instructions</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, fontSize: 13, lineHeight: 1.6 }}>
            <div>
              <h4 style={{ fontWeight: 600, color: 'var(--accent)', marginBottom: 4 }}>1. How to get YouTube Keys</h4>
              <p style={{ color: 'var(--text-secondary)' }}>
                Go to the Google Cloud Console, create a project, enable the YouTube Data API v3, and create OAuth client credentials. Copy client ID and Client Secret here.
              </p>
            </div>
            <div>
              <h4 style={{ fontWeight: 600, color: 'var(--accent)', marginBottom: 4 }}>2. Cloud AI Providers</h4>
              <p style={{ color: 'var(--text-secondary)' }}>
                Enter your OpenRouter, Groq, or Nvidia NIM API keys. Free cloud model presets (DeepSeek R1, Gemini 2.0 Flash, Llama 3.3 70B, Qwen 2.5 72B) are available above.
              </p>
            </div>
            <div>
              <h4 style={{ fontWeight: 600, color: 'var(--accent)', marginBottom: 4 }}>3. Local transcription</h4>
              <p style={{ color: 'var(--text-secondary)' }}>
                Whisper transcribes audio locally. On first run, it will automatically download the chosen model file.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
