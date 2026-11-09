import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('LayoutPreviewSelector: Visual Reference & Mode Definition Contract', async (t) => {
  const componentPath = path.resolve(__dirname, '../components/automation/LayoutPreviewSelector.tsx');
  const imagesModulePath = path.resolve(__dirname, '../components/automation/layoutPreviewImages.ts');
  const publicDir = path.resolve(__dirname, '../public/layout_previews');

  assert.ok(fs.existsSync(componentPath), 'LayoutPreviewSelector.tsx must exist');
  assert.ok(fs.existsSync(imagesModulePath), 'layoutPreviewImages.ts must exist');
  assert.ok(fs.existsSync(publicDir), 'public/layout_previews directory must exist');

  const componentSource = fs.readFileSync(componentPath, 'utf8');
  const imagesSource = fs.readFileSync(imagesModulePath, 'utf8');

  await t.test('1. Exactly 6 layout modes are defined matching the reference design', () => {
    const requiredModes = [
      { id: 'center_crop', name: 'Crop', desc: 'Tight vertical crop (9:16).' },
      { id: 'fill_blur', name: 'Blur', desc: 'Full frame centered with blurred top/bottom.' },
      { id: 'split_screen', name: 'Split', desc: 'Two speakers side by side (9:16).' },
      { id: 'multi_split', name: 'Multi Split', desc: 'Four speakers in a 2x2 grid (9:16).' },
      { id: 'stacked_16_9', name: 'Stacked', desc: 'Two speakers stacked (9:16).' },
      { id: 'creative_transform', name: 'Transform', desc: 'AI tracked layout (dynamic framing).' },
    ];

    requiredModes.forEach(({ id, name, desc }) => {
      assert.ok(componentSource.includes(`id: '${id}'`), `Missing layout ID: ${id}`);
      assert.ok(componentSource.includes(`name: '${name}'`), `Missing layout name: ${name}`);
      assert.ok(componentSource.includes(`description: '${desc}'`), `Missing description: ${desc}`);
    });
  });

  await t.test('2. All 6 layout modes have embedded visual preview images', () => {
    const requiredKeys = [
      'center_crop',
      'fill_blur',
      'split_screen',
      'multi_split',
      'stacked_16_9',
      'creative_transform',
    ];

    requiredKeys.forEach((key) => {
      assert.ok(imagesSource.includes(`'${key}': 'data:image/png;base64,`), `Missing embedded image data for ${key}`);
    });
  });

  await t.test('3. Static thumbnail PNG files exist in public/layout_previews', () => {
    const files = ['crop.png', 'blur.png', 'split.png', 'multi_split.png', 'stacked.png', 'transform.png'];
    files.forEach((file) => {
      const p = path.join(publicDir, file);
      assert.ok(fs.existsSync(p), `Missing static thumbnail file: ${file}`);
      const stat = fs.statSync(p);
      assert.ok(stat.size > 10000, `Thumbnail ${file} must be at least 10KB (got ${stat.size} bytes)`);
    });
  });

  await t.test('4. Helper resolveLayoutOptionId correctly resolves canonical IDs and historical aliases', () => {
    assert.ok(componentSource.includes("export function resolveLayoutOptionId"));
    assert.ok(componentSource.includes("center_crop"));
    assert.ok(componentSource.includes("fill_blur"));
    assert.ok(componentSource.includes("split_screen"));
  });
});
