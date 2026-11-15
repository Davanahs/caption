import test from 'node:test';
import assert from 'node:assert/strict';

import {
  toEvenPixel,
  toEvenSpan,
  toEvenPixels,
  toSourceCrop,
  toCanvasOverlay,
  calculateGameplayFraming,
  validateNormalizedRect,
  validateGamingLayout,
  calculateGamingCoordinates,
} from '../lib/gamingCoordinates.ts';

test('CHALLENGER SUITE A: Small Odd Dimensions & 7x7 Crop Containment Invariant', async (t) => {
  await t.test('7x7 source video crop near bottom-right edge must not exceed source dimensions', () => {
    // A valid normalized ROI near bottom-right
    const norm = { x: 0.95, y: 0.95, width: 0.05, height: 0.05 };
    const crop = toSourceCrop(norm, 7, 7);
    const maxW = Math.floor(7 / 2) * 2; // 6
    const maxH = Math.floor(7 / 2) * 2; // 6

    // Counterexample verification:
    // crop.x=6, crop.w=2 -> crop.x + crop.w = 8 > 7 (and > 6)
    assert.ok(
      crop.x + crop.w <= maxW,
      `Crop overflow on 7x7: crop.x (${crop.x}) + crop.w (${crop.w}) = ${crop.x + crop.w} exceeds maxW (${maxW})`
    );
    assert.ok(
      crop.y + crop.h <= maxH,
      `Crop overflow on 7x7: crop.y (${crop.y}) + crop.h (${crop.h}) = ${crop.y + crop.h} exceeds maxH (${maxH})`
    );
  });

  await t.test('Scan small odd dimensions (3..19) for boundary crop overflow', () => {
    const overflows = [];
    for (let dim = 3; dim <= 19; dim += 2) {
      const crop = toSourceCrop({ x: 0.95, y: 0.95, width: 0.05, height: 0.05 }, dim, dim);
      const maxDim = Math.floor(dim / 2) * 2;
      if (crop.x + crop.w > maxDim) {
        overflows.push({ dim, x: crop.x, w: crop.w, sum: crop.x + crop.w, maxDim });
      }
    }
    assert.equal(
      overflows.length,
      0,
      `Detected ${overflows.length} crop overflows on small odd dimensions: ${JSON.stringify(overflows)}`
    );
  });
});

test('CHALLENGER SUITE B: Zero and Negative Dimensions Parity & Validation Failure Modes', async (t) => {
  await t.test('calculateGamingCoordinates must reject zero or negative source dimensions (parity with Python)', () => {
    // In Python, to_source_crop raises ValueError("Source dimensions must be positive, got 0x0")
    // In TypeScript, calculateGamingCoordinates currently accepts src_w=0, src_h=0 without throwing!
    assert.throws(
      () => calculateGamingCoordinates({
        src_w: 0,
        src_h: 0,
        gameplay_roi: { x: 0.0, y: 0.0, width: 1.0, height: 1.0 },
        facecam_roi: { x: 0.7, y: 0.05, width: 0.25, height: 0.25 },
      }),
      /positive/i,
      'Must reject src_w=0, src_h=0'
    );
  });

  await t.test('calculateGamingCoordinates must reject negative source dimensions (parity with Python)', () => {
    // In Python, to_source_crop raises ValueError
    // In TypeScript, calculateGamingCoordinates emits negative crop offset in FFmpeg filter: crop=2:270:-1344:54
    assert.throws(
      () => calculateGamingCoordinates({
        src_w: -1920,
        src_h: 1080,
        gameplay_roi: { x: 0.0, y: 0.0, width: 1.0, height: 1.0 },
        facecam_roi: { x: 0.7, y: 0.05, width: 0.25, height: 0.25 },
      }),
      /positive/i,
      'Must reject negative src_w'
    );
  });

  await t.test('toCanvasOverlay must reject zero or negative canvas dimensions (parity with Python)', () => {
    // In Python, to_canvas_overlay raises ValueError("Canvas dimensions must be positive, got 0x1920")
    // In TypeScript, toCanvasOverlay accepts 0 without throwing and returns { x: 0, y: 0, w: 2, h: 960 }
    assert.throws(
      () => toCanvasOverlay({ x: 0.65, y: 0.04, width: 0.30, height: 0.22 }, 0, 1920),
      /positive/i,
      'Must reject canvasW=0'
    );
  });
});

test('CHALLENGER SUITE C: Non-Finite & NaN Dimension Handling in Quantization', async (t) => {
  await t.test('toEvenPixel and toEvenSpan must reject NaN dimension (parity with Python)', () => {
    // In Python: to_even_pixel(0.5, float('nan')) raises ValueError("cannot convert float NaN to integer")
    // In TypeScript: toEvenPixel(0.5, NaN) returns NaN silently!
    assert.throws(
      () => toEvenPixel(0.5, NaN),
      /finite/i,
      'toEvenPixel must throw on NaN dim instead of returning NaN'
    );
    assert.throws(
      () => toEvenSpan(0.5, NaN),
      /finite/i,
      'toEvenSpan must throw on NaN dim instead of returning NaN'
    );
  });
});

test('CHALLENGER SUITE D: Near-Boundary Epsilon Clamping & Negative Coordinate Leakage', async (t) => {
  await t.test('validateNormalizedRect must not leak negative coordinates when input is within negative epsilon', () => {
    // When x = -0.00005 (within eps=1e-4):
    // In Python: clean_x = max(0.0, ...) -> returns x = 0.0
    // In TypeScript: returns x = -0.00005, leaking a negative coordinate!
    const rect = { x: -0.00005, y: 0.1, width: 0.5, height: 0.5 };
    const validated = validateNormalizedRect(rect);
    assert.equal(
      validated.x,
      0.0,
      `validateNormalizedRect returned negative coordinate: x=${validated.x} (expected 0.0)`
    );
  });

  await t.test('validateNormalizedRect must clamp width so that x + width <= 1.0 when sum is within positive epsilon', () => {
    // When x = 0.5, width = 0.50005 (sum = 1.00005, within eps=1e-4):
    // In Python: clean_w = min(1.0 - clean_x, width) -> returns width = 0.5
    // In TypeScript: returns width = 0.50005, so x + width = 1.00005 > 1.0!
    const rect = { x: 0.5, y: 0.1, width: 0.50005, height: 0.5 };
    const validated = validateNormalizedRect(rect);
    assert.ok(
      validated.x + validated.width <= 1.0,
      `validateNormalizedRect returned sum > 1.0: ${validated.x} + ${validated.width} = ${validated.x + validated.width}`
    );
  });
});

test('CHALLENGER SUITE E: Interface Field Parity (canvas_width & canvas_height)', async (t) => {
  await t.test('GamingPlanResult in TypeScript must include canvas_width and canvas_height matching Python', () => {
    // In Python: plan.canvas_width = 1080, plan.canvas_height = 1920
    // In TypeScript: plan.canvas_width is undefined, plan.canvas_height is undefined
    const plan = calculateGamingCoordinates({
      src_w: 1920,
      src_h: 1080,
      canvas_w: 1080,
      canvas_h: 1920,
      gameplay_roi: { x: 0.0, y: 0.0, width: 1.0, height: 1.0 },
      facecam_roi: { x: 0.7, y: 0.05, width: 0.25, height: 0.25 },
      facecam_placement: 'top-right',
    });

    assert.equal(
      plan.canvas_width,
      1080,
      'plan.canvas_width is missing from GamingPlanResult in TypeScript'
    );
    assert.equal(
      plan.canvas_height,
      1920,
      'plan.canvas_height is missing from GamingPlanResult in TypeScript'
    );
  });
});
