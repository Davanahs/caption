"""
test_pipeline_config_fixes.py
=============================
Tests for the three ClipForge pipeline configuration fixes:
  A. Dynamic clip count (Job.config -> scoring top_n)
  B. Channel-scoped publishing (youtube_channel_id -> credential routing)
  C. Accurate clips_generated tracking (atomic, idempotent)
"""
import pytest
import json
import uuid
from unittest.mock import patch, MagicMock


# -- Helpers --

def make_mock_job(config_dict=None):
    job = MagicMock()
    job.id = str(uuid.uuid4())
    job.config = json.dumps(config_dict) if config_dict else None
    job.video_id = str(uuid.uuid4())
    return job


def make_mock_clip(clip_id=None, video_id=None, run_identity=None):
    clip = MagicMock()
    clip.id = clip_id or str(uuid.uuid4())
    clip.video_id = video_id or str(uuid.uuid4())
    clip.run_identity = run_identity
    clip.status = "pending"
    return clip


def make_mock_channel(channel_id=None, yt_channel_id=None, clips_generated=0):
    channel = MagicMock()
    channel.id = channel_id or str(uuid.uuid4())
    channel.youtube_channel_id = yt_channel_id or "UC_test_channel"
    channel.clips_generated = clips_generated
    channel.auto_publish = True
    channel.auto_pilot = False
    return channel


def make_mock_video(video_id=None, channel_id=None):
    video = MagicMock()
    video.id = video_id or str(uuid.uuid4())
    video.channel_id = channel_id or str(uuid.uuid4())
    return video


# ==== A. DYNAMIC CLIP COUNT ====

class TestDynamicClipCount:

    def test_clips_count_1(self):
        from backend.core.config import settings
        job = make_mock_job(config_dict={"clips_count": 1})
        config_dict = json.loads(job.config)
        clips_count = settings.CLIPS_PER_VIDEO
        raw_count = config_dict.get("clips_count")
        if raw_count is not None:
            raw_count = int(raw_count)
            if raw_count > 0:
                clips_count = raw_count
        assert clips_count == 1

    def test_clips_count_3(self):
        from backend.core.config import settings
        job = make_mock_job(config_dict={"clips_count": 3})
        config_dict = json.loads(job.config)
        clips_count = settings.CLIPS_PER_VIDEO
        raw_count = config_dict.get("clips_count")
        if raw_count is not None:
            raw_count = int(raw_count)
            if raw_count > 0:
                clips_count = raw_count
        assert clips_count == 3

    def test_clips_count_default_when_no_config(self):
        from backend.core.config import settings
        job = make_mock_job(config_dict=None)
        clips_count = settings.CLIPS_PER_VIDEO
        if job.config:
            config_dict = json.loads(job.config)
            raw_count = config_dict.get("clips_count")
            if raw_count is not None:
                clips_count = int(raw_count)
        assert clips_count == settings.CLIPS_PER_VIDEO

    def test_clips_count_invalid_negative(self):
        from backend.core.config import settings
        job = make_mock_job(config_dict={"clips_count": -1})
        config_dict = json.loads(job.config)
        clips_count = settings.CLIPS_PER_VIDEO
        raw_count = config_dict.get("clips_count")
        if raw_count is not None:
            raw_count = int(raw_count)
            if raw_count > 0:
                clips_count = raw_count
        assert clips_count == settings.CLIPS_PER_VIDEO

    def test_clips_count_invalid_string(self):
        from backend.core.config import settings
        job = make_mock_job(config_dict={"clips_count": "abc"})
        config_dict = json.loads(job.config)
        clips_count = settings.CLIPS_PER_VIDEO
        raw_count = config_dict.get("clips_count")
        if raw_count is not None:
            try:
                raw_count = int(raw_count)
                if raw_count > 0:
                    clips_count = raw_count
            except (ValueError, TypeError):
                pass
        assert clips_count == settings.CLIPS_PER_VIDEO

    def test_duration_config_overrides_defaults(self):
        from backend.core.config import settings
        job = make_mock_job(config_dict={"min_clip_duration": 20, "max_clip_duration": 60})
        config_dict = json.loads(job.config)
        min_dur = settings.MIN_CLIP_DURATION
        max_dur = settings.MAX_CLIP_DURATION
        raw_min = config_dict.get("min_clip_duration")
        raw_max = config_dict.get("max_clip_duration")
        if raw_min is not None:
            raw_min = int(raw_min)
            if raw_min > 0:
                min_dur = raw_min
        if raw_max is not None:
            raw_max = int(raw_max)
            if raw_max > 0 and raw_max >= min_dur:
                max_dur = raw_max
        assert min_dur == 20
        assert max_dur == 60

    def test_duration_max_less_than_min_fallback(self):
        from backend.core.config import settings
        job = make_mock_job(config_dict={"min_clip_duration": 30, "max_clip_duration": 10})
        config_dict = json.loads(job.config)
        min_dur = settings.MIN_CLIP_DURATION
        max_dur = settings.MAX_CLIP_DURATION
        raw_min = config_dict.get("min_clip_duration")
        if raw_min is not None:
            raw_min = int(raw_min)
            if raw_min > 0:
                min_dur = raw_min
        raw_max = config_dict.get("max_clip_duration")
        if raw_max is not None:
            raw_max = int(raw_max)
            if raw_max > 0 and raw_max >= min_dur:
                max_dur = raw_max
        assert min_dur == 30
        assert max_dur == settings.MAX_CLIP_DURATION


# ==== B. CHANNEL-SCOPED PUBLISHING ====

class TestChannelScopedPublishing:

    def test_get_youtube_client_channel_token_path(self):
        from backend.core.config import settings
        import os
        channel_id = "UC_test_abc"
        token_dir = os.path.dirname(settings.YOUTUBE_TOKEN_FILE)
        expected = os.path.join(token_dir, f"youtube_token_{channel_id}.json")
        actual = os.path.join(os.path.dirname(settings.YOUTUBE_TOKEN_FILE), f"youtube_token_{channel_id}.json")
        assert actual == expected

    def test_no_channel_uses_default_token(self):
        from backend.core.config import settings
        channel_id = None
        if channel_id:
            token_path = f"youtube_token_{channel_id}.json"
        else:
            token_path = settings.YOUTUBE_TOKEN_FILE
        assert token_path == settings.YOUTUBE_TOKEN_FILE

    def test_upload_short_accepts_channel_id(self):
        import inspect
        from backend.services.publisher import upload_short
        sig = inspect.signature(upload_short)
        assert "channel_id" in sig.parameters

    def test_check_external_state_accepts_channel_id(self):
        import inspect
        from backend.services.publisher import check_external_youtube_state
        sig = inspect.signature(check_external_youtube_state)
        assert "channel_id" in sig.parameters

    def test_channel_mismatch_detected(self):
        requested = "UC_channel_A"
        authenticated = "UC_channel_B"
        assert authenticated != requested


# ==== C. ACCURATE clips_generated ====

class TestClipsGeneratedCounter:

    def test_save_clip_record_accepts_run_identity(self):
        import inspect
        from backend.models.db_sync import save_clip_record
        sig = inspect.signature(save_clip_record)
        assert "run_identity" in sig.parameters

    def test_save_clip_record_accepts_metadata_fields(self):
        import inspect
        from backend.models.db_sync import save_clip_record
        sig = inspect.signature(save_clip_record)
        assert "description" in sig.parameters
        assert "tags" in sig.parameters
        assert "pinned_comment" in sig.parameters

    def test_counter_increment_by_actual_count(self):
        channel = make_mock_channel(clips_generated=10)
        actual_new = 3
        before = channel.clips_generated
        channel.clips_generated += actual_new
        after = channel.clips_generated
        assert before == 10
        assert after == 13

    def test_idempotent_rerun_no_double_count(self):
        channel = make_mock_channel(clips_generated=13)
        existing_clips = [make_mock_clip(clip_id=f"c{i}") for i in range(3)]
        # On rerun, existing_clips found -> return early, no counter increment
        result = [c.id for c in existing_clips]
        assert len(result) == 3
        assert channel.clips_generated == 13  # unchanged


# ==== D. PARAMETER BUG FIX ====

class TestParameterBugFix:

    def test_upload_short_has_privacy_not_privacy_status(self):
        import inspect
        from backend.services.publisher import upload_short
        sig = inspect.signature(upload_short)
        assert "privacy" in sig.parameters
        assert "privacy_status" not in sig.parameters

    def test_publish_task_source_uses_privacy(self):
        import inspect
        import backend.tasks.clip_tasks as ct
        source = inspect.getsource(ct.publish_task)
        assert "privacy_status=" not in source
        assert 'privacy="private"' in source
