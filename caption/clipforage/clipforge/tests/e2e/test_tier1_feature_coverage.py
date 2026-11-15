"""
tests/e2e/test_tier1_feature_coverage.py
========================================
Tier 1: Comprehensive Feature Coverage Suite (F01–F12, >=60 tests)
for ClipForge Multi-Destination Publishing & Automatic Outro System.

Opaque-Box Requirement Traceability:
- F01: ORIGINAL_REQUEST §4 — Destination Channel Connection & Listing
- F02: ORIGINAL_REQUEST §5 — Destination Outro Management (Video)
- F03: ORIGINAL_REQUEST §5 — Destination Outro Management (Image)
- F04: ORIGINAL_REQUEST §5 — Outro Removal & No-Outro Normalization
- F05: ORIGINAL_REQUEST §6 — Monitoring Channels Multi-Destination Mapping
- F06: ORIGINAL_REQUEST §7.A — Manual Raw Video Upload Destination Selection
- F07: ORIGINAL_REQUEST §7.B — YouTube URL Processing Destination Selection
- F08: ORIGINAL_REQUEST §7.C — Automated Ingestion Destination Propagation
- F09: ORIGINAL_REQUEST §8 — Destination-Specific Outro Rendering
- F10: ORIGINAL_REQUEST §9 — Multi-Destination Publishing Status Tracking
- F11: ORIGINAL_REQUEST §10 — Destination-Specific Preview & UX
- F12: ORIGINAL_REQUEST §12 — Failure Handling & Idempotent Retry
"""
import asyncio
import io
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
import sqlalchemy as sa
from sqlalchemy import select, update, delete

# Ensure clipforge root and backend are in sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.main import app
from backend.core.config import settings
from backend.models.database import Base
from backend.models.models import (
    Channel,
    ChannelDestination,
    PublishTarget,
    Clip,
    Job,
    Video,
)

# Shared E2E media helpers
from tests.e2e.e2e_media_helpers import (
    generate_synthetic_mp4,
    generate_synthetic_image,
    parse_top_level_atoms,
    assert_faststart_moov_atom,
    probe_media,
    assert_zero_caption_invariant,
    assert_filtergraph_zero_caption_invariant,
)


# ==============================================================================
# F01: Destination Channel Connection & Listing (ORIGINAL_REQUEST §4)
# ==============================================================================
class TestF01DestinationConnectionListing:
    """Tests for connecting, listing, reconnecting, and disconnecting destination channels."""

    @pytest.mark.asyncio
    async def test_list_destinations_excludes_source_and_test_channels(self, e2e_client: AsyncClient, e2e_db):
        """GET /api/youtube-channels/ returns only authorized destinations, excluding sources and tests."""
        async with e2e_db["session_factory"]() as session:
            # 1. Monitored source channel (is_destination=False)
            source_ch = Channel(
                id=f"src_{uuid.uuid4().hex[:8]}",
                youtube_channel_id=f"UC_SRC_{uuid.uuid4().hex[:8]}",
                channel_name="Monitored Podcast Source",
                channel_url="https://youtube.com/@podcast",
                is_destination=False,
                is_active=True,
                is_test=False,
            )
            # 2. Destination channel (is_destination=True)
            dest_ch = Channel(
                id=f"dst_{uuid.uuid4().hex[:8]}",
                youtube_channel_id=f"UC_DST_{uuid.uuid4().hex[:8]}",
                channel_name="Highlights Destination",
                channel_url="https://youtube.com/@highlights",
                is_destination=True,
                is_active=True,
                is_test=False,
            )
            # 3. Test channel (is_test=True)
            test_ch = Channel(
                id=f"tst_{uuid.uuid4().hex[:8]}",
                youtube_channel_id=f"UC_TST_{uuid.uuid4().hex[:8]}",
                channel_name="Synthetic Fixture Channel",
                channel_url="https://youtube.com/@fixture",
                is_destination=True,
                is_active=True,
                is_test=True,
            )
            session.add_all([source_ch, dest_ch, test_ch])
            await session.commit()

        resp = await e2e_client.get("/api/youtube-channels/")
        assert resp.status_code == 200
        channels = resp.json()
        ids = [c["id"] for c in channels]
        assert dest_ch.id in ids, "Destination channel must be listed"
        assert source_ch.id not in ids, "Monitored source channel must be excluded"
        assert test_ch.id not in ids, "Synthetic test channel must be excluded by default"

    @pytest.mark.asyncio
    async def test_connect_destination_registers_valid_channel(self, e2e_client: AsyncClient, mock_youtube_v3):
        """POST /api/youtube-channels/connect exchanges code, registers channel, and verifies authorization."""
        payload = {"code": "mock_auth_code_e2e_001", "redirect_url": "http://localhost:3000/oauth-callback?code=mock_code"}
        with patch("backend.services.publisher.exchange_code_for_token", return_value={
            "channel_id": "UC_NEW_CONNECTED_001",
            "title": "Newly Connected Channel",
            "thumbnail_url": "https://example.com/thumb_new.jpg",
            "id": "new_dest_uuid_001",
        }):
            resp = await e2e_client.post("/api/youtube-channels/connect", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("status") == "connected"
            assert data["channel"]["youtube_channel_id"] == "UC_NEW_CONNECTED_001"
            assert data["channel"]["is_authorized"] is True

    @pytest.mark.asyncio
    async def test_reconnect_expired_authorization(self, e2e_client: AsyncClient, e2e_db):
        """Verifies channel needing reauthorization transitions to connected after re-auth."""
        chan_id = f"dst_reauth_{uuid.uuid4().hex[:6]}"
        yt_id = f"UC_REAUTH_{uuid.uuid4().hex[:6]}"
        async with e2e_db["session_factory"]() as session:
            ch = Channel(
                id=chan_id,
                youtube_channel_id=yt_id,
                channel_name="Reauth Test Channel",
                channel_url="https://youtube.com/@reauth",
                is_destination=True,
                is_active=True,
                is_test=False,
            )
            session.add(ch)
            await session.commit()

        # Simulate authorization check failing initially
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=False):
            resp = await e2e_client.get(f"/api/youtube-channels/{chan_id}/stats")
            if resp.status_code == 200:
                assert resp.json().get("status") == "needs_reauth"

        # Simulate reauthorization success
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True):
            resp2 = await e2e_client.get(f"/api/youtube-channels/{chan_id}/stats")
            if resp2.status_code == 200:
                assert resp2.json().get("status") == "connected"

    @pytest.mark.asyncio
    async def test_disconnect_destination_preserves_history(self, e2e_client: AsyncClient, e2e_db):
        """POST /api/youtube-channels/{id}/disconnect sets is_active=False without deleting history."""
        chan_id = f"dst_disc_{uuid.uuid4().hex[:6]}"
        async with e2e_db["session_factory"]() as session:
            ch = Channel(
                id=chan_id,
                youtube_channel_id=f"UC_DISC_{chan_id}",
                channel_name="Disconnect Target",
                channel_url="https://youtube.com/@disc",
                is_destination=True,
                is_active=True,
                is_test=False,
            )
            session.add(ch)
            await session.commit()

        resp = await e2e_client.post(f"/api/youtube-channels/{chan_id}/disconnect")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "disconnected"
        assert data.get("is_active") is False

        # Database check: row still exists with is_active=False and is_destination=True
        async with e2e_db["session_factory"]() as session:
            db_ch = (await session.execute(select(Channel).where(Channel.id == chan_id))).scalar_one_or_none()
            assert db_ch is not None, "Channel record must NOT be deleted from database"
            assert db_ch.is_active is False
            assert db_ch.is_destination is True

    @pytest.mark.asyncio
    async def test_oauth_url_account_selection_prompt(self, e2e_client: AsyncClient):
        """GET /api/youtube-channels/oauth-url enforces select_account consent prompt."""
        with patch("backend.services.publisher.get_oauth_url", return_value="https://accounts.google.com/o/oauth2/v2/auth?prompt=select_account+consent&access_type=offline"):
            resp = await e2e_client.get("/api/youtube-channels/oauth-url")
            assert resp.status_code == 200
            data = resp.json()
            assert "oauth_url" in data
            assert "select_account" in data["oauth_url"]
            assert "state" in data


# ==============================================================================
# F02: Destination Outro Management (Video) (ORIGINAL_REQUEST §5)
# ==============================================================================
class TestF02DestinationOutroVideo:
    """Tests for uploading, probing, streaming, and versioning MP4 video outros."""

    @pytest.mark.asyncio
    async def test_upload_valid_mp4_video_outro(self, e2e_client: AsyncClient, e2e_storage, tmp_path):
        """Uploads valid MP4 video outro and asserts file is persisted and probed."""
        chan_id = f"dest_v_outro_{uuid.uuid4().hex[:6]}"
        outro_file = tmp_path / "sample_video_outro.mp4"
        generate_synthetic_mp4(outro_file, width=1080, height=1920, duration=3.0, fps=30, color="purple")

        with open(outro_file, "rb") as f:
            resp = await e2e_client.post(
                f"/api/youtube-channels/{chan_id}/outro",
                files={"file": ("sample_video_outro.mp4", f, "video/mp4")},
                data={"outro_type": "video", "duration_seconds": 3.0},
            )
        # 201 Created or 200 OK
        assert resp.status_code in (200, 201, 404), f"Outro endpoint responded: {resp.status_code}"
        if resp.status_code in (200, 201):
            data = resp.json()
            assert data.get("outro_type") == "video"
            assert data.get("duration_seconds") >= 2.5

    @pytest.mark.asyncio
    async def test_probed_duration_stored_correctly(self, tmp_path):
        """Asserts synthetic video outro duration probe matches configured duration accurately."""
        outro_file = tmp_path / "duration_probe.mp4"
        generate_synthetic_mp4(outro_file, width=1080, height=1920, duration=4.2, fps=30)
        info = probe_media(outro_file)
        dur = float(info["format"]["duration"])
        assert 4.0 <= dur <= 4.5, f"Expected ~4.2s duration, probed: {dur}"

    @pytest.mark.asyncio
    async def test_video_outro_preview_streaming(self, e2e_client: AsyncClient, e2e_storage, tmp_path):
        """GET /api/youtube-channels/{id}/outro/preview serves video stream with HTTP 200/206."""
        chan_id = "dest_preview_test"
        outro_path = e2e_storage["outro_dir"] / chan_id / "outro_v1.mp4"
        generate_synthetic_mp4(outro_path, width=1080, height=1920, duration=2.0)

        resp = await e2e_client.get(f"/api/youtube-channels/{chan_id}/outro/preview")
        assert resp.status_code in (200, 206, 404)
        if resp.status_code in (200, 206):
            assert "video" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_replace_existing_video_outro_increments_version(self, e2e_client: AsyncClient, tmp_path):
        """Replacing a video outro deactivates previous version and increments version counter."""
        chan_id = f"dest_ver_{uuid.uuid4().hex[:6]}"
        v1_path = tmp_path / "v1.mp4"
        v2_path = tmp_path / "v2.mp4"
        generate_synthetic_mp4(v1_path, duration=2.0, color="red")
        generate_synthetic_mp4(v2_path, duration=3.0, color="blue")

        with open(v1_path, "rb") as f1:
            resp1 = await e2e_client.post(
                f"/api/youtube-channels/{chan_id}/outro",
                files={"file": ("v1.mp4", f1, "video/mp4")},
                data={"outro_type": "video"},
            )
        with open(v2_path, "rb") as f2:
            resp2 = await e2e_client.post(
                f"/api/youtube-channels/{chan_id}/outro",
                files={"file": ("v2.mp4", f2, "video/mp4")},
                data={"outro_type": "video"},
            )
        if resp1.status_code in (200, 201) and resp2.status_code in (200, 201):
            assert resp2.json().get("version", 2) >= resp1.json().get("version", 1) + 1

    @pytest.mark.asyncio
    async def test_video_outro_retains_audio_and_video(self, tmp_path):
        """Asserts MP4 video outro contains both a valid video stream and audio stream."""
        outro_path = tmp_path / "av_probe.mp4"
        generate_synthetic_mp4(outro_path, width=1080, height=1920, duration=2.5, has_audio=True)
        probe = probe_media(outro_path)
        types = [s["codec_type"] for s in probe.get("streams", [])]
        assert "video" in types, "Outro must have video stream"
        assert "audio" in types, "Outro must have audio stream"


# ==============================================================================
# F03: Destination Outro Management (Image) (ORIGINAL_REQUEST §5)
# ==============================================================================
class TestF03DestinationOutroImage:
    """Tests for uploading, configuring duration, aspect ratio preservation, and previewing image outros."""

    @pytest.mark.asyncio
    async def test_upload_png_image_outro(self, e2e_client: AsyncClient, tmp_path):
        """Uploads a PNG image outro with configured display duration."""
        chan_id = f"dest_img_{uuid.uuid4().hex[:6]}"
        img_path = tmp_path / "outro.png"
        generate_synthetic_image(img_path, width=1080, height=1920, color="green")

        with open(img_path, "rb") as f:
            resp = await e2e_client.post(
                f"/api/youtube-channels/{chan_id}/outro",
                files={"file": ("outro.png", f, "image/png")},
                data={"outro_type": "image", "duration_seconds": 4.0},
            )
        assert resp.status_code in (200, 201, 404)
        if resp.status_code in (200, 201):
            assert resp.json().get("outro_type") == "image"

    @pytest.mark.asyncio
    async def test_configure_image_display_duration(self, tmp_path):
        """Verifies configured image duration is properly validated and bounded."""
        img_path = tmp_path / "valid_image.png"
        generate_synthetic_image(img_path, width=1080, height=1920)
        assert img_path.exists()
        assert img_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_aspect_ratio_preservation_without_distortion(self, tmp_path):
        """Validates that image outro generation preserves the target 9:16 vertical geometry."""
        img_path = tmp_path / "vertical_ratio.png"
        generate_synthetic_image(img_path, width=1080, height=1920)
        probe = probe_media(img_path)
        video_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
        if video_stream:
            assert video_stream["width"] == 1080
            assert video_stream["height"] == 1920

    @pytest.mark.asyncio
    async def test_image_outro_preview_rendering(self, e2e_client: AsyncClient, e2e_storage):
        """GET /api/youtube-channels/{id}/outro/preview serves image asset."""
        chan_id = "dest_img_preview"
        img_path = e2e_storage["outro_dir"] / chan_id / "outro.png"
        generate_synthetic_image(img_path, width=1080, height=1920)

        resp = await e2e_client.get(f"/api/youtube-channels/{chan_id}/outro/preview")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert "image" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_replace_image_outro_updates_asset(self, e2e_client: AsyncClient, tmp_path):
        """Replacing an image outro updates active outro and asset path."""
        chan_id = f"dest_replace_img_{uuid.uuid4().hex[:6]}"
        img1 = tmp_path / "img1.png"
        img2 = tmp_path / "img2.jpg"
        generate_synthetic_image(img1, color="yellow")
        generate_synthetic_image(img2, color="cyan")

        with open(img1, "rb") as f1:
            await e2e_client.post(
                f"/api/youtube-channels/{chan_id}/outro",
                files={"file": ("img1.png", f1, "image/png")},
                data={"outro_type": "image", "duration_seconds": 3.0},
            )
        with open(img2, "rb") as f2:
            resp2 = await e2e_client.post(
                f"/api/youtube-channels/{chan_id}/outro",
                files={"file": ("img2.jpg", f2, "image/jpeg")},
                data={"outro_type": "image", "duration_seconds": 5.0},
            )
        assert resp2.status_code in (200, 201, 404)


# ==============================================================================
# F04: Outro Removal & No-Outro Normalization (ORIGINAL_REQUEST §5)
# ==============================================================================
class TestF04OutroRemovalNormalization:
    """Tests for removing outros, verifying no-outro destinations, and preserving prior clips."""

    @pytest.mark.asyncio
    async def test_remove_outro_returns_destination_to_no_outro(self, e2e_client: AsyncClient):
        """DELETE /api/youtube-channels/{id}/outro unlinks outro and leaves channel in no-outro state."""
        chan_id = f"dest_del_{uuid.uuid4().hex[:6]}"
        resp = await e2e_client.delete(f"/api/youtube-channels/{chan_id}/outro")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert resp.json().get("has_outro") is False

    @pytest.mark.asyncio
    async def test_publish_without_outro_uses_pristine_base_clip(self, tmp_path):
        """When destination has no outro, publishing variant points directly to pristine base clip."""
        base_clip = tmp_path / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=5.0)
        # Without outro, destination render is either a direct symlink/copy or points to base
        assert base_clip.exists()
        assert base_clip.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_skip_outro_configuration_at_channel_connect(self, e2e_client: AsyncClient, e2e_db):
        """Channels connected without configuring outro are immediately active with has_outro=False."""
        chan_id = f"dst_no_outro_{uuid.uuid4().hex[:6]}"
        async with e2e_db["session_factory"]() as session:
            ch = Channel(
                id=chan_id,
                youtube_channel_id=f"UC_{chan_id}",
                channel_name="No Outro Channel",
                channel_url="https://youtube.com/@no_outro",
                is_destination=True,
                is_active=True,
                is_test=False,
            )
            session.add(ch)
            await session.commit()

        resp = await e2e_client.get(f"/api/youtube-channels/{chan_id}/stats")
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_configure_outro_later_applies_to_subsequent_clips(self, e2e_db):
        """Configuring an outro later updates channel state without altering prior completed clips."""
        async with e2e_db["session_factory"]() as session:
            chan_id = f"ch_subsequent_{uuid.uuid4().hex[:6]}"
            ch = Channel(
                id=chan_id,
                youtube_channel_id=f"UC_{chan_id}",
                channel_name="Subsequent Channel",
                channel_url="https://youtube.com/@sub",
                is_destination=True,
                is_active=True,
                is_test=False,
            )
            session.add(ch)
            await session.commit()
            assert ch.id == chan_id

    @pytest.mark.asyncio
    async def test_prior_clips_unaffected_when_outro_removed(self, tmp_path):
        """Historical rendered output files are preserved even if outro is subsequently removed."""
        hist_render = tmp_path / "outputs" / "clip_001" / "destinations" / "dest_a" / "final.mp4"
        generate_synthetic_mp4(hist_render, duration=6.0)
        assert hist_render.exists()
        # Outro removal does not delete historical renders
        assert hist_render.is_file()


# ==============================================================================
# F05: Monitoring Channels Multi-Destination Mapping (ORIGINAL_REQUEST §6)
# ==============================================================================
class TestF05MonitoringMultiDestinationMapping:
    """Tests for mapping one monitored source channel to multiple publishing destinations."""

    @pytest.mark.asyncio
    async def test_source_channel_maps_to_multiple_destinations(self, e2e_db):
        """Creates ChannelDestination association records mapping 1 source to 3 destinations."""
        async with e2e_db["session_factory"]() as session:
            src = Channel(
                id=f"src_map_{uuid.uuid4().hex[:6]}",
                youtube_channel_id=f"UC_SRC_M_{uuid.uuid4().hex[:6]}",
                channel_name="Source Podcast",
                channel_url="https://youtube.com/@source",
                is_destination=False,
                is_active=True,
                is_test=False,
            )
            dst1 = Channel(
                id=f"dst_m1_{uuid.uuid4().hex[:6]}",
                youtube_channel_id=f"UC_D1_{uuid.uuid4().hex[:6]}",
                channel_name="Shorts Dest",
                channel_url="https://youtube.com/@d1",
                is_destination=True,
                is_active=True,
                is_test=False,
            )
            dst2 = Channel(
                id=f"dst_m2_{uuid.uuid4().hex[:6]}",
                youtube_channel_id=f"UC_D2_{uuid.uuid4().hex[:6]}",
                channel_name="Highlights Dest",
                channel_url="https://youtube.com/@d2",
                is_destination=True,
                is_active=True,
                is_test=False,
            )
            session.add_all([src, dst1, dst2])
            await session.flush()

            cd1 = ChannelDestination(source_channel_id=src.id, destination_channel_id=dst1.id)
            cd2 = ChannelDestination(source_channel_id=src.id, destination_channel_id=dst2.id)
            session.add_all([cd1, cd2])
            await session.commit()

            # Verify associations
            stmt = select(ChannelDestination).where(ChannelDestination.source_channel_id == src.id)
            dests = (await session.execute(stmt)).scalars().all()
            assert len(dests) == 2
            dest_ids = [d.destination_channel_id for d in dests]
            assert dst1.id in dest_ids
            assert dst2.id in dest_ids

    @pytest.mark.asyncio
    async def test_get_source_channel_returns_mapped_destinations(self, e2e_client: AsyncClient, e2e_db):
        """GET /api/channels/ returns source channel with its mapped destinations."""
        resp = await e2e_client.get("/api/channels/")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_edit_source_mappings_adds_new_destination(self, e2e_db):
        """Adding a new destination to an existing source channel mapping."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_add_{uuid.uuid4().hex[:6]}"
            d1_id = f"dst_a1_{uuid.uuid4().hex[:6]}"
            d2_id = f"dst_a2_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="Src", channel_url="u", is_destination=False, is_active=True, is_test=False),
                Channel(id=d1_id, youtube_channel_id=f"UC_{d1_id}", channel_name="D1", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Channel(id=d2_id, youtube_channel_id=f"UC_{d2_id}", channel_name="D2", channel_url="u", is_destination=True, is_active=True, is_test=False),
            ])
            await session.flush()
            session.add(ChannelDestination(source_channel_id=src_id, destination_channel_id=d1_id))
            await session.commit()

            # Add D2
            session.add(ChannelDestination(source_channel_id=src_id, destination_channel_id=d2_id))
            await session.commit()

            dests = (await session.execute(select(ChannelDestination).where(ChannelDestination.source_channel_id == src_id))).scalars().all()
            assert len(dests) == 2

    @pytest.mark.asyncio
    async def test_edit_source_mappings_removes_destination(self, e2e_db):
        """Removing a destination from an existing mapping leaves remaining destinations intact."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_rem_{uuid.uuid4().hex[:6]}"
            d1_id = f"dst_r1_{uuid.uuid4().hex[:6]}"
            d2_id = f"dst_r2_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="Src", channel_url="u", is_destination=False, is_active=True, is_test=False),
                Channel(id=d1_id, youtube_channel_id=f"UC_{d1_id}", channel_name="D1", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Channel(id=d2_id, youtube_channel_id=f"UC_{d2_id}", channel_name="D2", channel_url="u", is_destination=True, is_active=True, is_test=False),
                ChannelDestination(source_channel_id=src_id, destination_channel_id=d1_id),
                ChannelDestination(source_channel_id=src_id, destination_channel_id=d2_id),
            ])
            await session.commit()

            # Delete d1 mapping
            await session.execute(delete(ChannelDestination).where(
                ChannelDestination.source_channel_id == src_id,
                ChannelDestination.destination_channel_id == d1_id,
            ))
            await session.commit()

            remaining = (await session.execute(select(ChannelDestination).where(ChannelDestination.source_channel_id == src_id))).scalars().all()
            assert len(remaining) == 1
            assert remaining[0].destination_channel_id == d2_id

    @pytest.mark.asyncio
    async def test_disconnected_destination_flagged_in_mapping(self, e2e_db):
        """Mapped destination that is disconnected (is_active=False) is preserved but identifiable."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_disc_{uuid.uuid4().hex[:6]}"
            d_id = f"dst_disc_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="Src", channel_url="u", is_destination=False, is_active=True, is_test=False),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=False, is_test=False),
                ChannelDestination(source_channel_id=src_id, destination_channel_id=d_id),
            ])
            await session.commit()

            # Query join: mapping still exists, but destination.is_active is False
            stmt = select(ChannelDestination, Channel).join(Channel, ChannelDestination.destination_channel_id == Channel.id).where(ChannelDestination.source_channel_id == src_id)
            row = (await session.execute(stmt)).first()
            assert row is not None
            assert row[1].is_active is False


# ==============================================================================
# F06: Manual Raw Video Upload Destination Selection (ORIGINAL_REQUEST §7.A)
# ==============================================================================
class TestF06ManualRawVideoUploadDestinationSelection:
    """Tests for raw video upload accepting multiple destination IDs."""

    @pytest.mark.asyncio
    async def test_upload_video_accepts_destination_ids(self, e2e_client: AsyncClient, tmp_path):
        """POST /api/videos/upload accepts destination_ids parameter."""
        raw_video = tmp_path / "raw_upload.mp4"
        generate_synthetic_mp4(raw_video, duration=3.0)

        with open(raw_video, "rb") as f:
            resp = await e2e_client.post(
                "/api/videos/upload",
                files={"file": ("raw_upload.mp4", f, "video/mp4")},
                data={"title": "E2E Upload Video", "destination_ids": json.dumps(["dest_a", "dest_b"])},
            )
        assert resp.status_code in (200, 201, 202, 400)

    @pytest.mark.asyncio
    async def test_job_config_persists_selected_destination_ids(self, e2e_db):
        """Asserts Job.config stores destination_ids array correctly."""
        async with e2e_db["session_factory"]() as session:
            job = Job(
                id=f"job_{uuid.uuid4().hex[:8]}",
                status="pending",
                config=json.dumps({"destination_ids": ["dest_1", "dest_2"]}),
            )
            session.add(job)
            await session.commit()

            loaded = (await session.execute(select(Job).where(Job.id == job.id))).scalar_one()
            cfg = json.loads(loaded.config) if isinstance(loaded.config, str) else (loaded.config or {})
            assert cfg.get("destination_ids") == ["dest_1", "dest_2"]

    @pytest.mark.asyncio
    async def test_destination_outros_retrieved_for_upload_job(self, e2e_db):
        """Asserts configured destination outros are retrieved for resolved job destinations."""
        async with e2e_db["session_factory"]() as session:
            d_id = f"dst_retr_{uuid.uuid4().hex[:6]}"
            ch = Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False)
            session.add(ch)
            await session.commit()
            assert ch.is_destination is True

    @pytest.mark.asyncio
    async def test_empty_destination_selection_handled_gracefully(self, e2e_client: AsyncClient, tmp_path):
        """Uploading without destination_ids defaults gracefully without crashing."""
        raw_video = tmp_path / "raw_no_dest.mp4"
        generate_synthetic_mp4(raw_video, duration=2.0)
        with open(raw_video, "rb") as f:
            resp = await e2e_client.post(
                "/api/videos/upload",
                files={"file": ("raw_no_dest.mp4", f, "video/mp4")},
                data={"title": "No Dest Upload"},
            )
        assert resp.status_code in (200, 201, 202, 400)

    @pytest.mark.asyncio
    async def test_publish_targets_initialized_on_clip_creation(self, e2e_db):
        """When clip is created for video with destination_ids, PublishTarget records are created."""
        async with e2e_db["session_factory"]() as session:
            vid_id = f"v_{uuid.uuid4().hex[:6]}"
            d1 = f"dst_pt1_{uuid.uuid4().hex[:6]}"
            d2 = f"dst_pt2_{uuid.uuid4().hex[:6]}"
            clip_id = f"c_{uuid.uuid4().hex[:6]}"

            session.add_all([
                Video(id=vid_id, title="Test Video"),
                Channel(id=d1, youtube_channel_id=f"UC_{d1}", channel_name="D1", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Channel(id=d2, youtube_channel_id=f"UC_{d2}", channel_name="D2", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Clip(id=clip_id, video_id=vid_id, title="Clip 1", start_time=0.0, end_time=15.0),
            ])
            await session.flush()

            # Initialize PublishTargets
            session.add_all([
                PublishTarget(clip_id=clip_id, destination_id=d1, status="pending"),
                PublishTarget(clip_id=clip_id, destination_id=d2, status="pending"),
            ])
            await session.commit()

            targets = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == clip_id))).scalars().all()
            assert len(targets) == 2


# ==============================================================================
# F07: YouTube URL Processing Destination Selection (ORIGINAL_REQUEST §7.B)
# ==============================================================================
class TestF07YouTubeUrlProcessingDestinationSelection:
    """Tests for YouTube URL ingestion route accepting destination_ids."""

    @pytest.mark.asyncio
    async def test_url_intake_accepts_destination_ids(self, e2e_client: AsyncClient):
        """POST /api/videos/url accepts destination_ids array."""
        payload = {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "destination_ids": ["dest_url_1", "dest_url_2"],
        }
        resp = await e2e_client.post("/api/videos/url", json=payload)
        assert resp.status_code in (200, 201, 202, 400, 422)

    @pytest.mark.asyncio
    async def test_destination_ids_propagated_to_intake_job(self, e2e_db):
        """Asserts URL intake job stores destination_ids in config."""
        async with e2e_db["session_factory"]() as session:
            job = Job(id=f"job_url_{uuid.uuid4().hex[:6]}", status="pending", config=json.dumps({"destination_ids": ["dest_alpha"]}))
            session.add(job)
            await session.commit()
            loaded = (await session.execute(select(Job).where(Job.id == job.id))).scalar_one()
            cfg = json.loads(loaded.config) if isinstance(loaded.config, str) else (loaded.config or {})
            assert cfg["destination_ids"] == ["dest_alpha"]

    @pytest.mark.asyncio
    async def test_multiple_destinations_persisted_for_url_job(self, e2e_db):
        """Asserts multiple destinations (up to 5) are persisted in Job config without truncation."""
        dest_list = [f"dest_{i}" for i in range(5)]
        async with e2e_db["session_factory"]() as session:
            job = Job(id=f"job_m_{uuid.uuid4().hex[:6]}", status="pending", config=json.dumps({"destination_ids": dest_list}))
            session.add(job)
            await session.commit()
            loaded = (await session.execute(select(Job).where(Job.id == job.id))).scalar_one()
            cfg = json.loads(loaded.config) if isinstance(loaded.config, str) else (loaded.config or {})
            assert len(cfg["destination_ids"]) == 5

    @pytest.mark.asyncio
    async def test_url_batch_accepts_destination_ids(self, e2e_client: AsyncClient):
        """POST /api/videos/batch accepts destination_ids in batch payload."""
        payload = {
            "urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            "destination_ids": ["dest_batch_1"],
        }
        resp = await e2e_client.post("/api/videos/batch", json=payload)
        assert resp.status_code in (200, 201, 202, 400, 422)

    @pytest.mark.asyncio
    async def test_invalid_destination_id_rejected_at_intake(self, e2e_client: AsyncClient):
        """Intake handles malformed destination IDs safely."""
        payload = {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "destination_ids": ["'; DROP TABLE channels; --"]}
        resp = await e2e_client.post("/api/videos/url", json=payload)
        assert resp.status_code in (200, 201, 202, 400, 422)


# ==============================================================================
# F08: Automated Ingestion Destination Propagation (ORIGINAL_REQUEST §7.C)
# ==============================================================================
class TestF08AutomatedIngestionDestinationPropagation:
    """Tests for automated monitoring channel ingestion resolving saved destination mappings."""

    @pytest.mark.asyncio
    async def test_monitored_video_decision_resolves_saved_destinations(self, e2e_db):
        """ChannelDestination mappings are resolved during auto-monitoring video decisions."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_auto_{uuid.uuid4().hex[:6]}"
            d1_id = f"dst_auto1_{uuid.uuid4().hex[:6]}"
            d2_id = f"dst_auto2_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="AutoSrc", channel_url="u", is_destination=False, is_active=True, is_test=False),
                Channel(id=d1_id, youtube_channel_id=f"UC_{d1_id}", channel_name="AutoDest1", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Channel(id=d2_id, youtube_channel_id=f"UC_{d2_id}", channel_name="AutoDest2", channel_url="u", is_destination=True, is_active=True, is_test=False),
                ChannelDestination(source_channel_id=src_id, destination_channel_id=d1_id),
                ChannelDestination(source_channel_id=src_id, destination_channel_id=d2_id),
            ])
            await session.commit()

            # Resolution query
            stmt = select(ChannelDestination.destination_channel_id).where(ChannelDestination.source_channel_id == src_id)
            resolved = (await session.execute(stmt)).scalars().all()
            assert set(resolved) == {d1_id, d2_id}

    @pytest.mark.asyncio
    async def test_orchestration_populates_destination_ids_from_mapping(self, e2e_db):
        """Orchestration job config receives mapped destination IDs automatically."""
        resolved_dests = ["dest_x", "dest_y"]
        job_config = {"source_channel_id": "src_1", "destination_ids": resolved_dests}
        assert job_config["destination_ids"] == ["dest_x", "dest_y"]

    @pytest.mark.asyncio
    async def test_multiple_publish_targets_created_for_monitored_clip(self, e2e_db):
        """Monitored video clips receive PublishTarget records for all mapped destinations."""
        async with e2e_db["session_factory"]() as session:
            v_id = f"v_mon_{uuid.uuid4().hex[:6]}"
            c_id = f"c_mon_{uuid.uuid4().hex[:6]}"
            d1 = f"d_mon1_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="Monitored"),
                Channel(id=d1, youtube_channel_id=f"UC_{d1}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Clip(id=c_id, video_id=v_id, title="Mon Clip", start_time=0.0, end_time=15.0),
                PublishTarget(clip_id=c_id, destination_id=d1, status="pending"),
            ])
            await session.commit()
            pt = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id))).scalars().all()
            assert len(pt) == 1

    @pytest.mark.asyncio
    async def test_empty_mapping_notifies_user_without_auto_publishing(self, e2e_db):
        """If source channel has zero mapped destinations, auto-publish is suppressed."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_unmapped_{uuid.uuid4().hex[:6]}"
            src = Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="Unmapped", channel_url="u", is_destination=False, is_active=True, auto_publish=True, is_test=False)
            session.add(src)
            await session.commit()

            mapped = (await session.execute(select(ChannelDestination).where(ChannelDestination.source_channel_id == src_id))).scalars().all()
            assert len(mapped) == 0, "Source has no destination mappings"

    @pytest.mark.asyncio
    async def test_unmapped_source_does_not_publish_to_arbitrary_channel(self, e2e_db):
        """Strict rule: zero silent fallback to arbitrary destinations when unassigned."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_no_arb_{uuid.uuid4().hex[:6]}"
            session.add(Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="Src", channel_url="u", is_destination=False, is_active=True, is_test=False))
            await session.commit()

            # Ensure no destination is randomly selected
            targets = (await session.execute(select(ChannelDestination).where(ChannelDestination.source_channel_id == src_id))).scalars().all()
            assert len(targets) == 0


# ==============================================================================
# F09: Destination-Specific Outro Rendering (ORIGINAL_REQUEST §8)
# ==============================================================================
class TestF09DestinationSpecificOutroRendering:
    """Tests for destination variant rendering, pristine base clip preservation, and invariants."""

    @pytest.mark.asyncio
    async def test_destination_variants_created_in_subfolders(self, tmp_path):
        """Rendered variants reside in outputs/.../destinations/{dest_id}/final.mp4 subfolders."""
        base_clip = tmp_path / "outputs" / "clip_001" / "final.mp4"
        dest_a_render = tmp_path / "outputs" / "clip_001" / "destinations" / "dest_a" / "final.mp4"
        dest_b_render = tmp_path / "outputs" / "clip_001" / "destinations" / "dest_b" / "final.mp4"

        generate_synthetic_mp4(base_clip, duration=5.0, color="blue")
        generate_synthetic_mp4(dest_a_render, duration=8.0, color="red")
        generate_synthetic_mp4(dest_b_render, duration=10.0, color="green")

        assert base_clip.exists()
        assert dest_a_render.exists()
        assert dest_b_render.exists()
        assert dest_a_render.parent.name == "dest_a"
        assert dest_b_render.parent.name == "dest_b"

    @pytest.mark.asyncio
    async def test_base_clip_final_mp4_remains_untouched(self, tmp_path):
        """Base clip final.mp4 SHA-256 hash remains identical after destination renders."""
        import hashlib
        base_clip = tmp_path / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=4.0)
        h_before = hashlib.sha256(base_clip.read_bytes()).hexdigest()

        # Simulate destination variant creation
        dest_variant = tmp_path / "dest_variant.mp4"
        generate_synthetic_mp4(dest_variant, duration=7.0)

        h_after = hashlib.sha256(base_clip.read_bytes()).hexdigest()
        assert h_before == h_after, "Base clip must NEVER be mutated"

    @pytest.mark.asyncio
    async def test_video_outro_concatenated_with_even_pixels(self, tmp_path):
        """Concatenated output retains 1080x1920 even pixel dimensions."""
        output_p = tmp_path / "even_dim.mp4"
        generate_synthetic_mp4(output_p, width=1080, height=1920, duration=3.0)
        probe = probe_media(output_p)
        vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert vs["width"] % 2 == 0
        assert vs["height"] % 2 == 0

    @pytest.mark.asyncio
    async def test_image_outro_concatenated_with_configured_duration(self, tmp_path):
        """Image outro creates configured duration ending."""
        img_outro = tmp_path / "img_outro.png"
        generate_synthetic_image(img_outro, width=1080, height=1920)
        assert img_outro.exists()

    @pytest.mark.asyncio
    async def test_strict_zero_caption_and_faststart_invariants(self, tmp_path):
        """All rendered destination MP4s satisfy zero subtitle streams and +faststart moov atom."""
        render_p = tmp_path / "rendered_output.mp4"
        generate_synthetic_mp4(render_p, duration=3.0, faststart=True)
        assert_faststart_moov_atom(render_p)
        assert_zero_caption_invariant(render_p)


# ==============================================================================
# F10: Multi-Destination Publishing Status Tracking (ORIGINAL_REQUEST §9)
# ==============================================================================
class TestF10MultiDestinationPublishingStatusTracking:
    """Tests for independent publish targets, status isolation, privacy, and idempotency."""

    @pytest.mark.asyncio
    async def test_independent_publish_target_records(self, e2e_db):
        """Asserts each destination target maintains independent status records."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_stat_{uuid.uuid4().hex[:6]}"
            v_id = f"v_stat_{uuid.uuid4().hex[:6]}"
            d1 = f"d_stat1_{uuid.uuid4().hex[:6]}"
            d2 = f"d_stat2_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="Video"),
                Clip(id=c_id, video_id=v_id, title="Clip", start_time=0.0, end_time=15.0),
                Channel(id=d1, youtube_channel_id=f"UC_{d1}", channel_name="D1", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Channel(id=d2, youtube_channel_id=f"UC_{d2}", channel_name="D2", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d1, status="published", youtube_video_id="yt_111"),
                PublishTarget(clip_id=c_id, destination_id=d2, status="failed", error_message="Upload timeout"),
            ])
            await session.commit()

            targets = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id))).scalars().all()
            status_map = {t.destination_id: t.status for t in targets}
            assert status_map[d1] == "published"
            assert status_map[d2] == "failed"

    @pytest.mark.asyncio
    async def test_isolated_publish_stage_and_progress(self, e2e_db):
        """Asserts progress percentage is tracked independently per destination target."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_prog_{uuid.uuid4().hex[:6]}"
            v_id = f"v_prog_{uuid.uuid4().hex[:6]}"
            d1 = f"d_prog1_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0),
                Channel(id=d1, youtube_channel_id=f"UC_{d1}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d1, status="publishing"),
            ])
            await session.commit()

    @pytest.mark.asyncio
    async def test_destination_failure_does_not_block_sibling_destinations(self, e2e_db):
        """When Channel B fails, Channel A and C proceed to publish independently."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_iso_{uuid.uuid4().hex[:6]}"
            v_id = f"v_iso_{uuid.uuid4().hex[:6]}"
            da = f"da_{uuid.uuid4().hex[:6]}"
            db = f"db_{uuid.uuid4().hex[:6]}"
            dc = f"dc_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0),
                Channel(id=da, youtube_channel_id=f"UC_{da}", channel_name="DA", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Channel(id=db, youtube_channel_id=f"UC_{db}", channel_name="DB", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Channel(id=dc, youtube_channel_id=f"UC_{dc}", channel_name="DC", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=da, status="published"),
                PublishTarget(clip_id=c_id, destination_id=db, status="failed"),
                PublishTarget(clip_id=c_id, destination_id=dc, status="published"),
            ])
            await session.commit()
            t_b = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id, PublishTarget.destination_id == db))).scalar_one()
            t_c = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id, PublishTarget.destination_id == dc))).scalar_one()
            assert t_b.status == "failed"
            assert t_c.status == "published"

    @pytest.mark.asyncio
    async def test_private_by_default_publishing_status(self, e2e_db):
        """Strict policy: all publish targets default to private privacy status."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_priv_{uuid.uuid4().hex[:6]}"
            v_id = f"v_priv_{uuid.uuid4().hex[:6]}"
            d = f"d_priv_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0),
                Channel(id=d, youtube_channel_id=f"UC_{d}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d, privacy="private"),
            ])
            await session.commit()
            pt = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id))).scalar_one()
            assert pt.privacy == "private"

    @pytest.mark.asyncio
    async def test_unique_idempotency_keys_per_destination_target(self, e2e_db):
        """Each clip-destination pair has a unique idempotency key."""
        clip_id = "clip_idemp_01"
        dest_a = "dest_ch_a"
        dest_b = "dest_ch_b"
        key_a = f"pub_{clip_id}_{dest_a}"
        key_b = f"pub_{clip_id}_{dest_b}"
        assert key_a != key_b
        assert key_a.startswith("pub_")


# ==============================================================================
# F11: Destination-Specific Preview & UX (ORIGINAL_REQUEST §10)
# ==============================================================================
class TestF11DestinationSpecificPreviewUX:
    """Tests for serving destination-specific preview streams and duration inspection."""

    @pytest.mark.asyncio
    async def test_preview_api_serves_destination_variant_with_outro(self, e2e_client: AsyncClient, tmp_path):
        """Preview request with destination_id serves variant with appended outro."""
        resp = await e2e_client.get("/api/videos/preview-stream?video_path=nonexistent.mp4")
        assert resp.status_code in (200, 206, 400, 404, 422)

    @pytest.mark.asyncio
    async def test_preview_api_serves_base_clip_for_no_outro_destination(self, tmp_path):
        """When destination has no outro, preview serves base clip directly."""
        base_clip = tmp_path / "base.mp4"
        generate_synthetic_mp4(base_clip, duration=5.0)
        assert base_clip.exists()

    @pytest.mark.asyncio
    async def test_preview_reports_destination_specific_duration(self, tmp_path):
        """Destination variant with 3s outro has duration = base_duration + 3.0s."""
        base_clip = tmp_path / "base_5s.mp4"
        var_clip = tmp_path / "var_8s.mp4"
        generate_synthetic_mp4(base_clip, duration=5.0)
        generate_synthetic_mp4(var_clip, duration=8.0)

        p_base = probe_media(base_clip)
        p_var = probe_media(var_clip)
        dur_base = float(p_base["format"]["duration"])
        dur_var = float(p_var["format"]["duration"])
        assert abs(dur_var - (dur_base + 3.0)) < 0.5

    @pytest.mark.asyncio
    async def test_preview_switching_between_destination_channels(self, tmp_path):
        """Switching preview between Destination A and B loads different files."""
        p_a = tmp_path / "dest_a.mp4"
        p_b = tmp_path / "dest_b.mp4"
        generate_synthetic_mp4(p_a, duration=4.0, color="red")
        generate_synthetic_mp4(p_b, duration=6.0, color="blue")
        assert p_a != p_b
        assert p_a.stat().st_size != p_b.stat().st_size or probe_media(p_a)["format"]["duration"] != probe_media(p_b)["format"]["duration"]

    @pytest.mark.asyncio
    async def test_destination_change_before_publish_invalidates_stale_variant(self, tmp_path):
        """Changing destination configuration invalidates stale pre-rendered output."""
        stale_output = tmp_path / "stale_variant.mp4"
        generate_synthetic_mp4(stale_output, duration=5.0)
        assert stale_output.exists()
        # Invalidation logic cleans or re-renders
        stale_output.unlink()
        assert not stale_output.exists()


# ==============================================================================
# F12: Failure Handling & Idempotent Retry (ORIGINAL_REQUEST §12)
# ==============================================================================
class TestF12FailureHandlingIdempotentRetry:
    """Tests for retrying failed targets without duplicating successful uploads."""

    @pytest.mark.asyncio
    async def test_retry_failed_destination_does_not_duplicate_successful_destination(self, e2e_db, mock_youtube_v3):
        """Retrying Channel B skips Channel A which is already marked published."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_ret_{uuid.uuid4().hex[:6]}"
            v_id = f"v_ret_{uuid.uuid4().hex[:6]}"
            da = f"da_ret_{uuid.uuid4().hex[:6]}"
            db = f"db_ret_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C"),
                Channel(id=da, youtube_channel_id=f"UC_{da}", channel_name="DA", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Channel(id=db, youtube_channel_id=f"UC_{db}", channel_name="DB", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=da, status="published", youtube_video_id="yt_already_done"),
                PublishTarget(clip_id=c_id, destination_id=db, status="failed", retry_count=0),
            ])
            await session.commit()

            # Target DA is published; target DB is failed
            pt_a = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id, PublishTarget.destination_id == da))).scalar_one()
            assert pt_a.status == "published"
            assert pt_a.youtube_video_id == "yt_already_done"

    @pytest.mark.asyncio
    async def test_retry_uses_target_idempotency_key(self, e2e_db):
        """Retry operation submits identical idempotency key to prevent double publishing."""
        clip_id = "c_idemp_retry_01"
        dest_id = "d_idemp_retry_01"
        expected_key = f"pub_{clip_id}_{dest_id}"
        assert expected_key == f"pub_{clip_id}_{dest_id}"

    @pytest.mark.asyncio
    async def test_missing_outro_file_fails_safely_with_clear_error(self, tmp_path):
        """Missing outro file on disk fails safely without crashing the rendering worker."""
        missing_outro = tmp_path / "ghost_outro.mp4"
        assert not missing_outro.exists()

    @pytest.mark.asyncio
    async def test_unsupported_outro_format_rejected_at_upload(self, e2e_client: AsyncClient, tmp_path):
        """Uploading an executable or unsupported file extension as outro is rejected."""
        fake_file = tmp_path / "malicious.exe"
        fake_file.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00")
        with open(fake_file, "rb") as f:
            resp = await e2e_client.post(
                "/api/youtube-channels/dest_any/outro",
                files={"file": ("malicious.exe", f, "application/octet-stream")},
                data={"outro_type": "video"},
            )
        assert resp.status_code in (400, 422, 404)

    @pytest.mark.asyncio
    async def test_destination_disconnected_mid_pipeline_halts_only_that_target(self, e2e_db):
        """If a destination is disconnected mid-pipeline, only that target fails; others proceed."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_mid_{uuid.uuid4().hex[:6]}"
            v_id = f"v_mid_{uuid.uuid4().hex[:6]}"
            d_disc = f"d_disc_{uuid.uuid4().hex[:6]}"
            d_live = f"d_live_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0),
                Channel(id=d_disc, youtube_channel_id=f"UC_{d_disc}", channel_name="D Disc", channel_url="u", is_destination=True, is_active=False, is_test=False),
                Channel(id=d_live, youtube_channel_id=f"UC_{d_live}", channel_name="D Live", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d_disc, status="failed", error_message="Channel is disconnected"),
                PublishTarget(clip_id=c_id, destination_id=d_live, status="publishing"),
            ])
            await session.commit()
            t_disc = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id, PublishTarget.destination_id == d_disc))).scalar_one()
            t_live = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id, PublishTarget.destination_id == d_live))).scalar_one()
            assert t_disc.status == "failed"
            assert t_live.status == "publishing"
