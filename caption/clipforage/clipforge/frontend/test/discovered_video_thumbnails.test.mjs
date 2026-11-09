import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Helper function mirroring formatDurationTimestamp from YouTubeVideoThumbnail.tsx
function formatDurationTimestamp(seconds) {
  if (typeof seconds !== 'number' || isNaN(seconds) || seconds <= 0) {
    return null;
  }
  const totalSeconds = Math.round(seconds);
  const hrs = Math.floor(totalSeconds / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  const pad = (n) => n.toString().padStart(2, '0');

  if (hrs > 0) {
    return `${hrs}:${pad(mins)}:${pad(secs)}`;
  }
  return `${pad(mins)}:${pad(secs)}`;
}

// Helper function mirroring getYouTubeThumbnailCandidates from YouTubeVideoThumbnail.tsx
function getYouTubeThumbnailCandidates(videoId, providedUrl) {
  const candidates = [];

  if (providedUrl && providedUrl.trim().length > 0) {
    candidates.push(providedUrl.trim());
  }

  const cleanId = (videoId || '').trim();
  if (cleanId && !cleanId.startsWith('synth_') && !cleanId.startsWith('test_')) {
    const mq = `https://i.ytimg.com/vi/${cleanId}/mqdefault.jpg`;
    const hq = `https://i.ytimg.com/vi/${cleanId}/hqdefault.jpg`;

    if (!candidates.includes(mq)) candidates.push(mq);
    if (!candidates.includes(hq)) candidates.push(hq);
  }

  return candidates;
}

test('Discovered Videos: Duration Timestamp Formatter Contract', () => {
  assert.equal(formatDurationTimestamp(null), null);
  assert.equal(formatDurationTimestamp(undefined), null);
  assert.equal(formatDurationTimestamp(0), null);
  assert.equal(formatDurationTimestamp(-10), null);

  // Standard seconds
  assert.equal(formatDurationTimestamp(32), '00:32');
  assert.equal(formatDurationTimestamp(45.4), '00:45');

  // Video lengths in minutes (e.g. 716s from Nishant Chahar video)
  assert.equal(formatDurationTimestamp(716), '11:56');
  assert.equal(formatDurationTimestamp(1017), '16:57');

  // Multi-hour videos
  assert.equal(formatDurationTimestamp(3665), '1:01:05');
});

test('Discovered Videos: Thumbnail Candidate Resolution Hierarchy', () => {
  const videoId = 'UBHOWXL4Apg';
  const provided = 'https://i.ytimg.com/vi/UBHOWXL4Apg/hq720_custom_3.jpg';

  const candidates = getYouTubeThumbnailCandidates(videoId, provided);
  assert.equal(candidates.length, 3);
  assert.equal(candidates[0], provided);
  assert.equal(candidates[1], 'https://i.ytimg.com/vi/UBHOWXL4Apg/mqdefault.jpg');
  assert.equal(candidates[2], 'https://i.ytimg.com/vi/UBHOWXL4Apg/hqdefault.jpg');
});

test('Discovered Videos: Fallback to mqdefault when provided thumbnail is missing', () => {
  const videoId = 'Cm45rJ_ayA4';
  const candidates = getYouTubeThumbnailCandidates(videoId, null);

  assert.equal(candidates.length, 2);
  assert.equal(candidates[0], 'https://i.ytimg.com/vi/Cm45rJ_ayA4/mqdefault.jpg');
  assert.equal(candidates[1], 'https://i.ytimg.com/vi/Cm45rJ_ayA4/hqdefault.jpg');
});

test('Discovered Videos: Synthetic IDs safely avoid external YouTube requests', () => {
  const videoId = 'synth_vid01';
  const candidates = getYouTubeThumbnailCandidates(videoId, null);

  assert.equal(candidates.length, 0);
});

test('Discovered Videos: Component Filesystem and JSX Contract', () => {
  const compPath = path.resolve(__dirname, '../components/automation/YouTubeVideoThumbnail.tsx');
  assert.ok(fs.existsSync(compPath), 'YouTubeVideoThumbnail.tsx must exist');

  const compContent = fs.readFileSync(compPath, 'utf8');
  assert.ok(compContent.includes("aspectRatio: '16 / 9'"), 'Must enforce 16:9 aspect ratio');
  assert.ok(compContent.includes("objectFit: 'cover'"), 'Must use cover object-fit');
  assert.ok(compContent.includes('loading="lazy"'), 'Must specify lazy loading');
  assert.ok(compContent.includes('YouTubeThumbnailPlaceholder'), 'Must define neutral fallback placeholder');
  assert.ok(compContent.includes('e.stopPropagation()'), 'Must stop click propagation on thumbnail');

  const pagePath = path.resolve(__dirname, '../app/automation/page.tsx');
  const pageContent = fs.readFileSync(pagePath, 'utf8');
  assert.ok(pageContent.includes('YouTubeVideoThumbnail'), 'Automation page must integrate YouTubeVideoThumbnail');
  assert.ok(pageContent.includes('thumbnailUrl={v.thumbnail}'), 'Must bind v.thumbnail property');
  assert.ok(pageContent.includes('videoId={v.id}'), 'Must bind v.id property');
});
