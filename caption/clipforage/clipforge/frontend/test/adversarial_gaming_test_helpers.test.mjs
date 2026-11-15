/**
 * adversarial_gaming_test_helpers.test.mjs
 * ========================================
 * Adversarial stress harness and empirical challenger suite for `gaming_test_helpers.mjs`.
 *
 * Authored by Challenger 2 (`challenger_t1_2`).
 *
 * Exercises:
 * 1. Mock Canvas 2D Recorder & Evaluator:
 *    - Extreme, non-standard, zero, negative, and odd canvas dimensions.
 *    - Zero-pixel draws, inverted dimensions, negative coordinates, sub-pixel floats.
 *    - Rapid draw bursts (10,000 calls) and reset memory clearing.
 *    - `assertCompositeCanvasParity` failure modes, boundary tolerances, and blind spot verification.
 * 2. Pointer Drag and Resize Simulators:
 *    - Extreme out-of-bounds coordinates, sub-pixel steps, zero-distance drags.
 *    - Invalid, null, undefined, and non-existent resize handles.
 *    - Severe collapse / overflow handle resizing and anchor behavior.
 * 3. Strict R5 Zero-Caption Invariant Injection:
 *    - Exhaustive injection of forbidden caption keywords into DOM (case variations, extensions).
 *    - Exhaustive injection of forbidden keys into API payloads (root and nested gaming_layout).
 *    - Negative values (false/null/0) proving presence alone triggers decisive rejection.
 *    - Empirical probing of key casing and nested object boundaries.
 * 4. Pure Geometry Oracles:
 *    - Extreme out-of-bounds, negative, microscopic, inverted, and oversized rectangles.
 *    - Codec even-pixel invariants across odd dimensions (1919x1079, 1281x721, 1x1).
 *    - Comparison of `clampNormalizedRect` oracle against canonical `gamingCoordinates.ts`.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_CANVAS_WIDTH,
  DEFAULT_CANVAS_HEIGHT,
  DEFAULT_CANVAS_ASPECT_RATIO,
  MIN_ROI_SIZE,
  CANONICAL_PRESETS,
  getCanonicalPresetRect,
  assertPresetParity,
  createMockCanvas,
  assertCompositeCanvasParity,
  createPointerEvent,
  simulatePointerDrag,
  simulateHandleResize,
  assertNoCaptionControlsInDOM,
  assertNoCaptionFieldsInPayload,
  clampNormalizedRect,
  computeEvenPixelCrop,
  assertNormalizedRect,
} from './gaming_test_helpers.mjs';

import {
  clampNormalizedRect as canonicalClamp,
  calculateResize as canonicalCalculateResize,
} from '../lib/gamingCoordinates.ts';

test('Adversarial Challenger Suite: gaming_test_helpers.mjs', async (t) => {

  // ============================================================================
  // SUITE 1: MOCK CANVAS 2D RECORDER & EVALUATOR ADVERSARIAL STRESS
  // ============================================================================
  await t.test('1. Mock Canvas: Non-standard dimensions, extreme values, and rapid bursts', async (st) => {

    await st.test('1a. Non-standard & extreme canvas dimensions', () => {
      // Zero dimensions
      const zeroCanvas = createMockCanvas(0, 0);
      assert.equal(zeroCanvas.canvas.width, 0);
      assert.equal(zeroCanvas.canvas.height, 0);
      assert.equal(zeroCanvas.canvas.getBoundingClientRect().width, 0);

      // Odd dimensions (1919x1079)
      const oddCanvas = createMockCanvas(1919, 1079);
      assert.equal(oddCanvas.canvas.width, 1919);
      assert.equal(oddCanvas.canvas.height, 1079);

      // 8K Extreme dimensions (7680x4320)
      const hugeCanvas = createMockCanvas(7680, 4320);
      assert.equal(hugeCanvas.canvas.width, 7680);
      assert.equal(hugeCanvas.canvas.height, 4320);

      // Sub-pixel floating point dimensions
      const floatCanvas = createMockCanvas(1080.5, 1920.75);
      assert.equal(floatCanvas.canvas.width, 1080.5);
      assert.equal(floatCanvas.canvas.height, 1920.75);

      // Unsupported context type returns null
      assert.equal(floatCanvas.canvas.getContext('webgl'), null);
      assert.equal(floatCanvas.canvas.getContext('2d'), floatCanvas.ctx);
    });

    await st.test('1b. Zero-pixel, inverted, negative, and sub-pixel drawImage calls', () => {
      const { ctx } = createMockCanvas();

      // Zero-pixel draw
      ctx.drawImage('img-zero', 0, 0, 0, 0, 0, 0, 0, 0);

      // Negative source and destination coordinates
      ctx.drawImage('img-neg', -100, -200, 500, 500, -50, -50, 200, 200);

      // Inverted bounding box (negative destination dimensions)
      ctx.drawImage('img-inverted', 0, 0, 1920, 1080, 500, 500, -300, -400);

      // Extreme out-of-bounds coordinates
      ctx.drawImage('img-extreme', 1e7, 1e7, 1e6, 1e6, -1e7, -1e7, 1e6, 1e6);

      // Sub-pixel floating point coordinates
      ctx.drawImage('img-subpixel', 10.333, 20.667, 300.25, 400.75, 50.125, 60.375, 700.5, 800.5);

      // 3-arg and 5-arg drawImage signatures
      ctx.drawImage('img-3arg', 10, 20);
      ctx.drawImage('img-5arg', 10, 20, 300, 400);

      const calls = ctx.getDrawCalls();
      assert.equal(calls.length, 7);

      assert.equal(calls[0].type, 'drawImage-9');
      assert.equal(calls[0].sw, 0);
      assert.equal(calls[0].dw, 0);

      assert.equal(calls[1].sx, -100);
      assert.equal(calls[1].dx, -50);

      assert.equal(calls[2].dw, -300);
      assert.equal(calls[2].dh, -400);

      assert.equal(calls[3].sx, 1e7);

      assert.equal(calls[4].sx, 10.333);
      assert.equal(calls[4].dw, 700.5);

      assert.equal(calls[5].type, 'drawImage-3');
      assert.equal(calls[6].type, 'drawImage-5');
    });

    await st.test('1c. Rapid draw burst (10,000 calls) and context reset', () => {
      const { ctx } = createMockCanvas();
      const startTime = performance.now();

      const BURST_COUNT = 10000;
      for (let i = 0; i < BURST_COUNT; i++) {
        ctx.drawImage('test-src', 0, 0, 100, 100, i % 1080, (i * 2) % 1920, 200, 200);
      }

      const elapsed = performance.now() - startTime;
      assert.equal(ctx.getDrawCalls().length, BURST_COUNT);
      assert.equal(ctx.getOperations().length, BURST_COUNT);
      assert.ok(elapsed < 200, `10,000 draw calls took ${elapsed}ms (should be < 200ms)`);

      // Verify reset clears both draw calls and operations
      ctx.reset();
      assert.equal(ctx.getDrawCalls().length, 0);
      assert.equal(ctx.getOperations().length, 0);
    });

    await st.test('1d. assertCompositeCanvasParity failure modes, tolerances, and sx/sy blind spot', () => {
      const { ctx } = createMockCanvas();

      // Case: 0 draw calls -> fails
      assert.throws(
        () => assertCompositeCanvasParity({ ctx }),
        /Expected at least 2 drawImage calls/
      );

      // Case: 1 draw call -> fails
      ctx.drawImage('gameplay', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
      assert.throws(
        () => assertCompositeCanvasParity({ ctx }),
        /Expected at least 2 drawImage calls/
      );

      // Add second draw call (facecam)
      ctx.drawImage('facecam', 1344, 54, 480, 270, 702, 76, 324, 422);

      // Exact match passes
      assertCompositeCanvasParity({
        ctx,
        expectedGameplayCrop: { w: 1920, h: 1080 },
        expectedFacecamCrop: { w: 480, h: 270 },
        expectedFacecamDest: { x: 702, y: 76, w: 324, h: 422 },
        tolerancePx: 0,
      });

      // Within tolerance (1px delta with tolerance 2px) passes
      assertCompositeCanvasParity({
        ctx,
        expectedGameplayCrop: { w: 1921, h: 1079 },
        expectedFacecamCrop: { w: 481, h: 269 },
        expectedFacecamDest: { x: 703, y: 75, w: 325, h: 421 },
        tolerancePx: 2,
      });

      // Exceeding tolerance: gameplay crop mismatch
      assert.throws(
        () => assertCompositeCanvasParity({
          ctx,
          expectedGameplayCrop: { w: 1950, h: 1080 },
          tolerancePx: 2,
        }),
        /Gameplay crop width mismatch: expected 1950, got 1920/
      );

      // Exceeding tolerance: facecam crop mismatch
      assert.throws(
        () => assertCompositeCanvasParity({
          ctx,
          expectedFacecamCrop: { w: 500, h: 270 },
          tolerancePx: 2,
        }),
        /Facecam crop width mismatch: expected 500, got 480/
      );

      // Exceeding tolerance: facecam dest mismatch
      assert.throws(
        () => assertCompositeCanvasParity({
          ctx,
          expectedFacecamDest: { x: 800, y: 76, w: 324, h: 422 },
          tolerancePx: 2,
        }),
        /Facecam dest x mismatch: expected 800, got 702/
      );

      // Adversarial Verification: assertCompositeCanvasParity validates sx, sy, and gameplay destination!
      // If we create a canvas where sx/sy are wildly wrong (e.g. sx=9999), assertCompositeCanvasParity throws!
      ctx.reset();
      ctx.drawImage('gameplay', 9999, 8888, 1920, 1080, 0, 0, 1080, 1920);
      ctx.drawImage('facecam', 0, 0, 480, 270, 702, 76, 324, 422);

      // Throws on bogus source crop origins!
      assert.throws(
        () => assertCompositeCanvasParity({
          ctx,
          expectedGameplayCrop: { x: 0, y: 0, w: 1920, h: 1080 },
          expectedFacecamCrop: { x: 1344, y: 54, w: 480, h: 270 },
          expectedFacecamDest: { x: 702, y: 76, w: 324, h: 422 },
          tolerancePx: 2,
        }),
        /Gameplay crop x mismatch: expected 0, got 9999/
      );
    });
  });

  // ============================================================================
  // SUITE 2: POINTER DRAG AND RESIZE SIMULATORS ADVERSARIAL STRESS
  // ============================================================================
  await t.test('2. Pointer Event Simulators: Out-of-bounds, sub-pixels, and invalid handles', async (st) => {

    await st.test('2a. Extreme out-of-bounds pointer events and sub-pixel float drag', () => {
      // Extreme negative coordinates
      const evtNeg = createPointerEvent('pointermove', { clientX: -99999, clientY: -88888 });
      assert.equal(evtNeg.clientX, -99999);
      assert.equal(evtNeg.clientY, -88888);
      assert.equal(evtNeg.pageX, -99999);
      assert.equal(evtNeg.pageY, -88888);

      // Sub-pixel drag sequence with 7 steps
      const recorded = [];
      simulatePointerDrag({
        startX: 10.125,
        startY: 20.375,
        endX: 17.125,
        endY: 27.375,
        steps: 7,
        onMove: (e) => recorded.push({ x: e.clientX, y: e.clientY }),
      });

      assert.equal(recorded.length, 7);
      // Step delta is exactly (17.125 - 10.125) / 7 = 1.0
      assert.equal(recorded[0].x, 11.125);
      assert.equal(recorded[0].y, 21.375);
      assert.equal(recorded[6].x, 17.125);
      assert.equal(recorded[6].y, 27.375);

      // Zero-distance drag (startX === endX, startY === endY)
      const zeroDragMoves = [];
      simulatePointerDrag({
        startX: 500,
        startY: 500,
        endX: 500,
        endY: 500,
        steps: 3,
        onMove: (e) => zeroDragMoves.push(e),
      });
      assert.equal(zeroDragMoves.length, 3);
      for (const m of zeroDragMoves) {
        assert.equal(m.clientX, 500);
        assert.equal(m.clientY, 500);
      }
    });

    await st.test('2b. simulateHandleResize with invalid, null, undefined handles', () => {
      const startRect = { x: 0.2, y: 0.2, width: 0.3, height: 0.3 };

      const invalidHandles = ['center', 'top', 'bottom', 'left', 'right', '', null, undefined, 'north-west', 123];
      for (const h of invalidHandles) {
        assert.throws(
          () => simulateHandleResize({ handle: h, startRect, deltaX: 0.1, deltaY: 0.1 }),
          /Invalid handle:/
        );
      }
    });

    await st.test('2c. simulateHandleResize: Collapse & boundary overflow behavior', () => {
      const initial = { x: 0.2, y: 0.2, width: 0.3, height: 0.3 };

      // Normal within-bounds resize on 'se' handle preserves top-left anchor (0.2, 0.2)
      const normalSE = simulateHandleResize({
        handle: 'se',
        startRect: initial,
        deltaX: 0.2,
        deltaY: 0.2,
        clamp: true,
      });
      assert.equal(normalSE.x, 0.2);
      assert.equal(normalSE.y, 0.2);
      assert.equal(Math.round(normalSE.width * 100) / 100, 0.5);
      assert.equal(Math.round(normalSE.height * 100) / 100, 0.5);

      // Severe negative resize collapsing rectangle on 'se' handle
      const collapsedSE = simulateHandleResize({
        handle: 'se',
        startRect: initial,
        deltaX: -0.5, // width becomes 0.3 - 0.5 = -0.2
        deltaY: -0.5, // height becomes -0.2
        clamp: true,
        minSize: 0.05,
      });
      assert.equal(collapsedSE.width, 0.05);
      assert.equal(collapsedSE.height, 0.05);
      assert.equal(collapsedSE.x, 0.2);
      assert.equal(collapsedSE.y, 0.2);

      // Massive expansion beyond canvas boundary (deltaX = 2.0, deltaY = 2.0)
      // Preserves opposite corner anchor point (0.2, 0.2) matching canonical calculateResize
      const overflowSE = simulateHandleResize({
        handle: 'se',
        startRect: initial,
        deltaX: 2.0,
        deltaY: 2.0,
        clamp: true,
      });
      const canonicalSE = canonicalCalculateResize(initial, 'se', 2.0, 2.0);
      assert.deepEqual(overflowSE, canonicalSE);
      assert.equal(overflowSE.x, 0.2); // Pinned to anchor x0
      assert.equal(overflowSE.y, 0.2); // Pinned to anchor y0
      assert.equal(overflowSE.width, 0.8); // Clamped to 1.0 - x0
      assert.equal(overflowSE.height, 0.8); // Clamped to 1.0 - y0

      // Raw unclamped mode (clamp = false)
      const rawResized = simulateHandleResize({
        handle: 'se',
        startRect: initial,
        deltaX: -0.5,
        deltaY: -0.5,
        clamp: false,
      });
      assert.equal(rawResized.width, -0.2);
      assert.equal(rawResized.height, -0.2);
    });
  });

  // ============================================================================
  // SUITE 3: STRICT R5 ZERO-CAPTION INVARIANT INJECTION STRESS
  // ============================================================================
  await t.test('3. R5 Invariant: Injection of prohibited caption keywords into DOM and payloads', async (st) => {

    await st.test('3a. DOM Injection: Case variations, extensions, and dirty UI elements', () => {
      // Clean baseline passes
      assertNoCaptionControlsInDOM('<div class="studio"><canvas id="gaming-preview"></canvas></div>');
      assertNoCaptionControlsInDOM({ innerHTML: '<section><h1>ClipForge Gaming Mode</h1></section>' });
      assertNoCaptionControlsInDOM('');
      assertNoCaptionControlsInDOM(null);

      // Keyword injection matrix
      const dirtySamples = [
        '<button>Enable Subtitles</button>',
        '<div class="subtitle-container"></div>',
        '<input type="checkbox" name="burn_subtitles" />',
        '<span>Burn-in Subtitles</span>',
        '<select id="subtitles_style"><option>Yellow</option></select>',
        '<p>Closed Caption settings</p>',
        '<div data-role="caption">Preview</div>',
        '<label>Upload file: sample.srt</label>',
        '<a href="/downloads/subs.vtt">Download VTT</a>',
        '<span data-format="style.ass">Advanced SubStation</span>',
        '<div>SUBTITLE</div>',
        '<div>CAPTION</div>',
        '<div>track.SRT</div>',
        '<div>track.VTT</div>',
        '<div>track.ASS</div>',
        '<div data-testid="caption-overlay"></div>',
      ];

      for (const dirty of dirtySamples) {
        assert.throws(
          () => assertNoCaptionControlsInDOM(dirty),
          /R5 Violation/,
          `Failed to reject dirty DOM sample: ${dirty}`
        );
      }

      // Adversarial boundary discovery: srt without dot (e.g. data-testid="srt-track") is not caught
      // because regex requires \.srt\b
      let srtWithoutDotCaught = false;
      try {
        assertNoCaptionControlsInDOM('<div data-testid="srt-track"></div>');
      } catch (e) {
        srtWithoutDotCaught = true;
      }
      assert.equal(srtWithoutDotCaught, false, 'Proves regex requires leading period for extensions');
    });

    await st.test('3b. API Payload Injection: Root keys, nested keys, and negative values', () => {
      const cleanBase = {
        video_id: 'vid-999',
        gaming_layout: {
          gameplay_roi: { x: 0, y: 0, width: 1, height: 1 },
          facecam_roi: { x: 0.7, y: 0.05, width: 0.25, height: 0.25 },
          facecam_placement: 'top-right',
          canvas_width: 1080,
          canvas_height: 1920,
        },
      };

      // Clean payload passes
      assertNoCaptionFieldsInPayload(cleanBase);

      // Root key injection: all 10 forbidden keys
      const forbiddenRootKeys = [
        'subtitles',
        'subtitle',
        'captions',
        'caption',
        'captions_style',
        'subtitle_format',
        'burn_subtitles',
        'srt',
        'vtt',
        'ass',
      ];

      for (const fk of forbiddenRootKeys) {
        // Test with truthy value
        const dirty1 = { ...cleanBase, [fk]: 'something' };
        assert.throws(
          () => assertNoCaptionFieldsInPayload(dirty1),
          new RegExp(`R5 Violation: API payload contains prohibited caption field '${fk}'`),
          `Expected rejection for root key '${fk}' with string value`
        );

        // Test with falsy value (e.g. subtitles: false or caption: null)
        // R5 requires ZERO caption fields even if disabled/null!
        const dirty2 = { ...cleanBase, [fk]: false };
        assert.throws(
          () => assertNoCaptionFieldsInPayload(dirty2),
          new RegExp(`R5 Violation: API payload contains prohibited caption field '${fk}'`),
          `Expected rejection for root key '${fk}' with false value`
        );

        const dirty3 = { ...cleanBase, [fk]: null };
        assert.throws(
          () => assertNoCaptionFieldsInPayload(dirty3),
          new RegExp(`R5 Violation: API payload contains prohibited caption field '${fk}'`),
          `Expected rejection for root key '${fk}' with null value`
        );
      }

      // Nested injection inside gaming_layout
      for (const fk of forbiddenRootKeys) {
        const dirtyNested = {
          ...cleanBase,
          gaming_layout: {
            ...cleanBase.gaming_layout,
            [fk]: true,
          },
        };
        assert.throws(
          () => assertNoCaptionFieldsInPayload(dirtyNested),
          new RegExp(`R5 Violation: gaming_layout contains prohibited caption field '${fk}'`),
          `Expected rejection for nested gaming_layout key '${fk}'`
        );
      }

      // Malformed payloads (null, primitive)
      assert.throws(() => assertNoCaptionFieldsInPayload(null), /Payload must be an object/);
      assert.throws(() => assertNoCaptionFieldsInPayload('not-an-object'), /Payload must be an object/);
      assert.throws(() => assertNoCaptionFieldsInPayload(12345), /Payload must be an object/);

      // Adversarial Boundary Verification:
      // 1. Casing: PascalCase keys like Subtitles are caught by case-insensitive scanner
      let pascalCaseCaught = false;
      try {
        assertNoCaptionFieldsInPayload({ Subtitles: true });
      } catch (e) {
        pascalCaseCaught = true;
      }
      assert.equal(pascalCaseCaught, true, 'Verifies helper check is case-insensitive');

      // 2. Arbitrary nested objects like payload.config.subtitles are caught by recursive scanner
      let nestedConfigCaught = false;
      try {
        assertNoCaptionFieldsInPayload({ config: { subtitles: true } });
      } catch (e) {
        nestedConfigCaught = true;
      }
      assert.equal(nestedConfigCaught, true, 'Verifies helper recursively checks nested objects');
    });
  });

  // ============================================================================
  // SUITE 4: PURE GEOMETRY ORACLES ADVERSARIAL STRESS
  // ============================================================================
  await t.test('4. Geometry Oracles: Extreme coordinates, odd codecs, and parity invariants', async (st) => {

    await st.test('4a. clampNormalizedRect: Comparison between helper oracle and canonical engine', () => {
      // In-bounds normal clamping
      const normInput = { x: 0.1, y: 0.1, width: 0.3, height: 0.3 };
      const normHelper = clampNormalizedRect(normInput);
      const normCanonical = canonicalClamp(normInput);
      assert.deepEqual(normHelper, normCanonical);

      // Extreme negative coordinates
      const neg = clampNormalizedRect({ x: -100, y: -200, width: 0.3, height: 0.3 });
      assert.equal(neg.x, 0.0);
      assert.equal(neg.y, 0.0);
      assert.equal(neg.width, 0.3);
      assert.equal(neg.height, 0.3);

      // Microscopic sizes (below MIN_ROI_SIZE = 0.05)
      const micro = clampNormalizedRect({ x: 0.1, y: 0.1, width: 0.00001, height: 0.00002 });
      assert.equal(micro.width, 0.05);
      assert.equal(micro.height, 0.05);

      // Clamping Parity Verification: Overflowing dimensions (x = 0.2, width = 0.9)
      const overInput = { x: 0.2, y: 0.2, width: 0.9, height: 0.9 };
      const overHelper = clampNormalizedRect(overInput);
      const overCanonical = canonicalClamp(overInput);

      // Both preserve origin x = 0.2, y = 0.2, and clamp width/height to 0.8:
      assert.deepEqual(overHelper, overCanonical);
      assert.equal(overHelper.x, 0.2);
      assert.equal(overHelper.y, 0.2);
      assert.equal(overHelper.width, 0.8);
      assert.equal(overHelper.height, 0.8);

      // Both produced valid NormalizedRects satisfying all invariants
      assertNormalizedRect(overHelper);
      assertNormalizedRect(overCanonical);
    });

    await st.test('4b. computeEvenPixelCrop: Codec parity across odd and non-standard resolutions', () => {
      const resolutions = [
        { w: 1919, h: 1079 }, // Odd dimension
        { w: 1921, h: 1081 }, // Odd dimension +1
        { w: 3840, h: 1600 }, // Ultrawide 21:9
        { w: 1281, h: 721 },  // Odd 720p+1
        { w: 853, h: 481 },   // 480p odd
        { w: 7680, h: 4320 }, // 8K UHD
        { w: 1080, h: 1920 }, // Vertical portrait
        { w: 100, h: 100 },   // Low res
      ];

      const testRects = [
        { x: 0.0, y: 0.0, width: 1.0, height: 1.0 },
        { x: 0.65, y: 0.04, width: 0.30, height: 0.22 },
        { x: 0.05, y: 0.74, width: 0.30, height: 0.22 },
        { x: 0.12345, y: 0.6789, width: 0.2345, height: 0.3456 },
      ];

      for (const res of resolutions) {
        const maxEvenW = Math.floor(res.w / 2) * 2;
        const maxEvenH = Math.floor(res.h / 2) * 2;

        for (const rect of testRects) {
          const crop = computeEvenPixelCrop(rect, res.w, res.h);

          // All output values must be even integers
          assert.equal(crop.x % 2, 0, `crop.x (${crop.x}) must be even for ${res.w}x${res.h}`);
          assert.equal(crop.y % 2, 0, `crop.y (${crop.y}) must be even for ${res.w}x${res.h}`);
          assert.equal(crop.w % 2, 0, `crop.w (${crop.w}) must be even for ${res.w}x${res.h}`);
          assert.equal(crop.h % 2, 0, `crop.h (${crop.h}) must be even for ${res.w}x${res.h}`);

          // Minimum 2 pixels
          assert.ok(crop.w >= 2, `crop.w (${crop.w}) must be >= 2`);
          assert.ok(crop.h >= 2, `crop.h (${crop.h}) must be >= 2`);

          // Strictly within even bounds
          assert.ok(crop.x >= 0, `crop.x (${crop.x}) must be >= 0`);
          assert.ok(crop.y >= 0, `crop.y (${crop.y}) must be >= 0`);
          assert.ok(
            crop.x + crop.w <= maxEvenW,
            `crop.x + crop.w (${crop.x + crop.w}) exceeds maxEvenW (${maxEvenW}) for resolution ${res.w}x${res.h}`
          );
          assert.ok(
            crop.y + crop.h <= maxEvenH,
            `crop.y + crop.h (${crop.y + crop.h}) exceeds maxEvenH (${maxEvenH}) for resolution ${res.w}x${res.h}`
          );
        }
      }
    });

    await st.test('4c. assertNormalizedRect: Non-finite and invalid boundaries', () => {
      // Non-finite values
      assert.throws(() => assertNormalizedRect({ x: NaN, y: 0, width: 0.3, height: 0.3 }), /x must be finite/);
      assert.throws(() => assertNormalizedRect({ x: 0, y: Infinity, width: 0.3, height: 0.3 }), /y must be finite/);
      assert.throws(() => assertNormalizedRect({ x: 0, y: 0, width: -Infinity, height: 0.3 }), /width must be finite/);

      // Negative values
      assert.throws(() => assertNormalizedRect({ x: -0.01, y: 0, width: 0.3, height: 0.3 }), /must be >= 0.0/);
      assert.throws(() => assertNormalizedRect({ x: 0, y: -0.01, width: 0.3, height: 0.3 }), /must be >= 0.0/);

      // Below minSize
      assert.throws(() => assertNormalizedRect({ x: 0, y: 0, width: 0.01, height: 0.3 }, 0.05), /must be >= 0.05/);

      // Boundary overflow (x + width > 1.0)
      assert.throws(() => assertNormalizedRect({ x: 0.8, y: 0, width: 0.3, height: 0.3 }), /must be <= 1.0/);
      assert.throws(() => assertNormalizedRect({ x: 0, y: 0.8, width: 0.3, height: 0.3 }), /must be <= 1.0/);
    });
  });
});
