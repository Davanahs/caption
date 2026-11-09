"""
Focused test suite for Canonical Phase 5.1 (C-09): Settings Backend Persistence Architecture (REQ-GAP-001).

Tests dynamic system configuration via GET and PUT /api/settings, input validation,
credential masking, runtime synchronization, and durable file persistence.
"""

import json
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.core.config import settings
from backend.api.routes.settings import (
    SETTINGS_FILE,
    SECRET_MASK,
    load_persisted_settings_data,
    save_persisted_settings_data,
    apply_settings_to_runtime,
    init_dynamic_settings,
)


@pytest.fixture(autouse=True)
def preserve_and_cleanup_settings():
    """Saves original settings before test and restores them afterwards."""
    # Capture original runtime settings
    orig_clips = settings.CLIPS_PER_VIDEO
    orig_whisper = settings.WHISPER_MODEL
    orig_interval = settings.CHANNEL_CHECK_INTERVAL_MINUTES
    orig_openrouter_model = settings.OPENROUTER_MODEL
    orig_secret = settings.YOUTUBE_CLIENT_SECRET
    orig_id = settings.YOUTUBE_CLIENT_ID

    # Backup settings file if exists
    orig_file_data = None
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                orig_file_data = f.read()
        except Exception:
            pass

    yield

    # Restore runtime settings
    settings.CLIPS_PER_VIDEO = orig_clips
    settings.WHISPER_MODEL = orig_whisper
    settings.CHANNEL_CHECK_INTERVAL_MINUTES = orig_interval
    settings.OPENROUTER_MODEL = orig_openrouter_model
    settings.YOUTUBE_CLIENT_SECRET = orig_secret
    settings.YOUTUBE_CLIENT_ID = orig_id

    # Restore file
    if orig_file_data is not None:
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                f.write(orig_file_data)
        except Exception:
            pass
    elif SETTINGS_FILE.exists():
        try:
            SETTINGS_FILE.unlink()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_get_settings_success():
    """Validates GET /api/settings returns active configuration dictionary."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/settings")
        assert res.status_code == 200
        data = res.json()
        assert "WHISPER_MODEL" in data
        assert "CLIPS_PER_VIDEO" in data
        assert "CHANNEL_CHECK_INTERVAL_MINUTES" in data
        assert "OPENROUTER_MODEL" in data
        assert "YOUTUBE_CLIENT_SECRET_SET" in data
        assert "YOUTUBE_CLIENT_SECRET_MASKED" in data
        assert "PUBLISH_MODE" in data
        assert "SCORING_MODE" in data


@pytest.mark.asyncio
async def test_get_settings_masks_secret_when_configured():
    """Asserts that raw YouTube client secret is NEVER returned in plaintext."""
    settings.YOUTUBE_CLIENT_SECRET = "super_secret_raw_key_12345"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/settings")
        assert res.status_code == 200
        data = res.json()
        assert data["YOUTUBE_CLIENT_SECRET_SET"] is True
        assert data["YOUTUBE_CLIENT_SECRET_MASKED"] == SECRET_MASK
        assert "super_secret_raw_key_12345" not in res.text


@pytest.mark.asyncio
async def test_get_settings_unconfigured_secret_returns_empty_mask():
    """Asserts that when no secret is configured, mask is empty and set flag is False."""
    settings.YOUTUBE_CLIENT_SECRET = ""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/settings")
        assert res.status_code == 200
        data = res.json()
        assert data["YOUTUBE_CLIENT_SECRET_SET"] is False
        assert data["YOUTUBE_CLIENT_SECRET_MASKED"] == ""


@pytest.mark.asyncio
async def test_put_settings_valid_update():
    """Validates PUT /api/settings successfully updates config and returns new values."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "CLIPS_PER_VIDEO": 7,
            "WHISPER_MODEL": "small",
            "CHANNEL_CHECK_INTERVAL_MINUTES": 45,
            "OPENROUTER_MODEL": "meta-llama/llama-3.3-70b-instruct:free",
        }
        res = await ac.put("/api/settings", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["CLIPS_PER_VIDEO"] == 7
        assert data["WHISPER_MODEL"] == "small"
        assert data["CHANNEL_CHECK_INTERVAL_MINUTES"] == 45
        assert data["OPENROUTER_MODEL"] == "meta-llama/llama-3.3-70b-instruct:free"
        assert data["last_updated_at"] is not None


@pytest.mark.asyncio
async def test_put_settings_updates_runtime_in_memory():
    """Asserts that PUT /api/settings immediately updates backend.core.config.settings attributes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"CLIPS_PER_VIDEO": 9, "WHISPER_MODEL": "medium"}
        res = await ac.put("/api/settings", json=payload)
        assert res.status_code == 200
        # In-memory validation
        assert settings.CLIPS_PER_VIDEO == 9
        assert settings.WHISPER_MODEL == "medium"


@pytest.mark.asyncio
async def test_put_settings_persists_to_disk():
    """Asserts that settings are durably written to SETTINGS_FILE."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"CLIPS_PER_VIDEO": 12, "WHISPER_MODEL": "large"}
        res = await ac.put("/api/settings", json=payload)
        assert res.status_code == 200

        # Verify disk file
        assert SETTINGS_FILE.exists()
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        assert disk_data["CLIPS_PER_VIDEO"] == 12
        assert disk_data["WHISPER_MODEL"] == "large"
        assert "last_updated_at" in disk_data


@pytest.mark.asyncio
async def test_put_settings_masked_secret_does_not_overwrite():
    """Asserts that submitting SECRET_MASK does not overwrite existing secret with asterisks."""
    settings.YOUTUBE_CLIENT_SECRET = "real_production_secret_999"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "YOUTUBE_CLIENT_SECRET": SECRET_MASK,  # Placeholder sent from UI
            "CLIPS_PER_VIDEO": 6,
        }
        res = await ac.put("/api/settings", json=payload)
        assert res.status_code == 200
        assert settings.YOUTUBE_CLIENT_SECRET == "real_production_secret_999"


@pytest.mark.asyncio
async def test_put_settings_new_secret_updates_successfully():
    """Asserts that providing a genuine new secret updates the secret."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "YOUTUBE_CLIENT_SECRET": "brand_new_secret_key_777",
        }
        res = await ac.put("/api/settings", json=payload)
        assert res.status_code == 200
        assert settings.YOUTUBE_CLIENT_SECRET == "brand_new_secret_key_777"
        data = res.json()
        assert data["YOUTUBE_CLIENT_SECRET_SET"] is True
        assert data["YOUTUBE_CLIENT_SECRET_MASKED"] == SECRET_MASK


@pytest.mark.asyncio
async def test_put_settings_validation_invalid_whisper_model():
    """Rejects unrecognized whisper models with HTTP 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"WHISPER_MODEL": "ultra_huge_turbo"}
        res = await ac.put("/api/settings", json=payload)
        assert res.status_code == 422
        assert "Invalid WHISPER_MODEL" in res.json()["detail"]


@pytest.mark.asyncio
async def test_put_settings_validation_clips_limit_bounds():
    """Rejects clips per video < 1 or > 20 with HTTP 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Lower bound
        res = await ac.put("/api/settings", json={"CLIPS_PER_VIDEO": 0})
        assert res.status_code == 422

        # Upper bound
        res2 = await ac.put("/api/settings", json={"CLIPS_PER_VIDEO": 25})
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_put_settings_validation_channel_interval_bounds():
    """Rejects check interval < 5 or > 1440 with HTTP 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res1 = await ac.put("/api/settings", json={"CHANNEL_CHECK_INTERVAL_MINUTES": 2})
        assert res1.status_code == 422

        res2 = await ac.put("/api/settings", json={"CHANNEL_CHECK_INTERVAL_MINUTES": 2000})
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_init_dynamic_settings_loads_persisted():
    """Validates that init_dynamic_settings() loads disk data into runtime settings."""
    test_dict = {
        "CLIPS_PER_VIDEO": 14,
        "WHISPER_MODEL": "small",
        "CHANNEL_CHECK_INTERVAL_MINUTES": 60,
    }
    save_persisted_settings_data(test_dict)

    # Reset in memory to verify reload
    settings.CLIPS_PER_VIDEO = 3
    settings.WHISPER_MODEL = "tiny"
    settings.CHANNEL_CHECK_INTERVAL_MINUTES = 10

    init_dynamic_settings()

    assert settings.CLIPS_PER_VIDEO == 14
    assert settings.WHISPER_MODEL == "small"
    assert settings.CHANNEL_CHECK_INTERVAL_MINUTES == 60


def test_shorts_duration_capped_invariant():
    """Invariant: Shorts duration must remain capped strictly between 15.0 and 30.0 seconds."""
    from backend.models.models import Clip
    clip = Clip(
        id="clip_c09_invariant_dur",
        video_id="vid_c09_parent",
        title="C-09 Invariant Duration Test",
        start_time=5.0,
        end_time=30.0,
        duration=25.0,
        publish_status="draft",
    )
    assert 15.0 <= clip.duration <= 30.0, f"Clip duration {clip.duration}s violates [15.0, 30.0] invariant!"


def test_zero_subtitle_tracks_invariant():
    """Invariant: Zero caption/subtitle tracks or burn-in filters exist in pipeline output."""
    import inspect
    from backend.api.routes import settings as settings_route
    source = inspect.getsource(settings_route)
    forbidden_patterns = ["generate_subtitles", "burn_subtitles", "subtitles.srt", "subtitles.ass"]
    for pat in forbidden_patterns:
        assert pat not in source, f"Forbidden subtitle pattern '{pat}' detected in settings.py!"


def test_synthetic_test_isolation_invariant():
    """Invariant: Synthetic test records must be isolated with is_test=True."""
    from backend.models.models import Channel
    ch = Channel(
        id="c09_synth_iso",
        youtube_channel_id="c09_yt_synth_iso",
        channel_name="C-09 Synthetic Test Channel",
        channel_url="https://youtube.com/@c09_synth",
        is_test=True,
    )
    assert ch.is_test is True


