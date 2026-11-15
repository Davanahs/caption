/**
 * gaming_test_helpers.test.mjs
 * ============================
 * Self-verification test suite for `frontend/test/gaming_test_helpers.mjs`.
 *
 * Validates:
 * 1. Canonical preset calculations and parity assertions for all 4 presets.
 * 2. Mock Canvas 2D creation, drawImage call recording, and parity evaluation.
 * 3. Pointer event simulation (drag sequences, handle resizing).
 * 4. Strict R5 Zero-Caption invariant assertions (DOM audit, payload inspection).
 * 5. Pure test oracles for boundary clamping and even-pixel codec alignment.
 */

import fs from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_CANVAS_WIDTH,
  DEFAULT_CANVAS_HEIGHT,
  DEFAULT_CANVAS_ASPECT_RATIO,
  MIN_ROI_SIZE,
  DEFAULT_FACECAM_MARGIN_X,
  DEFAULT_FACECAM_MARGIN_Y,
  DEFAULT_PRESET_MARGIN,
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
  getFacecamPreset,
  toEvenPixels,
  calculateResize,
} from '../lib/gamingCoordinates.ts';

test('Gaming Test Helpers Suite', async (t) => {

  await t.test('1. Constants and Canonical Presets Contract', () => {
    assert.equal(DEFAULT_CANVAS_WIDTH, 1080);
    assert.equal(DEFAULT_CANVAS_HEIGHT, 1920);
    assert.equal(DEFAULT_CANVAS_ASPECT_RATIO, 9 / 16);
    assert.equal(MIN_ROI_SIZE, 0.05);
    assert.equal(DEFAULT_FACECAM_MARGIN_X, 0.05);
    assert.equal(DEFAULT_FACECAM_MARGIN_Y, 0.04);
    assert.equal(DEFAULT_PRESET_MARGIN, 0.04);

    // Load authoritative golden vectors for genuine cross-contract verification
    const rawVectors = fs.readFileSync(
      new URL('../../docs/engineering/gaming_geometry_golden_vectors.json', import.meta.url),
      'utf8'
    );
    const { vectors } = JSON.parse(rawVectors);

    const presetVectorMap = {
      'top-left': 'vector-13-preset-top-left',
      'top-right': 'vector-14-preset-top-right',
      'bottom-left': 'vector-15-preset-bottom-left',
      'bottom-right': 'vector-16-preset-bottom-right',
    };

    const presets = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
    for (const p of presets) {
      const canonicalRect = getCanonicalPresetRect(p);
      assertNormalizedRect(canonicalRect);

      // 1. Verify against real production implementation getFacecamPreset
      const actualFromEngine = getFacecamPreset(p);
      assertPresetParity(actualFromEngine, p);

      // 2. Verify helper canonical rect matches production engine output
      assert.deepEqual(canonicalRect, actualFromEngine);

      // 3. Verify against authoritative golden vector
      const vector = vectors.find((v) => v.id === presetVectorMap[p]);
      assert.ok(vector, `Golden vector must exist for ${presetVectorMap[p]}`);
      assert.deepEqual(
        canonicalRect,
        vector.expected.facecam_resolved_output_rect,
        `Preset ${p} must match golden vector ${vector.id}`
      );
    }

    // Negative assertions: assertPresetParity must detect discrepancies
    assert.throws(
      () => assertPresetParity({ x: 0.04, y: 0.04, width: 0.30, height: 0.22 }, 'top-left'),
      /Preset top-left x mismatch: expected 0.05, got 0.04/,
      'Must detect flawed 0.04 margin on top-left'
    );

    assert.throws(() => getCanonicalPresetRect('invalid-preset'), /Unknown preset/);
  });

  await t.test('2. Mock Canvas 2D and Parity Evaluation', () => {
    const { canvas, ctx } = createMockCanvas(1080, 1920);
    assert.equal(canvas.width, 1080);
    assert.equal(canvas.height, 1920);

    // Simulate drawing Layer 1 (gameplay fill)
    ctx.drawImage('gameplay-img', 0, 0, 1920, 1080, 0, 0, 1080, 1920);

    // Simulate drawing Layer 2 (facecam PiP overlay at top-right)
    ctx.drawImage('facecam-img', 1344, 54, 480, 270, 702, 76, 324, 422);

    const draws = ctx.getDrawCalls();
    assert.equal(draws.length, 2);
    assert.equal(draws[0].sw, 1920);
    assert.equal(draws[0].sh, 1080);
    assert.equal(draws[1].dx, 702);
    assert.equal(draws[1].dy, 76);

    // Parity evaluation helper with full crop origins and destination
    assertCompositeCanvasParity({
      ctx,
      expectedGameplayCrop: { x: 0, y: 0, w: 1920, h: 1080 },
      expectedFacecamCrop: { x: 1344, y: 54, w: 480, h: 270 },
      expectedFacecamDest: { x: 702, y: 76, w: 324, h: 422 },
      tolerancePx: 1,
    });

    // Negative test: verify that mismatch in crop origin throws
    assert.throws(
      () => assertCompositeCanvasParity({
        ctx,
        expectedGameplayCrop: { x: 100, y: 0, w: 1920, h: 1080 },
      }),
      /Gameplay crop x mismatch/
    );

    assert.throws(
      () => assertCompositeCanvasParity({
        ctx,
        expectedFacecamCrop: { x: 100, y: 54, w: 480, h: 270 },
      }),
      /Facecam crop x mismatch/
    );

    assert.throws(
      () => assertCompositeCanvasParity({
        ctx,
        expectedGameplayDest: { x: 50, y: 0, w: 1080, h: 1920 },
      }),
      /Gameplay dest x mismatch/
    );
  });

  await t.test('3. Pointer Event Simulation (Drag and Handle Resize)', () => {
    // 3a. Drag sequence
    const recordedEvents = [];
    simulatePointerDrag({
      startX: 100,
      startY: 100,
      endX: 300,
      endY: 400,
      steps: 4,
      onDown: (e) => recordedEvents.push(e),
      onMove: (e) => recordedEvents.push(e),
      onUp: (e) => recordedEvents.push(e),
    });

    assert.equal(recordedEvents.length, 6); // 1 down + 4 moves + 1 up
    assert.equal(recordedEvents[0].type, 'pointerdown');
    assert.equal(recordedEvents[0].clientX, 100);
    assert.equal(recordedEvents[5].type, 'pointerup');
    assert.equal(recordedEvents[5].clientX, 300);
    assert.equal(recordedEvents[5].clientY, 400);

    // 3b. Corner resize handle with 4-handle anchor preservation
    const initialRect = { x: 0.2, y: 0.2, width: 0.3, height: 0.3 };

    // Test all 4 handles match canonical calculateResize and preserve opposite corner
    for (const handle of ['se', 'sw', 'ne', 'nw']) {
      const resized = simulateHandleResize({
        handle,
        startRect: initialRect,
        deltaX: 0.1,
        deltaY: 0.1,
      });
      const canonical = calculateResize(initialRect, handle, 0.1, 0.1);
      assert.deepEqual(resized, canonical, `Handle ${handle} must match canonical calculateResize`);
    }

    // SE handle: anchor top-left (0.2, 0.2)
    const seResized = simulateHandleResize({
      handle: 'se',
      startRect: initialRect,
      deltaX: 0.1,
      deltaY: 0.1,
    });
    assert.equal(seResized.x, 0.2);
    assert.equal(seResized.y, 0.2);
    assert.equal(seResized.width, 0.4);
    assert.equal(seResized.height, 0.4);

    // NW handle: anchor bottom-right (0.5, 0.5)
    const nwResized = simulateHandleResize({
      handle: 'nw',
      startRect: initialRect,
      deltaX: 0.1,
      deltaY: 0.1,
    });
    assert.equal(nwResized.x, 0.3);
    assert.equal(nwResized.y, 0.3);
    assert.equal(nwResized.width, 0.2);
    assert.equal(nwResized.height, 0.2);
    assert.equal(Math.round((nwResized.x + nwResized.width) * 100) / 100, 0.5);
    assert.equal(Math.round((nwResized.y + nwResized.height) * 100) / 100, 0.5);

    // Inward collapse clamping to minSize
    const collapsed = simulateHandleResize({
      handle: 'se',
      startRect: initialRect,
      deltaX: -0.5,
      deltaY: -0.5,
      minSize: 0.05,
    });
    assert.equal(collapsed.width, 0.05);
    assert.equal(collapsed.height, 0.05);
    assert.equal(collapsed.x, 0.2);
    assert.equal(collapsed.y, 0.2);
  });

  await t.test('4. Strict R5 Zero-Caption Invariant Assertions', () => {
    // Clean DOM passes
    const cleanHtml = `<div class="gaming-layout-studio"><canvas id="preview-9-16"></canvas><button>Generate</button></div>`;
    assertNoCaptionControlsInDOM(cleanHtml);

    // Prohibited subtitle text fails
    const dirtyHtml = `<div><label><input type="checkbox" name="enable_subtitles" /> Burn Subtitles</label></div>`;
    assert.throws(
      () => assertNoCaptionControlsInDOM(dirtyHtml),
      /R5 Violation/
    );

    // Clean payload passes
    const cleanPayload = {
      video_id: 'vid-123',
      gaming_layout: {
        gameplay_roi: { x: 0, y: 0, width: 1, height: 1 },
        facecam_roi: { x: 0.7, y: 0.05, width: 0.25, height: 0.25 },
        facecam_placement: 'top-right',
      },
    };
    assertNoCaptionFieldsInPayload(cleanPayload);

    // Forbidden caption field in payload fails
    const dirtyPayload = {
      ...cleanPayload,
      captions_style: 'yellow_bold',
    };
    assert.throws(
      () => assertNoCaptionFieldsInPayload(dirtyPayload),
      /R5 Violation: API payload contains prohibited caption field 'captions_style'/
    );

    // 4b. Deeply nested prohibited fields in payload (Finding 3)
    assert.throws(
      () => assertNoCaptionFieldsInPayload({ ...cleanPayload, config: { subtitles: true } }),
      /R5 Violation: API payload contains prohibited caption field 'subtitles' \(at config\.subtitles\)/
    );

    assert.throws(
      () => assertNoCaptionFieldsInPayload({ ...cleanPayload, options: { export: { captionStyle: 'yellow' } } }),
      /R5 Violation: API payload contains prohibited caption field 'captionStyle' \(at options\.export\.captionStyle\)/
    );

    // 4c. Prohibited fields inside array elements (Finding 3)
    assert.throws(
      () => assertNoCaptionFieldsInPayload({ ...cleanPayload, tracks: [{ type: 'audio' }, { srt: 'subs.srt' }] }),
      /R5 Violation: API payload contains prohibited caption field 'srt' \(at tracks\[1\]\.srt\)/
    );

    // 4d. Case variations & compound tokens (Finding 3)
    assert.throws(
      () => assertNoCaptionFieldsInPayload({ ...cleanPayload, Subtitles: true }),
      /R5 Violation: API payload contains prohibited caption field 'Subtitles'/
    );

    assert.throws(
      () => assertNoCaptionFieldsInPayload({ ...cleanPayload, burn_subtitles: true }),
      /R5 Violation: API payload contains prohibited caption field 'burn_subtitles'/
    );

    assert.throws(
      () => assertNoCaptionFieldsInPayload({ ...cleanPayload, srt_file: 'sub.srt' }),
      /R5 Violation: API payload contains prohibited caption field 'srt_file'/
    );

    // 4e. False positive immunity verification (Finding 3)
    const payloadWithInnocentKeys = {
      ...cleanPayload,
      asset_id: 'asset_99',
      class_name: 'gaming-mode',
      pass_through: true,
      assignee: 'editor',
    };
    assertNoCaptionFieldsInPayload(payloadWithInnocentKeys); // Must not throw!

    // 4f. DOM root element attribute rejection (Finding 6)
    const dirtyRootElement = {
      outerHTML: '<div data-testid="caption-controls" class="studio-panel"><canvas></canvas></div>',
      innerHTML: '<canvas></canvas>',
    };
    assert.throws(
      () => assertNoCaptionControlsInDOM(dirtyRootElement),
      /R5 Violation/
    );
  });

  await t.test('5. Pure Test Oracles: Clamping and Even-Pixel Alignment', () => {
    // 5a. Clamping oracle
    const clampedNeg = clampNormalizedRect({ x: -0.2, y: -0.1, width: 0.3, height: 0.3 });
    assert.equal(clampedNeg.x, 0.0);
    assert.equal(clampedNeg.y, 0.0);

    const clampedOverflow = clampNormalizedRect({ x: 0.85, y: 0.85, width: 0.3, height: 0.3 });
    assert.ok(clampedOverflow.x + clampedOverflow.width <= 1.0);
    assert.ok(clampedOverflow.y + clampedOverflow.height <= 1.0);

    const clampedMin = clampNormalizedRect({ x: 0.2, y: 0.2, width: 0.01, height: 0.01 }, 0.05);
    assert.equal(clampedMin.width, 0.05);
    assert.equal(clampedMin.height, 0.05);

    // 5b. Even-pixel crop oracle: Anchored position & boundary truncation (Finding 5)
    // When crop exceeds canvas/source boundaries, x/y must remain anchored and w/h shrunk
    const rightOverflowRect = { x: 0.8, y: 0.0, width: 0.3, height: 1.0 };
    const rightCrop = computeEvenPixelCrop(rightOverflowRect, 1920, 1080);
    assert.equal(rightCrop.x, 1536, 'x must remain anchored at 1536, NOT shifted leftward to 1344');
    assert.equal(rightCrop.w, 384, 'width must shrink to 384 to fit within 1920 source width');

    const bottomOverflowRect = { x: 0.0, y: 0.8, width: 1.0, height: 0.3 };
    const bottomCrop = computeEvenPixelCrop(bottomOverflowRect, 1920, 1080);
    assert.equal(bottomCrop.y, 864, 'y must remain anchored at 864, NOT shifted upward');
    assert.equal(bottomCrop.h, 216, 'height must shrink to 216 to fit within 1080 source height');

    // Test standard in-bounds rect parity with toEvenPixels
    const standardRect = { x: 0.65, y: 0.04, width: 0.30, height: 0.22 };
    const standardCrop = computeEvenPixelCrop(standardRect, 1920, 1080);
    const expectedStandard = toEvenPixels(standardRect, 1920, 1080);
    assert.deepEqual(standardCrop, expectedStandard);

    // Test odd dimensions: 1919x1079
    const oddRect = { x: 0.7, y: 0.05, width: 0.25, height: 0.25 };
    const oddCrop = computeEvenPixelCrop(oddRect, 1919, 1079);
    const expectedOdd = toEvenPixels(oddRect, 1919, 1079);
    assert.deepEqual(oddCrop, expectedOdd);
    assert.equal(oddCrop.x % 2, 0);
    assert.equal(oddCrop.y % 2, 0);
    assert.equal(oddCrop.w % 2, 0);
    assert.equal(oddCrop.h % 2, 0);
    assert.ok(oddCrop.x + oddCrop.w <= 1918);
    assert.ok(oddCrop.y + oddCrop.h <= 1078);
  });
});
