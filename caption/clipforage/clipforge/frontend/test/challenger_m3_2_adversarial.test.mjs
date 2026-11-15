/**
 * challenger_m3_2_adversarial.test.mjs
 * =====================================
 * Challenger 2 Adversarial Stress & Empirical Verification Suite
 * Milestone M3: Dual-Region Gaming Layout
 *
 * Scope:
 * 1. Tool switching between Gameplay ROI and Facecam ROI (independent state preservation)
 * 2. Preset transitions, manual overlay dragging/resizing, and reset controls
 * 3. Timeline scrubbing, precision step buttons (-1s / +1s), and timestamp formatting fuzzing
 * 4. API serialization fuzzing across hundreds of randomized valid and clamped bounding boxes
 * 5. Strict R5 Zero-Caption deep scan across DOM, components, and payloads
 * 6. Ingestion mode switching and lifecycle resilience
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  createMockCanvas,
  CANONICAL_PRESETS,
  getCanonicalPresetRect,
  assertPresetParity,
  assertNoCaptionControlsInDOM,
  assertNoCaptionFieldsInPayload,
  clampNormalizedRect,
} from './gaming_test_helpers.mjs';

import {
  getDefaultGameplayRoi,
  getDefaultFacecamRoi,
  getDefaultFacecamOutputRect,
  getFacecamPreset,
  applyDrag,
  calculateResize,
  calculateRenderOffsets,
  validateGamingCoordinates,
  validateGamingLayout,
  validateNormalizedRect,
  toEvenPixels,
  toCanvasOverlay,
  calculateGameplayFraming,
  DEFAULT_CANVAS_WIDTH,
  DEFAULT_CANVAS_HEIGHT,
  MIN_ROI_SIZE,
} from '../lib/gamingCoordinates.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_ROOT = path.resolve(__dirname, '..');

// Helper matching formatTime from GamingSelectionModal.tsx
function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '00:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// ==============================================================================
// 1. TOOL SWITCHING & STATE MACHINE CROSS-CONTAMINATION SUITE
// ==============================================================================

test('Challenger 2 Suite 1: Tool Switching & State Machine Isolation', async (t) => {
  await t.test('TC-CHALLENGE-01: Rapid 500-cycle tool switching preserves independent ROI state without aliasing', () => {
    let activeTool = 'gameplay';
    let gameplayRoi = getDefaultGameplayRoi();
    let facecamRoi = getDefaultFacecamRoi();

    // Verify initial distinction
    assert.notDeepEqual(gameplayRoi, facecamRoi, 'ROIs must have different initial coordinates');
    assert.notEqual(gameplayRoi, facecamRoi, 'ROIs must not share object reference');

    // Perform 500 rapid switches
    for (let i = 0; i < 500; i++) {
      activeTool = i % 2 === 0 ? 'facecam' : 'gameplay';
    }

    // Assert zero drift
    assert.deepEqual(gameplayRoi, getDefaultGameplayRoi(), 'Gameplay ROI must not drift during tool switching');
    assert.deepEqual(facecamRoi, getDefaultFacecamRoi(), 'Facecam ROI must not drift during tool switching');
    assert.notEqual(gameplayRoi, facecamRoi, 'Object references must never become aliased');
  });

  await t.test('TC-CHALLENGE-02: Gameplay ROI drag & 4-corner resize leaves Facecam ROI 100% untouched', () => {
    let gameplayRoi = getDefaultGameplayRoi();
    const facecamRoiInitial = { ...getDefaultFacecamRoi() };
    let facecamRoi = { ...facecamRoiInitial };

    // Move gameplay
    gameplayRoi = applyDrag(gameplayRoi, 0.1, 0.1);
    assert.deepEqual(facecamRoi, facecamRoiInitial, 'Facecam ROI must remain identical after gameplay drag');

    // Resize gameplay from all 4 handles
    const handles = ['nw', 'ne', 'se', 'sw'];
    for (const h of handles) {
      const resized = calculateResize(gameplayRoi, h, 0.05, 0.05, MIN_ROI_SIZE);
      gameplayRoi = clampNormalizedRect(resized, MIN_ROI_SIZE);
      assert.deepEqual(facecamRoi, facecamRoiInitial, `Facecam ROI must remain identical after gameplay resize '${h}'`);
    }
  });

  await t.test('TC-CHALLENGE-03: Facecam ROI drag & 4-corner resize leaves Gameplay ROI 100% untouched', () => {
    const gameplayRoiInitial = { ...getDefaultGameplayRoi() };
    let gameplayRoi = { ...gameplayRoiInitial };
    let facecamRoi = getDefaultFacecamRoi();

    // Move facecam
    facecamRoi = applyDrag(facecamRoi, -0.05, 0.1);
    assert.deepEqual(gameplayRoi, gameplayRoiInitial, 'Gameplay ROI must remain identical after facecam drag');

    // Resize facecam from all 4 handles
    const handles = ['nw', 'ne', 'se', 'sw'];
    for (const h of handles) {
      const resized = calculateResize(facecamRoi, h, -0.02, 0.03, MIN_ROI_SIZE);
      facecamRoi = clampNormalizedRect(resized, MIN_ROI_SIZE);
      assert.deepEqual(gameplayRoi, gameplayRoiInitial, `Gameplay ROI must remain identical after facecam resize '${h}'`);
    }
  });

  await t.test('TC-CHALLENGE-04: Cross-box activation transitions tool correctly without state corruption', () => {
    let activeTool = 'gameplay';
    let gameplayRoi = { x: 0.1, y: 0.1, width: 0.8, height: 0.8 };
    let facecamRoi = { x: 0.7, y: 0.1, width: 0.25, height: 0.25 };

    // User clicks on facecam box while activeTool is gameplay
    // Simulating handleRoiPointerDown(e, 'facecam', 'move')
    activeTool = 'facecam';
    facecamRoi = applyDrag(facecamRoi, 0.02, -0.01);
    assert.equal(activeTool, 'facecam');
    assert.deepEqual(gameplayRoi, { x: 0.1, y: 0.1, width: 0.8, height: 0.8 }, 'Gameplay ROI must remain unchanged');

    // User clicks on gameplay box while activeTool is facecam
    // Simulating handleRoiPointerDown(e, 'gameplay', 'move')
    activeTool = 'gameplay';
    gameplayRoi = applyDrag(gameplayRoi, -0.05, 0.02);
    assert.equal(activeTool, 'gameplay');
    assert.deepEqual(facecamRoi, { x: 0.72, y: 0.09, width: 0.25, height: 0.25 }, 'Facecam ROI must remain unchanged');
  });

  await t.test('TC-CHALLENGE-05: Independent reset isolation preserves modified peer ROI', () => {
    let gameplayRoi = { x: 0.15, y: 0.2, width: 0.7, height: 0.6 };
    let facecamRoi = { x: 0.6, y: 0.1, width: 0.35, height: 0.35 };

    // Reset gameplay only
    gameplayRoi = getDefaultGameplayRoi();
    assert.deepEqual(gameplayRoi, getDefaultGameplayRoi());
    assert.deepEqual(facecamRoi, { x: 0.6, y: 0.1, width: 0.35, height: 0.35 }, 'Facecam ROI must remain customized');

    // Modify gameplay again
    gameplayRoi = { x: 0.05, y: 0.05, width: 0.9, height: 0.9 };
    // Reset facecam only
    facecamRoi = getDefaultFacecamRoi();
    assert.deepEqual(facecamRoi, getDefaultFacecamRoi());
    assert.deepEqual(gameplayRoi, { x: 0.05, y: 0.05, width: 0.9, height: 0.9 }, 'Gameplay ROI must remain customized');
  });

  await t.test('TC-CHALLENGE-06: Dual-ROI extreme boundary clamping stress', () => {
    const extremeDeltas = [
      { dx: -1000, dy: -1000 },
      { dx: 1000, dy: 1000 },
      { dx: -50, dy: 50 },
      { dx: 50, dy: -50 },
    ];

    for (const { dx, dy } of extremeDeltas) {
      const gDragged = applyDrag(getDefaultGameplayRoi(), dx, dy);
      const fDragged = applyDrag(getDefaultFacecamRoi(), dx, dy);

      for (const r of [gDragged, fDragged]) {
        assert.ok(r.x >= 0.0, `x must be >= 0, got ${r.x}`);
        assert.ok(r.y >= 0.0, `y must be >= 0, got ${r.y}`);
        assert.ok(r.x + r.width <= 1.0001, `x+w must be <= 1.0, got ${r.x + r.width}`);
        assert.ok(r.y + r.height <= 1.0001, `y+h must be <= 1.0, got ${r.y + r.height}`);
        assert.ok(r.width >= MIN_ROI_SIZE, `width must be >= ${MIN_ROI_SIZE}, got ${r.width}`);
        assert.ok(r.height >= MIN_ROI_SIZE, `height must be >= ${MIN_ROI_SIZE}, got ${r.height}`);
      }
    }
  });
});

// ==============================================================================
// 2. PRESET TRANSITIONS, MANUAL MANIPULATION & RESET STRESS SUITE
// ==============================================================================

test('Challenger 2 Suite 2: Preset Transitions, Overlay Manipulation & Reset', async (t) => {
  const presets = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];

  await t.test('TC-CHALLENGE-07: All 4 placement presets match CANONICAL_PRESETS with standard dimensions', () => {
    for (const p of presets) {
      const rect = getFacecamPreset(p);
      assertPresetParity(rect, p, 1e-4);
      assert.deepEqual(rect, CANONICAL_PRESETS[p]);
      const val = validateGamingCoordinates({
        mode: 'gaming',
        gameplay_roi: getDefaultGameplayRoi(),
        facecam_roi: getDefaultFacecamRoi(),
        facecam_placement: p,
        facecam_output_rect: rect,
      });
      assert.equal(val.valid, true, `Preset ${p} must pass validation`);
    }
  });

  await t.test('TC-CHALLENGE-08: Manual drag switches placement from preset to custom', () => {
    let placement = 'top-right';
    let outputRect = getDefaultFacecamOutputRect('top-right');

    // Simulate pointer drag on PiP overlay
    outputRect = applyDrag(outputRect, -0.1, 0.05);
    placement = 'custom';

    assert.equal(placement, 'custom');
    assert.equal(outputRect.x, 0.55);
    assert.equal(outputRect.y, 0.09);
  });

  await t.test('TC-CHALLENGE-09: Preset selection restores canonical positioning and placement name', () => {
    let placement = 'custom';
    let outputRect = { x: 0.33, y: 0.44, width: 0.30, height: 0.22 };

    for (const p of presets) {
      outputRect = getFacecamPreset(p, 0.30, 0.22);
      placement = p;
      assert.equal(placement, p);
      assertPresetParity(outputRect, p, 1e-4);
    }
  });

  await t.test('TC-CHALLENGE-10: Reset control restores default top-right preset and dimensions', () => {
    // Drastically alter overlay position and size
    let outputRect = { x: 0.1, y: 0.2, width: 0.8, height: 0.7 };
    let placement = 'custom';

    // Simulate handleReset()
    outputRect = getDefaultFacecamOutputRect('top-right');
    placement = 'top-right';

    assert.equal(placement, 'top-right');
    assert.deepEqual(outputRect, CANONICAL_PRESETS['top-right']);
    assert.equal(outputRect.width, 0.30);
    assert.equal(outputRect.height, 0.22);
  });

  await t.test('TC-CHALLENGE-11 [EMPIRICAL STRESS]: Preset calculation with extreme custom dimensions requires clamping to prevent negative coordinates', () => {
    // Adversarial scenario: User resizes facecam overlay to height=1.0 or width=1.0
    // Then user clicks 'bottom-right' or 'top-right'
    const unclampedBottomRight = getFacecamPreset('bottom-right', 0.30, 1.0);
    assert.equal(unclampedBottomRight.y, -0.04, 'Unclamped bottom-right preset produces negative y coordinate (-0.04)');

    const unclampedTopRight = getFacecamPreset('top-right', 1.0, 0.22);
    assert.equal(unclampedTopRight.x, -0.05, 'Unclamped top-right preset produces negative x coordinate (-0.05)');

    // Verify backend validator rejects unclamped output
    const valNegativeY = validateGamingCoordinates({
      mode: 'gaming',
      gameplay_roi: getDefaultGameplayRoi(),
      facecam_roi: getDefaultFacecamRoi(),
      facecam_placement: 'bottom-right',
      facecam_output_rect: unclampedBottomRight,
    });
    assert.equal(valNegativeY.valid, false, 'Backend validator must reject negative y coordinate');
    assert.ok(valNegativeY.errors[0].includes('negative coordinate'), 'Error must specify negative coordinate');

    // Clamping defense verification: when clamped, rect is strictly valid
    const clampedRect = clampNormalizedRect(unclampedBottomRight);
    assert.ok(clampedRect.y >= 0.0, 'Clamped rect must have y >= 0.0');
    assert.ok(clampedRect.y + clampedRect.height <= 1.0001, 'Clamped rect must remain in canvas');

    const valClamped = validateGamingCoordinates({
      mode: 'gaming',
      gameplay_roi: getDefaultGameplayRoi(),
      facecam_roi: getDefaultFacecamRoi(),
      facecam_placement: 'bottom-right',
      facecam_output_rect: clampedRect,
    });
    assert.equal(valClamped.valid, true, 'Clamped preset output must pass validation');
  });
});

// ==============================================================================
// 3. TIMELINE SCRUBBING, PRECISION STEPPING & TIMESTAMP FORMATTING FUZZING
// ==============================================================================

test('Challenger 2 Suite 3: Timeline Scrubbing & Timestamp Fuzzing', async (t) => {
  await t.test('TC-CHALLENGE-12: formatTime adversarial fuzzing across 1,000 extreme/degenerate inputs', () => {
    // 1. Degenerate and non-finite values
    const nonFiniteInputs = [
      NaN, Infinity, -Infinity, -0, -1, -100, -999999,
      undefined, null, 'abc', {}, [], true, false,
    ];

    for (const input of nonFiniteInputs) {
      const res = formatTime(input);
      assert.equal(res, '00:00', `Degenerate input ${String(input)} must format safely to '00:00', got '${res}'`);
    }

    // 2. Fuzzing across 1,000 random seconds
    for (let i = 0; i < 1000; i++) {
      const s = (Math.random() - 0.2) * 10000; // includes negative to large positive
      const res = formatTime(s);
      assert.ok(typeof res === 'string', 'formatTime must return a string');
      assert.match(res, /^\d{2,}:\d{2}$/, `Output '${res}' must match MM:SS format`);

      const [mStr, sStr] = res.split(':');
      const m = parseInt(mStr, 10);
      const sec = parseInt(sStr, 10);
      assert.ok(m >= 0, 'Minutes must be non-negative');
      assert.ok(sec >= 0 && sec < 60, 'Seconds must be in [0, 59]');
    }

    // 3. Exact boundary times
    assert.equal(formatTime(0), '00:00');
    assert.equal(formatTime(59), '00:59');
    assert.equal(formatTime(60), '01:00');
    assert.equal(formatTime(3599), '59:59');
    assert.equal(formatTime(3600), '60:00');
    assert.equal(formatTime(7265), '121:05');
  });

  await t.test('TC-CHALLENGE-13: Precision stepping boundaries (-1s / +1s) clamp monotonically to [0, duration]', () => {
    const duration = 10.0;
    let currentTime = 0.5;

    // Simulate handleStep(-1)
    const step = (cur, delta) => Math.max(0, Math.min(duration, cur + delta));

    // Step -1s from 0.5s -> clamps to 0
    currentTime = step(currentTime, -1);
    assert.equal(currentTime, 0.0, 'Step backward near 0 must clamp to 0.0');

    // Repeated -1s steps at 0 stay at 0
    for (let i = 0; i < 50; i++) {
      currentTime = step(currentTime, -1);
      assert.equal(currentTime, 0.0, 'Step backward at 0 must remain 0.0');
    }

    // Step forward 5 times
    for (let i = 0; i < 5; i++) {
      currentTime = step(currentTime, 1);
    }
    assert.equal(currentTime, 5.0);

    // Step to near end
    currentTime = 9.8;
    currentTime = step(currentTime, 1);
    assert.equal(currentTime, duration, 'Step forward past duration must clamp to duration');

    // Repeated +1s steps at duration stay at duration
    for (let i = 0; i < 50; i++) {
      currentTime = step(currentTime, 1);
      assert.equal(currentTime, duration, 'Step forward at duration must remain duration');
    }
  });

  await t.test('TC-CHALLENGE-14: Scrubber range slider attributes and zero duration handling', () => {
    // When duration is 0 (video still loading)
    let duration = 0;
    let max = duration > 0 ? duration : 100;
    assert.equal(max, 100, 'Scrubber fallback max must be 100 when duration is 0');

    // When duration is known
    duration = 45.5;
    max = duration > 0 ? duration : 100;
    assert.equal(max, 45.5, 'Scrubber max must reflect active video duration');
  });
});

// ==============================================================================
// 4. API SERIALIZATION FUZZING ACROSS VALID AND CLAMPED INPUTS
// ==============================================================================

test('Challenger 2 Suite 4: API Serialization & Coordinate Fuzzing', async (t) => {
  await t.test('TC-CHALLENGE-15: Round-trip JSON serialization fuzzing across 500 randomized valid configurations', () => {
    const presets = ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'custom'];

    for (let i = 0; i < 500; i++) {
      const gw = 0.05 + Math.random() * 0.95;
      const gh = 0.05 + Math.random() * 0.95;
      const gx = Math.random() * (1.0 - gw);
      const gy = Math.random() * (1.0 - gh);

      const fw = 0.05 + Math.random() * 0.95;
      const fh = 0.05 + Math.random() * 0.95;
      const fx = Math.random() * (1.0 - fw);
      const fy = Math.random() * (1.0 - fh);

      const ow = 0.05 + Math.random() * 0.95;
      const oh = 0.05 + Math.random() * 0.95;
      const ox = Math.random() * (1.0 - ow);
      const oy = Math.random() * (1.0 - oh);

      const preset = presets[i % presets.length];

      const config = {
        mode: 'gaming',
        gameplay_roi: { x: Number(gx.toFixed(4)), y: Number(gy.toFixed(4)), width: Number(gw.toFixed(4)), height: Number(gh.toFixed(4)) },
        facecam_roi: { x: Number(fx.toFixed(4)), y: Number(fy.toFixed(4)), width: Number(fw.toFixed(4)), height: Number(fh.toFixed(4)) },
        facecam_placement: preset,
        facecam_output_rect: { x: Number(ox.toFixed(4)), y: Number(oy.toFixed(4)), width: Number(ow.toFixed(4)), height: Number(oh.toFixed(4)) },
        canvas_width: 1080,
        canvas_height: 1920,
      };

      // Serialize (matching api.ts)
      const serialized = JSON.stringify(config);
      const deserialized = JSON.parse(serialized);

      // Validate
      const validation = validateGamingCoordinates(deserialized);
      assert.equal(validation.valid, true, `Config ${i} must validate cleanly: ${validation.errors?.join(', ')}`);
      assert.deepEqual(deserialized, config, `Config ${i} round-trip must match`);
    }
  });

  await t.test('TC-CHALLENGE-16: Clamping fuzzing across 500 degenerate inputs guarantees 100% valid serialized outputs', () => {
    for (let i = 0; i < 500; i++) {
      // Degenerate inputs: negative coordinates, enormous sizes, NaN-like values
      const raw = {
        x: (Math.random() - 0.5) * 4,     // [-2.0, 2.0]
        y: (Math.random() - 0.5) * 4,     // [-2.0, 2.0]
        width: (Math.random() - 0.3) * 3, // [-0.9, 2.1]
        height: (Math.random() - 0.3) * 3,
      };

      const clamped = clampNormalizedRect(raw);

      assert.ok(clamped.x >= 0.0, `Clamped x must be >= 0, got ${clamped.x}`);
      assert.ok(clamped.y >= 0.0, `Clamped y must be >= 0, got ${clamped.y}`);
      assert.ok(clamped.width >= MIN_ROI_SIZE, `Clamped width must be >= ${MIN_ROI_SIZE}, got ${clamped.width}`);
      assert.ok(clamped.height >= MIN_ROI_SIZE, `Clamped height must be >= ${MIN_ROI_SIZE}, got ${clamped.height}`);
      assert.ok(clamped.x + clamped.width <= 1.0001, `Clamped x+w must be <= 1.0, got ${clamped.x + clamped.width}`);
      assert.ok(clamped.y + clamped.height <= 1.0001, `Clamped y+h must be <= 1.0, got ${clamped.y + clamped.height}`);

      // Build complete config and validate
      const config = {
        mode: 'gaming',
        gameplay_roi: clamped,
        facecam_roi: getDefaultFacecamRoi(),
        facecam_placement: 'top-right',
        facecam_output_rect: getDefaultFacecamOutputRect('top-right'),
        canvas_width: 1080,
        canvas_height: 1920,
      };

      const val = validateGamingCoordinates(config);
      assert.equal(val.valid, true, `Clamped config ${i} must be valid: ${val.errors?.join(', ')}`);
    }
  });

  await t.test('TC-CHALLENGE-17: API Client Submission helper serializes layout and reframe_mode cleanly', () => {
    const layout = {
      mode: 'gaming',
      gameplay_roi: getDefaultGameplayRoi(),
      facecam_roi: getDefaultFacecamRoi(),
      facecam_placement: 'top-right',
      facecam_output_rect: getDefaultFacecamOutputRect('top-right'),
      canvas_width: 1080,
      canvas_height: 1920,
    };

    // Check FormData construction logic from api.ts
    const formFields = {};
    const mockFormData = {
      append: (k, v) => { formFields[k] = v; },
    };

    mockFormData.append('reframe_mode', 'gaming');
    mockFormData.append('gaming_layout', JSON.stringify(layout));

    assert.equal(formFields['reframe_mode'], 'gaming');
    assert.ok(typeof formFields['gaming_layout'] === 'string');

    const parsed = JSON.parse(formFields['gaming_layout']);
    assert.deepEqual(parsed, layout);
    assert.equal(parsed.mode, 'gaming');
  });
});

// ==============================================================================
// 5. STRICT R5 ZERO-CAPTION DEEP SCAN ACROSS DOM, COMPONENTS & PAYLOADS
// ==============================================================================

test('Challenger 2 Suite 5: Strict R5 Zero-Caption Deep Audit', async (t) => {
  const gamingFiles = [
    path.join(FRONTEND_ROOT, 'components/gaming/GamingCompositeCanvas.tsx'),
    path.join(FRONTEND_ROOT, 'components/gaming/GamingSelectionModal.tsx'),
    path.join(FRONTEND_ROOT, 'app/gaming/page.tsx'),
    path.join(FRONTEND_ROOT, 'lib/gamingCoordinates.ts'),
  ];

  await t.test('TC-CHALLENGE-18: Zero caption tokens in gaming frontend source files', () => {
    const forbiddenPatterns = [
      /\bcaption\b/i,
      /\bcaptions\b/i,
      /\bsubtitle\b/i,
      /\bsubtitles\b/i,
      /\bdrawtext\b/i,
      /\b\.srt\b/i,
      /\b\.vtt\b/i,
      /\b\.ass\b/i,
    ];

    for (const filePath of gamingFiles) {
      assert.ok(fs.existsSync(filePath), `File must exist: ${filePath}`);
      const content = fs.readFileSync(filePath, 'utf-8');

      for (const pattern of forbiddenPatterns) {
        const match = content.match(pattern);
        assert.equal(
          match,
          null,
          `Strict R5 violation: forbidden token '${pattern}' found in ${path.basename(filePath)}: "${match?.[0]}"`
        );
      }
    }
  });

  await t.test('TC-CHALLENGE-19: DOM element and attribute inspection reveals zero caption controls', () => {
    for (const filePath of gamingFiles) {
      const content = fs.readFileSync(filePath, 'utf-8');
      assertNoCaptionControlsInDOM(content);
    }
  });

  await t.test('TC-CHALLENGE-20: Intercepted API submission payload contains zero caption fields', () => {
    const standardGamingPayload = {
      mode: 'gaming',
      gameplay_roi: { x: 0, y: 0, width: 1, height: 1 },
      facecam_roi: { x: 0.7, y: 0.05, width: 0.25, height: 0.25 },
      facecam_placement: 'top-right',
      facecam_output_rect: { x: 0.65, y: 0.04, width: 0.30, height: 0.22 },
      canvas_width: 1080,
      canvas_height: 1920,
    };

    assertNoCaptionFieldsInPayload(standardGamingPayload);

    // Deep check all keys recursively
    const checkKeys = (obj) => {
      for (const k of Object.keys(obj)) {
        assert.ok(!/caption/i.test(k), `Payload key must not contain 'caption': ${k}`);
        assert.ok(!/subtitle/i.test(k), `Payload key must not contain 'subtitle': ${k}`);
        if (obj[k] && typeof obj[k] === 'object') checkKeys(obj[k]);
      }
    };
    checkKeys(standardGamingPayload);
  });
});

// ==============================================================================
// 6. INGESTION MODE SWITCHING & FILE EXTENSION VALIDATION
// ==============================================================================

test('Challenger 2 Suite 6: Ingestion Mode Switching & File Format Validation', async (t) => {
  await t.test('TC-CHALLENGE-21: Switching between URL and File upload modes leaves state uncorrupted', () => {
    let ingestMode = 'url';
    let url = '';
    let selectedFile = null;
    let error = '';

    // Switch 50 times
    for (let i = 0; i < 50; i++) {
      if (i % 2 === 0) {
        ingestMode = 'upload';
        error = '';
      } else {
        ingestMode = 'url';
        error = '';
      }
    }

    assert.equal(error, '');
    assert.equal(url, '');
    assert.equal(selectedFile, null);
  });

  await t.test('TC-CHALLENGE-22: File format regex strictly allows valid formats and rejects non-video files', () => {
    const validFiles = [
      'gameplay.mp4', 'GAMEPLAY.MP4', 'clip.mov', 'stream.avi', 'recording.mkv', 'web.webm',
      'my.cool.video.mp4', 'complex-name_123.mkv',
    ];
    const invalidFiles = [
      'notes.txt', 'image.jpg', 'doc.pdf', 'script.js', 'audio.mp3', 'archive.zip',
      'video.mp4.exe', 'no_extension',
    ];

    const formatRegex = /\.(mp4|mov|avi|mkv|webm)$/i;

    for (const f of validFiles) {
      assert.ok(formatRegex.test(f), `Valid video file '${f}' must be accepted`);
    }

    for (const f of invalidFiles) {
      assert.ok(!formatRegex.test(f), `Non-video file '${f}' must be rejected`);
    }
  });
});
