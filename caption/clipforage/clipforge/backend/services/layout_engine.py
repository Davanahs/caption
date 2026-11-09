import math
from pathlib import Path
from backend.models.layout import LayoutPlan, RegionModel, AudioPolicy, BackgroundPolicy, ScaleMode, LayoutMode

class LayoutEngine:
    @staticmethod
    def create_vertical_plan(source_w: int, source_h: int, canvas_w: int = 1080, canvas_h: int = 1920, crop_coords: tuple[int, int, int, int] = None) -> LayoutPlan:
        """
        Creates a canonical single-source vertical plan.
        Preserves aspect ratio, fits inside the canvas, defaults to black padding.
        """
        region = RegionModel(
            source_index=0,
            x=0,
            y=0,
            w=canvas_w,
            h=canvas_h,
            scale_mode=ScaleMode.CONTAIN, # Fit within the canvas
            z_order=1,
            crop_coords=crop_coords
        )
        return LayoutPlan(
            mode=LayoutMode.CENTER_CROP,
            canvas_width=canvas_w,
            canvas_height=canvas_h,
            regions=[region],
            background_policy=BackgroundPolicy.NONE,
            audio_policy=AudioPolicy.PRIMARY_ONLY
        )

    @staticmethod
    def create_blur_plan(source_w: int, source_h: int, canvas_w: int = 1080, canvas_h: int = 1920) -> LayoutPlan:
        """
        Creates a single-source vertical plan with a blurred backdrop.
        If the source is already vertical, we scale it down slightly so the blur is visible.
        If it's horizontal, it will fit exactly into the width, revealing blur on top/bottom.
        """
        aspect_ratio = source_w / source_h
        target_aspect = canvas_w / canvas_h
        
        # Calculate FIT dimensions exactly
        if aspect_ratio > target_aspect:
            # Video is wider than canvas (e.g. 16:9 on 9:16)
            fit_w = canvas_w
            fit_h = int(canvas_w / aspect_ratio)
        else:
            # Video is taller than canvas (e.g. 9:16 on 9:16)
            # Scale down slightly to 80% to reveal the blur behind it
            fit_h = int(canvas_h * 0.8)
            fit_w = int(fit_h * aspect_ratio)
            
        fit_w = fit_w if fit_w % 2 == 0 else fit_w - 1
        fit_h = fit_h if fit_h % 2 == 0 else fit_h - 1
        
        region = RegionModel(
            source_index=0,
            x=(canvas_w - fit_w) // 2,
            y=(canvas_h - fit_h) // 2,
            w=fit_w,
            h=fit_h,
            scale_mode=ScaleMode.FIT,
            z_order=1
        )
        return LayoutPlan(
            mode=LayoutMode.BLUR_BACKGROUND,
            canvas_width=canvas_w,
            canvas_height=canvas_h,
            regions=[region],
            background_policy=BackgroundPolicy.BLUR,
            audio_policy=AudioPolicy.PRIMARY_ONLY
        )

    @staticmethod
    def create_modern_plan(source_w: int, source_h: int, canvas_w: int = 1080, canvas_h: int = 1920) -> LayoutPlan:
        h = int(canvas_w * (source_h / source_w))
        region = RegionModel(
            source_index=0,
            x=0,
            y=(canvas_h - h) // 2,
            w=canvas_w,
            h=h,
            scale_mode=ScaleMode.FILL,
            z_order=1
        )
        return LayoutPlan(
            mode=LayoutMode.MODERN_PADDING,
            canvas_width=canvas_w,
            canvas_height=canvas_h,
            regions=[region],
            background_policy=BackgroundPolicy.GRADIENT,
            audio_policy=AudioPolicy.PRIMARY_ONLY
        )

    @staticmethod
    def create_multi_split_plan(source_w: int, source_h: int, canvas_w: int = 1080, canvas_h: int = 1920) -> LayoutPlan:
        half_h = canvas_h // 2
        r1 = RegionModel(
            source_index=0, x=0, y=0, w=canvas_w, h=half_h,
            scale_mode=ScaleMode.CROP, z_order=1
        )
        r2 = RegionModel(
            source_index=1, x=0, y=half_h, w=canvas_w, h=half_h,
            scale_mode=ScaleMode.CROP, z_order=1
        )
        return LayoutPlan(
            mode=LayoutMode.MULTI_SPLIT,
            canvas_width=canvas_w,
            canvas_height=canvas_h,
            regions=[r1, r2],
            background_policy=BackgroundPolicy.NONE,
            audio_policy=AudioPolicy.MIX
        )

    @staticmethod
    def create_stacked_plan(source_w: int, source_h: int, canvas_w: int = 1080, canvas_h: int = 1920) -> LayoutPlan:
        h = int(canvas_w * (source_h / source_w))
        r1 = RegionModel(
            source_index=0, x=0, y=(canvas_h // 2 - h) // 2, w=canvas_w, h=h,
            scale_mode=ScaleMode.FILL, z_order=1
        )
        r2 = RegionModel(
            source_index=1, x=0, y=canvas_h // 2 + (canvas_h // 2 - h) // 2, w=canvas_w, h=h,
            scale_mode=ScaleMode.FILL, z_order=1
        )
        return LayoutPlan(
            mode=LayoutMode.STACKED_16_9,
            canvas_width=canvas_w,
            canvas_height=canvas_h,
            regions=[r1, r2],
            background_policy=BackgroundPolicy.COLOR,
            audio_policy=AudioPolicy.MIX
        )

    @staticmethod
    def create_transform_plan(source_w: int, source_h: int, canvas_w: int = 1080, canvas_h: int = 1920) -> LayoutPlan:
        region = RegionModel(
            source_index=0, x=0, y=0, w=canvas_w, h=canvas_h,
            scale_mode=ScaleMode.CROP, z_order=1,
            hflip=True, rotation_angle=2.5, scale_factor=1.1
        )
        return LayoutPlan(
            mode=LayoutMode.CREATIVE_TRANSFORM,
            canvas_width=canvas_w,
            canvas_height=canvas_h,
            regions=[region],
            background_policy=BackgroundPolicy.NONE,
            audio_policy=AudioPolicy.PRIMARY_ONLY
        )

    @staticmethod
    def create_podcast_plan(
        regions_normalized: list[dict],
        source_w: int,
        source_h: int,
        composition: str = "stacked",
        canvas_w: int = 1080,
        canvas_h: int = 1920
    ) -> LayoutPlan:
        """
        Creates a custom LayoutPlan based on user-selected manual crop regions
        for podcast and interview videos.
        Supports single-region framing and multi-region stacked compositions.
        """
        if not regions_normalized:
            return LayoutEngine.create_vertical_plan(source_w, source_h, canvas_w, canvas_h)

        crop_coords_list = []
        for r in regions_normalized:
            rx = float(r.get("x", 0.0))
            ry = float(r.get("y", 0.0))
            rw = float(r.get("width") if r.get("width") is not None else r.get("w", 0.5))
            rh = float(r.get("height") if r.get("height") is not None else r.get("h", 0.5))

            # Clamp normalized coordinates strictly to [0.0, 1.0]
            rx = max(0.0, min(0.99, rx))
            ry = max(0.0, min(0.99, ry))
            rw = max(0.01, min(1.0 - rx, rw))
            rh = max(0.01, min(1.0 - ry, rh))

            cx = int(round(rx * source_w))
            cy = int(round(ry * source_h))
            cw = int(round(rw * source_w))
            ch = int(round(rh * source_h))

            # Ensure even dimensions for video codecs
            cx = (cx // 2) * 2
            cy = (cy // 2) * 2
            cw = max(2, (cw // 2) * 2)
            ch = max(2, (ch // 2) * 2)

            # Clamp to frame dimensions
            if cx + cw > source_w:
                cw = max(2, ((source_w - cx) // 2) * 2)
            if cy + ch > source_h:
                ch = max(2, ((source_h - cy) // 2) * 2)

            crop_coords_list.append((cx, cy, cw, ch))

        comp_lower = (composition or "stacked").lower()
        if comp_lower in ("advanced_podcast", "camera_following"):
            # Advanced camera-following podcast: single vertical full-frame view (strictly NO stacked panels)
            region = RegionModel(
                source_index=0,
                x=0,
                y=0,
                w=canvas_w,
                h=canvas_h,
                crop_coords=crop_coords_list[0],
                scale_mode=ScaleMode.CONTAIN,
                z_order=1
            )
            return LayoutPlan(
                mode=LayoutMode.CENTER_CROP,
                canvas_width=canvas_w,
                canvas_height=canvas_h,
                regions=[region],
                background_policy=BackgroundPolicy.COLOR,
                audio_policy=AudioPolicy.PRIMARY_ONLY
            )

        if len(regions_normalized) == 1 or comp_lower in ("single", "single_region", "single_focus"):
            # Single speaker / single region full vertical framing
            region = RegionModel(
                source_index=0,
                x=0,
                y=0,
                w=canvas_w,
                h=canvas_h,
                crop_coords=crop_coords_list[0],
                scale_mode=ScaleMode.CONTAIN,
                z_order=1
            )
            return LayoutPlan(
                mode=LayoutMode.CENTER_CROP,
                canvas_width=canvas_w,
                canvas_height=canvas_h,
                regions=[region],
                background_policy=BackgroundPolicy.COLOR,
                audio_policy=AudioPolicy.PRIMARY_ONLY
            )
        else:
            # 2+ speakers stacked layout (top speaker, bottom speaker)
            half_h = canvas_h // 2
            r1 = RegionModel(
                source_index=0,
                x=0,
                y=0,
                w=canvas_w,
                h=half_h,
                crop_coords=crop_coords_list[0],
                scale_mode=ScaleMode.CONTAIN,
                z_order=1
            )
            r2 = RegionModel(
                source_index=1,
                x=0,
                y=half_h,
                w=canvas_w,
                h=half_h,
                crop_coords=crop_coords_list[1] if len(crop_coords_list) > 1 else crop_coords_list[0],
                scale_mode=ScaleMode.CONTAIN,
                z_order=2
            )
            return LayoutPlan(
                mode=LayoutMode.STACKED_16_9,
                canvas_width=canvas_w,
                canvas_height=canvas_h,
                regions=[r1, r2],
                background_policy=BackgroundPolicy.COLOR,
                audio_policy=AudioPolicy.PRIMARY_ONLY
            )

    @classmethod
    def resolve_plan(cls, mode_str: str, source_w: int, source_h: int, canvas_w: int = 1080, canvas_h: int = 1920) -> LayoutPlan:
        if not mode_str:
            return cls.create_vertical_plan(source_w, source_h, canvas_w, canvas_h)
            
        try:
            mode = LayoutMode(mode_str)
        except ValueError:
            mode = LayoutMode.CENTER_CROP

        if mode == LayoutMode.BLUR_BACKGROUND:
            return cls.create_blur_plan(source_w, source_h, canvas_w, canvas_h)
        elif mode == LayoutMode.MODERN_PADDING:
            return cls.create_modern_plan(source_w, source_h, canvas_w, canvas_h)
        elif mode == LayoutMode.MULTI_SPLIT:
            return cls.create_multi_split_plan(source_w, source_h, canvas_w, canvas_h)
        elif mode == LayoutMode.STACKED_16_9:
            return cls.create_stacked_plan(source_w, source_h, canvas_w, canvas_h)
        elif mode == LayoutMode.CREATIVE_TRANSFORM:
            return cls.create_transform_plan(source_w, source_h, canvas_w, canvas_h)
        else:
            return cls.create_vertical_plan(source_w, source_h, canvas_w, canvas_h)

    @staticmethod
    def build_render_graph(plan: LayoutPlan, inputs: list[Path]) -> str:
        """
        Constructs the precise, validated FFmpeg filtergraph string dynamically based on the plan.
        Raises ValueError if layout is invalid before touching ffmpeg.
        """
        if not inputs:
            raise ValueError("No input files provided")
        for r in plan.regions:
            if r.source_index < 0 or r.source_index >= len(inputs):
                raise ValueError(f"Region references invalid source index {r.source_index}")

        # Check which inputs are used multiple times (including by the background blur)
        from collections import defaultdict
        source_usage = defaultdict(int)
        
        if plan.background_policy == BackgroundPolicy.BLUR:
            source_usage[0] += 1
            
        for r in plan.regions:
            source_usage[r.source_index] += 1
            
        # Basic setup
        filters = []
        
        # Pre-split inputs
        split_names = defaultdict(list)
        for src_idx, count in source_usage.items():
            if count > 1:
                splits = [f"src_{src_idx}_{i}" for i in range(count)]
                filters.append(f"[{src_idx}:v]split={count}" + "".join([f"[{s}]" for s in splits]))
                split_names[src_idx] = splits
        
        def get_source_label(idx: int) -> str:
            if source_usage[idx] > 1:
                return split_names[idx].pop(0)
            return f"{idx}:v"
            
        out_labels = []

        # Background generation
        bg_label = "bg"
        if plan.background_policy == BackgroundPolicy.BLUR:
            # Assumes source 0 is used for blur
            bg_in = get_source_label(0)
            filters.append(f"[{bg_in}]scale={plan.canvas_width}:{plan.canvas_height}:force_original_aspect_ratio=increase,crop={plan.canvas_width}:{plan.canvas_height},boxblur=luma_radius=30:luma_power=2[{bg_label}]")
        elif plan.background_policy == BackgroundPolicy.COLOR:
            filters.append(f"color=c=black:s={plan.canvas_width}x{plan.canvas_height}[{bg_label}]")
        elif plan.background_policy == BackgroundPolicy.GRADIENT:
            # Modern dark gray solid as a base for 'gradient' policy since FFmpeg geq is slow
            filters.append(f"color=c=0x1a1a1a:s={plan.canvas_width}x{plan.canvas_height}[{bg_label}]")
        else: # NONE
            filters.append(f"color=c=black:s={plan.canvas_width}x{plan.canvas_height}[{bg_label}]")
            
        current_bg = bg_label

        # Process each region
        # Sort regions by z-order
        sorted_regions = sorted(plan.regions, key=lambda r: r.z_order)

        for i, r in enumerate(sorted_regions):
            v_in = get_source_label(r.source_index)
            # 1. Apply crop if crop_coords or dynamic_crop_file is present
            if r.dynamic_crop_file:
                # Use sendcmd for dynamic crop (w and h must be provided to initialize the crop filter correctly)
                # Note: We need initial width and height, usually they are set by the first crop command,
                # but ffmpeg crop requires initial w/h strings. If r.crop_coords is given alongside dynamic_crop_file, we use that for initialization.
                init_w = r.crop_coords[2] if r.crop_coords else r.w
                init_h = r.crop_coords[3] if r.crop_coords else r.h
                init_x = r.crop_coords[0] if r.crop_coords else 0
                init_y = r.crop_coords[1] if r.crop_coords else 0
                cmd_path_str = r.dynamic_crop_file.replace("\\", "/").replace(":", "\\:")
                filters.append(f"[{v_in}]sendcmd=f='{cmd_path_str}',crop={init_w}:{init_h}:{init_x}:{init_y}[cropped_{i}]")
                v_in = f"cropped_{i}"
            elif r.crop_coords:
                cx, cy, cw, ch = r.crop_coords
                filters.append(f"[{v_in}]crop={cw}:{ch}:{cx}:{cy}[cropped_{i}]")
                v_in = f"cropped_{i}"

            # 2. Zoom Interventions (Dynamic Crop)
            if r.zoom_interventions:
                zoom_expr = "1.0"
                for z in r.zoom_interventions:
                    zoom_expr += f"+({z.zoom_factor}-1.0)*between(t,{z.start_time},{z.end_time})"
                # Crop to center based on zoom factor (expressions quoted to protect commas in between() from splitting filtergraph)
                crop_filter = f"crop=w='iw/({zoom_expr})':h='ih/({zoom_expr})':x='(iw-out_w)/2':y='(ih-out_h)/2':exact=1"
                filters.append(f"[{v_in}]{crop_filter}[zoomed_{i}]")
                v_in = f"zoomed_{i}"

            # 2.5 Creative Transformations
            if getattr(r, 'scale_factor', 1.0) != 1.0:
                sf = r.scale_factor
                filters.append(f"[{v_in}]crop=iw/({sf}):ih/({sf}):(iw-iw/({sf}))/2:(ih-ih/({sf}))/2:exact=1[scaled_factor_{i}]")
                v_in = f"scaled_factor_{i}"

            if getattr(r, 'rotation_angle', 0.0) != 0.0:
                angle_rad = r.rotation_angle * math.pi / 180.0
                filters.append(f"[{v_in}]rotate={angle_rad}:c=black@0[rot_{i}]")
                v_in = f"rot_{i}"

            if getattr(r, 'hflip', False):
                filters.append(f"[{v_in}]hflip[hflip_{i}]")
                v_in = f"hflip_{i}"

            # 3. Scale
            if r.scale_mode == ScaleMode.CONTAIN:
                filters.append(f"[{v_in}]scale={r.w}:{r.h}:force_original_aspect_ratio=decrease,pad={r.w}:{r.h}:(ow-iw)/2:(oh-ih)/2:color=black[scaled_{i}]")
            elif r.scale_mode == ScaleMode.FILL:
                filters.append(f"[{v_in}]scale={r.w}:{r.h}[scaled_{i}]")
            elif r.scale_mode == ScaleMode.CROP:
                filters.append(f"[{v_in}]scale={r.w}:{r.h}:force_original_aspect_ratio=increase,crop={r.w}:{r.h}[scaled_{i}]")
            elif r.scale_mode == ScaleMode.FIT:
                # Scale proportionally without adding any padding (relies on RegionModel x,y for placement)
                filters.append(f"[{v_in}]scale={r.w}:{r.h}:force_original_aspect_ratio=decrease[scaled_{i}]")
            
            # 4. Temporal Fades & PTS alignment for secondary overlays
            v_overlay = f"scaled_{i}"
            if getattr(r, 'start_time', None) is not None and getattr(r, 'end_time', None) is not None:
                # Delay secondary overlay stream so frame 0 begins at start_time
                if r.start_time > 0:
                    v_shifted = f"shifted_{i}"
                    filters.append(f"[{v_overlay}]setpts=PTS-STARTPTS+{r.start_time}/TB[{v_shifted}]")
                    v_overlay = v_shifted

                if getattr(r, 'fade_duration', 0) > 0:
                    v_faded = f"faded_{i}"
                    filters.append(f"[{v_overlay}]format=rgba,fade=t=in:st={r.start_time}:d={r.fade_duration}:alpha=1,fade=t=out:st={r.end_time-r.fade_duration}:d={r.fade_duration}:alpha=1[{v_faded}]")
                    v_overlay = v_faded
            
            # 5. Overlay
            next_bg = f"overlayed_{i}"
            # Only region 0 on infinite background uses shortest=1 to prevent endless rendering.
            # Secondary regions (B-roll, cutaways, overlays) MUST use eof_action=pass so they never
            # truncate the base clip duration when a short overlay ends.
            if i == 0:
                overlay_cmd = f"overlay=x={r.x}:y={r.y}:shortest=1"
            else:
                overlay_cmd = f"overlay=x={r.x}:y={r.y}:eof_action=pass:repeatlast=0"

            if getattr(r, 'start_time', None) is not None and getattr(r, 'end_time', None) is not None:
                overlay_cmd += f":enable='between(t,{r.start_time},{r.end_time})'"
            filters.append(f"[{current_bg}][{v_overlay}]{overlay_cmd}[{next_bg}]")
            current_bg = next_bg

        # Final video output
        filters.append(f"[{current_bg}]setsar=1[outv]")

        # Audio handling
        if plan.audio_policy == AudioPolicy.PRIMARY_ONLY:
            # Map audio from source 0
            pass # We don't need a complex filter for audio if we just use -map 0:a later, but we can do an amix if we want
        elif plan.audio_policy == AudioPolicy.MUTE_SECONDARY:
            pass # Same as PRIMARY_ONLY if source 0 is primary
        elif plan.audio_policy == AudioPolicy.MIX:
            # Mix all distinct sources
            unique_sources = list(set([r.source_index for r in plan.regions]))
            if len(unique_sources) > 1:
                amix_inputs = "".join([f"[{src}:a]" for src in unique_sources])
                filters.append(f"{amix_inputs}amix=inputs={len(unique_sources)}:duration=first:dropout_transition=2[outa]")

        return ";".join(filters)
