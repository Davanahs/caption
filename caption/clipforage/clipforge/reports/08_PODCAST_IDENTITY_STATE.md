# Verification Report: PODCAST-IDENTITY-STATE-005
## Participant Identity State Machine and Uncertainty Policy

**Document:** `reports/08_PODCAST_IDENTITY_STATE.md`  
**Work Item:** `PODCAST-IDENTITY-STATE-005`  
**Timestamp:** 2026-11-04T02:23:40+05:30  
**Evaluator:** ClipForge Autonomous Verification Lead (Gravitas Reliability Runtime)  

---

### 1. Disposition
**DELIVERED & VERIFIED** (100% Complete for state machine & uncertainty policy).

---

### 2. State Machine Architecture & Policy
The Visibility-Driven podcast composition engine classifies each shot into one of four mutually exclusive states:
1. **`A_ONLY`**: Sole participant A detected and tracked; renders full 1080×1920 frame centered on A.
2. **`B_ONLY`**: Sole participant B detected and tracked; renders full 1080×1920 frame centered on B.
3. **`SIDE_BY_SIDE`**: Both distinct participants established simultaneously; renders horizontal 540×1920 split panels ($A$ left, $B$ right).
4. **`UNKNOWN_REVIEW`**: Ambiguous, occluded, collision, or unassigned detection; renders single centered 1080×1920 safe crop (zero speaker duplication).

---

### 3. Identity Safeguards & Anti-Hallucination Protections
- **Duplicate Prevention:** The engine prevents a single detected face from being assigned to both $A$ and $B$. Duplicate candidate boxes are deduplicated via IoU before participant matching.
- **Ambiguity Routing:**
  - Equidistant faces between Area A and Area B are marked ambiguous (`identity_ambiguous=True`) rather than randomly assigned.
  - Crossing trajectories (where spatial distance vectors collide within threshold $\Delta < 0.15$) trigger the ambiguity flag to prevent silent participant swapping.
  - Missing detections or out-of-frame coordinates route strictly to `UNKNOWN_REVIEW`.
- **Render Safety Invariant:** Under `UNKNOWN_REVIEW`, the video filtergraph produces a safe center crop (`crop=min(in_w\,in_h*9/16):in_h:(in_w-out_w)/2:0,scale=1080:1920`), maintaining continuous audio and strictly zero subtitle streams (`-sn`).

---

### 4. Empirical Test Suite Evidence (`test_podcast_identity_state_machine.py`)
- **Command:** `python -m pytest backend/tests/test_podcast_identity_state_machine.py -v`
- **Result:** **20 passed, 1 warning in 0.75s** (Exit code: 0)
- **Scenarios Verified:**
  1. `test_bounding_box_validation_rejects_nan_and_infinities`: Asserts rejection of NaN, $\pm\infty$.
  2. `test_bounding_box_validation_rejects_negative_or_zero_dimensions`: Asserts rejection of zero/negative width/height and sub-pixel noise.
  3. `test_bounding_box_validation_rejects_out_of_frame_coordinates`: Rejects coordinates $< 0.0$ or $> 1.0$.
  4. `test_bounding_box_validation_accepts_valid_boxes`: Accepts valid normalized boxes; validates confidence thresholds.
  5. `test_duplicate_face_detections_deduplicated`: NMS/IoU deduplication verified.
  6. `test_distinct_faces_preserved_in_deduplication`: Preserves separate participants.
  7. `test_match_participants_no_detections_returns_ambiguous`: Returns ambiguous metadata on empty input.
  8. `test_match_participants_invalid_detections_rejected`: Safely rejects corrupted coordinate streams.
  9. `test_match_participants_duplicate_face_never_assigned_to_both`: Duplicate face assigned to single participant only.
  10. `test_match_participants_single_detection_equidistant_ambiguous`: Equidistant detections marked ambiguous.
  11. `test_match_participants_single_detection_verified_a`: Confirmed assignment to A.
  12. `test_match_participants_single_detection_verified_b`: Confirmed assignment to B.
  13. `test_match_participants_two_faces_distinct_assigned_both`: Both distinct participants assigned.
  14. `test_match_participants_crossing_paths_marks_ambiguous_no_swap`: Trajectory collisions prevent identity swap.
  15. `test_match_participants_close_collision_marks_ambiguous`: Spatial collisions route to ambiguity.
  16. `test_classify_visibility_no_detections_routes_to_unknown_review`: Empty detections route to `UNKNOWN_REVIEW`.
  17. `test_classify_visibility_ambiguous_single_face_routes_to_unknown_review`: Ambiguous single detections route to `UNKNOWN_REVIEW`.
  18. `test_classify_visibility_same_face_duplicated_never_emits_side_by_side`: Prevents duplicated speaker in side-by-side.
  19. `test_classify_visibility_two_distinct_participants_triggers_side_by_side`: Two distinct participants trigger side-by-side.
  20. `test_unknown_review_filtergraph_renders_single_center_canvas`: Verified FFmpeg filtergraph for safe center fallback.

---

### 5. Progress & Completion Rating
- **Pre-Task Estimate:** 60% complete / 40% pending
- **Post-Verification Actual:** **100% complete** / 0% pending
- **Status:** Closed and fully verified.

