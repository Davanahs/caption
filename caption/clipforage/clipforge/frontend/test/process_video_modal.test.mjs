import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Helper function to test regex extraction directly
function extractYouTubeId(url) {
  if (!url || typeof url !== 'string') return null;
  const match = url.match(
    /(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/|live\/))([a-zA-Z0-9_-]{11})/
  );
  return match ? match[1] : null;
}

test('ProcessVideoModal Component & Integration Contract', async (t) => {
  const modalComponentPath = path.resolve(__dirname, '../components/ProcessVideoModal.tsx');
  const dashboardPagePath = path.resolve(__dirname, '../app/page.tsx');
  const apiLibPath = path.resolve(__dirname, '../lib/api.ts');
  const layoutSelectorPath = path.resolve(__dirname, '../components/LayoutThumbnailSelector.tsx');

  assert.ok(fs.existsSync(modalComponentPath), 'ProcessVideoModal.tsx must exist');
  assert.ok(fs.existsSync(dashboardPagePath), 'Dashboard page.tsx must exist');
  assert.ok(fs.existsSync(apiLibPath), 'lib/api.ts must exist');
  assert.ok(fs.existsSync(layoutSelectorPath), 'LayoutThumbnailSelector.tsx must exist');

  const modalSource = fs.readFileSync(modalComponentPath, 'utf8');
  const dashboardSource = fs.readFileSync(dashboardPagePath, 'utf8');
  const apiSource = fs.readFileSync(apiLibPath, 'utf8');

  await t.test('1. YouTube ID extraction regex handles all common URL variations', () => {
    assert.equal(extractYouTubeId('https://www.youtube.com/watch?v=Nt6d62vN7CU'), 'Nt6d62vN7CU');
    assert.equal(extractYouTubeId('https://youtu.be/Nt6d62vN7CU?si=TEZF-vFIkT054V98'), 'Nt6d62vN7CU');
    assert.equal(extractYouTubeId('https://www.youtube.com/shorts/dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
    assert.equal(extractYouTubeId('https://www.youtube.com/embed/dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
    assert.equal(extractYouTubeId('https://www.youtube.com/live/dQw4w9WgXcQ?feature=share'), 'dQw4w9WgXcQ');
    assert.equal(extractYouTubeId(''), null);
    assert.equal(extractYouTubeId('https://vimeo.com/123456789'), null);
    assert.equal(extractYouTubeId('not-a-valid-url'), null);
  });

  await t.test('2. Header and source video summary with YouTube thumbnail CDN', () => {
    assert.ok(modalSource.includes('Configure Your Clips'), 'Must have standard title');
    assert.ok(modalSource.includes('https://img.youtube.com/vi/'), 'Must use YouTube image CDN for real thumbnail');
    assert.ok(modalSource.includes('YouTube Source'), 'Must have badge for YouTube source');
    assert.ok(modalSource.includes('Uploaded File'), 'Must support local uploaded file display');
    assert.ok(modalSource.includes('Batch Ingestion'), 'Must support batch ingestion display');
  });

  await t.test('3. Clip Generation Mode selector (AI Highlights vs Equal Split)', () => {
    assert.ok(modalSource.includes('ai_highlights'), 'Must support ai_highlights mode');
    assert.ok(modalSource.includes('equal_split'), 'Must support equal_split mode');
    assert.ok(modalSource.includes('Find and score engaging viral moments automatically.'), 'Must explain AI Highlights');
    assert.ok(modalSource.includes('Divide the source video into segments of similar length.'), 'Must explain Equal Split');
  });

  await t.test('4. Clip count presets and custom input with live count summary', () => {
    [2, 3, 5, 8, 10].forEach(n => {
      assert.ok(modalSource.includes(`${n}`), `Must contain preset ${n}`);
    });
    assert.ok(modalSource.includes('Default'), '5 must be marked as default');
    assert.ok(modalSource.includes('Or custom (1–20)'), 'Must offer custom input (1-20)');
    assert.ok(modalSource.includes('clips will be generated'), 'Must have dynamic helper summary for clip count');
  });

  await t.test('5. Maximum clip duration with 49s optimal Shorts badge & reason', () => {
    [15, 30, 45, 49, 60].forEach(d => {
      assert.ok(modalSource.includes(`${d}s`), `Must offer ${d}s duration`);
    });
    assert.ok(modalSource.includes('Optimal'), '49s must be labeled Optimal');
    assert.ok(modalSource.includes('YouTube Shorts sweet spot'), 'Must explain why 49s is optimal for Shorts');
  });

  await t.test('6. Canonical LayoutThumbnailSelector is embedded in modal', () => {
    assert.ok(modalSource.includes('<LayoutThumbnailSelector'), 'Must embed LayoutThumbnailSelector');
    assert.ok(modalSource.includes('import LayoutThumbnailSelector'), 'Must import LayoutThumbnailSelector');
  });

  await t.test('7. Optional Enhancements with collapsible progressive disclosure', () => {
    assert.ok(modalSource.includes('Optional Enhancements'), 'Must include Optional Enhancements section');
    assert.ok(modalSource.includes('showEnhancements'), 'Must support expand/collapse toggle');
    assert.ok(modalSource.includes('Hook Title Overlay'), 'Must include Hook Title overlay');
    assert.ok(modalSource.includes('AI B-Roll Overlay'), 'Must include AI B-Roll overlay');
    assert.ok(modalSource.includes('AI Kinetic Hook Intro'), 'Must include AI Kinetic Hook Intro');
    assert.ok(modalSource.includes('AI Auto-Dubbing & Voice Translation'), 'Must include Dubbing selector');
  });

  await t.test('8. Multi-language dubbing options preserved', () => {
    ['none', 'es', 'hi', 'de', 'ja', 'pt', 'fr'].forEach(lang => {
      assert.ok(modalSource.includes(`value: '${lang}'`), `Must support language option ${lang}`);
    });
  });

  await t.test('9. Dynamic Live Configuration Summary bar above footer', () => {
    assert.ok(modalSource.includes('configurationSummary'), 'Must calculate live configuration summary');
    assert.ok(modalSource.includes('Plan:'), 'Must show Plan summary badge in footer');
  });

  await t.test('10. Footer processing actions and error resilience', () => {
    assert.ok(modalSource.includes('Cancel'), 'Must have Cancel button');
    assert.ok(modalSource.includes('Start Processing'), 'Must have Start Processing button');
    assert.ok(modalSource.includes('errorMessage'), 'Must render error banner when error occurs');
    assert.ok(modalSource.includes('isSubmitting'), 'Must prevent duplicate submissions');
  });

  await t.test('11. API client supports clipMode, targetDuration, and segmentationStrategy', () => {
    assert.ok(apiSource.includes('clipMode?: string'), 'SubmitYouTubeOptions must have clipMode');
    assert.ok(apiSource.includes('targetDuration?: number'), 'SubmitYouTubeOptions must have targetDuration');
    assert.ok(apiSource.includes('segmentationStrategy?: string'), 'SubmitYouTubeOptions must have segmentationStrategy');
    assert.ok(apiSource.includes("form.append('clip_mode', opts.clipMode)"), 'submitYouTubeUrl must append clip_mode');
    assert.ok(apiSource.includes("form.append('clip_mode', clipMode)"), 'uploadVideoFile must append clip_mode');
    assert.ok(apiSource.includes("clip_mode: clipMode || 'ai_highlights'"), 'submitBatchYouTubeUrls must include clip_mode');
    assert.ok(apiSource.includes("form.append('target_duration', opts.targetDuration.toString())"), 'submitYouTubeUrl must append target_duration');
    assert.ok(apiSource.includes("form.append('segmentation_strategy', opts.segmentationStrategy)"), 'submitYouTubeUrl must append segmentation_strategy');
  });

  await t.test('12. Dashboard page integrates ProcessVideoModal with Equal Split parameters', () => {
    assert.ok(dashboardSource.includes('<ProcessVideoModal'), 'Dashboard must render ProcessVideoModal');
    assert.ok(dashboardSource.includes('import ProcessVideoModal'), 'Dashboard must import ProcessVideoModal');
    assert.ok(dashboardSource.includes('confirmAndProcess'), 'Dashboard must pass confirmAndProcess');
    assert.ok(dashboardSource.includes("targetDuration = config.clipMode === 'equal_split'"), 'Dashboard must compute targetDuration for equal_split');
    assert.ok(dashboardSource.includes("segmentationStrategy = config.clipMode === 'equal_split' ? 'equal_splits' : undefined"), 'Dashboard must compute segmentationStrategy for equal_split');
  });

  await t.test('13. Equal Split UI card displays full source coverage and dynamic segment estimates', () => {
    assert.ok(modalSource.includes('Equal Split — Full Source Coverage'), 'Must display full source coverage card header');
    assert.ok(modalSource.includes('100% Timeline Covered'), 'Must display 100% timeline covered badge');
    assert.ok(modalSource.includes('Maximum Clip Limit'), 'Must display maximum clip limit label');
    assert.ok(modalSource.includes('Calculated Clip Count'), 'Must display calculated clip count label');
    assert.ok(modalSource.includes('Entire video (0:00 → End)'), 'Must confirm entire video coverage without remainder loss');
    assert.ok(modalSource.includes("targetDuration: clipMode === 'equal_split' ? maxClipDuration : undefined"), 'onConfirm must pass targetDuration for equal_split');
    assert.ok(modalSource.includes("segmentationStrategy: clipMode === 'equal_split' ? 'equal_splits' : undefined"), 'onConfirm must pass segmentationStrategy for equal_split');
  });

  await t.test('14. Equal Split disables/hides manual clip count and passes undefined clipsCount', () => {
    assert.ok(modalSource.includes("if (clipMode === 'equal_split') return undefined;"), 'effectiveClipsCount must be undefined in equal_split mode');
    assert.ok(modalSource.includes("clipsCount: clipMode === 'equal_split' ? undefined : (effectiveClipsCount || 5)"), 'onConfirm must omit manual clipsCount for equal_split');
    assert.ok(modalSource.includes("Maximum Clip Duration (Limit)"), 'Must clearly communicate duration is a maximum limit in equal_split');
    assert.ok(modalSource.includes("clipMode === 'ai_highlights' ? ("), 'Number of clips selector must only be shown for ai_highlights mode');
  });
});
