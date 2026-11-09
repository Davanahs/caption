'use client';

/**
 * LayoutThumbnailSelector
 * 
 * Canonical visual layout thumbnail selector component for ClipForge.
 * Re-exports the reference implementation from '@/components/automation/LayoutPreviewSelector'
 * ensuring standard, consistent visual layout selection across the entire application.
 */

export {
  default,
  default as LayoutThumbnailSelector,
  default as LayoutPreviewSelector,
  resolveLayoutOptionId,
  LAYOUT_OPTIONS,
} from './automation/LayoutPreviewSelector';

export type {
  LayoutPreviewSelectorProps,
  LayoutPreviewSelectorProps as LayoutThumbnailSelectorProps,
  LayoutOption,
} from './automation/LayoutPreviewSelector';
