"""
Unit tests for deterministic equal split video segmentation with full source coverage.
Verifies exact specifications:
- Clip count N = ceil(D / Lmax)
- Actual clip duration = D / N (all clips have identical duration, duration <= Lmax)
- Source duration <= Lmax produces N = 1 clip covering the entire source
- Invariants: starts at 0.0, zero gaps, zero overlaps, ends at D, duration > 0, sum(durations) == D
- Exact specification table from prompt:
    * 1000s @ 45s -> 23 clips, actual duration 43.478260...
    * 100s @ 45s  -> 3 clips, actual duration 33.333333...
    * 90s @ 45s   -> 2 clips, actual duration 45.0
    * 45s @ 45s   -> 1 clip, actual duration 45.0
    * 30s @ 45s   -> 1 clip, actual duration 30.0
    * 1s @ 45s    -> 1 clip, actual duration 1.0
    * 101s @ 50s  -> 3 clips, actual duration 33.666666...
- Prohibition of user-selected clip count in Equal Splits mode
- Clean rejection of invalid, non-finite, zero, or negative durations
- Preservation of full timeline without shortened remainder clip or dropped footage
"""
import math
import sys
from pathlib import Path
import pytest

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.services.segmentation import generate_equal_splits, MAX_EQUAL_SPLIT_CLIPS


def verify_equal_split_invariants(splits: list[dict], source_duration: float, max_clip_duration: float | None = None):
    """Assert all mathematical invariants defined in the definitive Equal Splits specification."""
    assert len(splits) > 0, "Must produce at least one segment"

    # Invariant 1: First segment starts at 0.0
    assert splits[0]["start"] == 0.0, f"First segment must start at 0.0, got {splits[0]['start']}"

    # Invariant 2 & 3: No gaps, no overlaps, consecutive continuity
    for i in range(len(splits) - 1):
        assert splits[i]["end"] == splits[i + 1]["start"], (
            f"Segment {i} end ({splits[i]['end']}) must match segment {i+1} start ({splits[i+1]['start']})"
        )

    # Invariant 4: Final segment reaches source duration exactly
    assert splits[-1]["end"] == source_duration, (
        f"Final segment end ({splits[-1]['end']}) must equal source duration ({source_duration})"
    )

    # Invariant 5: All segments have strictly positive duration
    expected_each_dur = source_duration / len(splits)
    for i, s in enumerate(splits):
        assert s["duration"] > 0, f"Segment duration must be positive, got {s['duration']}"
        # Every segment has the same duration (within floating point precision)
        assert abs(s["duration"] - expected_each_dur) < 1e-6, (
            f"Segment {i} duration ({s['duration']}) must equal expected {expected_each_dur}"
        )
        # Duration must equal end - start
        assert abs((s["end"] - s["start"]) - s["duration"]) < 1e-9

        # Invariant 6: Duration must not exceed user-selected maximum duration
        if max_clip_duration is not None:
            assert s["duration"] <= max_clip_duration + 1e-9, (
                f"Segment {i} duration {s['duration']} exceeds max duration {max_clip_duration}"
            )

    # Invariant 7: Sum of segment durations equals source duration exactly
    total_duration = sum(s["duration"] for s in splits)
    assert abs(total_duration - source_duration) < 1e-6, (
        f"Sum of durations ({total_duration}) must equal source duration ({source_duration})"
    )


@pytest.mark.parametrize("video_dur, target_dur, expected_n, expected_actual_dur", [
    (1000.0, 45.0, 23, 1000.0 / 23.0),   # 43.478260...
    (100.0,  45.0, 3,  100.0 / 3.0),     # 33.333333...
    (90.0,   45.0, 2,  45.0),            # 45.0
    (45.0,   45.0, 1,  45.0),            # 45.0
    (30.0,   45.0, 1,  30.0),            # 30.0
    (1.0,    45.0, 1,  1.0),             # 1.0
    (101.0,  50.0, 3,  101.0 / 3.0),     # 33.666666...
    (240.0,  25.0, 10, 24.0),            # 24.0s each (<= 25s limit)
    (60.0,   25.0, 3,  20.0),            # 20.0s each (<= 25s limit)
    (120.0,  25.0, 5,  24.0),            # 24.0s each (<= 25s limit)
    (360.0,  25.0, 15, 24.0),            # 24.0s each (<= 25s limit)
    (600.0,  25.0, 24, 25.0),            # 25.0s each
    (1200.0, 25.0, 48, 25.0),            # 25.0s each
])
def test_specification_exact_table_scenarios(video_dur, target_dur, expected_n, expected_actual_dur):
    """
    Verify the mandatory scenarios from Section 7 of the specification:
    N = ceil(D / Lmax), actual_clip_duration = D / N.
    """
    splits = generate_equal_splits(video_duration=video_dur, target_duration=target_dur)
    assert len(splits) == expected_n, (
        f"Expected {expected_n} clips for {video_dur}s with max {target_dur}s, got {len(splits)}"
    )

    for i, clip in enumerate(splits):
        assert abs(clip["duration"] - expected_actual_dur) < 1e-6, (
            f"Clip {i} duration {clip['duration']} != expected {expected_actual_dur}"
        )
        assert clip["duration"] <= target_dur + 1e-9
        assert clip["title"] == f"Part {i + 1} of {expected_n}"
        assert clip["score"] == 1.0

    verify_equal_split_invariants(splits, video_dur, max_clip_duration=target_dur)


def test_source_shorter_than_or_equal_target_duration():
    """When D <= Lmax, exactly N = 1 clip covering the entire source video is generated."""
    # Shorter: 30s <= 45s -> 1 clip
    s1 = generate_equal_splits(video_duration=30.0, target_duration=45.0)
    assert len(s1) == 1
    assert s1[0]["start"] == 0.0
    assert s1[0]["end"] == 30.0
    assert s1[0]["duration"] == 30.0
    verify_equal_split_invariants(s1, 30.0, 45.0)

    # Equal: 45s <= 45s -> 1 clip
    s2 = generate_equal_splits(video_duration=45.0, target_duration=45.0)
    assert len(s2) == 1
    assert s2[0]["start"] == 0.0
    assert s2[0]["end"] == 45.0
    assert s2[0]["duration"] == 45.0
    verify_equal_split_invariants(s2, 45.0, 45.0)

    # Tiny: 0.5s <= 15s -> 1 clip
    s3 = generate_equal_splits(video_duration=0.5, target_duration=15.0)
    assert len(s3) == 1
    assert s3[0]["start"] == 0.0
    assert s3[0]["end"] == 0.5
    assert s3[0]["duration"] == 0.5
    verify_equal_split_invariants(s3, 0.5, 15.0)


def test_user_selected_clip_count_prohibited_when_target_duration_provided():
    """
    Section 2 & 4: In Equal Splits mode, user must not choose number of clips.
    Backend calculates N automatically as ceil(D / Lmax), ignoring any num_clips argument.
    """
    # 1000s @ 45s requires 23 clips. Passing num_clips=5 must STILL produce 23 clips.
    s_23 = generate_equal_splits(video_duration=1000.0, num_clips=5, target_duration=45.0)
    assert len(s_23) == 23
    verify_equal_split_invariants(s_23, 1000.0, 45.0)

    # 240s @ 25s requires 10 clips. Passing num_clips=1 must STILL produce 10 clips.
    s_10 = generate_equal_splits(video_duration=240.0, num_clips=1, target_duration=25.0)
    assert len(s_10) == 10
    verify_equal_split_invariants(s_10, 240.0, 25.0)

    # Passing num_clips=100 must not inflate; it produces exactly ceil(240/25) = 10 clips.
    s_10_high = generate_equal_splits(video_duration=240.0, num_clips=100, target_duration=25.0)
    assert len(s_10_high) == 10
    verify_equal_split_invariants(s_10_high, 240.0, 25.0)


def test_absent_target_duration_with_explicit_num_clips_divides_evenly():
    """Manual division mode: when target_duration is absent, divides total duration evenly by explicit num_clips."""
    splits = generate_equal_splits(video_duration=120.0, num_clips=4, target_duration=None)
    assert len(splits) == 4
    for i, c in enumerate(splits):
        assert c["start"] == i * 30.0
        assert c["end"] == (i + 1) * 30.0
        assert c["duration"] == 30.0
    verify_equal_split_invariants(splits, 120.0)


def test_missing_maximum_duration_raises_and_never_defaults_to_three():
    """
    Task A: In Equal Splits mode, missing or None maximum duration must produce a clear
    validation error and must NEVER silently produce three clips.
    """
    # Neither target_duration nor num_clips provided
    with pytest.raises(ValueError, match="Maximum clip duration.*mandatory"):
        generate_equal_splits(video_duration=90.0)

    # Explicit None for both
    with pytest.raises(ValueError, match="Maximum clip duration.*mandatory"):
        generate_equal_splits(video_duration=90.0, num_clips=None, target_duration=None)

    # Scoped interface without max_clip_duration
    from backend.services.segmentation import generate_equal_splits_by_duration, generate_equal_divisions_by_count
    with pytest.raises(ValueError, match="max_clip_duration is mandatory"):
        generate_equal_splits_by_duration(video_duration=90.0, max_clip_duration=None)

    with pytest.raises(ValueError, match="num_clips is mandatory"):
        generate_equal_divisions_by_count(video_duration=90.0, num_clips=None)


@pytest.mark.parametrize("invalid_dur", [0.0, -1.0, -100.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_video_duration_raises(invalid_dur):
    """Invalid video duration must cleanly raise ValueError."""
    with pytest.raises(ValueError):
        generate_equal_splits(video_duration=invalid_dur, target_duration=45.0)


@pytest.mark.parametrize("invalid_target", [0.0, -1.0, -45.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_target_duration_raises(invalid_target):
    """Invalid target duration (zero, negative, NaN, infinity) must cleanly raise ValueError."""
    with pytest.raises(ValueError):
        generate_equal_splits(video_duration=100.0, target_duration=invalid_target)


def test_none_duration_raises():
    """None video duration raises ValueError."""
    with pytest.raises(ValueError):
        generate_equal_splits(video_duration=None, target_duration=45.0)


def test_invalid_num_clips_legacy_mode_raises():
    """When target_duration is None, non-positive or invalid num_clips raises ValueError."""
    with pytest.raises(ValueError):
        generate_equal_splits(video_duration=120.0, num_clips=0, target_duration=None)
    with pytest.raises(ValueError):
        generate_equal_splits(video_duration=120.0, num_clips=-3, target_duration=None)
    with pytest.raises(ValueError):
        generate_equal_splits(video_duration=120.0, num_clips="invalid", target_duration=None)


def test_long_videos_preserves_full_coverage():
    """Very long video (3600s / 1hr) with target duration 45s produces 80 equal clips of 45.0s."""
    splits = generate_equal_splits(video_duration=3600.0, target_duration=45.0)
    assert len(splits) == 80
    assert splits[0]["start"] == 0.0
    assert splits[-1]["end"] == 3600.0
    for s in splits:
        assert abs(s["duration"] - 45.0) < 1e-6
    verify_equal_split_invariants(splits, 3600.0, 45.0)


def test_no_cumulative_floating_point_drift():
    """
    Test scenario with non-round division (e.g. 1000s @ 45s -> 23 clips).
    Verifies that boundaries are calculated from original duration and index,
    guaranteeing end_i == start_{i+1} and end_{N-1} == D without cumulative drift.
    """
    splits = generate_equal_splits(video_duration=1000.0, target_duration=45.0)
    assert len(splits) == 23
    assert splits[0]["start"] == 0.0
    assert splits[-1]["end"] == 1000.0
    for i in range(len(splits) - 1):
        # Bit-exact boundary continuity
        assert splits[i]["end"] == splits[i + 1]["start"]
    # Final boundary must be exactly 1000.0
    assert splits[-1]["end"] == 1000.0
    verify_equal_split_invariants(splits, 1000.0, 45.0)


def test_scoring_task_preserves_all_equal_split_candidates_without_clips_count_truncation():
    """
    Downstream verification: In scoring_task, equal_splits mode must NOT truncate
    the candidate set to clips_count (e.g. 3). All 23 candidates must be preserved.
    """
    import json
    import tempfile
    import uuid
    from pathlib import Path
    from unittest.mock import MagicMock, patch
    from contextlib import contextmanager
    from backend.tasks.analysis_tasks import scoring_task

    mock_job = MagicMock()
    mock_job.id = f"job_eq_{uuid.uuid4().hex[:8]}"
    # Job config has default clips_count = 3
    mock_job.config = json.dumps({
        "segmentation_strategy": "equal_splits",
        "clip_mode": "equal_split",
        "clips_count": 3,
        "max_clip_duration": 45
    })
    mock_job.video_id = str(uuid.uuid4())

    # Generate 23 equal split candidates (1000s @ 45s)
    candidates = generate_equal_splits(video_duration=1000.0, target_duration=45.0)
    assert len(candidates) == 23

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as cand_file:
        json.dump(candidates, cand_file)
        cand_path = cand_file.name
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as out_file:
        out_path = out_file.name

    @contextmanager
    def fake_download(*args, **kwargs):
        yield cand_path

    @contextmanager
    def fake_upload(*args, **kwargs):
        yield out_path

    with patch("backend.models.database.SyncSessionLocal") as mock_session_cls, \
         patch("backend.models.artifact_sync.managed_download_sync", side_effect=fake_download), \
         patch("backend.models.artifact_sync.managed_upload_sync", side_effect=fake_upload), \
         patch("backend.models.db_sync.update_job_sync"):
        session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = session
        session.query.return_value.filter_by.return_value.first.return_value = mock_job

        res = scoring_task({
            "video_id": mock_job.video_id,
            "job_id": mock_job.id,
            "segmentation_strategy": "equal_splits"
        })
        assert res["scoring_version"] == "equal_splits_v1"

        # Verify output scored_clips.json contains all 23 clips, NOT truncated to 3!
        with open(out_path, "r") as f:
            scored = json.load(f)
        assert len(scored) == 23
        assert scored[0]["title"] == "Part 1 of 23"
        assert scored[-1]["title"] == "Part 23 of 23"

    try:
        Path(cand_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)
    except Exception:
        pass


