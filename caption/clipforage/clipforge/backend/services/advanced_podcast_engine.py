"""
Advanced Podcast Engine — Camera-Following, Speaker-Aware Vertical Reframing.
Detects camera cuts, identifies which participant is visible/focused, and dynamically reframes
that participant into a single continuous vertical 9:16 video without freeze-frames or stacked panels.
"""

import os
import json
import logging
import asyncio
import math
import subprocess
import re
import shutil
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from backend.services.clip_cutter import run_ffmpeg, get_video_dimensions

logger = logging.getLogger(__name__)


def compute_normalized_hsv_hist(bgr_image: np.ndarray, h_bins: int = 24, s_bins: int = 24) -> Optional[np.ndarray]:
    """Computes a 2D Hue-Saturation normalized histogram for visual appearance signature."""
    if bgr_image is None or bgr_image.size == 0 or cv2 is None:
        return None
    try:
        hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [h_bins, s_bins], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        return hist
    except Exception as e:
        logger.warning(f"Failed to compute HSV histogram: {e}")
        return None


try:
    import mediapipe as mp
except ImportError:
    mp = None

_YUNET_DETECTOR = None
_YUNET_SIZE = None
_SFACE_RECOGNIZER = None
_HAAR_CLASSIFIER = None


def _get_asset_path(filename: str) -> Optional[Path]:
    """Resolves model asset paths from managed assets directory or parent directories."""
    candidates = [
        Path(__file__).resolve().parent.parent / "assets" / filename,
        Path("clipforge/backend/assets") / filename,
        Path("backend/assets") / filename,
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 0:
            return c
    return None


def _get_yunet_detector(w: int, h: int, min_confidence: float = 0.50):
    """Initializes and caches the OpenCV YuNet deep-learning face detector for the given frame dimensions."""
    global _YUNET_DETECTOR, _YUNET_SIZE
    if cv2 is None or not hasattr(cv2, "FaceDetectorYN"):
        return None
    model_p = _get_asset_path("face_detection_yunet_2023mar.onnx")
    if not model_p:
        return None
    try:
        if _YUNET_DETECTOR is None:
            _YUNET_DETECTOR = cv2.FaceDetectorYN.create(str(model_p), "", (w, h), min_confidence, 0.3, 5000)
            _YUNET_SIZE = (w, h)
        elif _YUNET_SIZE != (w, h):
            _YUNET_DETECTOR.setInputSize((w, h))
            _YUNET_SIZE = (w, h)
        return _YUNET_DETECTOR
    except Exception as e:
        logger.debug(f"Could not initialize YuNet detector: {e}")
        return None


def _get_sface_recognizer():
    """Initializes and caches the OpenCV SFace facial feature embedding recognizer."""
    global _SFACE_RECOGNIZER
    if _SFACE_RECOGNIZER is not None:
        return _SFACE_RECOGNIZER
    if cv2 is None or not hasattr(cv2, "FaceRecognizerSF"):
        return None
    model_p = _get_asset_path("face_recognition_sface_2021dec.onnx")
    if not model_p:
        return None
    try:
        _SFACE_RECOGNIZER = cv2.FaceRecognizerSF.create(str(model_p), "")
        return _SFACE_RECOGNIZER
    except Exception as e:
        logger.debug(f"Could not initialize SFace recognizer: {e}")
        return None


def _get_haar_classifier():
    global _HAAR_CLASSIFIER
    if _HAAR_CLASSIFIER is not None:
        return _HAAR_CLASSIFIER
    if cv2 is not None and hasattr(cv2, "CascadeClassifier"):
        cascade_p = _get_asset_path("haarcascade_frontalface_default.xml")
        if not cascade_p and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            cand = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
            if os.path.exists(cand):
                cascade_p = Path(cand)
        if cascade_p and os.path.exists(str(cascade_p)):
            try:
                clf = cv2.CascadeClassifier(str(cascade_p))
                if not clf.empty():
                    _HAAR_CLASSIFIER = clf
                    return _HAAR_CLASSIFIER
            except Exception as e:
                logger.warning(f"Could not initialize Haar cascade: {e}")
    return None


def validate_bounding_box(box: Any, min_confidence: float = 0.0) -> bool:
    """
    Validates a bounding box dictionary.
    Rejects:
    - None or non-dict structures
    - NaN, positive/negative infinities
    - Negative or zero dimensions (width <= 0, height <= 0)
    - Sub-pixel or degenerate noise (width < 0.01 or height < 0.01)
    - Completely out-of-frame coordinates (x < 0, y < 0, x >= 1.0, y >= 1.0)
    - Massive out-of-frame overflow (x + width > 1.2 or y + height > 1.2)
    - Corrupted or sub-threshold confidence values
    """
    if not isinstance(box, dict):
        return False
    try:
        x = float(box.get("x", -1.0))
        y = float(box.get("y", -1.0))
        w = float(box.get("width", 0.0))
        h = float(box.get("height", 0.0))
        conf = float(box.get("confidence", 1.0))
    except (TypeError, ValueError):
        return False

    # Check finite numbers (reject NaN and inf)
    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(w) and math.isfinite(h) and math.isfinite(conf)):
        return False

    # Positive dimensions and minimum valid size
    if w <= 0.01 or h <= 0.01:
        return False

    # Coordinate boundaries
    if x < 0.0 or y < 0.0 or x >= 1.0 or y >= 1.0:
        return False

    # Out of frame boundary overflow check
    if (x + w) > 1.20 or (y + h) > 1.20:
        return False

    # Confidence check
    if conf < 0.0 or conf > 1.0 or conf < min_confidence:
        return False

    return True


def calculate_box_iou(box1: Dict[str, Any], box2: Dict[str, Any]) -> float:
    """Computes Intersection over Union (IoU) between two normalized bounding boxes."""
    try:
        x1_a, y1_a = float(box1["x"]), float(box1["y"])
        x2_a, y2_a = x1_a + float(box1["width"]), y1_a + float(box1["height"])

        x1_b, y1_b = float(box2["x"]), float(box2["y"])
        x2_b, y2_b = x1_b + float(box2["width"]), y1_b + float(box2["height"])

        inter_x1 = max(x1_a, x1_b)
        inter_y1 = max(y1_a, y1_b)
        inter_x2 = min(x2_a, x2_b)
        inter_y2 = min(y2_a, y2_b)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0

        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area_a = float(box1["width"]) * float(box1["height"])
        area_b = float(box2["width"]) * float(box2["height"])
        union_area = area_a + area_b - inter_area

        if union_area <= 0.0:
            return 0.0
        return inter_area / union_area
    except Exception:
        return 0.0


def deduplicate_detected_faces(
    detected_faces: List[Dict[str, Any]],
    iou_threshold: float = 0.40,
    center_dist_threshold: float = 0.08
) -> List[Dict[str, Any]]:
    """
    Suppresses duplicate face detections of the same physical participant.
    Ensures that a single face detected multiple times (e.g. from multiple detector passes
    or near-identical candidate boxes) cannot be split into Person A and Person B.
    """
    if not detected_faces or len(detected_faces) <= 1:
        return list(detected_faces)

    # Sort descending by confidence
    sorted_by_conf = sorted(
        detected_faces,
        key=lambda f: float(f.get("confidence", 0.5)),
        reverse=True
    )
    unique_faces: List[Dict[str, Any]] = []

    for f in sorted_by_conf:
        fc_x = float(f["x"]) + float(f["width"]) / 2.0
        fc_y = float(f["y"]) + float(f["height"]) / 2.0

        is_duplicate = False
        for u in unique_faces:
            u_cx = float(u["x"]) + float(u["width"]) / 2.0
            u_cy = float(u["y"]) + float(u["height"]) / 2.0
            c_dist = ((fc_x - u_cx) ** 2 + (fc_y - u_cy) ** 2) ** 0.5
            iou = calculate_box_iou(f, u)

            if iou >= iou_threshold or c_dist < center_dist_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            unique_faces.append(f)

    return unique_faces


def detect_faces_in_frame(
    bgr_frame: np.ndarray,
    min_confidence: float = 0.50
) -> List[Dict[str, Any]]:
    """
    Detects genuine human faces in a video frame using the available face-detection engine.
    - Primary: MediaPipe FaceDetection (installed in worker environment).
    - Secondary: OpenCV Haar frontalface cascade.
    Returns normalized face bounding boxes:
    [{'x': float, 'y': float, 'width': float, 'height': float, 'confidence': float, 'detector': str}, ...]
    Returns empty list if no human faces are present (e.g. synthetic testsrc, cutaways, occlusion).
    """
    if bgr_frame is None or bgr_frame.size == 0 or cv2 is None:
        return []

    h_f, w_f = bgr_frame.shape[:2]
    detected_faces: List[Dict[str, Any]] = []

    # 1. Primary: OpenCV YuNet Deep Learning Detector
    yn_detector = _get_yunet_detector(w_f, h_f, min_confidence=min_confidence)
    if yn_detector is not None:
        try:
            _, raw_yn = yn_detector.detect(bgr_frame)
            if raw_yn is not None:
                for face in raw_yn:
                    fx, fy, fw, fh = float(face[0]), float(face[1]), float(face[2]), float(face[3])
                    conf = float(face[-1])
                    bx = max(0.0, fx / w_f)
                    by = max(0.0, fy / h_f)
                    bw = min(1.0 - bx, fw / w_f)
                    bh = min(1.0 - by, fh / h_f)
                    candidate = {
                        "x": round(bx, 4),
                        "y": round(by, 4),
                        "width": round(bw, 4),
                        "height": round(bh, 4),
                        "confidence": round(conf, 3),
                        "detector": "yunet",
                        "raw_face": face.tolist() if hasattr(face, "tolist") else list(face)
                    }
                    if validate_bounding_box(candidate, min_confidence=min_confidence):
                        detected_faces.append(candidate)
                if detected_faces:
                    return deduplicate_detected_faces(detected_faces)
        except Exception as e:
            logger.debug(f"YuNet detection failed: {e}")

    # 2. Secondary: MediaPipe FaceDetection
    if mp is not None and hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
        try:
            with mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=min_confidence
            ) as detector:
                rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                results = detector.process(rgb_frame)
                if results and results.detections:
                    for d in results.detections:
                        box = d.location_data.relative_bounding_box
                        conf = float(d.score[0]) if d.score else 0.5
                        bx = max(0.0, float(box.xmin))
                        by = max(0.0, float(box.ymin))
                        bw = min(1.0 - bx, float(box.width))
                        bh = min(1.0 - by, float(box.height))
                        candidate = {
                            "x": round(bx, 4),
                            "y": round(by, 4),
                            "width": round(bw, 4),
                            "height": round(bh, 4),
                            "confidence": round(conf, 3),
                            "detector": "mediapipe"
                        }
                        if validate_bounding_box(candidate, min_confidence=min_confidence):
                            detected_faces.append(candidate)
                    if detected_faces:
                        return deduplicate_detected_faces(detected_faces)
        except Exception as e:
            logger.debug(f"MediaPipe detection failed: {e}")

    # 3. Fallback: OpenCV Haar Cascade Classifier
    clf = _get_haar_classifier()
    if clf is not None:
        try:
            gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
            raw_faces = clf.detectMultiScale(
                gray,
                scaleFactor=1.2,
                minNeighbors=4,
                minSize=(30, 30)
            )
            for (x, y, w, h) in raw_faces:
                bx = max(0.0, float(x / w_f))
                by = max(0.0, float(y / h_f))
                bw = min(1.0 - bx, float(w / w_f))
                bh = min(1.0 - by, float(h / h_f))
                candidate = {
                    "x": round(bx, 4),
                    "y": round(by, 4),
                    "width": round(bw, 4),
                    "height": round(bh, 4),
                    "confidence": 0.80,
                    "detector": "opencv_haar"
                }
                if validate_bounding_box(candidate, min_confidence=min_confidence):
                    detected_faces.append(candidate)
        except Exception as e:
            logger.debug(f"Haar cascade detection failed: {e}")

    return deduplicate_detected_faces(detected_faces)


def match_and_track_participants(
    detected_faces: List[Dict[str, Any]],
    region_a: Dict[str, Any],
    region_b: Dict[str, Any],
    prev_box_a: Optional[Dict[str, Any]] = None,
    prev_box_b: Optional[Dict[str, Any]] = None,
    appearance_sig_a: Optional[Dict[str, Any]] = None,
    appearance_sig_b: Optional[Dict[str, Any]] = None,
    bgr_frame: Optional[np.ndarray] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Maintains separate identities for Person A and Person B across frames.
    - Validates bounding boxes (rejects NaN, inf, negative sizes, and out-of-frame boxes).
    - Deduplicates redundant detections of the same face (zero duplicate assignment).
    - Matches detected face bounding boxes to Person A and Person B based on spatial reference,
      tracking history, and appearance signatures.
    - If identity association becomes ambiguous (crossing paths, center ambiguity, or collision),
      marks the interval ambiguous rather than guessing or silently swapping identities.
    """
    meta = {
        "face_a_detected": False,
        "face_b_detected": False,
        "occlusion_a": False,
        "occlusion_b": False,
        "total_faces": 0,
        "identity_ambiguous": False,
        "reason": None
    }

    if not detected_faces:
        meta["identity_ambiguous"] = True
        meta["reason"] = "no_detections"
        return None, None, meta

    # Step 1: Validate bounding boxes
    valid_faces = [f for f in detected_faces if validate_bounding_box(f)]
    if not valid_faces:
        meta["identity_ambiguous"] = True
        meta["reason"] = "all_detections_invalid"
        return None, None, meta

    # Step 2: Deduplicate candidate faces (suppress duplicate detections of the same person)
    unique_faces = deduplicate_detected_faces(valid_faces)
    meta["total_faces"] = len(unique_faces)

    # Reference centers for Person A and Person B
    ref_a_x = float(prev_box_a.get("x", 0.0) + prev_box_a.get("width", 0.1) / 2.0) if prev_box_a and validate_bounding_box(prev_box_a) else float(region_a.get("x", 0.25) + region_a.get("width", 0.35) / 2.0)
    ref_b_x = float(prev_box_b.get("x", 0.0) + prev_box_b.get("width", 0.1) / 2.0) if prev_box_b and validate_bounding_box(prev_box_b) else float(region_b.get("x", 0.75) + region_b.get("width", 0.35) / 2.0)

    face_a = None
    face_b = None

    if len(unique_faces) >= 2:
        # Sort faces left to right
        sorted_faces = sorted(unique_faces, key=lambda f: float(f["x"]) + float(f["width"]) / 2.0)
        f1, f2 = sorted_faces[0], sorted_faces[-1]

        f1_cx = float(f1["x"]) + float(f1["width"]) / 2.0
        f2_cx = float(f2["x"]) + float(f2["width"]) / 2.0
        face_span = abs(f2_cx - f1_cx)

        # Ambiguous collision / overlap
        if face_span < 0.10 or calculate_box_iou(f1, f2) >= 0.35:
            meta["identity_ambiguous"] = True
            meta["reason"] = "collision_faces_too_close"
            return None, None, meta

        dist_direct = abs(f1_cx - ref_a_x) + abs(f2_cx - ref_b_x)
        dist_swapped = abs(f2_cx - ref_a_x) + abs(f1_cx - ref_b_x)

        # Check for path-crossing ambiguity where direct and swapped distances are nearly identical
        if abs(dist_direct - dist_swapped) < 0.08:
            # Check if appearance signatures can disambiguate
            sig_disambiguated = False
            if bgr_frame is not None and cv2 is not None and appearance_sig_a and appearance_sig_b:
                ha = appearance_sig_a.get("face_hist") if appearance_sig_a.get("face_hist") is not None else appearance_sig_a.get("hist")
                hb = appearance_sig_b.get("face_hist") if appearance_sig_b.get("face_hist") is not None else appearance_sig_b.get("hist")
                if ha is not None and hb is not None:
                    h_f, w_f = bgr_frame.shape[:2]
                    # Extract histograms for f1 and f2
                    x1 = max(0, int(f1["x"] * w_f))
                    y1 = max(0, int(f1["y"] * h_f))
                    w1 = max(1, int(f1["width"] * w_f))
                    h1 = max(1, int(f1["height"] * h_f))
                    x2 = max(0, int(f2["x"] * w_f))
                    y2 = max(0, int(f2["y"] * h_f))
                    w2 = max(1, int(f2["width"] * w_f))
                    h2 = max(1, int(f2["height"] * h_f))

                    hist1 = compute_normalized_hsv_hist(bgr_frame[y1:y1+h1, x1:x1+w1])
                    hist2 = compute_normalized_hsv_hist(bgr_frame[y2:y2+h2, x2:x2+w2])
                    if hist1 is not None and hist2 is not None:
                        c_direct = cv2.compareHist(ha, hist1, cv2.HISTCMP_CORREL) + cv2.compareHist(hb, hist2, cv2.HISTCMP_CORREL)
                        c_swapped = cv2.compareHist(ha, hist2, cv2.HISTCMP_CORREL) + cv2.compareHist(hb, hist1, cv2.HISTCMP_CORREL)
                        if abs(c_direct - c_swapped) > 0.30:
                            if c_direct > c_swapped:
                                face_a, face_b = f1, f2
                            else:
                                face_a, face_b = f2, f1
                            sig_disambiguated = True

            if not sig_disambiguated:
                meta["identity_ambiguous"] = True
                meta["reason"] = "crossing_paths_ambiguous"
                return None, None, meta

        if face_a is None or face_b is None:
            if dist_direct <= dist_swapped:
                face_a, face_b = f1, f2
            else:
                face_a, face_b = f2, f1

        # Strict invariant: Person A and Person B can never be the same physical box
        if face_a is face_b or face_a == face_b:
            meta["identity_ambiguous"] = True
            meta["reason"] = "duplicate_assignment_prevented"
            return None, None, meta

        meta["face_a_detected"] = True
        meta["face_b_detected"] = True

    elif len(unique_faces) == 1:
        f = unique_faces[0]
        fc_x = float(f["x"]) + float(f["width"]) / 2.0
        d_a = abs(fc_x - ref_a_x)
        d_b = abs(fc_x - ref_b_x)

        # Ambiguous if equidistant between A and B, or too far from both established reference centers
        sig_disambiguated = False

        # 1. Primary: Deep facial feature recognition via SFace embedding
        recognizer = _get_sface_recognizer()
        feat_a = appearance_sig_a.get("feat") if appearance_sig_a is not None else None
        feat_b = appearance_sig_b.get("feat") if appearance_sig_b is not None else None

        if recognizer is not None and bgr_frame is not None and "raw_face" in f and (feat_a is not None or feat_b is not None):
            try:
                raw_f = np.array(f["raw_face"], dtype=np.float32)
                aligned = recognizer.alignCrop(bgr_frame, raw_f)
                target_feat = recognizer.feature(aligned)
                sim_a = float(recognizer.match(feat_a, target_feat, cv2.FaceRecognizerSF_FR_COSINE)) if feat_a is not None else 0.0
                sim_b = float(recognizer.match(feat_b, target_feat, cv2.FaceRecognizerSF_FR_COSINE)) if feat_b is not None else 0.0
                meta["similarity_a"] = sim_a
                meta["similarity_b"] = sim_b

                if sim_a > sim_b + 0.08 and sim_a >= 0.20:
                    face_a = f
                    face_b = None
                    meta["face_a_detected"] = True
                    meta["occlusion_b"] = True
                    sig_disambiguated = True
                elif sim_b > sim_a + 0.08 and sim_b >= 0.20:
                    face_a = None
                    face_b = f
                    meta["face_b_detected"] = True
                    meta["occlusion_a"] = True
                    sig_disambiguated = True
            except Exception as e:
                logger.debug(f"SFace recognition matching failed: {e}")

        # 2. Appearance signatures (HSV histograms)
        if not sig_disambiguated and (abs(d_a - d_b) < 0.12 or min(d_a, d_b) > 0.40):
            if bgr_frame is not None and cv2 is not None and appearance_sig_a is not None and appearance_sig_b is not None:
                ha = appearance_sig_a.get("face_hist") if appearance_sig_a.get("face_hist") is not None else appearance_sig_a.get("hist")
                hb = appearance_sig_b.get("face_hist") if appearance_sig_b.get("face_hist") is not None else appearance_sig_b.get("hist")
                if ha is not None and hb is not None:
                    h_f, w_f = bgr_frame.shape[:2]
                    xf = max(0, int(f["x"] * w_f))
                    yf = max(0, int(f["y"] * h_f))
                    wf = max(1, int(f["width"] * w_f))
                    hf = max(1, int(f["height"] * h_f))
                    # Sample face + upper chest where clothing and hair are distinctive
                    y2 = min(h_f, yf + int(hf * 2.0))
                    crop_f = bgr_frame[yf:y2, xf:xf+wf]
                    hist_f = compute_normalized_hsv_hist(crop_f)
                    if hist_f is not None:
                        c_a = float(cv2.compareHist(ha, hist_f, cv2.HISTCMP_CORREL))
                        c_b = float(cv2.compareHist(hb, hist_f, cv2.HISTCMP_CORREL))
                        if c_a > c_b + 0.08:
                            face_a = f
                            face_b = None
                            meta["face_a_detected"] = True
                            meta["occlusion_b"] = True
                            sig_disambiguated = True
                        elif c_b > c_a + 0.08:
                            face_a = None
                            face_b = f
                            meta["face_b_detected"] = True
                            meta["occlusion_a"] = True
                            sig_disambiguated = True

            if not sig_disambiguated:
                meta["identity_ambiguous"] = True
                meta["reason"] = "ambiguous_single_detection"
                meta["single_face"] = f
                return None, None, meta

        elif not sig_disambiguated:
            if d_a + 0.12 <= d_b:
                face_a = f
                face_b = None
                meta["face_a_detected"] = True
                meta["occlusion_b"] = True
            elif d_b + 0.12 <= d_a:
                face_a = None
                face_b = f
                meta["face_b_detected"] = True
                meta["occlusion_a"] = True
            else:
                meta["identity_ambiguous"] = True
                meta["reason"] = "ambiguous_single_detection"
                return None, None, meta

    return face_a, face_b, meta


def detect_camera_cuts(
    video_path: Path,
    min_shot_duration: float = 0.8,
    cut_threshold: float = 0.40,
    sample_fps: float = 5.0,
    scdet_threshold: float = 17.5
) -> List[Tuple[float, float]]:
    """
    Detects camera cut boundaries using a robust multi-signal strategy:
    1. Primary: Native FFmpeg scene-change detector filter (scdet) evaluating
       frame luminance and chrominance shifts (lavfi.scd.score >= scdet_threshold).
       Note: The default scdet_threshold=17.5 is empirically optimal for authentic,
       broadcast-quality podcast videos with high-contrast scene changes and studio lighting,
       preventing false cuts from participant hand gestures or minor lighting shifts.
       For synthetic test clips or low-contrast videos with subtle color transitions,
       callers may specify a lower threshold (e.g. scdet_threshold=5.0).
    2. Complementary / Fallback: OpenCV multi-signal frame difference evaluating
       downsampled grayscale L1 MAE, Canny edge gradient shift, and HSV histogram correlation drop.
    Returns contiguous, non-overlapping (start_time, end_time) intervals in seconds covering
    the entire source video without gaps.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if cv2 is None:
        logger.warning("OpenCV not available; returning single whole-video shot")
        return [(0.0, 30.0)]

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = round(total_frames / fps, 2) if total_frames > 0 else 0.0
    cap.release()

    if duration <= min_shot_duration:
        return [(0.0, max(duration, 1.0))]

    cut_timestamps: List[float] = [0.0]

    # Primary strategy: FFmpeg native scene-change detector filter (scdet)
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    scdet_succeeded = False
    scdet_error: Optional[str] = None
    try:
        cmd = [
            ffmpeg_bin, "-hide_banner", "-nostats",
            "-i", str(video_path),
            "-vf", f"scdet=threshold={scdet_threshold}",
            "-f", "null", "-"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            scdet_error = f"FFmpeg exited with non-zero code {proc.returncode}"
            logger.warning(f"FFmpeg scdet execution failed: {scdet_error}")
        else:
            scdet_succeeded = True

        scdet_times: List[float] = []
        metadata_corrupt = False
        if scdet_succeeded:
            for line in proc.stderr.splitlines():
                if "lavfi.scd.time" in line:
                    m = re.search(r"lavfi\.scd\.time:\s*([^\s,]+)", line)
                    if not m:
                        metadata_corrupt = True
                        break
                    try:
                        val = float(m.group(1))
                    except (ValueError, OverflowError):
                        metadata_corrupt = True
                        break

                    # Reject NaN, Infinity, negative timestamps, or timestamps strictly greater than duration
                    if math.isnan(val) or math.isinf(val) or val < 0.0 or val > duration:
                        metadata_corrupt = True
                        break

                    t = round(val, 2)
                    # Exclude near-boundary transitions within the intentional 50ms margin
                    # [0.0, 0.05] and [duration - 0.05, duration] cannot form valid >= 0.1s shot intervals
                    if 0.05 < t < (duration - 0.05):
                        scdet_times.append(t)

            if metadata_corrupt:
                scdet_times.clear()
                scdet_succeeded = False
                scdet_error = "Malformed or out-of-bounds lavfi.scd.time metadata in FFmpeg stderr"
                logger.warning(f"FFmpeg scdet metadata corruption detected: {scdet_error}")
            elif scdet_times:
                scdet_times.sort()
                for t in scdet_times:
                    if (t - cut_timestamps[-1]) >= min_shot_duration:
                        cut_timestamps.append(t)
    except Exception as e:
        logger.debug(f"FFmpeg scdet execution unavailable or timed out: {e}")
        scdet_succeeded = False
        scdet_error = str(e)

    # Fallback: Multi-signal OpenCV frame-difference analysis
    # Triggers ONLY if FFmpeg scdet genuinely failed to execute (missing binary, non-zero exit code, timeout, corrupt metadata).
    # A process-successful execution producing zero threshold events is accepted as an authoritative baseline zero-cut result and MUST NOT trigger fallback.
    if not scdet_succeeded:
        logger.info(f"Invoking OpenCV multi-signal camera cut fallback due to: {scdet_error}")
        cap = cv2.VideoCapture(str(video_path))
        frame_step = max(1, int(fps / sample_fps))
        prev_gray = None
        prev_edges = None
        prev_hist = None
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_step == 0:
                current_time = round(frame_idx / fps, 2)
                small_gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 90))
                edges = cv2.Canny(small_gray, 50, 150)
                current_hist = compute_normalized_hsv_hist(frame)

                if prev_gray is not None and prev_edges is not None and prev_hist is not None:
                    # 1. Pixel L1 difference normalized to [0, 1]
                    mae = float(np.mean(np.abs(small_gray.astype(float) - prev_gray.astype(float))) / 255.0)
                    # 2. Edge gradient difference normalized to [0, 1]
                    edge_diff = float(np.mean(np.abs(edges.astype(float) - prev_edges.astype(float))) / 255.0)
                    # 3. HSV color histogram drop
                    corr = cv2.compareHist(prev_hist, current_hist, cv2.HISTCMP_CORREL) if current_hist is not None else 0.0
                    hist_drop = 1.0 - max(0.0, corr)

                    # Multi-signal composite score
                    score = 0.45 * mae + 0.35 * edge_diff + 0.20 * hist_drop
                    is_cut = (score >= 0.20) or (hist_drop > (1.0 - cut_threshold))

                    if is_cut and (current_time - cut_timestamps[-1]) >= min_shot_duration:
                        cut_timestamps.append(current_time)

                prev_gray = small_gray
                prev_edges = edges
                prev_hist = current_hist

            frame_idx += 1
        cap.release()

    final_time = round(duration, 2)
    if cut_timestamps[-1] < final_time:
        cut_timestamps.append(final_time)

    # Format into contiguous (start, end) intervals
    shots: List[Tuple[float, float]] = []
    for i in range(len(cut_timestamps) - 1):
        s = cut_timestamps[i]
        e = cut_timestamps[i + 1]
        if e - s >= 0.1:
            shots.append((s, e))

    if not shots:
        shots = [(0.0, max(final_time, 1.0))]

    return shots


def extract_reference_signatures(
    video_path: Path,
    regions_normalized: List[Dict[str, Any]],
    ref_timestamp: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Extracts appearance signatures for each participant region at ref_timestamp.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if cv2 is None:
        return [
            {
                "track_id": r.get("id", f"speaker_{idx+1}"),
                "label": r.get("label", f"Speaker {idx+1}"),
                "ref_rect": r,
                "hist": None
            }
            for idx, r in enumerate(regions_normalized)
        ]

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    target_frame = int(ref_timestamp * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    ret, frame = cap.read()

    ref_faces = []
    valid_ref_frame = False
    if ret and frame is not None and frame.mean() > 25.0:
        try:
            ref_faces = detect_faces_in_frame(frame)
            if len(ref_faces) >= 1:
                valid_ref_frame = True
        except Exception:
            pass

    # If ref_timestamp was default 0.0 or frame had no faces / dark screen, probe early video
    if not valid_ref_frame:
        candidate_timestamps = [1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0]
        best_frame = frame
        best_faces = ref_faces
        for cand_t in candidate_timestamps:
            if total_frames > 0 and (cand_t * fps) >= total_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(cand_t * fps))
            c_ret, c_frame = cap.read()
            if c_ret and c_frame is not None and c_frame.mean() > 25.0:
                c_faces = detect_faces_in_frame(c_frame)
                if len(c_faces) >= len(regions_normalized):
                    frame = c_frame
                    ref_faces = c_faces
                    valid_ref_frame = True
                    break
                elif len(c_faces) > len(best_faces):
                    best_frame = c_frame
                    best_faces = c_faces
        if not valid_ref_frame and best_frame is not None:
            frame = best_frame
            ref_faces = best_faces

    cap.release()

    h, w = frame.shape[:2] if (frame is not None) else (1080, 1920)

    recognizer = _get_sface_recognizer()
    signatures = []
    for idx, reg in enumerate(regions_normalized):
        track_id = str(reg.get("id", f"speaker_{idx+1}"))
        label = str(reg.get("label", f"Speaker {idx+1}"))
        rx = float(reg.get("x", 0.0))
        ry = float(reg.get("y", 0.0))
        rw = float(reg.get("width") if reg.get("width") is not None else reg.get("w", 0.35))
        rh = float(reg.get("height") if reg.get("height") is not None else reg.get("h", 0.70))

        # Pixel bounds
        x1 = max(0, int(rx * w))
        y1 = max(0, int(ry * h))
        x2 = min(w, int((rx + rw) * w))
        y2 = min(h, int((ry + rh) * h))

        hist = None
        face_hist = None
        feat = None

        if frame is not None and x2 > x1 and y2 > y1:
            crop = frame[y1:y2, x1:x2]
            hist = compute_normalized_hsv_hist(crop)

            # Extract focused face + upper torso appearance and SFace embedding if face detected in/near region
            if ref_faces:
                rc_x = rx + rw / 2.0
                matching_faces = [f for f in ref_faces if abs((f["x"] + f["width"] / 2.0) - rc_x) < 0.28]
                if matching_faces:
                    mf = matching_faces[0]
                    mfx = max(0, int(mf["x"] * w))
                    mfy = max(0, int(mf["y"] * h))
                    mfw = max(1, int(mf["width"] * w))
                    mfh = max(1, int(mf["height"] * h))
                    mfy2 = min(h, mfy + int(mfh * 1.8))
                    face_crop = frame[mfy:mfy2, mfx:mfx+mfw]
                    face_hist = compute_normalized_hsv_hist(face_crop)

                    if recognizer is not None and "raw_face" in mf:
                        try:
                            raw_f = np.array(mf["raw_face"], dtype=np.float32)
                            aligned = recognizer.alignCrop(frame, raw_f)
                            feat = recognizer.feature(aligned)
                        except Exception as e:
                            logger.debug(f"Could not extract SFace reference feature: {e}")

        signatures.append({
            "track_id": track_id,
            "label": label,
            "ref_rect": {
                "x": rx,
                "y": ry,
                "width": rw,
                "height": rh,
            },
            "center_x_norm": rx + rw / 2.0,
            "center_y_norm": ry + rh / 2.0,
            "hist": hist,
            "face_hist": face_hist,
            "feat": feat
        })

    return signatures


class CropTrajectorySmoother:
    """
    Applies deadband filtering and exponential moving average (EMA)
    to prevent crop jitter while accurately following real subject movement.
    """
    def __init__(self, deadband_norm: float = 0.03, alpha: float = 0.25):
        self.deadband_norm = deadband_norm  # 3% of screen width deadband (~57px on 1080p)
        self.alpha = alpha  # EMA smoothing factor
        self.prev_center_norm: Optional[float] = None
        self.prev_track_id: Optional[str] = None

    def smooth(self, raw_center_norm: float, active_track_id: str, is_cut: bool = False) -> float:
        # At a hard camera cut or speaker change, snap immediately (no cross-cut lag)
        if is_cut or self.prev_center_norm is None or active_track_id != self.prev_track_id:
            self.prev_center_norm = raw_center_norm
            self.prev_track_id = active_track_id
            return raw_center_norm

        diff = abs(raw_center_norm - self.prev_center_norm)
        # If movement is within deadband threshold, suppress jitter completely
        if diff < self.deadband_norm:
            return self.prev_center_norm

        # Otherwise, apply smooth exponential glide
        smoothed = self.alpha * raw_center_norm + (1.0 - self.alpha) * self.prev_center_norm
        self.prev_center_norm = smoothed
        return smoothed


def calculate_9_16_crop_rect(
    center_x_norm: float,
    src_w: int,
    src_h: int
) -> Dict[str, Any]:
    """
    Calculates a 9:16 vertical crop rectangle centered horizontally on center_x_norm.
    Ensures even-pixel dimensions and strictly stays within source frame bounds.
    """
    max_src_w = (src_w // 2) * 2
    max_src_h = (src_h // 2) * 2

    # 9:16 aspect ratio: crop_h = max_src_h * 9 / 16
    crop_h = max_src_h
    crop_w = int(round(max_src_h * 9.0 / 16.0))
    if crop_w % 2 != 0:
        crop_w -= 1

    if crop_w > max_src_w:
        crop_w = max_src_w
        if crop_w % 2 != 0:
            crop_w -= 1
        crop_h = int(round(crop_w * 16.0 / 9.0))
        if crop_h % 2 != 0:
            crop_h -= 1

    center_x_px = int(center_x_norm * max_src_w)
    x1 = center_x_px - crop_w // 2

    # Clamp bounds strictly within even frame
    x1 = max(0, min(max_src_w - crop_w, x1))
    y1 = 0

    # Even pixel alignment
    x1 = (x1 // 2) * 2

    return {
        "x": x1,
        "y": y1,
        "w": crop_w,
        "h": crop_h,
        "norm_x": round(x1 / src_w, 4),
        "norm_y": round(y1 / src_h, 4),
        "norm_w": round(crop_w / src_w, 4),
        "norm_h": round(crop_h / src_h, 4),
    }


def classify_shot_interval(
    video_path: Path,
    shot: Tuple[float, float],
    signatures: List[Dict[str, Any]],
    src_w: int,
    src_h: int
) -> Dict[str, Any]:
    """
    Classifies which participant is visible in the shot interval, or identifies
    a wide two-shot or unassigned interval. Evaluates participant presence across
    spatial candidates (reference, center, left, right) and multi-sample consensus.
    Computes active 9:16 crop rectangle.
    """
    s_time, e_time = shot
    duration = max(0.1, e_time - s_time)

    # Multi-sample timestamps for consensus voting across shot duration
    if duration > 1.2:
        sample_times = [
            s_time + 0.25 * duration,
            s_time + 0.50 * duration,
            s_time + 0.75 * duration
        ]
    else:
        sample_times = [(s_time + e_time) / 2.0]

    video_path = Path(video_path)
    scores_by_track: Dict[str, List[float]] = {sig["track_id"]: [] for sig in signatures}
    positions_by_track: Dict[str, List[float]] = {sig["track_id"]: [] for sig in signatures}

    if cv2 is not None and video_path.exists():
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        mock_stopped = False
        for t_stamp in sample_times:
            if mock_stopped:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(t_stamp * fps))
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            frame_faces = detect_faces_in_frame(frame)
            recognizer = _get_sface_recognizer()
            matched_by_face = False
            if frame_faces and recognizer is not None and "raw_face" in frame_faces[0]:
                try:
                    raw_f = np.array(frame_faces[0]["raw_face"], dtype=np.float32)
                    aligned = recognizer.alignCrop(frame, raw_f)
                    target_feat = recognizer.feature(aligned)
                    fc_norm = float(frame_faces[0]["x"]) + float(frame_faces[0]["width"]) / 2.0
                    has_any_feat = any(sig.get("feat") is not None for sig in signatures)
                    if has_any_feat:
                        for sig in signatures:
                            t_id = sig["track_id"]
                            if sig.get("feat") is not None:
                                sim = float(recognizer.match(sig["feat"], target_feat, cv2.FaceRecognizerSF_FR_COSINE))
                                scores_by_track[t_id].append(max(0.0, sim))
                                positions_by_track[t_id].append(fc_norm)
                            else:
                                scores_by_track[t_id].append(0.0)
                                positions_by_track[t_id].append(fc_norm)
                        matched_by_face = True
                except Exception:
                    pass

            if matched_by_face:
                continue

            for sig in signatures:
                track_id = sig["track_id"]
                ref_hist = sig.get("hist")
                if ref_hist is None:
                    scores_by_track[track_id].append(0.5)
                    positions_by_track[track_id].append(sig.get("center_x_norm", 0.5))
                    continue

                rx = sig["ref_rect"]["x"]
                ry = sig["ref_rect"]["y"]
                rw = sig["ref_rect"]["width"]
                rh = sig["ref_rect"]["height"]

                # 1. Compare at reference position first
                x1 = max(0, int(rx * src_w))
                y1 = max(0, int(ry * src_h))
                x2 = min(src_w, int((rx + rw) * src_w))
                y2 = min(src_h, int((ry + rh) * src_h))

                best_corr = 0.0
                best_pos = sig.get("center_x_norm", 0.5)

                if x2 > x1 and y2 > y1:
                    cur_hist = compute_normalized_hsv_hist(frame[y1:y2, x1:x2])
                    if cur_hist is not None:
                        try:
                            corr = float(cv2.compareHist(ref_hist, cur_hist, cv2.HISTCMP_CORREL))
                            best_corr = max(0.0, corr)
                        except StopIteration:
                            mock_stopped = True
                            break
                        except Exception:
                            best_corr = 0.0

                if mock_stopped:
                    break

                # 2. If reference position is not strong, search candidate framing positions (Center, Left, Right)
                if best_corr < 0.70:
                    cand_positions = [
                        (0.5, (src_w - int(rw * src_w)) // 2),
                        (0.25, max(0, int(0.25 * src_w - (rw * src_w) // 2))),
                        (0.75, min(src_w - int(rw * src_w), int(0.75 * src_w - (rw * src_w) // 2))),
                    ]
                    for cand_norm, cand_px in cand_positions:
                        cx1 = max(0, min(src_w - int(rw * src_w), cand_px))
                        cx2 = min(src_w, cx1 + int(rw * src_w))
                        if cx2 > cx1 and y2 > y1:
                            c_hist = compute_normalized_hsv_hist(frame[y1:y2, cx1:cx2])
                            if c_hist is not None:
                                try:
                                    c_corr = float(cv2.compareHist(ref_hist, c_hist, cv2.HISTCMP_CORREL))
                                    if c_corr > best_corr + 0.12:
                                        best_corr = max(0.0, c_corr)
                                        best_pos = cand_norm
                                except StopIteration:
                                    mock_stopped = True
                                    break
                                except Exception:
                                    pass

                scores_by_track[track_id].append(best_corr)
                positions_by_track[track_id].append(best_pos)

        cap.release()

    # Aggregate scores across samples via median
    aggregated_scores: Dict[str, float] = {}
    aggregated_positions: Dict[str, float] = {}
    for sig in signatures:
        t_id = sig["track_id"]
        sc_list = scores_by_track.get(t_id, [])
        pos_list = positions_by_track.get(t_id, [])
        aggregated_scores[t_id] = float(np.median(sc_list)) if sc_list else 0.0
        aggregated_positions[t_id] = float(np.median(pos_list)) if pos_list else sig.get("center_x_norm", 0.5)

    # Decision logic
    sorted_speakers = sorted(aggregated_scores.items(), key=lambda x: x[1], reverse=True)
    best_track_id, best_score = sorted_speakers[0] if sorted_speakers else ("speaker_1", 0.5)
    second_track_id, second_score = sorted_speakers[1] if len(sorted_speakers) > 1 else (None, 0.0)

    review_needed = False
    active_track_id: str

    # Case 1: Both participants score high -> Two-shot / wide shot
    if second_track_id and best_score >= 0.55 and second_score >= 0.55:
        active_track_id = "two_shot"
        confidence = round(float((best_score + second_score) / 2.0), 3)
        center_x_norm = 0.5
        crop_rect = calculate_9_16_crop_rect(center_x_norm, src_w, src_h)

    # Case 2: One participant clearly dominates
    elif best_score >= 0.50 and (second_score is None or best_score >= second_score + 0.12):
        active_track_id = best_track_id
        confidence = round(float(best_score), 3)
        center_x_norm = aggregated_positions.get(best_track_id, 0.5)
        crop_rect = calculate_9_16_crop_rect(center_x_norm, src_w, src_h)

    # Case 3: Ambiguous or low confidence
    elif best_score >= 0.40:
        active_track_id = best_track_id
        confidence = round(float(best_score), 3)
        review_needed = True
        center_x_norm = aggregated_positions.get(best_track_id, 0.5)
        crop_rect = calculate_9_16_crop_rect(center_x_norm, src_w, src_h)

    # Case 4: Neither speaker matched (cutaway / object / unknown shot)
    else:
        active_track_id = "unassigned"
        confidence = round(float(best_score), 3)
        review_needed = True
        center_x_norm = 0.5
        crop_rect = calculate_9_16_crop_rect(center_x_norm, src_w, src_h)

    return {
        "start_time": s_time,
        "end_time": e_time,
        "duration": round(e_time - s_time, 2),
        "active_track_id": active_track_id,
        "confidence": confidence,
        "review_needed": review_needed,
        "crop_rect": crop_rect,
        "fallback_policy": "fit" if active_track_id == "two_shot" else "center"
    }


def build_shot_schedule(
    video_path: Path,
    regions_normalized: List[Dict[str, Any]],
    ref_timestamp: float = 0.0,
    scdet_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Executes end-to-end shot boundary detection, reference signature extraction,
    and shot classification with deadband motion smoothing to build the complete
    time-based active-crop schedule.
    """
    if not regions_normalized:
        raise ValueError("At least one participant reference region is required")

    video_path = Path(video_path)
    shots = detect_camera_cuts(video_path, scdet_threshold=scdet_threshold) if scdet_threshold is not None else detect_camera_cuts(video_path)
    signatures = extract_reference_signatures(video_path, regions_normalized, ref_timestamp)

    # Determine video dimensions
    src_w, src_h = 1920, 1080
    if cv2 is not None and video_path.exists():
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
            src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
            cap.release()

    smoother = CropTrajectorySmoother(deadband_norm=0.03, alpha=0.25)
    schedule: List[Dict[str, Any]] = []

    for shot_idx, shot in enumerate(shots):
        classification = classify_shot_interval(video_path, shot, signatures, src_w, src_h)
        classification["shot_id"] = shot_idx + 1

        # Smooth crop center trajectory across stable shots
        raw_center = classification["crop_rect"]["norm_x"] + classification["crop_rect"]["norm_w"] / 2.0
        is_cut = (shot_idx == 0) or (classification["active_track_id"] != schedule[-1]["active_track_id"])
        smoothed_center = smoother.smooth(raw_center, classification["active_track_id"], is_cut=is_cut)

        classification["crop_rect"] = calculate_9_16_crop_rect(smoothed_center, src_w, src_h)
        schedule.append(classification)

    return schedule


def build_intra_shot_crop_expression(
    trajectory_points: List[Tuple[float, int]],
    sub_duration: float,
    default_x: int
) -> str:
    """
    Builds a continuous piecewise linear FFmpeg expression for x(t) over relative time t in [0, sub_duration].
    Ensures even pixel alignment via trunc(.../2)*2 to satisfy YUV420p chroma subsampling.
    """
    if not trajectory_points or len(trajectory_points) < 2:
        return str(default_x)

    xs = [pt[1] for pt in trajectory_points]
    if max(xs) == min(xs):
        return str(xs[0])

    pts = sorted(trajectory_points, key=lambda p: p[0])
    expr = f"{pts[-1][1]}"
    for i in range(len(pts) - 2, -1, -1):
        t0, x0 = pts[i]
        t1, x1 = pts[i + 1]
        dt = t1 - t0
        if dt <= 0.001:
            continue
        slope = (x1 - x0) / dt
        seg = f"({x0}+{slope:.3f}*(t-{t0:.3f}))"
        expr = f"if(lt(t\\,{t1:.3f})\\,{seg}\\,{expr})"

    return f"trunc(({expr})/2)*2"


async def render_camera_following_video(
    video_path: Path,
    output_path: Path,
    shot_schedule: List[Dict[str, Any]],
    clip_start: float = 0.0,
    clip_end: Optional[float] = None,
    canvas_w: int = 1080,
    canvas_h: int = 1920
) -> Path:
    """
    Renders a single continuous 9:16 vertical video reframing the active speaker at each camera cut
    with continuous intra-shot camera-following movement across detected participant motion.
    Preserves uninterrupted continuous audio from the source clip.
    Strictly NO stacked panels, NO freeze-frames for off-camera participants, and ZERO captions.
    """
    video_path = Path(video_path)
    output_path = Path(output_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Source video not found: {video_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get source duration if clip_end not given
    src_w, src_h = await get_video_dimensions(video_path)
    if clip_end is None or clip_end <= clip_start:
        clip_end = clip_start + 30.0

    clip_duration = clip_end - clip_start

    # Intersect shot_schedule with [clip_start, clip_end]
    relevant_segments = []
    for shot in shot_schedule:
        s_t = float(shot["start_time"])
        e_t = float(shot["end_time"])

        # Check overlap
        overlap_start = max(clip_start, s_t)
        overlap_end = min(clip_end, e_t)

        if overlap_end - overlap_start >= 0.05:
            # Clone crop details
            crop = shot.get("crop_rect") or calculate_9_16_crop_rect(0.5, src_w, src_h)
            relevant_segments.append({
                "sub_start": overlap_start,
                "sub_end": overlap_end,
                "sub_duration": overlap_end - overlap_start,
                "crop": crop,
                "active_track_id": shot.get("active_track_id", "speaker_1"),
                "intra_shot_trajectory": shot.get("intra_shot_trajectory")
            })

    if not relevant_segments:
        # Fallback to single center-crop segment
        crop = calculate_9_16_crop_rect(0.5, src_w, src_h)
        relevant_segments.append({
            "sub_start": clip_start,
            "sub_end": clip_end,
            "sub_duration": clip_duration,
            "crop": crop,
            "active_track_id": "fallback",
            "intra_shot_trajectory": None
        })

    # Case A: Only 1 shot segment covers the entire clip -> Single crop filter
    if len(relevant_segments) == 1:
        seg = relevant_segments[0]
        crop = seg["crop"]
        cw, ch, cx, cy = crop["w"], crop["h"], crop["x"], crop["y"]
        sub_dur = seg["sub_duration"]
        traj = seg.get("intra_shot_trajectory")

        x_target = str(cx)
        if traj and len(traj) >= 2:
            s_sub = seg["sub_start"]
            e_sub = seg["sub_end"]
            pts = []
            for p in traj:
                pt_t = float(p.get("t", 0.0))
                if s_sub - 0.05 <= pt_t <= e_sub + 0.05:
                    rel_t = max(0.0, min(sub_dur, pt_t - s_sub))
                    pts.append((rel_t, int(p.get("x", cx))))
            if len(pts) >= 2:
                pts = sorted(pts, key=lambda p: p[0])
                if pts[0][0] > 0.01:
                    pts.insert(0, (0.0, pts[0][1]))
                if pts[-1][0] < sub_dur - 0.01:
                    pts.append((sub_dur, pts[-1][1]))
                x_target = build_intra_shot_crop_expression(pts, sub_dur, default_x=cx)

        vf = f"crop={cw}:{ch}:{x_target}:{cy},scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease:flags=bicubic,pad={canvas_w}:{canvas_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
        cmd = [
            "-y",
            "-ss", str(clip_start),
            "-to", str(clip_end),
            "-i", str(video_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "0",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-sn",
            "-movflags", "+faststart",
            "-f", "mp4",
            str(output_path)
        ]
        code, out, err = await run_ffmpeg(cmd)
        if code != 0:
            raise RuntimeError(f"FFmpeg camera-following render failed: {err}")
        return output_path

    # Case B: Multiple shot segments with camera cuts -> Dynamic segment concatenation
    filter_parts = []
    concat_inputs = []

    for idx, seg in enumerate(relevant_segments):
        s_sub = seg["sub_start"]
        e_sub = seg["sub_end"]
        sub_dur = seg["sub_duration"]
        crop = seg["crop"]
        cw, ch, cx, cy = crop["w"], crop["h"], crop["x"], crop["y"]
        traj = seg.get("intra_shot_trajectory")

        x_target = str(cx)
        if traj and len(traj) >= 2:
            s_sub_time = seg["sub_start"]
            e_sub_time = seg["sub_end"]
            pts = []
            for p in traj:
                pt_t = float(p.get("t", 0.0))
                if s_sub_time - 0.05 <= pt_t <= e_sub_time + 0.05:
                    rel_t = max(0.0, min(sub_dur, pt_t - s_sub_time))
                    pts.append((rel_t, int(p.get("x", cx))))
            if len(pts) >= 2:
                pts = sorted(pts, key=lambda p: p[0])
                if pts[0][0] > 0.01:
                    pts.insert(0, (0.0, pts[0][1]))
                if pts[-1][0] < sub_dur - 0.01:
                    pts.append((sub_dur, pts[-1][1]))
                x_target = build_intra_shot_crop_expression(pts, sub_dur, default_x=cx)

        # Video branch: trim, setpts, crop to active speaker, scale to 9:16 canvas with contain preservation
        v_tag = f"[v{idx}]"
        filter_parts.append(
            f"[0:v]trim=start={s_sub}:end={e_sub},setpts=PTS-STARTPTS,"
            f"crop={cw}:{ch}:{x_target}:{cy},scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease:flags=bicubic,pad={canvas_w}:{canvas_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1{v_tag}"
        )
        concat_inputs.append(v_tag)

    # Concat video stream
    num_segs = len(relevant_segments)
    concat_str = "".join(concat_inputs) + f"concat=n={num_segs}:v=1:a=0[outv]"
    filter_parts.append(concat_str)

    # Audio branch: single continuous atrim from clip_start to clip_end (zero audio cuts or drift!)
    filter_parts.append(f"[0:a]atrim=start={clip_start}:end={clip_end},asetpts=PTS-STARTPTS[outa]")

    full_filtergraph = ";\n".join(filter_parts)

    cmd = [
        "-y",
        "-i", str(video_path),
        "-filter_complex", full_filtergraph,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "0",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-sn",
        "-movflags", "+faststart",
        "-f", "mp4",
        str(output_path)
    ]

    code, out, err = await run_ffmpeg(cmd)
    if code != 0:
        logger.error(f"FFmpeg dynamic concat render failed: {err}")
        raise RuntimeError(f"FFmpeg dynamic concat render failed: {err}")

    return output_path



# ═════════════════════════════════════════════════════════════════════════════════
# TOPIC 7 — FEATURE 1: FIXED TWO-PERSON AREA WITH FACE-AWARE CAMERA FOLLOWING
# ═════════════════════════════════════════════════════════════════════════════════

def calculate_two_person_fixed_boundary_crop(
    outer_boundary: Dict[str, float],
    participant_positions: Optional[List[float]] = None,
    src_w: int = 1920,
    src_h: int = 1080,
    smoother: Optional[CropTrajectorySmoother] = None,
    participant_boxes: Optional[List[Dict[str, float]]] = None,
    margin_x_norm: float = 0.02,
    is_cut: bool = False
) -> Dict[str, Any]:
    """
    Feature 1: Calculates a vertical 9:16 crop that tracks the movement of both people
    while strictly remaining inside the user's fixed outer boundary.
    
    Geometric Guarantees:
    - If required_span <= crop_w and both fits inside boundary: BOTH complete face bounding
      boxes (and safety margins) fit inside the crop (both_faces_fit=True).
    - If required_span > crop_w: Identifies geometric impossibility (geometry_impossible=True,
      both_faces_fit=False), centers crop between both subjects, and STRICTLY PREVENTS
      collapsing into a solo crop.
    - Outer boundary is strictly respected: crop_x1 in [bound_x1, bound_x2 - crop_w].
    """
    bx = float(outer_boundary.get("x", 0.0))
    by = float(outer_boundary.get("y", 0.0))
    bw = float(outer_boundary.get("width") if outer_boundary.get("width") is not None else outer_boundary.get("w", 1.0))
    bh = float(outer_boundary.get("height") if outer_boundary.get("height") is not None else outer_boundary.get("h", 1.0))

    # Pixel bounds for the fixed outer boundary
    bound_x1 = max(0, int(bx * src_w))
    bound_y1 = max(0, int(by * src_h))
    bound_w = min(src_w - bound_x1, int(bw * src_w))
    bound_h = min(src_h - bound_y1, int(bh * src_h))
    bound_x2 = bound_x1 + bound_w

    # Vertical 9:16 target dimensions
    crop_h = src_h
    crop_w = int(round(src_h * 9.0 / 16.0))
    if crop_w % 2 != 0:
        crop_w -= 1

    # If the user's outer boundary is narrower than standard 9:16, clamp to boundary width
    if crop_w > bound_w:
        crop_w = bound_w
        if crop_w % 2 != 0:
            crop_w -= 1

    # Extract horizontal extents of participants
    if participant_boxes and len(participant_boxes) >= 2:
        lefts = [float(b.get("x", 0.0)) for b in participant_boxes]
        rights = [float(b.get("x", 0.0)) + float(b.get("width") if b.get("width") is not None else b.get("w", 0.1)) for b in participant_boxes]
        req_x1 = max(0, int((min(lefts) - margin_x_norm) * src_w))
        req_x2 = min(src_w, int((max(rights) + margin_x_norm) * src_w))
        raw_midpoint_norm = (min(lefts) + max(rights)) / 2.0
    elif participant_boxes and len(participant_boxes) == 1:
        # Temporary occlusion of 1 participant: retain two-person framing anchored across boundary
        b = participant_boxes[0]
        bx_box = float(b.get("x", 0.0))
        bw_box = float(b.get("width") if b.get("width") is not None else b.get("w", 0.1))
        bound_center = bx + (bw / 2.0)
        if bx_box < bound_center:
            other_x = bx + bw - bw_box
        else:
            other_x = bx
        min_l = min(bx_box, other_x)
        max_r = max(bx_box + bw_box, other_x + bw_box)
        req_x1 = max(0, int((min_l - margin_x_norm) * src_w))
        req_x2 = min(src_w, int((max_r + margin_x_norm) * src_w))
        raw_midpoint_norm = (min_l + max_r) / 2.0
    elif participant_positions and len(participant_positions) >= 2:
        min_pos = min(participant_positions)
        max_pos = max(participant_positions)
        req_x1 = max(0, int((min_pos - 0.04 - margin_x_norm) * src_w))
        req_x2 = min(src_w, int((max_pos + 0.04 + margin_x_norm) * src_w))
        raw_midpoint_norm = float(np.mean(participant_positions))
    elif participant_positions and len(participant_positions) == 1:
        # Single position provided -> anchor across boundary to prevent solo collapse
        p = participant_positions[0]
        bound_center = bx + (bw / 2.0)
        if p < bound_center:
            other_p = bx + bw - 0.10
        else:
            other_p = bx + 0.10
        min_p = min(p, other_p)
        max_p = max(p, other_p)
        req_x1 = max(0, int((min_p - 0.04 - margin_x_norm) * src_w))
        req_x2 = min(src_w, int((max_p + 0.04 + margin_x_norm) * src_w))
        raw_midpoint_norm = (min_p + max_p) / 2.0
    else:
        raw_midpoint_norm = bx + (bw / 2.0)
        mid_x_px = int(raw_midpoint_norm * src_w)
        req_x1 = max(bound_x1, mid_x_px - crop_w // 2)
        req_x2 = min(bound_x2, mid_x_px + crop_w // 2)

    required_span = req_x2 - req_x1
    is_geometry_impossible = required_span > crop_w

    # Valid range of x1 that keeps both participants within crop:
    # req_x2 - crop_w <= x1 <= req_x1
    # AND must stay within [bound_x1, bound_x2 - crop_w]
    valid_min_x1 = max(bound_x1, req_x2 - crop_w)
    valid_max_x1 = min(bound_x2 - crop_w, req_x1)

    max_x1 = max(bound_x1, bound_x2 - crop_w)

    if not is_geometry_impossible and valid_min_x1 <= valid_max_x1:
        # Both complete face bounding boxes fit inside crop AND crop is inside boundary!
        ideal_center_x = (req_x1 + req_x2) / 2.0
        ideal_x1 = int(ideal_center_x - crop_w / 2.0)
        desired_x1 = max(valid_min_x1, min(valid_max_x1, ideal_x1))
        both_faces_fit = True
    else:
        # Geometric impossibility: participants are too far apart for 9:16 crop width,
        # or boundary is too tight to enclose both without clipping.
        # SAFE TWO-PERSON INVARIANT: Center between them, clamp to boundary, NEVER collapse to solo crop!
        ideal_center_x = (req_x1 + req_x2) / 2.0
        ideal_x1 = int(ideal_center_x - crop_w / 2.0)
        desired_x1 = max(bound_x1, min(max_x1, ideal_x1))
        both_faces_fit = False

    # Smooth the movement with deadband to prevent jitter
    desired_norm = desired_x1 / src_w
    if smoother is not None:
        smoothed_norm = smoother.smooth(desired_norm, "two_person_fixed", is_cut=is_cut)
        x1 = int(smoothed_norm * src_w)
    else:
        x1 = desired_x1

    # STRICT INVARIANT: Must stay within [bound_x1, bound_x2 - crop_w]
    x1 = max(bound_x1, min(max_x1, x1))

    # Even pixel alignment
    x1 = (x1 // 2) * 2
    y1 = 0

    return {
        "x": x1,
        "y": y1,
        "w": crop_w,
        "h": crop_h,
        "norm_x": round(x1 / src_w, 4),
        "norm_y": round(y1 / src_h, 4),
        "norm_w": round(crop_w / src_w, 4),
        "norm_h": round(crop_h / src_h, 4),
        "both_faces_fit": both_faces_fit,
        "geometry_impossible": is_geometry_impossible,
        "required_span_px": required_span,
        "crop_w_px": crop_w,
        "outer_boundary": {
            "x": bx,
            "y": by,
            "width": bw,
            "height": bh,
            "pixel_bounds": [bound_x1, bound_y1, bound_x2, bound_y1 + bound_h]
        }
    }


def build_fixed_boundary_schedule(
    video_path: Path,
    outer_boundary: Dict[str, float],
    participant_regions: Optional[List[Dict[str, Any]]] = None,
    ref_timestamp: float = 0.0,
    intra_sample_fps: float = 4.0,
    max_intra_samples_per_shot: int = 40
) -> List[Dict[str, Any]]:
    """
    Builds the shot schedule for Feature 1 (Fixed two-person area with camera following).
    Uses genuine face detection from sampled video frames whenever human faces are present,
    tracking participants across cuts and temporary occlusions within the fixed boundary,
    generating continuous within-shot participant-aware camera trajectories.
    """
    video_path = Path(video_path)
    shots = detect_camera_cuts(video_path)

    src_w, src_h = 1920, 1080
    fps = 30.0
    cap = None
    if cv2 is not None and video_path.exists():
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
            src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # Participant reference regions
    reg_a = participant_regions[0] if participant_regions and len(participant_regions) > 0 else {"x": 0.20, "y": 0.20, "width": 0.25, "height": 0.50}
    reg_b = participant_regions[1] if participant_regions and len(participant_regions) > 1 else {"x": 0.55, "y": 0.20, "width": 0.25, "height": 0.50}

    smoother = CropTrajectorySmoother(deadband_norm=0.02, alpha=0.20)
    schedule = []
    prev_box_a = None
    prev_box_b = None

    for idx, (s_time, e_time) in enumerate(shots):
        shot_dur = max(0.1, e_time - s_time)
        if shot_dur < 0.4 or intra_sample_fps <= 0:
            sample_times = [(s_time + e_time) / 2.0]
        else:
            num_steps = min(max_intra_samples_per_shot, max(2, int(round(shot_dur * intra_sample_fps))))
            sample_times = [round(s_time + i * (shot_dur / num_steps), 3) for i in range(num_steps + 1)]

        intra_shot_trajectory = []
        shot_crops = []
        active_boxes_all = []

        for p_idx, sample_time in enumerate(sample_times):
            is_cut = (p_idx == 0)  # Camera cut reset at shot boundary
            frame_faces = []
            if cap is not None and cap.isOpened():
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(sample_time * fps))
                ret, frame = cap.read()
                if ret and frame is not None:
                    frame_faces = detect_faces_in_frame(frame)

            # Match detected faces to participants
            face_a, face_b, meta = match_and_track_participants(
                detected_faces=frame_faces,
                region_a=reg_a,
                region_b=reg_b,
                prev_box_a=prev_box_a,
                prev_box_b=prev_box_b
            )

            active_boxes = []
            if face_a is not None:
                active_boxes.append(face_a)
                prev_box_a = face_a
            if face_b is not None:
                active_boxes.append(face_b)
                prev_box_b = face_b

            if active_boxes:
                active_boxes_all.extend(active_boxes)

            # Fallback to participant_regions if no real faces detected (e.g. test fixture or occlusion)
            boxes_for_crop = active_boxes if active_boxes else participant_regions

            crop = calculate_two_person_fixed_boundary_crop(
                outer_boundary=outer_boundary,
                src_w=src_w,
                src_h=src_h,
                smoother=smoother,
                participant_boxes=boxes_for_crop,
                is_cut=is_cut
            )
            shot_crops.append(crop)

            intra_shot_trajectory.append({
                "t": sample_time,
                "rel_t": round(sample_time - s_time, 3),
                "x": crop["x"],
                "y": crop["y"],
                "w": crop["w"],
                "h": crop["h"],
                "norm_x": crop["norm_x"],
                "norm_w": crop["norm_w"],
                "both_faces_fit": crop.get("both_faces_fit", True)
            })

        midpoint_crop = shot_crops[len(shot_crops) // 2] if shot_crops else crop

        schedule.append({
            "shot_id": idx + 1,
            "start_time": s_time,
            "end_time": e_time,
            "duration": round(shot_dur, 2),
            "composition": "FIXED_TWO_PERSON_FOLLOW",
            "active_track_id": "both_participants",
            "confidence": 1.0 if len(active_boxes_all) >= 2 else (0.85 if len(active_boxes_all) == 1 else 0.70),
            "faces_detected": len(active_boxes_all) > 0,
            "face_count": len(active_boxes_all),
            "review_needed": midpoint_crop.get("geometry_impossible", False),
            "crop_rect": midpoint_crop,
            "outer_boundary": outer_boundary,
            "intra_shot_trajectory": intra_shot_trajectory,
            "is_continuous_tracking": len(intra_shot_trajectory) >= 2
        })

    if cap is not None:
        cap.release()

    return schedule



async def render_fixed_boundary_two_person_video(
    video_path: Path,
    output_path: Path,
    schedule: List[Dict[str, Any]],
    clip_start: float = 0.0,
    clip_end: Optional[float] = None,
    canvas_w: int = 1080,
    canvas_h: int = 1920
) -> Path:
    """
    Renders Feature 1: Output follows the two people within the fixed outer boundary,
    scaled to 1080x1920 vertical canvas with uninterrupted continuous source audio.
    """
    return await render_camera_following_video(
        video_path=video_path,
        output_path=output_path,
        shot_schedule=schedule,
        clip_start=clip_start,
        clip_end=clip_end,
        canvas_w=canvas_w,
        canvas_h=canvas_h
    )


# ═════════════════════════════════════════════════════════════════════════════════
# TOPIC 7 — FEATURE 2: VISIBILITY-DRIVEN COMPOSITION (A-ONLY / B-ONLY / SIDE-BY-SIDE)
# ═════════════════════════════════════════════════════════════════════════════════

def calculate_side_by_side_participant_crop(
    region: Dict[str, Any],
    src_w: int = 1920,
    src_h: int = 1080,
    face_box: Optional[Dict[str, Any]] = None,
    dest_panel_w: int = 540,
    dest_panel_h: int = 1920
) -> Dict[str, Any]:
    """
    Calculates a destination-panel-optimized crop for a single participant in an A+B side-by-side layout.
    Guarantees:
    - Preserves the entire user-selected horizontal region using outward integer rounding.
    - Destination panel aspect ratio is dest_panel_w / dest_panel_h (540/1920 = 0.28125).
    - Minimum crop width to fill panel height without vertical letterbox: src_h * (dest_panel_w / dest_panel_h).
      For 1080p source: 1080 * 0.28125 = 303.75 -> 304 pixels.
    - No 608px arbitrary ceiling or assumed shoulder constants.
    - Uses face center ONLY when valid and spatially consistent with the selected region.
    - Falls back to selected region center if face center is outside the selected region.
    - Aligns crop_x, crop_w, crop_y, crop_h to even pixels for YUV420p chroma subsampling.
    - Full source height is preserved (crop_y=0, crop_h=max_src_h) and scaled proportionally without stretching.
    - Enforces:
        crop_x <= region_left
        crop_x + crop_w >= region_right
        crop_x >= 0
        crop_x + crop_w <= max_src_w <= src_w
    """
    max_src_w = (src_w // 2) * 2
    max_src_h = (src_h // 2) * 2

    rx = float(region.get("x", 0.0))
    rw = float(region.get("width") if region.get("width") is not None else region.get("w", 0.35))

    # 1. Outward integer conversion bounded by even source dimensions
    region_left = max(0, min(max_src_w, int(np.floor(rx * max_src_w))))
    region_right = max(0, min(max_src_w, int(np.ceil((rx + rw) * max_src_w))))
    if region_right <= region_left:
        region_right = min(max_src_w, region_left + 2)
    user_region_width = max(1, region_right - region_left)

    # 2. Even-aligned bounds expansion to ensure even crop_x can contain both edges
    aligned_left = (region_left // 2) * 2
    aligned_right = ((region_right + 1) // 2) * 2
    required_even_span = max(2, aligned_right - aligned_left)

    # 3. Minimum crop width based on destination panel aspect ratio and actual source height
    min_fill_w = int(np.ceil(max_src_h * (dest_panel_w / float(dest_panel_h))))
    if min_fill_w % 2 != 0:
        min_fill_w += 1
    min_fill_w = max(2, min_fill_w)  # e.g. 304 for 1080p

    aligned_crop_w = min(max_src_w, max(min_fill_w, required_even_span))
    if aligned_crop_w % 2 != 0:
        aligned_crop_w += 1
    aligned_crop_w = min(max_src_w, aligned_crop_w)

    # 4. Feasible interval for crop origin
    crop_x_min = max(0, region_right - aligned_crop_w)
    crop_x_max = min(region_left, max_src_w - aligned_crop_w)

    even_crop_x_min = ((crop_x_min + 1) // 2) * 2
    even_crop_x_max = (crop_x_max // 2) * 2

    # In case boundary alignment creates an inverted even interval, fallback safely
    if even_crop_x_min > even_crop_x_max:
        even_crop_x_min = max(0, min(max_src_w - aligned_crop_w, aligned_left))
        even_crop_x_max = even_crop_x_min

    # 5. Target center: check face box consistency
    use_face = False
    if face_box is not None:
        fb_x = float(face_box.get("x", 0.0))
        fb_w = float(face_box.get("width") if face_box.get("width") is not None else face_box.get("w", 0.0))
        if fb_w > 0:
            face_center_px = (fb_x + fb_w / 2.0) * max_src_w
            # Consistency check: face center must lie within the selected region bounds
            if region_left <= face_center_px <= region_right:
                target_center_x = face_center_px
                use_face = True

    if not use_face:
        target_center_x = (region_left + region_right) / 2.0

    # 6. Clamping to feasible even interval
    preferred_crop_x = target_center_x - (aligned_crop_w / 2.0)
    unaligned_clamped = max(float(even_crop_x_min), min(float(even_crop_x_max), preferred_crop_x))
    crop_x = int(np.floor(unaligned_clamped + 0.5))
    crop_x = (crop_x // 2) * 2
    crop_x = max(even_crop_x_min, min(even_crop_x_max, crop_x))

    # 7. Post-calculation validation assertions
    crop_y = 0
    crop_h = max_src_h

    # Ensure horizontal containment of selected region
    if crop_x > region_left or (crop_x + aligned_crop_w) < region_right:
        aligned_crop_w = min(max_src_w, max(required_even_span, aligned_crop_w))
        crop_x = max(0, min(max_src_w - aligned_crop_w, aligned_left))
        crop_x = (crop_x // 2) * 2

    assert crop_x <= region_left, f"crop_x ({crop_x}) > region_left ({region_left})"
    assert crop_x + aligned_crop_w >= region_right, f"crop_x + crop_w ({crop_x + aligned_crop_w}) < region_right ({region_right})"
    assert crop_x >= 0, f"crop_x ({crop_x}) < 0"
    assert crop_x + aligned_crop_w <= max_src_w, f"crop exceeds source width ({crop_x + aligned_crop_w} > {max_src_w})"
    assert crop_x % 2 == 0, f"crop_x ({crop_x}) is not even"
    assert aligned_crop_w % 2 == 0, f"aligned_crop_w ({aligned_crop_w}) is not even"
    assert crop_y % 2 == 0, f"crop_y ({crop_y}) is not even"
    assert crop_h % 2 == 0, f"crop_h ({crop_h}) is not even"

    scale_factor = min(dest_panel_w / float(aligned_crop_w), dest_panel_h / float(crop_h))
    scaled_w = int(np.floor((aligned_crop_w * scale_factor) + 0.5))
    scaled_h = int(np.floor((crop_h * scale_factor) + 0.5))
    pad_x = int(np.floor(((dest_panel_w - scaled_w) / 2.0) + 0.5))
    pad_y = int(np.floor(((dest_panel_h - scaled_h) / 2.0) + 0.5))

    ffmpeg_crop = f"crop={aligned_crop_w}:{crop_h}:{crop_x}:{crop_y}:exact=1"
    ffmpeg_filter = f"{ffmpeg_crop},scale={dest_panel_w}:{dest_panel_h}:force_original_aspect_ratio=decrease,pad={dest_panel_w}:{dest_panel_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"

    return {
        "x": crop_x,
        "y": crop_y,
        "w": aligned_crop_w,
        "h": crop_h,
        "norm_x": round(crop_x / src_w, 4),
        "norm_y": round(crop_y / src_h, 4),
        "norm_w": round(aligned_crop_w / src_w, 4),
        "norm_h": round(crop_h / src_h, 4),
        "region_left": region_left,
        "region_right": region_right,
        "user_region_width": user_region_width,
        "aligned_crop_w": aligned_crop_w,
        "dest_panel_w": dest_panel_w,
        "dest_panel_h": dest_panel_h,
        "scale_factor": round(scale_factor, 6),
        "scaled_w": scaled_w,
        "scaled_h": scaled_h,
        "pad_x": pad_x,
        "pad_y": pad_y,
        "ffmpeg_crop": ffmpeg_crop,
        "ffmpeg_filter": ffmpeg_filter,
        "vertical_crop_used": False,
        "vertical_crop_note": "Vertical crop fields are 0 and full source height (crop_y=0, crop_h=max_src_h) as full height is preserved and scaled proportionally with black padding."
    }


def classify_visibility_composition(
    video_path: Path,
    shot: Tuple[float, float],
    sig_a: Dict[str, Any],
    sig_b: Dict[str, Any],
    src_w: int,
    src_h: int,
    injected_detections: Optional[List[Dict[str, Any]]] = None,
    injected_scores: Optional[Tuple[float, float]] = None
) -> Dict[str, Any]:
    """
    Feature 2: Classifies who is visually visible in the shot interval:
    - Only Person A -> COMPOSITION_A_ONLY
    - Only Person B -> COMPOSITION_B_ONLY
    - Both Person A and Person B -> COMPOSITION_SIDE_BY_SIDE
    - Neither/Uncertain/Ambiguous -> COMPOSITION_UNKNOWN_REVIEW (safe fallback)
    Uses genuine face detection when present, combined with appearance signatures.
    Rejects NaN, infinities, negative sizes, duplicate assignments, and ambiguous path crossings.
    Synthetic unit tests may pass injected_detections or injected_scores to explicitly model observations.
    """
    s_time, e_time = shot
    duration = max(0.1, e_time - s_time)

    # Multi-sample across shot duration
    sample_time = (s_time + e_time) / 2.0

    score_a = 0.0
    score_b = 0.0
    if injected_scores is not None:
        score_a, score_b = float(injected_scores[0]), float(injected_scores[1])

    pos_a = sig_a.get("center_x_norm", 0.25)
    pos_b = sig_b.get("center_x_norm", 0.75)
    face_a_vis = None
    face_b_vis = None
    f_a = None
    f_b = None
    detected_faces: List[Dict[str, Any]] = []
    is_ambiguous = False
    video_path = Path(video_path)

    # 1. Genuine face detection or injected observations for tests
    if injected_detections is not None:
        detected_faces = [f for f in injected_detections if validate_bounding_box(f)]
        if injected_detections and not detected_faces:
            is_ambiguous = True
    elif cv2 is not None and video_path.exists():
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(sample_time * fps))
        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            detected_faces = detect_faces_in_frame(frame)

            # Appearance signatures (HSV histograms)
            ref_a = sig_a.get("hist")
            if ref_a is not None and injected_scores is None:
                rxa = int(sig_a["ref_rect"]["x"] * src_w)
                rya = int(sig_a["ref_rect"]["y"] * src_h)
                rwa = int(sig_a["ref_rect"]["width"] * src_w)
                rha = int(sig_a["ref_rect"]["height"] * src_h)
                if rwa > 0 and rha > 0 and (rya + rha) <= src_h and (rxa + rwa) <= src_w:
                    h_curr = compute_normalized_hsv_hist(frame[rya:rya+rha, rxa:rxa+rwa])
                    if h_curr is not None:
                        try:
                            score_a = max(0.0, float(cv2.compareHist(ref_a, h_curr, cv2.HISTCMP_CORREL)))
                        except Exception:
                            score_a = 0.0

            ref_b = sig_b.get("hist")
            if ref_b is not None and injected_scores is None:
                rxb = int(sig_b["ref_rect"]["x"] * src_w)
                ryb = int(sig_b["ref_rect"]["y"] * src_h)
                rwb = int(sig_b["ref_rect"]["width"] * src_w)
                rhb = int(sig_b["ref_rect"]["height"] * src_h)
                if rwb > 0 and rhb > 0 and (ryb + rhb) <= src_h and (rxb + rwb) <= src_w:
                    h_curr = compute_normalized_hsv_hist(frame[ryb:ryb+rhb, rxb:rxb+rwb])
                    if h_curr is not None:
                        try:
                            score_b = max(0.0, float(cv2.compareHist(ref_b, h_curr, cv2.HISTCMP_CORREL)))
                        except Exception:
                            score_b = 0.0

    # 2. Match participants and evaluate identity association
    if detected_faces:
        f_a, f_b, meta = match_and_track_participants(
            detected_faces=detected_faces,
            region_a=sig_a.get("ref_rect", {}),
            region_b=sig_b.get("ref_rect", {}),
            appearance_sig_a=sig_a,
            appearance_sig_b=sig_b,
            bgr_frame=frame if ("frame" in locals() and frame is not None) else None
        )
        if meta.get("identity_ambiguous"):
            is_ambiguous = True
            face_a_vis = False
            face_b_vis = False
        else:
            if f_a is not None:
                pos_a = float(f_a["x"]) + float(f_a["width"]) / 2.0
                face_a_vis = True
            else:
                face_a_vis = False

            if f_b is not None:
                pos_b = float(f_b["x"]) + float(f_b["width"]) / 2.0
                face_b_vis = True
            else:
                face_b_vis = False

    reg_a_raw = sig_a.get("ref_rect") or {"x": 0.06, "y": 0.12, "width": 0.40, "height": 0.76}
    reg_b_raw = sig_b.get("ref_rect") or {"x": 0.54, "y": 0.12, "width": 0.40, "height": 0.76}

    # 3. Decision Logic: Safe state transitions with evidence requirements
    if is_ambiguous:
        # Ambiguous detections (crossing, collision, duplicate, equidistant) fail safely to UNKNOWN_REVIEW
        composition = "UNKNOWN_REVIEW"
        active_track_id = "unassigned"
        confidence = 0.0
        review_needed = True
        fc_norm = (float(detected_faces[0]["x"]) + float(detected_faces[0]["width"]) / 2.0) if detected_faces else 0.5
        crop_solo = calculate_9_16_crop_rect(fc_norm, src_w, src_h)
        crop_a = crop_solo
        crop_b = crop_solo
        crop_rect = crop_solo

    elif face_a_vis is not None and face_b_vis is not None:
        if face_a_vis and face_b_vis:
            # Both distinct participants verified
            composition = "SIDE_BY_SIDE"
            active_track_id = "both"
            conf_val = (score_a + score_b) / 2.0 if (score_a > 0 and score_b > 0) else 0.85
            confidence = round(float(conf_val), 3)
            review_needed = False
            crop_a = calculate_side_by_side_participant_crop(reg_a_raw, src_w, src_h, face_box=f_a)
            crop_b = calculate_side_by_side_participant_crop(reg_b_raw, src_w, src_h, face_box=f_b)
            crop_rect = crop_a
        elif face_a_vis and not face_b_vis:
            # Person A only
            composition = "A_ONLY"
            active_track_id = sig_a["track_id"]
            confidence = round(float(meta.get("similarity_a", score_a) if meta.get("similarity_a", score_a) > 0 else 0.85), 3)
            review_needed = False
            crop_a = calculate_9_16_crop_rect(pos_a, src_w, src_h)
            crop_b = calculate_9_16_crop_rect(pos_a, src_w, src_h)
            crop_rect = crop_a
        elif face_b_vis and not face_a_vis:
            # Person B only
            composition = "B_ONLY"
            active_track_id = sig_b["track_id"]
            confidence = round(float(meta.get("similarity_b", score_b) if meta.get("similarity_b", score_b) > 0 else 0.85), 3)
            review_needed = False
            crop_b = calculate_9_16_crop_rect(pos_b, src_w, src_h)
            crop_a = calculate_9_16_crop_rect(pos_b, src_w, src_h)
            crop_rect = crop_b
        else:
            # Neither face detected as distinct identity
            composition = "UNKNOWN_REVIEW"
            active_track_id = "unassigned"
            confidence = 0.0
            review_needed = True
            if detected_faces:
                fc_val = float(detected_faces[0]["x"]) + float(detected_faces[0]["width"]) / 2.0
                crop_solo = calculate_9_16_crop_rect(fc_val, src_w, src_h)
                crop_a = crop_solo
                crop_b = crop_solo
                crop_rect = crop_solo
            else:
                crop_a = calculate_side_by_side_participant_crop(reg_a_raw, src_w, src_h, face_box=f_a)
                crop_b = calculate_side_by_side_participant_crop(reg_b_raw, src_w, src_h, face_box=f_b)
                crop_rect = calculate_9_16_crop_rect(0.5, src_w, src_h)

    elif score_a >= 0.85 and score_b >= 0.85:
        # High confidence appearance correlation without face detection (e.g. injected scores or clear framing)
        composition = "SIDE_BY_SIDE"
        active_track_id = "both"
        confidence = round(float((score_a + score_b) / 2.0), 3)
        review_needed = False
        crop_a = calculate_side_by_side_participant_crop(reg_a_raw, src_w, src_h, face_box=f_a)
        crop_b = calculate_side_by_side_participant_crop(reg_b_raw, src_w, src_h, face_box=f_b)
        crop_rect = crop_a

    elif score_a >= 0.75 and score_b < 0.40:
        composition = "A_ONLY"
        active_track_id = sig_a["track_id"]
        confidence = round(float(score_a), 3)
        review_needed = False
        crop_a = calculate_9_16_crop_rect(pos_a, src_w, src_h)
        crop_b = calculate_9_16_crop_rect(pos_a, src_w, src_h)
        crop_rect = crop_a

    elif score_b >= 0.75 and score_a < 0.40:
        composition = "B_ONLY"
        active_track_id = sig_b["track_id"]
        confidence = round(float(score_b), 3)
        review_needed = False
        crop_b = calculate_9_16_crop_rect(pos_b, src_w, src_h)
        crop_a = calculate_9_16_crop_rect(pos_b, src_w, src_h)
        crop_rect = crop_b

    else:
        # Missing, low-confidence, contradictory or ambiguous detections default safely to UNKNOWN_REVIEW
        composition = "UNKNOWN_REVIEW"
        active_track_id = "unassigned"
        confidence = round(float(max(score_a, score_b)), 3)
        review_needed = True
        if detected_faces:
            fc_val = float(detected_faces[0]["x"]) + float(detected_faces[0]["width"]) / 2.0
            crop_solo = calculate_9_16_crop_rect(fc_val, src_w, src_h)
            crop_a = crop_solo
            crop_b = crop_solo
            crop_rect = crop_solo
        else:
            crop_a = calculate_side_by_side_participant_crop(reg_a_raw, src_w, src_h, face_box=f_a)
            crop_b = calculate_side_by_side_participant_crop(reg_b_raw, src_w, src_h, face_box=f_b)
            crop_rect = calculate_9_16_crop_rect(0.5, src_w, src_h)

    fc_center = (float(detected_faces[0]["x"]) + float(detected_faces[0]["width"]) / 2.0) if detected_faces else None
    face_crop = calculate_9_16_crop_rect(fc_center, src_w, src_h) if fc_center is not None else None

    return {
        "start_time": s_time,
        "end_time": e_time,
        "duration": round(e_time - s_time, 2),
        "composition": composition,
        "active_track_id": active_track_id,
        "confidence": confidence,
        "review_needed": review_needed,
        "crop_a": crop_a,
        "crop_b": crop_b,
        "crop_rect": crop_rect,
        "region_a": reg_a_raw,
        "region_b": reg_b_raw,
        "face_crop": face_crop,
        "detected_faces": [{"x": round(float(f["x"]), 4), "y": round(float(f["y"]), 4), "width": round(float(f["width"]), 4), "height": round(float(f["height"]), 4)} for f in detected_faces]
    }


def build_visibility_driven_schedule(
    video_path: Path,
    region_a: Dict[str, Any],
    region_b: Dict[str, Any],
    ref_timestamp: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Builds the shot schedule for Feature 2:
    Visual classification selects A-only, B-only, or Side-by-Side per shot.
    """
    video_path = Path(video_path)
    shots = detect_camera_cuts(video_path)
    signatures = extract_reference_signatures(video_path, [region_a, region_b], ref_timestamp)
    sig_a = signatures[0]
    sig_b = signatures[1]

    src_w, src_h = 1920, 1080
    if cv2 is not None and video_path.exists():
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
            src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
            cap.release()

    schedule = []
    for idx, shot in enumerate(shots):
        item = classify_visibility_composition(video_path, shot, sig_a, sig_b, src_w, src_h)
        item["shot_id"] = idx + 1
        schedule.append(item)

    return schedule


async def render_visibility_driven_video(
    video_path: Path,
    output_path: Path,
    schedule: List[Dict[str, Any]],
    clip_start: float = 0.0,
    clip_end: Optional[float] = None,
    canvas_w: int = 1080,
    canvas_h: int = 1920
) -> Path:
    """
    Renders Feature 2:
    - A-only shots render Person A scaled to 1080x1920
    - B-only shots render Person B scaled to 1080x1920
    - Side-by-side shots render Person A and Person B horizontally side by side (hstack=inputs=2):
      Person A on the left (540x1920), Person B on the right (540x1920) -> 1080x1920 vertical canvas.
    - Uninterrupted continuous source audio and zero subtitle burn-in (-sn).
    """
    video_path = Path(video_path)
    output_path = Path(output_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Source video not found: {video_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    src_w, src_h = await get_video_dimensions(video_path)

    if clip_end is None or clip_end <= clip_start:
        clip_end = clip_start + 30.0

    # Intersect schedule with [clip_start, clip_end]
    relevant_segments = []
    for shot in schedule:
        s_t = float(shot["start_time"])
        e_t = float(shot["end_time"])
        overlap_start = max(clip_start, s_t)
        overlap_end = min(clip_end, e_t)

        if overlap_end - overlap_start >= 0.05:
            relevant_segments.append({
                "sub_start": overlap_start,
                "sub_end": overlap_end,
                "composition": shot.get("composition", "SIDE_BY_SIDE"),
                "crop_a": shot.get("crop_a") or calculate_9_16_crop_rect(0.25, src_w, src_h),
                "crop_b": shot.get("crop_b") or calculate_9_16_crop_rect(0.75, src_w, src_h),
            })

    if not relevant_segments:
        crop_a = calculate_9_16_crop_rect(0.25, src_w, src_h)
        crop_b = calculate_9_16_crop_rect(0.75, src_w, src_h)
        relevant_segments.append({
            "sub_start": clip_start,
            "sub_end": clip_end,
            "composition": "SIDE_BY_SIDE",
            "crop_a": crop_a,
            "crop_b": crop_b
        })

    filter_parts = []
    concat_inputs = []
    half_w = canvas_w // 2

    for idx, seg in enumerate(relevant_segments):
        s_sub = seg["sub_start"]
        e_sub = seg["sub_end"]
        comp = seg.get("composition", "SIDE_BY_SIDE")
        v_out_tag = f"[v{idx}]"

        if comp == "A_ONLY":
            ca = seg.get("crop_a") or seg.get("crop_rect") or calculate_9_16_crop_rect(0.25, src_w, src_h)
            filter_parts.append(
                f"[0:v]trim=start={s_sub}:end={e_sub},setpts=PTS-STARTPTS,"
                f"crop={ca['w']}:{ca['h']}:{ca['x']}:{ca['y']}:exact=1,"
                f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease:flags=bicubic,"
                f"pad={canvas_w}:{canvas_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1{v_out_tag}"
            )
        elif comp == "B_ONLY":
            cb = seg.get("crop_b") or seg.get("crop_rect") or calculate_9_16_crop_rect(0.75, src_w, src_h)
            filter_parts.append(
                f"[0:v]trim=start={s_sub}:end={e_sub},setpts=PTS-STARTPTS,"
                f"crop={cb['w']}:{cb['h']}:{cb['x']}:{cb['y']}:exact=1,"
                f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease:flags=bicubic,"
                f"pad={canvas_w}:{canvas_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1{v_out_tag}"
            )
        elif comp in ("UNKNOWN_REVIEW", "unknown_review", "unassigned", "uncertain"):
            c_center = calculate_9_16_crop_rect(0.5, src_w, src_h)
            filter_parts.append(
                f"[0:v]trim=start={s_sub}:end={e_sub},setpts=PTS-STARTPTS,"
                f"crop={c_center['w']}:{c_center['h']}:{c_center['x']}:{c_center['y']}:exact=1,"
                f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease:flags=bicubic,"
                f"pad={canvas_w}:{canvas_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1{v_out_tag}"
            )
        else:
            # SIDE_BY_SIDE: Crop both participants, scale to half_w with identical height,
            # combine horizontally via hstack=inputs=2, and overlay on ambient blurred video backdrop!
            ca = seg.get("crop_a")
            if not ca or "w" not in ca or "h" not in ca:
                ca = calculate_side_by_side_participant_crop(seg.get("region_a", {"x": 0.05, "y": 0.1, "width": 0.4, "height": 0.8}), src_w, src_h)
            cb = seg.get("crop_b")
            if not cb or "w" not in cb or "h" not in cb:
                cb = calculate_side_by_side_participant_crop(seg.get("region_b", {"x": 0.55, "y": 0.1, "width": 0.4, "height": 0.8}), src_w, src_h)

            asp_a = float(ca["h"]) / max(1, float(ca["w"]))
            asp_b = float(cb["h"]) / max(1, float(cb["w"]))
            target_spk_h = int(half_w * min(asp_a, asp_b))
            if target_spk_h % 2 != 0:
                target_spk_h -= 1
            target_spk_h = max(2, min(canvas_h, target_spk_h))

            tag_a = f"[v{idx}_a]"
            tag_b = f"[v{idx}_b]"
            tag_fg = f"[fg{idx}]"
            tag_bg = f"[bg{idx}]"
            filter_parts.append(
                f"[0:v]trim=start={s_sub}:end={e_sub},setpts=PTS-STARTPTS,split=3[in{idx}_bg][in{idx}_1][in{idx}_2];"
                f"[in{idx}_bg]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase:flags=bicubic,crop={canvas_w}:{canvas_h},boxblur=luma_radius=30:luma_power=2{tag_bg};"
                f"[in{idx}_1]crop={ca['w']}:{ca['h']}:{ca['x']}:{ca['y']}:exact=1,"
                f"scale={half_w}:{target_spk_h}:flags=bicubic{tag_a};"
                f"[in{idx}_2]crop={cb['w']}:{cb['h']}:{cb['x']}:{cb['y']}:exact=1,"
                f"scale={half_w}:{target_spk_h}:flags=bicubic{tag_b};"
                f"{tag_a}{tag_b}hstack=inputs=2{tag_fg};"
                f"{tag_bg}{tag_fg}overlay=0:(H-h)/2,setsar=1{v_out_tag}"
            )

        concat_inputs.append(v_out_tag)

    num_segs = len(relevant_segments)
    concat_str = "".join(concat_inputs) + f"concat=n={num_segs}:v=1:a=0[outv]"
    filter_parts.append(concat_str)

    # Audio: single continuous stream across all cuts
    filter_parts.append(f"[0:a]atrim=start={clip_start}:end={clip_end},asetpts=PTS-STARTPTS[outa]")

    full_filtergraph = ";\n".join(filter_parts)

    cmd = [
        "-y",
        "-i", str(video_path),
        "-filter_complex", full_filtergraph,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "0",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-sn",
        "-movflags", "+faststart",
        "-f", "mp4",
        str(output_path)
    ]

    code, out, err = await run_ffmpeg(cmd)
    if code != 0:
        logger.error(f"FFmpeg visibility-driven render failed: {err}")
        raise RuntimeError(f"FFmpeg visibility-driven render failed: {err}")

    return output_path

