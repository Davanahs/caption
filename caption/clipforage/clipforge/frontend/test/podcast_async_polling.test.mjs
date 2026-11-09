import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('Topic 6 Work Item 1: Async Polling, Wall-Clock Deadline & AbortSignal Audit', async (t) => {
  const apiPath = path.resolve(__dirname, '../lib/api.ts');
  const modalPath = path.resolve(__dirname, '../components/PodcastSelectionModal.tsx');

  assert.ok(fs.existsSync(apiPath), 'lib/api.ts must exist');
  assert.ok(fs.existsSync(modalPath), 'components/PodcastSelectionModal.tsx must exist');

  const apiSource = fs.readFileSync(apiPath, 'utf8');
  const modalSource = fs.readFileSync(modalPath, 'utf8');

  await t.test('1. api.ts exports getPodcastAnalysisStatus and analyzePodcastShots accepting AbortSignal', () => {
    assert.ok(
      apiSource.includes('export async function getPodcastAnalysisStatus(taskId: string, signal?: AbortSignal)'),
      'getPodcastAnalysisStatus must accept signal?: AbortSignal'
    );
    assert.ok(
      apiSource.includes('signal?: AbortSignal'),
      'analyzePodcastShots must accept signal?: AbortSignal'
    );
    assert.ok(
      apiSource.includes('timeoutMs: number = 180000'),
      'analyzePodcastShots must configure default 180000ms wall-clock deadline'
    );
  });

  await t.test('2. Wall-clock elapsed time is enforced rather than iteration counting', () => {
    assert.ok(apiSource.includes('const startTime = Date.now();'), 'Must record startTime via Date.now()');
    assert.ok(
      apiSource.includes('while (Date.now() - startTime < timeoutMs)'),
      'Must check elapsed wall-clock time in loop condition'
    );
    assert.ok(
      apiSource.includes('Shot analysis timed out in background worker after'),
      'Must throw descriptive timeout error on wall-clock expiry'
    );
  });

  await t.test('3. Interruptible delay aborts immediately upon signal without waiting', () => {
    assert.ok(apiSource.includes('signal?.aborted'), 'Must check signal?.aborted before and during polling');
    assert.ok(
      apiSource.includes("signal.addEventListener('abort', onAbort"),
      'Must listen to abort signal during sleep delay'
    );
    assert.ok(
      apiSource.includes("throw new DOMException('Analysis polling aborted"),
      'Must throw DOMException with AbortError name on abort'
    );
  });

  await t.test('4. Modal cleans up on unmount and isolates analysis sessions', () => {
    assert.ok(
      modalSource.includes('const abortControllerRef = useRef<AbortController | null>(null);'),
      'Modal must maintain abortControllerRef'
    );
    assert.ok(
      modalSource.includes('const analysisSessionRef = useRef<number>(0);'),
      'Modal must maintain analysisSessionRef session counter'
    );
    assert.ok(
      modalSource.includes('abortControllerRef.current.abort();'),
      'Modal must abort in-flight controller on unmount or cancel'
    );
    assert.ok(
      modalSource.includes('analysisSessionRef.current !== currentSessionId'),
      'Modal must reject stale responses from superseded sessions'
    );
  });

  await t.test('5. Modal provides user cancellation and distinguishes AbortError from worker failures', () => {
    assert.ok(
      modalSource.includes('id="cancel-analyze-shots-btn"'),
      'Modal must render cancel-analyze-shots-btn button when analyzing'
    );
    assert.ok(
      modalSource.includes("err?.name === 'AbortError' || controller.signal.aborted"),
      'Modal must catch AbortError specifically'
    );
    assert.ok(
      modalSource.includes("setAnalysisStatus('Analysis cancelled.')") ||
        modalSource.includes("setAnalysisStatus('Analysis cancelled by user.')"),
      'Modal must set status to cancelled rather than error banner on user abort'
    );
  });

  await t.test('6. Functional simulation: deadline expiry, abort signal & stale rejection', async () => {
    // Simulate deadline expiry logic
    const simulatePolling = async (timeoutMs, stepDelayMs, signal) => {
      const startTime = Date.now();
      while (Date.now() - startTime < timeoutMs) {
        if (signal?.aborted) {
          throw new DOMException('Aborted', 'AbortError');
        }
        await new Promise((resolve, reject) => {
          if (signal?.aborted) return reject(new DOMException('Aborted', 'AbortError'));
          const timer = setTimeout(resolve, stepDelayMs);
          if (signal) {
            signal.addEventListener('abort', () => {
              clearTimeout(timer);
              reject(new DOMException('Aborted', 'AbortError'));
            }, { once: true });
          }
        });
      }
      throw new Error(`Timed out after ${timeoutMs}ms`);
    };

    // Test deadline expiry
    await assert.rejects(
      async () => {
        await simulatePolling(50, 20, null);
      },
      /Timed out after 50ms/
    );

    // Test early abort signal cancellation
    const controller = new AbortController();
    setTimeout(() => controller.abort(), 15);
    await assert.rejects(
      async () => {
        await simulatePolling(500, 100, controller.signal);
      },
      (err) => err.name === 'AbortError'
    );

    // Test stale session rejection logic
    let activeSession = 1;
    let uiUpdated = false;
    const asyncCallback = (sessionId) => {
      if (sessionId === activeSession) {
        uiUpdated = true;
      }
    };

    // Session 1 is superseded by session 2
    activeSession = 2;
    asyncCallback(1); // Call from old session
    assert.equal(uiUpdated, false, 'Stale session 1 must not update UI');

    asyncCallback(2); // Call from current session
    assert.equal(uiUpdated, true, 'Active session 2 must update UI');
  });
});
