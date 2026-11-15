/**
 * deep_adversarial_challenge.test.mjs
 * ===================================
 * Intensive adversarial stress test suite authored by Challenger 2 (Round 2)
 * to empirically challenge and verify the remediated frontend helpers in
 * `gaming_test_helpers.mjs`.
 *
 * Specific Focus Areas:
 * 1. Canvas Parity: Exhaustive permutation of invalid crop origins (sx, sy),
 *    invalid dimensions (sw, sh), and invalid destination geometries (dx, dy, dw, dh).
 * 2. Zero-Caption: 100-level deep nesting, multi-dimensional array nesting,
 *    case permutations, compound delimiters, falsy values, circular references,
 *    and strict false-positive immunity against innocent English words.
 * 3. Anchor Drift: Mathematical preservation of opposite corner anchors across
 *    all 4 resize handles ('se', 'ne', 'sw', 'nw') under boundary overshoots,
 *    severe negative collapse, and 1,000 randomized fuzzing iterations against
 *    the production `calculateResize` engine.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createMockCanvas,
  assertCompositeCanvasParity,
  assertNoCaptionFieldsInPayload,
  assertNoCaptionControlsInDOM,
  simulateHandleResize,
  clampNormalizedRect,
  computeEvenPixelCrop,
  assertNormalizedRect,
} from './gaming_test_helpers.mjs';

import {
  calculateResize as canonicalCalculateResize,
  clampNormalizedRect as canonicalClamp,
  toEvenPixels,
} from '../lib/gamingCoordinates.ts';

test('Deep Adversarial Challenger Suite (Round 2)', async (t) => {

  // ============================================================================
  // AREA 1: CANVAS PARITY EMPIRICAL VERIFICATION
  // ============================================================================
  await t.test('Area 1: Canvas Parity Crop Origin & Destination Boundary Enforcement', async (st) => {

    await st.test('1a. Baseline valid composite canvas passes parity assertion', () => {
      const { ctx } = createMockCanvas(1080, 1920);
      ctx.drawImage('gameplay', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
      ctx.drawImage('facecam', 1344, 54, 480, 270, 702, 76, 324, 422);

      // Parity assertion with strict 0px tolerance
      assertCompositeCanvasParity({
        ctx,
        expectedGameplayCrop: { x: 0, y: 0, w: 1920, h: 1080 },
        expectedFacecamCrop: { x: 1344, y: 54, w: 480, h: 270 },
        expectedFacecamDest: { x: 702, y: 76, w: 324, h: 422 },
        tolerancePx: 0,
      });
    });

    await st.test('1b. Exhaustive rejection of invalid crop origins and dimensions', () => {
      const { ctx } = createMockCanvas(1080, 1920);

      const permutations = [
        // Layer 1 Gameplay Crop Origin & Dimensions
        {
          name: 'gameplay sx wildly out-of-bounds (9999)',
          draw: (c) => c.drawImage('g', 9999, 0, 1920, 1080, 0, 0, 1080, 1920),
          error: /Gameplay crop x mismatch: expected 0, got 9999/,
        },
        {
          name: 'gameplay sx negative (-100)',
          draw: (c) => c.drawImage('g', -100, 0, 1920, 1080, 0, 0, 1080, 1920),
          error: /Gameplay crop x mismatch: expected 0, got -100/,
        },
        {
          name: 'gameplay sy out-of-bounds (8888)',
          draw: (c) => c.drawImage('g', 0, 8888, 1920, 1080, 0, 0, 1080, 1920),
          error: /Gameplay crop y mismatch: expected 0, got 8888/,
        },
        {
          name: 'gameplay sy negative (-50)',
          draw: (c) => c.drawImage('g', 0, -50, 1920, 1080, 0, 0, 1080, 1920),
          error: /Gameplay crop y mismatch: expected 0, got -50/,
        },
        {
          name: 'gameplay sw dimension mismatch',
          draw: (c) => c.drawImage('g', 0, 0, 1800, 1080, 0, 0, 1080, 1920),
          error: /Gameplay crop width mismatch: expected 1920, got 1800/,
        },
        {
          name: 'gameplay sh dimension mismatch',
          draw: (c) => c.drawImage('g', 0, 0, 1920, 1000, 0, 0, 1080, 1920),
          error: /Gameplay crop height mismatch: expected 1080, got 1000/,
        },
        // Layer 1 Gameplay Destination
        {
          name: 'gameplay dest dx shifted (10px)',
          draw: (c) => c.drawImage('g', 0, 0, 1920, 1080, 10, 0, 1080, 1920),
          error: /Gameplay dest x mismatch: expected 0, got 10/,
        },
        {
          name: 'gameplay dest dy shifted (15px)',
          draw: (c) => c.drawImage('g', 0, 0, 1920, 1080, 0, 15, 1080, 1920),
          error: /Gameplay dest y mismatch: expected 0, got 15/,
        },
        {
          name: 'gameplay dest dw shrunk (1000px instead of 1080px)',
          draw: (c) => c.drawImage('g', 0, 0, 1920, 1080, 0, 0, 1000, 1920),
          error: /Gameplay dest width mismatch: expected 1080, got 1000/,
        },
        {
          name: 'gameplay dest dh shrunk (1900px instead of 1920px)',
          draw: (c) => c.drawImage('g', 0, 0, 1920, 1080, 0, 0, 1080, 1900),
          error: /Gameplay dest height mismatch: expected 1920, got 1900/,
        },
        // Layer 2 Facecam Crop Origin & Dimensions
        {
          name: 'facecam sx shifted (0 instead of 1344)',
          draw: (c) => {
            c.drawImage('g', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
            c.drawImage('f', 0, 54, 480, 270, 702, 76, 324, 422);
          },
          error: /Facecam crop x mismatch: expected 1344, got 0/,
        },
        {
          name: 'facecam sy shifted (0 instead of 54)',
          draw: (c) => {
            c.drawImage('g', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
            c.drawImage('f', 1344, 0, 480, 270, 702, 76, 324, 422);
          },
          error: /Facecam crop y mismatch: expected 54, got 0/,
        },
        {
          name: 'facecam sw mismatch (400 instead of 480)',
          draw: (c) => {
            c.drawImage('g', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
            c.drawImage('f', 1344, 54, 400, 270, 702, 76, 324, 422);
          },
          error: /Facecam crop width mismatch: expected 480, got 400/,
        },
        {
          name: 'facecam sh mismatch (200 instead of 270)',
          draw: (c) => {
            c.drawImage('g', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
            c.drawImage('f', 1344, 54, 480, 200, 702, 76, 324, 422);
          },
          error: /Facecam crop height mismatch: expected 270, got 200/,
        },
        // Layer 2 Facecam Destination
        {
          name: 'facecam dest dx mismatch (800 instead of 702)',
          draw: (c) => {
            c.drawImage('g', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
            c.drawImage('f', 1344, 54, 480, 270, 800, 76, 324, 422);
          },
          error: /Facecam dest x mismatch: expected 702, got 800/,
        },
        {
          name: 'facecam dest dy mismatch (100 instead of 76)',
          draw: (c) => {
            c.drawImage('g', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
            c.drawImage('f', 1344, 54, 480, 270, 702, 100, 324, 422);
          },
          error: /Facecam dest y mismatch: expected 76, got 100/,
        },
        {
          name: 'facecam dest dw mismatch (400 instead of 324)',
          draw: (c) => {
            c.drawImage('g', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
            c.drawImage('f', 1344, 54, 480, 270, 702, 76, 400, 422);
          },
          error: /Facecam dest width mismatch: expected 324, got 400/,
        },
        {
          name: 'facecam dest dh mismatch (500 instead of 422)',
          draw: (c) => {
            c.drawImage('g', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
            c.drawImage('f', 1344, 54, 480, 270, 702, 76, 324, 500);
          },
          error: /Facecam dest height mismatch: expected 422, got 500/,
        },
      ];

      for (const p of permutations) {
        ctx.reset();
        p.draw(ctx);
        if (ctx.getDrawCalls().length === 1) {
          // If only gameplay was drawn, add normal facecam
          ctx.drawImage('f', 1344, 54, 480, 270, 702, 76, 324, 422);
        }

        assert.throws(
          () => assertCompositeCanvasParity({
            ctx,
            expectedGameplayCrop: { x: 0, y: 0, w: 1920, h: 1080 },
            expectedFacecamCrop: { x: 1344, y: 54, w: 480, h: 270 },
            expectedFacecamDest: { x: 702, y: 76, w: 324, h: 422 },
            tolerancePx: 2,
          }),
          p.error,
          `Failed on scenario: ${p.name}`
        );
      }
    });

    await st.test('1c. Custom expectedGameplayDest verification', () => {
      const { ctx } = createMockCanvas(1080, 1920);
      // Gameplay drawn offset to (50, 50, 980, 1820)
      ctx.drawImage('g', 0, 0, 1920, 1080, 50, 50, 980, 1820);
      ctx.drawImage('f', 1344, 54, 480, 270, 702, 76, 324, 422);

      // Matches when custom expectedGameplayDest provided
      assertCompositeCanvasParity({
        ctx,
        expectedGameplayCrop: { x: 0, y: 0, w: 1920, h: 1080 },
        expectedGameplayDest: { x: 50, y: 50, w: 980, h: 1820 },
        expectedFacecamCrop: { x: 1344, y: 54, w: 480, h: 270 },
        expectedFacecamDest: { x: 702, y: 76, w: 324, h: 422 },
        tolerancePx: 0,
      });

      // Throws if custom expectedGameplayDest mismatches
      assert.throws(
        () => assertCompositeCanvasParity({
          ctx,
          expectedGameplayDest: { x: 0, y: 0, w: 1080, h: 1920 },
        }),
        /Gameplay dest x mismatch/
      );
    });
  });

  // ============================================================================
  // AREA 2: ZERO-CAPTION R5 PENETRATION & IMMUNITY
  // ============================================================================
  await t.test('Area 2: Zero-Caption Deep Nesting, Invariants, and False-Positive Immunity', async (st) => {

    await st.test('2a. Deeply nested payloads (100 levels)', () => {
      let deepPayload = { burn_subtitles: true };
      for (let i = 0; i < 100; i++) {
        deepPayload = { [`level_${i}`]: deepPayload };
      }
      assert.throws(
        () => assertNoCaptionFieldsInPayload(deepPayload),
        /R5 Violation.*burn_subtitles/
      );
    });

    await st.test('2b. Multi-dimensional array nesting with mixed types', () => {
      const arrayPayload = {
        meta: { id: 'req_1' },
        nestedArray: [
          1,
          'safe string',
          null,
          [
            true,
            [
              [
                { CaptionsStyle: 'bold' }
              ]
            ]
          ]
        ]
      };
      assert.throws(
        () => assertNoCaptionFieldsInPayload(arrayPayload),
        /R5 Violation.*CaptionsStyle/
      );
    });

    await st.test('2c. Case variations across all forbidden keywords', () => {
      const caseVariants = [
        'subtitles', 'Subtitles', 'SUBTITLES', 'sUbTiTlEs',
        'captions', 'Captions', 'CAPTIONS', 'cApTiOnS',
        'srt', 'Srt', 'SRT', 'sRt',
        'vtt', 'Vtt', 'VTT', 'vTt',
        'ass', 'Ass', 'ASS', 'aSs'
      ];

      for (const k of caseVariants) {
        assert.throws(
          () => assertNoCaptionFieldsInPayload({ [k]: true }),
          new RegExp(`R5 Violation.*'${k}'`),
          `Expected rejection for case variant: ${k}`
        );
      }
    });

    await st.test('2d. Compound tokens with diverse separators', () => {
      const compoundVariants = [
        'burn_subtitles', 'burnSubtitles', 'burn-subtitles', 'burn.subtitles',
        'subtitle_format', 'subtitleFormat', 'subtitle-format', 'subtitle.format',
        'caption_position', 'captionPosition', 'caption-position', 'caption.position',
        'srt_stream', 'srtStream', 'srt-stream', 'srt.stream',
        'vtt_export', 'vttExport', 'vtt-export', 'vtt.export',
        'ass_styles', 'assStyles', 'ass-styles', 'ass.styles'
      ];

      for (const k of compoundVariants) {
        assert.throws(
          () => assertNoCaptionFieldsInPayload({ [k]: 1 }),
          new RegExp(`R5 Violation.*'${k}'`),
          `Expected rejection for compound variant: ${k}`
        );
      }
    });

    await st.test('2e. Presence alone triggers rejection (negative and falsy values)', () => {
      const falsyValues = [false, null, 0, '', [], {}, undefined];
      for (const val of falsyValues) {
        assert.throws(
          () => assertNoCaptionFieldsInPayload({ subtitles: val }),
          /R5 Violation.*subtitles/,
          `Failed on falsy value: ${val}`
        );
      }
    });

    await st.test('2f. Circular reference robustness without infinite loop', () => {
      const circular = { name: 'gaming_job' };
      circular.loop = circular;
      circular.child = { back: circular };

      // Clean circular object passes without stack overflow
      assertNoCaptionFieldsInPayload(circular);

      // Dirty circular object fails gracefully
      circular.child.subtitles = false;
      assert.throws(
        () => assertNoCaptionFieldsInPayload(circular),
        /R5 Violation.*subtitles/
      );
    });

    await st.test('2g. False positive immunity: Innocent words containing sub-tokens', () => {
      const innocentDict = {
        asset_id: 'asset_99',
        asset_url: 'https://example.com/asset.mp4',
        assets: ['video.mp4'],
        pass_through: true,
        compass_angle: 45,
        mass_render: false,
        glass_overlay: true,
        bass_gain: 0,
        subtotal_duration: 60.5,
        subtask_count: 3,
        subpath_prefix: '/gaming',
        classic_mode: true,
        destination_canvas: { x: 0, y: 0, width: 1080, height: 1920 },
        assignee_id: 'usr_42',
        assumed_fps: 60,
      };

      // None of these should throw
      assertNoCaptionFieldsInPayload(innocentDict);
    });
  });

  // ============================================================================
  // AREA 3: ANCHOR DRIFT & RESIZE BOUNDARY ENFORCEMENT
  // ============================================================================
  await t.test('Area 3: Anchor Drift Invariance Across All 4 Handles', async (st) => {

    await st.test('3a. Deterministic corner pinning under boundary expansion and collapse', () => {
      const initial = { x: 0.20, y: 0.30, width: 0.35, height: 0.25 };
      const minSize = 0.05;

      const deltas = [
        [0.05, 0.05],     // In-bounds expansion
        [-0.05, -0.05],   // In-bounds shrinkage
        [5.0, 5.0],       // Severe boundary overshoot
        [-5.0, -5.0],     // Severe inward collapse
        [100.0, -100.0],  // Mixed massive deltas
        [-100.0, 100.0],
      ];

      for (const [dx, dy] of deltas) {
        // Handle 'se' -> fixed anchor: top-left (0.20, 0.30)
        const se = simulateHandleResize({ handle: 'se', startRect: initial, deltaX: dx, deltaY: dy });
        assert.equal(se.x, initial.x, `Handle 'se' drifted top-left x anchor!`);
        assert.equal(se.y, initial.y, `Handle 'se' drifted top-left y anchor!`);
        assert.ok(se.width >= minSize);
        assert.ok(se.height >= minSize);
        assert.ok(se.x + se.width <= 1.0001);
        assert.ok(se.y + se.height <= 1.0001);

        // Handle 'ne' -> fixed anchor: bottom-left (0.20, 0.30 + 0.25 = 0.55)
        const ne = simulateHandleResize({ handle: 'ne', startRect: initial, deltaX: dx, deltaY: dy });
        assert.equal(ne.x, initial.x, `Handle 'ne' drifted bottom-left x anchor!`);
        const neBottom = Math.round((ne.y + ne.height) * 10000) / 10000;
        const expectedNEBottom = Math.round((initial.y + initial.height) * 10000) / 10000;
        assert.equal(neBottom, expectedNEBottom, `Handle 'ne' drifted bottom-left y anchor!`);
        assert.ok(ne.y >= 0.0);
        assert.ok(ne.x + ne.width <= 1.0001);

        // Handle 'sw' -> fixed anchor: top-right (0.20 + 0.35 = 0.55, 0.30)
        const sw = simulateHandleResize({ handle: 'sw', startRect: initial, deltaX: dx, deltaY: dy });
        assert.equal(sw.y, initial.y, `Handle 'sw' drifted top-right y anchor!`);
        const swRight = Math.round((sw.x + sw.width) * 10000) / 10000;
        const expectedSWRight = Math.round((initial.x + initial.width) * 10000) / 10000;
        assert.equal(swRight, expectedSWRight, `Handle 'sw' drifted top-right x anchor!`);
        assert.ok(sw.x >= 0.0);
        assert.ok(sw.y + sw.height <= 1.0001);

        // Handle 'nw' -> fixed anchor: bottom-right (0.55, 0.55)
        const nw = simulateHandleResize({ handle: 'nw', startRect: initial, deltaX: dx, deltaY: dy });
        const nwRight = Math.round((nw.x + nw.width) * 10000) / 10000;
        const nwBottom = Math.round((nw.y + nw.height) * 10000) / 10000;
        const expectedNWRight = Math.round((initial.x + initial.width) * 10000) / 10000;
        const expectedNWBottom = Math.round((initial.y + initial.height) * 10000) / 10000;
        assert.equal(nwRight, expectedNWRight, `Handle 'nw' drifted bottom-right x anchor!`);
        assert.equal(nwBottom, expectedNWBottom, `Handle 'nw' drifted bottom-right y anchor!`);
        assert.ok(nw.x >= 0.0);
        assert.ok(nw.y >= 0.0);
      }
    });

    await st.test('3b. 1,000 randomized fuzzing iterations against production calculateResize', () => {
      const handles = ['se', 'sw', 'ne', 'nw'];

      for (let i = 0; i < 1000; i++) {
        const handle = handles[Math.floor(Math.random() * handles.length)];
        const rx = Math.random() * 0.75;
        const ry = Math.random() * 0.75;
        const rw = 0.05 + Math.random() * (0.95 - rx);
        const rh = 0.05 + Math.random() * (0.95 - ry);
        const rect = { x: rx, y: ry, width: rw, height: rh };
        const dx = (Math.random() - 0.5) * 3.0; // [-1.5, 1.5]
        const dy = (Math.random() - 0.5) * 3.0;

        const helperResult = simulateHandleResize({
          handle,
          startRect: rect,
          deltaX: dx,
          deltaY: dy,
        });

        const prodResult = canonicalCalculateResize(rect, handle, dx, dy);

        assert.deepEqual(
          helperResult,
          prodResult,
          `Fuzzing mismatch at iteration ${i} for handle ${handle}: helper=${JSON.stringify(helperResult)}, prod=${JSON.stringify(prodResult)}`
        );

        assertNormalizedRect(helperResult);
      }
    });
  });
});
