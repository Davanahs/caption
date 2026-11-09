"""
Unit and Regression Tests for Independent Camera Cut Evaluator and Ground Truth Manifest
========================================================================================
Work Item: PODCAST-CUT-VALIDATION-015
Logic Domain: L7 (Camera Cut Detection & Tracking)
"""

import hashlib
import json
import os
import pytest

from backend.benchmarks.evaluate_independent_camera_cuts import (
    CameraCutEvaluator,
    evaluate_predictions,
)


class TestCameraCutEvaluatorMatching:
    """Tests for bipartite 1-to-1 matching logic and metrics."""

    def test_perfect_match(self):
        gt = [2.24, 17.16, 32.32]
        pred = [2.24, 17.16, 32.32]

        res = CameraCutEvaluator.match_predictions_to_ground_truth(
            predictions=pred,
            ground_truth=gt,
            tolerance_sec=0.000,
        )
        assert res["tp"] == 3
        assert res["fp"] == 0
        assert res["fn"] == 0
        assert res["precision"] == 1.0
        assert res["recall"] == 1.0
        assert res["f1"] == 1.0
        assert res["mate_sec"] == 0.0

    def test_empty_predictions(self):
        gt = [2.24, 17.16, 32.32]
        pred = []

        res = CameraCutEvaluator.match_predictions_to_ground_truth(
            predictions=pred,
            ground_truth=gt,
            tolerance_sec=0.120,
        )
        assert res["tp"] == 0
        assert res["fp"] == 0
        assert res["fn"] == 3
        assert res["precision"] == 0.0
        assert res["recall"] == 0.0
        assert res["f1"] == 0.0
        assert res["mate_sec"] == 0.0

    def test_empty_ground_truth(self):
        gt = []
        pred = [10.0, 20.0]

        res = CameraCutEvaluator.match_predictions_to_ground_truth(
            predictions=pred,
            ground_truth=gt,
            tolerance_sec=0.120,
        )
        assert res["tp"] == 0
        assert res["fp"] == 2
        assert res["fn"] == 0
        assert res["precision"] == 0.0
        assert res["recall"] == 0.0
        assert res["f1"] == 0.0

    def test_duplicate_prediction_oversegmentation_penalty(self):
        """
        Critical rule: Multiple predictions near one GT cut MUST NOT be double-counted.
        Only one gets TP, extra predictions become FP.
        """
        gt = [17.16]
        # Two predictions very close to 17.16s
        pred = [17.14, 17.18]

        res = CameraCutEvaluator.match_predictions_to_ground_truth(
            predictions=pred,
            ground_truth=gt,
            tolerance_sec=0.120,
        )
        assert res["tp"] == 1, "Only one prediction should match GT cut"
        assert res["fp"] == 1, "Duplicate prediction must be penalized as FP"
        assert res["fn"] == 0
        assert res["precision"] == 0.5  # 1 TP / (1 TP + 1 FP)
        assert res["recall"] == 1.0     # 1 TP / (1 TP + 0 FN)
        assert len(res["matches"]) == 1

    def test_duplicate_identical_prediction_timestamps(self):
        """Tests that identical duplicate prediction timestamps are penalized as FP."""
        gt = [10.0]
        pred = [10.0, 10.0, 10.0]

        res = CameraCutEvaluator.match_predictions_to_ground_truth(
            predictions=pred,
            ground_truth=gt,
            tolerance_sec=0.120,
        )
        assert res["tp"] == 1
        assert res["fp"] == 2
        assert res["fn"] == 0
        assert pytest.approx(res["precision"], rel=1e-3) == 0.3333
        assert res["recall"] == 1.0

    def test_tolerance_boundaries(self):
        gt = [10.000]
        # At 10.040s, delta is 40ms
        pred_40ms = [10.040]
        # At 10.120s, delta is 120ms
        pred_120ms = [10.120]
        # At 10.250s, delta is 250ms
        pred_250ms = [10.250]
        # At 10.300s, delta is 300ms
        pred_300ms = [10.300]

        # Exact tier (0ms)
        r0 = CameraCutEvaluator.match_predictions_to_ground_truth(pred_40ms, gt, 0.000)
        assert r0["tp"] == 0

        # 40ms tier
        r40 = CameraCutEvaluator.match_predictions_to_ground_truth(pred_40ms, gt, 0.040)
        assert r40["tp"] == 1

        # 120ms tier with 120ms pred
        r120 = CameraCutEvaluator.match_predictions_to_ground_truth(pred_120ms, gt, 0.120)
        assert r120["tp"] == 1

        # 120ms tier with 250ms pred (fails)
        r120_fail = CameraCutEvaluator.match_predictions_to_ground_truth(pred_250ms, gt, 0.120)
        assert r120_fail["tp"] == 0

        # 250ms tier with 250ms pred (matches)
        r250 = CameraCutEvaluator.match_predictions_to_ground_truth(pred_250ms, gt, 0.250)
        assert r250["tp"] == 1

        # 250ms tier with 300ms pred (fails)
        r250_fail = CameraCutEvaluator.match_predictions_to_ground_truth(pred_300ms, gt, 0.250)
        assert r250_fail["tp"] == 0

    def test_mate_calculation(self):
        gt = [10.0, 20.0]
        pred = [10.02, 19.96]  # errors: 0.02, 0.04 -> mean = 0.03

        res = CameraCutEvaluator.match_predictions_to_ground_truth(
            predictions=pred,
            ground_truth=gt,
            tolerance_sec=0.120,
        )
        assert res["tp"] == 2
        assert pytest.approx(res["mate_sec"], rel=1e-4) == 0.030


class TestIndependentGroundTruthManifest:
    """Tests schema, provenance, and cryptographic integrity of v3 ground truth."""

    @pytest.fixture
    def gt_path(self):
        return os.path.join(
            "D:\\automation video clips\\clipforge",
            "backend",
            "benchmarks",
            "authentic_podcast_ground_truth_independent_v3.json",
        )

    @pytest.fixture
    def prov_path(self):
        return os.path.join(
            "D:\\automation video clips\\clipforge",
            "backend",
            "benchmarks",
            "ground_truth_provenance_manifest.json",
        )

    @pytest.fixture
    def pass2_path(self):
        return os.path.join(
            "D:\\automation video clips\\clipforge",
            "backend",
            "benchmarks",
            "independent_reviewer_pass2_annotations.json",
        )

    def test_v3_file_exists_and_valid_json(self, gt_path):
        assert os.path.exists(gt_path), f"File {gt_path} does not exist"
        with open(gt_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == "3.0.0"
        assert data["work_item"] == "PODCAST-CUT-VALIDATION-015"
        assert data["is_synthetic"] is False
        assert data["duration_sec"] == 981.08
        assert data["nominal_fps"] == 25.0

    def test_v3_cut_counts_and_structure(self, gt_path):
        with open(gt_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cuts = data["editorial_camera_cuts"]
        assert len(cuts) == 30, f"Expected 30 total editorial cuts in 0-300s, got {len(cuts)}"

        cuts_0_180 = [c for c in cuts if c["timestamp"] <= 180.0]
        cuts_180_300 = [c for c in cuts if c["timestamp"] > 180.0]

        assert len(cuts_0_180) == 21, f"Expected 21 cuts in 0-180s, got {len(cuts_0_180)}"
        assert len(cuts_180_300) == 9, f"Expected 9 cuts in 180-300s, got {len(cuts_180_300)}"

        # Validate monotonic timestamps and frame indices
        for i in range(1, len(cuts)):
            assert cuts[i]["frame_index"] > cuts[i-1]["frame_index"]
            assert cuts[i]["timestamp"] > cuts[i-1]["timestamp"]
            # verify frame-accurate arithmetic
            expected_sec = round(cuts[i]["frame_index"] / 25.0, 2)
            assert cuts[i]["timestamp"] == expected_sec

    def test_sub_second_graphic_insert_separation(self, gt_path):
        """Verifies that graphic inserts can be separated from pure camera cuts."""
        evaluator = CameraCutEvaluator(ground_truth_path=gt_path)
        editorial_only = evaluator.get_ground_truth_cuts(max_time_sec=180.0, include_graphic_inserts=False)
        all_transitions = evaluator.get_ground_truth_cuts(max_time_sec=180.0, include_graphic_inserts=True)

        assert len(editorial_only) == 21
        assert len(all_transitions) == 24  # 21 cuts + 3 graphic insert endpoints

    def test_two_independent_passes_convergence(self, gt_path, pass2_path):
        """
        Critical validation: Confirms that Pass 1 (v3) and Pass 2 (Reviewer Pass)
        converged on the exact same 30 camera cuts across the 0-300s window.
        """
        assert os.path.exists(pass2_path), f"File {pass2_path} does not exist"
        with open(gt_path, "r", encoding="utf-8") as f:
            v3 = json.load(f)
        with open(pass2_path, "r", encoding="utf-8") as f:
            p2 = json.load(f)

        v3_cuts = [(c["frame_index"], c["timestamp"]) for c in v3["editorial_camera_cuts"]]
        p2_cuts = [(c["frame_index"], c["timestamp"]) for c in p2["editorial_cuts"]]

        assert len(v3_cuts) == 30
        assert len(p2_cuts) == 30
        assert v3_cuts == p2_cuts, "Pass 1 and Pass 2 must reach 100% frame-level convergence"

    def test_v3_hash_matches_provenance_manifest(self, gt_path, prov_path):
        assert os.path.exists(prov_path), f"File {prov_path} does not exist"
        with open(prov_path, "r", encoding="utf-8") as f:
            prov = json.load(f)

        with open(gt_path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()

        manifest_hash = prov["ground_truth_artifacts"]["v3_0_0_independent_ground_truth"]["sha256"]
        assert actual_hash == manifest_hash, (
            f"Ground truth hash {actual_hash} does not match provenance manifest {manifest_hash}"
        )

    def test_evaluator_against_v3_gt(self, gt_path):
        evaluator = CameraCutEvaluator(ground_truth_path=gt_path)
        gt_180 = evaluator.get_ground_truth_cuts(max_time_sec=180.0)
        gt_300 = evaluator.get_ground_truth_cuts(max_time_sec=300.0)

        assert len(gt_180) == 21
        assert len(gt_300) == 30

        # Self-evaluation must yield 100% precision and recall across all tiers
        res = evaluator.evaluate(predictions=gt_180, max_time_sec=180.0)
        for tier_name, tier_metrics in res["tolerance_tiers"].items():
            assert tier_metrics["tp"] == 21
            assert tier_metrics["fp"] == 0
            assert tier_metrics["fn"] == 0
            assert tier_metrics["precision"] == 1.0
            assert tier_metrics["recall"] == 1.0
            assert tier_metrics["f1"] == 1.0
            assert tier_metrics["mate_sec"] == 0.0
