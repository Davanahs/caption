# End-to-End Validation & Pipeline Audits

## Goal
Verify the end-to-end pipeline execution from Checkpoint 140, specifically addressing the transcription provider audit (Groq fallback) and the LLM Router fallback robustness using a shared Redis state.

## User Review Required
No major breaking changes are proposed. The changes are robustness enhancements for cloud API fallbacks.

## Open Questions
- None.

## Proposed Changes

### 1. Transcription Provider Audit
**Findings:**
- `GROQ_API_KEY` is present and valid.
- The `transcribe_via_groq` logic correctly uses `ffmpeg` to extract a 16kHz mono MP3.
- When tested inside the `clipforge_worker` container, Groq transcription **succeeds**. 
- The prior failure was likely due to the `clipforge_worker` container running in a stale state before the `GROQ_API_KEY` was populated in `.env` (it was resolved when we restarted the worker during the DB schema fix).
- Groq has a hard limit of 25MB. For long videos (>25 mins), the extracted MP3 will exceed 24.5MB, causing an intentional fallback to local Whisper.

**Actions:**
- Keep local Whisper as the intentional fallback.
- Add detailed logging when `transcribe_via_groq` falls back to Whisper due to size limits.

#### [MODIFY] `backend/services/transcriber.py`
- Improve logging when Groq falls back to Whisper.
- Ensure the exception message is clearly logged.

---

### 2. LLM Router Robustness Audit
**Findings:**
- `openrouter_out_of_credits` is currently a local variable, causing each celery task to hit 402s repeatedly.
- The proposed process-local global variable is insufficient because it won't synchronize the cooldown across multiple Celery workers/processes.
- The user-configured model (`OPENROUTER_MODEL`) is not subject to the fallback check currently and also requires provider-scoped logic.

**Actions:**
- Replace the local `openrouter_out_of_credits` variable with a **shared Redis state** using `settings.REDIS_URL`. 
- Conceptually, set a key like `openrouter:credits_exhausted` with a 1-hour TTL when a 402 is encountered.
- Before querying *any* paid OpenRouter model (including the user-configured one), check this Redis key. If the key exists, skip the paid models and proceed to free models or fallback providers.

#### [MODIFY] `backend/services/llm_router.py`
- Connect to Redis using `redis.Redis.from_url(settings.REDIS_URL)`.
- Write helper functions to set and get the provider-scoped cooldown (`openrouter:cooldown`).
- Update `route_and_generate()` to respect this shared state across all models.

#### [NEW] `scratch/test_llm_router_cooldown.py`
- Automated test to simulate the multi-worker 402 scenario, cooldown expiry, and 429 independence.

## Verification Plan
### Automated Tests
- `scratch/test_llm_router_cooldown.py`:
  - 1st call -> simulates 402 (via mock).
  - 2nd call -> verify paid models skipped.
  - Expire cooldown manually -> verify paid models become eligible again.
  - 429 scenario -> verify retry policy acts independently of 402 cooldown.

### Manual Verification
- Re-run the real pipeline from the affected stage (using a new trigger or stale recovery) and ensure the final artifact correctly outputs as a ≤50s vertical video.
