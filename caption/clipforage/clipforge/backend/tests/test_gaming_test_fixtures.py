"""
test_gaming_test_fixtures.py
============================
Verification test suite for `backend/tests/gaming_test_fixtures.py` and
`docs/engineering/gaming_geometry_golden_vectors.json`.

Proves:
1. Synthetic video generation via FFmpeg lavfi (1080p, 4K ultrawide, odd-dimension, portrait).
2. Opaque-box inspection with ffprobe (dimensions, h264, yuv420p, aac, faststart moov atom).
3. Strict R5 Zero-Caption invariant enforcement (0 subtitle streams, 0 subtitle files, no caption filters).
4. Negative detection (detects and rejects subtitle files or prohibited filters).
5. Mock DB and Celery task execution helpers.
6. Completeness and validity of `gaming_geometry_golden_vectors.json` (>= 15 vectors, covers presets, odd dimensions, 4K, ultrawide).
"""

import json
import os
import subprocess
from pathlib import Path
import pytest

from backend.tests.gaming_test_fixtures import (
    generate_synthetic_video,
    create_synthetic_1080p_gameplay,
    create_synthetic_4k_ultrawide,
    create_synthetic_odd_dimension,
    create_synthetic_portrait,
    probe_media,
    assert_faststart_moov_atom,
    assert_zero_caption_invariant,
    assert_filtergraph_zero_caption_invariant,
    assert_gaming_video_invariants,
    create_mock_db_session,
    create_mock_celery_task,
    MockJob,
)


class TestGoldenVectorsContract:
    """Verifies that docs/engineering/gaming_geometry_golden_vectors.json adheres to specifications."""

    def test_golden_vectors_file_exists_and_parses(self):
        vectors_path = Path("docs/engineering/gaming_geometry_golden_vectors.json")
        assert vectors_path.exists(), f"Golden vectors file missing at {vectors_path}"

        with open(vectors_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "vectors" in data, "Golden vectors file must contain 'vectors' list"
        vectors = data["vectors"]
        assert len(vectors) >= 15, f"Expected >= 15 vectors, found {len(vectors)}"

    def test_golden_vectors_cover_all_mandatory_categories(self):
        vectors_path = Path("docs/engineering/gaming_geometry_golden_vectors.json")
        with open(vectors_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        vectors = data["vectors"]
        vector_ids = [v["id"] for v in vectors]
        categories = {v.get("category") for v in vectors}

        # Check required categories
        assert "standard-16-9" in categories
        assert "high-resolution" in categories
        assert "ultrawide-21-9" in categories
        assert "odd-dimension" in categories
        assert "placement-presets" in categories
        assert "custom-placement" in categories
        assert "boundary-limits" in categories

        # Check specific required vector scenarios
        required_ids = [
            "vector-01-1080p-standard-top-right",
            "vector-02-720p-standard-top-left",
            "vector-03-4k-highres-bottom-right",
            "vector-13-preset-top-left",
            "vector-14-preset-top-right",
            "vector-15-preset-bottom-left",
            "vector-16-preset-bottom-right",
            "vector-17-custom-placement-center-floating",
            "vector-19-boundary-minimum-size",
            "vector-31-odd-dimension-1919x1079",
            "vector-32-ultrawide-21-9-3840x1600",
        ]
        for req in required_ids:
            assert req in vector_ids, f"Missing mandatory vector: {req}"

    def test_golden_vector_geometry_coordinates_are_even_pixel_aligned(self):
        """Verifies that all valid vectors specify even-pixel crop coordinates for YUV420p."""
        vectors_path = Path("docs/engineering/gaming_geometry_golden_vectors.json")
        with open(vectors_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for v in data["vectors"]:
            exp = v.get("expected", {})
            if not exp.get("is_valid", False):
                continue
            # Some vectors test UI letterbox compensation rather than FFmpeg crops
            if "gameplay_crop" not in exp:
                continue

            gc = exp["gameplay_crop"]
            fc = exp["facecam_crop"]
            fd = exp["facecam_dest"]

            assert gc["x"] % 2 == 0, f"[{v['id']}] gameplay_crop.x must be even: {gc['x']}"
            assert gc["y"] % 2 == 0, f"[{v['id']}] gameplay_crop.y must be even: {gc['y']}"
            assert gc["w"] % 2 == 0, f"[{v['id']}] gameplay_crop.w must be even: {gc['w']}"
            assert gc["h"] % 2 == 0, f"[{v['id']}] gameplay_crop.h must be even: {gc['h']}"

            assert fc["x"] % 2 == 0, f"[{v['id']}] facecam_crop.x must be even: {fc['x']}"
            assert fc["y"] % 2 == 0, f"[{v['id']}] facecam_crop.y must be even: {fc['y']}"
            assert fc["w"] % 2 == 0, f"[{v['id']}] facecam_crop.w must be even: {fc['w']}"
            assert fc["h"] % 2 == 0, f"[{v['id']}] facecam_crop.h must be even: {fc['h']}"

            assert fd["x"] % 2 == 0, f"[{v['id']}] facecam_dest.x must be even: {fd['x']}"
            assert fd["y"] % 2 == 0, f"[{v['id']}] facecam_dest.y must be even: {fd['y']}"
            assert fd["w"] % 2 == 0, f"[{v['id']}] facecam_dest.w must be even: {fd['w']}"
            assert fd["h"] % 2 == 0, f"[{v['id']}] facecam_dest.h must be even: {fd['h']}"


class TestSyntheticMediaFixtures:
    """Verifies synthetic video creation using FFmpeg lavfi sources."""

    def test_create_synthetic_1080p_gameplay(self, tmp_path):
        out_file = tmp_path / "test_1080p.mp4"
        created = create_synthetic_1080p_gameplay(out_file, duration=1.0, fps=25)
        assert created.exists()
        assert created.stat().st_size > 0

        probe = probe_media(created)
        v_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        a_stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")

        assert v_stream["width"] == 1920
        assert v_stream["height"] == 1080
        assert v_stream["codec_name"] == "h264"
        assert v_stream["pix_fmt"] == "yuv420p"
        assert a_stream["codec_name"] == "aac"

        # Verify faststart moov atom precedes mdat
        atoms = assert_faststart_moov_atom(created)
        assert atoms.index("moov") < atoms.index("mdat")

    def test_create_synthetic_4k_ultrawide(self, tmp_path):
        out_file = tmp_path / "test_4k_uw.mp4"
        created = create_synthetic_4k_ultrawide(out_file, duration=1.0, fps=25)
        assert created.exists()

        probe = probe_media(created)
        v_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert v_stream["width"] == 3840
        assert v_stream["height"] == 1600

    def test_create_synthetic_odd_dimension(self, tmp_path):
        out_file = tmp_path / "test_odd.mp4"
        created = create_synthetic_odd_dimension(out_file, duration=1.0, fps=25, width=1919, height=1079)
        assert created.exists()

        probe = probe_media(created)
        v_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert v_stream["width"] == 1919
        assert v_stream["height"] == 1079

    def test_create_synthetic_portrait(self, tmp_path):
        out_file = tmp_path / "test_portrait.mp4"
        created = create_synthetic_portrait(out_file, duration=1.0, fps=25)
        assert created.exists()

        probe = probe_media(created)
        v_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert v_stream["width"] == 1080
        assert v_stream["height"] == 1920


class TestOpaqueBoxInspectorsAndInvariants:
    """Verifies ffprobe inspection functions and R5 Zero-Caption invariant enforcement."""

    def test_assert_gaming_video_invariants_passes_on_valid_9_16(self, tmp_path):
        # Generate 9:16 target video
        out_file = tmp_path / "clean_9_16.mp4"
        generate_synthetic_video(
            output_path=out_file,
            width=1080,
            height=1920,
            duration=1.0,
            fps=25,
            faststart=True,
        )

        res = assert_gaming_video_invariants(
            out_file,
            expected_width=1080,
            expected_height=1920,
            expected_video_codec="h264",
            expected_pix_fmt="yuv420p",
            expected_audio_codec="aac",
            check_faststart=True,
            check_zero_captions=True,
        )
        assert res["width"] == 1080
        assert res["height"] == 1920
        assert res["video_codec"] == "h264"
        assert res["audio_codec"] == "aac"

    def test_r5_zero_caption_passes_when_no_subtitles(self, tmp_path):
        out_file = tmp_path / "clean_video.mp4"
        create_synthetic_1080p_gameplay(out_file, duration=1.0)
        # Must not raise
        assert_zero_caption_invariant(out_file, check_directory=True)

    def test_r5_zero_caption_fails_if_caption_file_exists(self, tmp_path):
        out_file = tmp_path / "video.mp4"
        create_synthetic_1080p_gameplay(out_file, duration=1.0)

        # Drop forbidden subtitle file
        srt_file = tmp_path / "leaked_captions.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

        with pytest.raises(AssertionError) as exc_info:
            assert_zero_caption_invariant(out_file, check_directory=True)
        assert "R5 Violation" in str(exc_info.value)
        assert "leaked_captions.srt" in str(exc_info.value)

    def test_filtergraph_zero_caption_invariant(self):
        clean_graph = (
            "[0:v]crop=1920:1080:0:0,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v0];"
            "[1:v]crop=480:270:1344:54,scale=324:422:force_original_aspect_ratio=increase,crop=324:422[v1];"
            "[v0][v1]overlay=x=702:y=76:eof_action=pass:repeatlast=0,setsar=1[outv]"
        )
        # Must pass cleanly
        assert_filtergraph_zero_caption_invariant(clean_graph)

        dirty_graph = clean_graph + ";[outv]drawtext=text='Game Over'[finalv]"
        with pytest.raises(AssertionError) as exc_info:
            assert_filtergraph_zero_caption_invariant(dirty_graph)
        assert "R5 Violation" in str(exc_info.value)
        assert "drawtext=" in str(exc_info.value)


class TestMockDbAndCeleryHelpers:
    """Verifies mock DB session and Celery task helpers."""

    @pytest.mark.asyncio
    async def test_mock_db_session_operations(self):
        mock_db = create_mock_db_session()
        job = MockJob(job_id="job-123", status="PENDING")

        mock_db.add(job)
        assert len(mock_db.added_objects) == 1
        assert mock_db.added_objects[0].id == "job-123"

        await mock_db.commit()
        assert mock_db.committed is True

        res = await mock_db.execute("dummy statement")
        returned_job = res.scalar_one_or_none()
        assert returned_job is not None
        assert returned_job.id == "job-123"

    def test_mock_celery_task_helpers(self):
        task = create_mock_celery_task("celery-task-999")
        assert task.id == "celery-task-999"

        async_res = task.apply_async(kwargs={"job_id": "job-123"})
        assert async_res.id == "celery-task-999"
        assert async_res.ready() is False
        assert async_res.state == "PENDING"
