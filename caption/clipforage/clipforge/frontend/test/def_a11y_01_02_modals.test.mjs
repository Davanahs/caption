import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('DEF-A11Y-01 & DEF-A11Y-02: Modal ARIA Dialog Roles, Semantics & Focus Trap Contract', async (t) => {
  const processModalPath = path.resolve(__dirname, '../components/ProcessVideoModal.tsx');
  const podcastModalPath = path.resolve(__dirname, '../components/PodcastSelectionModal.tsx');
  const focusTrapPath = path.resolve(__dirname, '../lib/useFocusTrap.ts');

  assert.ok(fs.existsSync(processModalPath), 'ProcessVideoModal.tsx must exist');
  assert.ok(fs.existsSync(podcastModalPath), 'PodcastSelectionModal.tsx must exist');
  assert.ok(fs.existsSync(focusTrapPath), 'useFocusTrap.ts must exist');

  const processModalSource = fs.readFileSync(processModalPath, 'utf8');
  const podcastModalSource = fs.readFileSync(podcastModalPath, 'utf8');
  const focusTrapSource = fs.readFileSync(focusTrapPath, 'utf8');

  await t.test('1. DEF-A11Y-01: ProcessVideoModal root container has role="dialog" and aria-modal="true"', () => {
    assert.ok(processModalSource.includes('role="dialog"'), 'ProcessVideoModal must have role="dialog"');
    assert.ok(processModalSource.includes('aria-modal="true"'), 'ProcessVideoModal must have aria-modal="true"');
    assert.ok(processModalSource.includes('aria-labelledby="clip-modal-title"'), 'ProcessVideoModal must link title with aria-labelledby');
    assert.ok(processModalSource.includes('id="clip-modal-title"'), 'ProcessVideoModal must have title element matching aria-labelledby');
    assert.ok(processModalSource.includes('aria-describedby="clip-modal-description"'), 'ProcessVideoModal must have aria-describedby');
  });

  await t.test('2. DEF-A11Y-01: PodcastSelectionModal root container has role="dialog" and aria-modal="true"', () => {
    assert.ok(podcastModalSource.includes('role="dialog"'), 'PodcastSelectionModal must have role="dialog"');
    assert.ok(podcastModalSource.includes('aria-modal="true"'), 'PodcastSelectionModal must have aria-modal="true"');
    assert.ok(podcastModalSource.includes('aria-labelledby="podcast-modal-title"'), 'PodcastSelectionModal must link title with aria-labelledby');
    assert.ok(podcastModalSource.includes('id="podcast-modal-title"'), 'PodcastSelectionModal must have title element matching aria-labelledby');
  });

  await t.test('3. DEF-A11Y-02: useFocusTrap implementation contains forward and backward Tab trapping', () => {
    assert.ok(focusTrapSource.includes('e.key === \'Tab\''), 'useFocusTrap must handle Tab key');
    assert.ok(focusTrapSource.includes('e.shiftKey'), 'useFocusTrap must handle Shift+Tab for backward trapping');
    assert.ok(focusTrapSource.includes('e.key === \'Escape\''), 'useFocusTrap must handle Escape key');
    assert.ok(focusTrapSource.includes('previousActiveElement'), 'useFocusTrap must restore previous active element on unmount');
  });

  await t.test('4. DEF-A11Y-02: Both modals integrate useFocusTrap with container ref', () => {
    assert.ok(processModalSource.includes('useFocusTrap('), 'ProcessVideoModal must invoke useFocusTrap');
    assert.ok(processModalSource.includes('modalContainerRef'), 'ProcessVideoModal must pass modalContainerRef');
    assert.ok(podcastModalSource.includes('useFocusTrap('), 'PodcastSelectionModal must invoke useFocusTrap');
    assert.ok(podcastModalSource.includes('modalContainerRef'), 'PodcastSelectionModal must pass modalContainerRef');
  });
});
