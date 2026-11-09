# ClipForge Authentic-Footage Two-Person Dialogue Validation Protocol

**Document Version:** 1.0.0  
**Logic Domain:** L7 (Advanced Multi-Speaker Podcast Framing & Active Speaker Tracking)  
**Status:** **BLOCKED / NOT TESTED** (Awaiting authorized authentic multi-person footage)  
**Authoritative Rule:** Master Engineering Rulebook Rule 15 (Zero Synthetic Substitution for Empirical Proof)

---

## 1. Executive Summary & Purpose

Topic 7 introduces automated multi-speaker framing, shot segmentation, and dynamic active speaker tracking for podcast interviews. While unit tests and mock integration tests verify algebraic geometry, coordinate transformations, and state-machine transitions, **production-grade visual validation requires authentic human footage**.

Per ClipForge engineering governance, synthetic fixtures (such as animated colored boxes, static single faces, or artificial synthetic noise) **MUST NOT** be substituted for real two-person dialogue. Until genuine multi-speaker video footage is provided and processed through this protocol, Criterion 7.3 remains classified as **`BLOCKED / NOT TESTED`**.

This document defines the formal, reproducible protocol and quantitative acceptance criteria required to validate Criterion 7.3 once authentic media is provisioned.

---

## 2. Test Media Requirements

The validation test suite requires at least one authentic video file satisfying the following technical specifications:

| Parameter | Minimum Requirement | Recommended Specification |
| :--- | :--- | :--- |
| **Format** | MP4 / H.264 / AAC | MP4 / H.264 / AAC |
| **Resolution** | 1920 × 1080 (16:9 Landscape) | 1920 × 1080 or 4K UHD |
| **Framerate** | 24 fps to 60 fps | 30 fps or 60 fps constant |
| **Duration** | Minimum 120 seconds | 180 – 300 seconds |
| **Participants** | Exactly two distinct human speakers | Two distinct human speakers with contrasting clothing/appearance |
| **Audio** | Clear stereo or dual-mono dialogue | High SNR dialogue with distinct voice characteristics |
| **License / Authorization** | Explicit tenant authorization / CC0 / Open Domain | Permitted for local algorithmic evaluation |

---

## 3. Mandatory Behavioral Intervals & Stress Challenges

The authentic test footage MUST contain verified time-stamped intervals exhibiting the following 8 challenge conditions:

### 3.1 Interval Taxonomy
1. **Interval A (Speaker A Solo, ~20s):** Speaker A speaks continuously while Speaker B remains silent, nodding or taking notes.
2. **Interval B (Speaker B Solo, ~20s):** Speaker B speaks continuously while Speaker A remains silent.
3. **Interval Dual/Overlap (~15s):** Both speakers talk simultaneously, interrupt, or laugh together.
4. **Interval Rapid Alternation (~30s):** Fast conversational turn-taking with utterance durations between 1.0s and 2.5s.
5. **Interval Wide Shot / Reaction (~20s):** Camera angle showing both participants simultaneously (two-shot) where system dynamically chooses reaction shots or side-by-side equal split.

### 3.2 Robustness & Environmental Challenges
6. **Camera Cuts & Angles:**
   - Abrupt visual cuts between wide-angle and close-up views.
   - Distinct camera angles (e.g. 45° profile versus frontal).
7. **Occlusion & Gesturing:**
   - Hand gestures near the mouth, coffee mugs, microphones, or laptops partially occluding the face.
   - Rapid head turns exceeding 60° yaw.
8. **Exit & Re-entry:**
   - One speaker briefly leans out of frame or leaves their seat, followed by re-entry into the same seat.
   - The tracking system MUST re-associate the returning speaker with their previous identity without identity swapping.

---

## 4. Quantitative Acceptance Gates & Metrics

To pass Topic 7 Criterion 7.3, the automated benchmark harness (`backend/benchmarks/benchmark_authentic_podcast.py`) must evaluate model output against verified ground-truth timestamps and achieve the following empirical thresholds:

### 4.1 Shot Boundary Precision & Recall
- **Definition:** Accuracy of detecting natural visual scene changes and speaker transition boundaries without introducing false cut artifacts.
- **Formulas:**
  $$\text{Precision} = \frac{TP_{cuts}}{TP_{cuts} + FP_{cuts}} \ge 95.0\%$$
  $$\text{Recall} = \frac{TP_{cuts}}{TP_{cuts} + FN_{cuts}} \ge 90.0\%$$
- **Tolerance Window:** $\pm 250\text{ ms}$ around human ground-truth boundary.

### 4.2 Active Speaker Identification Accuracy
- **Definition:** The percentage of video frames where the visually framed speaker matches the actual ground-truth dominant speaker.
- **Formula:**
  $$\text{Accuracy}_{speaker} = \frac{\sum_{t=1}^T \mathbb{I}(\text{FramedSpeaker}(t) == \text{ActiveSpeaker}(t))}{T} \ge 92.0\%$$
- **Grace Period:** A 300ms transition latency window is granted following sudden speaker switches to allow smooth camera panning.

### 4.3 False Switch Rate (FSR)
- **Definition:** Unwarranted rapid camera jumping or flipping between participants during pauses, throat clears, or short filler words ("uh-huh", "yeah").
- **Formula:**
  $$\text{FSR} = \frac{\text{Total Unwarranted Camera Switches}}{\text{Total Dialogue Duration in Seconds}} \le 0.05 \text{ switches/sec}$$
  *(Must not exceed 1 false switch per 20 seconds).*

### 4.4 Crop Jitter & Motion Stability
- **Definition:** High-frequency bounding box displacement across consecutive frames when a speaker is stationary.
- **Formula:**
  $$\text{Jitter}_{RMS} = \sqrt{\frac{1}{N} \sum_{i=1}^N (\Delta \text{Center}_x^2 + \Delta \text{Center}_y^2)} \le 2.5 \text{ pixels/frame}$$
- Camera smoothing (exponential moving average / Kalman filter) must eliminate micro-tremors without introducing noticeable lag.

### 4.5 Manual Review Fallback Rate
- **Definition:** The percentage of processed video duration flagged as ambiguous (confidence $< 0.65$ or unresolvable overlap).
- **Threshold:** $\le 8.0\%$ of total clip duration.

---

## 5. Execution Protocol

When authentic interview footage is provisioned, execute the following protocol:

### Step 1: Ingest Media and Annotation
Place the authentic media file in `uploads/authentic_podcast_test.mp4`.
Create a corresponding ground-truth JSON annotation in `uploads/authentic_podcast_ground_truth.json` containing:
```json
{
  "media_path": "uploads/authentic_podcast_test.mp4",
  "duration_sec": 180.0,
  "speakers": ["Speaker_A", "Speaker_B"],
  "speaker_regions": {
    "Speaker_A": {"x": 0.05, "y": 0.15, "width": 0.40, "height": 0.70},
    "Speaker_B": {"x": 0.55, "y": 0.15, "width": 0.40, "height": 0.70}
  },
  "segments": [
    {"start": 0.0, "end": 14.5, "active_speaker": "Speaker_A", "cut_type": "solo"},
    {"start": 14.5, "end": 28.2, "active_speaker": "Speaker_B", "cut_type": "solo"},
    {"start": 28.2, "end": 35.0, "active_speaker": "both", "cut_type": "split"}
  ]
}
```

### Step 2: Execute Automated Acceptance Harness
Run either the dedicated acceptance harness or benchmark script:
```bash
python backend/scripts/run_authentic_podcast_acceptance.py --input uploads/authentic_podcast_test.mp4 --ground-truth uploads/authentic_podcast_ground_truth.json
# or
python backend/benchmarks/benchmark_authentic_podcast.py --input uploads/authentic_podcast_test.mp4 --ground-truth uploads/authentic_podcast_ground_truth.json
```

### Step 3: Exit Codes and Enforcement Gate
The acceptance harness strictly returns standardized POSIX exit codes:
- **`0`**: `PASS` — All 6 quantitative thresholds, zero subtitle streams (`-sn`), and 1080x1920 geometry satisfied.
- **`1`**: `FAIL` — Authentic media provided, but one or more quantitative metrics breached acceptable thresholds.
- **`2`**: `BLOCKED / NOT TESTED` — Media file absent, ground truth missing, or synthetic substitution rejected.

### Step 4: Anti-Synthetic Gate (Master Engineering Rulebook Rule 15)
Per Rule 15, synthetic fixtures (such as test cards, colored rectangles, lavfi generated streams, or files with `synthetic`/`dummy` keywords) are strictly prohibited from being used to claim authentic validation. The gate automatically rejects synthetic media and exits with code 2.

### Step 5: Audit Output Metrics & Artifacts
Inspect generated reports and manifests:
- Results: `backend/benchmarks/benchmark_results.json`
- Canonical Manifest: `docs/engineering/AUTHENTIC_PODCAST_ACCEPTANCE_MANIFEST.json`
- Automated Test Suite: `backend/tests/test_authentic_podcast_validation_gate.py` (13/13 passing)

---

## 6. Current Verification Declaration

```
=============================================================================
CRITERION 7.3: AUTHENTIC TWO-PERSON INTERVIEW VALIDATION
WORK ITEM:     PODCAST-AUTHENTIC-VALIDATION-012
STATUS:        COMPLETED (EVALUATION EXECUTED)
DISPOSITION:   AUTHENTIC VALIDATION EXECUTED (GATE OUTCOME: FAIL)
SOURCE MEDIA:  "The Morning Routine That Can Change Your Life | Dr. Sweta Adatia | Raj Shamani Clips"
               URL: https://youtu.be/0GjbIOS9Q90
               SHA-256: 8144a74a30ddebbbdb1946c43bbddd018e4b7891aedd31ddcb846d326ff7e4c0
               File Size: 243,392,976 bytes (232.12 MiB), 1920x1080 @ 25fps, H.264/AAC
RENDERED OUT:  outputs/authentic_podcast_acceptance_rendered.mp4
               SHA-256: fb3e72892a7901de5774fa51c116ffb4ddc7a514e5381c58bdd5406b1e0abf96
               File Size: 41,328,687 bytes (39.41 MiB), 1080x1920 vertical canvas
INVARIANTS:    Zero subtitle streams (-sn): PASS (0 streams observed)
               1080x1920 vertical geometry: PASS (exact 9:16 verified)
METRICS:       - False Switch Rate: 0.0000 <= 0.05 switches/s (PASS)
               - Crop Jitter RMS:   1.75 <= 2.5 px/frame (PASS)
               - Shot Precision:    0.0000 < 0.95 (FAIL)
               - Shot Recall:       0.0000 < 0.90 (FAIL)
               - Speaker Accuracy:  0.4750 < 0.92 (FAIL)
               - Manual Review Rate: 0.4878 > 0.08 (FAIL)
ROOT CAUSE:    detect_camera_cuts in L7 relies on whole-frame HSV histogram correlation
               with cut_threshold=0.40. In studio broadcasts where background wall
               and lighting remain constant, cuts between wide and solo shots have
               correlation >= 0.65, grouping 341.2s into a single shot.
REMEDIATION:   Documented defect in L7 frozen logic. Proposed L7 modification requires
               local face-presence aware cut detection or adaptive thresholding.
=============================================================================
```


