import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('Phase 2 Accessibility & Modal Interaction Contract', async (t) => {
  const processModalPath = path.resolve(__dirname, '../components/ProcessVideoModal.tsx');
  const podcastModalPath = path.resolve(__dirname, '../components/PodcastSelectionModal.tsx');
  const clipsPagePath = path.resolve(__dirname, '../app/clips/page.tsx');
  const scoreRingPath = path.resolve(__dirname, '../components/ScoreRing.tsx');
  const dashboardPath = path.resolve(__dirname, '../app/page.tsx');
  const focusTrapPath = path.resolve(__dirname, '../lib/useFocusTrap.ts');

  assert.ok(fs.existsSync(processModalPath), 'ProcessVideoModal.tsx must exist');
  assert.ok(fs.existsSync(podcastModalPath), 'PodcastSelectionModal.tsx must exist');
  assert.ok(fs.existsSync(clipsPagePath), 'app/clips/page.tsx must exist');
  assert.ok(fs.existsSync(scoreRingPath), 'components/ScoreRing.tsx must exist');
  assert.ok(fs.existsSync(dashboardPath), 'app/page.tsx must exist');
  assert.ok(fs.existsSync(focusTrapPath), 'lib/useFocusTrap.ts must exist');

  const processModalSource = fs.readFileSync(processModalPath, 'utf8');
  const podcastModalSource = fs.readFileSync(podcastModalPath, 'utf8');
  const clipsPageSource = fs.readFileSync(clipsPagePath, 'utf8');
  const scoreRingSource = fs.readFileSync(scoreRingPath, 'utf8');
  const dashboardSource = fs.readFileSync(dashboardPath, 'utf8');
  const focusTrapSource = fs.readFileSync(focusTrapPath, 'utf8');

  // ── DEF-A11Y-01: Modal Dialog Semantics ────────────────────────────────
  await t.test('DEF-A11Y-01: ProcessVideoModal has complete dialog semantics', () => {
    assert.ok(processModalSource.includes('role="dialog"'), 'ProcessVideoModal must have role="dialog"');
    assert.ok(processModalSource.includes('aria-modal="true"'), 'ProcessVideoModal must have aria-modal="true"');
    assert.ok(processModalSource.includes('aria-labelledby="clip-modal-title"'), 'ProcessVideoModal must have aria-labelledby');
    assert.ok(processModalSource.includes('aria-describedby="clip-modal-description"'), 'ProcessVideoModal must have aria-describedby');
    assert.ok(processModalSource.includes('id="clip-modal-title"'), 'ProcessVideoModal must define id="clip-modal-title"');
    assert.ok(processModalSource.includes('id="clip-modal-description"'), 'ProcessVideoModal must define id="clip-modal-description"');
    assert.ok(processModalSource.includes('aria-label="Close dialog"'), 'ProcessVideoModal must have accessible close button label');
  });

  await t.test('DEF-A11Y-01: PodcastSelectionModal has complete dialog semantics', () => {
    assert.ok(podcastModalSource.includes('role="dialog"'), 'PodcastSelectionModal must have role="dialog"');
    assert.ok(podcastModalSource.includes('aria-modal="true"'), 'PodcastSelectionModal must have aria-modal="true"');
    assert.ok(podcastModalSource.includes('aria-labelledby="podcast-modal-title"'), 'PodcastSelectionModal must have aria-labelledby');
    assert.ok(podcastModalSource.includes('aria-describedby="podcast-modal-description"'), 'PodcastSelectionModal must have aria-describedby');
    assert.ok(podcastModalSource.includes('id="podcast-modal-title"'), 'PodcastSelectionModal must define id="podcast-modal-title"');
    assert.ok(podcastModalSource.includes('id="podcast-modal-description"'), 'PodcastSelectionModal must define id="podcast-modal-description"');
    assert.ok(podcastModalSource.includes('aria-label="Close dialog"'), 'PodcastSelectionModal must have accessible close button label');
  });

  await t.test('DEF-A11Y-01: PreviewModal in clips page has dialog semantics', () => {
    assert.ok(clipsPageSource.includes('role="dialog"'), 'PreviewModal must have role="dialog"');
    assert.ok(clipsPageSource.includes('aria-modal="true"'), 'PreviewModal must have aria-modal="true"');
    assert.ok(clipsPageSource.includes('aria-labelledby="preview-modal-title"'), 'PreviewModal must have aria-labelledby');
    assert.ok(clipsPageSource.includes('id="preview-modal-title"'), 'PreviewModal must define title ID');
  });

  // ── DEF-A11Y-02: Modal Keyboard Focus Trap & Management ──────────────
  await t.test('DEF-A11Y-02: useFocusTrap hook provides comprehensive keyboard management', () => {
    assert.ok(focusTrapSource.includes('previousActiveElement.current = document.activeElement'), 'Must save previous active element on modal open');
    assert.ok(focusTrapSource.includes('previousActiveElement.current.focus()'), 'Must restore focus to trigger on modal close');
    assert.ok(focusTrapSource.includes("e.key === 'Escape'"), 'Must handle Escape key to close modal');
    assert.ok(focusTrapSource.includes("e.key === 'Tab'"), 'Must intercept Tab key');
    assert.ok(focusTrapSource.includes('e.shiftKey'), 'Must handle Shift+Tab backward cycling');
    assert.ok(focusTrapSource.includes('lastElement.focus()'), 'Must wrap backward to last element');
    assert.ok(focusTrapSource.includes('firstElement.focus()'), 'Must wrap forward to first element');
  });

  await t.test('DEF-A11Y-02: Focus trap is wired into ProcessVideoModal, PodcastSelectionModal, and PreviewModal', () => {
    assert.ok(processModalSource.includes('useFocusTrap(isOpen, modalContainerRef'), 'ProcessVideoModal must call useFocusTrap');
    assert.ok(processModalSource.includes('ref={modalContainerRef}'), 'ProcessVideoModal must attach ref to modal container');
    assert.ok(processModalSource.includes('tabIndex={-1}'), 'ProcessVideoModal container must have tabIndex={-1}');

    assert.ok(podcastModalSource.includes('useFocusTrap(isOpen, modalContainerRef'), 'PodcastSelectionModal must call useFocusTrap');
    assert.ok(podcastModalSource.includes('ref={modalContainerRef}'), 'PodcastSelectionModal must attach ref to modal container');
    assert.ok(podcastModalSource.includes('tabIndex={-1}'), 'PodcastSelectionModal container must have tabIndex={-1}');

    assert.ok(clipsPageSource.includes('useFocusTrap(true, modalContainerRef'), 'PreviewModal must call useFocusTrap');
    assert.ok(clipsPageSource.includes('ref={modalContainerRef}'), 'PreviewModal must attach ref to modal container');
  });

  // ── DEF-A11Y-03: ScoreRing Accessible Semantics ────────────────────────
  await t.test('DEF-A11Y-03: ScoreRing uses role="meter" with range and label', () => {
    assert.ok(scoreRingSource.includes('role="meter"'), 'ScoreRing must use role="meter" for bounded measurement');
    assert.ok(scoreRingSource.includes('aria-valuenow={boundedScore}'), 'ScoreRing must expose aria-valuenow');
    assert.ok(scoreRingSource.includes('aria-valuemin={0}'), 'ScoreRing must expose aria-valuemin={0}');
    assert.ok(scoreRingSource.includes('aria-valuemax={10}'), 'ScoreRing must expose aria-valuemax={10}');
    assert.ok(scoreRingSource.includes('aria-label='), 'ScoreRing must expose descriptive aria-label');
    assert.ok(scoreRingSource.includes('aria-hidden="true"'), 'ScoreRing must hide decorative numeric text from duplicate screen-reader reading');

    // Also verify clips page implementation
    assert.ok(clipsPageSource.includes('role="meter"'), 'Clips page ScoreRing must use role="meter"');
    assert.ok(clipsPageSource.includes('aria-valuenow='), 'Clips page ScoreRing must have aria-valuenow');
    assert.ok(clipsPageSource.includes('aria-valuemin={0}'), 'Clips page ScoreRing must have aria-valuemin');
    assert.ok(clipsPageSource.includes('aria-valuemax={10}'), 'Clips page ScoreRing must have aria-valuemax');
  });

  // ── DEF-A11Y-04: URL Input Validation Semantics ───────────────────────
  await t.test('DEF-A11Y-04: Dashboard YouTube URL input has accessible validation semantics', () => {
    assert.ok(dashboardSource.includes('htmlFor="dashboard-youtube-url"'), 'Dashboard label must have htmlFor="dashboard-youtube-url"');
    assert.ok(dashboardSource.includes('id="dashboard-youtube-url"'), 'Dashboard input must have id="dashboard-youtube-url"');
    assert.ok(dashboardSource.includes('aria-invalid={url.trim().length > 0 && !extractYouTubeVideoId(url.trim())}'), 'Dashboard input must bind aria-invalid to validation state');
    assert.ok(dashboardSource.includes('aria-describedby={url.trim().length > 0 && !extractYouTubeVideoId(url.trim()) ? "dashboard-youtube-url-error" : undefined}'), 'Dashboard input must bind aria-describedby');
    assert.ok(dashboardSource.includes('id="dashboard-youtube-url-error"'), 'Error element must have matching id="dashboard-youtube-url-error"');
    assert.ok(dashboardSource.includes('role="alert"'), 'Error element must have role="alert" for immediate screen reader announcement');
  });

  await t.test('DEF-A11Y-04: PodcastSelectionModal YouTube URL input has accessible validation semantics', () => {
    assert.ok(podcastModalSource.includes('id="podcast-youtube-url-input"'), 'Podcast URL input must have id');
    assert.ok(podcastModalSource.includes('aria-label="YouTube Video Link"'), 'Podcast URL input must have accessible aria-label');
    assert.ok(podcastModalSource.includes('aria-invalid={!!urlError}'), 'Podcast URL input must bind aria-invalid to urlError state');
    assert.ok(podcastModalSource.includes('aria-describedby={urlError ? "podcast-url-error-msg" : undefined}'), 'Podcast URL input must bind aria-describedby');
    assert.ok(podcastModalSource.includes('id="podcast-url-error-msg"'), 'Podcast error element must have matching id');
    assert.ok(podcastModalSource.includes('role="alert"'), 'Podcast error element must have role="alert"');
    assert.ok(podcastModalSource.includes('if (urlError) setUrlError(null);'), 'Podcast URL input must clear error when user types');
  });
});
