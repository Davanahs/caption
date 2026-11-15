import test from 'node:test';
import assert from 'node:assert/strict';

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
  toSourceCrop,
  toCanvasOverlay,
  calculateGameplayFraming,
  calculateGameplayFillFraming,
  validateNormalizedRect,
  validateGamingLayout,
  validateGamingCoordinates,
  calculateGamingCoordinates,
  MIN_ROI_SIZE,
  DEFAULT_CANVAS_WIDTH,
  DEFAULT_CANVAS_HEIGHT,
} from '../lib/gamingCoordinates.ts';

// Simple deterministic PRNG for reproducible property fuzzing
function createRng(seed = 123456789) {
  let s = seed;
  return function next() {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

test('CHALLENGER SUITE 1: Extreme Container Aspect Ratios (32:9, 1:1, 9:21, 100:1, 1:100)', async (t) => {
  const videoResolutions = [
    { name: '16:9 1080p', w: 1920, h: 1080 },
    { name: '21:9 Ultrawide', w: 2560, h: 1080 },
    { name: '32:9 Super-Ultrawide', w: 5120, h: 1440 },
    { name: '4:3 Standard', w: 1440, h: 1080 },
    { name: '1:1 Square', w: 1080, h: 1080 },
    { name: '9:16 Vertical Shorts', w: 1080, h: 1920 },
    { name: '9:21 Ultra-tall Phone', w: 1080, h: 2520 },
    { name: 'Odd dimension', w: 1921, h: 1081 },
  ];

  const containerSizes = [
    { name: '32:9 Super-Ultrawide monitor', cw: 3840, ch: 1080 },
    { name: '32:9 Large monitor', cw: 5120, ch: 1440 },
    { name: '1:1 Square viewport', cw: 800, ch: 800 },
    { name: '1:1 Large Square viewport', cw: 1400, ch: 1400 },
    { name: '9:21 Tall Mobile viewport', cw: 900, ch: 2100 },
    { name: '9:21 Fullscreen Mobile', cw: 1080, ch: 2520 },
    { name: 'Extreme 100:1 Ribbon', cw: 10000, ch: 100 },
    { name: 'Extreme 1:100 Column', cw: 100, ch: 10000 },
    { name: 'Micro 2x2 container', cw: 2, ch: 2 },
    { name: 'Fractional Subpixel container', cw: 853.6, ch: 480.2 },
  ];

  for (const c of containerSizes) {
    for (const v of videoResolutions) {
      await t.test(`calculateRenderOffsets: ${c.name} (${c.cw}x${c.ch}) with video ${v.name} (${v.w}x${v.h})`, () => {
        const offsets = calculateRenderOffsets(c.cw, c.ch, v.w, v.h);

        // Invariant 1: Non-negative offsets
        assert.ok(offsets.renderLeft >= 0, `renderLeft must be >= 0, got ${offsets.renderLeft}`);
        assert.ok(offsets.renderTop >= 0, `renderTop must be >= 0, got ${offsets.renderTop}`);

        // Invariant 2: Positive render dimensions bounded by container
        assert.ok(offsets.renderWidth > 0, `renderWidth must be > 0, got ${offsets.renderWidth}`);
        assert.ok(offsets.renderHeight > 0, `renderHeight must be > 0, got ${offsets.renderHeight}`);
        assert.ok(offsets.renderWidth <= Math.ceil(c.cw) + 1, `renderWidth ${offsets.renderWidth} exceeds container ${c.cw}`);
        assert.ok(offsets.renderHeight <= Math.ceil(c.ch) + 1, `renderHeight ${offsets.renderHeight} exceeds container ${c.ch}`);

        // Invariant 3: Total span fits container within 1px rounding tolerance
        assert.ok(
          offsets.renderLeft + offsets.renderWidth <= Math.ceil(c.cw) + 1,
          `Horizontal span ${offsets.renderLeft} + ${offsets.renderWidth} = ${offsets.renderLeft + offsets.renderWidth} exceeds ${c.cw}`
        );
        assert.ok(
          offsets.renderTop + offsets.renderHeight <= Math.ceil(c.ch) + 1,
          `Vertical span ${offsets.renderTop} + ${offsets.renderHeight} = ${offsets.renderTop + offsets.renderHeight} exceeds ${c.ch}`
        );

        // Invariant 4: Centering symmetry (left bar equals right bar, top equals bottom within 1px)
        const rightBar = c.cw - (offsets.renderLeft + offsets.renderWidth);
        const bottomBar = c.ch - (offsets.renderTop + offsets.renderHeight);
        assert.ok(
          Math.abs(offsets.renderLeft - rightBar) <= 2,
          `Horizontal asymmetry: left ${offsets.renderLeft} vs right ${rightBar}`
        );
        assert.ok(
          Math.abs(offsets.renderTop - bottomBar) <= 2,
          `Vertical asymmetry: top ${offsets.renderTop} vs bottom ${bottomBar}`
        );

        // Invariant 5: Aspect ratio preservation within integer rounding
        const videoAR = v.w / v.h;
        const renderAR = offsets.renderWidth / offsets.renderHeight;
        if (offsets.renderWidth > 10 && offsets.renderHeight > 10) {
          const arDiff = Math.abs(videoAR - renderAR) / videoAR;
          assert.ok(arDiff < 0.05, `Aspect ratio distortion ${arDiff}: expected ${videoAR}, got ${renderAR}`);
        }
      });
    }
  }

  await t.test('calculateRenderOffsets handles zero and negative dimensions without crash or NaN', () => {
    const zeroC = calculateRenderOffsets(0, 500, 1920, 1080);
    assert.equal(zeroC.renderWidth, 0);
    assert.equal(zeroC.renderLeft, 0);

    const zeroV = calculateRenderOffsets(800, 600, 0, 1080);
    assert.equal(zeroV.renderWidth, 800);
    assert.equal(zeroV.renderHeight, 600);

    const negC = calculateRenderOffsets(-100, -200, 1920, 1080);
    assert.equal(negC.renderWidth, 0);
    assert.equal(negC.renderHeight, 0);
  });
});

test('CHALLENGER SUITE 2: Subpixel Clicks, Fractional Positions & Letterbox/Pillarbox Padding', async (t) => {
  const container = { left: 50.5, top: 40.25, width: 800, height: 600 };
  const videoW = 1920;
  const videoH = 1080;
  const offsets = calculateRenderOffsets(container.width, container.height, videoW, videoH);
  // 16:9 in 800x600 (4:3) -> Letterbox with top/bottom bars
  // renderWidth = 800, renderHeight = 450, renderTop = 75, renderLeft = 0

  await t.test('Subpixel click exactly at letterbox boundary clamps without drift', () => {
    const activeTopClientY = container.top + offsets.renderTop; // 40.25 + 75 = 115.25
    const activeBottomClientY = activeTopClientY + offsets.renderHeight; // 115.25 + 450 = 565.25

    // Click 0.001px above active video (in black bar)
    const justAbove = displayToNormalized(container.left + 400, activeTopClientY - 0.001, container, videoW, videoH);
    assert.equal(justAbove.y, 0.0);

    // Click exactly on the boundary
    const onBoundary = displayToNormalized(container.left + 400, activeTopClientY, container, videoW, videoH);
    assert.equal(onBoundary.y, 0.0);

    // Click 0.001px inside active video
    const justBelow = displayToNormalized(container.left + 400, activeTopClientY + 0.001, container, videoW, videoH);
    assert.ok(justBelow.y >= 0.0 && justBelow.y <= 0.0001);

    // Click 0.001px below bottom boundary (in bottom black bar)
    const justPastBottom = displayToNormalized(container.left + 400, activeBottomClientY + 0.001, container, videoW, videoH);
    assert.equal(justPastBottom.y, 1.0);
  });

  await t.test('Clicks deep in black bars clamp strictly to 0.0 and 1.0', () => {
    // Top bar click (clientY = container.top = 40.25)
    const topBarClick = displayToNormalized(container.left + 400, container.top + 5, container, videoW, videoH);
    assert.equal(topBarClick.y, 0.0);
    assert.equal(topBarClick.x, 0.5);

    // Bottom bar click (clientY = container.top + container.height - 5)
    const bottomBarClick = displayToNormalized(container.left + 400, container.top + container.height - 5, container, videoW, videoH);
    assert.equal(bottomBarClick.y, 1.0);
    assert.equal(bottomBarClick.x, 0.5);
  });

  await t.test('Clicks far outside container (-10000, +10000) clamp safely to [0.0, 1.0]', () => {
    const farLeftTop = displayToNormalized(-10000, -10000, container, videoW, videoH);
    assert.equal(farLeftTop.x, 0.0);
    assert.equal(farLeftTop.y, 0.0);

    const farRightBottom = displayToNormalized(10000, 10000, container, videoW, videoH);
    assert.equal(farRightBottom.x, 1.0);
    assert.equal(farRightBottom.y, 1.0);
  });

  await t.test('displayToNormalizedLetterbox returns both render_rect and clamped pointer', () => {
    const res = displayToNormalizedLetterbox(container.left + 400, container.top + 300, container, videoW, videoH);
    assert.ok(res.render_rect);
    assert.equal(res.render_rect.width, offsets.renderWidth);
    assert.equal(res.render_rect.height, offsets.renderHeight);
    assert.equal(res.render_rect.x, offsets.renderLeft);
    assert.equal(res.render_rect.y, offsets.renderTop);
    assert.equal(res.normalized_pointer.x, 0.5);
    assert.equal(res.normalized_pointer.y, 0.5);
  });

  await t.test('Roundtrip fidelity: normalizedToDisplay(displayToNormalized(p)) recovers position <= 1px', () => {
    const testPoints = [
      { cx: container.left + 100, cy: container.top + offsets.renderTop + 50 },
      { cx: container.left + 400, cy: container.top + offsets.renderTop + 225 },
      { cx: container.left + 750, cy: container.top + offsets.renderTop + 400 },
    ];

    for (const pt of testPoints) {
      const norm = displayToNormalized(pt.cx, pt.cy, container, videoW, videoH);
      const disp = normalizedToDisplay(
        { x: norm.x, y: norm.y, width: 0.1, height: 0.1 },
        container.width,
        container.height,
        offsets
      );

      const recoveredX = container.left + disp.left;
      const recoveredY = container.top + disp.top;
      assert.ok(
        Math.abs(recoveredX - pt.cx) <= 1.0,
        `X mismatch: original ${pt.cx}, recovered ${recoveredX}`
      );
      assert.ok(
        Math.abs(recoveredY - pt.cy) <= 1.0,
        `Y mismatch: original ${pt.cy}, recovered ${recoveredY}`
      );
    }
  });

  await t.test('High-density subpixel grid monotonicity test (1,000 steps)', () => {
    let prevNormX = -1;
    for (let step = 0; step <= 1000; step++) {
      const clientX = container.left + offsets.renderLeft + (step / 1000) * offsets.renderWidth;
      const norm = displayToNormalized(clientX, container.top + offsets.renderTop + 100, container, videoW, videoH);

      assert.ok(norm.x >= 0.0 && norm.x <= 1.0, `norm.x out of bounds: ${norm.x}`);
      assert.ok(norm.x >= prevNormX, `Monotonicity violated: step ${step}, prev ${prevNormX}, current ${norm.x}`);
      prevNormX = norm.x;
    }
    assert.equal(prevNormX, 1.0);
  });
});

test('CHALLENGER SUITE 3: Boundary Dragging Past Bounds & Invariant Verification', async (t) => {
  const initialRects = [
    { name: 'Top-Left origin', rect: { x: 0.0, y: 0.0, width: 0.25, height: 0.25 } },
    { name: 'Bottom-Right boundary', rect: { x: 0.75, y: 0.75, width: 0.25, height: 0.25 } },
    { name: 'Center', rect: { x: 0.35, y: 0.35, width: 0.30, height: 0.30 } },
    { name: 'Minimum size 0.05', rect: { x: 0.50, y: 0.50, width: 0.05, height: 0.05 } },
    { name: 'Full frame 1.0', rect: { x: 0.0, y: 0.0, width: 1.0, height: 1.0 } },
  ];

  const extremeDeltas = [
    { name: 'Massive positive overshoot (+10.0)', dx: 10.0, dy: 10.0 },
    { name: 'Massive negative undershoot (-10.0)', dx: -10.0, dy: -10.0 },
    { name: 'Extreme diagonal (+5.0, -5.0)', dx: 5.0, dy: -5.0 },
    { name: 'Extreme diagonal (-5.0, +5.0)', dx: -5.0, dy: 5.0 },
    { name: 'Micro-delta (+1e-6)', dx: 1e-6, dy: 1e-6 },
    { name: 'Zero delta', dx: 0, dy: 0 },
    { name: 'Right-edge touch delta (+0.75)', dx: 0.75, dy: 0 },
    { name: 'Bottom-edge touch delta (+0.75)', dx: 0, dy: 0.75 },
  ];

  for (const { name: rName, rect } of initialRects) {
    for (const { name: dName, dx, dy } of extremeDeltas) {
      await t.test(`applyDrag: ${rName} with ${dName}`, () => {
        const moved = applyDrag(rect, dx, dy);

        // Invariant 1: Width and height MUST NEVER change during drag
        assert.equal(moved.width, rect.width, `Width mutated during drag! Expected ${rect.width}, got ${moved.width}`);
        assert.equal(moved.height, rect.height, `Height mutated during drag! Expected ${rect.height}, got ${moved.height}`);

        // Invariant 2: Left and top must remain non-negative
        assert.ok(moved.x >= 0.0, `moved.x negative: ${moved.x}`);
        assert.ok(moved.y >= 0.0, `moved.y negative: ${moved.y}`);

        // Invariant 3: Right and bottom must not exceed 1.0 (with 1e-4 float tolerance)
        assert.ok(
          moved.x + moved.width <= 1.0001,
          `moved.x + width exceeds 1.0: ${moved.x} + ${moved.width} = ${moved.x + moved.width}`
        );
        assert.ok(
          moved.y + moved.height <= 1.0001,
          `moved.y + height exceeds 1.0: ${moved.y} + ${moved.height} = ${moved.y + moved.height}`
        );

        // Invariant 4: Clamping at boundaries
        if (dx >= 1.0) {
          assert.ok(
            Math.abs(moved.x - (1.0 - rect.width)) <= 1e-4,
            `Did not clamp to right boundary: expected ${1.0 - rect.width}, got ${moved.x}`
          );
        }
        if (dx <= -1.0) {
          assert.equal(moved.x, 0.0, `Did not clamp to left boundary: expected 0.0, got ${moved.x}`);
        }
        if (dy >= 1.0) {
          assert.ok(
            Math.abs(moved.y - (1.0 - rect.height)) <= 1e-4,
            `Did not clamp to bottom boundary: expected ${1.0 - rect.height}, got ${moved.y}`
          );
        }
        if (dy <= -1.0) {
          assert.equal(moved.y, 0.0, `Did not clamp to top boundary: expected 0.0, got ${moved.y}`);
        }
      });
    }
  }
});

test('CHALLENGER SUITE 4: Resize Handle Corner Inversions & Opposite Anchor Invariance', async (t) => {
  const handles = ['se', 'ne', 'sw', 'nw'];

  const testRectangles = [
    { name: 'Standard center rect', rect: { x: 0.3, y: 0.3, width: 0.4, height: 0.4 } },
    { name: 'Minimum size rect (0.05)', rect: { x: 0.4, y: 0.4, width: 0.05, height: 0.05 } },
    { name: 'Near top-left boundary', rect: { x: 0.0, y: 0.0, width: 0.2, height: 0.2 } },
    { name: 'Near bottom-right boundary', rect: { x: 0.8, y: 0.8, width: 0.2, height: 0.2 } },
    { name: 'Wide landscape rect', rect: { x: 0.1, y: 0.3, width: 0.8, height: 0.2 } },
    { name: 'Tall portrait rect', rect: { x: 0.3, y: 0.1, width: 0.2, height: 0.8 } },
  ];

  const extremeResizeDeltas = [
    // Massive inversions dragging handle past opposite corner
    { name: 'Invert way past opposite corner (-2.0, -2.0)', dx: -2.0, dy: -2.0 },
    { name: 'Invert way past opposite corner (+2.0, +2.0)', dx: 2.0, dy: 2.0 },
    { name: 'Invert X only (-2.0, 0)', dx: -2.0, dy: 0 },
    { name: 'Invert Y only (0, -2.0)', dx: 0, dy: -2.0 },
    { name: 'Invert X only (+2.0, 0)', dx: 2.0, dy: 0 },
    { name: 'Invert Y only (0, +2.0)', dx: 0, dy: 2.0 },
    // Normal expansions to boundaries
    { name: 'Expand past canvas right/bottom (+1.0, +1.0)', dx: 1.0, dy: 1.0 },
    { name: 'Expand past canvas left/top (-1.0, -1.0)', dx: -1.0, dy: -1.0 },
  ];

  for (const handle of handles) {
    for (const { name: rName, rect } of testRectangles) {
      for (const { name: dName, dx, dy } of extremeResizeDeltas) {
        await t.test(`calculateResize: handle '${handle}' on ${rName} with ${dName}`, () => {
          const res = calculateResize(rect, handle, dx, dy, MIN_ROI_SIZE);

          // Invariant 1: Width and height MUST NEVER be below MIN_ROI_SIZE (0.05)
          assert.ok(
            res.width >= MIN_ROI_SIZE - 1e-4,
            `Width fell below minSize (${MIN_ROI_SIZE}): got ${res.width}`
          );
          assert.ok(
            res.height >= MIN_ROI_SIZE - 1e-4,
            `Height fell below minSize (${MIN_ROI_SIZE}): got ${res.height}`
          );

          // Invariant 2: Left and top must remain non-negative
          assert.ok(res.x >= 0.0, `res.x is negative: ${res.x}`);
          assert.ok(res.y >= 0.0, `res.y is negative: ${res.y}`);

          // Invariant 3: Boundaries within [0.0, 1.0]
          assert.ok(
            res.x + res.width <= 1.0001,
            `res.x + width exceeds 1.0: ${res.x} + ${res.width} = ${res.x + res.width}`
          );
          assert.ok(
            res.y + res.height <= 1.0001,
            `res.y + height exceeds 1.0: ${res.y} + ${res.height} = ${res.y + res.height}`
          );

          // Invariant 4: Opposite Corner Anchor Stability
          switch (handle) {
            case 'se': {
              // Anchor is Top-Left (x0, y0)
              assert.ok(
                Math.abs(res.x - rect.x) <= 1e-4,
                `SE anchor X shifted! Expected ${rect.x}, got ${res.x}`
              );
              assert.ok(
                Math.abs(res.y - rect.y) <= 1e-4,
                `SE anchor Y shifted! Expected ${rect.y}, got ${res.y}`
              );
              break;
            }
            case 'ne': {
              // Anchor is Bottom-Left (x0, y0 + h0)
              const expectedBottom = rect.y + rect.height;
              const actualBottom = res.y + res.height;
              assert.ok(
                Math.abs(res.x - rect.x) <= 1e-4,
                `NE anchor X shifted! Expected ${rect.x}, got ${res.x}`
              );
              assert.ok(
                Math.abs(actualBottom - expectedBottom) <= 1e-4,
                `NE anchor Bottom shifted! Expected ${expectedBottom}, got ${actualBottom}`
              );
              break;
            }
            case 'sw': {
              // Anchor is Top-Right (x0 + w0, y0)
              const expectedRight = rect.x + rect.width;
              const actualRight = res.x + res.width;
              assert.ok(
                Math.abs(actualRight - expectedRight) <= 1e-4,
                `SW anchor Right shifted! Expected ${expectedRight}, got ${actualRight}`
              );
              assert.ok(
                Math.abs(res.y - rect.y) <= 1e-4,
                `SW anchor Y shifted! Expected ${rect.y}, got ${res.y}`
              );
              break;
            }
            case 'nw': {
              // Anchor is Bottom-Right (x0 + w0, y0 + h0)
              const expectedRight = rect.x + rect.width;
              const expectedBottom = rect.y + rect.height;
              const actualRight = res.x + res.width;
              const actualBottom = res.y + res.height;
              assert.ok(
                Math.abs(actualRight - expectedRight) <= 1e-4,
                `NW anchor Right shifted! Expected ${expectedRight}, got ${actualRight}`
              );
              assert.ok(
                Math.abs(actualBottom - expectedBottom) <= 1e-4,
                `NW anchor Bottom shifted! Expected ${expectedBottom}, got ${actualBottom}`
              );
              break;
            }
          }
        });
      }
    }
  }
});

test('CHALLENGER SUITE 5: Property-Based Fuzzing & Mathematical Codec Invariants', async (t) => {
  const rng = createRng(42);

  const resolutions = [
    [1920, 1080],
    [3840, 2160],
    [2560, 1440],
    [1280, 720],
    [640, 480],
    [1080, 1920],
    [2560, 1080],
    [3440, 1440],
    [3840, 1600],
    [1921, 1081],
    [1281, 721],
    [853, 481],
    [1919, 1079],
    [1081, 1921],
  ];

  await t.test('Fuzz 1,000 valid normalized rects against toEvenPixels across realistic resolutions', () => {
    let checked = 0;
    for (let i = 0; i < 1000; i++) {
      // Generate valid normalized rect
      const minS = 0.05;
      const w = minS + rng() * (1.0 - minS);
      const h = minS + rng() * (1.0 - minS);
      const x = rng() * (1.0 - w);
      const y = rng() * (1.0 - h);
      const normRect = {
        x: Math.round(x * 10000) / 10000,
        y: Math.round(y * 10000) / 10000,
        width: Math.round(w * 10000) / 10000,
        height: Math.round(h * 10000) / 10000,
      };

      const [srcW, srcH] = resolutions[i % resolutions.length];
      const maxW = Math.floor(srcW / 2) * 2;
      const maxH = Math.floor(srcH / 2) * 2;

      const crop = toEvenPixels(normRect, srcW, srcH);

      // Invariant 1: Even integer coordinates and spans
      assert.equal(crop.x % 2, 0, `crop.x ${crop.x} is not even on ${srcW}x${srcH}`);
      assert.equal(crop.y % 2, 0, `crop.y ${crop.y} is not even on ${srcW}x${srcH}`);
      assert.equal(crop.w % 2, 0, `crop.w ${crop.w} is not even on ${srcW}x${srcH}`);
      assert.equal(crop.h % 2, 0, `crop.h ${crop.h} is not even on ${srcW}x${srcH}`);

      // Invariant 2: Positive spans >= 2
      assert.ok(crop.w >= 2, `crop.w ${crop.w} < 2`);
      assert.ok(crop.h >= 2, `crop.h ${crop.h} < 2`);

      // Invariant 3: Crop MUST NOT exceed source boundaries (even dimension)
      assert.ok(
        crop.x + crop.w <= maxW,
        `Crop X overflow: ${crop.x} + ${crop.w} = ${crop.x + crop.w} > maxW ${maxW} (srcW ${srcW})`
      );
      assert.ok(
        crop.y + crop.h <= maxH,
        `Crop Y overflow: ${crop.y} + ${crop.h} = ${crop.y + crop.h} > maxH ${maxH} (srcH ${srcH})`
      );

      checked++;
    }
    assert.equal(checked, 1000);
  });

  await t.test('Fuzz 1,000 random drag and resize operations verifying all invariants hold', () => {
    const handles = ['se', 'ne', 'sw', 'nw'];
    for (let i = 0; i < 1000; i++) {
      const minS = 0.05;
      const w = minS + rng() * (1.0 - minS);
      const h = minS + rng() * (1.0 - minS);
      const x = rng() * (1.0 - w);
      const y = rng() * (1.0 - h);
      const rect = { x, y, width: w, height: h };

      const handle = handles[Math.floor(rng() * 4)];
      const dx = (rng() - 0.5) * 3.0; // [-1.5, +1.5]
      const dy = (rng() - 0.5) * 3.0; // [-1.5, +1.5]

      const resized = calculateResize(rect, handle, dx, dy, minS);

      assert.ok(resized.x >= 0.0 && resized.x <= 0.9501);
      assert.ok(resized.y >= 0.0 && resized.y <= 0.9501);
      assert.ok(resized.width >= minS - 1e-4);
      assert.ok(resized.height >= minS - 1e-4);
      assert.ok(resized.x + resized.width <= 1.0001);
      assert.ok(resized.y + resized.height <= 1.0001);

      const dragged = applyDrag(resized, (rng() - 0.5) * 3.0, (rng() - 0.5) * 3.0);
      assert.ok(dragged.x >= 0.0 && dragged.x <= 1.0001 - dragged.width);
      assert.ok(dragged.y >= 0.0 && dragged.y <= 1.0001 - dragged.height);
      assert.equal(dragged.width, resized.width);
      assert.equal(dragged.height, resized.height);
    }
  });

  await t.test('Scale-to-fill gameplay framing properties across extreme aspect ratios', () => {
    const testCases = [
      { name: 'Ultra-wide 32:9', crop: { x: 0, y: 0, w: 3840, h: 1080 } },
      { name: 'Square 1:1', crop: { x: 0, y: 0, w: 1080, h: 1080 } },
      { name: 'Ultra-tall 9:21', crop: { x: 0, y: 0, w: 1080, h: 2520 } },
      { name: 'Standard 16:9', crop: { x: 0, y: 0, w: 1920, h: 1080 } },
      { name: 'Vertical 9:16', crop: { x: 0, y: 0, w: 1080, h: 1920 } },
    ];

    for (const tc of testCases) {
      const framing = calculateGameplayFraming(tc.crop, 1080, 1920);

      // Invariant 1: Scaled output MUST completely cover or exceed the canvas dimensions
      assert.ok(
        framing.scaledW >= 1080,
        `scaledW ${framing.scaledW} < canvasWidth 1080 for ${tc.name}`
      );
      assert.ok(
        framing.scaledH >= 1920,
        `scaledH ${framing.scaledH} < canvasHeight 1920 for ${tc.name}`
      );

      // Invariant 2: At least one dimension MUST exactly match canvas dimension (no wasted margin)
      assert.ok(
        framing.scaledW === 1080 || framing.scaledH === 1920,
        `Neither dimension matches canvas: ${framing.scaledW}x${framing.scaledH}`
      );

      // Invariant 3: Aspect ratio of scaled video matches source crop within float precision
      const cropAR = tc.crop.w / tc.crop.h;
      const scaledAR = framing.scaledW / framing.scaledH;
      assert.ok(
        Math.abs(cropAR - scaledAR) / cropAR < 0.005,
        `Aspect ratio distorted for ${tc.name}: crop ${cropAR} vs scaled ${scaledAR}`
      );

      // Invariant 4: Centering offsets are non-negative
      assert.ok(framing.cropOffsetX >= 0, `cropOffsetX negative: ${framing.cropOffsetX}`);
      assert.ok(framing.cropOffsetY >= 0, `cropOffsetY negative: ${framing.cropOffsetY}`);

      // Invariant 5: SubCrop stays inside original crop bounds
      if (framing.sourceSubCrop) {
        assert.ok(framing.sourceSubCrop.x >= tc.crop.x);
        assert.ok(framing.sourceSubCrop.y >= tc.crop.y);
        assert.ok(framing.sourceSubCrop.x + framing.sourceSubCrop.w <= tc.crop.x + tc.crop.w);
        assert.ok(framing.sourceSubCrop.y + framing.sourceSubCrop.h <= tc.crop.y + tc.crop.h);
      }
    }
  });
});

test('CHALLENGER SUITE 6: Validation Rejections, Presets & Error Boundary Conditions', async (t) => {
  await t.test('All 4 placement presets pass validation with strict canvas containment', () => {
    for (const preset of ['top-left', 'top-right', 'bottom-left', 'bottom-right']) {
      const rect = getFacecamPreset(preset);
      const validated = validateNormalizedRect(rect, preset);
      assert.ok(validated.x >= 0.0);
      assert.ok(validated.y >= 0.0);
      assert.ok(validated.x + validated.width <= 1.0001);
      assert.ok(validated.y + validated.height <= 1.0001);

      const overlay = toCanvasOverlay(rect, 1080, 1920);
      assert.equal(overlay.x % 2, 0);
      assert.equal(overlay.y % 2, 0);
      assert.equal(overlay.w % 2, 0);
      assert.equal(overlay.h % 2, 0);
      assert.ok(overlay.x + overlay.w <= 1080);
      assert.ok(overlay.y + overlay.h <= 1920);
    }
  });

  await t.test('Rejection of invalid input formats', () => {
    assert.throws(() => validateNormalizedRect(null), /must be an object/);
    assert.throws(() => validateNormalizedRect(undefined), /must be an object/);
    assert.throws(() => validateNormalizedRect('not an object'), /must be an object/);
    assert.throws(() => validateNormalizedRect({ x: 'abc', y: 0, width: 0.5, height: 0.5 }), /non-finite/);
    assert.throws(() => validateNormalizedRect({ x: NaN, y: 0, width: 0.5, height: 0.5 }), /non-finite/);
    assert.throws(() => validateNormalizedRect({ x: 0, y: Infinity, width: 0.5, height: 0.5 }), /non-finite/);
    assert.throws(() => validateNormalizedRect({ x: -0.05, y: 0, width: 0.5, height: 0.5 }), /negative coordinate/);
    assert.throws(() => validateNormalizedRect({ x: 0, y: 0, width: 0.04, height: 0.5 }), /must be >= 0.05/);
    assert.throws(() => validateNormalizedRect({ x: 0, y: 0, width: 0.5, height: 0.04 }), /must be >= 0.05/);
    assert.throws(() => validateNormalizedRect({ x: 1.05, y: 0, width: 0.5, height: 0.5 }), /out of bounds/);
    assert.throws(() => validateNormalizedRect({ x: 0.8, y: 0.8, width: 0.3, height: 0.3 }), /out of bounds/);
  });

  await t.test('calculateGamingCoordinates produces complete verified plan matching all contracts', () => {
    const input = {
      src_w: 1920,
      src_h: 1080,
      canvas_w: 1080,
      canvas_h: 1920,
      gameplay_roi: { x: 0.0, y: 0.0, width: 1.0, height: 1.0 },
      facecam_roi: { x: 0.7, y: 0.05, width: 0.25, height: 0.25 },
      facecam_placement: 'top-right',
    };

    const plan = calculateGamingCoordinates(input);
    assert.equal(plan.is_valid, true);

    // Gameplay crop
    assert.deepEqual(plan.gameplay_crop, { x: 0, y: 0, w: 1920, h: 1080 });

    // Facecam crop
    assert.deepEqual(plan.facecam_crop, { x: 1344, y: 54, w: 480, h: 270 });

    // Facecam canvas dest (preset top-right: x=0.65, y=0.04, w=0.30, h=0.22 on 1080x1920)
    assert.deepEqual(plan.facecam_dest, { x: 702, y: 76, w: 324, h: 422 });

    // FFmpeg strings
    assert.equal(plan.ffmpeg_crop_gameplay, 'crop=1920:1080:0:0');
    assert.equal(plan.ffmpeg_crop_facecam, 'crop=480:270:1344:54');
    assert.ok(plan.ffmpeg_filtergraph.includes('scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v0]'));
    assert.ok(plan.ffmpeg_filtergraph.includes('scale=324:422:force_original_aspect_ratio=increase,crop=324:422[v1]'));
    assert.ok(plan.ffmpeg_filtergraph.includes('overlay=x=702:y=76:eof_action=pass:repeatlast=0,setsar=1[outv]'));
  });
});
