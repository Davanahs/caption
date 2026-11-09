'use client';

import React from 'react';
import { LAYOUT_PREVIEW_IMAGES } from './layoutPreviewImages';

export interface LayoutPreviewSelectorProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  title?: string;
  subtitle?: string;
  badge?: string;
  className?: string;
}

export interface LayoutOption {
  id: string;
  aliases: string[];
  name: string;
  subtitle: string;
  description: string;
  badge?: string;
  renderPreview: (selected: boolean) => React.ReactNode;
}

export const LAYOUT_OPTIONS: LayoutOption[] = [
  // ── 1. Crop — Tight vertical 9:16 framing ──────────────────────────────────
  {
    id: 'center_crop',
    aliases: ['crop', 'center_crop'],
    name: 'Crop',
    subtitle: 'Tight vertical crop (9:16)',
    description: 'Tight vertical crop (9:16).',
    renderPreview: () => (
      <img
        src={LAYOUT_PREVIEW_IMAGES['center_crop']}
        alt="Crop layout preview — Tight vertical crop (9:16)"
        style={{
          maxHeight: 96,
          width: 'auto',
          maxWidth: '100%',
          objectFit: 'contain',
          borderRadius: 4,
          boxShadow: '0 3px 10px rgba(0, 0, 0, 0.55)',
          display: 'block',
        }}
      />
    ),
  },

  // ── 2. Blur — Centered video with blurred background ───────────────────────
  {
    id: 'fill_blur',
    aliases: ['fill_blur', 'blur_background', 'blur'],
    name: 'Blur',
    subtitle: 'Full frame centered with blurred top/bottom',
    description: 'Full frame centered with blurred top/bottom.',
    renderPreview: () => (
      <img
        src={LAYOUT_PREVIEW_IMAGES['fill_blur']}
        alt="Blur layout preview — Full frame centered with blurred top/bottom"
        style={{
          maxHeight: 96,
          width: 'auto',
          maxWidth: '100%',
          objectFit: 'contain',
          borderRadius: 4,
          boxShadow: '0 3px 10px rgba(0, 0, 0, 0.55)',
          display: 'block',
        }}
      />
    ),
  },

  // ── 3. Split — Two speakers side by side ───────────────────────────────────
  {
    id: 'split_screen',
    aliases: ['split_screen', 'split'],
    name: 'Split',
    subtitle: 'Two speakers side by side (9:16)',
    description: 'Two speakers side by side (9:16).',
    renderPreview: () => (
      <img
        src={LAYOUT_PREVIEW_IMAGES['split_screen']}
        alt="Split layout preview — Two speakers side by side (9:16)"
        style={{
          maxHeight: 96,
          width: 'auto',
          maxWidth: '100%',
          objectFit: 'contain',
          borderRadius: 4,
          boxShadow: '0 3px 10px rgba(0, 0, 0, 0.55)',
          display: 'block',
        }}
      />
    ),
  },

  // ── 4. Multi Split — Four speakers in a 2x2 grid ───────────────────────────
  {
    id: 'multi_split',
    aliases: ['multi_split'],
    name: 'Multi Split',
    subtitle: 'Four speakers in a 2x2 grid (9:16)',
    description: 'Four speakers in a 2x2 grid (9:16).',
    renderPreview: () => (
      <img
        src={LAYOUT_PREVIEW_IMAGES['multi_split']}
        alt="Multi Split layout preview — Four speakers in a 2x2 grid (9:16)"
        style={{
          maxHeight: 96,
          width: 'auto',
          maxWidth: '100%',
          objectFit: 'contain',
          borderRadius: 4,
          boxShadow: '0 3px 10px rgba(0, 0, 0, 0.55)',
          display: 'block',
        }}
      />
    ),
  },

  // ── 5. Stacked — Two speakers arranged vertically ──────────────────────────
  {
    id: 'stacked_16_9',
    aliases: ['stacked_16_9', 'stacked'],
    name: 'Stacked',
    subtitle: 'Two speakers stacked (9:16)',
    description: 'Two speakers stacked (9:16).',
    renderPreview: () => (
      <img
        src={LAYOUT_PREVIEW_IMAGES['stacked_16_9']}
        alt="Stacked layout preview — Two speakers stacked (9:16)"
        style={{
          maxHeight: 96,
          width: 'auto',
          maxWidth: '100%',
          objectFit: 'contain',
          borderRadius: 4,
          boxShadow: '0 3px 10px rgba(0, 0, 0, 0.55)',
          display: 'block',
        }}
      />
    ),
  },

  // ── 6. Transform — AI-tracked dynamic framing ──────────────────────────────
  {
    id: 'creative_transform',
    aliases: ['creative_transform', 'transform'],
    name: 'Transform',
    subtitle: 'AI tracked layout (dynamic framing)',
    description: 'AI tracked layout (dynamic framing).',
    renderPreview: () => (
      <img
        src={LAYOUT_PREVIEW_IMAGES['creative_transform']}
        alt="Transform layout preview — AI tracked layout (dynamic framing)"
        style={{
          maxHeight: 96,
          width: 'auto',
          maxWidth: '100%',
          objectFit: 'contain',
          borderRadius: 4,
          boxShadow: '0 3px 10px rgba(0, 0, 0, 0.55)',
          display: 'block',
        }}
      />
    ),
  },
];

// Helper to resolve any incoming value to one of the 6 canonical IDs
export function resolveLayoutOptionId(val: string | undefined): string {
  if (!val) return 'center_crop';
  const clean = val.toLowerCase().trim();
  for (const opt of LAYOUT_OPTIONS) {
    if (opt.id === clean || opt.aliases.includes(clean)) {
      return opt.id;
    }
  }
  if (clean === 'fit_black' || clean === 'static_wide') {
    return 'fill_blur';
  }
  return 'center_crop';
}

export default function LayoutPreviewSelector({
  value,
  onChange,
  disabled = false,
  title = 'Layout Mode (Reframe)',
  subtitle = 'Choose a layout to preview how your clip will be framed.',
  badge = '9:16 Shorts',
  className = '',
}: LayoutPreviewSelectorProps) {
  const selectedId = resolveLayoutOptionId(value);

  const handleSelect = (id: string) => {
    if (disabled) return;
    onChange(id);
  };

  const handleKeyDown = (e: React.KeyboardEvent, id: string) => {
    if (disabled) return;
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      onChange(id);
    }
  };

  return (
    <div className={`layout-preview-selector-container ${className}`.trim()} style={{ width: '100%' }}>
      {/* Header with info matching reference design */}
      {(title || subtitle || badge) && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
            {title && (
              <h3 style={{ fontSize: 14, fontWeight: 600, color: '#f8fafc', margin: 0, letterSpacing: '-0.01em' }}>
                {title}
              </h3>
            )}
            {badge && (
              <span
                style={{
                  fontSize: 10,
                  color: '#818cf8',
                  background: 'rgba(99, 102, 241, 0.12)',
                  padding: '1px 6px',
                  borderRadius: 4,
                  fontWeight: 500,
                }}
              >
                {badge}
              </span>
            )}
          </div>
          {subtitle && (
            <p style={{ fontSize: 11.5, color: '#94a3b8', margin: 0, lineHeight: 1.3 }}>
              {subtitle}
            </p>
          )}
        </div>
      )}

      {/* 6-Card Responsive Grid (3 columns x 2 rows on desktop) */}
      <div
        role="radiogroup"
        aria-label={title || 'Layout Mode (Reframe)'}
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 8,
          marginBottom: 8,
        }}
      >
        {LAYOUT_OPTIONS.map((opt) => {
          const isSelected = selectedId === opt.id;

          return (
            <div
              key={opt.id}
              role="radio"
              aria-checked={isSelected}
              tabIndex={disabled ? -1 : 0}
              onClick={() => handleSelect(opt.id)}
              onKeyDown={(e) => handleKeyDown(e, opt.id)}
              aria-label={`${opt.name} — ${opt.description}`}
              style={{
                background: '#0e1526',
                border: isSelected ? '2px solid #7c6cf0' : '1px solid #1e293b',
                borderRadius: 8,
                padding: '8px 8px 6px',
                cursor: disabled ? 'not-allowed' : 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'stretch',
                justifyContent: 'space-between',
                transition: 'border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease',
                boxShadow: isSelected
                  ? '0 0 0 1px rgba(124, 108, 240, 0.35), 0 4px 14px rgba(124, 108, 240, 0.18)'
                  : 'none',
                opacity: disabled ? 0.6 : 1,
                outline: 'none',
                userSelect: 'none',
              }}
              onMouseEnter={(e) => {
                if (!isSelected && !disabled) {
                  e.currentTarget.style.borderColor = '#334155';
                  e.currentTarget.style.background = '#111a2e';
                }
              }}
              onMouseLeave={(e) => {
                if (!isSelected && !disabled) {
                  e.currentTarget.style.borderColor = '#1e293b';
                  e.currentTarget.style.background = '#0e1526';
                }
              }}
            >
              {/* Visual Preview Thumbnail Area */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: 100,
                  marginBottom: 6,
                  overflow: 'hidden',
                }}
              >
                {opt.renderPreview(isSelected)}
              </div>

              {/* Bottom Info Row: Title, Description, and Radio Indicator */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: 6,
                  width: '100%',
                }}
              >
                {/* Left: Name & Description */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 11.5,
                      fontWeight: 600,
                      color: isSelected ? '#ffffff' : '#f8fafc',
                      marginBottom: 1,
                    }}
                  >
                    {opt.name}
                  </div>
                  <div
                    style={{
                      fontSize: 9.5,
                      color: '#94a3b8',
                      lineHeight: 1.2,
                    }}
                  >
                    {opt.description}
                  </div>
                </div>

                {/* Right: Radio Button matching reference design */}
                <div
                  style={{
                    width: 14,
                    height: 14,
                    borderRadius: '50%',
                    border: isSelected ? '2px solid #7c6cf0' : '1.5px solid #475569',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: 1,
                    transition: 'all 0.15s ease',
                    background: 'transparent',
                  }}
                >
                  {isSelected && (
                    <div
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: '#818cf8',
                      }}
                    />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Active selection configuration footer */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '4px 10px',
          borderRadius: 6,
          background: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid #1e293b',
          fontSize: 10.5,
        }}
      >
        <span style={{ color: '#94a3b8' }}>
          Active Layout: <strong style={{ color: '#f8fafc' }}>
            {LAYOUT_OPTIONS.find((o) => o.id === selectedId)?.name}
          </strong> — {LAYOUT_OPTIONS.find((o) => o.id === selectedId)?.description}
        </span>
        <span style={{ color: '#818cf8', fontSize: 10, fontFamily: 'monospace' }}>
          config: {selectedId}
        </span>
      </div>
    </div>
  );
}

export { LayoutPreviewSelector as LayoutThumbnailSelector };
