/**
 * frontend/test/gaming_coordinates_adversarial_m1_iter2.test.mjs
 *
 * EMPIRICAL ADVERSARIAL CHALLENGE SUITE — Milestone M1 Iteration 2
 * Author: Frontend Challenger (critic, specialist)
 *
 * Tests the 4 critical challenge areas:
 * 1. Corner anchor invariance & resize handle inversion stress
 * 2. Boundary clamping, subpixel precision & near-boundary epsilon
 * 3. Letterbox/pillarbox offset calculations & pointer mapping
 * 4. Dimension validation & codec parity across edge cases
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  calculateRenderOffsets,
  displayToNormalized,
  displayToNormalizedLetterbox,
  normalizedToDisplay,
  clampNormalizedRect,
  calculateResize,
  applyDrag,
  getFacecamPreset,
  toEvenPixel,
  toEvenSpan,
  toEvenPixels,
  toSourceCrop,
  toCanvasOverlay,
  calculateGameplayFraming,
  validateNormalizedRect,
  validateGamingLayout,
  validateGamingCoordinates,
  calculateGamingCoordinates,
  MIN_ROI_SIZE,
  DEFAULT_CANVAS_WIDTH,
  DEFAULT_CANVAS_HEIGHT,
} from '../lib/gamingCoordinates.ts';

// ---------------------------------------------------------------------------
// SUITE 1: Corner Resize Handles & Anchor Invariance
// ---------------------------------------------------------------------------
test('SUITE 1: Corner Resize Handles & Anchor Invariance', async (t) => {
  const handles = ['se', 'ne', 'sw', 'nw'];

  await t.test('Anchor point mathematically invariant under extreme deltas', () => {
    const initialRect = { x: 0.3, y: 0.3, width: 0.4, height: 0.4 };
    const extremeDeltas = [
      [-10.0, -10.0],
      [+10.0, +10.0],
      [-0.35, -0.35], // Inversion attempt past anchor
      [+0.35, +0.35],
      [0.0, 0.0],
      [-1.0, 0.0],
      [0.0, -1.0],
      [+1.0, 0.0],
      [0.0, +1.0],
    ];

    for (const [dx, dy] of extremeDeltas) {
      // SE: Top-Left anchor (x0, y0) must NOT move
      const rSE = calculateResize(initialRect, 'se', dx, dy);
      assert.strictEqual(rSE.x, initialRect.x, `SE handle shifted anchor x: ${rSE.x} != ${initialRect.x} at dx=${dx}, dy=${dy}`);
      assert.strictEqual(rSE.y, initialRect.y, `SE handle shifted anchor y: ${rSE.y} != ${initialRect.y} at dx=${dx}, dy=${dy}`);
      assert.ok(rSE.width >= MIN_ROI_SIZE - 1e-4, `SE width < minSize: ${rSE.width}`);
      assert.ok(rSE.height >= MIN_ROI_SIZE - 1e-4, `SE height < minSize: ${rSE.height}`);
      assert.ok(rSE.x + rSE.width <= 1.0001, `SE x+w > 1: ${rSE.x + rSE.width}`);
      assert.ok(rSE.y + rSE.height <= 1.0001, `SE y+h > 1: ${rSE.y + rSE.height}`);

      // NE: Bottom-Left anchor (x0, y0 + h0) must NOT move
      const rNE = calculateResize(initialRect, 'ne', dx, dy);
      const neBottomY = Math.round((rNE.y + rNE.height) * 10000) / 10000;
      const initialBottomY = Math.round((initialRect.y + initialRect.height) * 10000) / 10000;
      assert.strictEqual(rNE.x, initialRect.x, `NE handle shifted anchor x: ${rNE.x} != ${initialRect.x}`);
      assert.strictEqual(neBottomY, initialBottomY, `NE handle shifted bottom anchor y: ${neBottomY} != ${initialBottomY}`);
      assert.ok(rNE.width >= MIN_ROI_SIZE - 1e-4, `NE width < minSize: ${rNE.width}`);
      assert.ok(rNE.height >= MIN_ROI_SIZE - 1e-4, `NE height < minSize: ${rNE.height}`);

      // SW: Top-Right anchor (x0 + w0, y0) must NOT move
      const rSW = calculateResize(initialRect, 'sw', dx, dy);
      const swRightX = Math.round((rSW.x + rSW.width) * 10000) / 10000;
      const initialRightX = Math.round((initialRect.x + initialRect.width) * 10000) / 10000;
      assert.strictEqual(rSW.y, initialRect.y, `SW handle shifted anchor y: ${rSW.y} != ${initialRect.y}`);
      assert.strictEqual(swRightX, initialRightX, `SW handle shifted right anchor x: ${swRightX} != ${initialRightX}`);
      assert.ok(rSW.width >= MIN_ROI_SIZE - 1e-4, `SW width < minSize: ${rSW.width}`);
      assert.ok(rSW.height >= MIN_ROI_SIZE - 1e-4, `SW height < minSize: ${rSW.height}`);

      // NW: Bottom-Right anchor (x0 + w0, y0 + h0) must NOT move
      const rNW = calculateResize(initialRect, 'nw', dx, dy);
      const nwRightX = Math.round((rNW.x + rNW.width) * 10000) / 10000;
      const nwBottomY = Math.round((rNW.y + rNW.height) * 10000) / 10000;
      assert.strictEqual(nwRightX, initialRightX, `NW handle shifted right anchor x: ${nwRightX} != ${initialRightX}`);
      assert.strictEqual(nwBottomY, initialBottomY, `NW handle shifted bottom anchor y: ${nwBottomY} != ${initialBottomY}`);
      assert.ok(rNW.width >= MIN_ROI_SIZE - 1e-4, `NW width < minSize: ${rNW.width}`);
      assert.ok(rNW.height >= MIN_ROI_SIZE - 1e-4, `NW height < minSize: ${rNW.height}`);
    }
  });

  await t.test('Fuzzing 5,000 random resize operations verifies containment and minSize', () => {
    let rngState = 42;
    function pseudoRandom() {
      rngState = (rngState * 1664525 + 1013904223) % 4294967296;
      return rngState / 4294967296;
    }

    for (let i = 0; i < 5000; i++) {
      const handle = handles[Math.floor(pseudoRandom() * 4)];
      const w0 = MIN_ROI_SIZE + pseudoRandom() * (1.0 - MIN_ROI_SIZE);
      const h0 = MIN_ROI_SIZE + pseudoRandom() * (1.0 - MIN_ROI_SIZE);
      const x0 = pseudoRandom() * (1.0 - w0);
      const y0 = pseudoRandom() * (1.0 - h0);
      const initial = {
        x: Math.round(x0 * 10000) / 10000,
        y: Math.round(y0 * 10000) / 10000,
        width: Math.round(w0 * 10000) / 10000,
        height: Math.round(h0 * 10000) / 10000,
      };

      const dx = (pseudoRandom() - 0.5) * 4.0;
      const dy = (pseudoRandom() - 0.5) * 4.0;

      const res = calculateResize(initial, handle, dx, dy);

      assert.ok(res.x >= 0.0, `res.x negative: ${res.x}`);
      assert.ok(res.y >= 0.0, `res.y negative: ${res.y}`);
      assert.ok(res.width >= MIN_ROI_SIZE - 1e-4, `res.width < minSize: ${res.width}`);
      assert.ok(res.height >= MIN_ROI_SIZE - 1e-4, `res.height < minSize: ${res.height}`);
      assert.ok(res.x + res.width <= 1.0001, `res.x + res.width > 1.0: ${res.x + res.width}`);
      assert.ok(res.y + res.height <= 1.0001, `res.y + res.height > 1.0: ${res.y + res.height}`);

      // Crucially, must be valid according to validateNormalizedRect
      assert.doesNotThrow(() => validateNormalizedRect(res), `Fuzzed resize output failed validateNormalizedRect: ${JSON.stringify(res)}`);
    }
  });
});

// ---------------------------------------------------------------------------
// SUITE 2: Boundary Clamping, Subpixel Precision & Near-Boundary Epsilon
// ---------------------------------------------------------------------------
test('SUITE 2: Boundary Clamping, Subpixel Precision & Near-Boundary Epsilon', async (t) => {
  await t.test('clampNormalizedRect handles out-of-range, NaN, and negative inputs', () => {
    const pathologicalCases = [
      { x: -0.5, y: -0.5, width: 2.0, height: 2.0 },
      { x: 1.5, y: 1.5, width: 0.1, height: 0.1 },
      { x: NaN, y: NaN, width: NaN, height: NaN },
      { x: Infinity, y: -Infinity, width: Infinity, height: -Infinity },
      { x: 0.0, y: 0.0, width: 0.001, height: 0.001 },
      { x: 0.98, y: 0.98, width: 0.1, height: 0.1 },
    ];

    for (const c of pathologicalCases) {
      const clamped = clampNormalizedRect(c);
      assert.ok(clamped.x >= 0.0, `clamped.x < 0: ${clamped.x}`);
      assert.ok(clamped.y >= 0.0, `clamped.y < 0: ${clamped.y}`);
      assert.ok(clamped.width >= MIN_ROI_SIZE - 1e-4, `clamped.width < minSize: ${clamped.width}`);
      assert.ok(clamped.height >= MIN_ROI_SIZE - 1e-4, `clamped.height < minSize: ${clamped.height}`);
      assert.ok(clamped.x + clamped.width <= 1.0001, `clamped.x + clamped.width > 1.0: ${clamped.x + clamped.width}`);
      assert.ok(clamped.y + clamped.height <= 1.0001, `clamped.y + clamped.height > 1.0: ${clamped.y + clamped.height}`);
      assert.doesNotThrow(() => validateNormalizedRect(clamped));
    }
  });

  await t.test('validateNormalizedRect precision and clean output guarantees', () => {
    // Exact boundary at 0.0 and 1.0
    const edge = validateNormalizedRect({ x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
    assert.strictEqual(edge.x, 0.0);
    assert.strictEqual(edge.y, 0.0);
    assert.strictEqual(edge.width, 1.0);
    assert.strictEqual(edge.height, 1.0);

    // Epsilon near 0.0: x = -0.00005 should be cleaned to 0.0 without throwing
    const nearZero = validateNormalizedRect({ x: -0.00005, y: 0.0, width: 0.5, height: 0.5 });
    assert.strictEqual(nearZero.x, 0.0);

    // Epsilon near 1.0: x = 0.5, width = 0.50005 should be cleaned so x + width <= 1.0
    const nearOne = validateNormalizedRect({ x: 0.5, y: 0.0, width: 0.50005, height: 0.5 });
    assert.ok(nearOne.x + nearOne.width <= 1.0, `Cleaned sum > 1.0: ${nearOne.x + nearOne.width}`);

    // Rejection beyond epsilon
    assert.throws(() => validateNormalizedRect({ x: -0.0002, y: 0.0, width: 0.5, height: 0.5 }), /negative coordinate/);
    assert.throws(() => validateNormalizedRect({ x: 0.0, y: 0.0, width: 0.04, height: 0.5 }), /width must be >= 0.05/);
    assert.throws(() => validateNormalizedRect({ x: 0.6, y: 0.0, width: 0.5, height: 0.5 }), /out of bounds/);
  });
});

// ---------------------------------------------------------------------------
// SUITE 3: Letterboxing, Pillarboxing & Pointer Mapping
// ---------------------------------------------------------------------------
test('SUITE 3: Letterboxing, Pillarboxing & Pointer Mapping', async (t) => {
  await t.test('calculateRenderOffsets with extreme aspect ratios', () => {
    // Ultra-wide banner container (1000 x 10) with 16:9 video
    const banner = calculateRenderOffsets(1000, 10, 1920, 1080);
    assert.strictEqual(banner.renderHeight, 10);
    assert.strictEqual(banner.renderTop, 0);
    assert.ok(banner.renderWidth <= 1000);
    assert.ok(banner.renderLeft >= 0);

    // Ultra-tall strip container (10 x 1000) with 16:9 video
    const strip = calculateRenderOffsets(10, 1000, 1920, 1080);
    assert.strictEqual(strip.renderWidth, 10);
    assert.strictEqual(strip.renderLeft, 0);
    assert.ok(strip.renderHeight <= 1000);
    assert.ok(strip.renderTop >= 0);

    // Identical aspect ratio
    const match = calculateRenderOffsets(960, 540, 1920, 1080);
    assert.strictEqual(match.renderLeft, 0);
    assert.strictEqual(match.renderTop, 0);
    assert.strictEqual(match.renderWidth, 960);
    assert.strictEqual(match.renderHeight, 540);
  });

  await t.test('displayToNormalized boundary pointer clamping', () => {
    const container = { left: 100, top: 100, width: 800, height: 800 };
    // 16:9 video in 800x800 container: letterboxed with renderTop > 0
    const offsets = calculateRenderOffsets(800, 800, 1920, 1080);
    assert.ok(offsets.renderTop > 0);

    // Click above video frame (in top black bar)
    const topBarClick = displayToNormalized(container.left + 400, container.top + 10, container, 1920, 1080);
    assert.strictEqual(topBarClick.y, 0.0, 'Top black bar click must clamp to y=0.0');

    // Click below video frame (in bottom black bar)
    const bottomBarClick = displayToNormalized(container.left + 400, container.top + 790, container, 1920, 1080);
    assert.strictEqual(bottomBarClick.y, 1.0, 'Bottom black bar click must clamp to y=1.0');

    // Click inside video frame center
    const centerClick = displayToNormalized(container.left + 400, container.top + 400, container, 1920, 1080);
    assert.strictEqual(centerClick.x, 0.5);
    assert.strictEqual(centerClick.y, 0.5);
  });

  await t.test('calculateRenderOffsets graceful handling of non-positive dimensions', () => {
    const z1 = calculateRenderOffsets(0, 500, 1920, 1080);
    assert.strictEqual(z1.renderWidth, 0);
    assert.strictEqual(z1.renderLeft, 0);

    const z2 = calculateRenderOffsets(500, -100, 1920, 1080);
    assert.strictEqual(z2.renderHeight, 0);
    assert.strictEqual(z2.renderTop, 0);

    const z3 = calculateRenderOffsets(500, 500, 0, 1080);
    assert.strictEqual(z3.renderLeft, 0);
    assert.strictEqual(z3.renderTop, 0);
  });
});

// ---------------------------------------------------------------------------
// SUITE 4: Dimension Validation, Codec Containment & FFmpeg Parity
// ---------------------------------------------------------------------------
test('SUITE 4: Dimension Validation, Codec Containment & FFmpeg Parity', async (t) => {
  await t.test('All odd dimensions from 3 to 255 maintain strict containment in toSourceCrop', () => {
    for (let dim = 3; dim <= 255; dim += 2) {
      const maxDim = Math.floor(dim / 2) * 2;
      // Test extreme normalized coordinates: bottom-right corner
      const rect = { x: 0.95, y: 0.95, width: 0.05, height: 0.05 };
      const crop = toSourceCrop(rect, dim, dim);
      assert.ok(crop.x + crop.w <= maxDim, `Overflow on ${dim}x${dim}: x(${crop.x}) + w(${crop.w}) = ${crop.x + crop.w} > maxDim(${maxDim})`);
      assert.ok(crop.y + crop.h <= maxDim, `Overflow on ${dim}x${dim}: y(${crop.y}) + h(${crop.h}) = ${crop.y + crop.h} > maxDim(${maxDim})`);
      assert.strictEqual(crop.x % 2, 0, `crop.x not even: ${crop.x}`);
      assert.strictEqual(crop.y % 2, 0, `crop.y not even: ${crop.y}`);
      assert.strictEqual(crop.w % 2, 0, `crop.w not even: ${crop.w}`);
      assert.strictEqual(crop.h % 2, 0, `crop.h not even: ${crop.h}`);
    }
  });

  await t.test('Positive and finite dimension enforcement across all entry points', () => {
    const invalidDims = [0, -1, -1920, NaN, Infinity, -Infinity];

    for (const d of invalidDims) {
      assert.throws(() => toSourceCrop({ x: 0, y: 0, width: 1, height: 1 }, d, 1080));
      assert.throws(() => toSourceCrop({ x: 0, y: 0, width: 1, height: 1 }, 1920, d));
      assert.throws(() => toCanvasOverlay({ x: 0, y: 0, width: 0.3, height: 0.2 }, d, 1920));
      assert.throws(() => toCanvasOverlay({ x: 0, y: 0, width: 0.3, height: 0.2 }, 1080, d));
      assert.throws(() => calculateGameplayFraming({ x: 0, y: 0, w: 100, h: 100 }, d, 1920));
      assert.throws(() => calculateGameplayFraming({ x: 0, y: 0, w: 100, h: 100 }, 1080, d));
      assert.throws(() => calculateGamingCoordinates({
        src_w: d,
        src_h: 1080,
        gameplay_roi: { x: 0, y: 0, width: 1, height: 1 },
        facecam_roi: { x: 0.7, y: 0.05, width: 0.25, height: 0.25 },
      }));
    }
  });

  await t.test('calculateGamingCoordinates produces valid 9:16 vertical plan and FFmpeg filters', () => {
    const plan = calculateGamingCoordinates({
      src_w: 1920,
      src_h: 1080,
      canvas_w: 1080,
      canvas_h: 1920,
      gameplay_roi: { x: 0.1, y: 0.1, width: 0.8, height: 0.8 },
      facecam_roi: { x: 0.7, y: 0.05, width: 0.25, height: 0.25 },
      facecam_placement: 'top-right',
    });

    assert.strictEqual(plan.is_valid, true);
    assert.strictEqual(plan.canvas_width, 1080);
    assert.strictEqual(plan.canvas_height, 1920);
    assert.ok(plan.gameplay_crop.w > 0 && plan.gameplay_crop.w % 2 === 0);
    assert.ok(plan.gameplay_crop.h > 0 && plan.gameplay_crop.h % 2 === 0);
    assert.ok(plan.facecam_crop.w > 0 && plan.facecam_crop.w % 2 === 0);
    assert.ok(plan.facecam_crop.h > 0 && plan.facecam_crop.h % 2 === 0);
    assert.ok(plan.facecam_dest.w > 0 && plan.facecam_dest.w % 2 === 0);
    assert.ok(plan.facecam_dest.h > 0 && plan.facecam_dest.h % 2 === 0);

    // Verify FFmpeg filter syntax
    assert.match(plan.ffmpeg_filtergraph, /\[0:v\]crop=\d+:\d+:\d+:\d+,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920\[v0\]/);
    assert.match(plan.ffmpeg_filtergraph, /\[1:v\]crop=\d+:\d+:\d+:\d+,scale=\d+:\d+:force_original_aspect_ratio=increase,crop=\d+:\d+\[v1\]/);
    assert.match(plan.ffmpeg_filtergraph, /\[v0\]\[v1\]overlay=x=\d+:y=\d+:eof_action=pass:repeatlast=0,setsar=1\[outv\]/);
  });
});
