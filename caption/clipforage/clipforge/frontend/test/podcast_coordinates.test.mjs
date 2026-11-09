import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createDefaultPodcastRegions,
  clampNormalizedRect,
  displayToNormalized,
  normalizedToDisplay,
  calculatePanelFraming,
  getOutputPreviewGeometry,
} from '../lib/podcastCoordinates.ts';

test('Podcast Coordinate Utilities and Normalization Contract', async (t) => {
  await t.test('1. createDefaultPodcastRegions returns 2 valid normalized regions', () => {
    const regions = createDefaultPodcastRegions();
    assert.equal(regions.length, 2);
    assert.equal(regions[0].id, 'area-1');
    assert.equal(regions[1].id, 'area-2');

    for (const r of regions) {
      assert.ok(r.x >= 0.0 && r.x <= 1.0, 'x must be between 0 and 1');
      assert.ok(r.y >= 0.0 && r.y <= 1.0, 'y must be between 0 and 1');
      assert.ok(r.width > 0.0 && r.x + r.width <= 1.0, 'width must fit inside frame');
      assert.ok(r.height > 0.0 && r.y + r.height <= 1.0, 'height must fit inside frame');
      assert.ok(r.color.startsWith('#'), 'Must have distinct color');
    }

    // Assert speaker 1 is on the left and speaker 2 is on the right
    assert.ok(regions[0].x < regions[1].x, 'Speaker 1 is on left, Speaker 2 is on right');
  });

  await t.test('2. clampNormalizedRect clamps out-of-bounds coordinates and enforces min size', () => {
    // Negative coordinates
    const clampedNegative = clampNormalizedRect({ x: -0.2, y: -0.5, width: 0.4, height: 0.4 });
    assert.equal(clampedNegative.x, 0.0);
    assert.equal(clampedNegative.y, 0.0);

    // Over-boundary coordinates
    const clampedOverflow = clampNormalizedRect({ x: 0.8, y: 0.7, width: 0.5, height: 0.5 });
    assert.ok(clampedOverflow.x + clampedOverflow.width <= 1.0);
    assert.ok(clampedOverflow.y + clampedOverflow.height <= 1.0);

    // Below minimum size
    const clampedTiny = clampNormalizedRect({ x: 0.2, y: 0.2, width: 0.01, height: 0.02 }, 0.05);
    assert.equal(clampedTiny.width, 0.05);
    assert.equal(clampedTiny.height, 0.05);
  });

  await t.test('3. displayToNormalized converts display pointer coordinates accurately', () => {
    const container = { left: 100, top: 50, width: 800, height: 450 };

    // Point at top-left
    const tl = displayToNormalized(100, 50, container);
    assert.equal(tl.x, 0.0);
    assert.equal(tl.y, 0.0);

    // Point at center
    const center = displayToNormalized(500, 275, container);
    assert.equal(center.x, 0.5);
    assert.equal(center.y, 0.5);

    // Point at bottom-right
    const br = displayToNormalized(900, 500, container);
    assert.equal(br.x, 1.0);
    assert.equal(br.y, 1.0);

    // Point outside container (clamped)
    const outside = displayToNormalized(1200, -20, container);
    assert.equal(outside.x, 1.0);
    assert.equal(outside.y, 0.0);
  });

  await t.test('4. normalizedToDisplay converts normalized values to display pixels', () => {
    const normRect = { x: 0.1, y: 0.2, width: 0.4, height: 0.5 };
    const container = { width: 1000, height: 500 };

    const disp = normalizedToDisplay(normRect, container);
    assert.equal(disp.left, 100);
    assert.equal(disp.top, 100);
    assert.equal(disp.width, 400);
    assert.equal(disp.height, 250);
  });

  await t.test('5. Normalized coordinates remain scale-invariant when container resizes', () => {
    const normRect = { x: 0.25, y: 0.25, width: 0.5, height: 0.5 };

    // At 1920x1080 display size
    const largeDisp = normalizedToDisplay(normRect, { width: 1920, height: 1080 });
    const largeBack = displayToNormalized(
      largeDisp.left,
      largeDisp.top,
      { left: 0, top: 0, width: 1920, height: 1080 }
    );
    assert.equal(largeBack.x, 0.25);
    assert.equal(largeBack.y, 0.25);

    // At small 640x360 laptop/mobile display size
    const smallDisp = normalizedToDisplay(normRect, { width: 640, height: 360 });
    const smallBack = displayToNormalized(
      smallDisp.left,
      smallDisp.top,
      { left: 0, top: 0, width: 640, height: 360 }
    );
    assert.equal(smallBack.x, 0.25);
    assert.equal(smallBack.y, 0.25);
  });

  await t.test('6. calculatePanelFraming preserves aspect ratio with contain scaling and centering padding', () => {
    // 400x600 region in 1920x1080 -> ar = 0.667 (taller than 1080x960 panel ar=1.125)
    const norm = { x: 0.1, y: 0.1, width: 400 / 1920, height: 600 / 1080 };
    const framing = calculatePanelFraming(norm, 1080, 960, 1920, 1080);

    // Height must scale to fit 960 exactly without cropping
    assert.equal(framing.scaledH, 960);
    // Width scaled proportionally: 400 * (960 / 600) = 640
    assert.equal(framing.scaledW, 640);
    // Centering padding on left and right: (1080 - 640) / 2 = 220
    assert.equal(framing.padX, 220);
    assert.equal(framing.padY, 0);
    // Zero pixels cut off
    assert.equal(framing.isTight, false);
  });

  await t.test('7. calculatePanelFraming detects tight vertical regions and generates headroom warnings', () => {
    // Extremely tight vertical box: height is only 15% of frame
    const tightNorm = { x: 0.3, y: 0.02, width: 0.2, height: 0.15 };
    const framing = calculatePanelFraming(tightNorm, 1080, 960, 1920, 1080);

    assert.equal(framing.isTight, true);
    assert.ok(framing.tightWarning !== null);
  });

  await t.test('8. getOutputPreviewGeometry for stacked composition produces 2 panels with top and bottom 1080x960 framing', () => {
    const regions = [
      { id: 'area-1', label: 'Speaker 1', x: 0.05, y: 0.1, width: 0.4, height: 0.8, color: '#3b82f6' },
      { id: 'area-2', label: 'Speaker 2', x: 0.55, y: 0.1, width: 0.4, height: 0.8, color: '#a855f7' },
    ];
    const geom = getOutputPreviewGeometry('stacked', regions, 1080, 1920, 1920, 1080);

    assert.equal(geom.composition, 'stacked');
    assert.equal(geom.canvasWidth, 1080);
    assert.equal(geom.canvasHeight, 1920);
    assert.equal(geom.panels.length, 2);

    // Top panel (Speaker 1)
    const p1 = geom.panels[0];
    assert.equal(p1.panelId, 'top-panel-speaker-1');
    assert.equal(p1.panelWidth, 1080);
    assert.equal(p1.panelHeight, 960);
    assert.equal(p1.panelTop, 0);
    assert.equal(p1.speakerLabel, 'Speaker 1');

    // Bottom panel (Speaker 2)
    const p2 = geom.panels[1];
    assert.equal(p2.panelId, 'bottom-panel-speaker-2');
    assert.equal(p2.panelWidth, 1080);
    assert.equal(p2.panelHeight, 960);
    assert.equal(p2.panelTop, 960);
    assert.equal(p2.speakerLabel, 'Speaker 2');
  });

  await t.test('9. getOutputPreviewGeometry for single_region composition produces 1 panel with full 1080x1920 framing using primary speaker', () => {
    const regions = [
      { id: 'area-1', label: 'Speaker 1', x: 0.2, y: 0.1, width: 0.5, height: 0.8, color: '#3b82f6' },
      { id: 'area-2', label: 'Speaker 2', x: 0.6, y: 0.1, width: 0.3, height: 0.8, color: '#a855f7' },
    ];
    // With 2 areas but single_region composition, must deterministically select Speaker 1 (Area 1, index 0)
    const geom = getOutputPreviewGeometry('single_region', regions, 1080, 1920, 1920, 1080);

    assert.equal(geom.composition, 'single_region');
    assert.equal(geom.panels.length, 1);
    const p = geom.panels[0];
    assert.equal(p.panelId, 'single-focus-panel');
    assert.equal(p.panelWidth, 1080);
    assert.equal(p.panelHeight, 1920);
    assert.equal(p.panelTop, 0);
    assert.equal(p.speakerLabel, 'Speaker 1');
  });

  await t.test('10. getOutputPreviewGeometry for side_by_side composition produces 2 horizontal half-panels (540x1920 each)', () => {
    const regions = [
      { id: 'area-1', label: 'Speaker 1', x: 0.05, y: 0.1, width: 0.4, height: 0.8, color: '#3b82f6' },
      { id: 'area-2', label: 'Speaker 2', x: 0.55, y: 0.1, width: 0.4, height: 0.8, color: '#a855f7' },
    ];
    const geom = getOutputPreviewGeometry('side_by_side', regions, 1080, 1920, 1920, 1080);

    assert.equal(geom.composition, 'side_by_side');
    assert.equal(geom.canvasWidth, 1080);
    assert.equal(geom.canvasHeight, 1920);
    assert.equal(geom.panels.length, 2);

    // Left half-panel (Speaker A)
    const pA = geom.panels[0];
    assert.equal(pA.panelId, 'left-panel-speaker-a');
    assert.equal(pA.panelWidth, 540);
    assert.equal(pA.panelHeight, 1920);
    assert.equal(pA.panelLeft, 0);
    assert.equal(pA.panelTop, 0);
    assert.equal(pA.speakerLabel, 'Speaker 1');

    // Right half-panel (Speaker B)
    const pB = geom.panels[1];
    assert.equal(pB.panelId, 'right-panel-speaker-b');
    assert.equal(pB.panelWidth, 540);
    assert.equal(pB.panelHeight, 1920);
    assert.equal(pB.panelLeft, 540);
    assert.equal(pB.panelTop, 0);
    assert.equal(pB.speakerLabel, 'Speaker 2');
  });

  await t.test('11. getOutputPreviewGeometry for fixed_two_person composition produces 1 continuous 1080x1920 canvas enclosing both participants', () => {
    const regions = [
      { id: 'area-1', label: 'Speaker 1', x: 0.1, y: 0.15, width: 0.3, height: 0.7, color: '#3b82f6' },
      { id: 'area-2', label: 'Speaker 2', x: 0.6, y: 0.15, width: 0.3, height: 0.7, color: '#a855f7' },
    ];
    const geom = getOutputPreviewGeometry('fixed_two_person', regions, 1080, 1920, 1920, 1080);

    assert.equal(geom.composition, 'fixed_two_person');
    assert.equal(geom.canvasWidth, 1080);
    assert.equal(geom.canvasHeight, 1920);
    assert.equal(geom.panels.length, 1);

    const p = geom.panels[0];
    assert.equal(p.panelId, 'two-person-boundary-panel');
    assert.equal(p.panelWidth, 1080);
    assert.equal(p.panelHeight, 1920);
    assert.equal(p.panelLeft, 0);
    assert.equal(p.panelTop, 0);
    assert.equal(p.speakerLabel, 'Both Participants (Fixed Outer Boundary)');
    assert.ok(p.framing.scaledW > 0);
    assert.ok(p.framing.scaledH > 0);
  });

  await t.test('12. getOutputPreviewGeometry handles shot-specific states: a_only, b_only, unknown_review', () => {
    const regions = [
      { id: 'area-1', label: 'Speaker 1', x: 0.1, y: 0.1, width: 0.35, height: 0.8, color: '#3b82f6' },
      { id: 'area-2', label: 'Speaker 2', x: 0.55, y: 0.1, width: 0.35, height: 0.8, color: '#a855f7' },
    ];

    // a_only
    const geomA = getOutputPreviewGeometry('a_only', regions, 1080, 1920, 1920, 1080);
    assert.equal(geomA.panels.length, 1);
    assert.equal(geomA.panels[0].speakerLabel, 'Speaker 1');
    assert.equal(geomA.panels[0].panelWidth, 1080);

    // b_only
    const geomB = getOutputPreviewGeometry('b_only', regions, 1080, 1920, 1920, 1080);
    assert.equal(geomB.panels.length, 1);
    assert.equal(geomB.panels[0].speakerLabel, 'Speaker 2');
    assert.equal(geomB.panels[0].panelWidth, 1080);

    // unknown_review (safe fallback centered frame)
    const geomUnk = getOutputPreviewGeometry('unknown_review', regions, 1080, 1920, 1920, 1080);
    assert.equal(geomUnk.panels.length, 1);
    assert.equal(geomUnk.panels[0].panelId, 'unknown-review-panel');
    assert.equal(geomUnk.panels[0].speakerLabel, 'Unknown Visibility (Safe Fallback)');
    assert.equal(geomUnk.panels[0].panelWidth, 1080);
    assert.ok(geomUnk.overallWarning !== null && geomUnk.overallWarning.includes('Review warning'));
  });

  await t.test('13. calculatePanelFraming correctly handles odd-pixel dimensions and rounding', () => {
    // Odd pixel rect: width = 333px in 1920 frame
    const oddRect = { x: 101 / 1920, y: 51 / 1080, width: 333 / 1920, height: 555 / 1080 };
    const framing = calculatePanelFraming(oddRect, 540, 1920, 1920, 1080);

    assert.ok(Number.isFinite(framing.scaledW));
    assert.ok(Number.isFinite(framing.scaledH));
    assert.ok(framing.padX >= 0);
    assert.ok(framing.padY >= 0);
    // Even-pixel aligned crop dimensions
    assert.equal(framing.cropW, 332);
    assert.equal(framing.cropH, 554);
  });
});


