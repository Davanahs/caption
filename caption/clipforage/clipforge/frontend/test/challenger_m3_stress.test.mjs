/**
 * challenger_m3_stress.test.mjs
 * ==============================
 * Empirical Challenger Stress & Fuzzing Harness for Milestone M3.
 *
 * Authored by: Challenger 1 (Milestone M3)
 * Roles: critic, specialist
 *
 * Adversarially tests:
 * 1. Corner resize handle fuzzing under extreme deltas, boundary pushes, negative/sub-minimum values.
 * 2. Facecam PiP drag bounds and boundary clamping under erratic/extreme translations.
 * 3. Letterbox offset compensation across extreme container aspect ratios (32:9, 9:32, 1:1, tiny containers, fractional/subpixel).
 * 4. Canvas draw call parity: Layer 1 and Layer 2 draw calls operate with finite, non-negative, even-pixel aligned coordinates.
 * 5. Component interaction & event loop simulation with rapid pointer jumps and payload validation.
 */

import test from 'node:test';
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
  getDefaultGameplayRoi,
  getDefaultFacecamRoi,
  getDefaultFacecamOutputRect,
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

// Full HTML5 Canvas 2D context mock including clipping path operations
function createFullMockCanvas(width = DEFAULT_CANVAS_WIDTH, height = DEFAULT_CANVAS_HEIGHT) {
  const drawCalls = [];
  const operations = [];

  const ctx = {
    canvas: null,
    fillStyle: '#000000',
    strokeStyle: '#000000',
    lineWidth: 1,
    globalAlpha: 1.0,

    drawImage: (...args) => {
      let parsed;
      if (args.length === 9) {
        parsed = {
          type: 'drawImage-9',
          image: args[0],
          sx: args[1],
          sy: args[2],
          sw: args[3],
          sh: args[4],
          dx: args[5],
          dy: args[6],
          dw: args[7],
          dh: args[8],
        };
      } else if (args.length === 5) {
        parsed = {
          type: 'drawImage-5',
          image: args[0],
          dx: args[1],
          dy: args[2],
          dw: args[3],
          dh: args[4],
        };
      } else {
        parsed = {
          type: 'drawImage-3',
          image: args[0],
          dx: args[1],
          dy: args[2],
        };
      }
      drawCalls.push(parsed);
      operations.push({ op: 'drawImage', args: parsed });
    },

    fillRect: (x, y, w, h) => { operations.push({ op: 'fillRect', x, y, w, h }); },
    strokeRect: (x, y, w, h) => { operations.push({ op: 'strokeRect', x, y, w, h }); },
    clearRect: (x, y, w, h) => { operations.push({ op: 'clearRect', x, y, w, h }); },
    rect: (x, y, w, h) => { operations.push({ op: 'rect', x, y, w, h }); },
    clip: () => { operations.push({ op: 'clip' }); },
    save: () => { operations.push({ op: 'save' }); },
    restore: () => { operations.push({ op: 'restore' }); },
    beginPath: () => { operations.push({ op: 'beginPath' }); },
    closePath: () => { operations.push({ op: 'closePath' }); },
    stroke: () => { operations.push({ op: 'stroke' }); },
    fill: () => { operations.push({ op: 'fill' }); },
    scale: (sx, sy) => { operations.push({ op: 'scale', sx, sy }); },
    translate: (tx, ty) => { operations.push({ op: 'translate', tx, ty }); },

    getDrawCalls: () => [...drawCalls],
    getOperations: () => [...operations],
    reset: () => {
      drawCalls.length = 0;
      operations.length = 0;
    },
  };

  const canvas = {
    width,
    height,
    clientWidth: width,
    clientHeight: height,
    getContext: (type) => (type === '2d' ? ctx : null),
  };

  ctx.canvas = canvas;
  return { canvas, ctx };
}

// Deterministic PRNG for reproducible fuzzing (Lehmer LCG)
function createRng(seed = 987654321) {
  let s = seed >>> 0;
  return function next() {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

// ==============================================================================
// SUITE 1: CORNER RESIZE HANDLE FUZZING UNDER EXTREME DELTAS & INVERSIONS
// ==============================================================================

test('CHALLENGER SUITE 1: Corner Resize Handles Under Extreme Deltas & Boundary Pushes', async (t) => {
  const handles = ['se', 'ne', 'sw', 'nw'];

  const baseRects = [
    { name: 'Standard center rect', rect: { x: 0.35, y: 0.35, width: 0.30, height: 0.30 } },
    { name: 'Minimum size rect (0.05)', rect: { x: 0.50, y: 0.50, width: 0.05, height: 0.05 } },
    { name: 'Full canvas rect (1.0)', rect: { x: 0.0, y: 0.0, width: 1.0, height: 1.0 } },
    { name: 'Top-left corner', rect: { x: 0.0, y: 0.0, width: 0.15, height: 0.15 } },
    { name: 'Bottom-right corner', rect: { x: 0.85, y: 0.85, width: 0.15, height: 0.15 } },
    { name: 'Top-right corner', rect: { x: 0.85, y: 0.0, width: 0.15, height: 0.15 } },
    { name: 'Bottom-left corner', rect: { x: 0.0, y: 0.85, width: 0.15, height: 0.15 } },
    { name: 'Extreme wide rect', rect: { x: 0.05, y: 0.40, width: 0.90, height: 0.05 } },
    { name: 'Extreme tall rect', rect: { x: 0.40, y: 0.05, width: 0.05, height: 0.90 } },
  ];

  const extremeDeltas = [
    { name: 'Massive outward expansion (+100.0, +100.0)', dx: 100.0, dy: 100.0 },
    { name: 'Massive inward collapse (-100.0, -100.0)', dx: -100.0, dy: -100.0 },
    { name: 'Opposite inversion (+50.0, -50.0)', dx: 50.0, dy: -50.0 },
    { name: 'Opposite inversion (-50.0, +50.0)', dx: -50.0, dy: 50.0 },
    { name: 'Zero delta', dx: 0, dy: 0 },
    { name: 'Subpixel micro-delta (+1e-7, +1e-7)', dx: 1e-7, dy: 1e-7 },
    { name: 'Subpixel micro-delta (-1e-7, -1e-7)', dx: -1e-7, dy: -1e-7 },
    { name: 'Exact min-collapse delta (-w0 + minSize)', dx: -0.25, dy: -0.25 },
  ];

  for (const handle of handles) {
    for (const { name: rName, rect } of baseRects) {
      for (const { name: dName, dx, dy } of extremeDeltas) {
        await t.test(`calculateResize: handle '${handle}' on ${rName} with ${dName}`, () => {
          const resized = calculateResize(rect, handle, dx, dy, MIN_ROI_SIZE);
          const clamped = clampNormalizedRect(resized, MIN_ROI_SIZE);

          // 1. Coordinates and dimensions must be finite
          assert.ok(Number.isFinite(clamped.x), `clamped.x is non-finite: ${clamped.x}`);
          assert.ok(Number.isFinite(clamped.y), `clamped.y is non-finite: ${clamped.y}`);
          assert.ok(Number.isFinite(clamped.width), `clamped.width is non-finite: ${clamped.width}`);
          assert.ok(Number.isFinite(clamped.height), `clamped.height is non-finite: ${clamped.height}`);

          // 2. Minimum dimension invariant
          assert.ok(
            clamped.width >= MIN_ROI_SIZE - 1e-4,
            `Width fell below MIN_ROI_SIZE: ${clamped.width}`
          );
          assert.ok(
            clamped.height >= MIN_ROI_SIZE - 1e-4,
            `Height fell below MIN_ROI_SIZE: ${clamped.height}`
          );

          // 3. Strict [0.0, 1.0] boundary containment
          assert.ok(clamped.x >= 0.0, `clamped.x is negative: ${clamped.x}`);
          assert.ok(clamped.y >= 0.0, `clamped.y is negative: ${clamped.y}`);
          assert.ok(
            clamped.x + clamped.width <= 1.0001,
            `X overflow: ${clamped.x} + ${clamped.width} = ${clamped.x + clamped.width}`
          );
          assert.ok(
            clamped.y + clamped.height <= 1.0001,
            `Y overflow: ${clamped.y} + ${clamped.height} = ${clamped.y + clamped.height}`
          );

          // 4. Anchor preservation for resizing
          if (handle === 'se') {
            // Anchor is Top-Left (x0, y0)
            assert.ok(Math.abs(clamped.x - rect.x) <= 1e-4, `SE anchor X shifted`);
            assert.ok(Math.abs(clamped.y - rect.y) <= 1e-4, `SE anchor Y shifted`);
          } else if (handle === 'ne') {
            // Anchor is Bottom-Left (x0, y0 + h0)
            assert.ok(Math.abs(clamped.x - rect.x) <= 1e-4, `NE anchor X shifted`);
            assert.ok(Math.abs((clamped.y + clamped.height) - (rect.y + rect.height)) <= 1e-4, `NE anchor Bottom shifted`);
          } else if (handle === 'sw') {
            // Anchor is Top-Right (x0 + w0, y0)
            assert.ok(Math.abs((clamped.x + clamped.width) - (rect.x + rect.width)) <= 1e-4, `SW anchor Right shifted`);
            assert.ok(Math.abs(clamped.y - rect.y) <= 1e-4, `SW anchor Y shifted`);
          } else if (handle === 'nw') {
            // Anchor is Bottom-Right (x0 + w0, y0 + h0)
            assert.ok(Math.abs((clamped.x + clamped.width) - (rect.x + rect.width)) <= 1e-4, `NW anchor Right shifted`);
            assert.ok(Math.abs((clamped.y + clamped.height) - (rect.y + rect.height)) <= 1e-4, `NW anchor Bottom shifted`);
          }
        });
      }
    }
  }

  // Fuzz 5,000 randomized resize events
  await t.test('Fuzz 5,000 randomized resize operations with erratic inputs', () => {
    const rng = createRng(1001);
    for (let i = 0; i < 5000; i++) {
      const minS = 0.05;
      const w = minS + rng() * (1.0 - minS);
      const h = minS + rng() * (1.0 - minS);
      const x = rng() * (1.0 - w);
      const y = rng() * (1.0 - h);
      const initial = { x, y, width: w, height: h };

      const handle = handles[Math.floor(rng() * 4)];
      const dx = (rng() - 0.5) * 10.0; // [-5.0, +5.0]
      const dy = (rng() - 0.5) * 10.0;

      const resized = calculateResize(initial, handle, dx, dy, minS);
      const clamped = clampNormalizedRect(resized, minS);

      assert.ok(Number.isFinite(clamped.x) && clamped.x >= 0.0 && clamped.x <= 0.9501);
      assert.ok(Number.isFinite(clamped.y) && clamped.y >= 0.0 && clamped.y <= 0.9501);
      assert.ok(clamped.width >= minS - 1e-4 && clamped.width <= 1.0001);
      assert.ok(clamped.height >= minS - 1e-4 && clamped.height <= 1.0001);
      assert.ok(clamped.x + clamped.width <= 1.0001);
      assert.ok(clamped.y + clamped.height <= 1.0001);
    }
  });
});

// ==============================================================================
// SUITE 2: FACECAM PIP DRAG BOUNDS & BOUNDARY CLAMPING
// ==============================================================================

test('CHALLENGER SUITE 2: Facecam PiP Drag Bounds & Clamping Under Erratic Translations', async (t) => {
  const initialPositions = [
    { name: 'Top-Right default preset', rect: getDefaultFacecamOutputRect('top-right') },
    { name: 'Top-Left preset', rect: getDefaultFacecamOutputRect('top-left') },
    { name: 'Bottom-Left preset', rect: getDefaultFacecamOutputRect('bottom-left') },
    { name: 'Bottom-Right preset', rect: getDefaultFacecamOutputRect('bottom-right') },
    { name: 'Center placement', rect: { x: 0.35, y: 0.39, width: 0.30, height: 0.22 } },
    { name: 'Tiny PiP (0.05x0.05)', rect: { x: 0.5, y: 0.5, width: 0.05, height: 0.05 } },
    { name: 'Huge PiP (0.90x0.90)', rect: { x: 0.05, y: 0.05, width: 0.90, height: 0.90 } },
  ];

  const erraticTranslations = [
    { name: 'Violent right drag (+20.0)', dx: 20.0, dy: 0 },
    { name: 'Violent left drag (-20.0)', dx: -20.0, dy: 0 },
    { name: 'Violent bottom drag (+20.0)', dx: 0, dy: 20.0 },
    { name: 'Violent top drag (-20.0)', dx: 0, dy: -20.0 },
    { name: 'Extreme diagonal drag (+100.0, +100.0)', dx: 100.0, dy: 100.0 },
    { name: 'Extreme diagonal drag (-100.0, -100.0)', dx: -100.0, dy: -100.0 },
    { name: 'Micro drag (1e-6)', dx: 1e-6, dy: 1e-6 },
    { name: 'Zero drag', dx: 0, dy: 0 },
  ];

  for (const { name: pName, rect } of initialPositions) {
    for (const { name: tName, dx, dy } of erraticTranslations) {
      await t.test(`applyDrag: ${pName} with ${tName}`, () => {
        const moved = applyDrag(rect, dx, dy);

        // Invariant 1: Width and height MUST remain strictly identical
        assert.equal(moved.width, rect.width, `Width mutated during drag! Expected ${rect.width}, got ${moved.width}`);
        assert.equal(moved.height, rect.height, `Height mutated during drag! Expected ${rect.height}, got ${moved.height}`);

        // Invariant 2: Left and top non-negative
        assert.ok(moved.x >= 0.0, `moved.x negative: ${moved.x}`);
        assert.ok(moved.y >= 0.0, `moved.y negative: ${moved.y}`);

        // Invariant 3: Right and bottom strictly bounded by 1.0
        assert.ok(
          moved.x + moved.width <= 1.0001,
          `Right edge overflow: ${moved.x} + ${moved.width} = ${moved.x + moved.width}`
        );
        assert.ok(
          moved.y + moved.height <= 1.0001,
          `Bottom edge overflow: ${moved.y} + ${moved.height} = ${moved.y + moved.height}`
        );

        // Invariant 4: Maximum boundary clamping checks
        if (dx >= 1.0) {
          assert.ok(
            Math.abs(moved.x - (1.0 - rect.width)) <= 1e-4,
            `Failed right boundary clamp: expected ${1.0 - rect.width}, got ${moved.x}`
          );
        }
        if (dx <= -1.0) {
          assert.equal(moved.x, 0.0, `Failed left boundary clamp: expected 0.0, got ${moved.x}`);
        }
        if (dy >= 1.0) {
          assert.ok(
            Math.abs(moved.y - (1.0 - rect.height)) <= 1e-4,
            `Failed bottom boundary clamp: expected ${1.0 - rect.height}, got ${moved.y}`
          );
        }
        if (dy <= -1.0) {
          assert.equal(moved.y, 0.0, `Failed top boundary clamp: expected 0.0, got ${moved.y}`);
        }
      });
    }
  }

  // Fuzz 5,000 randomized drag operations
  await t.test('Fuzz 5,000 randomized drag operations on facecam overlay', () => {
    const rng = createRng(2002);
    for (let i = 0; i < 5000; i++) {
      const w = 0.10 + rng() * 0.40;
      const h = 0.10 + rng() * 0.40;
      const x = rng() * (1.0 - w);
      const y = rng() * (1.0 - h);
      const initial = { x, y, width: w, height: h };

      const dx = (rng() - 0.5) * 5.0;
      const dy = (rng() - 0.5) * 5.0;

      const moved = applyDrag(initial, dx, dy);

      assert.equal(moved.width, initial.width);
      assert.equal(moved.height, initial.height);
      assert.ok(moved.x >= 0.0 && moved.x <= 1.0001 - moved.width);
      assert.ok(moved.y >= 0.0 && moved.y <= 1.0001 - moved.height);
    }
  });
});

// ==============================================================================
// SUITE 3: LETTERBOX COMPENSATION ACROSS EXTREME CONTAINER ASPECT RATIOS
// ==============================================================================

test('CHALLENGER SUITE 3: Letterbox Compensation Across Extreme Container Ratios', async (t) => {
  const containerAspects = [
    { name: '32:9 Super-Ultrawide Monitor', cw: 5120, ch: 1440 },
    { name: '32:9 Desktop Dual-QHD', cw: 3840, ch: 1080 },
    { name: '9:32 Ultra-tall Vertical Display', cw: 1080, ch: 3840 },
    { name: '9:32 Mobile Scroll Rig', cw: 720, ch: 2560 },
    { name: '1:1 Square Viewport (Large)', cw: 1200, ch: 1200 },
    { name: '1:1 Square Viewport (Small)', cw: 400, ch: 400 },
    { name: '4:3 Legacy Viewport', cw: 1024, ch: 768 },
    { name: '21:9 Ultrawide Display', cw: 2560, ch: 1080 },
    { name: '100:1 Extreme Ribbon', cw: 10000, ch: 100 },
    { name: '1:100 Extreme Column', cw: 100, ch: 10000 },
    { name: 'Micro 2x2 container', cw: 2, ch: 2 },
    { name: 'Micro 10x10 container', cw: 10, ch: 10 },
    { name: 'Subpixel Fractional container', cw: 853.7, ch: 479.3 },
  ];

  const videoAspects = [
    { name: '16:9 1080p Standard', vw: 1920, vh: 1080 },
    { name: '16:9 4K UHD', vw: 3840, vh: 2160 },
    { name: '9:16 Vertical Shorts', vw: 1080, vh: 1920 },
    { name: '21:9 Ultrawide Video', vw: 2560, vh: 1080 },
    { name: '32:9 Super-Ultrawide Video', vw: 5120, vh: 1440 },
    { name: '1:1 Square Video', vw: 1080, vh: 1080 },
    { name: '4:3 Standard Video', vw: 1440, vh: 1080 },
    { name: 'Odd dimension video', vw: 1921, vh: 1081 },
  ];

  for (const c of containerAspects) {
    for (const v of videoAspects) {
      await t.test(`Letterbox offsets: container ${c.name} (${c.cw}x${c.ch}) with video ${v.name} (${v.vw}x${v.vh})`, () => {
        const offsets = calculateRenderOffsets(c.cw, c.ch, v.vw, v.vh);

        // 1. Offsets must be finite and non-negative
        assert.ok(Number.isFinite(offsets.renderLeft), `renderLeft not finite: ${offsets.renderLeft}`);
        assert.ok(Number.isFinite(offsets.renderTop), `renderTop not finite: ${offsets.renderTop}`);
        assert.ok(Number.isFinite(offsets.renderWidth), `renderWidth not finite: ${offsets.renderWidth}`);
        assert.ok(Number.isFinite(offsets.renderHeight), `renderHeight not finite: ${offsets.renderHeight}`);

        assert.ok(offsets.renderLeft >= 0, `renderLeft negative: ${offsets.renderLeft}`);
        assert.ok(offsets.renderTop >= 0, `renderTop negative: ${offsets.renderTop}`);
        assert.ok(offsets.renderWidth > 0, `renderWidth non-positive: ${offsets.renderWidth}`);
        assert.ok(offsets.renderHeight > 0, `renderHeight non-positive: ${offsets.renderHeight}`);

        // 2. Fits within container bounds (with 1px rounding tolerance)
        assert.ok(
          offsets.renderLeft + offsets.renderWidth <= Math.ceil(c.cw) + 1,
          `Render width overflow container: ${offsets.renderLeft} + ${offsets.renderWidth} > ${c.cw}`
        );
        assert.ok(
          offsets.renderTop + offsets.renderHeight <= Math.ceil(c.ch) + 1,
          `Render height overflow container: ${offsets.renderTop} + ${offsets.renderHeight} > ${c.ch}`
        );

        // 3. Pointer conversion robustness across extreme points
        const containerRect = { left: 100, top: 100, width: c.cw, height: c.ch };
        const testPoints = [
          // Center of container
          { cx: 100 + c.cw / 2, cy: 100 + c.ch / 2 },
          // Top-left of container (may be in letterbox)
          { cx: 100, cy: 100 },
          // Bottom-right of container
          { cx: 100 + c.cw, cy: 100 + c.ch },
          // Far outside negative
          { cx: -50000, cy: -50000 },
          // Far outside positive
          { cx: 50000, cy: 50000 },
          // Active render rect top-left
          { cx: 100 + offsets.renderLeft, cy: 100 + offsets.renderTop },
          // Active render rect bottom-right
          { cx: 100 + offsets.renderLeft + offsets.renderWidth, cy: 100 + offsets.renderTop + offsets.renderHeight },
        ];

        for (const pt of testPoints) {
          const norm = displayToNormalized(pt.cx, pt.cy, containerRect, v.vw, v.vh);
          assert.ok(Number.isFinite(norm.x), `norm.x is NaN or Inf: ${norm.x}`);
          assert.ok(Number.isFinite(norm.y), `norm.y is NaN or Inf: ${norm.y}`);
          assert.ok(norm.x >= 0.0 && norm.x <= 1.0, `norm.x un-clamped: ${norm.x}`);
          assert.ok(norm.y >= 0.0 && norm.y <= 1.0, `norm.y un-clamped: ${norm.y}`);

          const letterboxRes = displayToNormalizedLetterbox(pt.cx, pt.cy, containerRect, v.vw, v.vh);
          assert.ok(Number.isFinite(letterboxRes.normalized_pointer.x));
          assert.ok(Number.isFinite(letterboxRes.normalized_pointer.y));
          assert.ok(letterboxRes.normalized_pointer.x >= 0.0 && letterboxRes.normalized_pointer.x <= 1.0);
          assert.ok(letterboxRes.normalized_pointer.y >= 0.0 && letterboxRes.normalized_pointer.y <= 1.0);
        }
      });
    }
  }

  await t.test('Graceful fallback for zero, negative, or degenerate inputs', () => {
    const zeroC = calculateRenderOffsets(0, 0, 1920, 1080);
    assert.equal(zeroC.renderWidth, 0);
    assert.equal(zeroC.renderHeight, 0);

    const negC = calculateRenderOffsets(-100, -100, 1920, 1080);
    assert.equal(negC.renderWidth, 0);
    assert.equal(negC.renderHeight, 0);

    const zeroV = calculateRenderOffsets(800, 600, 0, 0);
    assert.equal(zeroV.renderWidth, 800);
    assert.equal(zeroV.renderHeight, 600);

    // Empty container pointer mapping
    const emptyNorm = displayToNormalized(100, 100, { left: 0, top: 0, width: 0, height: 0 });
    assert.equal(emptyNorm.x, 0);
    assert.equal(emptyNorm.y, 0);
  });
});

// ==============================================================================
// SUITE 4: CANVAS DRAW CALL PARITY & EVEN-PIXEL CODEC ALIGNMENT
// ==============================================================================

test('CHALLENGER SUITE 4: Canvas Draw Call Parity & Even-Pixel Invariants', async (t) => {
  const resolutions = [
    { name: '1080p Standard', w: 1920, h: 1080 },
    { name: '720p HD', w: 1280, h: 720 },
    { name: '4K UHD', w: 3840, h: 2160 },
    { name: '1440p QHD', w: 2560, h: 1440 },
    { name: 'Odd dimension 1081p', w: 1921, h: 1081 },
    { name: 'Odd dimension 721p', w: 1281, h: 721 },
    { name: 'Sub-HD 481p odd', w: 853, h: 481 },
    { name: 'Vertical 9:16 video', w: 1080, h: 1920 },
    { name: 'Square 1:1 video', w: 1080, h: 1080 },
    { name: 'Ultrawide 21:9', w: 2560, h: 1080 },
    { name: 'Super-Ultrawide 32:9', w: 5120, h: 1440 },
  ];

  const presets = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];

  for (const { name: resName, w: srcW, h: srcH } of resolutions) {
    for (const preset of presets) {
      await t.test(`Draw call parity: ${resName} (${srcW}x${srcH}) with facecam preset ${preset}`, () => {
        const { canvas, ctx } = createFullMockCanvas(DEFAULT_CANVAS_WIDTH, DEFAULT_CANVAS_HEIGHT);

        const gameplayRoi = getDefaultGameplayRoi();
        const facecamRoi = getDefaultFacecamRoi();
        const facecamOutputRect = getFacecamPreset(preset);

        // Compute crops matching GamingCompositeCanvas.tsx lines 145-185
        const gCrop = toEvenPixels(gameplayRoi, srcW, srcH);
        const fCrop = toEvenPixels(facecamRoi, srcW, srcH);
        const fDest = toCanvasOverlay(facecamOutputRect, canvas.width, canvas.height);

        // Execute simulated Layer 1 & Layer 2 draw calls
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Layer 1 (Gameplay)
        ctx.drawImage('sourceVideo', gCrop.x, gCrop.y, gCrop.w, gCrop.h, 0, 0, canvas.width, canvas.height);

        // Layer 2 (Facecam PiP with clip)
        ctx.save();
        ctx.beginPath();
        ctx.rect(fDest.x, fDest.y, fDest.w, fDest.h);
        ctx.clip();
        ctx.drawImage('sourceVideo', fCrop.x, fCrop.y, fCrop.w, fCrop.h, fDest.x, fDest.y, fDest.w, fDest.h);
        ctx.restore();

        const drawCalls = ctx.getDrawCalls();
        assert.equal(drawCalls.length, 2, `Expected exactly 2 drawImage calls, got ${drawCalls.length}`);

        const [drawLayer1, drawLayer2] = drawCalls;

        // Verify Layer 1 (Gameplay)
        // 1. All arguments finite
        assert.ok(Number.isFinite(drawLayer1.sx));
        assert.ok(Number.isFinite(drawLayer1.sy));
        assert.ok(Number.isFinite(drawLayer1.sw));
        assert.ok(Number.isFinite(drawLayer1.sh));
        assert.ok(Number.isFinite(drawLayer1.dx));
        assert.ok(Number.isFinite(drawLayer1.dy));
        assert.ok(Number.isFinite(drawLayer1.dw));
        assert.ok(Number.isFinite(drawLayer1.dh));

        // 2. All arguments non-negative
        assert.ok(drawLayer1.sx >= 0);
        assert.ok(drawLayer1.sy >= 0);
        assert.ok(drawLayer1.sw > 0);
        assert.ok(drawLayer1.sh > 0);
        assert.ok(drawLayer1.dx >= 0);
        assert.ok(drawLayer1.dy >= 0);
        assert.equal(drawLayer1.dw, DEFAULT_CANVAS_WIDTH);
        assert.equal(drawLayer1.dh, DEFAULT_CANVAS_HEIGHT);

        // 3. Even-pixel codec alignment on source crop
        assert.equal(drawLayer1.sx % 2, 0, `Layer 1 sx ${drawLayer1.sx} is not even`);
        assert.equal(drawLayer1.sy % 2, 0, `Layer 1 sy ${drawLayer1.sy} is not even`);
        assert.equal(drawLayer1.sw % 2, 0, `Layer 1 sw ${drawLayer1.sw} is not even`);
        assert.equal(drawLayer1.sh % 2, 0, `Layer 1 sh ${drawLayer1.sh} is not even`);

        // 4. Source crop stays within source dimensions (even dimension max)
        const maxSrcW = Math.floor(srcW / 2) * 2;
        const maxSrcH = Math.floor(srcH / 2) * 2;
        assert.ok(drawLayer1.sx + drawLayer1.sw <= maxSrcW);
        assert.ok(drawLayer1.sy + drawLayer1.sh <= maxSrcH);

        // Verify Layer 2 (Facecam PiP)
        // 1. All arguments finite
        assert.ok(Number.isFinite(drawLayer2.sx));
        assert.ok(Number.isFinite(drawLayer2.sy));
        assert.ok(Number.isFinite(drawLayer2.sw));
        assert.ok(Number.isFinite(drawLayer2.sh));
        assert.ok(Number.isFinite(drawLayer2.dx));
        assert.ok(Number.isFinite(drawLayer2.dy));
        assert.ok(Number.isFinite(drawLayer2.dw));
        assert.ok(Number.isFinite(drawLayer2.dh));

        // 2. All arguments non-negative
        assert.ok(drawLayer2.sx >= 0);
        assert.ok(drawLayer2.sy >= 0);
        assert.ok(drawLayer2.sw > 0);
        assert.ok(drawLayer2.sh > 0);
        assert.ok(drawLayer2.dx >= 0);
        assert.ok(drawLayer2.dy >= 0);
        assert.ok(drawLayer2.dw > 0);
        assert.ok(drawLayer2.dh > 0);

        // 3. Even-pixel alignment on both source crop and canvas destination
        assert.equal(drawLayer2.sx % 2, 0, `Layer 2 sx ${drawLayer2.sx} not even`);
        assert.equal(drawLayer2.sy % 2, 0, `Layer 2 sy ${drawLayer2.sy} not even`);
        assert.equal(drawLayer2.sw % 2, 0, `Layer 2 sw ${drawLayer2.sw} not even`);
        assert.equal(drawLayer2.sh % 2, 0, `Layer 2 sh ${drawLayer2.sh} not even`);

        assert.equal(drawLayer2.dx % 2, 0, `Layer 2 dx ${drawLayer2.dx} not even`);
        assert.equal(drawLayer2.dy % 2, 0, `Layer 2 dy ${drawLayer2.dy} not even`);
        assert.equal(drawLayer2.dw % 2, 0, `Layer 2 dw ${drawLayer2.dw} not even`);
        assert.equal(drawLayer2.dh % 2, 0, `Layer 2 dh ${drawLayer2.dh} not even`);

        // 4. Bounded strictly inside source video and canvas dimensions
        assert.ok(drawLayer2.sx + drawLayer2.sw <= maxSrcW);
        assert.ok(drawLayer2.sy + drawLayer2.sh <= maxSrcH);
        assert.ok(drawLayer2.dx + drawLayer2.dw <= DEFAULT_CANVAS_WIDTH);
        assert.ok(drawLayer2.dy + drawLayer2.dh <= DEFAULT_CANVAS_HEIGHT);
      });
    }
  }

  // Fuzz 3,000 arbitrary custom layouts into canvas draw calls
  await t.test('Fuzz 3,000 arbitrary custom layouts into canvas draw calls', () => {
    const rng = createRng(3003);
    for (let i = 0; i < 3000; i++) {
      const srcW = 320 + Math.floor(rng() * 3520); // 320 to 3840
      const srcH = 240 + Math.floor(rng() * 1920); // 240 to 2160

      const gW = 0.05 + rng() * 0.95;
      const gH = 0.05 + rng() * 0.95;
      const gX = rng() * (1.0 - gW);
      const gY = rng() * (1.0 - gH);

      const fW = 0.05 + rng() * 0.95;
      const fH = 0.05 + rng() * 0.95;
      const fX = rng() * (1.0 - fW);
      const fY = rng() * (1.0 - fH);

      const oW = 0.05 + rng() * 0.95;
      const oH = 0.05 + rng() * 0.95;
      const oX = rng() * (1.0 - oW);
      const oY = rng() * (1.0 - oH);

      const gCrop = toEvenPixels({ x: gX, y: gY, width: gW, height: gH }, srcW, srcH);
      const fCrop = toEvenPixels({ x: fX, y: fY, width: fW, height: fH }, srcW, srcH);
      const fDest = toCanvasOverlay({ x: oX, y: oY, width: oW, height: oH }, 1080, 1920);

      // Verify all even and non-negative
      assert.equal(gCrop.x % 2, 0);
      assert.equal(gCrop.y % 2, 0);
      assert.equal(gCrop.w % 2, 0);
      assert.equal(gCrop.h % 2, 0);

      assert.equal(fCrop.x % 2, 0);
      assert.equal(fCrop.y % 2, 0);
      assert.equal(fCrop.w % 2, 0);
      assert.equal(fCrop.h % 2, 0);

      assert.equal(fDest.x % 2, 0);
      assert.equal(fDest.y % 2, 0);
      assert.equal(fDest.w % 2, 0);
      assert.equal(fDest.h % 2, 0);

      const maxSrcW = Math.floor(srcW / 2) * 2;
      const maxSrcH = Math.floor(srcH / 2) * 2;

      assert.ok(gCrop.x + gCrop.w <= maxSrcW);
      assert.ok(gCrop.y + gCrop.h <= maxSrcH);
      assert.ok(fCrop.x + fCrop.w <= maxSrcW);
      assert.ok(fCrop.y + fCrop.h <= maxSrcH);
      assert.ok(fDest.x + fDest.w <= 1080);
      assert.ok(fDest.y + fDest.h <= 1920);
    }
  });
});

// ==============================================================================
// SUITE 5: COMPONENT EVENT LOOP SIMULATION & ZERO-CAPTION VALIDATION
// ==============================================================================

test('CHALLENGER SUITE 5: Component Event Loop Simulation & R5 Zero-Caption Mandate', async (t) => {
  // Test simulated state transitions of facecam overlay drag and resize
  await t.test('Simulated pointer event sequence on facecam overlay produces valid GamingLayout', () => {
    let currentRect = getDefaultFacecamOutputRect('top-right');
    let currentPlacement = 'top-right';

    const notifyChange = (nextRect, nextPlacement) => {
      currentRect = nextRect;
      currentPlacement = nextPlacement;
    };

    const containerRect = { width: 270, height: 480 };

    // 1. Move drag sequence
    const startX = 200;
    const startY = 50;
    const initialRect = { ...currentRect };

    const movePointer = (clientX, clientY) => {
      const deltaX = (clientX - startX) / containerRect.width;
      const deltaY = (clientY - startY) / containerRect.height;
      const nextRect = applyDrag(initialRect, deltaX, deltaY);
      notifyChange(nextRect, 'custom');
    };

    // Step 1: Drag right and down past edge
    movePointer(500, 300);
    assert.equal(currentPlacement, 'custom');
    assert.ok(currentRect.x + currentRect.width <= 1.0001);
    assert.ok(currentRect.y + currentRect.height <= 1.0001);

    // Step 2: Drag negative past top-left edge
    movePointer(-200, -100);
    assert.equal(currentRect.x, 0.0);
    assert.equal(currentRect.y, 0.0);

    // 2. Corner resize sequence on handle 'se'
    const resizeHandle = 'se';
    const resizeStartX = 100;
    const resizeStartY = 100;
    const resizeInitialRect = { ...currentRect };

    const resizePointer = (clientX, clientY) => {
      const deltaX = (clientX - resizeStartX) / containerRect.width;
      const deltaY = (clientY - resizeStartY) / containerRect.height;
      const resized = calculateResize(resizeInitialRect, resizeHandle, deltaX, deltaY, MIN_ROI_SIZE);
      const clamped = clampNormalizedRect(resized, MIN_ROI_SIZE);
      notifyChange(clamped, 'custom');
    };

    // Resize inward past minimum size
    resizePointer(-500, -500);
    assert.ok(currentRect.width >= MIN_ROI_SIZE - 1e-4);
    assert.ok(currentRect.height >= MIN_ROI_SIZE - 1e-4);

    // Resize outward past container right
    resizePointer(1000, 1000);
    assert.ok(currentRect.x + currentRect.width <= 1.0001);
    assert.ok(currentRect.y + currentRect.height <= 1.0001);

    // 3. Construct outgoing payload and audit
    const payload = {
      mode: 'gaming',
      gameplay_roi: getDefaultGameplayRoi(),
      facecam_roi: getDefaultFacecamRoi(),
      facecam_placement: currentPlacement,
      facecam_output_rect: currentRect,
      canvas_width: DEFAULT_CANVAS_WIDTH,
      canvas_height: DEFAULT_CANVAS_HEIGHT,
    };

    const validated = validateGamingCoordinates(payload);
    assert.equal(validated.valid, true, `Payload validation failed: ${validated.errors.join(', ')}`);

    // 4. Strict R5 Zero-Caption Mandate: No caption/subtitle tokens in serialized JSON
    const serialized = JSON.stringify(payload);
    for (const forbidden of ['caption', 'subtitle', 'srt', 'vtt', 'ass']) {
      assert.ok(
        !serialized.toLowerCase().includes(forbidden),
        `Forbidden caption token '${forbidden}' detected in payload: ${serialized}`
      );
    }
  });
});
