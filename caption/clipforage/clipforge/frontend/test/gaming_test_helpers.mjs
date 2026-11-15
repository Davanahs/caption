/**
 * gaming_test_helpers.mjs
 * =======================
 * Reusable ESM test helpers for Node.js native `node --test` suites
 * validating ClipForge Dual-Region Gaming Layout functionality.
 *
 * Provides:
 * 1. Mock Canvas 2D evaluation & drawImage call recording
 * 2. Pointer event simulations (drag, resize handles, clicks)
 * 3. Preset verification & canonical geometry calculation
 * 4. Strict R5 Zero-Caption invariant assertions (DOM, payloads, artifacts)
 * 5. Pure test oracles for normalized coordinate math & even-pixel alignment
 */

import assert from 'node:assert/strict';

// ==============================================================================
// 1. CANONICAL CONSTANTS & PRESETS
// ==============================================================================

export const DEFAULT_CANVAS_WIDTH = 1080;
export const DEFAULT_CANVAS_HEIGHT = 1920;
export const DEFAULT_CANVAS_ASPECT_RATIO = 9 / 16; // 0.5625

export const MIN_ROI_SIZE = 0.05;
export const DEFAULT_FACECAM_WIDTH = 0.30;
export const DEFAULT_FACECAM_HEIGHT = 0.22;
export const DEFAULT_FACECAM_MARGIN_X = 0.05;
export const DEFAULT_FACECAM_MARGIN_Y = 0.04;
export const DEFAULT_PRESET_MARGIN = DEFAULT_FACECAM_MARGIN_Y;

/**
 * Authoritative Canonical Preset Rectangles
 */
export const CANONICAL_PRESETS = {
  'top-left': {
    x: DEFAULT_FACECAM_MARGIN_X,
    y: DEFAULT_FACECAM_MARGIN_Y,
    width: DEFAULT_FACECAM_WIDTH,
    height: DEFAULT_FACECAM_HEIGHT,
  },
  'top-right': {
    x: Math.round((1.0 - DEFAULT_FACECAM_WIDTH - DEFAULT_FACECAM_MARGIN_X) * 10000) / 10000,
    y: DEFAULT_FACECAM_MARGIN_Y,
    width: DEFAULT_FACECAM_WIDTH,
    height: DEFAULT_FACECAM_HEIGHT,
  },
  'bottom-left': {
    x: DEFAULT_FACECAM_MARGIN_X,
    y: Math.round((1.0 - DEFAULT_FACECAM_HEIGHT - DEFAULT_FACECAM_MARGIN_Y) * 10000) / 10000,
    width: DEFAULT_FACECAM_WIDTH,
    height: DEFAULT_FACECAM_HEIGHT,
  },
  'bottom-right': {
    x: Math.round((1.0 - DEFAULT_FACECAM_WIDTH - DEFAULT_FACECAM_MARGIN_X) * 10000) / 10000,
    y: Math.round((1.0 - DEFAULT_FACECAM_HEIGHT - DEFAULT_FACECAM_MARGIN_Y) * 10000) / 10000,
    width: DEFAULT_FACECAM_WIDTH,
    height: DEFAULT_FACECAM_HEIGHT,
  },
};

/**
 * Returns canonical expected preset normalized coordinates.
 * @param {'top-left'|'top-right'|'bottom-left'|'bottom-right'} preset
 * @returns {{x: number, y: number, width: number, height: number}}
 */
export function getCanonicalPresetRect(preset) {
  const p = CANONICAL_PRESETS[preset];
  if (!p) {
    throw new Error(`Unknown preset: ${preset}. Valid presets are ${Object.keys(CANONICAL_PRESETS).join(', ')}`);
  }
  return { ...p };
}

/**
 * Asserts an actual rectangle matches canonical preset within floating-point tolerance.
 */
export function assertPresetParity(actualRect, preset, tolerance = 1e-5) {
  const expected = getCanonicalPresetRect(preset);
  assert.ok(actualRect, `Actual rectangle must be defined for preset ${preset}`);
  assert.ok(
    Math.abs(actualRect.x - expected.x) <= tolerance,
    `Preset ${preset} x mismatch: expected ${expected.x}, got ${actualRect.x}`
  );
  assert.ok(
    Math.abs(actualRect.y - expected.y) <= tolerance,
    `Preset ${preset} y mismatch: expected ${expected.y}, got ${actualRect.y}`
  );
  assert.ok(
    Math.abs(actualRect.width - expected.width) <= tolerance,
    `Preset ${preset} width mismatch: expected ${expected.width}, got ${actualRect.width}`
  );
  assert.ok(
    Math.abs(actualRect.height - expected.height) <= tolerance,
    `Preset ${preset} height mismatch: expected ${expected.height}, got ${actualRect.height}`
  );
}

// ==============================================================================
// 2. MOCK CANVAS 2D EVALUATION
// ==============================================================================

/**
 * Creates a mock HTML5 Canvas and 2D Context recording draw operations.
 * Allows deterministic opaque-box evaluation of 9:16 composite canvas preview.
 */
export function createMockCanvas(width = DEFAULT_CANVAS_WIDTH, height = DEFAULT_CANVAS_HEIGHT) {
  const drawCalls = [];
  const operations = [];

  const ctx = {
    canvas: null, // assigned below
    fillStyle: '#000000',
    strokeStyle: '#000000',
    lineWidth: 1,
    globalAlpha: 1.0,

    drawImage: (...args) => {
      // Signatures:
      // drawImage(image, dx, dy)
      // drawImage(image, dx, dy, dw, dh)
      // drawImage(image, sx, sy, sw, sh, dx, dy, dw, dh)
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

    fillRect: (x, y, w, h) => {
      operations.push({ op: 'fillRect', x, y, w, h, fillStyle: ctx.fillStyle });
    },

    strokeRect: (x, y, w, h) => {
      operations.push({ op: 'strokeRect', x, y, w, h, strokeStyle: ctx.strokeStyle });
    },

    clearRect: (x, y, w, h) => {
      operations.push({ op: 'clearRect', x, y, w, h });
    },

    save: () => { operations.push({ op: 'save' }); },
    restore: () => { operations.push({ op: 'restore' }); },
    beginPath: () => { operations.push({ op: 'beginPath' }); },
    closePath: () => { operations.push({ op: 'closePath' }); },
    stroke: () => { operations.push({ op: 'stroke' }); },
    fill: () => { operations.push({ op: 'fill' }); },
    scale: (sx, sy) => { operations.push({ op: 'scale', sx, sy }); },
    translate: (tx, ty) => { operations.push({ op: 'translate', tx, ty }); },

    // Test inspection getters
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
    getBoundingClientRect: () => ({
      left: 0,
      top: 0,
      right: width,
      bottom: height,
      width,
      height,
      x: 0,
      y: 0,
    }),
  };

  ctx.canvas = canvas;
  return { canvas, ctx };
}

/**
 * Evaluates whether canvas drawImage calls match expected composite layout.
 * Asserts Layer 1 (gameplay at index 0) and Layer 2 (facecam at index 1).
 * Validates crop origin (sx, sy), dimensions (sw, sh), and destination bounds (dx, dy, dw, dh).
 */
export function assertCompositeCanvasParity({
  ctx,
  expectedGameplayCrop,
  expectedFacecamCrop,
  expectedFacecamDest,
  expectedGameplayDest,
  tolerancePx = 2,
}) {
  const draws = ctx.getDrawCalls();
  assert.ok(draws.length >= 2, `Expected at least 2 drawImage calls (gameplay + facecam), got ${draws.length}`);

  const gameplayDraw = draws[0];
  const facecamDraw = draws[1];

  const canvasWidth = ctx.canvas?.width || DEFAULT_CANVAS_WIDTH;
  const canvasHeight = ctx.canvas?.height || DEFAULT_CANVAS_HEIGHT;

  if (expectedGameplayCrop) {
    if (expectedGameplayCrop.x !== undefined) {
      assert.ok(
        Math.abs(gameplayDraw.sx - expectedGameplayCrop.x) <= tolerancePx,
        `Gameplay crop x mismatch: expected ${expectedGameplayCrop.x}, got ${gameplayDraw.sx}`
      );
    }
    if (expectedGameplayCrop.y !== undefined) {
      assert.ok(
        Math.abs(gameplayDraw.sy - expectedGameplayCrop.y) <= tolerancePx,
        `Gameplay crop y mismatch: expected ${expectedGameplayCrop.y}, got ${gameplayDraw.sy}`
      );
    }
    const expGW = expectedGameplayCrop.w !== undefined ? expectedGameplayCrop.w : expectedGameplayCrop.width;
    if (expGW !== undefined) {
      assert.ok(
        Math.abs(gameplayDraw.sw - expGW) <= tolerancePx,
        `Gameplay crop width mismatch: expected ${expGW}, got ${gameplayDraw.sw}`
      );
    }
    const expGH = expectedGameplayCrop.h !== undefined ? expectedGameplayCrop.h : expectedGameplayCrop.height;
    if (expGH !== undefined) {
      assert.ok(
        Math.abs(gameplayDraw.sh - expGH) <= tolerancePx,
        `Gameplay crop height mismatch: expected ${expGH}, got ${gameplayDraw.sh}`
      );
    }
  }

  // Layer 1 Gameplay Destination: fills canvas unless explicitly overridden
  const targetGameplayDest = expectedGameplayDest || {
    x: 0,
    y: 0,
    w: canvasWidth,
    h: canvasHeight,
  };
  const expGDestX = targetGameplayDest.x ?? 0;
  const expGDestY = targetGameplayDest.y ?? 0;
  const expGDestW = targetGameplayDest.w !== undefined ? targetGameplayDest.w : (targetGameplayDest.width ?? canvasWidth);
  const expGDestH = targetGameplayDest.h !== undefined ? targetGameplayDest.h : (targetGameplayDest.height ?? canvasHeight);

  assert.ok(
    Math.abs(gameplayDraw.dx - expGDestX) <= tolerancePx,
    `Gameplay dest x mismatch: expected ${expGDestX}, got ${gameplayDraw.dx}`
  );
  assert.ok(
    Math.abs(gameplayDraw.dy - expGDestY) <= tolerancePx,
    `Gameplay dest y mismatch: expected ${expGDestY}, got ${gameplayDraw.dy}`
  );
  assert.ok(
    Math.abs(gameplayDraw.dw - expGDestW) <= tolerancePx,
    `Gameplay dest width mismatch: expected ${expGDestW}, got ${gameplayDraw.dw}`
  );
  assert.ok(
    Math.abs(gameplayDraw.dh - expGDestH) <= tolerancePx,
    `Gameplay dest height mismatch: expected ${expGDestH}, got ${gameplayDraw.dh}`
  );

  if (expectedFacecamCrop) {
    if (expectedFacecamCrop.x !== undefined) {
      assert.ok(
        Math.abs(facecamDraw.sx - expectedFacecamCrop.x) <= tolerancePx,
        `Facecam crop x mismatch: expected ${expectedFacecamCrop.x}, got ${facecamDraw.sx}`
      );
    }
    if (expectedFacecamCrop.y !== undefined) {
      assert.ok(
        Math.abs(facecamDraw.sy - expectedFacecamCrop.y) <= tolerancePx,
        `Facecam crop y mismatch: expected ${expectedFacecamCrop.y}, got ${facecamDraw.sy}`
      );
    }
    const expFW = expectedFacecamCrop.w !== undefined ? expectedFacecamCrop.w : expectedFacecamCrop.width;
    if (expFW !== undefined) {
      assert.ok(
        Math.abs(facecamDraw.sw - expFW) <= tolerancePx,
        `Facecam crop width mismatch: expected ${expFW}, got ${facecamDraw.sw}`
      );
    }
    const expFH = expectedFacecamCrop.h !== undefined ? expectedFacecamCrop.h : expectedFacecamCrop.height;
    if (expFH !== undefined) {
      assert.ok(
        Math.abs(facecamDraw.sh - expFH) <= tolerancePx,
        `Facecam crop height mismatch: expected ${expFH}, got ${facecamDraw.sh}`
      );
    }
  }

  if (expectedFacecamDest) {
    const expFDestX = expectedFacecamDest.x;
    const expFDestY = expectedFacecamDest.y;
    const expFDestW = expectedFacecamDest.w !== undefined ? expectedFacecamDest.w : expectedFacecamDest.width;
    const expFDestH = expectedFacecamDest.h !== undefined ? expectedFacecamDest.h : expectedFacecamDest.height;

    if (expFDestX !== undefined) {
      assert.ok(
        Math.abs(facecamDraw.dx - expFDestX) <= tolerancePx,
        `Facecam dest x mismatch: expected ${expFDestX}, got ${facecamDraw.dx}`
      );
    }
    if (expFDestY !== undefined) {
      assert.ok(
        Math.abs(facecamDraw.dy - expFDestY) <= tolerancePx,
        `Facecam dest y mismatch: expected ${expFDestY}, got ${facecamDraw.dy}`
      );
    }
    if (expFDestW !== undefined) {
      assert.ok(
        Math.abs(facecamDraw.dw - expFDestW) <= tolerancePx,
        `Facecam dest width mismatch: expected ${expFDestW}, got ${facecamDraw.dw}`
      );
    }
    if (expFDestH !== undefined) {
      assert.ok(
        Math.abs(facecamDraw.dh - expFDestH) <= tolerancePx,
        `Facecam dest height mismatch: expected ${expFDestH}, got ${facecamDraw.dh}`
      );
    }
  }
}

// ==============================================================================
// 3. POINTER EVENT SIMULATION HELPERS
// ==============================================================================

/**
 * Creates synthetic PointerEvent / MouseEvent payload.
 */
export function createPointerEvent(type, { clientX = 0, clientY = 0, button = 0, buttons = 1 } = {}) {
  return {
    type,
    clientX,
    clientY,
    pageX: clientX,
    pageY: clientY,
    button,
    buttons,
    preventDefault: () => {},
    stopPropagation: () => {},
  };
}

/**
 * Simulates a continuous drag sequence from (startX, startY) to (endX, endY).
 * Calls provided callbacks or dispatches events on element.
 */
export function simulatePointerDrag({
  startX,
  startY,
  endX,
  endY,
  steps = 5,
  onDown = null,
  onMove = null,
  onUp = null,
}) {
  const downEvt = createPointerEvent('pointerdown', { clientX: startX, clientY: startY });
  if (onDown) onDown(downEvt);

  const dx = (endX - startX) / steps;
  const dy = (endY - startY) / steps;

  for (let i = 1; i <= steps; i++) {
    const curX = startX + dx * i;
    const curY = startY + dy * i;
    const moveEvt = createPointerEvent('pointermove', { clientX: curX, clientY: curY });
    if (onMove) onMove(moveEvt);
  }

  const upEvt = createPointerEvent('pointerup', { clientX: endX, clientY: endY, buttons: 0 });
  if (onUp) onUp(upEvt);

  return { startX, startY, endX, endY };
}

/**
 * Simulates resizing a bounding box via a corner resize handle ('nw', 'ne', 'sw', 'se').
 * Preserves the opposite corner as a fixed anchor point matching gamingCoordinates.ts calculateResize.
 */
export function simulateHandleResize({
  handle,
  startRect,
  deltaX,
  deltaY,
  clamp = true,
  minSize = MIN_ROI_SIZE,
}) {
  const validHandles = ['nw', 'ne', 'sw', 'se'];
  if (!validHandles.includes(handle)) {
    throw new Error(`Invalid handle: ${handle}`);
  }

  const x0 = Number.isFinite(startRect.x) ? startRect.x : 0.0;
  const y0 = Number.isFinite(startRect.y) ? startRect.y : 0.0;
  const w0 = Number.isFinite(startRect.width) ? startRect.width : minSize;
  const h0 = Number.isFinite(startRect.height) ? startRect.height : minSize;

  if (!clamp) {
    let x = x0;
    let y = y0;
    let width = w0;
    let height = h0;

    switch (handle) {
      case 'se':
        width += deltaX;
        height += deltaY;
        break;
      case 'sw':
        x += deltaX;
        width -= deltaX;
        height += deltaY;
        break;
      case 'ne':
        y += deltaY;
        width += deltaX;
        height -= deltaY;
        break;
      case 'nw':
        x += deltaX;
        y += deltaY;
        width -= deltaX;
        height -= deltaY;
        break;
    }
    return { x, y, width, height };
  }

  let x = x0;
  let y = y0;
  let width = w0;
  let height = h0;

  switch (handle) {
    case 'se': {
      // Anchor: Top-Left (x0, y0)
      const r = Math.max(x0 + minSize, Math.min(1.0, x0 + w0 + deltaX));
      const b = Math.max(y0 + minSize, Math.min(1.0, y0 + h0 + deltaY));
      x = x0;
      y = y0;
      width = r - x0;
      height = b - y0;
      break;
    }
    case 'ne': {
      // Anchor: Bottom-Left (x0, y0 + h0)
      const r = Math.max(x0 + minSize, Math.min(1.0, x0 + w0 + deltaX));
      const newY = Math.max(0.0, Math.min(y0 + h0 - minSize, y0 + deltaY));
      x = x0;
      y = newY;
      width = r - x0;
      height = (y0 + h0) - newY;
      break;
    }
    case 'sw': {
      // Anchor: Top-Right (x0 + w0, y0)
      const newX = Math.max(0.0, Math.min(x0 + w0 - minSize, x0 + deltaX));
      const b = Math.max(y0 + minSize, Math.min(1.0, y0 + h0 + deltaY));
      x = newX;
      y = y0;
      width = (x0 + w0) - newX;
      height = b - y0;
      break;
    }
    case 'nw': {
      // Anchor: Bottom-Right (x0 + w0, y0 + h0)
      const newX = Math.max(0.0, Math.min(x0 + w0 - minSize, x0 + deltaX));
      const newY = Math.max(0.0, Math.min(y0 + h0 - minSize, y0 + deltaY));
      x = newX;
      y = newY;
      width = (x0 + w0) - newX;
      height = (y0 + h0) - newY;
      break;
    }
  }

  return {
    x: Math.round(x * 10000) / 10000,
    y: Math.round(y * 10000) / 10000,
    width: Math.round(width * 10000) / 10000,
    height: Math.round(height * 10000) / 10000,
  };
}

// ==============================================================================
// 4. STRICT R5 ZERO-CAPTION ASSERTION HELPERS
// ==============================================================================

/**
 * Inspects a DOM element or HTML/JSX source string to verify zero caption controls exist.
 * Asserts absence of:
 * - Subtitle toggle switches
 * - Caption style selectors
 * - SRT / VTT uploaders
 * - Caption burning options
 * Inspects outerHTML of root elements to detect attributes (data-testid, class, aria-labels)
 * and falls back to innerHTML or raw string.
 */
export function assertNoCaptionControlsInDOM(sourceOrHtml) {
  const content = typeof sourceOrHtml === 'string'
    ? sourceOrHtml
    : (sourceOrHtml?.outerHTML || sourceOrHtml?.innerHTML || '');

  const forbiddenPatterns = [
    /subtitle/i,
    /caption/i,
    /\.srt\b/i,
    /\.vtt\b/i,
    /\.ass\b/i,
    /closed caption/i,
    /burn-in subtitles/i,
    /subtitles_style/i,
  ];

  for (const pattern of forbiddenPatterns) {
    assert.ok(
      !pattern.test(content),
      `R5 Violation: Prohibited caption/subtitle reference matching ${pattern} found in UI source:\n${content.slice(0, 300)}...`
    );
  }
}

/**
 * Asserts that an API submission payload contains strictly zero caption or subtitle parameters.
 * Recursively scans all payload keys, nested objects, and arrays.
 * Rejects case variations (Subtitles, Captions, SRT), compound tokens (burn_subtitles, captionStyle),
 * and format extensions (srt, vtt, ass) without false-positive matching on legitimate words (asset, pass).
 */
export function assertNoCaptionFieldsInPayload(payload) {
  assert.ok(payload && typeof payload === 'object', 'Payload must be an object');

  const forbiddenPattern = /subtitle|caption|\bsrt\b|\bvtt\b|\bass\b/i;
  const seen = new WeakSet();

  function isForbiddenKey(key) {
    if (forbiddenPattern.test(key)) {
      return true;
    }
    // Check normalized key by splitting camelCase, snake_case, kebab-case, and dot notation
    const normalized = key
      .replace(/([a-z])([A-Z])/g, (m, p1, p2) => `${p1} ${p2}`)
      .replace(/[._\-]/g, ' ');
    return forbiddenPattern.test(normalized);
  }

  function scan(current, path = '') {
    if (!current || typeof current !== 'object') {
      return;
    }
    if (seen.has(current)) {
      return;
    }
    seen.add(current);

    if (Array.isArray(current)) {
      current.forEach((item, index) => {
        scan(item, path ? `${path}[${index}]` : `[${index}]`);
      });
      return;
    }

    for (const key of Object.keys(current)) {
      const fullPath = path ? `${path}.${key}` : key;

      if (isForbiddenKey(key)) {
        if (path === 'gaming_layout' || path.startsWith('gaming_layout.')) {
          assert.fail(`R5 Violation: gaming_layout contains prohibited caption field '${key}' (at ${fullPath})`);
        } else {
          assert.fail(`R5 Violation: API payload contains prohibited caption field '${key}' (at ${fullPath})`);
        }
      }

      scan(current[key], fullPath);
    }
  }

  scan(payload);
}

// ==============================================================================
// 5. PURE TEST ORACLES (COORDINATES & EVEN PIXELS)
// ==============================================================================

/**
 * Authoritative boundary clamping oracle.
 * Enforces:
 *   0.0 <= x <= 1.0 - minSize
 *   0.0 <= y <= 1.0 - minSize
 *   minSize <= width <= 1.0 - x
 *   minSize <= height <= 1.0 - y
 * Clamps origin (x, y) first to prevent coordinate shifting on overflowing width/height.
 */
export function clampNormalizedRect(rect, minSize = MIN_ROI_SIZE) {
  const safeX = Number.isFinite(rect.x) ? rect.x : 0.0;
  const safeY = Number.isFinite(rect.y) ? rect.y : 0.0;
  const safeW = Number.isFinite(rect.width) ? rect.width : minSize;
  const safeH = Number.isFinite(rect.height) ? rect.height : minSize;

  let x = Math.max(0.0, Math.min(1.0 - minSize, safeX));
  let y = Math.max(0.0, Math.min(1.0 - minSize, safeY));
  let width = Math.max(minSize, Math.min(1.0 - x, safeW));
  let height = Math.max(minSize, Math.min(1.0 - y, safeH));

  return {
    x: Math.round(x * 10000) / 10000,
    y: Math.round(y * 10000) / 10000,
    width: Math.round(width * 10000) / 10000,
    height: Math.round(height * 10000) / 10000,
  };
}

/**
 * Authoritative Even-Pixel conversion formula:
 *   floor((coord * dim) / 2) * 2
 * Anchors origin (x, y) and truncates width/height on boundary overflow.
 */
export function computeEvenPixelCrop(normRect, srcW, srcH) {
  const maxW = Math.floor(srcW / 2) * 2;
  const maxH = Math.floor(srcH / 2) * 2;

  let x = Math.floor((Math.max(0, normRect.x) * srcW) / 2) * 2;
  let y = Math.floor((Math.max(0, normRect.y) * srcH) / 2) * 2;
  let w = Math.max(2, Math.floor((Math.max(0, normRect.width) * srcW) / 2) * 2);
  let h = Math.max(2, Math.floor((Math.max(0, normRect.height) * srcH) / 2) * 2);

  if (x + w > maxW) {
    w = Math.max(2, Math.floor((maxW - x) / 2) * 2);
  }
  if (y + h > maxH) {
    h = Math.max(2, Math.floor((maxH - y) / 2) * 2);
  }

  return { x, y, w, h };
}

/**
 * Asserts a NormalizedRect adheres to all geometry invariants.
 */
export function assertNormalizedRect(rect, minSize = MIN_ROI_SIZE) {
  assert.ok(rect, 'Rect must be defined');
  assert.ok(Number.isFinite(rect.x), `x must be finite, got ${rect.x}`);
  assert.ok(Number.isFinite(rect.y), `y must be finite, got ${rect.y}`);
  assert.ok(Number.isFinite(rect.width), `width must be finite, got ${rect.width}`);
  assert.ok(Number.isFinite(rect.height), `height must be finite, got ${rect.height}`);

  assert.ok(rect.x >= 0.0, `x (${rect.x}) must be >= 0.0`);
  assert.ok(rect.y >= 0.0, `y (${rect.y}) must be >= 0.0`);
  assert.ok(rect.width >= minSize, `width (${rect.width}) must be >= ${minSize}`);
  assert.ok(rect.height >= minSize, `height (${rect.height}) must be >= ${minSize}`);
  assert.ok(rect.x + rect.width <= 1.000001, `x + width (${rect.x + rect.width}) must be <= 1.0`);
  assert.ok(rect.y + rect.height <= 1.000001, `y + height (${rect.y + rect.height}) must be <= 1.0`);
}
