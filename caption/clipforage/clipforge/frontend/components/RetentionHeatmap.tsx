'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getClipRetention, applyAutofix as apiApplyAutofix, getSfxPlan, generateSfxPlan, applySfxPlan, SFXPlan } from '@/lib/api';

interface DropoffRisk {
  start_time: number;
  end_time: number;
  reason: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  confidence_score: number;
  suggested_intervention_types: string[];
}

interface RetentionHeatmapProps {
  clipId: string;
}

export function RetentionHeatmap({ clipId }: RetentionHeatmapProps) {
  const [data, setData] = useState<{ overall_score: number; risks: DropoffRisk[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [autofixing, setAutofixing] = useState(false);
  const [applyingSfx, setApplyingSfx] = useState(false);

  const fetchRetentionData = useCallback(() => {
    setLoading(true);
    setError(null);
    setRetryCount((c) => c + 1);
  }, []);

  useEffect(() => {
    let ignore = false;
    getClipRetention(clipId)
      .then((json) => {
        if (!ignore) {
          setData(json);
          setError(null);
          setLoading(false);
        }
      })
      .catch((err: any) => {
        if (!ignore) {
          const msg = err?.message || '';
          if (msg.includes('404') || msg.includes('not found') || msg.includes('Clip or video file not found')) {
            setError('Retention data unavailable: clip media not yet rendered or processing.');
          } else {
            setError(err.message || 'Failed to load retention data');
          }
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [clipId, retryCount]);

  const applyAutofix = async () => {
    setAutofixing(true);
    try {
      const json = await apiApplyAutofix(clipId);
      alert(`Auto-fix variant rendering started with ${json.interventions} zoom interventions! You can preview it in the clip preview modal once complete.`);
    } catch (err: any) {
      alert(`Error applying Auto-fix: ${err.message}`);
    } finally {
      setAutofixing(false);
    }
  };

  const applySfx = async () => {
    setApplyingSfx(true);
    try {
      let plan: SFXPlan;
      try {
        plan = await getSfxPlan(clipId);
      } catch {
        plan = await generateSfxPlan(clipId);
      }
      if (!plan.placements || plan.placements.length === 0) {
        alert("No suitable sound-effect placements were found. The clip was not modified.");
        return;
      }
      const res = await applySfxPlan(clipId, plan);
      if (res.applied === false) {
        alert(res.message || "No suitable sound-effect placements were found. The clip was not modified.");
        return;
      }
      alert(`Auto-SFX applied! Task started. Note: This creates a new ClipVariant.`);
    } catch (err: any) {
      alert(`Error applying Auto-SFX: ${err.message}`);
    } finally {
      setApplyingSfx(false);
    }
  };


  if (loading) return <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', padding: 14 }}>Analyzing Retention Heatmap...</div>;
  if (error) return (
    <div style={{ fontSize: 12, color: '#ef4444', padding: 14 }}>
      Error: {error} 
      <button onClick={fetchRetentionData} style={{ marginLeft: 8, color: '#3b82f6', background: 'transparent', border: 'none', cursor: 'pointer' }}>Retry</button>
    </div>
  );
  if (!data) return null;

  return (
    <div style={{ background: 'rgba(59,130,246,0.05)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 12, padding: '16px', marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#60a5fa' }}>Retention Heatmap & Auto-Fix</div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', marginTop: 4 }}>
            Retention Health Score: <span style={{ fontWeight: 'bold', color: '#fff' }}>{(data.overall_score > 1.0 ? Math.min(100, Math.max(0, data.overall_score)) : Math.min(100, Math.max(0, data.overall_score * 100))).toFixed(0)} / 100</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button 
            onClick={applySfx}
            disabled={applyingSfx || data.risks.length === 0}
            style={{
              background: applyingSfx || data.risks.length === 0 ? 'rgba(255,255,255,0.1)' : '#8b5cf6',
              color: '#fff',
              border: 'none',
              padding: '8px 12px',
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 600,
              cursor: applyingSfx || data.risks.length === 0 ? 'not-allowed' : 'pointer',
            }}
          >
            {applyingSfx ? 'Applying...' : 'Auto-SFX'}
          </button>
          <button 
            onClick={applyAutofix}
            disabled={autofixing || data.risks.length === 0}
            style={{
              background: autofixing || data.risks.length === 0 ? 'rgba(255,255,255,0.1)' : '#2563eb',
              color: '#fff',
              border: 'none',
              padding: '8px 12px',
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 600,
              cursor: autofixing || data.risks.length === 0 ? 'not-allowed' : 'pointer',
            }}
          >
            {autofixing ? 'Applying...' : '1-Click Auto-Fix'}
          </button>
        </div>
      </div>

      <div>
        {data.risks.length === 0 ? (
          <div style={{ fontSize: 12, color: '#34d399' }}>No major drop-off risks detected!</div>
        ) : (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'rgba(255,255,255,0.8)' }}>Detected Drop-off Risk Zones</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.risks.map((risk, idx) => {
                const colors = {
                  critical: { bg: 'rgba(239,68,68,0.2)', text: '#f87171' },
                  high: { bg: 'rgba(249,115,22,0.2)', text: '#fb923c' },
                  medium: { bg: 'rgba(234,179,8,0.2)', text: '#facc15' },
                  low: { bg: 'rgba(113,113,122,0.2)', text: '#a1a1aa' },
                };
                const color = colors[risk.severity] || colors.low;
                
                return (
                  <div key={idx} style={{ 
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
                    background: 'rgba(0,0,0,0.3)', padding: '10px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ fontSize: 12, fontFamily: 'monospace', color: 'rgba(255,255,255,0.5)', width: 70 }}>
                        {risk.start_time.toFixed(1)}s - {risk.end_time.toFixed(1)}s
                      </div>
                      <div>
                        <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.9)' }}>{risk.reason}</div>
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginTop: 2 }}>Suggests: {risk.suggested_intervention_types.join(', ')}</div>
                      </div>
                    </div>
                    <div style={{ 
                      fontSize: 10, textTransform: 'uppercase', fontWeight: 700, 
                      background: color.bg, color: color.text, 
                      padding: '2px 6px', borderRadius: 4 
                    }}>
                      {risk.severity}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

