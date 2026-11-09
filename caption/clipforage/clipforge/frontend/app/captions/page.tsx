'use client';

import React from 'react';

export default function CaptionsPage() {
  return (
    <div
      style={{
        width: 'calc(100% + 64px)',
        height: '100vh',
        margin: '-32px',
        overflow: 'hidden',
        position: 'relative',
        background: '#0B0813',
      }}
    >
      <iframe
        src="/caption/index.html"
        style={{
          width: '100%',
          height: '100%',
          border: 'none',
          display: 'block',
          background: '#0B0813',
        }}
        title="Caption Forge"
        allow="microphone; camera; autoplay; encrypted-media; fullscreen"
      />
    </div>
  );
}
