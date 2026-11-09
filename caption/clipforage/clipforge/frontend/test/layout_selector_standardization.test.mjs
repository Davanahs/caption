import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('Layout Selector Standardization: Global Visual Thumbnail Selector Verification', async (t) => {
  const sharedComponentPath = path.resolve(__dirname, '../components/LayoutThumbnailSelector.tsx');
  const previewSelectorPath = path.resolve(__dirname, '../components/automation/LayoutPreviewSelector.tsx');
  const imagesModulePath = path.resolve(__dirname, '../components/automation/layoutPreviewImages.ts');
  const dashboardPath = path.resolve(__dirname, '../app/page.tsx');
  const automationPath = path.resolve(__dirname, '../app/automation/page.tsx');

  assert.ok(fs.existsSync(sharedComponentPath), 'LayoutThumbnailSelector.tsx must exist');
  assert.ok(fs.existsSync(previewSelectorPath), 'LayoutPreviewSelector.tsx must exist');
  assert.ok(fs.existsSync(imagesModulePath), 'layoutPreviewImages.ts must exist');
  assert.ok(fs.existsSync(dashboardPath), 'Dashboard page.tsx must exist');
  assert.ok(fs.existsSync(automationPath), 'Automation page.tsx must exist');

  const sharedContent = fs.readFileSync(sharedComponentPath, 'utf8');
  const previewContent = fs.readFileSync(previewSelectorPath, 'utf8');
  const dashboardContent = fs.readFileSync(dashboardPath, 'utf8');
  const automationContent = fs.readFileSync(automationPath, 'utf8');

  await t.test('1. Shared canonical LayoutThumbnailSelector re-exports the reference implementation', () => {
    assert.ok(sharedContent.includes("default as LayoutThumbnailSelector"), 'Must re-export LayoutThumbnailSelector');
    assert.ok(sharedContent.includes("default as LayoutPreviewSelector"), 'Must re-export LayoutPreviewSelector');
    assert.ok(sharedContent.includes("resolveLayoutOptionId"), 'Must re-export resolveLayoutOptionId');
    assert.ok(sharedContent.includes("LAYOUT_OPTIONS"), 'Must re-export LAYOUT_OPTIONS');
  });

  await t.test('2. Dashboard replaces legacy text-only layout dropdown with visual LayoutThumbnailSelector', () => {
    // Must NOT contain the old text dropdown
    assert.ok(!dashboardContent.includes('<select\n              className="input-field layout-mode-select"'), 'Legacy select element must be removed');
    assert.ok(!dashboardContent.includes('className="input-field layout-mode-select"'), 'Legacy layout-mode-select class must be gone');
    
    // Must import and render LayoutThumbnailSelector
    assert.ok(dashboardContent.includes("import LayoutThumbnailSelector from '@/components/LayoutThumbnailSelector';"), 'Dashboard must import shared component');
    assert.ok(dashboardContent.includes('<LayoutThumbnailSelector'), 'Dashboard must render LayoutThumbnailSelector');
    assert.ok(dashboardContent.includes('value={reframeMode || \'blur\'}'), 'Dashboard must bind value to reframeMode with blur fallback');
    assert.ok(dashboardContent.includes('onChange={val => setReframeMode(val)}'), 'Dashboard must update reframeMode state on change');
  });

  await t.test('3. Monitored Channels consumes canonical layout selector with channel profile binding', () => {
    assert.ok(automationContent.includes('from \'@/components/LayoutThumbnailSelector\';'), 'Automation page must import from shared component');
    assert.ok(automationContent.includes('<LayoutPreviewSelector'), 'Automation must render canonical selector');
    assert.ok(automationContent.includes('value={profile.video_layout || \'fill_blur\'}'), 'Automation must bind value to profile.video_layout');
    assert.ok(automationContent.includes("updateField('video_layout', val)"), 'Automation must update video_layout on selection');
  });

  await t.test('4. All 6 supported layout options are defined with exact labels, descriptions, and previews', () => {
    const expectedLayouts = [
      { id: 'center_crop', name: 'Crop', desc: 'Tight vertical crop (9:16).' },
      { id: 'fill_blur', name: 'Blur', desc: 'Full frame centered with blurred top/bottom.' },
      { id: 'split_screen', name: 'Split', desc: 'Two speakers side by side (9:16).' },
      { id: 'multi_split', name: 'Multi Split', desc: 'Four speakers in a 2x2 grid (9:16).' },
      { id: 'stacked_16_9', name: 'Stacked', desc: 'Two speakers stacked (9:16).' },
      { id: 'creative_transform', name: 'Transform', desc: 'AI tracked layout (dynamic framing).' },
    ];

    expectedLayouts.forEach(({ id, name, desc }) => {
      assert.ok(previewContent.includes(`id: '${id}'`), `Missing layout ID: ${id}`);
      assert.ok(previewContent.includes(`name: '${name}'`), `Missing layout name: ${name}`);
      assert.ok(previewContent.includes(`description: '${desc}'`), `Missing layout description: ${desc}`);
    });
  });

  await t.test('5. Helper resolveLayoutOptionId correctly resolves canonical IDs and historical aliases', () => {
    assert.ok(previewContent.includes('export function resolveLayoutOptionId'), 'resolveLayoutOptionId must be exported');
    assert.ok(previewContent.includes("aliases: ['crop', 'center_crop']"), 'Crop aliases must be present');
    assert.ok(previewContent.includes("aliases: ['fill_blur', 'blur_background', 'blur']"), 'Blur aliases must be present');
    assert.ok(previewContent.includes("aliases: ['split_screen', 'split']"), 'Split aliases must be present');
    assert.ok(previewContent.includes("aliases: ['stacked_16_9', 'stacked']"), 'Stacked aliases must be present');
    assert.ok(previewContent.includes("aliases: ['creative_transform', 'transform']"), 'Transform aliases must be present');
  });

  await t.test('6. Backend tasks and layout engine compatibility mapping', () => {
    const backendClipTasksPath = path.resolve(__dirname, '../../backend/tasks/clip_tasks.py');
    assert.ok(fs.existsSync(backendClipTasksPath), 'backend clip_tasks.py must exist');
    const clipTasksContent = fs.readFileSync(backendClipTasksPath, 'utf8');

    // Verify clip_tasks maps all canonical IDs to rendering modes
    assert.ok(clipTasksContent.includes('"fill_blur": "blur_background"'));
    assert.ok(clipTasksContent.includes('"center_crop": "center_crop"'));
    assert.ok(clipTasksContent.includes('"split_screen": "multi_split"'));
    assert.ok(clipTasksContent.includes('"multi_split": "multi_split"'));
    assert.ok(clipTasksContent.includes('"stacked_16_9": "stacked_16_9"'));
    assert.ok(clipTasksContent.includes('"creative_transform": "creative_transform"'));
  });
});
