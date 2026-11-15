/**
 * frontend/test/gaming_interactive_challenger_stress.test.mjs
 * 
 * Adversarial stress testing of interactive frontend geometry functions:
 * - calculateResize with pathological drag vectors (cross-over inversions)
 * - applyDrag with extreme out-of-bounds pointer offsets
 * - displayToNormalized with extreme letterbox, zero containers, and off-screen clicks
 * - clampNormalizedRect with NaN, Infinity, negative sizes
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  calculateResize,
  applyDrag,
  displayToNormalized,
  normalizedToDisplay,
  clampNormalizedRect,
  calculateRenderOffsets,
  getFacecamPreset,
} from '../lib/gamingCoordinates.ts';

test('INTERACTIVE ADVERSARIAL SUITE 1: Extreme Pointer Off-Screen and Zero Containers in Letterbox', () => {
  const container = { left: 100, top: 100, width: 800, height: 600 };

  // Click far off-screen to the left/top
  const farNegative = displayToNormalized(-10000, -10000, container, 1920, 1080);
  assert.equal(farNegative.x, 0.0, 'Pointer far left must clamp to x=0.0');
  assert.equal(farNegative.y, 0.0, 'Pointer far top must clamp to y=0.0');

  // Click far off-screen to the right/bottom
  const farPositive = displayToNormalized(10000, 10000, container, 1920, 1080);
  assert.equal(farPositive.x, 1.0, 'Pointer far right must clamp to x=1.0');
  assert.equal(farPositive.y, 1.0, 'Pointer far bottom must clamp to y=1.0');

  // Zero container dimensions
  const zeroContainer = { left: 0, top: 0, width: 0, height: 0 };
  const zeroRes = displayToNormalized(50, 50, zeroContainer, 1920, 1080);
  assert.equal(zeroRes.x, 0.0, 'Zero container must return safe norm x=0.0');
  assert.equal(zeroRes.y, 0.0, 'Zero container must return safe norm y=0.0');

  // Negative container dimensions
  const negContainer = { left: 0, top: 0, width: -100, height: -100 };
  const negRes = displayToNormalized(50, 50, negContainer, 1920, 1080);
  assert.equal(negRes.x, 0.0, 'Negative container must return safe norm x=0.0');
});

test('INTERACTIVE ADVERSARIAL SUITE 2: Extreme applyDrag Vectors and Boundary Containment', () => {
  const initialRect = { x: 0.5, y: 0.5, width: 0.3, height: 0.3 };

  // Extreme right drag
  const dragRight = applyDrag(initialRect, 10.0, 0.0);
  assert.equal(dragRight.x, 0.7, 'Right drag must clamp x at 1.0 - width (0.7)');
  assert.equal(dragRight.width, 0.3, 'Drag must not alter width');

  // Extreme left drag
  const dragLeft = applyDrag(initialRect, -10.0, 0.0);
  assert.equal(dragLeft.x, 0.0, 'Left drag must clamp x at 0.0');
  assert.equal(dragLeft.width, 0.3, 'Drag must not alter width');

  // Extreme bottom drag
  const dragBottom = applyDrag(initialRect, 0.0, 10.0);
  assert.equal(dragBottom.y, 0.7, 'Bottom drag must clamp y at 1.0 - height (0.7)');
  assert.equal(dragBottom.height, 0.3, 'Drag must not alter height');

  // Extreme top drag
  const dragTop = applyDrag(initialRect, 0.0, -10.0);
  assert.equal(dragTop.y, 0.0, 'Top drag must clamp y at 0.0');
  assert.equal(dragTop.height, 0.3, 'Drag must not alter height');
});

test('INTERACTIVE ADVERSARIAL SUITE 3: Resize Cross-Over Inversion and Minimum Dimension Clamping', () => {
  const baseRect = { x: 0.2, y: 0.2, width: 0.4, height: 0.4 };

  // Drag 'se' handle way past top-left anchor (e.g. to (0.0, 0.0))
  const resizedSE = calculateResize(baseRect, 'se', 0.0, 0.0);
  assert(resizedSE.width >= 0.05, `Width must be >= 0.05, got ${resizedSE.width}`);
  assert(resizedSE.height >= 0.05, `Height must be >= 0.05, got ${resizedSE.height}`);
  assert(resizedSE.x >= 0.0 && resizedSE.x + resizedSE.width <= 1.0);
  assert(resizedSE.y >= 0.0 && resizedSE.y + resizedSE.height <= 1.0);

  // Drag 'nw' handle way past bottom-right anchor (e.g. to (1.0, 1.0))
  const resizedNW = calculateResize(baseRect, 'nw', 1.0, 1.0);
  assert(resizedNW.width >= 0.05, `Width must be >= 0.05, got ${resizedNW.width}`);
  assert(resizedNW.height >= 0.05, `Height must be >= 0.05, got ${resizedNW.height}`);
  assert(resizedNW.x >= 0.0 && resizedNW.x + resizedNW.width <= 1.0);
  assert(resizedNW.y >= 0.0 && resizedNW.y + resizedNW.height <= 1.0);

  // Drag 'ne' handle way past bottom-left anchor (e.g. to (0.0, 1.0))
  const resizedNE = calculateResize(baseRect, 'ne', 0.0, 1.0);
  assert(resizedNE.width >= 0.05, `Width must be >= 0.05, got ${resizedNE.width}`);
  assert(resizedNE.height >= 0.05, `Height must be >= 0.05, got ${resizedNE.height}`);
  assert(resizedNE.x >= 0.0 && resizedNE.x + resizedNE.width <= 1.0);
  assert(resizedNE.y >= 0.0 && resizedNE.y + resizedNE.height <= 1.0);

  // Drag 'sw' handle way past top-right anchor (e.g. to (1.0, 0.0))
  const resizedSW = calculateResize(baseRect, 'sw', 1.0, 0.0);
  assert(resizedSW.width >= 0.05, `Width must be >= 0.05, got ${resizedSW.width}`);
  assert(resizedSW.height >= 0.05, `Height must be >= 0.05, got ${resizedSW.height}`);
  assert(resizedSW.x >= 0.0 && resizedSW.x + resizedSW.width <= 1.0);
  assert(resizedSW.y >= 0.0 && resizedSW.y + resizedSW.height <= 1.0);
});

test('INTERACTIVE ADVERSARIAL SUITE 4: clampNormalizedRect with Non-Finite and Degenerate Values', () => {
  // NaN inputs
  const nanRect = clampNormalizedRect({ x: NaN, y: NaN, width: NaN, height: NaN });
  assert.equal(nanRect.x, 0.0);
  assert.equal(nanRect.y, 0.0);
  assert.equal(nanRect.width, 0.05);
  assert.equal(nanRect.height, 0.05);

  // Infinity inputs
  const infRect = clampNormalizedRect({ x: Infinity, y: -Infinity, width: Infinity, height: -Infinity });
  assert.equal(infRect.x, 0.0);
  assert.equal(infRect.y, 0.0);
  assert.equal(infRect.width, 0.05);
  assert.equal(infRect.height, 0.05);

  // Negative sizes
  const negRect = clampNormalizedRect({ x: 0.5, y: 0.5, width: -0.2, height: -0.2 });
  assert.equal(negRect.width, 0.05);
  assert.equal(negRect.height, 0.05);
});
