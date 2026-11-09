"""
Reframe Engine — Handles advanced spatial layouts, dynamic face tracking,
backdrop blurring, and podcast split screens for vertical video generation.
"""
import asyncio
import numpy as np
from pathlib import Path
from backend.core.config import settings
from backend.services.clip_cutter import run_ffmpeg, get_video_dimensions
from backend.models.layout import LayoutPlan, ScaleMode
from backend.services.layout_engine import LayoutEngine


def apply_smoothing_and_deadzone(target_centers, width, height, crop_w, crop_h, alpha, dead_zone_x=None, dead_zone_y=None):
    if dead_zone_x is None: dead_zone_x = width * 0.05
    if dead_zone_y is None: dead_zone_y = height * 0.05
    
    smoothed_cx = None
    smoothed_cy = None
    coords = []
    
    for (tcx, tcy) in target_centers:
        # Shift target to box origin instead of center
        raw_x = tcx - crop_w / 2
        # Move Y up slightly to give headroom
        raw_y = tcy - crop_h * 0.4
        
        # Constrain to bounds
        raw_x = max(0, min(width - crop_w, raw_x))
        raw_y = max(0, min(height - crop_h, raw_y))

        if smoothed_cx is None:
            smoothed_cx = raw_x
            smoothed_cy = raw_y
        else:
            # Apply deadzone to target
            dist_x = abs(raw_x - smoothed_cx)
            dist_y = abs(raw_y - smoothed_cy)
            
            active_target_x = raw_x if dist_x > dead_zone_x else smoothed_cx
            active_target_y = raw_y if dist_y > dead_zone_y else smoothed_cy
            
            # EMA
            smoothed_cx = alpha * active_target_x + (1 - alpha) * smoothed_cx
            smoothed_cy = alpha * active_target_y + (1 - alpha) * smoothed_cy
        
        # Re-constrain smoothed values to absolute boundaries
        final_x = int(max(0, min(width - crop_w, smoothed_cx)))
        final_y = int(max(0, min(height - crop_h, smoothed_cy)))
        
        # Ensure even coordinates
        final_x = (final_x // 2) * 2
        final_y = (final_y // 2) * 2

        coords.append((final_x, final_y, crop_w, crop_h))
        
    return coords

def build_dynamic_crop_coords(
    video_path: Path,
    crop_w: int,
    crop_h: int,
    width: int,
    height: int,
    alpha: float = 0.15,
    sample_fps: float = 5.0,
) -> tuple[list[tuple[int, int, int, int]], list[int], float, int]:
    default_x = (width - crop_w) // 2
    default_y = (height - crop_h) // 2
    coords = []
    try:
        import cv2
        import mediapipe as mp
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return [(default_x, default_y, crop_w, crop_h)], [0], 25.0, 1

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, int(fps / sample_fps))
        frame_indices = list(range(0, total_frames, step))

        mp_face_mesh = mp.solutions.face_mesh
        mp_face_detection = mp.solutions.face_detection
        
        # State for persistent tracking
        locked_track_id = None
        lock_duration = 0
        grace_period = 0
        MAX_GRACE_PERIOD = int(sample_fps * 1.5)  # 1.5 seconds grace
        SWITCH_THRESHOLD = int(sample_fps * 2.0)  # Must be "better" for 2 secs
        
        tracks = {}
        next_track_id = 0
        
        # Smoothing state
        smoothed_cx = None
        smoothed_cy = None
        
        # Target states
        target_centers = []

        with mp_face_mesh.FaceMesh(max_num_faces=3, refine_landmarks=True, min_detection_confidence=0.5) as face_mesh, mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5) as face_detector:
            for idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if not ret or frame is None:
                    target_centers.append(target_centers[-1] if target_centers else (default_x + crop_w//2, default_y + crop_h//2))
                    continue

                h_f, w_f, _ = frame.shape
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results_mesh = face_mesh.process(rgb_frame)

                current_faces = []
                if results_mesh.multi_face_landmarks:
                    for face_landmarks in results_mesh.multi_face_landmarks:
                        xs_mesh = [l.x * w_f for l in face_landmarks.landmark]
                        ys_mesh = [l.y * h_f for l in face_landmarks.landmark]
                        fx_min, fx_max = min(xs_mesh), max(xs_mesh)
                        fy_min, fy_max = min(ys_mesh), max(ys_mesh)
                        cx_mesh = (fx_min + fx_max) / 2
                        cy_mesh = (fy_min + fy_max) / 2
                        fw_mesh = fx_max - fx_min
                        fh_mesh = fy_max - fy_min
                        # Score face size as a proxy for relevance
                        score = fw_mesh * fh_mesh
                        current_faces.append({"center": (cx_mesh, cy_mesh), "box": (fx_min, fy_min, fw_mesh, fh_mesh), "score": score})
                else:
                    # fallback to face_detector
                    results_det = face_detector.process(rgb_frame)
                    if results_det and results_det.detections:
                        for d in results_det.detections:
                            box = d.location_data.relative_bounding_box
                            fx, fy, fw, fh = int(box.xmin * w_f), int(box.ymin * h_f), int(box.width * w_f), int(box.height * h_f)
                            cx_det = fx + fw / 2
                            cy_det = fy + fh / 2
                            score = fw * fh
                            current_faces.append({"center": (cx_det, cy_det), "box": (fx, fy, fw, fh), "score": score})
                
                # Tracking Logic
                print(f"[DEBUG] frame {idx}: found {len(current_faces)} faces")
                new_tracks = {}
                for face in current_faces:
                    fc_x, fc_y = face["center"]
                    matched_id = None
                    min_dist = 150.0
                    for tid, tinfo in tracks.items():
                        tc_x, tc_y = tinfo["center"]
                        dist = np.sqrt((fc_x - tc_x)**2 + (fc_y - tc_y)**2)
                        if dist < min_dist:
                            min_dist = dist
                            matched_id = tid
                    
                    if matched_id is not None:
                        new_tracks[matched_id] = {"center": (fc_x, fc_y), "score": face["score"], "missed": 0, "active_frames": tracks[matched_id].get("active_frames", 0) + 1}
                    else:
                        new_tracks[next_track_id] = {"center": (fc_x, fc_y), "score": face["score"], "missed": 0, "active_frames": 1}
                        next_track_id += 1
                
                # Add missed tracks for grace period
                for tid, tinfo in tracks.items():
                    if tid not in new_tracks:
                        missed = tinfo.get("missed", 0) + 1
                        if missed <= MAX_GRACE_PERIOD:
                            new_tracks[tid] = {"center": tinfo["center"], "score": tinfo["score"], "missed": missed, "active_frames": tinfo.get("active_frames", 0)}
                
                tracks = new_tracks
                
                best_id = None
                best_score = -1
                for tid, tinfo in tracks.items():
                    if tinfo["missed"] == 0 and tinfo["score"] > best_score:
                        best_score = tinfo["score"]
                        best_id = tid
                
                # Subject Switch Logic
                if locked_track_id is None:
                    if best_id is not None:
                        locked_track_id = best_id
                        lock_duration = tracks[best_id]["active_frames"]
                else:
                    if locked_track_id in tracks:
                        if tracks[locked_track_id]["missed"] > 0:
                            grace_period += 1
                        else:
                            grace_period = 0
                            lock_duration += 1
                        
                        # Switch only if another track is significantly better for a sustained time
                        if best_id != locked_track_id and best_id is not None:
                            if tracks[best_id]["active_frames"] > SWITCH_THRESHOLD and tracks[best_id]["score"] > tracks[locked_track_id]["score"] * 1.5:
                                locked_track_id = best_id
                                lock_duration = tracks[best_id]["active_frames"]
                                grace_period = 0
                                
                        # Hard lose track
                        if grace_period > MAX_GRACE_PERIOD:
                            locked_track_id = best_id if best_id is not None else None
                            grace_period = 0
                            lock_duration = 0
                    else:
                        locked_track_id = best_id if best_id is not None else None
                        grace_period = 0
                        lock_duration = 0

                # Determine target center for this frame
                if locked_track_id is not None and locked_track_id in tracks:
                    target_cx, target_cy = tracks[locked_track_id]["center"]
                else:
                    target_cx, target_cy = (default_x + crop_w//2, default_y + crop_h//2)
                    
                target_centers.append((target_cx, target_cy))

        cap.release()
        
        coords = apply_smoothing_and_deadzone(target_centers, width, height, crop_w, crop_h, alpha)

        return (coords if coords else [(default_x, default_y, crop_w, crop_h)]), (frame_indices if coords else [0]), fps, total_frames

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[FaceCrop] tracking error: {e}. Defaulting to center crop.")
        return [(default_x, default_y, crop_w, crop_h)], [0], 25.0, 1

def detect_best_crop_x(video_path: Path, crop_w: int, width: int, height: int, start_sec: float = None, end_sec: float = None) -> int:
    default_x = (width - crop_w) // 2
    try:
        import cv2
        import mediapipe as mp
        if not video_path.exists(): return default_x
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened(): return default_x
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        start_frame = int(start_sec * fps) if start_sec is not None else 0
        end_frame = min(int(end_sec * fps), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))) if end_sec is not None else int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total_frames = end_frame - start_frame
        sample_interval = max(1, int(fps))
        frame_indices = list(range(start_frame, start_frame + total_frames, sample_interval))
        if len(frame_indices) > 30:
            step = len(frame_indices) / 30
            frame_indices = [frame_indices[int(i * step)] for i in range(30)]
        
        face_x_coords = []
        mp_face_detection = mp.solutions.face_detection
        with mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5) as face_detector:
            for idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if not ret or frame is None: continue
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_detector.process(rgb_frame)
                if results.detections:
                    largest_det = max(results.detections, key=lambda d: d.location_data.relative_bounding_box.width * d.location_data.relative_bounding_box.height)
                    box = largest_det.location_data.relative_bounding_box
                    h_f, w_f, _ = frame.shape
                    fx = int(box.xmin * w_f)
                    fw = int(box.width * w_f)
                    face_x_coords.append(fx + fw // 2)
        cap.release()
        if face_x_coords:
            median_x = int(np.median(face_x_coords))
            return max(0, min(width - crop_w, median_x - crop_w // 2))
    except Exception as e:
        print(f"[FaceCrop] Static error: {e}")
    return default_x

async def burn_hook_title(input_path: Path, output_path: Path, title: str, video_width: int = 1080, font_size: int = 55, max_chars: int = 48, y_offset: int = 36) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)
    from backend.services.clip_cutter import burn_hook_title as _burn
    return await _burn(input_path, output_path, title, video_width, font_size, max_chars, y_offset)

async def reframe_to_vertical(
    input_path: Path, 
    output_path: Path, 
    mode: str = None, 
    template_path: Path = None, 
    hook_title_text: str = None,
    plan: LayoutPlan = None
) -> Path:
    """
    Renders a final video given an input and a LayoutPlan.
    For legacy callers that pass a `mode` string ("blur", "fit", "face"), 
    it will synthesize the corresponding validated LayoutPlan and pipe it to LayoutEngine.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    width, height = await get_video_dimensions(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_w, target_h = 1080, 1920
    cmd_file_path = None
    
    # 1. Compatibility resolution: If no explicit plan is provided, build one from legacy 'mode'
    if plan is None:
        if mode is None:
            mode = getattr(settings, "REFRAME_MODE", "blur_background")
        
        print(f"[Reframe] Input: {width}x{height}, generating plan for legacy mode={mode}")
        
        # Canonical & legacy mode mappings
        if mode == "blur" or mode == "fill_blur": mode = "blur_background"
        if mode == "fit" or mode == "fit_black": mode = "static_wide"
        if mode == "crop": mode = "center_crop"
        if mode == "split" or mode == "split_screen": mode = "multi_split"
        if mode == "stacked": mode = "stacked_16_9"
        if mode == "transform": mode = "creative_transform"
        
        try:
            from backend.models.layout import LayoutMode
            parsed_mode = LayoutMode(mode)
        except ValueError:
            parsed_mode = LayoutMode.CENTER_CROP

        plan = LayoutEngine.resolve_plan(parsed_mode.value, width, height, target_w, target_h)

        input_ratio = width / height
        target_ratio = target_w / target_h
        
        if input_ratio <= target_ratio + 0.02 and parsed_mode != LayoutMode.BLUR_BACKGROUND:
            # Already vertical-ish
            plan.regions[0].scale_mode = ScaleMode.CONTAIN
            
        elif parsed_mode == LayoutMode.CENTER_CROP:
            # Face-tracking dynamic crop Mode
            plan.regions[0].scale_mode = ScaleMode.CONTAIN # The face crop makes it 9:16 already
            
            crop_h = (height // 2) * 2
            crop_w = (int(crop_h * 9 / 16) // 2) * 2
            if crop_w > width:
                crop_w = (width // 2) * 2
                crop_h = (int(crop_w * 16 / 9) // 2) * 2
            
            try:
                coords, frame_indices, fps, total_frames = await asyncio.to_thread(build_dynamic_crop_coords, input_path, crop_w, crop_h, width, height)
                if len(coords) >= 1 and total_frames > 0:
                    all_coords = []
                    for f in range(total_frames):
                        idx = 0
                        while idx < len(frame_indices) - 1 and frame_indices[idx + 1] <= f: idx += 1
                        if idx >= len(frame_indices) - 1 or len(coords) <= 1: all_coords.append(coords[-1])
                        else:
                            f0, f1 = frame_indices[idx], frame_indices[idx + 1]
                            c0, c1 = coords[idx], coords[idx + 1]
                            t_ratio = (f - f0) / (f1 - f0) if f1 != f0 else 0
                            cx = int(c0[0] + (c1[0] - c0[0]) * t_ratio)
                            cy = int(c0[1] + (c1[1] - c0[1]) * t_ratio)
                            cw = int(c0[2] + (c1[2] - c0[2]) * t_ratio)
                            ch = int(c0[3] + (c1[3] - c0[3]) * t_ratio)
                            all_coords.append((cx, cy, cw, ch))
                    cmd_file_path = output_path.parent / f"{output_path.stem}_crop_cmd.txt"
                    with open(cmd_file_path, "w", encoding="utf-8") as f_cmd:
                        for idx_frame, (cx, cy, cw, ch) in enumerate(all_coords):
                            t = idx_frame / fps
                            f_cmd.write(f"{t:.4f} crop x {cx};\n")
                            f_cmd.write(f"{t:.4f} crop y {cy};\n")
                            f_cmd.write(f"{t:.4f} crop w {cw};\n")
                            f_cmd.write(f"{t:.4f} crop h {ch};\n")
                    
                    init_x, init_y, init_w, init_h = all_coords[0]
                    plan.regions[0].crop_coords = (init_x, init_y, init_w, init_h)
                    plan.regions[0].dynamic_crop_file = str(cmd_file_path)
                else: 
                    raise ValueError("No coords returned from dynamic crop")
            except Exception as dyn_err:
                print(f"[Reframe] Dynamic crop failed ({dyn_err})")
                crop_x = await asyncio.to_thread(detect_best_crop_x, input_path, crop_w, width, height)
                crop_y = (height - crop_h) // 2
                crop_x = (crop_x // 2) * 2
                crop_y = (crop_y // 2) * 2
                plan.regions[0].crop_coords = (crop_x, crop_y, crop_w, crop_h)
    
    # 2. Render using the canonical LayoutEngine
    try:
        # Determine how many times we need the input
        # To avoid ffmpeg 'split' deadlocks, we supply the input multiple times
        # Background blur needs 1 if used.
        # Regions need 1 each.
        from collections import defaultdict
        source_counts = defaultdict(int)
        
        if plan.background_policy == plan.background_policy.BLUR:
            # We will use source 0 for background blur, so that's 1 usage of input_path
            source_counts[0] += 1
            
        for r in plan.regions:
            source_counts[r.source_index] += 1
            
        flat_inputs = []
        source_mapping = defaultdict(list)
        
        # We only have `input_path` (source index 0) for legacy mode
        # But for generality, we map all.
        # Assuming all region.source_index refer to `input_path` for legacy wrapper.
        # So we just flatten input_path N times.
        for _ in range(sum(source_counts.values())):
            flat_inputs.append(input_path)
            
        # Re-assign source indices in the plan so each gets a unique input index
        current_idx = 0
        if plan.background_policy == plan.background_policy.BLUR:
            # We assume bg blur implicitly uses source 0 in LayoutEngine. 
            # If LayoutEngine hardcodes [0:v], we must make sure the FIRST input is for blur.
            # So current_idx=0 is for blur, we move to 1 for regions.
            current_idx += 1
            
        for r in plan.regions:
            r.source_index = current_idx
            current_idx += 1
            
        filtergraph = LayoutEngine.build_render_graph(plan, flat_inputs)
        
        ffmpeg_cmd = []
        for inp in flat_inputs:
            ffmpeg_cmd.extend(["-i", str(inp)])
            
        # Optional: unsharp mask (for upscaled outputs to add crispness) 
        # To avoid duplicating logic inside LayoutEngine, we can append standard post-processing
        # but let's strictly append it to outv instead
        filtergraph = filtergraph.replace("[outv]", ",unsharp=5:5:0.8:3:3:0.4[outv]")
        
        ffmpeg_cmd.extend([
            "-filter_complex", filtergraph,
            "-map", "[outv]"
        ])
        
        if "[outa]" in filtergraph:
            ffmpeg_cmd.extend(["-map", "[outa]"])
        else:
            # Map primary audio natively
            ffmpeg_cmd.extend(["-map", "0:a?"])
            
        ffmpeg_cmd.extend([
            "-y",
            "-c:v", "libx264", "-c:a", "aac", 
            "-preset", "fast", "-crf", "18",
            "-movflags", "+faststart", 
            "-f", "mp4",
            str(output_path)
        ])
        
        code, _, err = await run_ffmpeg(ffmpeg_cmd)
        if code != 0: 
            raise RuntimeError(f"FFmpeg reframe failed: {err}")
            
    finally:
        if cmd_file_path and cmd_file_path.exists():
            try: cmd_file_path.unlink()
            except Exception: pass

    # 3. Post-processing
    if False: # hook_title_text (Disabled for visual remediation)
        titled_path = output_path.with_suffix(".titled.mp4")
        try:
            await burn_hook_title(input_path=output_path, output_path=titled_path, title=hook_title_text)
            titled_path.replace(output_path)
        except Exception as ht_err:
            print(f"[HookTitle] Failed: {ht_err}")
            if titled_path.exists(): titled_path.unlink()

    return output_path
