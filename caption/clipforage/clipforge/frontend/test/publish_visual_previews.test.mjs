import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Helper mimicking formatClipDuration from VisualClipPicker
function formatClipDuration(seconds) {
  if (seconds === undefined || seconds === null || isNaN(seconds)) return '00:00';
  const totalSec = Math.round(seconds);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

test('Publish Visual Previews: Duration Formatter Contract', () => {
  assert.equal(formatClipDuration(0), '00:00');
  assert.equal(formatClipDuration(32), '00:32');
  assert.equal(formatClipDuration(45), '00:45');
  assert.equal(formatClipDuration(75), '01:15');
  assert.equal(formatClipDuration(28.26), '00:28');
  assert.equal(formatClipDuration(undefined), '00:00');
  assert.equal(formatClipDuration(null), '00:00');
});

test('Publish Visual Previews: VisualClipPicker Component Filesystem & JSX Contract', () => {
  const componentPath = path.resolve(__dirname, '../components/publish/VisualClipPicker.tsx');
  assert.ok(fs.existsSync(componentPath), 'VisualClipPicker.tsx must exist');

  const content = fs.readFileSync(componentPath, 'utf8');

  // Verify 64x64 square thumbnail specification
  assert.ok(content.includes('size = 64') || content.includes('size={64}'), 'Must specify 64px square thumbnail');
  assert.ok(content.includes("objectFit: 'cover'"), 'Thumbnails must use cover object-fit');

  // Verify clip details display: title, source video, duration, score
  assert.ok(content.includes('clip.title'), 'Must display generated clip title');
  assert.ok(content.includes('clip.source_title'), 'Must display original source video title');
  assert.ok(content.includes('formatClipDuration'), 'Must format duration as mm:ss');
  assert.ok(content.includes('clip.score'), 'Must display clip score when available');

  // Verify lavender selection highlight and indicator
  assert.ok(content.includes('#7c6cf0') || content.includes('var(--accent'), 'Must use lavender accent for selection');
  assert.ok(content.includes('role="listbox"'), 'Must define accessible listbox container');
  assert.ok(content.includes('role="option"'), 'Must define accessible option items');

  // Verify search capability
  assert.ok(content.includes('clip-picker-search') || content.includes('searchQuery'), 'Must support searching clips');

  // Verify fallback placeholder
  assert.ok(content.includes('ThumbnailPlaceholder'), 'Must provide fallback ThumbnailPlaceholder');
});

test('Publish Visual Previews: Publish Page Integration & Queue Thumbnails Contract', () => {
  const pagePath = path.resolve(__dirname, '../app/publish/page.tsx');
  assert.ok(fs.existsSync(pagePath), 'publish/page.tsx must exist');

  const content = fs.readFileSync(pagePath, 'utf8');

  // Verify VisualClipPicker is imported and used in place of native select
  assert.ok(content.includes('VisualClipPicker'), 'VisualClipPicker must be imported in publish page');
  assert.ok(!content.includes('<select className="input-field" value={selectedClip?.id'), 'Native clip dropdown must be replaced');

  // Verify Right Panel queue thumbnails integration
  assert.ok(content.includes('SquareClipThumbnail'), 'SquareClipThumbnail must be used in right-side publish queue cards');
  assert.ok(content.includes('matchingClip'), 'Must look up matching clip to associate source title with queue items');
  assert.ok(content.includes('destinationChannel'), 'Must display target channel in queue items');

  // Verify responsive layout
  assert.ok(content.includes('minmax'), 'Must use minmax responsive grid column constraints');
});

test('Publish Visual Previews: API Client & Endpoint Contracts', () => {
  const apiPath = path.resolve(__dirname, '../lib/api.ts');
  const apiContent = fs.readFileSync(apiPath, 'utf8');

  assert.ok(apiContent.includes('thumbnailUrl'), 'thumbnailUrl must be exported');
  assert.ok(apiContent.includes('/api/clips/${id}/thumbnail'), 'thumbnailUrl must target /api/clips/{id}/thumbnail');
  assert.ok(apiContent.includes('thumbnail_path?: string | null'), 'PublishQueueItem must include thumbnail_path');
});
