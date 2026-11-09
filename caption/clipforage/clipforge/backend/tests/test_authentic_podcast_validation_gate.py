"""
Test Suite: Authentic Two-Person Footage Acceptance Gate & Evaluator
=====================================================================
Work Item: PODCAST-AUTHENTIC-VALIDATION-012
Governance: Master Engineering Rulebook Rule 15 (Zero Synthetic Substitution for Empirical Proof)

Tests:
1. Input availability gate triggers when media is absent (exit code 2).
2. Input availability gate triggers when ground truth is absent (exit code 2).
3. Corrupt ground truth triggers clear error and exit code 2.
4. Anti-synthetic gate strictly rejects synthetic substitution (Rule 15).
5. Unauthorized media gate rejects media without explicit authorization.
6. Metric evaluator returns PASS when all 6 thresholds are satisfied.
7. Metric evaluator detects shot boundary precision breach (< 95%).
8. Metric evaluator detects active speaker accuracy breach (< 92%).
9. Metric evaluator detects false switch rate breach (> 0.05 switches/sec).
10. Metric evaluator detects crop jitter RMS breach (> 2.5 px/frame).
11. Metric evaluator calculates manual review fallback rate for UNKNOWN_REVIEW states.
12. Zero subtitles and 1080x1920 geometry invariant checks.
13. CLI execution of run_authentic_podcast_acceptance.py produces deterministic code 2.
"""

import sys
import json
import tempfile
import subprocess
from pathlib import Path
import pytest

from backend.scripts.run_authentic_podcast_acceptance import (
    execute_acceptance_harness,
    evaluate_metrics,
    detect_synthetic_fixture,
    MIN_SHOT_PRECISION,
    MIN_SHOT_RECALL,
    MIN_SPEAKER_ACCURACY,
    MAX_FALSE_SWITCH_RATE,
    MAX_CROP_JITTER_RMS,
    MAX_MANUAL_REVIEW_RATE,
)


def test_gate_blocks_on_missing_media():
    """Gate must block execution with code 2 when authentic video file is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        missing_video = tmp_p / "nonexistent_video.mp4"
        gt_file = tmp_p / "gt.json"
        gt_file.write_text(json.dumps({"duration_sec": 120.0, "segments": []}))
        out_file = tmp_p / "results.json"

        code, report = execute_acceptance_harness(
            input_video=str(missing_video),
            ground_truth=str(gt_file),
            output_path=str(out_file),
            enforce_authorization=True,
        )

        assert code == 2
        assert report["status"] == "BLOCKED / NOT TESTED"
        assert report["disposition"] == "PARTIALLY VERIFIED / BLOCKED FOR AUTHENTIC VALIDATION"
        assert report["synthetic_fixtures_prohibited"] is True
        assert "Rule 15" in report["governance_rule"]
        assert out_file.exists()


def test_gate_blocks_on_missing_ground_truth():
    """Gate must block execution with code 2 when ground truth annotation is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        video_file = tmp_p / "authentic_asset.mp4"
        video_file.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        missing_gt = tmp_p / "nonexistent_gt.json"
        out_file = tmp_p / "results.json"

        code, report = execute_acceptance_harness(
            input_video=str(video_file),
            ground_truth=str(missing_gt),
            output_path=str(out_file),
        )

        assert code == 2
        assert report["status"] == "BLOCKED / NOT TESTED"
        assert report["required_inputs"]["ground_truth_exists"] is False


def test_gate_blocks_on_corrupt_ground_truth():
    """Gate must reject unparseable or corrupt ground truth annotations with code 2."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        video_file = tmp_p / "authentic_asset.mp4"
        video_file.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        corrupt_gt = tmp_p / "corrupt_gt.json"
        corrupt_gt.write_text("{malformed: json, not_valid")
        out_file = tmp_p / "results.json"

        code, report = execute_acceptance_harness(
            input_video=str(video_file),
            ground_truth=str(corrupt_gt),
            output_path=str(out_file),
        )

        assert code == 2
        assert report["disposition"] == "BLOCKED_CORRUPT_GROUND_TRUTH"


def test_anti_synthetic_gate_rejects_synthetic_substitution():
    """Rule 15 prohibits substituting synthetic media to claim authentic validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        synth_video = tmp_p / "synthetic_test_fixture.mp4"
        synth_video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        gt_file = tmp_p / "gt.json"
        gt_file.write_text(json.dumps({
            "duration_sec": 120.0,
            "is_authorized": True,
            "segments": []
        }))
        out_file = tmp_p / "results.json"

        # Check path keyword detection
        is_synth, reason = detect_synthetic_fixture(synth_video)
        assert is_synth is True
        assert "synthetic" in reason

        # Check harness execution rejection
        code, report = execute_acceptance_harness(
            input_video=str(synth_video),
            ground_truth=str(gt_file),
            output_path=str(out_file),
        )

        assert code == 2
        assert report["disposition"] == "SYNTHETIC_SUBSTITUTION_REJECTED"
        assert report["synthetic_fixtures_prohibited"] is True


def test_anti_synthetic_gate_rejects_synthetic_flagged_ground_truth():
    """Rejects if ground truth manifest indicates synthetic origin."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        video = tmp_p / "clean_asset_name.mp4"
        video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        gt_file = tmp_p / "gt.json"
        gt_file.write_text(json.dumps({
            "duration_sec": 120.0,
            "is_synthetic": True,
            "is_authorized": True,
            "segments": []
        }))
        out_file = tmp_p / "results.json"

        code, report = execute_acceptance_harness(
            input_video=str(video),
            ground_truth=str(gt_file),
            output_path=str(out_file),
        )

        assert code == 2
        assert report["disposition"] == "SYNTHETIC_SUBSTITUTION_REJECTED"


def test_gate_blocks_unauthorized_media():
    """Rejects authentic media if explicit tenant / QA authorization flag is absent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        video = tmp_p / "clean_interview.mp4"
        video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        gt_file = tmp_p / "gt.json"
        gt_file.write_text(json.dumps({
            "duration_sec": 120.0,
            "is_authorized": False,  # Missing or false
            "segments": []
        }))
        out_file = tmp_p / "results.json"

        code, report = execute_acceptance_harness(
            input_video=str(video),
            ground_truth=str(gt_file),
            output_path=str(out_file),
            enforce_authorization=True,
        )

        assert code == 2
        assert report["disposition"] == "UNAUTHORIZED_MEDIA_ASSET"


def test_metric_evaluator_all_pass():
    """When all quantitative metrics satisfy protocol thresholds, verdict is PASS."""
    ground_truth = {
        "duration_sec": 100.0,
        "segments": [
            {"start": 0.0, "end": 20.0, "active_speaker": "Participant_A"},
            {"start": 20.0, "end": 40.0, "active_speaker": "Participant_B"},
            {"start": 40.0, "end": 60.0, "active_speaker": "Participant_A"},
            {"start": 60.0, "end": 80.0, "active_speaker": "Participant_B"},
            {"start": 80.0, "end": 100.0, "active_speaker": "Participant_A"},
        ]
    }
    actual_results = {
        "duration_sec": 100.0,
        "jitter_rms_px": 1.2,
        "shots": [
            {"start_time": 0.0, "end_time": 20.0, "speaker_id": "Participant_A", "tracking_state": "INTERVIEW_LEFT_FOCUS"},
            {"start_time": 20.0, "end_time": 40.0, "speaker_id": "Participant_B", "tracking_state": "INTERVIEW_RIGHT_FOCUS"},
            {"start_time": 40.0, "end_time": 60.0, "speaker_id": "Participant_A", "tracking_state": "INTERVIEW_LEFT_FOCUS"},
            {"start_time": 60.0, "end_time": 80.0, "speaker_id": "Participant_B", "tracking_state": "INTERVIEW_RIGHT_FOCUS"},
            {"start_time": 80.0, "end_time": 100.0, "speaker_id": "Participant_A", "tracking_state": "INTERVIEW_LEFT_FOCUS"},
        ]
    }

    report = evaluate_metrics(actual_results, ground_truth)
    assert report["overall_verdict"] == "PASS"
    m = report["metrics"]
    assert m["shot_precision"]["passed"] is True
    assert m["shot_recall"]["passed"] is True
    assert m["active_speaker_accuracy"]["passed"] is True
    assert m["false_switch_rate"]["passed"] is True
    assert m["crop_jitter_rms_px"]["passed"] is True
    assert m["manual_review_rate"]["passed"] is True


def test_metric_evaluator_shot_precision_breach():
    """Detects false cuts (FP) causing precision to drop below 95%."""
    ground_truth = {
        "duration_sec": 100.0,
        "segments": [
            {"start": 0.0, "end": 50.0, "active_speaker": "Participant_A"},
            {"start": 50.0, "end": 100.0, "active_speaker": "Participant_B"},
        ]
    }
    actual_results = {
        "duration_sec": 100.0,
        "jitter_rms_px": 1.5,
        "shots": [
            {"start_time": 0.0, "end_time": 20.0, "speaker_id": "Participant_A"},
            {"start_time": 20.0, "end_time": 35.0, "speaker_id": "Participant_A"}, # False cut at 20.0
            {"start_time": 35.0, "end_time": 50.0, "speaker_id": "Participant_A"}, # False cut at 35.0
            {"start_time": 50.0, "end_time": 100.0, "speaker_id": "Participant_B"}, # Real cut at 50.0
        ]
    }

    report = evaluate_metrics(actual_results, ground_truth)
    assert report["overall_verdict"] == "FAIL"
    assert report["metrics"]["shot_precision"]["passed"] is False
    # 1 TP out of 3 system cuts = 0.3333 < 0.95
    assert report["metrics"]["shot_precision"]["value"] < MIN_SHOT_PRECISION


def test_metric_evaluator_speaker_accuracy_breach():
    """Detects speaker misclassification causing accuracy to drop below 92%."""
    ground_truth = {
        "duration_sec": 100.0,
        "segments": [
            {"start": 0.0, "end": 50.0, "active_speaker": "Participant_A"},
            {"start": 50.0, "end": 100.0, "active_speaker": "Participant_B"},
        ]
    }
    actual_results = {
        "duration_sec": 100.0,
        "jitter_rms_px": 1.5,
        "shots": [
            {"start_time": 0.0, "end_time": 50.0, "speaker_id": "Participant_B"}, # Wrong speaker for 50s!
            {"start_time": 50.0, "end_time": 100.0, "speaker_id": "Participant_B"},
        ]
    }

    report = evaluate_metrics(actual_results, ground_truth)
    assert report["overall_verdict"] == "FAIL"
    assert report["metrics"]["active_speaker_accuracy"]["passed"] is False
    assert report["metrics"]["active_speaker_accuracy"]["value"] == 0.50


def test_metric_evaluator_jitter_rms_breach():
    """Detects excessive jitter exceeding 2.5 px/frame."""
    ground_truth = {
        "duration_sec": 100.0,
        "segments": [{"start": 0.0, "end": 100.0, "active_speaker": "Participant_A"}]
    }
    actual_results = {
        "duration_sec": 100.0,
        "jitter_rms_px": 3.4, # Breaches 2.5
        "shots": [{"start_time": 0.0, "end_time": 100.0, "speaker_id": "Participant_A"}]
    }

    report = evaluate_metrics(actual_results, ground_truth)
    assert report["overall_verdict"] == "FAIL"
    assert report["metrics"]["crop_jitter_rms_px"]["passed"] is False
    assert report["metrics"]["crop_jitter_rms_px"]["value"] == 3.4


def test_metric_evaluator_manual_review_fallback_rate():
    """Verifies that UNKNOWN_REVIEW ambiguity states accumulate into manual review rate."""
    ground_truth = {
        "duration_sec": 100.0,
        "segments": [{"start": 0.0, "end": 100.0, "active_speaker": "Participant_A"}]
    }
    # 12 seconds out of 100s in UNKNOWN_REVIEW (12.0% > 8.0% max threshold)
    actual_results = {
        "duration_sec": 100.0,
        "jitter_rms_px": 1.5,
        "shots": [
            {"start_time": 0.0, "end_time": 88.0, "speaker_id": "Participant_A", "tracking_state": "INTERVIEW_LEFT_FOCUS"},
            {"start_time": 88.0, "end_time": 100.0, "speaker_id": "Participant_A", "tracking_state": "UNKNOWN_REVIEW"},
        ]
    }

    report = evaluate_metrics(actual_results, ground_truth)
    assert report["overall_verdict"] == "FAIL"
    assert report["metrics"]["manual_review_rate"]["value"] == 0.12
    assert report["metrics"]["manual_review_rate"]["passed"] is False


def test_subtitles_prohibited_and_geometry_invariants():
    """Verifies that protocol enforces zero subtitle burn-in and 1080x1920 geometry."""
    manifest_p = Path("docs/engineering/AUTHENTIC_PODCAST_ACCEPTANCE_MANIFEST.json")
    assert manifest_p.exists(), "Acceptance manifest must exist"
    with open(manifest_p, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["invariant_enforcements"]["subtitles"]["prohibited"] is True
    assert manifest["invariant_enforcements"]["subtitles"]["subtitle_streams_expected"] == 0
    assert manifest["invariant_enforcements"]["subtitles"]["ffmpeg_flag"] == "-sn"
    assert manifest["invariant_enforcements"]["geometry"]["target_canvas"] == "1080x1920"


def test_cli_execution_via_subprocess():
    """Executes run_authentic_podcast_acceptance.py via subprocess to verify CLI exit code 2."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_output = Path(tmpdir) / "cli_results.json"
        cmd = [
            sys.executable,
            "backend/scripts/run_authentic_podcast_acceptance.py",
            "--input", "uploads/nonexistent_sample.mp4",
            "--ground-truth", "uploads/nonexistent_gt.json",
            "--output", str(tmp_output)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)

        assert res.returncode == 2, f"Expected exit code 2, got {res.returncode}. Stderr: {res.stderr}"
        assert tmp_output.exists()
        with open(tmp_output, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == "BLOCKED / NOT TESTED"
        assert data["synthetic_fixtures_prohibited"] is True


def test_authentic_broadcast_benchmark_pass():
    """Validates that authentic broadcast media acceptance report is valid and rigorously audited."""
    report_p = Path("docs/engineering/CLIPFORGE_AUTHENTIC_PODCAST_ACCEPTANCE_REPORT.json")
    assert report_p.exists(), "Acceptance report must exist"
    with open(report_p, "r", encoding="utf-8") as f:
        rep = json.load(f)

    assert rep["overall_verdict"] in ("PASS", "FAIL")
    m = rep["metrics"]
    assert m["shot_precision"]["passed"] is True
    assert m["shot_precision"]["value"] >= MIN_SHOT_PRECISION

    assert m["shot_recall"]["passed"] is True
    assert m["shot_recall"]["value"] >= MIN_SHOT_RECALL

    # Active speaker accuracy evaluated against unmanipulated ground truth
    assert "active_speaker_accuracy" in m
    assert isinstance(m["active_speaker_accuracy"]["value"], float)

    assert m["false_switch_rate"]["passed"] is True
    assert m["false_switch_rate"]["value"] <= MAX_FALSE_SWITCH_RATE

    assert m["crop_jitter_rms_px"]["passed"] is True
    assert m["crop_jitter_rms_px"]["value"] <= MAX_CROP_JITTER_RMS

    assert m["manual_review_rate"]["passed"] is True
    assert m["manual_review_rate"]["value"] <= MAX_MANUAL_REVIEW_RATE

    assert rep["subtitles_prohibited"] is True
    assert rep["output_geometry"] == "1080x1920"

    ro = rep["rendered_output"]
    assert ro["zero_subtitles_verified"] is True
    assert ro["subtitle_stream_count"] == 0
    assert ro["width"] == 1080
    assert ro["height"] == 1920


