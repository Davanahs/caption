import test from 'node:test';
import assert from 'node:assert/strict';

const DEFAULT_API_BASE = 'http://localhost:8000';

function getApiBase() {
  return process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE;
}

function buildClipsQuery(params) {
  if (!params) return '/api/clips';
  const filtered = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  );
  const q = new URLSearchParams(filtered).toString();
  return `/api/clips${q ? '?' + q : ''}`;
}

function buildDownloadUrl(clipId) {
  return `${getApiBase()}/api/clips/${clipId}/download`;
}

function buildThumbnailUrl(clipId) {
  return `${getApiBase()}/api/clips/${clipId}/thumbnail`;
}

function buildUploadFormData(payload) {
  const form = new FormData();
  form.append('url', payload.url);
  if (payload.numClips !== undefined) form.append('num_clips', payload.numClips.toString());
  if (payload.maxClipDuration !== undefined) form.append('max_clip_duration', payload.maxClipDuration.toString());
  if (payload.reframeMode !== undefined) form.append('reframe_mode', payload.reframeMode);
  if (payload.hookTitle !== undefined) form.append('hook_title', payload.hookTitle ? 'true' : 'false');
  form.append('enable_broll', payload.enableBroll ? 'true' : 'false');
  form.append('enable_hook', payload.enableHook ? 'true' : 'false');
  if (payload.destinationIds && payload.destinationIds.length > 0) {
    form.append('destination_ids', JSON.stringify(payload.destinationIds));
  }
  return form;
}

test('API Contract: Base URL falls back to localhost:8000 when unset', () => {
  const originalEnv = process.env.NEXT_PUBLIC_API_URL;
  delete process.env.NEXT_PUBLIC_API_URL;
  assert.equal(getApiBase(), 'http://localhost:8000');
  if (originalEnv !== undefined) {
    process.env.NEXT_PUBLIC_API_URL = originalEnv;
  } else {
    delete process.env.NEXT_PUBLIC_API_URL;
  }
});

test('API Contract: Download and Thumbnail URLs construct canonical endpoint paths', () => {
  const clipId = 'c123-test-uuid';
  assert.equal(buildDownloadUrl(clipId), 'http://localhost:8000/api/clips/c123-test-uuid/download');
  assert.equal(buildThumbnailUrl(clipId), 'http://localhost:8000/api/clips/c123-test-uuid/thumbnail');
});

test('API Contract: Clips query string builder serializes only defined filter params', () => {
  assert.equal(buildClipsQuery(), '/api/clips');
  assert.equal(buildClipsQuery({}), '/api/clips');
  assert.equal(
    buildClipsQuery({ video_id: 'vid-456' }),
    '/api/clips?video_id=vid-456'
  );
  assert.equal(
    buildClipsQuery({ video_id: 'vid-456', from_date: '2026-01-01', to_date: '2026-01-31' }),
    '/api/clips?video_id=vid-456&from_date=2026-01-01&to_date=2026-01-31'
  );
  // Undefined or empty values must be omitted
  assert.equal(
    buildClipsQuery({ video_id: 'vid-456', from_date: undefined, to_date: '' }),
    '/api/clips?video_id=vid-456'
  );
});

test('API Contract: Upload form data maps options accurately to backend fields', () => {
  const formData = buildUploadFormData({
    url: 'https://youtube.com/watch?v=dQw4w9WgXcQ',
    numClips: 5,
    maxClipDuration: 28,
    reframeMode: 'center_crop',
    hookTitle: true,
    enableBroll: false,
    enableHook: true,
    destinationIds: ['dest-1', 'dest-2'],
  });

  assert.equal(formData.get('url'), 'https://youtube.com/watch?v=dQw4w9WgXcQ');
  assert.equal(formData.get('num_clips'), '5');
  assert.equal(formData.get('max_clip_duration'), '28');
  assert.equal(formData.get('reframe_mode'), 'center_crop');
  assert.equal(formData.get('hook_title'), 'true');
  assert.equal(formData.get('enable_broll'), 'false');
  assert.equal(formData.get('enable_hook'), 'true');
  assert.equal(formData.get('destination_ids'), JSON.stringify(['dest-1', 'dest-2']));
});
