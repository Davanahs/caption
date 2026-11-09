'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const nav = [
  { href: '/',                icon: '⚡', label: 'Dashboard' },
  { href: '/captions',        icon: '💬', label: 'Caption Studio' },
  { href: '/podcasts',        icon: '🎙️', label: 'Podcasts / Interviews' },
  { href: '/studio',          icon: '🎞️', label: 'Upload Studio' },
  { href: '/clips',           icon: '🎬', label: 'Clips Library' },
  { href: '/analytics',       icon: '📊', label: 'Analytics' },
  { href: '/automation',      icon: '🤖', label: 'Automation' },
  { href: '/youtube-channels', icon: '📺', label: 'My YouTube Channels' },
  { href: '/publish',         icon: '🚀', label: 'Publish' },
  { href: '/settings',        icon: '⚙️', label: 'Settings' },
];

const StatusDot = ({ status }: { status?: string }) => {
  const isOk = status === 'ok' || status === 'online';
  const isChecking = !status || status === 'checking' || status === 'connecting';
  const color = isOk ? '#10b981' : isChecking ? '#f59e0b' : '#ef4444';
  const shadow = isOk ? '0 0 6px #10b981' : isChecking ? '0 0 6px #f59e0b' : 'none';
  return (
    <div style={{
      width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
      background: color,
      boxShadow: shadow,
      transition: 'background 0.3s, box-shadow 0.3s',
    }} />
  );
};

export default function Sidebar() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [health, setHealth] = useState<{
    api: string; db: string; redis: string; worker: string;
  } | null>(null);
  const [workerStats, setWorkerStats] = useState<{ active: number; pending: number } | null>(null);
  const [prevPathname, setPrevPathname] = useState(pathname);
  if (prevPathname !== pathname) {
    setPrevPathname(pathname);
    setIsOpen(false);
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    let isMounted = true;
    let timerId: NodeJS.Timeout;

    const check = async () => {
      if (!isMounted) return;

      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000);
        
        // 1. Check health: try apiBase, then fallback to relative '/api/health' if needed
        let res: Response | null = null;
        try {
          res = await fetch(`${apiBase}/api/health`, { signal: controller.signal });
        } catch {
          try {
            res = await fetch('/api/health', { signal: controller.signal });
          } catch {
            res = null;
          }
        }
        clearTimeout(timeoutId);
        
        if (res && res.ok) {
          const data = await res.json();
          if (isMounted) setHealth(data.components || { api: 'ok', db: 'ok', redis: 'ok', worker: 'online' });
        } else {
          if (isMounted) setHealth({ api: 'offline', db: 'unknown', redis: 'unknown', worker: 'unknown' });
        }

        // 2. Check stats: try apiBase, then fallback to relative '/api/jobs/stats'
        let statsRes: Response | null = null;
        try {
          statsRes = await fetch(`${apiBase}/api/jobs/stats`);
        } catch {
          try {
            statsRes = await fetch('/api/jobs/stats');
          } catch {
            statsRes = null;
          }
        }
        if (statsRes && statsRes.ok) {
          const statsData = await statsRes.json();
          if (isMounted && statsData?.queue) {
            setWorkerStats({
              active: statsData.queue.active ?? 0,
              pending: statsData.queue.pending ?? 0,
            });
          }
        }
      } catch {
        if (isMounted) setHealth({ api: 'offline', db: 'unknown', redis: 'unknown', worker: 'unknown' });
      }

      // Schedule next check only after this one completes
      if (isMounted) {
        timerId = setTimeout(check, 10000);
      }
    };

    check();
    return () => {
      isMounted = false;
      if (timerId) clearTimeout(timerId);
    };
  }, []);

  const isWorkerOk = health?.worker === 'online';

  return (
    <>
      {/* Mobile Topbar */}
      <header className="mobile-topbar" aria-label="Mobile navigation header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 30, height: 30, borderRadius: 8,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15,
          }}>⚡</div>
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: '#f1f5f9' }}>
            ClipForge
          </span>
        </div>
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          aria-expanded={isOpen}
          aria-label="Toggle navigation menu"
          style={{
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '6px 12px',
            color: '#fff',
            cursor: 'pointer',
            fontSize: 16,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {isOpen ? '✕' : '☰'}
        </button>
      </header>

      {/* Backdrop overlay for mobile drawer */}
      {isOpen && (
        <div
          className="mobile-drawer-backdrop"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside className={`sidebar${isOpen ? ' open' : ''}`} aria-label="Sidebar navigation">
        {/* Logo */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 6px', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, boxShadow: '0 0 20px rgba(99,102,241,0.4)'
              }}>⚡</div>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 18, color: '#f1f5f9' }}>
                ClipForge
              </span>
            </div>
            {isOpen && (
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close navigation menu"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontSize: 18,
                  padding: 4,
                }}
              >
                ✕
              </button>
            )}
          </div>
        
        {/* System Diagnostics */}
        <div style={{ 
          display: 'flex', flexDirection: 'column', gap: 6, padding: '10px', 
          background: 'rgba(0,0,0,0.2)', borderRadius: 8, fontSize: 10, color: '#94a3b8' 
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>API</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>{health ? health.api.toUpperCase() : 'CONNECTING...'}</span>
              <StatusDot status={health ? health.api : 'connecting'} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>Database</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>{health ? health.db.toUpperCase() : 'CONNECTING...'}</span>
              <StatusDot status={health ? health.db : 'connecting'} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>Redis</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>{health ? health.redis.toUpperCase() : 'CONNECTING...'}</span>
              <StatusDot status={health ? health.redis : 'connecting'} />
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {nav.map(item => (
          <Link
            key={item.href}
            href={item.href}
            className={`sidebar-link${pathname === item.href ? ' active' : ''}`}
          >
            <span style={{ fontSize: 16 }}>{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>

      {/* Bottom — Live Worker Status */}
      <div style={{ paddingTop: 16, borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{
          padding: '10px 12px', borderRadius: 10,
          background: !health ? 'rgba(99,102,241,0.06)' : isWorkerOk ? 'rgba(16,185,129,0.07)' : 'rgba(239,68,68,0.07)',
          border: `1px solid ${!health ? 'rgba(99,102,241,0.18)' : isWorkerOk ? 'rgba(16,185,129,0.18)' : 'rgba(239,68,68,0.18)'}`,
          transition: 'all 0.3s',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{
              fontSize: 11, fontWeight: 700, letterSpacing: '0.06em',
              color: !health ? '#a5b4fc' : isWorkerOk ? '#34d399' : '#f87171'
            }}>
              ⚙️ WORKER
            </span>
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
              padding: '2px 7px', borderRadius: 4,
              background: !health ? 'rgba(245,158,11,0.15)' : isWorkerOk ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)',
              color: !health ? '#fbbf24' : isWorkerOk ? '#6ee7b7' : '#fca5a5',
            }}>
              {!health ? 'CONNECTING...' : health.worker.toUpperCase()}
            </span>
          </div>

          {workerStats !== null ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              <div style={{
                textAlign: 'center', background: 'rgba(99,102,241,0.12)',
                borderRadius: 8, padding: '6px 0',
                border: '1px solid rgba(99,102,241,0.15)',
              }}>
                <div style={{
                  fontSize: 18, fontWeight: 800, color: '#818cf8',
                  fontFamily: "'Space Grotesk', sans-serif", lineHeight: 1,
                }}>
                  {workerStats.active}
                </div>
                <div style={{ fontSize: 9, color: '#64748b', marginTop: 3, letterSpacing: '0.05em' }}>ACTIVE</div>
              </div>
              <div style={{
                textAlign: 'center', background: 'rgba(245,158,11,0.10)',
                borderRadius: 8, padding: '6px 0',
                border: '1px solid rgba(245,158,11,0.15)',
              }}>
                <div style={{
                  fontSize: 18, fontWeight: 800, color: '#fbbf24',
                  fontFamily: "'Space Grotesk', sans-serif", lineHeight: 1,
                }}>
                  {workerStats.pending}
                </div>
                <div style={{ fontSize: 9, color: '#64748b', marginTop: 3, letterSpacing: '0.05em' }}>QUEUED</div>
              </div>
            </div>
          ) : (
            <div style={{ fontSize: 10, color: '#64748b', textAlign: 'center', padding: '6px 0' }}>
              Connecting to workers...
            </div>
          )}
        </div>

        <div style={{ fontSize: 11, color: '#334155', textAlign: 'center' }}>
          ClipForge v1.0 · AI Powered
        </div>
      </div>
    </aside>
    </>
  );
}
