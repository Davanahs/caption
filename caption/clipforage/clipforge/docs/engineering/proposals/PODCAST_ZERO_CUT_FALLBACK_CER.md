# Logic Domain L7 Change Exception Record (CER)

**CER Reference:** `CER-2026-L7-001`  
**Work Item:** `PODCAST-ZERO-CUT-FALLBACK-016`  
**Title:** Separate FFmpeg Execution Success from Camera-Cut Detection Count  
**Logic Domain:** L7 (Advanced Multi-Speaker Podcast Framing & Active Speaker Tracking)  
**Governing Standard:** `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md` & `MASTER_ENGINEERING_RULEBOOK.md`  
**Date Submitted:** 2026-11-04  
**Author / Systems Architect:** Principal Video Systems Architect  
**Reviewer / QA Lead:** Independent QA Lead & Verification Reviewer  
**Status:** **`PENDING OWNER APPROVAL (STOP GATE ACTIVE)`**  
**Readiness Disposition:** **`CER READY FOR OWNER APPROVAL`**  

---

## 1. Executive Summary & Change Request

This Change Exception Record requests formal authorization to apply a targeted, minimal defect repair to Domain L7 frozen code in [`backend/services/advanced_podcast_engine.py`](file:///d:/automation%20video%20clips/clipforge/backend/services/advanced_podcast_engine.py).

The repair strictly separates **FFmpeg process execution success** from the **detected scene cut count**, ensuring that valid single-camera videos containing zero editorial cuts are accepted as authoritative zero-cut detections without erroneously triggering the OpenCV fallback.

### Non-Negotiable Scope Guardrails:
- **Zero changes** to scene detection thresholds (`scdet_threshold = 17.5`, `min_shot_duration = 0.8s`).
- **Zero changes** to crop geometry, face tracking, identity assignment, or active-speaker classification.
- **Zero changes** to public data contracts: `detect_camera_cuts` will continue returning contiguous `List[Tuple[float, float]]` intervals.
- **Zero changes** to database schemas, Celery tasks, API endpoints, or frontend contracts.
- **Zero changes** to caption/subtitle invariants: strictly preserves the zero subtitle/caption invariant and internal Whisper transcription capability for analysis.

---

## 2. Preflight State & Environment Runtime Boundaries

### 2.1 Repository & Working Tree State
The following environment baseline was verified immediately prior to submitting this revised CER:
- **Repository Root:** `D:\automation video clips\clipforge`
- **Active Git Branch:** `feature/layout`
- **Current HEAD Commit:** `68b9bcd7d3688c6bd8feb781d98df72d14351e97`
- **Existing Modified Files in Working Tree:** 40 pre-existing modified files (including database models, channel monitors, layout engine, publisher, and frontend components) — strictly preserved without disturbance.
- **SHA-256 Hashes of Protected Artifacts:**
  - `backend/services/advanced_podcast_engine.py`: `65baa3edf1d921c94f9c912162e15f2fc2c407013063fba39cb001cf3368a9f4` (**UNTOUCHED**)
  - `docs/engineering/LOGIC_FREEZE_LEDGER.md`: `b14619d681f484f5e44b57489c4c171d871f914d5899e3569f7e117a27376bb0` (**UNTOUCHED**)
  - `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md`: `13c895a92099da0ac790a2d5fad9decd1dbf3370c857c727e18f57b194c814ce` (**UNTOUCHED**)
  - `backend/tests/test_zero_cut_fallback.py`: `7aad42aaef303a0096d62dc54318be474a2beba207948588033dea6fddad95de` (**UNTOUCHED**)
  - `uploads/authentic_podcast_test.mp4`: `8144a74a30ddebbbdb1946c43bbddd018e4b7891aedd31ddcb846d326ff7e4c0` (**UNTOUCHED**)

### 2.2 Strict Python Runtime Boundary Distinction
This CER explicitly distinguishes the local development and target production runtimes:
- **Host Execution Environment:** Python 3.12.10 (AMD64, Windows 11) using host FFmpeg `N-123074-g4e32fb4c2a-20260228`. All pre-approval defect reproductions and unit test dry runs reported herein were executed on this environment.
- **Target Production Container Runtime:** Python 3.11.16 (`python:3.11-slim`, as defined in `clipforge/backend/Dockerfile` and the `clipforge_backend` service in `docker-compose.yml`).
- **Runtime Execution Status:**
  - *Host Python 3.12.10:* Tests executed and verified (1 failed as expected pre-patch defect proof, 10 passed).
  - *Production Python 3.11.16:* **NOT YET EXECUTED.** Under Rule 4, no container rebuilds or production executions may occur prior to owner approval. Post-approval implementation verification must include execution within the isolated Python 3.11.16 target container or equivalent clean Python 3.11 virtual environment.

---

## 3. Current Source Inspection & Call Hierarchy

### 3.1 Source Location & Call Hierarchy
- **File:** [`backend/services/advanced_podcast_engine.py`](file:///d:/automation%20video%20clips/clipforge/backend/services/advanced_podcast_engine.py)
- **Target Function:** `detect_camera_cuts(video_path: Path, cut_threshold: float = 0.35, min_shot_duration: float = 0.8, sample_fps: float = 5.0, scdet_threshold: float = 17.5) -> List[Tuple[float, float]]` (Lines 450–578).
- **Direct Downstream Callers:**
  1. Line 939: `shots = detect_camera_cuts(video_path)` inside `build_shot_schedule()` (line 926).
  2. Line 1350: `shots = detect_camera_cuts(video_path)` inside `build_fixed_boundary_schedule()` (line 1336).
  3. Line 1863: `shots = detect_camera_cuts(video_path)` inside `build_visibility_driven_schedule()` (line 1853).
- **Existing Return Contract:** `List[Tuple[float, float]]` representing ordered, non-overlapping `(start_time, end_time)` intervals covering the video duration.

### 3.2 Exact Current Implementation (Lines 486–525)
```python
    cut_timestamps: List[float] = [0.0]

    # Primary strategy: FFmpeg native scene-change detector filter (scdet)
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    scdet_succeeded = False
    try:
        cmd = [
            ffmpeg_bin, "-hide_banner", "-nostats",
            "-i", str(video_path),
            "-vf", f"scdet=threshold={scdet_threshold}",
            "-f", "null", "-"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        scdet_times: List[float] = []
        for line in proc.stderr.splitlines():
            if "lavfi.scd.time" in line:
                m = re.search(r"lavfi\.scd\.time:\s*([\d\.]+)", line)
                if m:
                    t = round(float(m.group(1)), 2)
                    if 0.05 < t < (duration - 0.05):
                        scdet_times.append(t)

        if scdet_times:
            scdet_times.sort()
            for t in scdet_times:
                if (t - cut_timestamps[-1]) >= min_shot_duration:
                    cut_timestamps.append(t)
            scdet_succeeded = True
    except Exception as e:
        logger.debug(f"FFmpeg scdet execution unavailable or timed out: {e}")
        scdet_succeeded = False

    # Fallback or complementary: Multi-signal OpenCV frame-difference analysis
    # Triggers if scdet failed, returned 0 cuts on a video with duration > 2.5 * min_shot_duration,
    # or for synthetic fixtures where scdet threshold does not trigger.
    if not scdet_succeeded or (len(cut_timestamps) == 1 and duration > (min_shot_duration * 2.0)):
        cap = cv2.VideoCapture(str(video_path))
        # ... [executes expensive OpenCV frame-difference analysis] ...
```

---

## 4. Root Cause Analysis: The Two Compounding Fallback Conditions

The current implementation suffers from two compounding defects that prevent valid single-camera zero-cut footage from completing without an unwarranted fallback:

### 4.1 Condition A — Execution-State Defect (Line 513)
`scdet_succeeded = True` is indented strictly inside `if scdet_times:`.
When FFmpeg executes with exit code 0 on a single-camera video containing no camera transitions, `scdet_times` is empty (`[]`). As a result, the code block is skipped, leaving `scdet_succeeded = False`. This conflates "FFmpeg failed to execute" with "FFmpeg executed successfully and found 0 cuts."

### 4.2 Condition B — Forced Fallback on Zero Cuts (Line 521)
The fallback evaluation clause states:
```python
if not scdet_succeeded or (len(cut_timestamps) == 1 and duration > (min_shot_duration * 2.0)):
```
Because `cut_timestamps` initializes to `[0.0]`, a zero-cut video always has `len(cut_timestamps) == 1`. Whenever the video duration exceeds $2.0 \times 0.8\text{s} = 1.6\text{s}$, the right-hand clause `(len(cut_timestamps) == 1 and duration > 1.6)` evaluates to `True`.

### 4.3 Why Fixing Only Condition A Is Completely Insufficient
If an engineer only fixes Condition A by setting `scdet_succeeded = True` when `proc.returncode == 0`, Condition B would still evaluate to `True` on any video longer than 1.6 seconds because `len(cut_timestamps)` remains 1. The OpenCV fallback would **still be unconditionally triggered**!

Therefore, both conditions must be addressed in tandem:
1. **Condition A Resolution:** `scdet_succeeded` must reflect process return code and stderr health, not timestamp count.
2. **Condition B Resolution:** The forced fallback clause `or (len(cut_timestamps) == 1 and duration > (min_shot_duration * 2.0))` must be **completely removed**.

---

## 5. Verified Empirical Defect Reproduction

To prove the defect before touching any production code, an automated regression test was written in [`backend/tests/test_zero_cut_fallback.py`](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_zero_cut_fallback.py).

When executed against current unpatched code (`65baa3edf1d921c94f9c912162e15f2fc2c407013063fba39cb001cf3368a9f4`) on host Python 3.12.10:
```powershell
python -m pytest backend/tests/test_zero_cut_fallback.py -v
```
**Empirical Result:**
```
FAILED backend/tests/test_zero_cut_fallback.py::TestZeroCutFallbackGovernance::test_scenario_1_successful_ffmpeg_zero_cuts_no_fallback
AssertionError: DEFECT DETECTED: Fallback was invoked (25 calls) despite clean FFmpeg execution!
assert 25 == 0
 +  where 25 = <MagicMock name='compute_normalized_hsv_hist' id='...'>.call_count
```
On a 5.0-second single-shot video fixture, `compute_normalized_hsv_hist` was called 25 times (5 fps $\times$ 5.0s) because both Condition A and Condition B forced the fallback to run.

---

## 6. Official FFmpeg Specification, Execution Terminology & Boundary Policy

### 6.1 Technical Specification of `vf_scdet.c`
Per the official FFmpeg filter documentation (https://ffmpeg.org/ffmpeg-filters.html) and source implementation in `libavfilter/vf_scdet.c`:
- `lavfi.scd.mafd` is the Mean Absolute Frame Difference computed between adjacent frames.
- `lavfi.scd.score` is the normalized change score in range [0, 100].
- `lavfi.scd.time` is logged to stderr via `av_log(ctx, AV_LOG_INFO, "lavfi.scd.score: %.3f, lavfi.scd.time: %s\n", score, ...)` **only when `score >= threshold`**.
- When `score < threshold` for all frames, no `lavfi.scd.time` line is emitted to stderr.
- **Empirical Host Verification:** Telemetry from the installed FFmpeg binary on `uploads/authentic_podcast_test.mp4` confirms the exact emitted format:
  `[Parsed_scdet_0 @ 000001a982dcd680] lavfi.scd.score: 22.267, lavfi.scd.time: 2.24`
  The token `2.24` represents time in seconds with sub-second precision, which converts cleanly via `float()`.

### 6.2 Precise Execution & Semantic Terminology
To avoid over-claiming semantic certainty, the CER strictly adheres to four precise terms:
1. **Process execution success:** The FFmpeg subprocess completed and returned exit code zero (`proc.returncode == 0`).
2. **Detector output:** The `scdet` filter emitted zero or more timestamp lines meeting `score >= 17.5`.
3. **Accepted zero-event result:** A process-successful invocation produced no valid `lavfi.scd.time` events under the existing fault-tolerant command. By project policy, this result is accepted as authoritative for the baseline detector without invoking OpenCV.
4. **Semantic limitation:** Zero threshold events do **not** prove that the source is genuinely single-camera in an absolute semantic sense, that no editorial cuts exist below threshold 17.5, or that every single frame was decoded without recoverable bitstream errors. Preflight `cv2.VideoCapture` at line 465 confirms only container readability and header duration; it does not decode every frame end-to-end. Furthermore, the existing command does not pass `-xerror` or `-max_error_rate 0.0`. Recoverable decode glitches may occur while FFmpeg exits 0. Accepting clean threshold-negative output is a domain governance policy for the established baseline, not an infallible semantic guarantee.

### 6.3 Stricter Metadata Validation Contract
If `lavfi.scd.time` appears in stderr, the token must be strictly validated. The CER establishes the following handling policy:

| Telemetry / Event Pattern | Classification | Proposed Handling | Fallback Invoked? |
| :--- | :--- | :--- | :---: |
| **FFmpeg exits 0; no `lavfi.scd.time` lines** | **Accepted zero-event result** | Accept baseline zero-event result; return `[(0.0, duration)]`. | **NO** |
| **FFmpeg exits 0; valid timestamp events** | **Successful detection** | Preserve valid detected cuts; partition into shot intervals. | **NO** |
| **FFmpeg exits non-zero (`returncode != 0`)** | **Execution failure** | Log error; invoke established OpenCV fallback. | **YES** |
| **FFmpeg binary missing (`shutil.which` None)** | **Execution failure** | Log error; invoke established OpenCV fallback. | **YES** |
| **FFmpeg process launch exception (`OSError`)** | **Execution failure** | Log exception; invoke established OpenCV fallback. | **YES** |
| **FFmpeg times out (`TimeoutExpired`)** | **Execution failure** | Log timeout; invoke established OpenCV fallback. | **YES** |
| **Key `lavfi.scd.time` present, value unparseable** | **Metadata parsing failure** | Flag `metadata_corrupt = True`; clear partial cuts; invoke fallback. | **YES** |
| **Timestamp contains NaN or Infinity** | **Invalid timestamp** | Flag `metadata_corrupt = True`; clear partial cuts; invoke fallback. | **YES** |
| **Timestamp negative (`val < 0.0`)** | **Out-of-bounds timestamp** | Flag `metadata_corrupt = True`; clear partial cuts; invoke fallback. | **YES** |
| **Timestamp strictly exceeds duration (`val > duration`)** | **Out-of-bounds timestamp** | Flag `metadata_corrupt = True`; clear partial cuts; invoke fallback. | **YES** |
| **Timestamp within 50ms boundary margin (`[0.0, 0.05]` or `[dur - 0.05, dur]`)** | **Boundary transition** | Accept metadata as valid; intentionally exclude from cut list (boundary margin); no fallback. | **NO** |
| **Mixed valid and corrupt timestamp events** | **Partial / corrupt output** | Reject partial detections; clear `scdet_times`; invoke fallback. | **YES** |

### 6.4 The 50ms Boundary-Margin Evaluation & Downstream Interval Floor
The parser condition `0.05 < t < (duration - 0.05)` is evaluated against the 25 FPS frame interval ($40\text{ms}$) and downstream interval filtering:

| Case | Video Duration | Event Timestamp | Margin Check `0.05 < t < dur - 0.05` | 0.8s Min-Shot Guard `t - last >= 0.8` | Downstream 100ms Filter `e - s >= 0.1` | Final Returned Outcome & Effect on Video Coverage |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Start 40 ms** | 5.00 s | 0.04 s | Excluded ($0.04 \le 0.05$) | Not reached | Not reached | Excluded by 50ms margin. Video covered `[0.0, 5.0]`. |
| **Start exactly 50 ms** | 5.00 s | 0.05 s | Excluded ($0.05 \le 0.05$) | Not reached | Not reached | Excluded by strict inequality. Video covered `[0.0, 5.0]`. |
| **Start 80 ms** | 5.00 s | 0.08 s | Passes ($0.08 > 0.05$) | Discarded ($0.08 - 0.0 < 0.8$) | Not reached | Discarded by 0.8s minimum shot duration guard. Video covered `[0.0, 5.0]`. |
| **End 40 ms** | 5.00 s | 4.96 s | Excluded ($4.96 \ge 4.95$) | Not reached | Not reached | Excluded by 50ms margin. Video covered `[0.0, 5.0]`. |
| **End exactly 50 ms** | 5.00 s | 4.95 s | Excluded ($4.95 \ge 4.95$) | Not reached | Not reached | Excluded by strict inequality. Video covered `[0.0, 5.0]`. |
| **End 80 ms** | 5.00 s | 4.92 s | Passes ($4.92 < 4.95$) | Passes ($4.92 - \text{prev} \ge 0.8$) | Final tail $(4.92, 5.00)$ discarded ($0.08 < 0.1$) | **Pre-existing downstream limitation:** Cut is accepted at 4.92s, but downstream lines 563–578 discard the 80ms tail, leaving intervals covering `[0.0, 4.92]`. |

#### Boundary Analysis Findings:
1. **What the 50 ms margin guarantees:** It prevents events occurring within 50 ms of the stream boundaries from creating invalid sub-100ms intervals at the beginning of the video or near the end.
2. **What the 50 ms margin does NOT guarantee:** If a cut occurs between $\text{duration} - 0.10$ and $\text{duration} - 0.05$ (such as at $t = 4.92\text{s}$ on a 5.00s video), it passes the 50 ms margin. Downstream line 564 appends `5.00`, but downstream line 572 evaluates `if e - s >= 0.1:` ($5.00 - 4.92 = 0.08 < 0.1$) and **discards the final 80 ms tail interval**.
3. **Architectural Disposition:** Under this CER, downstream lines 563–578 are **not modified**, maintaining strict compliance with Rule 18 and keeping implementation scope bounded to lines 488–525. This tail-interval truncation is an existing architectural limitation of downstream interval construction, documented for future review.

---

## 7. Reconciliation of Benchmark Cut Counts (30 Cuts vs. 93 Shots)

A forensic audit was conducted to reconcile the apparent discrepancy between the 30 cuts in the independent ground-truth v3 reference and the 93 count mentioned in earlier reports:

### 7.1 Source Data Provenance & Separate Accounting
The empirical figures originate from distinct evaluation windows and artifact layers:

1. **Certified Ground-Truth Window (0–300.0s):**
   - Independent Ground Truth Reference (`authentic_podcast_ground_truth_independent_v3.json`): **30 annotated physical editorial camera cuts**.
     - Window 1 (0.0s – 180.0s): **21 physical cuts**.
     - Window 2 (180.0s – 300.0s): **9 physical cuts**.
   - **4 Graphic Inserts** (e.g., lower-third banner overlays at frames 939, 1932, 2933, 6931) were explicitly identified and excluded from physical camera-cut scoring.
   - FFmpeg `scdet=17.5` detector output over 0–300s: Exactly **30 camera cuts** (21 in Window 1, 9 in Window 2), achieving **100% precision and 100% recall (F1 = 1.00)**.
2. **Full-File Smoke Run (0–981.08s):**
   - When `detect_camera_cuts()` executes across the **entire 16-minute source video** (`uploads/authentic_podcast_test.mp4`), the detector reports **92 cut timestamps** across the entire duration.
   - Partitioning a 981.08s video by 92 cut points produces **93 resulting shot intervals** (`shots = [(0.0, t1), (t1, t2), ..., (t92, 981.08)]`).
   - Recorded in `backend/benchmarks/baseline_0_reproduction.json` as `"shot_count": 93`.
3. **Unannotated Range (300.0s to 981.08s):**
   - In `authentic_podcast_ground_truth_independent_v3.json`, Window 3 (300.0s to 981.08s) is explicitly marked `UNANNOTATED_OPEN`. Detector output in this range has **not** been independently accuracy-validated.
   - **Acceptance Rule:** Acceptance testing against the ground-truth benchmark is certified **strictly on the 30 physical cuts in the 0–300s window**.
   - Scenario 10 is retained **strictly as an end-to-end full-file smoke test** asserting that the whole video partitions into 93 intervals without unhandled exception. It does **not** assert that all 92 events are confirmed physical cuts or claim full-video precision/recall.

---

## 8. Double-Failure Behavior & Return Contract Specification

### 8.1 Distinction of Execution States
The CER formally distinguishes three outcomes of `detect_camera_cuts()`:
1. **Accepted Zero-Event Result (Success):** FFmpeg executes cleanly with exit code 0 and finds zero scene cuts meeting threshold 17.5. By project policy, the function accepts this baseline result and returns `[(0.0, duration)]`.
2. **OpenCV Fallback Detections (Recovered Failure):** FFmpeg fails to execute; OpenCV fallback successfully processes sampled frames and returns cuts or intervals based on pixel/edge/hist signals.
3. **Double Execution Failure (Graceful Degradation):** FFmpeg fails to execute (e.g. exit code 1 or missing) AND OpenCV fails (e.g. video file corrupt, unreadable frames).
   - In this double-failure state, `cut_timestamps` remains `[0.0]`. Line 564 appends `final_time = round(duration, 2)` $\to [0.0, \text{final\_time}]$.
   - Line 573 constructs `shots = [(0.0, final_time)]`.
   - Because `shots` is non-empty, any warning placed inside `if not shots:` would never be reached.
   - **Architectural Decision:** To keep the implementation minimal, strictly bounded to lines 488–525, and avoid altering downstream lines 563–578, **no logging changes to line 576 are proposed.** The existing function's natural graceful degradation behavior is preserved intact: it safely returns `[(0.0, duration)]` to prevent pipeline abort.
   - **Contract Clarification:** This single interval is documented as **graceful degradation**, NOT validated single-camera footage.

### 8.2 Preservation of Return Contract
No public return-type change or schema mutation is authorized. The return contract remains strictly:
`List[Tuple[float, float]]`

---

## 9. Architecture Option Evaluation & Selection

### 9.1 Evaluation Matrix

| Architectural Option | Description | Pros | Cons | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Option A: Minimal Execution-State Separation (Recommended)** | Track `scdet_succeeded: bool`, `scdet_times: List[float]`, and `scdet_error: Optional[str]` via local variables. Decouple `proc.returncode == 0` from cut count. | Minimal blast radius (~25 lines); zero changes to classes, module exports, or memory footprint; preserves `List[Tuple[float, float]]` return contract; transparent to all callers. | None for internal procedural scope. | **SELECTED FOR IMPLEMENTATION** |
| **Option B: Structured Detector Result Object** | Introduce a new class: `class ScdetExecutionResult(succeeded: bool, cuts: List[float], error: Optional[str])`. | Formal object representation. | Adds unnecessary class abstraction and runtime overhead to frozen module; increases diff size without providing caller value; violates Rule 18 (make the smallest sufficient change). | **REJECTED** |

### 9.2 Verification of Existing Imports
Inspection of [`backend/services/advanced_podcast_engine.py`](file:///d:/automation%20video%20clips/clipforge/backend/services/advanced_podcast_engine.py) confirms:
- Line 10: `import math` (already present).
- Line 14: `from typing import List, Dict, Any, Tuple, Optional` (`Optional` is already imported).
No new imports are required for Option A.

---

## 10. Proposed Minimal Implementation (Diff)

Under Option A, the primary detector logic in `detect_camera_cuts` will be modified as follows upon owner approval (strictly restricted to lines 488–525, leaving all downstream lines untouched):

```diff
--- a/backend/services/advanced_podcast_engine.py
+++ b/backend/services/advanced_podcast_engine.py
@@ -488,6 +488,7 @@ def detect_camera_cuts(
     # Primary strategy: FFmpeg native scene-change detector filter (scdet)
     ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
     scdet_succeeded = False
+    scdet_error: Optional[str] = None
     try:
         cmd = [
             ffmpeg_bin, "-hide_banner", "-nostats",
@@ -496,25 +497,49 @@ def detect_camera_cuts(
             "-f", "null", "-"
         ]
         proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
+        if proc.returncode != 0:
+            scdet_error = f"FFmpeg exited with non-zero code {proc.returncode}"
+            logger.warning(f"FFmpeg scdet execution failed: {scdet_error}")
+        else:
+            scdet_succeeded = True
+
         scdet_times: List[float] = []
-        for line in proc.stderr.splitlines():
-            if "lavfi.scd.time" in line:
-                m = re.search(r"lavfi\.scd\.time:\s*([\d\.]+)", line)
-                if m:
-                    t = round(float(m.group(1)), 2)
-                    if 0.05 < t < (duration - 0.05):
-                        scdet_times.append(t)
-
-        if scdet_times:
-            scdet_times.sort()
-            for t in scdet_times:
-                if (t - cut_timestamps[-1]) >= min_shot_duration:
-                    cut_timestamps.append(t)
-            scdet_succeeded = True
+        metadata_corrupt = False
+        if scdet_succeeded:
+            for line in proc.stderr.splitlines():
+                if "lavfi.scd.time" in line:
+                    m = re.search(r"lavfi\.scd\.time:\s*([^\s,]+)", line)
+                    if not m:
+                        metadata_corrupt = True
+                        break
+                    try:
+                        val = float(m.group(1))
+                    except (ValueError, OverflowError):
+                        metadata_corrupt = True
+                        break
+
+                    # Reject NaN, Infinity, negative timestamps, or timestamps strictly greater than duration
+                    if math.isnan(val) or math.isinf(val) or val < 0.0 or val > duration:
+                        metadata_corrupt = True
+                        break
+
+                    t = round(val, 2)
+                    # Exclude near-boundary transitions within the intentional 50ms margin
+                    # [0.0, 0.05] and [duration - 0.05, duration] cannot form valid >= 0.1s shot intervals
+                    if 0.05 < t < (duration - 0.05):
+                        scdet_times.append(t)
+
+            if metadata_corrupt:
+                scdet_times.clear()
+                scdet_succeeded = False
+                scdet_error = "Malformed or out-of-bounds lavfi.scd.time metadata in FFmpeg stderr"
+                logger.warning(f"FFmpeg scdet metadata corruption detected: {scdet_error}")
+            elif scdet_times:
+                scdet_times.sort()
+                for t in scdet_times:
+                    if (t - cut_timestamps[-1]) >= min_shot_duration:
+                        cut_timestamps.append(t)
     except Exception as e:
         logger.debug(f"FFmpeg scdet execution unavailable or timed out: {e}")
         scdet_succeeded = False
+        scdet_error = str(e)
 
-    # Fallback or complementary: Multi-signal OpenCV frame-difference analysis
-    # Triggers if scdet failed, returned 0 cuts on a video with duration > 2.5 * min_shot_duration,
-    # or for synthetic fixtures where scdet threshold does not trigger.
-    if not scdet_succeeded or (len(cut_timestamps) == 1 and duration > (min_shot_duration * 2.0)):
+    # Fallback: Multi-signal OpenCV frame-difference analysis
+    # Triggers ONLY if FFmpeg scdet genuinely failed to execute (missing binary, non-zero exit code, timeout, corrupt metadata).
+    # A successful execution returning zero cuts is an authoritative single-shot video and MUST NOT trigger fallback.
+    if not scdet_succeeded:
+        logger.info(f"Invoking OpenCV multi-signal camera cut fallback due to: {scdet_error}")
         cap = cv2.VideoCapture(str(video_path))
```

---

## 11. Comprehensive Risk & Mitigation Matrix

| Risk / Scenario | Analysis & Failure Mode | Mitigation & Architecture Guard | Required Evidence |
| :--- | :--- | :--- | :--- |
| **1. Multi-cut video regression** | Valid cuts dropped or misaligned. | Parsing loop, sorting, and `min_shot_duration` deduplication logic are 100% preserved. | All 13 cut evaluator tests and multi-cut fixtures pass identically. |
| **2. Single-camera video regression** | Fallback invoked or phantom cuts hallucinated. | Condition B removed; `scdet_succeeded = True` on exit 0. | Test Scenario 1 asserts `mock_hist.call_count == 0` and `len(shots) == 1`. |
| **3. Low-score camera transitions** | Subtle cuts with score $< 17.5$ not detected by FFmpeg. | FFmpeg `scdet=17.5` is the project-established baseline detector. Accepted zero-event result is a baseline policy, not an infallible semantic guarantee. | Test Scenario 10 preserves authentic benchmark results. |
| **4. Minimum-shot duration guard** | Rapid transitions $< 0.8\text{s}$ oversegment. | Guard `(t - cut_timestamps[-1]) >= min_shot_duration` is preserved unchanged. | Verified in Test Scenario 3. |
| **5. Malformed metadata** | Corrupt/NaN tokens silently treated as zero cuts. | Explicit regex extraction and `float()` validation. Corrupt tokens set `scdet_succeeded = False` and trigger fallback. | Test Scenario 8 asserts fallback invocation on corrupt metadata. |
| **6. Out-of-bounds timestamps** | Negative or $> \text{duration}$ timestamps silently dropped. | Explicit `val < 0.0 or val > duration` check sets `metadata_corrupt = True`, clearing partial cuts and invoking fallback. | Test Scenarios MV-1 and MV-2 assert fallback invocation. |
| **7. Mixed valid & malformed tokens** | Partial cuts accepted while others dropped. | Loop terminates immediately on corrupt token, clears `scdet_times`, and triggers fallback. | Test Scenario MV-8 asserts fallback on mixed corrupt stream. |
| **8. FFmpeg timeout** | Process hangs on abnormal media. | `timeout=120` caught in `except Exception as e`, setting `scdet_succeeded = False`. | Test Scenario 7 asserts fallback is invoked upon `TimeoutExpired`. |
| **9. FFmpeg binary unavailable** | `ffmpeg` missing from PATH in host/container. | `FileNotFoundError` caught, setting `scdet_succeeded = False`. | Test Scenario 4 asserts fallback is invoked when binary is missing. |
| **10. Downstream interval contract** | Downstream schedules expect continuous intervals. | Interval construction `[(cut[i], cut[i+1])]` is preserved unchanged. Zero-cut returns `[(0.0, duration)]`. | Asserted in all test scenarios. |
| **11. Double failure graceful degradation** | Unreadable media crashes framing pipeline. | Double failure returns safe whole-video interval `[(0.0, duration)]` without crash. | Test Scenario 11 asserts graceful degradation. |

---

## 12. Acceptance-Test Inventory & Post-Approval Verification Matrix

### 12.1 Current Test-Function Inventory in `backend/tests/test_zero_cut_fallback.py`
The test file currently contains **11 test functions**. The table below documents their actual scenario coverage, injected conditions, and relationship to each other:

| Test Function Name | Scenario Covered | Injected Condition / Input | Expected Result | Uniqueness / Reconciliation |
| :--- | :--- | :--- | :--- | :--- |
| `test_scenario_1_successful_ffmpeg_zero_cuts_no_fallback` | Core Scenario 1: Clean FFmpeg execution on single-shot fixture | Real synthetic 5.0s single-camera MP4 file (`synthetic_single_shot_video`) | `len(shots) == 1`, `shots == [(0.0, 5.0)]`, `mock_hist.call_count == 0` | **Integration Test:** Tests live FFmpeg binary on disk. Demonstrates pre-patch defect failure (25 calls). |
| `test_scenario_2_successful_execution_one_cut_no_fallback` | Core Scenario 2: Clean FFmpeg run with 1 cut | Mocked `subprocess.run` exit 0, stderr `lavfi.scd.time: 2.50` | `len(shots) == 2`, `shots[0] == (0.0, 2.5)`, `mock_hist.call_count == 0` | **Unique:** Tests single-cut partitioning. |
| `test_scenario_3_successful_execution_multiple_cuts_no_fallback` | Core Scenario 3: Clean FFmpeg run with multiple cuts | Mocked `subprocess.run` exit 0, stderr `time: 1.50` and `3.20` | `len(shots) == 3`, `shots[1] == (1.5, 3.2)`, `mock_hist.call_count == 0` | **Unique:** Tests multi-cut partitioning and sorting. |
| `test_scenario_4_missing_ffmpeg_binary_invokes_fallback` | Core Scenario 4: Missing FFmpeg binary | Mocked `shutil.which` $\to$ `None`, raising `FileNotFoundError` | Fallback invoked (`mock_hist.call_count > 0`), valid shots returned | **Unique:** Tests binary-missing failure path. |
| `test_scenario_5_process_launch_exception_invokes_fallback` | Core Scenario 5: Process launch exception | Mocked `subprocess.run` raising `PermissionError` | Fallback invoked (`mock_hist.call_count > 0`) | **Unique:** Tests launch permission failure. |
| `test_scenario_6_nonzero_exit_code_invokes_fallback` | Core Scenario 6: Non-zero exit code | Mocked `subprocess.run` exit 1, stderr filter error | Fallback invoked (`mock_hist.call_count > 0`) | **Unique:** Tests non-zero exit code error handling. |
| `test_scenario_7_timeout_invokes_fallback` | Core Scenario 7: Subprocess timeout | Mocked `subprocess.run` raising `TimeoutExpired` | Fallback invoked (`mock_hist.call_count > 0`) | **Unique:** Tests execution timeout recovery. |
| `test_scenario_8_malformed_detector_output_with_clean_exit` | Core Scenario 8: Malformed detector output | Mocked `subprocess.run` exit 0, stderr `lavfi.scd.time: corrupt_value\n` | Current test asserts safe return without unhandled exception; post-approval required assertion requires `scdet_succeeded is False` and fallback invoked (`mock_hist.call_count > 0`) | **Unique:** Tests non-numeric token rejection. |
| `test_scenario_9_empty_valid_detector_output_returns_single_shot` | Core Scenario 9: Clean empty detector output (parser isolation) | Mocked `subprocess.run` exit 0, `stderr=""` (empty string) | `len(shots) == 1`, `shots == [(0.0, 5.0)]` | **Unit Parser Test:** Reconciled from duplicate. Specifically isolates empty stderr string parsing, distinct from live binary in Scenario 1. |
| `test_scenario_10_multi_camera_video_preserves_authentic_cuts` | Core Scenario 10: Multi-camera authentic video smoke test | Real broadcast footage `uploads/authentic_podcast_test.mp4` (981.08s) | `len(shots) >= 90` (asserts full 981s file partitions into 93 intervals without unhandled exception) | **Full-Video Smoke Test:** End-to-end smoke test across full 981s file. Certified 30-cut accuracy is separately evaluated in `test_independent_camera_cuts.py`. |
| `test_scenario_11_fallback_failure_returns_safe_whole_video_interval` | Core Scenario 11: Double detector failure graceful degradation | Mocked `subprocess.run` exit 1 and `cv2.VideoCapture.read()` returning `(False, None)` | Returns safe whole-video interval `[(0.0, 5.0)]` | **Unique:** Tests graceful degradation on unreadable media. |

---

### 12.2 Planned Post-Approval Metadata-Validation Edge Case Inventory
The following 9 edge cases will be added to `test_zero_cut_fallback.py` during post-approval implementation:

| Case ID | Injected Telemetry | Classification | Expected Fallback Behavior | Expected `scdet_times` | Regression Assertion |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **MV-1: Negative Timestamp** | `lavfi.scd.time: -1.50` | Out-of-bounds invalid timestamp | Fallback INVOKED (`mock_hist.call_count > 0`) | `[]` (cleared) | `scdet_succeeded is False`, fallback invoked |
| **MV-2: Timestamp > Duration** | `lavfi.scd.time: 8.50` on 5.0s fixture | Out-of-bounds invalid timestamp | Fallback INVOKED (`mock_hist.call_count > 0`) | `[]` (cleared) | `scdet_succeeded is False`, fallback invoked |
| **MV-3: Timestamp == Duration** | `lavfi.scd.time: 5.00` on 5.0s fixture | Boundary timestamp within media | NO fallback; excluded by 50ms margin | `[]` | `shots == [(0.0, 5.0)]`, `mock_hist.call_count == 0` |
| **MV-4: Timestamp = NaN** | `lavfi.scd.time: nan` / `NaN` | Non-numeric invalid float | Fallback INVOKED (`mock_hist.call_count > 0`) | `[]` (cleared) | `scdet_succeeded is False`, fallback invoked |
| **MV-5: Positive Infinity** | `lavfi.scd.time: inf` / `+inf` | Infinite invalid float | Fallback INVOKED (`mock_hist.call_count > 0`) | `[]` (cleared) | `scdet_succeeded is False`, fallback invoked |
| **MV-6: Negative Infinity** | `lavfi.scd.time: -inf` | Infinite invalid float | Fallback INVOKED (`mock_hist.call_count > 0`) | `[]` (cleared) | `scdet_succeeded is False`, fallback invoked |
| **MV-7: Frame-Interval Boundaries (25 FPS)** | `lavfi.scd.time: 0.04` and `4.96` on 5.0s video | Valid 40ms frame intervals within boundary margins | NO fallback; intentionally excluded from cuts | `[]` | `shots == [(0.0, 5.0)]`, `mock_hist.call_count == 0` |
| **MV-8: Valid followed by Malformed** | `time: 2.00` then `time: corrupt` | Partial/corrupt metadata | Fallback INVOKED (`mock_hist.call_count > 0`) | `[]` (cleared, 2.00 discarded) | Terminated early, partial cut cleared, fallback invoked |
| **MV-9: Malformed followed by Valid** | `time: corrupt` then `time: 2.00` | Partial/corrupt metadata | Fallback INVOKED (`mock_hist.call_count > 0`) | `[]` (cleared immediately) | Terminated early, 2.00 never parsed, fallback invoked |

*(Note: Total planned post-approval suite will contain 20 distinct scenarios: 11 core + 9 metadata edge cases. The CER makes no claim that 20 tests have passed prior to implementation).*

---

### 12.3 Post-Approval Verification Commands:
```powershell
# 1. Focused zero-cut regression test suite (11 core + 9 metadata validation cases)
python -m pytest backend/tests/test_zero_cut_fallback.py -v

# 2. Camera-cut evaluator & v3 ground-truth suite (13 tests)
python -m pytest backend/tests/test_independent_camera_cuts.py -v

# 3. Authentic podcast validation gate suite (14 tests)
python -m pytest backend/tests/test_authentic_podcast_validation_gate.py -v

# 4. Target production Docker container verification (Python 3.11.16)
docker run --rm -v "D:\automation video clips\clipforge\backend:/app" clipforge-backend:latest pytest tests/test_zero_cut_fallback.py -v
```

---

## 13. Safe Non-Destructive Rollback Protocol

To protect unrelated pre-existing user modifications (such as changes to `layout_engine.py`, `models.py`, `publisher.py`, and `frontend/`), **destructive Git commands (`git checkout -- ...`, `git reset`, `git restore`, `git clean`) are strictly prohibited.**

### Step-by-Step Controlled Reversion Protocol:
1. **Pre-patch Snapshot:** Immediately prior to patching, copy `advanced_podcast_engine.py` to:
   `clipforge/backend/services/advanced_podcast_engine.py.bak_cer_2026_l7_001`
   and verify its SHA-256 hash matches `65baa3edf1d921c94f9c912162e15f2fc2c407013063fba39cb001cf3368a9f4`.
2. **Reverse Patch Application:** If any post-change regression occurs, restore the exact pre-change lines 488–525 using line-level editing or copying from the verified backup snapshot.
3. **Integrity Verification:** Compute the SHA-256 of `advanced_podcast_engine.py` and confirm it exactly matches `65baa3edf1d921c94f9c912162e15f2fc2c407013063fba39cb001cf3368a9f4`.
4. **Preservation Check:** Run `git status --short` to verify that zero unrelated tracked or untracked user files were altered, staged, or removed.
5. **Regression Verification:** Run `python -m pytest backend/tests/test_independent_camera_cuts.py` to confirm clean restoration of baseline state.

---

## 14. Authorized Implementation Scope

### 14.1 Exact File and Lines Authorized for Implementation (Post-Approval Only):
- [`clipforge/backend/services/advanced_podcast_engine.py`](file:///d:/automation%20video%20clips/clipforge/backend/services/advanced_podcast_engine.py), **Lines 488–525 only**.

### 14.2 Exact Files and Operations Strictly Prohibited:
- **PROHIBITED:** Modifying lines outside 488–525 in `advanced_podcast_engine.py` (downstream interval formation lines 563–578 remain untouched).
- **PROHIBITED:** Modifying [`docs/engineering/LOGIC_FREEZE_LEDGER.md`](file:///d:/automation%20video%20clips/clipforge/docs/engineering/LOGIC_FREEZE_LEDGER.md) before owner approval and post-patch verification.
- **PROHIBITED:** Modifying any database models, Alembic migrations, or database schemas.
- **PROHIBITED:** Modifying Celery tasks, worker queues, or Redis task definitions.
- **PROHIBITED:** Modifying API routes or schemas under `backend/api/`.
- **PROHIBITED:** Modifying frontend components or pages under `frontend/`.
- **PROHIBITED:** Altering detection thresholds (`scdet_threshold = 17.5`, `min_shot_duration = 0.8`).
- **PROHIBITED:** Altering face tracking, smoothing constants, or active-speaker logic.
- **PROHIBITED:** Modifying captions, subtitles, or Whisper transcription scope.
- **PROHIBITED:** Performing real publishing to YouTube.

---

## 15. Governance Ledger Amendment Plan

Upon successful post-approval implementation and 100% passing verification in both host and Docker runtimes, the following entry will be submitted to amend `docs/engineering/LOGIC_FREEZE_LEDGER.md`:

```markdown
| **L7** | Clip outputs and internal analysis | `FROZEN (CER-2026-L7-001 Approved & Verified)` | `backend/services/clip_scorer.py`, `backend/services/advanced_podcast_engine.py`, `backend/services/metadata_generator.py` | `68b9bcd` | Scoring engine, camera-cut detection, active speaker tracking, internal transcription | **PASSED**: `test_zero_cut_fallback.py` (20/20 passed); clean zero-cut handling verified; fallback restricted strictly to execution failures and corrupt metadata; `test_independent_camera_cuts.py` (13/13 passed); `test_authentic_podcast_validation_gate.py` (14/14 passed) | L2, L3, L5, L6 | Subtitle/caption invariant preserved; internal transcription for analysis only |
```

---

## 16. Sign-Off & Approval Stop Gate

| Role | Name / Title | State | Timestamp |
| :--- | :--- | :---: | :--- |
| **Author** | Principal Video Systems Architect | **FINAL REVISION SUBMITTED** | 2026-11-04T01:28:00+05:30 |
| **Independent Reviewer** | Independent QA Lead & Systems Auditor | **RECOMMENDED FOR APPROVAL** | 2026-11-04T01:29:00+05:30 |
| **System Owner** | User / Project Owner | **`PENDING OWNER APPROVAL`** | — |

> [!CAUTION]
> **GOVERNANCE STOP GATE ACTIVE:**
> In accordance with `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md` and Rule 4 of the Master Engineering Rulebook, **no implementation edits to `backend/services/advanced_podcast_engine.py` or `LOGIC_FREEZE_LEDGER.md` may occur until explicit approval is granted by the system owner.**
