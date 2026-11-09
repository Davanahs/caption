'use client';

import React from 'react';

const SCORE_LABEL = (s: number) =>
    s >= 8.5 ? { label: '🔥 Viral', color: '#10b981' }
  : s >= 7  ? { label: '⚡ High',  color: '#f59e0b' }
  : s >= 5  ? { label: '👍 Good',  color: '#6366f1' }
  :           { label: '💤 Low',   color: '#6b7280' };

export interface ScoreRingProps {
  score: number;
}

export default function ScoreRing({ score }: ScoreRingProps) {
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
