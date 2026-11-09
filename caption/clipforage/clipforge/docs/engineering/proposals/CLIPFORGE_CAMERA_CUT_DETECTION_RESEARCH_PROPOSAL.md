# ClipForge — Camera-Cut / Shot-Boundary Detection Research & Proposal

**Document type:** Engineering research, repository comparison and implementation proposal  
**Work item:** `PODCAST-CUT-DETECTION-013`  
**Target repository location:** `docs/engineering/proposals/CLIPFORGE_CAMERA_CUT_DETECTION_RESEARCH_PROPOSAL.md`  
**Prepared:** 3 November 2026  
**Status:** RESEARCH / PROPOSAL ONLY — NOT AN IMPLEMENTATION AUTHORIZATION  
**Scope:** Detect intentional editorial shot changes in podcast/interview footage and supply correct shot intervals to the existing Podcast visibility/composition pipeline.

---

## 1. Executive summary

ClipForge's recent authentic-footage acceptance run on the owner-supplied interview reports that the current cut detector missed editorial changes between a two-person wide shot and individual participant close-ups. The report attributes this to a full-frame HSV histogram-correlation approach: the set/background and lighting remain similar while the camera angle changes, so the global histogram remains similar enough that the transition is missed.

The problem is not that the camera is unstable. The video is edited using intentional camera cuts. ClipForge must detect those cuts and treat each resulting shot independently. It must not stabilize different editorial angles into a single long shot.

A search of public implementations found established, reusable shot-boundary systems:

1. **PySceneDetect** — a maintained Python/OpenCV library with content, adaptive, histogram, perceptual-hash and threshold detectors; BSD-3-Clause license. Its adaptive/content detectors are suitable classical baselines. Its published benchmark data also warns that histogram-only detection can underperform substantially on hard cuts in short web clips.
2. **TransNet V2** — a pretrained neural shot-boundary detector with an official GitHub repository, inference code and a PyTorch inference implementation; repository license is MIT. Its authors report benchmark F1 values on ClipShots, BBC Planet Earth and RAI. These published results are promising but are not proof of performance on ClipForge's exact podcast source.
3. **FFmpeg `scdet`** — a lightweight frame-difference/scene-score filter already available in FFmpeg. It is a useful low-dependency baseline or auxiliary signal, not a sufficiently proven sole solution for this particular footage.
4. **AutoShot** — a research implementation and short-video dataset from CVPRW 2023. The paper reports improvements over TransNetV2 on its evaluation datasets. It is worth an optional research comparison, but its repository's documented setup depends on externally hosted model weights/data and should not become an initial production dependency without an isolated compatibility and provenance review.

### Proposal

Do not immediately replace ClipForge's detector with a library or a guessed threshold. First build a reproducible local bake-off on the full authentic podcast video and additional representative clips where available. Compare:

- Current ClipForge detector (baseline).
- PySceneDetect `AdaptiveDetector`.
- PySceneDetect `ContentDetector` (including edge-change weighting as a separately measured configuration).
- PySceneDetect `HashDetector` and `HistogramDetector` as controls, not presumed winners.
- FFmpeg `scdet` as a baseline/auxiliary signal.
- TransNet V2 pretrained inference as the primary learned-model candidate.
- AutoShot only if its weights, dependencies and license/provenance are practical in the existing environment.

Select an approach only after the candidate outputs are compared against independently annotated authentic shot boundaries. Keep shot detection separate from participant identity, active-speaker recognition and composition classification.

**No library is proven to solve ClipForge's source yet.** The strongest next step is a measured candidate bake-off, not an immediate production rewrite.

---

## 2. Precise problem definition

### 2.1 What ClipForge needs to detect

A *shot boundary* is a transition between consecutive camera shots. In the supplied interview, examples include:

- two-person wide shot → participant A close-up;
- participant A close-up → participant B close-up;
- participant B close-up → two-person wide shot;
- opening/title graphic → interview shot, where applicable.

Those are intentional editorial cuts. A cut can occur even if the studio wall, lighting, table, microphones and overall color palette remain similar.

### 2.2 What shot detection does not establish

Shot detection only identifies **where the camera shot changes**. It does not, by itself, determine:

- who is speaking;
- who is visible;
- whether the shot contains A, B or both;
- whether a visible person is listening or speaking;
- whether two face detections belong to the same participant across a cut.

After a cut is detected, the existing downstream pipeline must independently analyze the new shot for visibility, identity and composition. Do not use “one visible face” as equivalent to “one active speaker”.

### 2.3 Why the current approach may fail

The prior ClipForge report says `detect_camera_cuts()` uses a global HSV histogram correlation with a threshold around `0.40`. A wide shot and a close-up can share most of their background pixels and color distribution. A global histogram discards much of the spatial arrangement that distinguishes those shots. The reported correlation of approximately `0.65–0.75` across some camera switches would therefore remain above the cut threshold.

This explanation is plausible and consistent with the reported result, but Gravitas must re-open the current source and reproduce the values before treating every historical parameter or statement as current fact.

---

## 3. External implementations reviewed

### 3.1 PySceneDetect — classical baseline and practical integration candidate

**Repository:** https://github.com/Breakthrough/PySceneDetect  
**Documentation:** https://www.scenedetect.com/docs/latest/  
**License:** BSD-3-Clause  
**Latest release observed during research:** v0.7.2, dated 11 October 2026.

PySceneDetect is a mature Python/OpenCV-based scene-cut and transition-detection library. Its Python API returns scene intervals, and it supports multiple detector families rather than just one threshold.

Relevant algorithms:

| Detector | Method | Relevance to ClipForge | Caution |
|---|---|---|---|
| `ContentDetector` | Weighted changes between adjacent frames in HSV; can include edge changes | Useful classical hard-cut baseline; adjacent-frame change can respond to a cut even if the background palette is shared | Motion/gestures and camera motion can also create frame differences |
| `AdaptiveDetector` | Content score compared with a rolling local average | Particularly worth testing when the video has variable levels of motion; adaptive local baseline can mitigate some fast-motion false positives | Still a visual heuristic; not guaranteed on similar-looking camera angles |
| `HashDetector` | Perceptual hash comparison between adjacent frames | Low-complexity comparison signal; grayscale hash is less sensitive to pure color changes | Spatial structure is compressed; not guaranteed to distinguish all similar compositions |
| `HistogramDetector` | Histogram differences in Y channel | Useful as a comparator and for some transitions | It remains histogram-based and may repeat the current failure mode |
| `ThresholdDetector` | Brightness crossing for fades to/from black | Useful for fades and black transitions | Not the primary detector for ordinary camera-to-camera hard cuts |

PySceneDetect's own public benchmark page is unusually useful because it publishes detector-by-dataset precision, recall and F1 and describes its matching convention. At the listed v0.7 default settings, the page reports these hard-cut F1 values:

| Detector | BBC Planet Earth | AutoShot dataset | ClipShots hard cuts |
|---|---:|---:|---:|
| AdaptiveDetector | 91.59 | 73.86 | 55.75 |
| ContentDetector | 86.69 | 69.26 | 55.84 |
| HashDetector | 83.10 | 64.84 | 43.98 |
| HistogramDetector | 79.96 | 57.82 | 19.80 |

Important qualification: the page says these scores were measured with v0.7 defaults and that v0.7.2 changed the histogram and hash defaults; benchmark tables were noted as awaiting regeneration. They are not ClipForge-specific results and must not be presented as expected performance on the supplied podcast.

The benchmark page also describes a TRECVID-SBD-style greedy one-to-one nearest-neighbor match with configurable frame tolerance for hard cuts. This is a helpful model for a correct ClipForge evaluator: one prediction must not be credited against multiple ground-truth cuts.

**Assessment:** PySceneDetect is the lowest-friction library to benchmark first. It is Python-native, has an established API, several classical detector options, a permissive BSD license and a current release. It should first be used as an offline candidate, not immediately made a production dependency.

### 3.2 TransNet V2 — learned shot-boundary candidate

**Official repository:** https://github.com/soCzech/TransNetV2  
**Paper:** https://arxiv.org/abs/2008.04838  
**Repository license shown:** MIT  
**Inference:** The repository contains an inference path and a released PyTorch inference implementation.

TransNet V2 is a neural-network approach designed specifically for fast shot-transition detection. Its repository says training the network is not required to run inference; pretrained inference assets/code are provided. The authors publish reevaluated F1 values:

| Dataset | TransNet V2 reported F1 |
|---|---:|
| ClipShots | 77.9 |
| BBC Planet Earth | 96.2 |
| RAI | 93.9 |

These are results reported by the TransNet V2 authors under their evaluation setup. Do not directly compare them numerically with PySceneDetect's benchmark table as if they were generated by one identical code path, parameter sweep and matching configuration. Re-evaluate all candidates through one ClipForge-owned evaluator.

A PyTorch inference package, `transnetv2-pytorch`, also exists on PyPI and describes CPU and CUDA inference. It is a third-party reimplementation; its package license, exact dependency pins, model-weight provenance and reproducibility must be checked independently rather than assumed from the original repository license.

**Assessment:** TransNet V2 is the most important learned-model candidate to test against this authentic edited interview. A trained temporal model may be better suited than global histogram correlation to recognize shot-transition patterns. It may also impose extra model/dependency/runtime costs. The active ClipForge runtime is intentionally retained on Python 3.11.16; do not upgrade Python or disturb the existing PyTorch/MediaPipe/NumPy environment to test it. Use an isolated, reproducible candidate environment or container with pinned dependencies and no impact on the running application.

### 3.3 FFmpeg `scdet` — lightweight baseline / auxiliary signal

**Implementation:** https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_scdet.c  
**Documentation:** https://ffmpeg.org/ffmpeg-filters.html#scdet

FFmpeg implements the `scdet` video filter. Its source exposes a configurable scene-change threshold and a scene-score calculation based on differences between successive frames. The filter can expose per-frame scene-change metadata.

**Assessment:** This candidate has low integration friction because ClipForge already relies heavily on FFmpeg. It is worth measuring as a baseline and possibly as an auxiliary signal. It should not be assumed to solve the same-background issue: a simple difference score is still dependent on how much adjacent frames differ. A similar studio set does not prevent a close-up from producing a substantial frame change, but only the actual footage can establish whether the score is sufficiently separable.

### 3.4 AutoShot — optional research candidate

**Repository:** https://github.com/wentaozhu/AutoShot  
**Paper:** https://arxiv.org/abs/2304.06116  
**Repository license shown:** MIT

AutoShot introduces the SHOT dataset: 853 complete short videos, 11,606 shot annotations and 2,716 high-quality boundary annotations across 200 test videos. The authors report performance improvements against TransNet V2 on SHOT and modest improvements on ClipShots, BBC and RAI.

The repository documents an inference/evaluation workflow and points to model/data hosted via external Google Drive/Baidu links. It is a smaller research repository than PySceneDetect and has a more involved model/weight acquisition process.

**Assessment:** Interesting second-stage candidate because it targets short-form video and reports strong research results. Do not select it first for ClipForge without confirming that the required weight files are obtainable, checksummed, license-compatible, reproducible and usable on the retained Python 3.11 runtime. Do not make a large model or new dependency mandatory merely because its paper reports an improvement on benchmark datasets.

### 3.5 Community comparison harness — useful methodology reference, not a dependency

**Repository:** https://github.com/ravi-movva/shot-boundary-harness

This public harness compares PySceneDetect, TransNetV2 and AutoShot through a common JSON output schema and contains ground-truth evaluation helpers. Its README is useful as an example of reproducible side-by-side experiments. Its sample results are not evidence for ClipForge's footage, and the repository itself should not be imported as a production component without separate maintenance, licensing and code review.

---

## 4. What the research implies for this podcast footage

The supplied source is a professionally edited interview. A shot can switch between cameras while retaining the same room, background, desk and lighting. The detection task is a **shot-boundary detection** problem, not participant tracking and not image stabilization.

The candidate methods have different strengths:

- A global histogram compares color distributions but discards the spatial placement of subjects. It is particularly risky when a wide shot and a close-up share the same set.
- PySceneDetect's content/adaptive detectors inspect adjacent-frame content changes. This is a useful non-neural baseline and may recognize the sudden spatial change at a camera cut.
- TransNet V2 uses learned temporal visual features and is the most important pretrained model candidate for this class of edit.
- FFmpeg `scdet` gives a low-cost adjacent-frame score, useful for a baseline or additional feature.
- Face/participant detection can support downstream shot classification, but it must not be the sole cut signal. A face detector can miss a face, detect a listener, or be affected by gestures and occlusions.

A key architectural separation is required:

1. **Shot-cut detector:** Where did the editor change camera shots?
2. **Per-shot visibility classifier:** Does the new shot contain A, B, both or insufficient evidence?
3. **Identity continuity:** Is the person detected in this shot the same participant A/B as in previous shots?
4. **Active-speaker inference:** Who is speaking in the audio? This is a separate multimodal problem and must not be inferred solely from which camera is showing a close-up.
5. **Crop/tracking engine:** How should the selected composition be framed within the new shot?

A correct shot detector does not by itself prove speaker identity or active-speaker accuracy.

---

## 5. Proposed evaluation bake-off

### 5.1 Candidate matrix

Run these candidates offline against the same source files, timestamps, ground-truth annotations and evaluation script:

| Candidate ID | Detector | Role | Runtime class | Include? |
|---|---|---|---|---|
| BASELINE-0 | Current ClipForge `detect_camera_cuts()` | Reproduce existing result | Existing CPU/OpenCV | Mandatory |
| CLASSIC-1 | PySceneDetect `AdaptiveDetector` | Main classical candidate | CPU | Mandatory |
| CLASSIC-2 | PySceneDetect `ContentDetector` with edge-weighted experiment | Adjacent-frame/edge candidate | CPU | Mandatory |
| CLASSIC-3 | PySceneDetect `HashDetector` and `HistogramDetector` | Controls and diagnostics | CPU | Mandatory |
| FFMPEG-1 | FFmpeg `scdet` | Low-dependency baseline / auxiliary score | CPU | Mandatory |
| ML-1 | TransNet V2 pretrained inference | Main learned candidate | CPU and optional CUDA | Mandatory if isolated runtime is feasible |
| ML-2 | AutoShot pretrained inference | Optional research comparison | Isolated runtime | Optional; only if weights/dependencies are safely obtainable |

Do not merge these outputs into one ensemble before measuring each one independently. First establish each candidate's raw performance. Only then evaluate a hybrid if it offers measurable improvement.

### 5.2 Dataset requirements

Use:

1. The full owner-supplied interview video (not only the first 180 seconds).
2. The previous first-180-second region as a regression subset.
3. At least two additional representative interview/podcast clips if the owner can provide them or if they are already authorized local assets.
4. Existing synthetic test clips only for deterministic unit tests, never as a substitute for authentic evaluation.

The authentic annotations must be made independently of detector outputs. Annotate hard cuts with frame index, timestamp, previous shot description, next shot description, and reviewer provenance. Mark ambiguous transitions rather than inventing labels.

### 5.3 Evaluation methodology

The benchmark must use one ClipForge-owned evaluator for every detector.

Required controls:

- Convert every prediction and ground-truth boundary to a canonical source frame index.
- Record source FPS, frame count, duration, time base and any decoder offset.
- Use greedy one-to-one nearest-neighbor matching; a prediction can match at most one ground-truth boundary and vice versa.
- Report exact-frame metrics and tolerance metrics separately (for example ±1 frame and ±3 frames at 25 FPS).
- Report precision, recall and F1; do not report only accuracy.
- Report true positives, false positives and false negatives.
- Report mean/median absolute boundary timing error for matched cuts.
- Report per-video and per-transition-type results, not only a global pooled score.
- Report runtime, frames per second, peak memory and hardware/software versions.
- Preserve raw per-frame scores and candidate configuration for reproducibility.
- Check that the ground truth has not been built from the detector's own predictions.

The current protocol's acceptance thresholds (precision ≥95%, recall ≥90%) must not be weakened to make a candidate pass. If those thresholds are not statistically meaningful for the amount/type of authentic annotated data, report that as a separate protocol concern and provide confidence/coverage information; do not silently change the gate.

### 5.4 Threshold tuning discipline

Use a tuning interval and a separate hold-out interval/video. Do not tune a threshold on the exact same shots used for final acceptance and then present the result as an independent test.

For learned models, record the exact weight checksum, model version, input frame resize/sampling settings, inference package version and post-processing threshold.

For classical methods, record all constructor arguments, frame sampling, resize, edge settings, minimum scene length and filtering behavior.

### 5.5 Runtime compatibility constraints

The owner's explicit runtime decision is to retain Python 3.11.16. Do not upgrade Python.

- Inspect the current Docker Python version and installed packages before experiments.
- Do not alter the active container, lockfiles or shared dependency set just to try a detector.
- Use a disposable, isolated environment/container for TransNet V2 / AutoShot dependency evaluation.
- Prefer reusing existing FFmpeg/OpenCV infrastructure where it delivers comparable results.
- Measure CPU-only performance. Test CUDA on the existing NVIDIA RTX 3050 only if the isolated environment can safely access it and without changing the stable production runtime.
- Do not download weights from untrusted mirrors. Verify official provenance, hashes and licensing.

---

## 6. Recommended decision framework

The research supports a **benchmark-first decision**, not an immediate hardcoded replacement.

### Candidate path A — PySceneDetect AdaptiveDetector

Advantages:
- Mature, actively maintained Python library.
- BSD-3-Clause license.
- Existing Python API and scene interval output.
- Multiple classical detector types for comparison.
- Published benchmarks and parameter sweep data.
- No large neural model required.

Risks:
- Still heuristic and based on pixel/content differences.
- Similar visual shots can still be difficult.
- Published benchmark scores vary materially by dataset.

Use as the main low-risk candidate and classical fallback if it performs sufficiently on authentic podcast hold-out clips.

### Candidate path B — TransNet V2

Advantages:
- Model specifically trained for shot-transition detection.
- Pretrained inference is available; model training is not required for initial use.
- Authors publish strong results on ClipShots, BBC and RAI.
- Official repository is MIT-licensed.

Risks:
- Adds a model and inference runtime.
- Actual CPU/GPU cost in ClipForge is not yet measured.
- The published benchmark does not establish performance on this exact interview or every type of editorial podcast cut.
- A third-party PyTorch reimplementation/package needs its own dependency and license audit.

Use as the main learned candidate. If it materially outperforms the classical methods on authentic hold-out clips and fits the retained runtime, consider it as the primary detector or as a corroborating signal.

### Candidate path C — Hybrid detector

A possible hybrid design could use a learned shot-boundary score as the primary signal and a lightweight classical score as a corroboration/diagnostic signal. Participant visibility changes may be useful as secondary evidence after a boundary candidate is generated.

Do not require two detectors to agree blindly: that can reduce recall. Use a calibrated fusion or decision policy only if validation proves that it improves the precision/recall trade-off on the held-out interview footage.

### Not recommended as an immediate fix

- Lowering the existing HSV histogram threshold globally.
- Using `HistogramDetector` alone as a replacement for a histogram-based system.
- Relying on face-count changes as the only cut signal.
- Treating every participant movement as a new camera shot.
- Hardcoding the supplied video's shot timestamps in production code.
- Changing speaker identity assignment to compensate for missed cuts.
- Adding a large model dependency before isolated compatibility testing.

---

## 7. Proposed production architecture (subject to bake-off)

Keep the application-facing interface stable. Introduce or retain one detector abstraction returning canonical boundary events rather than letting every candidate define its own incompatible shot format.

Conceptual event:

```json
{
  "frame_index": 437,
  "timestamp_seconds": 17.48,
  "score": 0.91,
  "detector": "transnetv2",
  "event_type": "hard_cut"
}
```

The real schema must follow ClipForge conventions and include source identity/provenance where needed.

Expected internal flow:

```text
Video source
   ↓
Frame decoder / canonical timebase
   ↓
ShotBoundaryDetector interface
   ├── Current baseline (benchmark only)
   ├── PySceneDetect adapter
   ├── FFmpeg scdet adapter
   └── TransNetV2 adapter
   ↓
Boundary normalization + deduplication + minimum-duration policy
   ↓
Canonical shot intervals
   ↓
Per-shot visibility classification
   ↓
A_ONLY / B_ONLY / SIDE_BY_SIDE / UNKNOWN_REVIEW
   ↓
Identity continuity + within-shot tracking
   ↓
Crop trajectory and actual FFmpeg render
```

Requirements:

- Candidate detectors must be selectable in offline benchmark/test configuration only until production selection is approved.
- Production must have an explicit, deterministic selected detector and configuration.
- Do not silently switch detectors on runtime failure unless the fallback is deliberately designed, observable and validated.
- The benchmark output must preserve raw score streams and normalized boundary lists.
- Shot boundaries must be mapped correctly to frame indices/timecode and must not create gaps or overlaps in shot intervals.
- At a shot cut, reset shot-local crop trajectory as appropriate; preserve participant A/B identity continuity separately where evidence supports it.
- A new shot does not automatically mean the currently visible person is speaking.

---

## 8. Integration and acceptance tests

Required authentic test cases:

- Two-person wide → A close-up.
- A close-up → B close-up.
- B close-up → two-person wide.
- Same background/lighting, different camera framing.
- Stable close-up with gestures and head movement (must not produce repeated false cuts).
- Lighting change without an editorial cut.
- A camera move without a hard cut.
- Brief flash/transition graphic.
- Rapid sequence of genuine cuts.
- Opening/title card into an interview shot.

Required downstream checks:

- Shot interval list matches the annotated editorial structure.
- Visibility classification is run independently for each shot.
- Correct A_ONLY/B_ONLY/SIDE_BY_SIDE state is selected only when supported by visible evidence.
- UNKNOWN_REVIEW is used when evidence is missing/ambiguous.
- Identity mapping is not reset incorrectly at every cut.
- Crop smoothing does not interpolate across unrelated editorial camera angles.
- The final rendered output follows the original edit.
- Standard Podcast workflows do not regress.
- Fixed Two-Person and Visibility-Driven remain separate supported Advanced options.
- No captions/subtitles are added; preserve internal transcription.

---

## 9. Risks and project constraints

1. **Dataset mismatch:** public benchmarks include documentaries, short web videos and other content; none proves a candidate's performance on ClipForge's exact interview workflow.
2. **Metric ambiguity:** precision/recall can be falsely zero if timestamps, frame indices, tolerance or predicted/ground-truth formats are mismatched. Audit the evaluator before judging the detector.
3. **Model/dependency risk:** TransNet V2 and AutoShot must be tested in isolated environments. Do not change the active Python 3.11.16 runtime or its ML dependency pins.
4. **Resource cost:** measure CPU latency and memory; do not infer RTX 3050 performance from published results.
5. **License/provenance:** check the actual package, model weights, transitive dependencies and redistribution constraints before shipping.
6. **False positives:** aggressive detection can split on gestures, lighting, motion or transitions and harm downstream tracking.
7. **False negatives:** conservative detection can merge different camera angles and cause the composition failure already seen.
8. **Identity confusion:** cut detection must not be used to guess speaker identity or speaking turn.
9. **Governance:** L7 is frozen; this file is a proposal only. Any production implementation must be recorded under the established Logic Freeze exception process.

---

## 10. Agent-ready research / implementation proposal prompt

The following prompt may be given to Gravitas after the owner chooses to proceed. It authorizes an initial research and benchmark phase only; it does not authorize immediate L7 production changes.

```text
You are the ClipForge Principal Video Systems Architect and independent research engineer.

WORK ITEM: PODCAST-CUT-DETECTION-013
SCOPE: Research and benchmark open-source shot-boundary detectors for ClipForge's authentic podcast camera cuts.
MODE: RESEARCH + ISOLATED BENCHMARK ONLY. Do not change production detector logic, active dependencies, Docker configuration, Python runtime or frozen L7 code in this phase.

Read docs/engineering/proposals/CLIPFORGE_CAMERA_CUT_DETECTION_RESEARCH_PROPOSAL.md and the current authentic Podcast report.

Inspect the actual current code and reproduce the camera-cut failure. Audit the existing boundary evaluator and verify timestamps, frame indices, matching tolerance and precision/recall calculations before drawing conclusions.

Build an isolated, reproducible candidate benchmark using:
1. Current ClipForge detector.
2. PySceneDetect AdaptiveDetector.
3. PySceneDetect ContentDetector, including a separately recorded edge-weight experiment.
4. PySceneDetect HashDetector and HistogramDetector as diagnostic controls.
5. FFmpeg scdet.
6. TransNet V2 pretrained inference if it can run in an isolated environment without modifying the active ClipForge runtime.
7. AutoShot only if official pretrained weights/dependencies/license are practical and verifiable.

Use the owner-supplied authentic interview video and independently reviewed ground truth. Use the same decoder/timebase, exact one-to-one boundary matcher, tolerance settings and reporting code for every detector. Report exact-frame and tolerance-based precision, recall, F1, TP/FP/FN, timing error, runtime, peak memory and environment. Preserve raw score streams and prediction JSON/CSV.

Benchmark the full supplied video and the prior first-180-second region. Use additional authorized authentic clips if available. Do not synthesize missing camera cuts or manually hardcode production timestamps.

Do not treat a model's published paper score as a ClipForge result. Clearly separate published benchmark claims from locally measured ClipForge results. Record each candidate's exact version, parameters, weights checksum and license.

The current Python runtime decision is frozen at Python 3.11.16. Do not upgrade Python or change active PyTorch/MediaPipe/NumPy dependencies. Keep neural model experiments isolated.

Do not change the active L7 implementation in this phase. Prepare a decision proposal with candidate comparison, benchmark evidence, compatibility/risk assessment and a recommended implementation path. Stop for owner approval before any production L7 code changes.

Preserve the Git working tree; no destructive commands, commits or pushes. Do not restart services, change database records, publish videos or alter user media. Preserve the no-caption/no-subtitle requirement and keep internal transcription intact.
```

If the owner later authorizes implementation, create a separate implementation prompt that names the selected detector, approved architecture changes, dependency/runtime constraints and rollback strategy. Complete implementation, code review, authentic rendering and independent three-pass verification before marking the issue complete.

---

## 11. Research references and repositories

1. PySceneDetect repository (BSD-3-Clause): https://github.com/Breakthrough/PySceneDetect
2. PySceneDetect documentation: https://www.scenedetect.com/docs/latest/
3. PySceneDetect detector benchmark methodology and results: https://www.scenedetect.com/benchmarks/
4. PySceneDetect v0.7.2 release notes: https://github.com/Breakthrough/PySceneDetect/releases
5. TransNet V2 official repository (MIT): https://github.com/soCzech/TransNetV2
6. TransNet V2 paper: https://arxiv.org/abs/2008.04838
7. TransNet V2 PyTorch inference package (third-party implementation): https://pypi.org/project/transnetv2-pytorch/
8. AutoShot repository (MIT): https://github.com/wentaozhu/AutoShot
9. AutoShot paper: https://arxiv.org/abs/2304.06116
10. FFmpeg `scdet` implementation: https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_scdet.c
11. FFmpeg filters documentation: https://ffmpeg.org/ffmpeg-filters.html#scdet
12. Example community comparison harness (research reference only): https://github.com/ravi-movva/shot-boundary-harness

---

## 12. Final recommendation

Run a local, isolated bake-off first. PySceneDetect AdaptiveDetector is the most practical classical baseline. TransNet V2 is the most important learned-model candidate to evaluate. FFmpeg `scdet` is a useful low-cost control. AutoShot is optional pending weight/dependency feasibility.

Do not immediately install or adopt any candidate. The selected solution must be demonstrated on the authentic ClipForge interview footage using independently annotated shot boundaries, one consistent evaluator, hold-out data and actual rendered output.

**Final status of this document: PROPOSAL ONLY — no production code, dependency, runtime or L7 logic has been changed.**
