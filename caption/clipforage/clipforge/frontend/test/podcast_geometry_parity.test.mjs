import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  calculateSideBySideParticipantCrop,
  getOutputPreviewGeometry,
} from '../lib/podcastCoordinates.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const goldenVectorsPath = path.resolve(__dirname, '../../docs/engineering/podcast_geometry_golden_vectors.json');

test('Frontend/Backend Crop Geometry Parity against Golden Vectors', async (t) => {
  assert.ok(fs.existsSync(goldenVectorsPath), `Golden vectors file must exist at ${goldenVectorsPath}`);
  const rawData = fs.readFileSync(goldenVectorsPath, 'utf-8');
  const fixture = JSON.parse(rawData);
  const vectors = fixture.vectors;

  assert.ok(vectors.length >= 18, `Expected at least 18 golden vectors, found ${vectors.length}`);

  for (const v of vectors) {
    await t.test(`Golden Vector: ${v.id} - ${v.description}`, () => {
      const inp = v.input;
      const exp = v.expected;

      const actual = calculateSideBySideParticipantCrop(
        inp.region,
        inp.src_w,
        inp.src_h,
        inp.face_box,
        inp.dest_panel_w,
        inp.dest_panel_h
      );

      // 1. Exact pixel bounds parity with Python backend
      assert.equal(actual.x, exp.x, `[${v.id}] crop x must match`);
      assert.equal(actual.y, exp.y, `[${v.id}] crop y must match`);
      assert.equal(actual.w, exp.w, `[${v.id}] crop w must match`);
      assert.equal(actual.h, exp.h, `[${v.id}] crop h must match`);

      // 2. Even dimensions for video codecs
      assert.equal(actual.x % 2, 0, `[${v.id}] crop x must be even`);
      assert.equal(actual.y % 2, 0, `[${v.id}] crop y must be even`);
      assert.equal(actual.w % 2, 0, `[${v.id}] crop w must be even`);
      assert.equal(actual.h % 2, 0, `[${v.id}] crop h must be even`);

      // 3. Containment within source bounds
      const maxSrcW = Math.floor(inp.src_w / 2) * 2;
      const maxSrcH = Math.floor(inp.src_h / 2) * 2;
      assert.ok(actual.x >= 0, `[${v.id}] crop x must be non-negative`);
      assert.ok(actual.x + actual.w <= maxSrcW, `[${v.id}] crop must fit horizontally`);
      assert.ok(actual.y >= 0, `[${v.id}] crop y must be non-negative`);
      assert.ok(actual.y + actual.h <= maxSrcH, `[${v.id}] crop must fit vertically`);

      // 4. Destination panel framing & padding parity
      assert.equal(actual.scaled_w, exp.scaled_w, `[${v.id}] scaled_w must match`);
      assert.equal(actual.scaled_h, exp.scaled_h, `[${v.id}] scaled_h must match`);
      assert.equal(actual.pad_x, exp.pad_x, `[${v.id}] pad_x must match`);
      assert.equal(actual.pad_y, exp.pad_y, `[${v.id}] pad_y must match`);
      assert.ok(Math.abs(actual.scale_factor - exp.scale_factor) < 1e-5, `[${v.id}] scale_factor must match`);

      // 5. FFmpeg filter string parity
      assert.equal(actual.ffmpeg_crop, exp.ffmpeg_crop, `[${v.id}] ffmpeg_crop must match`);
      assert.equal(actual.ffmpeg_filter, exp.ffmpeg_filter, `[${v.id}] ffmpeg_filter must match`);
      assert.ok(actual.ffmpeg_crop.includes(':exact=1'), `[${v.id}] ffmpeg_crop must contain exact=1`);
    });
  }

  await t.test('OutputPreviewGeometry side_by_side composition uses exact panel framing', () => {
    const regions = [
      { id: 'area-1', label: 'Speaker 1', x: 0.1, y: 0.1, width: 0.3, height: 0.8, color: '#3b82f6' },
      { id: 'area-2', label: 'Speaker 2', x: 0.6, y: 0.1, width: 0.3, height: 0.8, color: '#a855f7' },
    ];
    const geom = getOutputPreviewGeometry('side_by_side', regions, 1080, 1920, 1920, 1080);
    assert.equal(geom.composition, 'side_by_side');
    assert.equal(geom.panels.length, 2);

    const pA = geom.panels[0];
    const pB = geom.panels[1];

    // Half width panels (540x1920)
    assert.equal(pA.panelWidth, 540);
    assert.equal(pA.panelHeight, 1920);
    assert.equal(pB.panelWidth, 540);
    assert.equal(pB.panelHeight, 1920);

    // Framing values must match calculateSideBySideParticipantCrop
    const expCropA = calculateSideBySideParticipantCrop(regions[0], 1920, 1080, null, 540, 1920);
    assert.equal(pA.framing.cropW, expCropA.w);
    assert.equal(pA.framing.cropH, expCropA.h);
    assert.equal(pA.framing.cropX, expCropA.x);
    assert.equal(pA.framing.cropY, expCropA.y);
    assert.equal(pA.framing.scaledW, expCropA.scaled_w);
    assert.equal(pA.framing.scaledH, expCropA.scaled_h);
    assert.equal(pA.framing.padX, expCropA.pad_x);
    assert.equal(pA.framing.padY, expCropA.pad_y);
  });
});
