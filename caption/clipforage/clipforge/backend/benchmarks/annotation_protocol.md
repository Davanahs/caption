# ClipForge Ground-Truth Camera-Cut Annotation Protocol

**Document Version:** 3.0.0  
**Work Item:** `PODCAST-CUT-VALIDATION-015`  
**Logic Domain:** L7 (Advanced Multi-Speaker Podcast Framing & Active Speaker Tracking)  
**Governance:** Master Engineering Rulebook Rule 15 (Empirical Proof & Ground-Truth Independence)  
**Author:** Principal Video Systems Architect & Independent QA Reviewer  
**Status:** Canonical & Immutable Reference Specification  

---

## 1. Objectives & Ground-Truth Independence Charter

This protocol establishes the authoritative, blind, frame-accurate ground-truth annotation standard for camera transitions in authentic multi-speaker podcast footage within ClipForge.

### 1.1 The Ground-Truth Circularity Problem
In previous benchmarks (`PODCAST-AUTHENTIC-VALIDATION-012` and subsequent bakeoffs), forensic reconciliation uncovered that:
1. Version 1.0.0 ground truth (`SHA-256: 8fc7f98a...`) relied on coarse human estimates rounded to whole or half seconds, causing the pure HSV detector to score 0.00 precision and 0.00 recall.
2. Version 2.0.0 ground truth (`SHA-256: bc563dad...`) replaced those human estimates with the raw output timestamps of FFmpeg `scdet=threshold=17.5`, yielding an artificial 100% precision and 100% recall.
3. This created a **circular validation dependency**: the evaluation metric evaluated the detector against its own predictions.

### 1.2 Independence Guarantees
Under this protocol:
- Annotations are defined strictly by direct human inspection of the source video frames.
- Frame indices are ground-truth anchors; timestamps are strictly derived by deterministic arithmetic:
  $$\text{Timestamp (seconds)} = \frac{\text{Frame Index}}{25.0}$$
- Detector outputs, confidence scores, and algorithm-specific parameters must NOT be consulted or used to define or adjust transition boundaries.
- Editorial camera cuts are explicitly separated from sub-second graphic inserts, lower-thirds, slides, and participant body gestures.

---

## 2. Source Asset Specifications

| Property | Value | Verification Method |
| :--- | :--- | :--- |
| **Media File** | `uploads/authentic_podcast_test.mp4` | Local filesystem |
| **SHA-256 Hash** | `8144a74a30ddebbbdb1946c43bbddd018e4b7891aedd31ddcb846d326ff7e4c0` | Cryptographic SHA-256 digest |
| **File Size** | `243,392,976` bytes | Operating system stat |
| **Nominal Frame Rate** | `25.0` fps (CBR progressive) | `ffprobe -show_streams` |
| **Timebase** | `1/25` second per frame ($40.0\text{ ms}$) | Video container timescale |
| **Frame Dimensions** | $1920 \times 1080$ pixels (16:9 Landscape) | Stream metadata |
| **Total Duration** | $981.08$ seconds ($24,527$ video frames) | Decoded packet count |

---

## 3. Transition Classification Taxonomy

Every visual discontinuity in the video stream must be classified into one of four mutually exclusive categories:

### 3.1 Category 1: Hard Editorial Camera Cut (`HARD_CAMERA_CUT`)
- **Definition:** An instantaneous, zero-frame duration transition where the broadcast director switches between physical cameras.
- **Physical Setups:**
  1. `WIDE_TWO_SHOT`: Camera capturing both Speaker A (Dr. Sweta Adatia, screen-left) and Speaker B (Raj Shamani, screen-right) seated at the studio table.
  2. `SPEAKER_A_SOLO`: Close-up camera centered on Dr. Sweta Adatia ($cx \approx 0.42$).
  3. `SPEAKER_B_SOLO`: Close-up camera centered on Raj Shamani ($cx \approx 0.44$).
  4. `INTRO_CARD`: Title card or opening sequence before the podcast conversation begins.
- **Boundary Rule:** The cut timestamp is assigned to the **exact first frame of the new camera angle**.
- **Frame Index:** Frame $k$ is a cut if Frame $k-1$ shows Camera $X$ and Frame $k$ shows Camera $Y$ ($X \neq Y$).
- **Ground Truth Role:** Included in primary camera-cut evaluation benchmark.

### 3.2 Category 2: Graphic / Presentation Insert (`GRAPHIC_INSERT`)
- **Definition:** An editorial overlay, presentation slide, or quote card that temporarily appears over the footage or replaces the video stream, typically lasting between $0.4\text{s}$ and $1.0\text{s}$.
- **Examples in Footage:**
  - $18.56\text{s}$ to $19.04\text{s}$ (Frames 464 to 475, $12$ frames, $0.48\text{s}$): Quote slide insert.
  - $77.28\text{s}$ to $78.16\text{s}$ (Frames 1932 to 1953, $22$ frames, $0.88\text{s}$): Topic graphic insert.
  - $182.32\text{s}$ to $183.20\text{s}$ (Frames 4558 to 4579, $22$ frames, $0.88\text{s}$): Concept graphic insert.
- **Boundary Rule:** The entry into the graphic insert is recorded at the first insert frame; the exit is recorded at the first returning camera frame.
- **Ground Truth Role:** Tracked as auxiliary transition events; must be evaluatable both separately and jointly with camera cuts.

### 3.3 Category 3: Intra-Shot Subject Motion (`INTRA_SHOT_GESTURE`)
- **Definition:** Rapid physical movement within a single continuous shot.
- **Examples in Footage:**
  - Speaker gesturing hands across the table towards the camera.
  - Speaker leaning forward or turning head rapidly.
  - Cough, laugh, or micro-reframe.
- **Boundary Rule:** **NOT A CUT**. Frame difference spikes caused by subject motion MUST NOT be annotated as cuts.
- **Ground Truth Role:** Negative test cases. Any detector triggering a cut during intra-shot motion commits a False Positive ($FP$).

### 3.4 Category 4: Digital Pan / Continuous Zoom (`DIGITAL_ZOOM`)
- **Definition:** Continuous camera scaling or repositioning over multiple frames without an abrupt cut.
- **Boundary Rule:** **NOT A CUT**. Continuous transitions are evaluated under camera framing (L7), not cut detection.

---

## 4. Evaluation Window Boundaries & Coverage Attestation

To maintain strict truth-in-reporting and avoid fabricating historical claims:

| Window ID | Time Range | Frame Range | Status | Annotation Depth |
| :--- | :--- | :--- | :--- | :--- |
| **Window 1 (Primary)** | $0.00\text{s} - 180.00\text{s}$ | Frames $0 - 4500$ | **Fully Verified** | Frame-by-frame visual audit; all 21 physical cuts + 1 graphic insert verified. |
| **Window 2 (Secondary)** | $180.00\text{s} - 300.00\text{s}$ | Frames $4500 - 7500$ | **Fully Verified** | Frame-by-frame visual audit; all 9 physical cuts + 2 graphic inserts verified. |
| **Window 3 (Extended)** | $300.00\text{s} - 981.08\text{s}$ | Frames $7500 - 24527$ | **Unannotated / Open** | 681.08s of footage (69.4% of asset) currently lacks independent human annotation. Any claim of full 981s validation is unproven and prohibited. |

---

## 5. Evaluation Matching & Metric Formulation

An independent evaluator must employ bipartite nearest-neighbor matching between predicted cuts $P = \{p_j\}$ and ground-truth cuts $G = \{g_i\}$.

### 5.1 Temporal Tolerance Tiers
Evaluations must report across four standard tolerance thresholds:
1. **Exact Frame ($\tau = 0\text{ ms}$, $\Delta f = 0$ frames):** Exact frame identity ($p_j = g_i$).
2. **Adjacent Frame ($\tau = \pm 40\text{ ms}$, $\Delta f = \pm 1$ frame):** Single-frame boundary tolerance.
3. **Tight Window ($\tau = \pm 120\text{ ms}$, $\Delta f = \pm 3$ frames):** Standard broadcast editorial tolerance.
4. **Loose Window ($\tau = \pm 250\text{ ms}$, $\Delta f = \pm 6$ frames):** Coarse temporal alignment tolerance.

### 5.2 1-to-1 Matching Rules
- Each ground-truth cut $g_i$ can match at most **one** prediction $p_j$.
- If multiple predictions fall within $\tau$ of $g_i$:
  - The closest prediction in absolute time $|p_j - g_i|$ is declared the True Positive ($TP$).
  - All additional predictions within the window are classified as False Positives ($FP$) due to **over-segmentation**.
- Any prediction $p_j$ with no unassigned $g_i$ within $\tau$ is classified as a False Positive ($FP$).
- Any ground-truth cut $g_i$ with no unassigned $p_j$ within $\tau$ is classified as a False Negative ($FN$).

### 5.3 Formal Metric Definitions
$$\text{Precision} = \frac{TP}{TP + FP}$$
$$\text{Recall} = \frac{TP}{TP + FN}$$
$$F_1 = \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$
$$\text{MATE (Mean Absolute Time Error)} = \frac{1}{|TP|} \sum_{(g_i, p_j) \in TP} |p_j - g_i|$$

