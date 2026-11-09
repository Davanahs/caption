# Verification Report: PODCAST-GEOMETRY-PARITY-004
## Crop Math and FFmpeg Render Parity Verification

**Document:** `reports/07_PODCAST_GEOMETRY_PARITY.md`  
**Work Item:** `PODCAST-GEOMETRY-PARITY-004`  
**Timestamp:** 2026-11-04T02:22:50+05:30  
**Evaluator:** ClipForge Autonomous Verification Lead (Gravitas Reliability Runtime)  

---

### 1. Disposition
**DELIVERED & VERIFIED** (100% Complete).

---

### 2. Crop Math Formulation & Cross-Layer Parity
To guarantee exact mathematical equivalence between frontend preview rendering (TypeScript: `frontend/lib/podcastCoordinates.ts`) and backend video rendering (Python: `backend/services/advanced_podcast_engine.py`), the outward integer rounding and containment rules are defined as:

1. **Outward Region Extents:**
   $$\text{region\_left} = \max(0, \min(\text{src\_w}, \lfloor\text{rx} \times \text{src\_w}\rfloor))$$
   $$\text{region\_right} = \max(0, \min(\text{src\_w}, \lceil(\text{rx} + \text{rw}) \times \text{src\_w}\rceil))$$
2. **Destination Minimum Fill Width:**
   $$\text{min\_fill\_w} = \lceil\text{src\_h} \times (\text{dest\_panel\_w} / \text{dest\_panel\_h})\rceil$$
   *(e.g., $1080 \times (540/1920) = 303.75 \to 304\text{px}$ on 1080p source; $202.5 \to 204\text{px}$ on 720p source)*
3. **Aligned Crop Width:**
   $$\text{aligned\_crop\_w} = \min(\text{src\_w}, \max(\text{min\_fill\_w}, \text{region\_right} - \text{region\_left}))$$
4. **Centering & Clamp:**
   - Center anchor $C_x$ defaults to region midpoint $(\text{region\_left} + \text{region\_right}) / 2$.
   - If a valid `face_box` exists whose center lies inside $[\text{region\_left}, \text{region\_right}]$, $C_x$ uses the face center.
   $$\text{crop\_x} = \max(0, \min(\text{src\_w} - \text{aligned\_crop\_w}, \lfloor C_x - \text{aligned\_crop\_w} / 2 \rfloor))$$
5. **YUV420p Even Alignment:**
   - Coordinates ($x, y, w, h$) are forced to even integer boundaries (`val - (val % 2)`), preventing chroma distortion and FFmpeg filter errors.

---

### 3. Golden Vector Coverage (18 Vectors in `podcast_geometry_golden_vectors.json`)
The 18 golden vectors comprehensively cover:
- `vector-01`: Full-frame ($1.0 \times 1.0$)
- `vector-02`: Narrow region (96px, expanding to 304px fill)
- `vector-03`: Wide region (1536px, exceeding min fill)
- `vector-04`: Fractional subpixel coordinates
- `vector-05`: Tiny box (2px, expanding safely)
- `vector-06`: Touch left/top boundaries ($x=0, y=0$)
- `vector-07`: Touch right/bottom boundaries ($x+\text{width}=\text{src\_w}$)
- `vector-08`: Out-of-range negative coordinates clamped
- `vector-09`: Out-of-range overflow coordinates clamped
- `vector-10`: 4K high resolution source ($3840 \times 2160$)
- `vector-11`: 720p standard source ($1280 \times 720$)
- `vector-12`: Odd source dimensions ($1921 \times 1081$)
- `vector-13`: Box wider than source frame
- `vector-14`: Face center inside region (used for centering)
- `vector-15`: Face center outside region (rejected, fallback to region center)
- `vector-16`: Left boundary clamp ($x=0$)
- `vector-17`: Right boundary clamp ($x+w=\text{src\_w}$)
- `vector-18`: 4:3 non-widescreen aspect ratio ($1440 \times 1080$)

---

### 4. Empirical Test Suite Evidence

#### Backend Python Suite (`test_podcast_geometry_parity.py`)
- **Command:** `python -m pytest backend/tests/test_podcast_geometry_parity.py -v`
- **Result:** **23 passed, 2 warnings in 1.40s** (Exit code: 0)
- **Scenarios Verified:**
  - 18 golden vectors tested parameterized against Python crop engine: 100% exact pixel match.
  - Odd source dimension even bounds tested.
  - Standard Stacked Split regression (1080x960 top / bottom) verified.
  - Single Speaker Focus regression (deterministic Area 1) verified.
  - Real FFmpeg filtergraph rendering verified.

#### Frontend TypeScript Suite (`podcast_geometry_parity.test.mjs`)
- **Command:** `node --test test/podcast_geometry_parity.test.mjs`
- **Result:** **20 passed, 0 failed in 104ms** (Exit code: 0)
- **Scenarios Verified:**
  - All 18 golden vectors matched in TypeScript implementation.
  - `getOutputPreviewGeometry` side-by-side composition matches panel framing.

---

### 5. Logic Domain L7 Governance
- Verified existing implementation against all acceptance criteria.
- Zero production code edits required (current code already 100% compliant).
- Logic Freeze status preserved with zero unapproved mutations.

---

### 6. Progress & Completion Rating
- **Pre-Task Estimate:** 70% complete / 30% pending
- **Post-Verification Actual:** **100% complete** / 0% pending
- **Status:** Closed and fully verified.

