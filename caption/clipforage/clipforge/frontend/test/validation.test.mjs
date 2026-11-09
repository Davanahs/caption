import test from 'node:test';
import assert from 'node:assert/strict';

// Helper matching frontend YouTube URL parsing logic
function extractYouTubeVideoId(url) {
  if (!url || typeof url !== 'string') return null;
  const match = url.match(
    /(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/|live\/))([a-zA-Z0-9_-]{11})/
  );
  return match ? match[1] : null;
}

// Helper matching Shorts duration restriction (< 30.0s)
function validateShortDuration(durationSeconds) {
  if (typeof durationSeconds !== 'number' || isNaN(durationSeconds)) {
    return { valid: false, error: 'Duration must be a valid number' };
  }
  if (durationSeconds <= 0) {
    return { valid: false, error: 'Duration must be greater than 0' };
  }
  if (durationSeconds >= 30.0) {
    return { valid: false, error: 'Short duration must be strictly less than 30.0 seconds' };
  }
  return { valid: true };
}

// Helper matching schedule date validation logic
function validateScheduleDate(dateString) {
  if (!dateString) {
    return { valid: true, scheduled: false }; // Immediate release
  }
  const date = new Date(dateString);
  if (isNaN(date.getTime())) {
    return { valid: false, error: 'Invalid date format' };
  }
  if (date.getTime() <= Date.now()) {
    return { valid: false, error: 'Scheduled date must be in the future' };
  }
  return { valid: true, scheduled: true, iso: date.toISOString() };
}

// Helper matching tag parsing in publish/page.tsx
function parseTags(tagsString) {
  if (!tagsString || typeof tagsString !== 'string') return [];
  return tagsString
    .split(',')
    .map(t => t.trim())
    .filter(t => t.length > 0);
}

test('Validation: YouTube URL extraction across standard URL formats', () => {
  const validCases = [
    { url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', expected: 'dQw4w9WgXcQ' },
    { url: 'https://youtu.be/dQw4w9WgXcQ', expected: 'dQw4w9WgXcQ' },
    { url: 'https://www.youtube.com/shorts/dQw4w9WgXcQ', expected: 'dQw4w9WgXcQ' },
    { url: 'https://youtube.com/live/dQw4w9WgXcQ', expected: 'dQw4w9WgXcQ' },
    { url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s', expected: 'dQw4w9WgXcQ' },
    { url: 'https://www.youtube.com/embed/dQw4w9WgXcQ', expected: 'dQw4w9WgXcQ' },
  ];

  for (const { url, expected } of validCases) {
    assert.equal(extractYouTubeVideoId(url), expected, `Failed to extract ID from: ${url}`);
  }

  const invalidCases = [
    'https://vimeo.com/123456789',
    'https://tiktok.com/@user/video/123',
    'https://google.com',
    'not-a-valid-url',
    '',
    null,
    undefined,
  ];

  for (const url of invalidCases) {
    assert.equal(extractYouTubeVideoId(url), null, `Expected null for invalid URL: ${url}`);
  }
});

test('Validation: Shorts duration boundary strictly enforces < 30.0s', () => {
  assert.equal(validateShortDuration(29.99).valid, true);
  assert.equal(validateShortDuration(15.0).valid, true);
  assert.equal(validateShortDuration(5.2).valid, true);

  // Exact 30.0s boundary and above must fail
  assert.equal(validateShortDuration(30.0).valid, false);
  assert.equal(validateShortDuration(30.01).valid, false);
  assert.equal(validateShortDuration(60.0).valid, false);
  assert.equal(validateShortDuration(0).valid, false);
  assert.equal(validateShortDuration(-5).valid, false);
  assert.equal(validateShortDuration(NaN).valid, false);
});

test('Validation: Schedule date must reject past dates and accept future ISO strings', () => {
  const pastDate = new Date(Date.now() - 3600000).toISOString();
  const futureDate = new Date(Date.now() + 86400000).toISOString();

  assert.equal(validateScheduleDate(pastDate).valid, false);
  assert.equal(validateScheduleDate(futureDate).valid, true);
  assert.equal(validateScheduleDate('').valid, true); // Immediate release is valid
  assert.equal(validateScheduleDate('not-a-date').valid, false);
});

test('Validation: Publish tags parsing splits and trims comma-separated input', () => {
  assert.deepEqual(parseTags('gaming, shorts, viral'), ['gaming', 'shorts', 'viral']);
  assert.deepEqual(parseTags(' single '), ['single']);
  assert.deepEqual(parseTags(''), []);
  assert.deepEqual(parseTags('  ,  ,,  '), []);
  assert.deepEqual(parseTags('tag1, tag2,tag3'), ['tag1', 'tag2', 'tag3']);
});
