"""
ClipForge Independent Camera Cut Evaluator
==========================================
Work Item: PODCAST-CUT-VALIDATION-015
Logic Domain: L7 (Camera Cut Detection & Tracking)

Implements strict 1-to-1 bipartite nearest-neighbor matching across four standard tolerance
tiers (0ms, 40ms, 120ms, 250ms), strictly penalizing over-segmentation duplicates as False Positives,
and missing cuts as False Negatives.
"""

import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple, Union


class CameraCutEvaluator:
    """
    Evaluates camera cut detector predictions against canonical ground truth.
    """

    TOLERANCES = {
        "exact_0ms": 0.000,
        "frame_40ms": 0.040,
        "tight_120ms": 0.120,
        "loose_250ms": 0.250,
    }

    def __init__(
        self,
        ground_truth_path: Optional[str] = None,
        ground_truth_dict: Optional[Dict[str, Any]] = None,
    ):
        if ground_truth_dict is not None:
            self.gt_data = ground_truth_dict
        elif ground_truth_path is not None:
            with open(ground_truth_path, "r", encoding="utf-8") as f:
                self.gt_data = json.load(f)
        else:
            default_p = os.path.join(
                os.path.dirname(__file__),
                "authentic_podcast_ground_truth_independent_v3.json",
            )
            with open(default_p, "r", encoding="utf-8") as f:
                self.gt_data = json.load(f)

    def get_ground_truth_cuts(
        self,
        max_time_sec: float = 180.0,
        include_graphic_inserts: bool = False,
    ) -> List[float]:
        """
        Retrieves ground-truth cut timestamps within [0.0, max_time_sec].
        """
        cuts = []
        for c in self.gt_data.get("editorial_camera_cuts", []):
            t = float(c["timestamp"])
            if t <= max_time_sec:
                cuts.append(t)

        if include_graphic_inserts:
            for g in self.gt_data.get("graphic_inserts", []):
                t_start = float(g["start_sec"])
                t_end = float(g["end_sec"])
                if t_start <= max_time_sec and t_start not in cuts:
                    cuts.append(t_start)
                if t_end <= max_time_sec and t_end not in cuts:
                    cuts.append(t_end)

        cuts.sort()
        return cuts

    @classmethod
    def match_predictions_to_ground_truth(
        cls,
        predictions: List[float],
        ground_truth: List[float],
        tolerance_sec: float = 0.120,
    ) -> Dict[str, Any]:
        """
        Strict 1-to-1 bipartite nearest-neighbor matching.

        Rules:
        1. Only pairs with |pred - gt| <= tolerance_sec can match.
        2. Sorted greedily by absolute time difference.
        3. Each gt cut can match at most one prediction.
        4. Each prediction can match at most one gt cut.
        5. Extra predictions within tolerance are penalized as FP (over-segmentation).
        """
        preds = sorted([float(p) for p in predictions])
        gts = sorted([float(g) for g in ground_truth])

        if not gts:
            return {
                "tp": 0,
                "fp": len(preds),
                "fn": 0,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "mate_sec": 0.0,
                "max_error_sec": 0.0,
                "matches": [],
                "unmatched_predictions": preds,
                "unmatched_ground_truth": [],
            }

        if not preds:
            return {
                "tp": 0,
                "fp": 0,
                "fn": len(gts),
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "mate_sec": 0.0,
                "max_error_sec": 0.0,
                "matches": [],
                "unmatched_predictions": [],
                "unmatched_ground_truth": gts,
            }

        # Build candidate edges
        candidate_pairs = []
        for p_idx, p in enumerate(preds):
            for g_idx, g in enumerate(gts):
                delta = abs(p - g)
                if delta <= tolerance_sec + 1e-9:
                    candidate_pairs.append((delta, p_idx, g_idx))

        # Sort by smallest error first
        candidate_pairs.sort(key=lambda x: x[0])

        matched_preds = set()
        matched_gts = set()
        matches = []
        errors = []

        for delta, p_idx, g_idx in candidate_pairs:
            if p_idx not in matched_preds and g_idx not in matched_gts:
                matched_preds.add(p_idx)
                matched_gts.add(g_idx)
                matches.append({
                    "pred_sec": preds[p_idx],
                    "gt_sec": gts[g_idx],
                    "delta_sec": round(delta, 5),
                })
                errors.append(delta)

        tp = len(matches)
        fp = len(preds) - tp
        fn = len(gts) - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            (2.0 * precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        mate_sec = sum(errors) / len(errors) if errors else 0.0
        max_error = max(errors) if errors else 0.0

        unmatched_preds = [
            preds[i] for i in range(len(preds)) if i not in matched_preds
        ]
        unmatched_gts = [
            gts[i] for i in range(len(gts)) if i not in matched_gts
        ]

        return {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "mate_sec": round(mate_sec, 5),
            "max_error_sec": round(max_error, 5),
            "matches": matches,
            "unmatched_predictions": unmatched_preds,
            "unmatched_ground_truth": unmatched_gts,
        }

    def evaluate(
        self,
        predictions: List[float],
        max_time_sec: float = 180.0,
        include_graphic_inserts: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluates predictions against ground truth across all 4 tolerance tiers.
        """
        # Filter predictions to window
        preds_in_window = [p for p in predictions if 0.0 <= p <= max_time_sec]
        gt_cuts = self.get_ground_truth_cuts(
            max_time_sec=max_time_sec,
            include_graphic_inserts=include_graphic_inserts,
        )

        results_by_tier = {}
        for tier_name, tol_sec in self.TOLERANCES.items():
            results_by_tier[tier_name] = self.match_predictions_to_ground_truth(
                predictions=preds_in_window,
                ground_truth=gt_cuts,
                tolerance_sec=tol_sec,
            )

        return {
            "evaluation_window_sec": [0.0, max_time_sec],
            "include_graphic_inserts": include_graphic_inserts,
            "ground_truth_cuts_count": len(gt_cuts),
            "predictions_in_window_count": len(preds_in_window),
            "tolerance_tiers": results_by_tier,
        }


def evaluate_predictions(
    predictions: List[float],
    ground_truth_path: Optional[str] = None,
    max_time_sec: float = 180.0,
    include_graphic_inserts: bool = False,
) -> Dict[str, Any]:
    """Convenience helper function."""
    evaluator = CameraCutEvaluator(ground_truth_path=ground_truth_path)
    return evaluator.evaluate(
        predictions=predictions,
        max_time_sec=max_time_sec,
        include_graphic_inserts=include_graphic_inserts,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            data = json.load(f)
        # Handle dict or list
        if isinstance(data, list):
            preds = data
        elif "cut_timestamps" in data:
            preds = data["cut_timestamps"]
        elif "detected_cuts" in data:
            preds = data["detected_cuts"]
        else:
            print("Could not find cut timestamps in JSON file.")
            sys.exit(1)

        evaluator = CameraCutEvaluator()
        res_180 = evaluator.evaluate(preds, max_time_sec=180.0)
        res_300 = evaluator.evaluate(preds, max_time_sec=300.0)

        print("\n=== Evaluation on 0-180s Window ===")
        for tier, m in res_180["tolerance_tiers"].items():
            print(
                f"{tier:14s}: P={m['precision']:.3f}, R={m['recall']:.3f}, "
                f"F1={m['f1']:.3f}, TP={m['tp']}, FP={m['fp']}, FN={m['fn']}, "
                f"MATE={m['mate_sec']*1000:.1f}ms"
            )

        print("\n=== Evaluation on 0-300s Window ===")
        for tier, m in res_300["tolerance_tiers"].items():
            print(
                f"{tier:14s}: P={m['precision']:.3f}, R={m['recall']:.3f}, "
                f"F1={m['f1']:.3f}, TP={m['tp']}, FP={m['fp']}, FN={m['fn']}, "
                f"MATE={m['mate_sec']*1000:.1f}ms"
            )
    else:
        print("Usage: python evaluate_independent_camera_cuts.py <predictions.json>")

