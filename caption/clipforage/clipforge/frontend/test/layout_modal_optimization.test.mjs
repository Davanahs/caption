import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('Layout Modal UX Optimization Contract', async (t) => {
  const layoutSelectorPath = path.resolve(__dirname, '../components/automation/LayoutPreviewSelector.tsx');
  const automationPagePath = path.resolve(__dirname, '../app/automation/page.tsx');

  const layoutSelectorSource = fs.readFileSync(layoutSelectorPath, 'utf8');
  const automationPageSource = fs.readFileSync(automationPagePath, 'utf8');

  await t.test('1. Layout card thumbnails are reduced for compact laptop display (maxHeight <= 100px)', () => {
    // Assert thumbnail preview maxHeight is <= 100px
    const maxHeightMatches = [...layoutSelectorSource.matchAll(/maxHeight:\s*(\d+)/g)];
    assert.ok(maxHeightMatches.length >= 6, 'Must define preview maxHeight on all 6 options');
    for (const match of maxHeightMatches) {
      const height = parseInt(match[1], 10);
      assert.ok(height <= 100, `Thumbnail maxHeight (${height}px) must be <= 100px (reduced from original 188px)`);
    }
  });

  await t.test('2. Layout card preview container height is compact (<= 110px)', () => {
    const containerHeightMatch = layoutSelectorSource.match(/height:\s*(\d+),\s*marginBottom:\s*\d+,\s*overflow:\s*'hidden'/);
    assert.ok(containerHeightMatch, 'Preview container height must be defined');
    const containerHeight = parseInt(containerHeightMatch[1], 10);
    assert.ok(containerHeight <= 110, `Preview container height (${containerHeight}px) must be <= 110px`);
  });

  await t.test('3. Modal footprint is reduced (maxWidth <= 780px, down from 980px)', () => {
    assert.ok(!automationPageSource.includes('maxWidth: 980'), 'Old 980px maxWidth must be removed');
    assert.ok(automationPageSource.includes('maxWidth: 760'), 'Modal must have compact maxWidth of 760px');
  });

  await t.test('4. Modal maxHeight fits standard 1366x768 screens without overflow (<= 720px)', () => {
    assert.ok(
      automationPageSource.includes("maxHeight: 'min(96vh, 720px)'"),
      'Modal must clamp maxHeight to fit comfortably within 768px laptop viewports'
    );
  });

  await t.test('5. Modal overlay is decoupled from animate-fade-up containing block', () => {
    // Ensure animate-fade-up div closes before modal definitions
    const fadeUpCloseIdx = automationPageSource.indexOf('</div>\n    </div>\n\n      {/* ── Modal: Edit Channel');
    assert.ok(fadeUpCloseIdx !== -1, 'animate-fade-up container must close before fixed modal overlays');
  });

  await t.test('6. All 6 layout options, action buttons, and form controls are preserved', () => {
    const requiredOptions = ['center_crop', 'fill_blur', 'split_screen', 'multi_split', 'stacked_16_9', 'creative_transform'];
    for (const opt of requiredOptions) {
      assert.ok(layoutSelectorSource.includes(`id: '${opt}'`), `Must preserve layout option ${opt}`);
    }

    assert.ok(automationPageSource.includes('Save Profile Defaults'), 'Must preserve "Save Profile Defaults" button');
    assert.ok(automationPageSource.includes('Cancel'), 'Must preserve "Cancel" button');
    assert.ok(automationPageSource.includes('Min Duration'), 'Must preserve "Min Duration" slider');
    assert.ok(automationPageSource.includes('Max Duration'), 'Must preserve "Max Duration" slider');
    assert.ok(automationPageSource.includes('Clips Count'), 'Must preserve "Clips Count" slider');
    assert.ok(automationPageSource.includes('Duration Mode'), 'Must preserve "Duration Mode" select');
    assert.ok(automationPageSource.includes('Segmentation Strategy'), 'Must preserve "Segmentation Strategy" select');
    assert.ok(automationPageSource.includes('Scoring Mode'), 'Must preserve "Scoring Mode" select');
  });
});
