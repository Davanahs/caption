import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('Advanced Podcast Component, Workflow, & API Contract', async (t) => {
  const modalPath = path.resolve(__dirname, '../components/PodcastSelectionModal.tsx');
  const podcastsPagePath = path.resolve(__dirname, '../app/podcasts/page.tsx');
  const apiPath = path.resolve(__dirname, '../lib/api.ts');

  assert.ok(fs.existsSync(modalPath), 'PodcastSelectionModal.tsx must exist');
  assert.ok(fs.existsSync(podcastsPagePath), 'app/podcasts/page.tsx must exist');
  assert.ok(fs.existsSync(apiPath), 'lib/api.ts must exist');

  const modalSource = fs.readFileSync(modalPath, 'utf8');
  const podcastsPageSource = fs.readFileSync(podcastsPagePath, 'utf8');
  const apiSource = fs.readFileSync(apiPath, 'utf8');

  await t.test('1. Advanced Podcast card exists on podcasts studio page with exact spec copy', () => {
    assert.ok(podcastsPageSource.includes('Advanced Podcast'), 'Must have Title: Advanced Podcast');
    assert.ok(
      podcastsPageSource.includes('A vertical podcast clip that follows the person shown by the original camera.'),
      'Must have Description: A vertical podcast clip that follows the person shown by the original camera.'
    );
    assert.ok(
      podcastsPageSource.includes('Select each participant once. ClipForge follows camera cuts and reframes whoever the original camera is showing.'),
      'Must have Supporting line: Select each participant once...'
    );
    assert.ok(
      podcastsPageSource.includes('Explore Advanced Podcast'),
      'Must have Action: Explore Advanced Podcast'
    );
    assert.ok(
      podcastsPageSource.includes('explore-advanced-podcast-btn'),
      'Must have button with id explore-advanced-podcast-btn'
    );
  });

  await t.test('2. 2-Feature Podcast Layout Selector exists under Step 3 Clip Settings', () => {
    assert.ok(modalSource.includes('feature-standard-camera-following-btn'), 'Must have standard camera following button');
    assert.ok(modalSource.includes('feature-ai-smart-director-btn'), 'Must have AI smart director button');
    assert.ok(modalSource.includes('Standard'), 'Must have Standard feature card');
    assert.ok(modalSource.includes('Continuous Camera Follower'), 'Must specify continuous camera follower');
    assert.ok(modalSource.includes('AI Smart Director'), 'Must specify AI smart director');
    assert.ok(!modalSource.includes('id="advanced-podcast-modal-card"'), 'Must remove redundant bottom card');
  });

  await t.test('3. Clean unified header and 2-feature studio state', () => {
    assert.ok(modalSource.includes('🎙️ Podcast & Interview Studio'), 'Must have unified studio header');
    assert.ok(
      modalSource.includes('Choose between Standard Camera Follower or AI Smart Director to generate viral 9:16 vertical clips.'),
      'Must have unified description'
    );
    assert.ok(modalSource.includes('selectedFeature, setSelectedFeature'), 'Must maintain selectedFeature state');
    assert.ok(!modalSource.includes('← Back to Manual Mode'), 'Must remove confusing Back to Manual Mode toggle');
  });

  await t.test('4. Shot analysis controls and schedule display are present', () => {
    assert.ok(modalSource.includes('analyze-shots-btn'), 'Must have analyze-shots-btn button');
    assert.ok(modalSource.includes('Analyze Camera Cuts & Speakers'), 'Must have analyze CTA');
    assert.ok(modalSource.includes('handleAnalyzeShots'), 'Must have handleAnalyzeShots function');
    assert.ok(modalSource.includes('Detected Shot Schedule'), 'Must render shot schedule table');
    assert.ok(modalSource.includes('Review Needed'), 'Must render review needed badge for uncertain cuts');
    assert.ok(modalSource.includes('handleOverrideShot'), 'Must allow user override of active speaker');
    assert.ok(modalSource.includes('toggle-shot-schedule-btn'), 'Must have collapsible accordion toggle button');
    assert.ok(modalSource.includes('Camera Cuts Detected'), 'Must have summary pill');
  });

  await t.test('5. Single 9:16 camera-following output semantics (NO stacked panels)', () => {
    assert.ok(modalSource.includes('Camera-Following Preview (9:16)'), 'Must have camera-following preview label');
    assert.ok(modalSource.includes('Single continuous 9:16 vertical view reframes the active participant'), 'Must emphasize single continuous vertical view');
    assert.ok(modalSource.includes('generate-advanced-clips-btn'), 'Must have generate-advanced-clips-btn CTA');
  });

  await t.test('6. API client exports analyzePodcastShots and serializes shot_schedule', () => {
    assert.ok(apiSource.includes('export async function analyzePodcastShots'), 'Must export analyzePodcastShots');
    assert.ok(apiSource.includes('/api/videos/podcast/analyze-shots'), 'Must call analyze-shots endpoint');
    assert.ok(apiSource.includes('shotSchedule?: any[]'), 'SubmitYouTubeOptions must include shotSchedule');
    assert.ok(apiSource.includes("form.append('shot_schedule', JSON.stringify(opts.shotSchedule))"), 'Must serialize shot_schedule in submitYouTubeUrl');
  });

  await t.test('7. Shot schedule supports row selection and active preview switching', () => {
    assert.ok(modalSource.includes('selectedShotId'), 'Must maintain selectedShotId state');
    assert.ok(modalSource.includes('setSelectedShotId'), 'Must provide setSelectedShotId updater');
    assert.ok(modalSource.includes('onClick={() => setSelectedShotId(shot.shot_id)}'), 'Must allow selecting shot rows to preview framing');
    assert.ok(modalSource.includes('Previewing Shot:'), 'Must display active previewing shot header');
  });

  await t.test('8. Standard Podcast Camera Follower (Feature 1) continuous 9:16 vertical view without rigid boundaries', () => {
    assert.ok(modalSource.includes("'camera_following'"), 'Must support camera_following composition');
    assert.ok(modalSource.includes('Continuous Camera Follower'), 'Must specify continuous camera follower');
    assert.ok(!modalSource.includes('id="geometry-limit-warning"'), 'Must remove rigid geometry limit warning');
    assert.ok(!modalSource.includes('Set Outer Clipping Boundary'), 'Must remove rigid outer boundary button');
  });

  await t.test('9. Visibility-Driven Option (Feature 2) renders horizontal side-by-side half-panels (flex-row)', () => {
    assert.ok(modalSource.includes("'visibility_driven'"), 'Must support visibility_driven composition');
    assert.ok(modalSource.includes("outputPreviewGeom.composition === 'side_by_side'"), 'Must check for side_by_side composition in preview container');
    assert.ok(modalSource.includes("'flex-row'"), 'Side-by-side preview container must use flex-row for horizontal composition');
    assert.ok(modalSource.includes('Initial Preview — Side-by-Side (A + B)'), 'Must display initial pre-analysis side-by-side preview badge');
  });

  await t.test('10. Honest preview disclaimer discloses thumbnail or geometric representation', () => {
    assert.ok(modalSource.includes('Preview uses YouTube thumbnail or geometric placeholder'), 'Must disclose preview image provenance');
    assert.ok(modalSource.includes('Final render calculates exact pixel boundaries from video frames'), 'Must explain final render calculations');
  });
});
