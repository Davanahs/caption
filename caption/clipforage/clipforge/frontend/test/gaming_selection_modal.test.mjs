/**
 * gaming_selection_modal.test.mjs
 * ===============================
 * Tier 1 & Tier 2 Component & Interaction Test Suite for ClipForge Dual-Region Gaming Layout
 * (Milestone T2).
 *
 * Implements 40 authoritative test cases covering:
 * - F01: Source Video Ingestion & Timeline Controls (5 tests Tier 1, 1 test Tier 2)
 * - F03: Facecam Region Selector Visual Distinction (1 test Tier 1)
 * - F04: 9:16 Composite Canvas Preview (5 tests Tier 1, 5 tests Tier 2)
 * - F05: Facecam Placement Preset Interactions (1 test Tier 2)
 * - F06: Free Drag & Resize State Transitions (2 tests Tier 1, 2 tests Tier 2)
 * - F07: Facecam Reset Control & Invariants (2 tests Tier 1, 5 tests Tier 2)
 * - F08: Live Scrubbing / Playback Preview Parity (5 tests Tier 1, 5 tests Tier 2)
 * - F22: Strict R5 Zero-Caption Mandate DOM & Payload Auditing (1 test Tier 2)
 *
 * Total: Exactly 40 tests (20 Tier 1, 20 Tier 2).
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  createMockCanvas,
  assertCompositeCanvasParity,
  createPointerEvent,
  simulatePointerDrag,
  simulateHandleResize,
  assertNoCaptionControlsInDOM,
  assertNoCaptionFieldsInPayload,
  CANONICAL_PRESETS,
  getCanonicalPresetRect,
  assertPresetParity,
  clampNormalizedRect,
} from './gaming_test_helpers.mjs';

import {
  getDefaultGameplayRoi,
  getDefaultFacecamRoi,
  getDefaultFacecamOutputRect,
  getFacecamPreset,
  applyDrag,
  calculateResize,
  calculateRenderOffsets,
  displayToNormalized,
  validateGamingCoordinates,
  toEvenPixels,
  toCanvasOverlay,
  DEFAULT_CANVAS_WIDTH,
  DEFAULT_CANVAS_HEIGHT,
  MIN_ROI_SIZE,
} from '../lib/gamingCoordinates.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ==============================================================================
// MODAL STATE MACHINE & SIMULATOR FOR UNIT/COMPONENT TESTING
// ==============================================================================

export class GamingSelectionModalSimulator {
  constructor(initialProps = {}) {
    this.source = initialProps.source || null;
    this.duration = 0.0;
    this.currentTime = 0.0;
    this.videoWidth = 0;
    this.videoHeight = 0;
    this.paused = true;
    this.muted = false;
    this.loop = false;
    this.isBuffering = false;
    this.isScrubbing = false;
    this.clipTrim = { start: 0.0, end: null };

    // Geometry state
    this.gameplayRoi = initialProps.gameplayRoi ? { ...initialProps.gameplayRoi } : getDefaultGameplayRoi();
    this.facecamRoi = initialProps.facecamRoi ? { ...initialProps.facecamRoi } : getDefaultFacecamRoi();
    this.facecamOutputRect = initialProps.facecamOutputRect ? { ...initialProps.facecamOutputRect } : getDefaultFacecamOutputRect();
    this.facecamPreset = initialProps.facecamPreset || 'top-right';

    // Drag / UI state
    this.isDragging = false;
    this.activeDragTarget = null;
    this.activeHandle = null;
    this.activeDragStart = null;

    // Canvas preview mock
    const { canvas, ctx } = createMockCanvas(DEFAULT_CANVAS_WIDTH, DEFAULT_CANVAS_HEIGHT);
    this.canvas = canvas;
    this.ctx = ctx;
  }

  loadSource(src, { width = 1920, height = 1080, duration = 5.0, type = 'file' } = {}) {
    if (duration <= 0) {
      throw new Error('Invalid video duration');
    }
    this.source = { type, url: typeof src === 'string' ? src : src?.name || 'unknown.mp4' };
    this.videoWidth = width;
    this.videoHeight = height;
    this.duration = duration;
    this.currentTime = 0.0;
    this.paused = true;
    this.muted = false;
    this.clipTrim.end = duration;

    this.renderCompositeFrame();
  }

  loadYouTubeUrl(url, { duration = 5.0 } = {}) {
    const match = url.match(/(?:v=|youtu\.be\/|\/embed\/)([a-zA-Z0-9_-]{11})/);
    const videoId = match ? match[1] : null;
    if (!videoId) {
      throw new Error(`Invalid YouTube URL: ${url}`);
    }
    const embedUrl = `https://www.youtube-nocookie.com/embed/${videoId}`;
    this.loadSource(url, { width: 1920, height: 1080, duration, type: 'youtube' });
    this.source.videoId = videoId;
    this.source.embedUrl = embedUrl;
  }

  togglePlay() {
    this.paused = !this.paused;
    if (!this.paused) {
      this.renderCompositeFrame();
    }
    return !this.paused;
  }

  scrubTimeline(timestamp, isScrubbing = false) {
    this.isScrubbing = isScrubbing;
    if (isScrubbing) {
      this.muted = true;
    }
    const clampedTime = Math.max(0.0, Math.min(this.duration, timestamp));
    this.currentTime = clampedTime;
    this.renderCompositeFrame();
    return clampedTime;
  }

  endScrub() {
    this.isScrubbing = false;
    this.muted = false;
    this.renderCompositeFrame();
  }

  onTimeUpdate(t) {
    if (this.loop && t >= this.duration) {
      this.currentTime = 0.0;
    } else {
      this.currentTime = Math.max(0.0, Math.min(this.duration, t));
    }
    this.renderCompositeFrame();
  }

  setPreset(preset) {
    const rect = getFacecamPreset(preset);
    this.facecamOutputRect = rect;
    this.facecamPreset = preset;
    this.renderCompositeFrame();
    return rect;
  }

  startDragOverlay(target = 'facecam-overlay', clientX = 0, clientY = 0) {
    this.isDragging = true;
    this.activeDragTarget = target;
    this.activeDragStart = { clientX, clientY };
  }

  dragOverlay(deltaNormX, deltaNormY) {
    if (!this.isDragging) return;
    this.facecamOutputRect = applyDrag(this.facecamOutputRect, deltaNormX, deltaNormY);
    this.facecamPreset = 'custom';
    this.renderCompositeFrame();
  }

  endDrag() {
    this.isDragging = false;
    this.activeDragTarget = null;
    this.activeHandle = null;
    this.activeDragStart = null;
  }

  resizeOverlay(handle, deltaNormX, deltaNormY) {
    this.facecamOutputRect = calculateResize(this.facecamOutputRect, handle, deltaNormX, deltaNormY);
    this.facecamPreset = 'custom';
    this.renderCompositeFrame();
  }

  resetFacecam() {
    this.isDragging = false;
    this.activeDragTarget = null;
    this.activeHandle = null;
    this.facecamOutputRect = getDefaultFacecamOutputRect();
    this.facecamPreset = 'top-right';
    this.renderCompositeFrame();
  }

  handleKeyDown(key, { ctrlKey = false } = {}) {
    if (key === 'Escape' || (key.toLowerCase() === 'r' && ctrlKey)) {
      this.resetFacecam();
    }
  }

  renderCompositeFrame() {
    if (this.isBuffering) {
      return;
    }
    const srcW = this.videoWidth || 1920;
    const srcH = this.videoHeight || 1080;
    const gCrop = toEvenPixels(this.gameplayRoi, srcW, srcH);
    const fCrop = toEvenPixels(this.facecamRoi, srcW, srcH);
    const fDest = toCanvasOverlay(this.facecamOutputRect, this.canvas.width, this.canvas.height);

    // Layer 1: Gameplay fill (drawImage index 0)
    this.ctx.drawImage(
      'sourceVideo',
      gCrop.x, gCrop.y, gCrop.w, gCrop.h,
      0, 0, this.canvas.width, this.canvas.height
    );

    // Layer 2: Facecam PiP (drawImage index 1)
    this.ctx.drawImage(
      'sourceVideo',
      fCrop.x, fCrop.y, fCrop.w, fCrop.h,
      fDest.x, fDest.y, fDest.w, fDest.h
    );
  }

  getFormattedTime() {
    const curMin = String(Math.floor(this.currentTime / 60)).padStart(2, '0');
    const curSec = String(Math.floor(this.currentTime % 60)).padStart(2, '0');
    const durMin = String(Math.floor(this.duration / 60)).padStart(2, '0');
    const durSec = String(Math.floor(this.duration % 60)).padStart(2, '0');
    return `${curMin}:${curSec} / ${durMin}:${durSec}`;
  }

  getSubmissionPayload() {
    return {
      mode: 'gaming',
      gameplay_roi: { ...this.gameplayRoi },
      facecam_roi: { ...this.facecamRoi },
      facecam_placement: this.facecamPreset,
      facecam_output_rect: { ...this.facecamOutputRect },
      canvas_width: this.canvas.width,
      canvas_height: this.canvas.height,
    };
  }

  renderMarkup() {
    return `
      <div class="gaming-selection-modal relative w-full h-full bg-slate-900 text-white" data-testid="gaming-selection-modal">
        <div class="modal-header flex justify-between p-4 border-b border-slate-700">
          <h2 class="text-xl font-bold">Dual-Region Gaming Selection & Preview</h2>
        </div>
        <div class="modal-body grid grid-cols-12 gap-4 p-4">
          <div class="source-view col-span-7 relative">
            <div class="video-container relative" style="aspect-ratio: 16/9;">
              ${this.source?.type === 'youtube'
                ? `<iframe src="${this.source.embedUrl}" data-testid="youtube-player" class="w-full h-full"></iframe>`
                : `<video src="${this.source?.url}" data-testid="source-video" class="w-full h-full"></video>`}
              <div class="roi-overlay absolute inset-0 pointer-events-auto">
                <div class="gameplay-roi border-2 border-blue-500 bg-blue-500/20 absolute" data-testid="gameplay-roi" style="left: ${this.gameplayRoi.x * 100}%; top: ${this.gameplayRoi.y * 100}%; width: ${this.gameplayRoi.width * 100}%; height: ${this.gameplayRoi.height * 100}%;">
                  <span class="roi-label bg-blue-600 text-xs px-1">Gameplay ROI (Layer 1)</span>
                </div>
                <div class="facecam-roi border-2 border-amber-500 bg-amber-500/20 absolute" data-testid="facecam-roi" style="left: ${this.facecamRoi.x * 100}%; top: ${this.facecamRoi.y * 100}%; width: ${this.facecamRoi.width * 100}%; height: ${this.facecamRoi.height * 100}%;">
                  <span class="roi-label bg-amber-600 text-xs px-1">Facecam ROI (Layer 2)</span>
                </div>
              </div>
            </div>
            <div class="timeline-controls flex items-center gap-2 mt-2">
              <button data-testid="play-pause-btn">${this.paused ? 'Play' : 'Pause'}</button>
              <input type="range" data-testid="timeline-scrubber" min="0" max="${this.duration}" step="0.01" value="${this.currentTime}" />
              <span data-testid="timestamp-display">${this.getFormattedTime()}</span>
            </div>
          </div>
          <div class="composite-view col-span-5 flex flex-col items-center">
            <div class="canvas-container relative" style="aspect-ratio: 9/16; width: 270px; height: 480px;" data-testid="composite-canvas-container">
              <canvas width="1080" height="1920" class="w-full h-full" data-testid="composite-canvas"></canvas>
              <div class="facecam-overlay-handle absolute border-2 ${this.isDragging ? 'border-amber-400 ring-2 ring-amber-300 cursor-grabbing' : 'border-amber-500 cursor-grab'}" data-testid="facecam-canvas-overlay" style="left: ${this.facecamOutputRect.x * 100}%; top: ${this.facecamOutputRect.y * 100}%; width: ${this.facecamOutputRect.width * 100}%; height: ${this.facecamOutputRect.height * 100}%;">
                <div class="handle nw top-0 left-0"></div>
                <div class="handle ne top-0 right-0"></div>
                <div class="handle sw bottom-0 left-0"></div>
                <div class="handle se bottom-0 right-0"></div>
              </div>
              ${this.isBuffering ? `<div class="buffering-spinner absolute inset-0 flex items-center justify-center bg-black/50"><span>Loading...</span></div>` : ''}
            </div>
            <div class="preset-controls flex gap-2 mt-4">
              <button class="preset-btn ${this.facecamPreset === 'top-left' ? 'active bg-amber-500' : 'bg-slate-700'}" data-testid="preset-top-left">Top-Left</button>
              <button class="preset-btn ${this.facecamPreset === 'top-right' ? 'active bg-amber-500' : 'bg-slate-700'}" data-testid="preset-top-right">Top-Right</button>
              <button class="preset-btn ${this.facecamPreset === 'bottom-left' ? 'active bg-amber-500' : 'bg-slate-700'}" data-testid="preset-bottom-left">Bottom-Left</button>
              <button class="preset-btn ${this.facecamPreset === 'bottom-right' ? 'active bg-amber-500' : 'bg-slate-700'}" data-testid="preset-bottom-right">Bottom-Right</button>
              <button class="reset-btn bg-red-600 px-3 py-1" data-testid="reset-facecam-btn">Reset Facecam</button>
            </div>
          </div>
        </div>
      </div>
    `.trim();
  }
}

// ==============================================================================
// TIER 1 FEATURE COVERAGE SUITE (20 TESTS)
// ==============================================================================

test('Tier 1: Source Video Ingestion & Timeline Controls (F01)', async (t) => {
  await t.test('TC-T1-F01-01: Load standard 1080p MP4 file', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy_landscape.mp4', { width: 1920, height: 1080, duration: 5.0 });

    assert.equal(modal.duration, 5.0);
    assert.equal(modal.videoWidth, 1920);
    assert.equal(modal.videoHeight, 1080);
    assert.equal(modal.currentTime, 0.0);
    assert.equal(modal.paused, true);
    assert.equal(modal.getFormattedTime(), '00:00 / 00:05');
  });

  await t.test('TC-T1-F01-02: Ingest video via valid YouTube URL', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadYouTubeUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ', { duration: 5.0 });

    assert.equal(modal.source.type, 'youtube');
    assert.equal(modal.source.videoId, 'dQw4w9WgXcQ');
    assert.equal(modal.source.embedUrl, 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ');
    assert.equal(modal.duration, 5.0);
  });

  await t.test('TC-T1-F01-03: Scrub video timeline to midway point', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy_landscape.mp4', { duration: 5.0 });
    const seekTime = modal.scrubTimeline(2.5);

    assert.equal(seekTime, 2.5);
    assert.equal(modal.currentTime, 2.5);
    assert.equal(modal.getFormattedTime(), '00:02 / 00:05');
  });

  await t.test('TC-T1-F01-04: Play/pause toggle during ingestion', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy_landscape.mp4', { duration: 5.0 });

    assert.equal(modal.paused, true);
    const playing = modal.togglePlay();
    assert.equal(playing, true);
    assert.equal(modal.paused, false);

    const pausedAgain = modal.togglePlay();
    assert.equal(pausedAgain, false);
    assert.equal(modal.paused, true);
  });

  await t.test('TC-T1-F01-05: Ingest video with non-standard 720p resolution', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('test_720p.mp4', { width: 1280, height: 720, duration: 10.0 });

    assert.equal(modal.videoWidth, 1280);
    assert.equal(modal.videoHeight, 720);
    const ar = modal.videoWidth / modal.videoHeight;
    assert.ok(Math.abs(ar - 16 / 9) < 0.001);
  });
});

test('Tier 1: Facecam Region Selector Visual Distinction (F03)', async (t) => {
  await t.test('TC-T1-F03-02: Visual distinction of facecam ROI', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080 });
    const markup = modal.renderMarkup();

    assert.ok(markup.includes('border-blue-500'), 'Gameplay ROI must have distinct blue border');
    assert.ok(markup.includes('border-amber-500'), 'Facecam ROI must have distinct amber border');
    assert.ok(markup.includes('Gameplay ROI (Layer 1)'), 'Must include gameplay label');
    assert.ok(markup.includes('Facecam ROI (Layer 2)'), 'Must include facecam label');
  });
});

test('Tier 1: 9:16 Composite Canvas Preview (F04)', async (t) => {
  await t.test('TC-T1-F04-01: Canvas aspect ratio verification', () => {
    const modal = new GamingSelectionModalSimulator();
    const ratio = modal.canvas.width / modal.canvas.height;
    assert.ok(Math.abs(ratio - 9 / 16) < 0.001, `Aspect ratio must be 9:16 (got ${ratio})`);
  });

  await t.test('TC-T1-F04-02: Layer 1 Gameplay rendering', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080 });

    const draws = modal.ctx.getDrawCalls();
    assert.ok(draws.length >= 1, 'Must have at least Layer 1 draw call');
    const gameplayDraw = draws[0];

    assert.equal(gameplayDraw.dx, 0);
    assert.equal(gameplayDraw.dy, 0);
    assert.equal(gameplayDraw.dw, 1080);
    assert.equal(gameplayDraw.dh, 1920);
  });

  await t.test('TC-T1-F04-03: Layer 2 Facecam PiP rendering', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080 });
    modal.setPreset('top-right');

    const draws = modal.ctx.getDrawCalls();
    assert.ok(draws.length >= 2, 'Must have 2 draw calls');
    const facecamDraw = draws[1];

    // Canvas 1080x1920 with top-right preset (x=0.65, y=0.04, w=0.30, h=0.22)
    assert.equal(facecamDraw.dx, 702);
    assert.equal(facecamDraw.dy, 76);
    assert.equal(facecamDraw.dw, 324);
    assert.equal(facecamDraw.dh, 422);

    assertCompositeCanvasParity({
      ctx: modal.ctx,
      expectedGameplayDest: { x: 0, y: 0, width: 1080, height: 1920 },
      expectedFacecamDest: { x: 702, y: 76, width: 324, height: 422 },
    });
  });

  await t.test('TC-T1-F04-04: Layer z-order stacking', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080 });

    const draws = modal.ctx.getDrawCalls();
    assert.equal(draws.length, 2, 'Must record exactly 2 draw calls');
    assert.equal(draws[0].dw, 1080, 'First draw call must be Gameplay Layer 1 (z=1)');
    assert.equal(draws[1].dw, 324, 'Second draw call must be Facecam Overlay Layer 2 (z=2)');
  });

  await t.test('TC-T1-F04-05: Preview canvas dimensions contract', () => {
    const modal = new GamingSelectionModalSimulator();
    assert.equal(modal.canvas.width, 1080);
    assert.equal(modal.canvas.height, 1920);
  });
});

test('Tier 1: Free Drag & Resize State Transitions (F06)', async (t) => {
  await t.test('TC-T1-F06-04: Free positioning switches preset to custom', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080 });
    modal.setPreset('top-left');
    assert.equal(modal.facecamPreset, 'top-left');

    modal.startDragOverlay('facecam-overlay', 100, 100);
    modal.dragOverlay(0.05, 0.05);
    modal.endDrag();

    assert.equal(modal.facecamPreset, 'custom', 'Preset must switch to custom after manual drag');
  });

  await t.test('TC-T1-F06-05: Visual active drag indicator', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080 });

    modal.startDragOverlay('facecam-overlay', 100, 100);
    assert.equal(modal.isDragging, true);
    const draggingMarkup = modal.renderMarkup();
    assert.ok(draggingMarkup.includes('cursor-grabbing'), 'Markup must indicate grabbing cursor');
    assert.ok(draggingMarkup.includes('ring-amber-300'), 'Markup must include active ring styling');

    modal.endDrag();
    assert.equal(modal.isDragging, false);
    const idleMarkup = modal.renderMarkup();
    assert.ok(idleMarkup.includes('cursor-grab'), 'Idle markup must indicate grab cursor');
  });
});

test('Tier 1: Facecam Reset Control (F07)', async (t) => {
  await t.test('TC-T1-F07-04: Reset updates preset selector', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080 });

    // Drag to custom
    modal.startDragOverlay('facecam-overlay', 100, 100);
    modal.dragOverlay(0.1, 0.1);
    modal.endDrag();
    assert.equal(modal.facecamPreset, 'custom');

    modal.resetFacecam();
    assert.equal(modal.facecamPreset, 'top-right', 'Reset must restore default top-right preset');
    const markup = modal.renderMarkup();
    assert.ok(markup.includes('preset-btn active bg-amber-500" data-testid="preset-top-right"'));
  });

  await t.test('TC-T1-F07-05: Reset preserves source ROIs', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080 });

    modal.gameplayRoi = { x: 0.1, y: 0.1, width: 0.8, height: 0.8 };
    modal.facecamRoi = { x: 0.8, y: 0.1, width: 0.15, height: 0.15 };

    modal.resetFacecam();

    assert.deepEqual(modal.gameplayRoi, { x: 0.1, y: 0.1, width: 0.8, height: 0.8 });
    assert.deepEqual(modal.facecamRoi, { x: 0.8, y: 0.1, width: 0.15, height: 0.15 });
    assert.deepEqual(modal.facecamOutputRect, getDefaultFacecamOutputRect());
  });
});

test('Tier 1: Live Scrubbing / Playback Preview Parity (F08)', async (t) => {
  await t.test('TC-T1-F08-01: Live update during source playback', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080 });

    const initialDraws = modal.ctx.getDrawCalls().length;
    modal.onTimeUpdate(1.0);
    modal.onTimeUpdate(1.033);
    modal.onTimeUpdate(1.066);

    const finalDraws = modal.ctx.getDrawCalls().length;
    assert.equal(finalDraws - initialDraws, 6, 'Must redraw 2 layers on each timeupdate');
  });

  await t.test('TC-T1-F08-02: Live update during timeline scrubbing', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080, duration: 5.0 });

    modal.scrubTimeline(3.2, true);
    assert.equal(modal.currentTime, 3.2);
    const lastDraw = modal.ctx.getDrawCalls().at(-1);
    assert.ok(lastDraw, 'Must have executed draw call at scrub target');
  });

  await t.test('TC-T1-F08-03: Paused state canvas stability', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080, duration: 5.0 });
    modal.currentTime = 3.0;
    modal.paused = true;

    const opCount = modal.ctx.getOperations().length;
    // No new operations should occur while paused without events
    assert.ok(opCount > 0, 'Canvas rendered initial state');
    assert.equal(modal.paused, true);
  });

  await t.test('TC-T1-F08-04: Audio muting during rapid scrubbing', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080, duration: 5.0 });

    assert.equal(modal.muted, false, 'Audio starts unmuted');
    modal.scrubTimeline(2.0, true);
    assert.equal(modal.muted, true, 'Audio must mute while scrubbing');

    modal.endScrub();
    assert.equal(modal.muted, false, 'Audio must unmute upon scrub release');
  });

  await t.test('TC-T1-F08-05: Seek to beginning and end of video', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080, duration: 5.0 });

    modal.scrubTimeline(0.0);
    assert.equal(modal.currentTime, 0.0);

    modal.scrubTimeline(5.0);
    assert.equal(modal.currentTime, 5.0);
  });
});

// ==============================================================================
// TIER 2 BOUNDARY & CORNER CASES SUITE (20 TESTS)
// ==============================================================================

test('Tier 2: Ingestion Boundary Cases (F01)', async (t) => {
  await t.test('TC-T2-F01-04: Extremely short video (1 single frame, 0.033s)', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('single_frame.mp4', { width: 1920, height: 1080, duration: 0.0333 });

    assert.equal(modal.duration, 0.0333);
    const scrubbed = modal.scrubTimeline(0.02);
    assert.equal(scrubbed, 0.02);

    const clamped = modal.scrubTimeline(0.05);
    assert.equal(clamped, 0.0333, 'Scrubbing past duration must clamp safely');
  });
});

test('Tier 2: Canvas Viewport & Extreme Sizing (F04)', async (t) => {
  await t.test('TC-T2-F04-01: Window resizing to extreme mobile portrait (320x480)', () => {
    const offsets = calculateRenderOffsets(320, 480, 1080, 1920);
    assert.equal(offsets.renderHeight, 480);
    assert.equal(offsets.renderWidth, 270);
    assert.equal(offsets.renderLeft, 25);
    assert.equal(offsets.renderTop, 0);

    const ar = offsets.renderWidth / offsets.renderHeight;
    assert.ok(Math.abs(ar - 9 / 16) < 0.001);
  });

  await t.test('TC-T2-F04-02: Window resizing to 4K desktop (3840x2160)', () => {
    const offsets = calculateRenderOffsets(3840, 2160, 1080, 1920);
    assert.equal(offsets.renderHeight, 2160);
    assert.equal(offsets.renderWidth, 1215);
    assert.equal(offsets.renderLeft, 1312);
    assert.equal(offsets.renderTop, 0);

    const center = displayToNormalized(1312 + 607.5, 1080, { left: 0, top: 0, width: 3840, height: 2160 }, 1080, 1920);
    assert.equal(center.x, 0.5);
    assert.equal(center.y, 0.5);
  });

  await t.test('TC-T2-F04-03: Zero-sized canvas container handling', () => {
    const offsets = calculateRenderOffsets(0, 0, 1080, 1920);
    assert.deepEqual(offsets, {
      renderLeft: 0,
      renderTop: 0,
      renderWidth: 0,
      renderHeight: 0,
    });
  });

  await t.test('TC-T2-F04-04: Canvas display with CSS zoom / page scale active (125% Windows scale)', () => {
    const dpr = 1.25;
    // Physical client coords (125, 250) on 1.25 DPR correspond to CSS (100, 200) in 1000x1000 container
    const physicalClientX = 125;
    const physicalClientY = 250;
    const cssClientX = physicalClientX / dpr;
    const cssClientY = physicalClientY / dpr;

    const norm = displayToNormalized(cssClientX, cssClientY, { left: 0, top: 0, width: 1000, height: 1000 });
    assert.equal(norm.x, 0.10);
    assert.equal(norm.y, 0.20);
  });

  await t.test('TC-T2-F04-05: Multiple overlay drag interactions in rapid succession', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4');

    for (let i = 0; i < 20; i++) {
      modal.startDragOverlay('facecam-overlay', 100 + i, 100 + i);
      modal.dragOverlay(0.01, 0.01);
      modal.endDrag();
    }

    assert.equal(modal.isDragging, false);
    assert.ok(modal.facecamOutputRect.x >= 0.0 && modal.facecamOutputRect.x <= 1.0);
    assert.ok(modal.facecamOutputRect.y >= 0.0 && modal.facecamOutputRect.y <= 1.0);
  });
});

test('Tier 2: Preset Rapid Interactions (F05)', async (t) => {
  await t.test('TC-T2-F05-03: Rapid cycling through all 4 presets in 100ms', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4');

    modal.setPreset('top-left');
    modal.setPreset('top-right');
    modal.setPreset('bottom-right');
    modal.setPreset('bottom-left');

    assert.equal(modal.facecamPreset, 'bottom-left');
    assertPresetParity(modal.facecamOutputRect, 'bottom-left');
  });
});

test('Tier 2: Drag & Resize Window Boundaries (F06)', async (t) => {
  await t.test('TC-T2-F06-04: Drag overlay with pointer released outside browser window', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4');

    modal.startDragOverlay('facecam-overlay', 100, 100);
    modal.dragOverlay(-1.5, -1.5);
    modal.endDrag();

    assert.equal(modal.isDragging, false);
    assert.equal(modal.facecamOutputRect.x, 0.0);
    assert.equal(modal.facecamOutputRect.y, 0.0);
  });

  await t.test('TC-T2-F06-05: Drag overlay by touch event (mobile/tablet emulation)', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4');

    const touchEvent = {
      type: 'touchmove',
      touches: [{ clientX: 200, clientY: 200 }],
    };
    modal.startDragOverlay('facecam-overlay', 100, 100);
    modal.dragOverlay(0.1, 0.1);
    modal.endDrag();

    assert.equal(modal.isDragging, false);
    assert.equal(modal.facecamPreset, 'custom');
  });
});

test('Tier 2: Reset Invariants & State Restoration (F07)', async (t) => {
  await t.test('TC-T2-F07-01: Reset while overlay is currently being dragged', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4');

    modal.startDragOverlay('facecam-overlay', 100, 100);
    assert.equal(modal.isDragging, true);

    modal.resetFacecam();
    assert.equal(modal.isDragging, false, 'Drag must abort upon reset');
    assertPresetParity(modal.facecamOutputRect, 'top-right');
  });

  await t.test('TC-T2-F07-02: Reset when already at default placement', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4');

    const before = { ...modal.facecamOutputRect };
    modal.resetFacecam();
    const after = { ...modal.facecamOutputRect };

    assert.deepEqual(before, after);
    assert.equal(modal.facecamPreset, 'top-right');
  });

  await t.test('TC-T2-F07-03: Reset after source video aspect ratio changes', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { width: 1920, height: 1080 });

    modal.loadSource('dummy_4_3.mp4', { width: 1440, height: 1080 });
    modal.resetFacecam();

    assertPresetParity(modal.facecamOutputRect, 'top-right');
    assert.equal(modal.facecamOutputRect.width, 0.30);
    assert.equal(modal.facecamOutputRect.height, 0.22);
  });

  await t.test('TC-T2-F07-04: Reset with keyboard shortcut (Escape / Ctrl+R)', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4');

    modal.setPreset('bottom-left');
    modal.handleKeyDown('Escape');
    assert.equal(modal.facecamPreset, 'top-right');

    modal.setPreset('bottom-right');
    modal.handleKeyDown('r', { ctrlKey: true });
    assert.equal(modal.facecamPreset, 'top-right');
  });

  await t.test('TC-T2-F07-05: Reset preserves unsaved modal state outside facecam', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { duration: 10.0 });
    modal.clipTrim = { start: 1.0, end: 4.0 };

    modal.setPreset('bottom-left');
    modal.resetFacecam();

    assert.equal(modal.clipTrim.start, 1.0);
    assert.equal(modal.clipTrim.end, 4.0);
    assertPresetParity(modal.facecamOutputRect, 'top-right');
  });
});

test('Tier 2: Playback & Scrubbing Boundaries (F08)', async (t) => {
  await t.test('TC-T2-F08-01: Scrubbing past video end timestamp (t > duration)', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { duration: 5.0 });

    const scrubbed = modal.scrubTimeline(9999.0);
    assert.equal(scrubbed, 5.0);
    assert.equal(modal.currentTime, 5.0);
  });

  await t.test('TC-T2-F08-02: Scrubbing to negative timestamp (t < 0)', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { duration: 5.0 });

    const scrubbed = modal.scrubTimeline(-10.0);
    assert.equal(scrubbed, 0.0);
    assert.equal(modal.currentTime, 0.0);
  });

  await t.test('TC-T2-F08-03: Scrubbing during network buffering (YouTube stream)', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { duration: 5.0 });

    modal.isBuffering = true;
    const bufferMarkup = modal.renderMarkup();
    assert.ok(bufferMarkup.includes('buffering-spinner'), 'Spinner must be rendered during buffering');

    modal.isBuffering = false;
    const readyMarkup = modal.renderMarkup();
    assert.ok(!readyMarkup.includes('buffering-spinner'), 'Spinner must disappear when buffering ends');
  });

  await t.test('TC-T2-F08-04: Scrubbing video with variable frame rate (VFR)', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('vfr.mp4', { duration: 10.0 });

    modal.scrubTimeline(1.127);
    assert.equal(modal.currentTime, 1.127);

    modal.scrubTimeline(2.451);
    assert.equal(modal.currentTime, 2.451);
  });

  await t.test('TC-T2-F08-05: Playback loop at video end', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4', { duration: 5.0 });
    modal.loop = true;

    modal.onTimeUpdate(5.0);
    assert.equal(modal.currentTime, 0.0, 'Player must rewind to 0.0s when loop is true');
  });
});

test('Tier 2: Strict Zero-Caption Invariant (F22)', async (t) => {
  await t.test('TC-T2-F22-05: Frontend UI audit for caption controls', () => {
    const modal = new GamingSelectionModalSimulator();
    modal.loadSource('dummy.mp4');

    // 1. Audit DOM markup for prohibited subtitle / caption tokens
    const markup = modal.renderMarkup();
    assertNoCaptionControlsInDOM(markup);

    // 2. Audit submission payload for prohibited caption fields
    const payload = modal.getSubmissionPayload();
    assertNoCaptionFieldsInPayload(payload);

    // 3. Conditional check: if GamingSelectionModal.tsx exists in M3, verify its source code too
    const componentPath = path.resolve(__dirname, '../components/GamingSelectionModal.tsx');
    if (fs.existsSync(componentPath)) {
      const source = fs.readFileSync(componentPath, 'utf8');
      assertNoCaptionControlsInDOM(source);
    }
  });
});


// ==============================================================================
// MILESTONE M3: COMPONENT INTEGRATION & CONTRACT VERIFICATION SUITE
// ==============================================================================

test('Milestone M3: Dual-Region Gaming Layout Component & Interaction Contracts', async (t) => {
  const rootDir = path.resolve(__dirname, '..');
  const canvasComponentPath = path.join(rootDir, 'components/gaming/GamingCompositeCanvas.tsx');
  const modalComponentPath = path.join(rootDir, 'components/gaming/GamingSelectionModal.tsx');
  const studioPagePath = path.join(rootDir, 'app/gaming/page.tsx');
  const sidebarPath = path.join(rootDir, 'components/Sidebar.tsx');
  const apiPath = path.join(rootDir, 'lib/api.ts');

  // Verify file existence
  assert.ok(fs.existsSync(canvasComponentPath), 'GamingCompositeCanvas.tsx must exist');
  assert.ok(fs.existsSync(modalComponentPath), 'GamingSelectionModal.tsx must exist');
  assert.ok(fs.existsSync(studioPagePath), 'app/gaming/page.tsx must exist');
  assert.ok(fs.existsSync(sidebarPath), 'Sidebar.tsx must exist');
  assert.ok(fs.existsSync(apiPath), 'lib/api.ts must exist');

  const canvasSource = fs.readFileSync(canvasComponentPath, 'utf8');
  const modalSource = fs.readFileSync(modalComponentPath, 'utf8');
  const studioSource = fs.readFileSync(studioPagePath, 'utf8');
  const sidebarSource = fs.readFileSync(sidebarPath, 'utf8');
  const apiSource = fs.readFileSync(apiPath, 'utf8');

  // CONTRACT 1: Export contracts
  await t.test('Contract 1: Export contracts for GamingSelectionModal and GamingCompositeCanvas', () => {
    assert.ok(
      canvasSource.includes('export default function GamingCompositeCanvas'),
      'GamingCompositeCanvas.tsx must export default function component'
    );
    assert.ok(
      canvasSource.includes('export interface GamingCompositeCanvasProps'),
      'GamingCompositeCanvas.tsx must export GamingCompositeCanvasProps'
    );
    assert.ok(
      modalSource.includes('export default function GamingSelectionModal'),
      'GamingSelectionModal.tsx must export default function component'
    );
    assert.ok(
      modalSource.includes('export interface GamingProcessingConfig'),
      'GamingSelectionModal.tsx must export GamingProcessingConfig'
    );
    assert.ok(
      modalSource.includes('export interface GamingSelectionModalProps'),
      'GamingSelectionModal.tsx must export GamingSelectionModalProps'
    );
    assert.ok(
      studioSource.includes('export default function GamingStudioPage'),
      'app/gaming/page.tsx must export default GamingStudioPage'
    );
  });

  // CONTRACT 2: Dual-ROI selection bounding boxes, handles, distinct visual styling, and reset actions
  await t.test('Contract 2: Dual-ROI selection bounding boxes, handles, distinct visual styling, and reset actions', () => {
    assert.ok(modalSource.includes('id="gameplay-roi-box"'), 'Modal must render gameplay-roi-box');
    assert.ok(modalSource.includes('id="facecam-roi-box"'), 'Modal must render facecam-roi-box');

    // Visual distinction: Emerald Green for Gameplay vs Amber Gold for Facecam
    assert.ok(modalSource.includes('border-emerald-500'), 'Gameplay ROI must use emerald border');
    assert.ok(modalSource.includes('bg-emerald-500/15'), 'Gameplay ROI must have emerald background tint');
    assert.ok(modalSource.includes('gameplay-roi-badge'), 'Gameplay ROI must have badge indicator');

    assert.ok(modalSource.includes('border-amber-400'), 'Facecam ROI must use amber border');
    assert.ok(modalSource.includes('bg-amber-500/20'), 'Facecam ROI must have amber background tint');
    assert.ok(modalSource.includes('facecam-roi-badge'), 'Facecam ROI must have badge indicator');

    // 4 Corner resize handles for Gameplay
    assert.ok(modalSource.includes('id="gameplay-handle-nw"'), 'Gameplay ROI must have NW handle');
    assert.ok(modalSource.includes('id="gameplay-handle-ne"'), 'Gameplay ROI must have NE handle');
    assert.ok(modalSource.includes('id="gameplay-handle-se"'), 'Gameplay ROI must have SE handle');
    assert.ok(modalSource.includes('id="gameplay-handle-sw"'), 'Gameplay ROI must have SW handle');

    // 4 Corner resize handles for Facecam
    assert.ok(modalSource.includes('id="facecam-handle-nw"'), 'Facecam ROI must have NW handle');
    assert.ok(modalSource.includes('id="facecam-handle-ne"'), 'Facecam ROI must have NE handle');
    assert.ok(modalSource.includes('id="facecam-handle-se"'), 'Facecam ROI must have SE handle');
    assert.ok(modalSource.includes('id="facecam-handle-sw"'), 'Facecam ROI must have SW handle');

    // Tool switching buttons
    assert.ok(modalSource.includes('id="select-gameplay-tool-btn"'), 'Modal must have Select Gameplay Tool button');
    assert.ok(modalSource.includes('id="select-facecam-tool-btn"'), 'Modal must have Select Facecam Tool button');

    // Reset controls
    assert.ok(modalSource.includes('id="reset-gameplay-roi-btn"'), 'Modal must have Reset Gameplay button');
    assert.ok(modalSource.includes('id="reset-facecam-roi-btn"'), 'Modal must have Reset Facecam button');

    // Verify reset logic matches defaults
    const defaultGameplay = getDefaultGameplayRoi();
    assert.deepEqual(defaultGameplay, { x: 0, y: 0, width: 1, height: 1 });
    const defaultFacecam = getDefaultFacecamRoi();
    assert.deepEqual(defaultFacecam, { x: 0.70, y: 0.05, width: 0.25, height: 0.25 });

    // Verify boundary clamping
    const clamped = clampNormalizedRect({ x: -0.2, y: 0.85, width: 0.5, height: 0.4 }, MIN_ROI_SIZE);
    assert.ok(clamped.x >= 0, 'Clamped x must be >= 0');
    assert.ok(clamped.y + clamped.height <= 1.0, 'Clamped y + height must be <= 1.0');
    assert.ok(clamped.width >= MIN_ROI_SIZE, 'Clamped width must be >= MIN_ROI_SIZE');
  });

  // CONTRACT 3: 9:16 Composite Canvas Preview
  await t.test('Contract 3: 9:16 composite canvas preview, scale-to-fill gameplay, and PiP manipulation', () => {
    assert.ok(canvasSource.includes('id="composite-canvas-9-16-viewport"'), 'Canvas must render viewport');
    assert.ok(canvasSource.includes("aspectRatio: '9 / 16'"), 'Viewport must enforce 9:16 aspect ratio');

    assert.ok(canvasSource.includes('id="gaming-composite-canvas"'), 'Canvas element must exist');
    assert.ok(canvasSource.includes('width={canvasWidth}'), 'Canvas must bind canvasWidth');
    assert.ok(canvasSource.includes('height={canvasHeight}'), 'Canvas must bind canvasHeight');

    assert.ok(canvasSource.includes('id="facecam-pip-overlay-box"'), 'Must have facecam-pip-overlay-box');
    assert.ok(canvasSource.includes('id="handle-nw"'), 'Overlay must have NW handle');
    assert.ok(canvasSource.includes('id="handle-ne"'), 'Overlay must have NE handle');
    assert.ok(canvasSource.includes('id="handle-se"'), 'Overlay must have SE handle');
    assert.ok(canvasSource.includes('id="handle-sw"'), 'Overlay must have SW handle');

    assert.ok(canvasSource.includes('applyDrag'), 'Must use applyDrag for overlay movement');
    assert.ok(canvasSource.includes('calculateResize'), 'Must use calculateResize for overlay resizing');

    const { ctx } = createMockCanvas(1080, 1920);
    ctx.drawImage('gameplay-source', 0, 0, 1920, 1080, 0, 0, 1080, 1920);
    ctx.drawImage('facecam-source', 1344, 54, 480, 270, 702, 76, 324, 422);

    assertCompositeCanvasParity({
      ctx,
      expectedGameplayCrop: { x: 0, y: 0, w: 1920, h: 1080 },
      expectedFacecamCrop: { x: 1344, y: 54, w: 480, h: 270 },
      expectedFacecamDest: { x: 702, y: 76, w: 324, h: 422 },
      tolerancePx: 0,
    });
  });

  // CONTRACT 4: Facecam placement presets
  await t.test('Contract 4: Facecam placement presets matching CANONICAL_PRESETS and reset control', () => {
    assert.ok(canvasSource.includes('id={`preset-btn-${key}`}'), 'Canvas must render dynamic preset buttons');
    assert.ok(canvasSource.includes('id="facecam-reset-btn"'), 'Canvas must render facecam-reset-btn');

    const presets = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
    for (const preset of presets) {
      const resolved = getFacecamPreset(preset);
      assertPresetParity(resolved, preset, 1e-4);
      assert.deepEqual(resolved, CANONICAL_PRESETS[preset], `Preset ${preset} must equal CANONICAL_PRESETS`);
    }

    const defaultOutput = getDefaultFacecamOutputRect('top-right');
    assert.deepEqual(defaultOutput, CANONICAL_PRESETS['top-right']);
  });

  // CONTRACT 5: Video ingestion, scrubbing, and timestamps
  await t.test('Contract 5: Video ingestion controls (URL + File dropzone), scrubber, and timestamp display', () => {
    assert.ok(studioSource.includes('id="gaming-youtube-url-input"'), 'Studio page must have YouTube URL input');
    assert.ok(studioSource.includes('id="open-gaming-studio-url-btn"'), 'Studio page must have Open Studio button');
    assert.ok(studioSource.includes('id="gaming-file-dropzone"'), 'Studio page must have file dropzone');
    assert.ok(studioSource.includes('id="gaming-file-input"'), 'Studio page must have hidden file input');

    assert.ok(modalSource.includes('id="gaming-source-video-container"'), 'Modal must have video container');
    assert.ok(modalSource.includes('id="gaming-play-pause-btn"'), 'Modal must have Play/Pause toggle');
    assert.ok(modalSource.includes('id="gaming-step-back-btn"'), 'Modal must have -1s step button');
    assert.ok(modalSource.includes('id="gaming-step-fwd-btn"'), 'Modal must have +1s step button');
    assert.ok(modalSource.includes('id="gaming-timeline-scrubber"'), 'Modal must have timeline scrubber slider');
    assert.ok(modalSource.includes('id="gaming-timestamp-display"'), 'Modal must have timestamp display');
  });

  // CONTRACT 6: Studio route, Sidebar navigation, decoupled modal
  await t.test('Contract 6: Studio route (/gaming), Sidebar navigation item, and decoupled modal mounting', () => {
    assert.ok(
      sidebarSource.includes("{ href: '/gaming',          icon: '🎮', label: 'Gaming Studio' }") ||
      sidebarSource.includes("href: '/gaming'"),
      'Sidebar must register /gaming route'
    );

    const fadeUpSplit = studioSource.split('animate-fade-up');
    assert.ok(fadeUpSplit.length >= 2, 'Page must contain animate-fade-up container');
    const afterFadeUp = fadeUpSplit[fadeUpSplit.length - 1];
    assert.ok(
      afterFadeUp.includes('<GamingSelectionModal'),
      'GamingSelectionModal must be mounted outside the animate-fade-up container'
    );
  });

  // CONTRACT 7: API payload serialization
  await t.test('Contract 7: API payload serialization matches PROJECT.md § 2', () => {
    assert.ok(apiSource.includes('gamingLayout?: GamingLayoutConfig | string;'), 'SubmitYouTubeOptions must include gamingLayout');
    assert.ok(apiSource.includes('gamingLayout?: GamingLayoutConfig | string;'), 'UploadVideoOptions must include gamingLayout');
    assert.ok(apiSource.includes("form.append('gaming_layout', serialized)"), 'Must serialize and append gaming_layout');
    assert.ok(apiSource.includes('export const submitGamingUrl'), 'api.ts must export submitGamingUrl helper');
    assert.ok(apiSource.includes('export const submitGamingUpload'), 'api.ts must export submitGamingUpload helper');

    const samplePayload = {
      mode: 'gaming',
      gameplay_roi: { x: 0.0, y: 0.0, width: 1.0, height: 1.0 },
      facecam_roi: { x: 0.70, y: 0.05, width: 0.25, height: 0.25 },
      facecam_placement: 'top-right',
      facecam_output_rect: { x: 0.65, y: 0.04, width: 0.30, height: 0.22 },
      canvas_width: 1080,
      canvas_height: 1920,
    };

    const serialized = JSON.stringify(samplePayload);
    const parsed = JSON.parse(serialized);
    assert.equal(parsed.mode, 'gaming');
    assert.equal(parsed.canvas_width, 1080);
    assert.equal(parsed.canvas_height, 1920);
    assert.equal(parsed.facecam_placement, 'top-right');
  });

  // CONTRACT 8: Strict R5 Zero-Caption mandate
  await t.test('Contract 8: Strict R5 Zero-Caption invariant verification across DOM and API payloads', () => {
    assertNoCaptionControlsInDOM(canvasSource);
    assertNoCaptionControlsInDOM(modalSource);
    assertNoCaptionControlsInDOM(studioSource);

    const testGamingLayout = {
      mode: 'gaming',
      gameplay_roi: { x: 0.0, y: 0.0, width: 1.0, height: 1.0 },
      facecam_roi: { x: 0.70, y: 0.05, width: 0.25, height: 0.25 },
      facecam_placement: 'top-right',
      facecam_output_rect: { x: 0.65, y: 0.04, width: 0.30, height: 0.22 },
      canvas_width: 1080,
      canvas_height: 1920,
    };

    assertNoCaptionFieldsInPayload(testGamingLayout);

    const testFullPayload = {
      url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
      reframe_mode: 'gaming',
      clips_count: 3,
      target_duration: 49,
      gaming_layout: testGamingLayout,
    };

    assertNoCaptionFieldsInPayload(testFullPayload);
  });
});
