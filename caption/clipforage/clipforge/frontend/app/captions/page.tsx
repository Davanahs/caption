'use client';

import React, { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

function CaptionsFrame() {
  const searchParams = useSearchParams();
  const queryString = searchParams ? searchParams.toString() : '';
  const iframeSrc = queryString ? `/caption/index.html?${queryString}` : '/caption/index.html';

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
        src={iframeSrc}
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

export default function CaptionsPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, color: '#94a3b8' }}>Loading Caption Studio...</div>}>
      <CaptionsFrame />
    </Suspense>
  );
}
