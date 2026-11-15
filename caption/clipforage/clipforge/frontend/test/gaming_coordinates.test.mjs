/**
 * gaming_coordinates.test.mjs
 * ============================
 * Tier 1 & Tier 2 Mathematical and Geometric Invariants Test Suite for ClipForge
 * Dual-Region Gaming Layout (Milestone T2).
 *
 * Implements 63 authoritative test cases covering:
 * - F02: Gameplay ROI Coordinate Math & Handle Resizing (5 tests Tier 1, 4 tests Tier 2)
 * - F03: Facecam ROI Coordinate Math & Independent Resize (4 tests Tier 1, 4 tests Tier 2)
 * - F05: Preset Coordinates Math & Margin Padding (5 tests Tier 1, 3 tests Tier 2)
 * - F06: Overlay Canvas Drag & 4-Corner Resize Math (3 tests Tier 1, 3 tests Tier 2)
 * - F07: Reset Coordinate Math (3 tests Tier 1)
 * - F09: Normalized Unit Space Math & Display Conversions (5 tests Tier 1, 3 tests Tier 2)
 * - F10: Letterbox/Pillarbox Compensation Math (5 tests Tier 1, 5 tests Tier 2)
 * - F11: Boundary Clamping & Minimum Dimension Enforcement (5 tests Tier 1, 5 tests Tier 2)
 * - F13: Golden Vectors Parity Engine (1 test Tier 1)
 *
 * Total: Exactly 63 tests (36 Tier 1, 27 Tier 2).
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  calculateRenderOffsets,
  displayToNormalized,
  displayToNormalizedLetterbox,
  normalizedToDisplay,
  clampNormalizedRect,
  calculateResize,
  applyResizeHandle,
  applyDrag,
  getFacecamPreset,
  getDefaultGameplayRoi,
  getDefaultFacecamRoi,
  getDefaultFacecamOutputRect,
  toEvenPixel,
  toEvenSpan,
  toEvenPixels,
  toCanvasOverlay,
  calculateGameplayFraming,
  validateNormalizedRect,
  validateGamingLayout,
  validateGamingCoordinates,
  calculateGamingCoordinates,
} from '../lib/gamingCoordinates.ts';

import {
  CANONICAL_PRESETS,
  getCanonicalPresetRect,
  assertPresetParity,
  simulateHandleResize,
  assertNormalizedRect,
  computeEvenPixelCrop,
  assertNoCaptionFieldsInPayload,
} from './gaming_test_helpers.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const goldenVectorsPath = path.resolve(__dirname, '../../docs/engineering/gaming_geometry_golden_vectors.json');

// ==============================================================================
// TIER 1 FEATURE COVERAGE (36 TESTS)
// ==============================================================================

test('Tier 1: Gameplay Region Selector (F02)', async (t) => {
  await t.test('TC-T1-F02-01: Initialize default gameplay ROI', () => {
    const roi = getDefaultGameplayRoi();
    assert.deepEqual(roi, { x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
  });

  await t.test('TC-T1-F02-02: Move gameplay ROI bounding box', () => {
    const moved = applyDrag({ x: 0.2, y: 0.2, width: 0.6, height: 0.6 }, 0.1, 0.0);
    assert.equal(moved.x, 0.3);
    assert.equal(moved.y, 0.2);
    assert.equal(moved.width, 0.6);
    assert.equal(moved.height, 0.6);
  });

  await t.test('TC-T1-F02-03: Resize gameplay ROI via bottom-right handle', () => {
    const resized = calculateResize({ x: 0.2, y: 0.2, width: 0.5, height: 0.5 }, 'se', 0.05, 0.05);
    assert.equal(resized.x, 0.2);
    assert.equal(resized.y, 0.2);
    assert.equal(resized.width, 0.55);
    assert.equal(resized.height, 0.55);
  });

  await t.test('TC-T1-F02-04: Resize gameplay ROI via top-left handle', () => {
    const resized = calculateResize({ x: 0.2, y: 0.2, width: 0.5, height: 0.5 }, 'nw', 0.05, 0.05);
    assert.equal(resized.x, 0.25);
    assert.equal(resized.y, 0.25);
    assert.equal(resized.width, 0.45);
    assert.equal(resized.height, 0.45);
  });

  await t.test('TC-T1-F02-05: Reset gameplay ROI to full frame', () => {
    const reset = getDefaultGameplayRoi();
    assert.deepEqual(reset, { x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
  });
});

test('Tier 1: Facecam Region Selector (F03)', async (t) => {
  await t.test('TC-T1-F03-01: Initialize default facecam ROI', () => {
    const roi = getDefaultFacecamRoi();
    assert.deepEqual(roi, { x: 0.70, y: 0.05, width: 0.25, height: 0.25 });
  });

  await t.test('TC-T1-F03-03: Drag facecam ROI independently of gameplay', () => {
    const gameplayRoi = getDefaultGameplayRoi();
    const facecamRoi = getDefaultFacecamRoi();
    const movedFacecam = applyDrag(facecamRoi, -0.2, 0.0);

    assert.equal(movedFacecam.x, 0.50);
    assert.deepEqual(gameplayRoi, { x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
  });

  await t.test('TC-T1-F03-04: Resize facecam ROI independently', () => {
    const gameplayRoi = getDefaultGameplayRoi();
    const facecamRoi = applyDrag(getDefaultFacecamRoi(), -0.2, 0.0); // x: 0.50, width: 0.25
    const resizedFacecam = calculateResize(facecamRoi, 'se', 0.1, 0.0);

    assert.equal(resizedFacecam.width, 0.35);
    assert.deepEqual(gameplayRoi, { x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
  });

  await t.test('TC-T1-F03-05: Reset facecam ROI', () => {
    const reset = getDefaultFacecamRoi();
    assert.deepEqual(reset, { x: 0.70, y: 0.05, width: 0.25, height: 0.25 });
  });
});

test('Tier 1: Facecam Placement Presets (F05)', async (t) => {
  await t.test('TC-T1-F05-01: Select top-left preset', () => {
    const rect = getFacecamPreset('top-left');
    assertPresetParity(rect, 'top-left');
    assert.deepEqual(rect, { x: 0.05, y: 0.04, width: 0.30, height: 0.22 });
  });

  await t.test('TC-T1-F05-02: Select top-right preset', () => {
    const rect = getFacecamPreset('top-right');
    assertPresetParity(rect, 'top-right');
    assert.deepEqual(rect, { x: 0.65, y: 0.04, width: 0.30, height: 0.22 });
  });

  await t.test('TC-T1-F05-03: Select bottom-left preset', () => {
    const rect = getFacecamPreset('bottom-left');
    assertPresetParity(rect, 'bottom-left');
    assert.deepEqual(rect, { x: 0.05, y: 0.74, width: 0.30, height: 0.22 });
  });

  await t.test('TC-T1-F05-04: Select bottom-right preset', () => {
    const rect = getFacecamPreset('bottom-right');
    assertPresetParity(rect, 'bottom-right');
    assert.deepEqual(rect, { x: 0.65, y: 0.74, width: 0.30, height: 0.22 });
  });

  await t.test('TC-T1-F05-05: Preset margin padding enforcement', () => {
    const presets = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
    for (const p of presets) {
      const rect = getFacecamPreset(p);
      assert.ok(rect.x >= 0.05 - 1e-5, `${p} x margin must be >= 0.05`);
      assert.ok(rect.y >= 0.04 - 1e-5, `${p} y margin must be >= 0.04`);
      assert.ok(rect.x + rect.width <= 0.95 + 1e-5, `${p} right edge must be <= 0.95`);
      assert.ok(rect.y + rect.height <= 0.96 + 1e-5, `${p} bottom edge must be <= 0.96`);
    }
  });
});

test('Tier 1: Free Drag & Resize on Canvas (F06)', async (t) => {
  await t.test('TC-T1-F06-01: Drag facecam overlay on 9:16 canvas', () => {
    const moved = applyDrag({ x: 0.3, y: 0.3, width: 0.3, height: 0.22 }, 0.2, 0.2);
    assert.equal(moved.x, 0.5);
    assert.equal(moved.y, 0.5);
    assert.equal(moved.width, 0.3);
    assert.equal(moved.height, 0.22);
  });

  await t.test('TC-T1-F06-02: Resize facecam overlay via SE handle', () => {
    const resized = calculateResize({ x: 0.5, y: 0.5, width: 0.3, height: 0.2 }, 'se', 0.05, 0.0);
    assert.equal(resized.width, 0.35);
    assert.equal(resized.height, 0.2);
    assert.equal(resized.x, 0.5);
    assert.equal(resized.y, 0.5);
  });

  await t.test('TC-T1-F06-03: Resize facecam overlay via NW handle', () => {
    const resized = calculateResize({ x: 0.5, y: 0.5, width: 0.3, height: 0.2 }, 'nw', 0.05, 0.05);
    assert.equal(resized.x, 0.55);
    assert.equal(resized.y, 0.55);
    assert.equal(resized.width, 0.25);
    assert.equal(resized.height, 0.15);
    // Anchor check: bottom-right corner must remain at (0.8, 0.7)
    assert.ok(Math.abs(resized.x + resized.width - 0.8) < 1e-5);
    assert.ok(Math.abs(resized.y + resized.height - 0.7) < 1e-5);
  });
});

test('Tier 1: Facecam Reset Control (F07)', async (t) => {
  await t.test('TC-T1-F07-01: Reset facecam to default position', () => {
    const def = getDefaultFacecamOutputRect();
    assert.equal(def.x, 0.65);
    assert.equal(def.y, 0.04);
  });

  await t.test('TC-T1-F07-02: Reset facecam to default dimensions', () => {
    const def = getDefaultFacecamOutputRect();
    assert.equal(def.width, 0.30);
    assert.equal(def.height, 0.22);
  });

  await t.test('TC-T1-F07-03: Reset button idempotency', () => {
    const r1 = getDefaultFacecamOutputRect();
    const r2 = getDefaultFacecamOutputRect();
    assert.deepEqual(r1, r2);
  });
});

test('Tier 1: Normalized Coordinate Space (F09)', async (t) => {
  await t.test('TC-T1-F09-01: Normalized coordinates bounds', () => {
    const rect = { x: 0.1, y: 0.2, width: 0.3, height: 0.4 };
    assertNormalizedRect(rect);
  });

  await t.test('TC-T1-F09-02: Convert display pixels to normalized', () => {
    const norm = displayToNormalized(100, 200, { left: 0, top: 0, width: 1000, height: 1000 });
    assert.equal(norm.x, 0.10);
    assert.equal(norm.y, 0.20);
  });

  await t.test('TC-T1-F09-03: Convert normalized to display pixels', () => {
    const disp = normalizedToDisplay({ x: 0.25, y: 0.25, width: 0.5, height: 0.5 }, 1920, 1080);
    assert.equal(disp.left, 480);
    assert.equal(disp.top, 270);
    assert.equal(disp.width, 960);
    assert.equal(disp.height, 540);
  });

  await t.test('TC-T1-F09-04: Aspect ratio scaling invariance', () => {
    const norm1 = displayToNormalized(400, 225, { left: 0, top: 0, width: 800, height: 450 });
    const norm2 = displayToNormalized(800, 450, { left: 0, top: 0, width: 1600, height: 900 });
    assert.equal(norm1.x, norm2.x);
    assert.equal(norm1.y, norm2.y);
  });

  await t.test('TC-T1-F09-05: Minimum size invariant enforcement', () => {
    const clamped = clampNormalizedRect({ x: 0.1, y: 0.1, width: 0.02, height: 0.03 });
    assert.equal(clamped.width, 0.05);
    assert.equal(clamped.height, 0.05);
  });
});

test('Tier 1: Letterbox / Pillarbox Compensation (F10)', async (t) => {
  await t.test('TC-T1-F10-01: 16:9 video in 4:3 letterboxed container', () => {
    const offsets = calculateRenderOffsets(800, 600, 1920, 1080);
    assert.equal(offsets.renderWidth, 800);
    assert.equal(offsets.renderHeight, 450);
    assert.equal(offsets.renderTop, 75);
    assert.equal(offsets.renderLeft, 0);
  });

  await t.test('TC-T1-F10-02: 9:16 video in 16:9 pillarboxed container', () => {
    const offsets = calculateRenderOffsets(1600, 900, 1080, 1920);
    assert.equal(offsets.renderHeight, 900);
    assert.equal(offsets.renderWidth, 506);
    assert.equal(offsets.renderLeft, 547);
    assert.equal(offsets.renderTop, 0);
  });

  await t.test('TC-T1-F10-03: Clicks inside letterbox bar clamped', () => {
    const norm = displayToNormalized(500, 20, { left: 0, top: 0, width: 800, height: 600 }, 1920, 1080);
    assert.equal(norm.y, 0.0);
  });

  await t.test('TC-T1-F10-04: Responsive container resize compensation', () => {
    const c1 = displayToNormalized(400, 225, { left: 0, top: 0, width: 800, height: 450 }, 1920, 1080);
    const c2 = displayToNormalized(600, 337.5, { left: 0, top: 0, width: 1200, height: 675 }, 1920, 1080);
    assert.equal(c1.x, 0.5);
    assert.equal(c1.y, 0.5);
    assert.equal(c2.x, 0.5);
    assert.equal(c2.y, 0.5);
  });

  await t.test('TC-T1-F10-05: Exact match container (zero letterboxing)', () => {
    const offsets = calculateRenderOffsets(1920, 1080, 1920, 1080);
    assert.equal(offsets.renderLeft, 0);
    assert.equal(offsets.renderTop, 0);
    assert.equal(offsets.renderWidth, 1920);
    assert.equal(offsets.renderHeight, 1080);
  });
});

test('Tier 1: Strict Boundary Clamping (F11)', async (t) => {
  await t.test('TC-T1-F11-01: Negative x, y clamping', () => {
    const clamped = clampNormalizedRect({ x: -0.15, y: -0.20, width: 0.3, height: 0.3 });
    assert.equal(clamped.x, 0.0);
    assert.equal(clamped.y, 0.0);
    assert.equal(clamped.width, 0.3);
    assert.equal(clamped.height, 0.3);
  });

  await t.test('TC-T1-F11-02: Maximum boundary overflow clamping', () => {
    const clamped = clampNormalizedRect({ x: 0.85, y: 0.85, width: 0.3, height: 0.3 });
    assert.ok(clamped.x + clamped.width <= 1.0001);
    assert.ok(clamped.y + clamped.height <= 1.0001);
  });

  await t.test('TC-T1-F11-03: Minimum dimension enforcement', () => {
    const clamped = clampNormalizedRect({ x: 0.2, y: 0.2, width: 0.01, height: 0.02 });
    assert.equal(clamped.width, 0.05);
    assert.equal(clamped.height, 0.05);
  });

  await t.test('TC-T1-F11-04: Invariant validation 0 <= x <= 1-w, 0 <= y <= 1-h', () => {
    const rect = clampNormalizedRect({ x: 0.7, y: 0.8, width: 0.4, height: 0.4 });
    assertNormalizedRect(rect);
  });

  await t.test('TC-T1-F11-05: Overlay clamping on 9:16 canvas', () => {
    const moved = applyDrag({ x: 0.6, y: 0.7, width: 0.3, height: 0.22 }, 0.5, 0.5);
    assert.equal(moved.x, 0.7);
    assert.equal(moved.y, 0.78);
  });
});

test('Tier 1: Golden Vectors Parity Engine (F13)', async (t) => {
  await t.test('TC-T1-F13-03: TypeScript parity against golden vectors', () => {
    assert.ok(fs.existsSync(goldenVectorsPath), `Golden vectors file must exist at ${goldenVectorsPath}`);
    const rawData = fs.readFileSync(goldenVectorsPath, 'utf-8');
    const fixture = JSON.parse(rawData);
    const vectors = fixture.vectors;

    assert.ok(vectors.length >= 30, `Expected at least 30 golden vectors, found ${vectors.length}`);

    for (const v of vectors) {
      const inp = v.input;
      const exp = v.expected;

      if (exp.is_valid) {
        if (inp.container && inp.pointer) {
          const res = displayToNormalizedLetterbox(
            inp.pointer.clientX,
            inp.pointer.clientY,
            inp.container,
            inp.src_w,
            inp.src_h
          );
          assert.deepEqual(res.render_rect, exp.render_rect, `[${v.id}] render_rect mismatch`);
          assert.deepEqual(res.normalized_pointer, exp.normalized_pointer, `[${v.id}] normalized_pointer mismatch`);
        } else {
          const plan = calculateGamingCoordinates(inp);
          assert.deepEqual(plan.facecam_resolved_output_rect, exp.facecam_resolved_output_rect, `[${v.id}] facecam_resolved_output_rect mismatch`);
          assert.deepEqual(plan.gameplay_crop, exp.gameplay_crop, `[${v.id}] gameplay_crop mismatch`);
          assert.deepEqual(plan.facecam_crop, exp.facecam_crop, `[${v.id}] facecam_crop mismatch`);
          assert.deepEqual(plan.facecam_dest, exp.facecam_dest, `[${v.id}] facecam_dest mismatch`);
          assert.ok(Math.abs(plan.gameplay_scale_factor - exp.gameplay_scale_factor) < 1e-4, `[${v.id}] scale factor mismatch`);
          assert.equal(plan.gameplay_scaled_w, exp.gameplay_scaled_w, `[${v.id}] scaled_w mismatch`);
          assert.equal(plan.gameplay_scaled_h, exp.gameplay_scaled_h, `[${v.id}] scaled_h mismatch`);
          assert.equal(plan.ffmpeg_crop_gameplay, exp.ffmpeg_crop_gameplay, `[${v.id}] crop gameplay mismatch`);
          assert.equal(plan.ffmpeg_crop_facecam, exp.ffmpeg_crop_facecam, `[${v.id}] crop facecam mismatch`);
          assert.equal(plan.ffmpeg_filtergraph, exp.ffmpeg_filtergraph, `[${v.id}] filtergraph mismatch`);

          // Zero-caption assertion on plan result
          assertNoCaptionFieldsInPayload(plan);
        }
      } else {
        assert.throws(
          () => validateGamingLayout(inp),
          new RegExp(exp.error_message_substring, 'i'),
          `[${v.id}] Expected validation error`
        );
      }
    }
  });
});

// ==============================================================================
// TIER 2 BOUNDARY & CORNER CASES (27 TESTS)
// ==============================================================================

test('Tier 2: Gameplay ROI Boundaries & Min Dimensions (F02)', async (t) => {
  await t.test('TC-T2-F02-01: Gameplay ROI dragged to extreme top-left offscreen (x=-1.0, y=-1.0)', () => {
    const moved = applyDrag({ x: 0.2, y: 0.2, width: 0.5, height: 0.5 }, -2.0, -2.0);
    assert.equal(moved.x, 0.0);
    assert.equal(moved.y, 0.0);
    assert.equal(moved.width, 0.5);
    assert.equal(moved.height, 0.5);
  });

  await t.test('TC-T2-F02-02: Gameplay ROI dragged to extreme bottom-right (x=2.0, y=2.0)', () => {
    const moved = applyDrag({ x: 0.2, y: 0.2, width: 0.5, height: 0.5 }, 2.0, 2.0);
    assert.equal(moved.x, 0.5);
    assert.equal(moved.y, 0.5);
    assert.equal(moved.width, 0.5);
    assert.equal(moved.height, 0.5);
  });

  await t.test('TC-T2-F02-03: Attempt to shrink gameplay ROI to 0 width', () => {
    const resized = calculateResize({ x: 0.5, y: 0.5, width: 0.2, height: 0.2 }, 'se', -0.3, 0.0);
    assert.equal(resized.width, 0.05);
  });

  await t.test('TC-T2-F02-04: Gameplay ROI with w=1.0, h=1.0 (Full source frame)', () => {
    const clamped = clampNormalizedRect({ x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
    assert.deepEqual(clamped, { x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
  });
});

test('Tier 2: Facecam ROI Corner & Minimum Boundaries (F03)', async (t) => {
  await t.test('TC-T2-F03-01: Facecam ROI collapsed to minimum size (0.05 x 0.05)', () => {
    const resized = calculateResize({ x: 0.5, y: 0.5, width: 0.1, height: 0.1 }, 'se', -0.5, -0.5);
    assert.equal(resized.width, 0.05);
    assert.equal(resized.height, 0.05);
  });

  await t.test('TC-T2-F03-02: Facecam ROI expanded to full screen (1.0 x 1.0)', () => {
    const clamped = clampNormalizedRect({ x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
    assert.deepEqual(clamped, { x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
  });

  await t.test('TC-T2-F03-04: Facecam ROI positioned at exact bottom-right corner (x=0.95, y=0.95, w=0.05, h=0.05)', () => {
    const clamped = clampNormalizedRect({ x: 0.95, y: 0.95, width: 0.05, height: 0.05 });
    assert.equal(clamped.x, 0.95);
    assert.equal(clamped.y, 0.95);
    assert.equal(clamped.width, 0.05);
    assert.equal(clamped.height, 0.05);
    assert.equal(clamped.x + clamped.width, 1.0);
    assert.equal(clamped.y + clamped.height, 1.0);
  });

  await t.test('TC-T2-F03-05: Inverted drag on facecam handle (dragging right handle past left edge)', () => {
    const resized = calculateResize({ x: 0.4, y: 0.4, width: 0.2, height: 0.2 }, 'se', -0.5, 0.0);
    assert.ok(resized.width >= 0.05);
    assert.equal(resized.x, 0.4);
  });
});

test('Tier 2: Presets on Custom Dimensions & Margins (F05)', async (t) => {
  await t.test('TC-T2-F05-01: Apply preset when overlay width is custom (w=0.45, h=0.35)', () => {
    const rect = getFacecamPreset('top-left', 0.45, 0.35);
    assert.equal(rect.x, 0.05);
    assert.equal(rect.y, 0.04);
    assert.equal(rect.width, 0.45);
    assert.equal(rect.height, 0.35);
  });

  await t.test('TC-T2-F05-02: Apply preset when overlay dimensions exceed margin space (w=0.95)', () => {
    const rect = getFacecamPreset('top-right', 0.95, 0.22);
    assert.equal(rect.x, 0.00);
    assert.equal(rect.width, 0.95);
    assert.ok(rect.x + rect.width <= 1.0);
  });

  await t.test('TC-T2-F05-05: Preset application on non-standard canvas dimensions', () => {
    const preset = getFacecamPreset('top-left');
    const overlay = toCanvasOverlay(preset, 720, 1280);
    assert.equal(overlay.x % 2, 0);
    assert.equal(overlay.y % 2, 0);
    assert.equal(overlay.w % 2, 0);
    assert.equal(overlay.h % 2, 0);
    assert.equal(overlay.x, 36);
    assert.equal(overlay.y, 50);
  });
});

test('Tier 2: Drag & Resize Canvas Overflow Boundaries (F06)', async (t) => {
  await t.test('TC-T2-F06-01: Drag overlay past right canvas edge (x > 1.0)', () => {
    const moved = applyDrag({ x: 0.5, y: 0.5, width: 0.3, height: 0.2 }, 1.5, 0.0);
    assert.equal(moved.x, 0.7);
  });

  await t.test('TC-T2-F06-02: Drag overlay past bottom canvas edge (y > 1.0)', () => {
    const moved = applyDrag({ x: 0.5, y: 0.5, width: 0.3, height: 0.2 }, 0.0, 1.5);
    assert.equal(moved.y, 0.8);
  });

  await t.test('TC-T2-F06-03: Resize overlay to exceed canvas width (w > 1.0)', () => {
    const resized = calculateResize({ x: 0.2, y: 0.2, width: 0.5, height: 0.5 }, 'se', 1.0, 0.0);
    assert.equal(resized.width, 0.8);
    assert.equal(resized.x + resized.width, 1.0);
  });
});

test('Tier 2: Floating-Point Precision & Extreme Edges (F09)', async (t) => {
  await t.test('TC-T2-F09-01: Coordinate with 16 decimal places of precision', () => {
    const clamped = clampNormalizedRect({ x: 0.1234567890123456, y: 0.6543210987654321, width: 0.3, height: 0.2 });
    assert.equal(clamped.x, 0.1235);
    assert.equal(clamped.y, 0.6543);
  });

  await t.test('TC-T2-F09-02: Coordinate boundary edge (x=0.0, y=0.0)', () => {
    const px = toEvenPixel(0.0, 1920);
    assert.equal(px, 0);
  });

  await t.test('TC-T2-F09-03: Coordinate boundary edge (x=1.0, y=1.0) with w=0.0, h=0.0', () => {
    const clamped = clampNormalizedRect({ x: 1.0, y: 1.0, width: 0.0, height: 0.0 });
    assert.equal(clamped.x, 0.95);
    assert.equal(clamped.y, 0.95);
    assert.equal(clamped.width, 0.05);
    assert.equal(clamped.height, 0.05);
  });
});

test('Tier 2: Letterbox Ultrawide & Tall Aspect Ratios (F10)', async (t) => {
  await t.test('TC-T2-F10-01: Extreme ultrawide video 32:9 (3840x1080)', () => {
    const offsets = calculateRenderOffsets(1600, 900, 3840, 1080);
    assert.equal(offsets.renderWidth, 1600);
    assert.equal(offsets.renderHeight, 450);
    assert.equal(offsets.renderTop, 225);
    assert.equal(offsets.renderLeft, 0);
  });

  await t.test('TC-T2-F10-02: Tall vertical video 9:21 (1080x2520)', () => {
    const offsets = calculateRenderOffsets(1600, 900, 1080, 2520);
    assert.equal(offsets.renderHeight, 900);
    assert.equal(offsets.renderWidth, 386);
    assert.equal(offsets.renderLeft, 607);
    assert.equal(offsets.renderTop, 0);
  });

  await t.test('TC-T2-F10-03: Click in exact corner of letterbox padding', () => {
    const norm = displayToNormalized(0, 0, { left: 0, top: 0, width: 800, height: 800 }, 1920, 1080);
    assert.equal(norm.x, 0.0);
    assert.equal(norm.y, 0.0);
  });

  await t.test('TC-T2-F10-04: Resizing window to 1px width', () => {
    const offsets = calculateRenderOffsets(1, 900, 1920, 1080);
    assert.equal(offsets.renderLeft, 0);
    assert.ok(offsets.renderWidth >= 0);
    assert.ok(offsets.renderHeight >= 0);
  });

  await t.test('TC-T2-F10-05: Sub-pixel container offsets (0.5px padding)', () => {
    const norm = displayToNormalized(400.5, 300.5, { left: 0, top: 0, width: 801, height: 601 }, 1920, 1080);
    assert.ok(Number.isFinite(norm.x));
    assert.ok(Number.isFinite(norm.y));
    assert.ok(norm.x >= 0.0 && norm.x <= 1.0);
    assert.ok(norm.y >= 0.0 && norm.y <= 1.0);
  });
});

test('Tier 2: Extreme Negative & Overflow Clamping (F11)', async (t) => {
  await t.test('TC-T2-F11-01: Extreme negative coordinates (x=-9999, y=-9999)', () => {
    const clamped = clampNormalizedRect({ x: -9999, y: -9999, width: 0.3, height: 0.3 });
    assert.equal(clamped.x, 0.0);
    assert.equal(clamped.y, 0.0);
    assert.equal(clamped.width, 0.3);
    assert.equal(clamped.height, 0.3);
  });

  await t.test('TC-T2-F11-02: Extreme positive coordinates (x=9999, y=9999)', () => {
    const moved = applyDrag({ x: 0.5, y: 0.5, width: 0.3, height: 0.3 }, 9999, 9999);
    assert.equal(moved.x, 0.7);
    assert.equal(moved.y, 0.7);
  });

  await t.test('TC-T2-F11-03: Over-sized candidate width (w=2.5)', () => {
    const clamped = clampNormalizedRect({ x: 0.5, y: 0.5, width: 2.5, height: 0.2 });
    assert.equal(clamped.x, 0.5);
    assert.equal(clamped.width, 0.5);
  });

  await t.test('TC-T2-F11-04: Micro-sized candidate width (w=0.000001)', () => {
    const clamped = clampNormalizedRect({ x: 0.2, y: 0.2, width: 0.000001, height: 0.2 });
    assert.equal(clamped.width, 0.05);
  });

  await t.test('TC-T2-F11-05: Sum of x + w = 1.000002 due to float addition', () => {
    const clamped = clampNormalizedRect({ x: 0.700001, y: 0.1, width: 0.300001, height: 0.2 });
    assert.ok(clamped.x + clamped.width <= 1.000001);
  });
});
