import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('PodcastSelectionModal Component & Workflow Contract', async (t) => {
  const modalPath = path.resolve(__dirname, '../components/PodcastSelectionModal.tsx');
  const podcastsPagePath = path.resolve(__dirname, '../app/podcasts/page.tsx');
  const dashboardPagePath = path.resolve(__dirname, '../app/page.tsx');
  const apiPath = path.resolve(__dirname, '../lib/api.ts');

  assert.ok(fs.existsSync(modalPath), 'PodcastSelectionModal.tsx must exist');
  assert.ok(fs.existsSync(podcastsPagePath), 'app/podcasts/page.tsx must exist');
  assert.ok(fs.existsSync(dashboardPagePath), 'app/page.tsx must exist');
  assert.ok(fs.existsSync(apiPath), 'lib/api.ts must exist');

  const modalSource = fs.readFileSync(modalPath, 'utf8');
  const podcastsPageSource = fs.readFileSync(podcastsPagePath, 'utf8');
  const dashboardSource = fs.readFileSync(dashboardPagePath, 'utf8');
  const apiSource = fs.readFileSync(apiPath, 'utf8');

  await t.test('1. Modal exports default React component and types', () => {
    assert.ok(modalSource.includes('export default function PodcastSelectionModal'), 'Must export default component');
    assert.ok(modalSource.includes('export interface PodcastProcessingConfig'), 'Must export config interface');
  });

  await t.test('2. Modal has YouTube player embed and preview metadata', () => {
    assert.ok(modalSource.includes('https://www.youtube-nocookie.com/embed/'), 'Must use privacy-enhanced embed URL');
    assert.ok(modalSource.includes('https://img.youtube.com/vi/'), 'Must display video thumbnail from YouTube CDN');
    assert.ok(modalSource.includes('1. Paste YouTube Link'), 'Must have Step 1 header matching reference');
  });

  await t.test('3. Area selection overlay supports bounding boxes, handles, and labels', () => {
    assert.ok(modalSource.includes('2. Select Areas for Clipping'), 'Must have Step 2 header matching reference');
    assert.ok(modalSource.includes('Add Another Area'), 'Must have Add Another Area action');
    assert.ok(modalSource.includes('Adjust'), 'Must have Adjust button for areas');
    assert.ok(modalSource.includes('Clear Areas'), 'Must support clearing areas');
    assert.ok(modalSource.includes('nw'), 'Must have corner resize handles');
    assert.ok(modalSource.includes('se'), 'Must have corner resize handles');
  });

  await t.test('4. Mode toggle enables clean switching between playback and area editing', () => {
    assert.ok(modalSource.includes('Select & Adjust Areas'), 'Must have edit mode toggle');
    assert.ok(modalSource.includes('Watch & Play Video'), 'Must have playback mode toggle');
    assert.ok(modalSource.includes("pointerEvents: interactionMode === 'playback' ? 'auto' : 'none'"), 'Must toggle iframe pointer events');
  });

  await t.test('5. Step 3 Clip Settings has duration, composition, and Generate Clips CTA', () => {
    assert.ok(modalSource.includes('3. Clip Settings'), 'Must have Step 3 header');
    assert.ok(modalSource.includes('Stacked Split (2 Speakers) [9:16]'), 'Must support 2-speaker stacked composition');
    assert.ok(modalSource.includes('30s (Recommended)'), 'Must have 30s recommended duration option');
    assert.ok(modalSource.includes('Generate Clips'), 'Must have Generate Clips CTA');
  });

  await t.test('6. Selected Areas Preview displays vertical 9:16 layout representation', () => {
    assert.ok(modalSource.includes('Selected Areas Preview'), 'Must have Selected Areas Preview title');
    assert.ok(modalSource.includes('Both speaker areas will be cropped and stacked'), 'Must explain stacked framing');
  });

  await t.test('7. Bottom 5-step numbered workflow cards match visual reference', () => {
    assert.ok(modalSource.includes('1. Paste YouTube Link'), 'Must have card 1');
    assert.ok(modalSource.includes('2. Watch & Select Areas'), 'Must have card 2');
    assert.ok(modalSource.includes('3. Set Clip Options'), 'Must have card 3');
    assert.ok(modalSource.includes('4. AI Processing'), 'Must have card 4');
    assert.ok(modalSource.includes('5. Get Your Clips'), 'Must have card 5');
  });

  await t.test('8. Dashboard page integrates entry points and handles submission', () => {
    assert.ok(dashboardSource.includes('podcast-interview-mode-btn'), 'Must have visible podcast intake button');
    assert.ok(dashboardSource.includes('podcast-quick-launch-link'), 'Must have quick launch link');
    assert.ok(dashboardSource.includes('PodcastSelectionModal'), 'Must mount PodcastSelectionModal');
    assert.ok(dashboardSource.includes('confirmAndProcessPodcast'), 'Must have submission handler');
  });

  await t.test('9. API client serializes regions and podcast_composition', () => {
    assert.ok(apiSource.includes('regions'), 'SubmitYouTubeOptions must include regions');
    assert.ok(apiSource.includes('podcastComposition'), 'SubmitYouTubeOptions must include podcastComposition');
  });

  await t.test('10. Frame preview endpoint client integration and status badge', () => {
    assert.ok(apiSource.includes('export function getVideoFrameUrl'), 'lib/api.ts must export getVideoFrameUrl');
    assert.ok(modalSource.includes('getVideoFrameUrl'), 'PodcastSelectionModal must call getVideoFrameUrl');
    assert.ok(modalSource.includes('frame-preview-status-badge'), 'Modal must have frame-preview-status-badge');
    assert.ok(modalSource.includes('Real Frame @'), 'Modal must show real frame badge text');
    assert.ok(modalSource.includes('Geometry Fallback'), 'Modal must show fallback badge when frame unavailable');
  });

  await t.test('11. Shot table row keyboard accessibility and race cancellation', () => {
    assert.ok(modalSource.includes('role="button"'), 'Shot table rows must have role="button"');
    assert.ok(modalSource.includes('tabIndex={0}'), 'Shot table rows must be keyboard focusable');
    assert.ok(modalSource.includes('onKeyDown'), 'Shot table rows must support keyboard selection');
    assert.ok(modalSource.includes('AbortController'), 'Modal must use AbortController to cancel in-flight frame requests');
  });
});

