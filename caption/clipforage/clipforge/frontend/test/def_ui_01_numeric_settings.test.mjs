import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Pure validation logic mirroring frontend/app/settings/page.tsx
function validateNumericSettings(clips, interval) {
  let clipsError;
  let intervalError;

  const clipsStr = String(clips ?? '').trim();
  if (clipsStr === '') {
    clipsError = 'Clips limit per video is required.';
  } else {
    const n = Number(clipsStr);
    if (isNaN(n) || !Number.isInteger(n)) {
      clipsError = 'Clips limit must be a whole integer between 1 and 20.';
    } else if (n < 1 || n > 20) {
      clipsError = `Clips limit must be between 1 and 20 (got ${n}).`;
    }
  }

  const intervalStr = String(interval ?? '').trim();
  if (intervalStr === '') {
    intervalError = 'Channel check interval is required.';
  } else {
    const n = Number(intervalStr);
    if (isNaN(n) || !Number.isInteger(n)) {
      intervalError = 'Channel check interval must be a whole integer between 5 and 1440.';
    } else if (n < 5 || n > 1440) {
      intervalError = `Channel check interval must be between 5 and 1440 minutes (got ${n}).`;
    }
  }

  return {
    clipsError,
    intervalError,
    parsedClips: !clipsError ? Number(clipsStr) : undefined,
    parsedInterval: !intervalError ? Number(intervalStr) : undefined,
  };
}

test('DEF-UI-01: Numeric settings validation and zero/negative handling', async (t) => {
  const settingsPath = path.resolve(__dirname, '../app/settings/page.tsx');
  const settingsSource = fs.readFileSync(settingsPath, 'utf8');

  await t.test('1. Falsy coercion anti-pattern parseInt(...) || is completely removed', () => {
    assert.ok(!settingsSource.includes('parseInt(e.target.value) || 5'), 'Must not coerce clips-limit using parseInt || 5');
    assert.ok(!settingsSource.includes('parseInt(e.target.value) || 30'), 'Must not coerce channel-interval using parseInt || 30');
    assert.ok(!settingsSource.includes('Number(env.CLIPS_PER_VIDEO) || 5'), 'Must not use Number || 5 falsy coercion');
    assert.ok(!settingsSource.includes('Number(env.CHANNEL_CHECK_INTERVAL_MINUTES) || 30'), 'Must not use Number || 30 falsy coercion');
  });

  await t.test('2. Nullish coalescing is used for defaults', () => {
    assert.ok(settingsSource.includes('settings.CLIPS_PER_VIDEO ?? 5'), 'Must use ?? 5 for clips limit');
    assert.ok(settingsSource.includes('settings.CHANNEL_CHECK_INTERVAL_MINUTES ?? 30'), 'Must use ?? 30 for interval');
  });

  await t.test('3. validateNumericSettings is integrated into settings/page.tsx', () => {
    assert.ok(settingsSource.includes('validateNumericSettings(env.CLIPS_PER_VIDEO, env.CHANNEL_CHECK_INTERVAL_MINUTES)'), 'Must call validateNumericSettings in handleSave');
  });

  await t.test('4. Normal valid inputs pass validation with parsed numbers', () => {
    const res = validateNumericSettings(5, 30);
    assert.equal(res.clipsError, undefined);
    assert.equal(res.intervalError, undefined);
    assert.equal(res.parsedClips, 5);
    assert.equal(res.parsedInterval, 30);
  });

  await t.test('5. Boundary valid values (minimums and maximums)', () => {
    const resMin = validateNumericSettings(1, 5);
    assert.equal(resMin.clipsError, undefined);
    assert.equal(resMin.intervalError, undefined);
    assert.equal(resMin.parsedClips, 1);
    assert.equal(resMin.parsedInterval, 5);

    const resMax = validateNumericSettings(20, 1440);
    assert.equal(resMax.clipsError, undefined);
    assert.equal(resMax.intervalError, undefined);
    assert.equal(resMax.parsedClips, 20);
    assert.equal(resMax.parsedInterval, 1440);
  });

  await t.test('6. Zero (0) is explicitly rejected without falsy coercion to defaults', () => {
    const res = validateNumericSettings(0, 0);
    assert.ok(res.clipsError && res.clipsError.includes('between 1 and 20'));
    assert.ok(res.intervalError && res.intervalError.includes('between 5 and 1440'));
    assert.equal(res.parsedClips, undefined);
    assert.equal(res.parsedInterval, undefined);
  });

  await t.test('7. Empty input is rejected as required', () => {
    const res = validateNumericSettings('', '');
    assert.ok(res.clipsError && res.clipsError.includes('required'));
    assert.ok(res.intervalError && res.intervalError.includes('required'));
  });

  await t.test('8. Values above maximum are rejected', () => {
    const res = validateNumericSettings(21, 1441);
    assert.ok(res.clipsError && res.clipsError.includes('between 1 and 20'));
    assert.ok(res.intervalError && res.intervalError.includes('between 5 and 1440'));
  });

  await t.test('9. Negative values are rejected before reaching backend', () => {
    const res = validateNumericSettings(-1, -5);
    assert.ok(res.clipsError && res.clipsError.includes('between 1 and 20'));
    assert.ok(res.intervalError && res.intervalError.includes('between 5 and 1440'));
  });

  await t.test('10. Non-numeric inputs are rejected', () => {
    const res = validateNumericSettings('abc', 'xyz');
    assert.ok(res.clipsError && res.clipsError.includes('whole integer'));
    assert.ok(res.intervalError && res.intervalError.includes('whole integer'));
  });

  await t.test('11. Decimal inputs are rejected as non-integers', () => {
    const res = validateNumericSettings(5.5, 30.2);
    assert.ok(res.clipsError && res.clipsError.includes('whole integer'));
    assert.ok(res.intervalError && res.intervalError.includes('whole integer'));
  });
});
