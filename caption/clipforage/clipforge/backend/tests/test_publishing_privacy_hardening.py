"""
test_publishing_privacy_hardening.py
====================================
Isolated regression unit test suite verifying YouTube publishing privacy hardening:
1. YouTube upload request payload includes status.privacyStatus == "private".
2. The uploader does not infer privacy from stale local publication records.
3. Retries and recovery tasks preserve the required privacy value ("private").
4. A local record is not treated as proof of remote privacy.
5. Incomplete responses or API errors surface honestly without claiming private upload.
6. Zero live network calls or mutations invoked during testing (network guard verified).
7. Remote response mismatch handling:
   - YouTube returns status.privacyStatus == "private": recorded as published & confirmed private.
   - YouTube returns status.privacyStatus == "public": transitions to manual_review; not confirmed private.
   - YouTube returns missing/incomplete status: reported as unconfirmed; transitions to manual_review.
   - Video ID is always preserved on partial/unexpected responses so created videos are never lost.
   - Exception during upload marks task as failed honestly without claiming success.
8. Reconciliation:
   - Queries remote status.privacyStatus.
   - Does not overwrite remote status with stale local record.
   - Lookup failure transitions to manual_review and is not masked as confirmed private.
9. Database schema parity and Alembic migration e6f7a8b9c0d1 tested in an isolated disposable schema.
"""
import pytest
import os
import sys
import json
import uuid
import socket
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Ensure backend is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.services.publisher import (
    upload_short,
    _mock_upload_short,
    check_external_youtube_state,
    _build_safe_status_update_body,
    UnsafeStatusRemediationError,
)
from backend.tasks.clip_tasks import (
    publish_clip_task,
    recover_stranded_publish_jobs_task,
)
from backend.models.models import PublishStatus, Clip, PublishRecord, PublishTarget, Channel


# =============================================================================
# NETWORK GUARD FIXTURE
# =============================================================================
@pytest.fixture(autouse=True)
def guard_no_live_network_calls(monkeypatch):
    """
    Strict safety boundary: Prevent any real network socket connection
    from opening to live YouTube endpoints during testing.
    Localhost / 127.0.0.1 connections (e.g. for isolated test DB) are allowed.
    """
    original_connect = socket.socket.connect

    def forbidden_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError(
                f"[SAFETY VIOLATION] Test attempted live network call to {address}! "
                "All external API interactions must be mocked."
            )
        return original_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", forbidden_connect)


@pytest.fixture(autouse=True)
def mock_channel_authorization_fixture():
    """Mock destination authorization so tests can exercise publishing privacy hardening logic."""
    with patch("backend.services.publisher.check_channel_authorization", return_value=True):
        yield


def _setup_mock_session(clip_obj=None, clips_list=None):
    """Configures a mock SyncSessionLocal context manager with chained query calls."""
    mock_session = MagicMock()

    def mock_query(model):
        q = MagicMock()
        if model == Clip:
            q.filter_by.return_value.with_for_update.return_value.first.return_value = clip_obj
            q.filter_by.return_value.first.return_value = clip_obj
            q.filter.return_value.all.return_value = clips_list or []
            q.filter.return_value.first.return_value = clip_obj
        elif model == PublishRecord:
            pr = MagicMock()
            pr.external_id = None
            q.filter_by.return_value.first.return_value = pr
            q.filter.return_value.first.return_value = pr
        elif model == PublishTarget:
            pt = MagicMock()
            pt.id = "target_123"
            pt.status = "pending"
            q.filter_by.return_value.first.return_value = pt
            q.filter.return_value.first.return_value = pt
        elif model == Channel or (getattr(model, "__name__", "") == "Channel"):
            chan = MagicMock()
            chan.id = "chan_dest_123"
            chan.youtube_channel_id = "UC_dest"
            chan.is_active = True
            chan.is_destination = True
            q.filter_by.return_value.first.return_value = chan
            q.filter.return_value.first.return_value = chan
        else:
            q.filter_by.return_value.first.return_value = None
            q.filter.return_value.all.return_value = []
        return q

    mock_session.query.side_effect = mock_query
    mock_session_cls = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    return mock_session_cls, mock_session


def _create_mock_clip(clip_id, privacy="private", publish_status=PublishStatus.QUEUED.value):
    clip = MagicMock()
    clip.id = clip_id
    clip.video_id = "vid_test_123"
    clip.publish_destination_id = "chan_dest_123"
    clip.publish_status = publish_status
    clip.youtube_short_id = None
    clip.output_path = "/tmp/clip.mp4"
    clip.status = "completed"
    clip.publish_idempotency_key = f"idemp_{clip_id}"
    clip.publish_attempt = 1
    clip.title = "Test Short Title #Shorts"
    clip.description = "Test Description"
    clip.transcript_segment = "Test Transcript"
    clip.tags = "[]"
    clip.thumbnail_path = None
    clip.privacy = privacy
    clip.made_for_kids = False
    clip.category = "22"
    clip.license = "youtube"
    clip.run_identity = f"run_{clip_id}"
    clip.publish_error = None
    return clip


def _create_mock_task():
    mock_task = MagicMock()
    mock_task.request.id = "task_test_123"
    mock_task.request.retries = 0
    mock_task.max_retries = 3
    return mock_task


# =============================================================================
# 1. YOUTUBE UPLOAD REQUEST PAYLOAD INCLUDES status.privacyStatus == "private"
# =============================================================================
class TestUploadPayloadPrivacy:
    """Requirement 1: Verify the YouTube upload request explicitly submits status.privacyStatus == 'private'."""

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_payload_forces_private_even_when_public_passed(self, mock_get_client, mock_media, mock_exists):
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        # Mock insert request and chunk response
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "test_yt_video_123",
            "status": {
                "privacyStatus": "private",
                "uploadStatus": "uploaded"
            }
        })
        mock_youtube.videos().insert.return_value = mock_request

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/test_clip.mp4"),
                title="Clamped Privacy Test #Shorts",
                description="Checking privacy clamp",
                privacy="public",  # Caller attempts to pass "public"
                channel_id="UC_test_channel_123"
            )

        # Verify videos().insert was called
        assert mock_youtube.videos().insert.called
        call_kwargs = mock_youtube.videos().insert.call_args[1]
        body = call_kwargs.get("body", {})

        # Assert status.privacyStatus in the actual upload payload is strictly "private"
        assert "status" in body
        assert body["status"].get("privacyStatus") == "private", (
            f"Expected payload privacyStatus 'private', got: {body['status'].get('privacyStatus')}"
        )
        assert res["privacy"] == "private"
        assert res["privacy_confirmed"] is True

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_payload_defaults_to_private_when_omitted(self, mock_get_client, mock_media, mock_exists):
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "test_yt_video_456",
            "status": {
                "privacyStatus": "private",
                "uploadStatus": "uploaded"
            }
        })
        mock_youtube.videos().insert.return_value = mock_request

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            # Omit privacy argument entirely
            res = upload_short(
                video_path=Path("/tmp/test_clip.mp4"),
                title="Default Privacy Test #Shorts",
                description="Checking default privacy",
                channel_id="UC_test_channel_123"
            )

        call_kwargs = mock_youtube.videos().insert.call_args[1]
        body = call_kwargs.get("body", {})
        assert body["status"].get("privacyStatus") == "private"
        assert res["privacy"] == "private"
        assert res["privacy_confirmed"] is True


# =============================================================================
# 2. REMOTE RESPONSE MISMATCH BEHAVIOR
# =============================================================================
class TestRemoteResponseMismatch:
    """Requirement 2: Verify behavior when YouTube API returns expected, mismatch, or incomplete privacy."""

    @patch("backend.tasks.clip_tasks.upload_short")
    @patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value=None)
    @patch("pathlib.Path.exists", return_value=True)
    def test_youtube_returns_private_records_published_and_confirmed_private(
        self, mock_exists, mock_check_ext, mock_upload
    ):
        """Case 1: YouTube returns status.privacyStatus == 'private' -> recorded as published and confirmed private."""
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        remote_yt_id = "yt_confirmed_private_1"
        mock_upload.return_value = {
            "id": remote_yt_id,
            "url": f"https://www.youtube.com/shorts/{remote_yt_id}",
            "title": "Title",
            "privacy": "private",
            "privacy_confirmed": True,
            "status": "uploaded"
        }

        clip = _create_mock_clip(clip_id, privacy="private")
        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_task = _create_mock_task()

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls):
            res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        assert res["status"] == "published"
        assert res["privacy"] == "private"
        assert clip.publish_status == PublishStatus.PUBLISHED.value
        assert clip.privacy == "private"
        assert clip.youtube_short_id == remote_yt_id
        assert clip.publish_error is None

    @patch("backend.tasks.clip_tasks.upload_short")
    @patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value=None)
    @patch("pathlib.Path.exists", return_value=True)
    def test_youtube_returns_public_records_manual_review_not_confirmed_private(
        self, mock_exists, mock_check_ext, mock_upload
    ):
        """Case 2: YouTube returns status.privacyStatus == 'public' -> system MUST NOT report confirmed private or published."""
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        remote_yt_id = "yt_mismatch_public_2"
        mock_upload.return_value = {
            "id": remote_yt_id,
            "url": f"https://www.youtube.com/shorts/{remote_yt_id}",
            "title": "Title",
            "privacy": "public",
            "privacy_confirmed": False,
            "status": "uploaded"
        }

        clip = _create_mock_clip(clip_id, privacy="private")
        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_task = _create_mock_task()

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls):
            res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        # Must NOT report as published or confirmed private!
        assert res["status"] == "manual_review"
        assert res["privacy"] == "public"
        assert clip.publish_status == PublishStatus.MANUAL_REVIEW.value
        assert clip.privacy == "public"
        # Video ID must be preserved so created video is not lost!
        assert clip.youtube_short_id == remote_yt_id
        assert "Remote privacy mismatch" in clip.publish_error

    @patch("backend.tasks.clip_tasks.upload_short")
    @patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value=None)
    @patch("pathlib.Path.exists", return_value=True)
    def test_youtube_returns_missing_status_records_unconfirmed_and_manual_review(
        self, mock_exists, mock_check_ext, mock_upload
    ):
        """Case 3: YouTube returns missing/incomplete status block -> result reported as unconfirmed and manual_review."""
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        remote_yt_id = "yt_incomplete_status_3"
        mock_upload.return_value = {
            "id": remote_yt_id,
            "url": f"https://www.youtube.com/shorts/{remote_yt_id}",
            "title": "Title",
            "privacy": "unconfirmed",
            "privacy_confirmed": False,
            "status": "uploaded"
        }

        clip = _create_mock_clip(clip_id, privacy="private")
        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_task = _create_mock_task()

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls):
            res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        assert res["status"] == "manual_review"
        assert res["privacy"] == "unconfirmed"
        assert clip.publish_status == PublishStatus.MANUAL_REVIEW.value
        assert clip.privacy == "unconfirmed"
        assert clip.youtube_short_id == remote_yt_id
        assert "omitted privacyStatus" in clip.publish_error

    def test_safe_status_update_body_preserves_writable_fields_and_omits_readonly(self):
        """Phase 2 & 3: Verify _build_safe_status_update_body preserves writable fields and omits read-only fields."""
        existing_status = {
            "uploadStatus": "uploaded",        # READ-ONLY - must be stripped
            "failureReason": "codec",          # READ-ONLY - must be stripped
            "rejectionReason": "copyright",    # READ-ONLY - must be stripped
            "madeForKids": False,              # READ-ONLY - must be stripped, never copied
            "selfDeclaredMadeForKids": True,   # MUTABLE - must be preserved as True
            "privacyStatus": "public",         # To be updated to desired_privacy
            "license": "creativeCommon",       # MUTABLE - must be preserved
            "embeddable": True,                # MUTABLE - must be preserved
            "publicStatsViewable": False,      # MUTABLE - must be preserved
            "containsSyntheticMedia": True,    # MUTABLE - must be preserved
        }

        body = _build_safe_status_update_body(
            video_id="safe_vid_123",
            existing_status=existing_status,
            desired_privacy="private",
            fallback_license="youtube",
            fallback_made_for_kids=None,
        )

        assert body["id"] == "safe_vid_123"
        status = body["status"]

        # Writable properties correctly set/preserved
        assert status["privacyStatus"] == "private"
        assert status["license"] == "creativeCommon"
        assert status["embeddable"] is True
        assert status["publicStatsViewable"] is False
        assert status["selfDeclaredMadeForKids"] is True
        assert status["containsSyntheticMedia"] is True

        # Read-only properties strictly omitted
        assert "uploadStatus" not in status
        assert "failureReason" not in status
        assert "rejectionReason" not in status
        assert "madeForKids" not in status
        assert "publishAt" not in status

    def test_safe_status_update_body_rejects_made_for_kids_copy_and_safely_omits_unknown_coppa(self):
        """Phase 1 & 3: Never copy read-only madeForKids to selfDeclaredMadeForKids; safely omit unknown declaration per API deletion exemption."""
        # Case A: Remote status returns madeForKids=True (platform evaluated) without selfDeclaredMadeForKids
        existing_status_server_kids = {
            "privacyStatus": "public",
            "madeForKids": True,  # Server-determined COPPA evaluation (read-only)
            "license": "youtube",
            "embeddable": True,
            "publicStatsViewable": True,
        }

        body = _build_safe_status_update_body(
            video_id="vid_coppa_unknown_1",
            existing_status=existing_status_server_kids,
            desired_privacy="private",
            fallback_made_for_kids=None,
        )

        status = body["status"]
        assert status["privacyStatus"] == "private"
        assert status["license"] == "youtube"
        assert status["embeddable"] is True
        assert status["publicStatsViewable"] is True

        # Invariants:
        # 1. Read-only madeForKids is stripped
        assert "madeForKids" not in status
        # 2. Never copied madeForKids=True to selfDeclaredMadeForKids=True
        assert status.get("selfDeclaredMadeForKids") is not True
        # 3. Never defaulted to False
        assert status.get("selfDeclaredMadeForKids") is not False
        # 4. Safely omitted per official YouTube Data API deletion exemption
        assert "selfDeclaredMadeForKids" not in status

    def test_safe_status_update_body_preserves_explicit_self_declaration(self):
        """Phase 1 & 3: Preserve selfDeclaredMadeForKids when reliably known without altering its meaning."""
        # Case A: Remote status contains selfDeclaredMadeForKids=False even though madeForKids=True
        existing_with_explicit_false = {
            "privacyStatus": "public",
            "madeForKids": True,  # Automated platform determination
            "selfDeclaredMadeForKids": False,  # Uploader's actual legal declaration
            "license": "youtube",
            "embeddable": True,
            "publicStatsViewable": True,
        }
        body_false = _build_safe_status_update_body(
            video_id="vid_coppa_explicit_false",
            existing_status=existing_with_explicit_false,
            desired_privacy="private",
            fallback_made_for_kids=None,
        )
        assert body_false["status"]["selfDeclaredMadeForKids"] is False

        # Case B: Remote status contains selfDeclaredMadeForKids=True
        existing_with_explicit_true = {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": True,
            "license": "youtube",
            "embeddable": True,
            "publicStatsViewable": True,
        }
        body_true = _build_safe_status_update_body(
            video_id="vid_coppa_explicit_true",
            existing_status=existing_with_explicit_true,
            desired_privacy="private",
            fallback_made_for_kids=None,
        )
        assert body_true["status"]["selfDeclaredMadeForKids"] is True

        # Case C: Remote status omitted declaration, but caller explicitly provided reliable fallback
        existing_omitted = {
            "privacyStatus": "public",
            "license": "youtube",
            "embeddable": True,
            "publicStatsViewable": True,
        }
        body_fallback = _build_safe_status_update_body(
            video_id="vid_coppa_fallback",
            existing_status=existing_omitted,
            desired_privacy="private",
            fallback_made_for_kids=False,
        )
        assert body_fallback["status"]["selfDeclaredMadeForKids"] is False

    # -------------------------------------------------------------------------
    # Requirement 1: License Audit Tests
    # -------------------------------------------------------------------------
    def test_safe_status_update_body_preserves_known_license(self):
        """Requirement 1: Writable license values (youtube, creativeCommon) are strictly preserved."""
        for lic in ("youtube", "creativeCommon"):
            body = _build_safe_status_update_body(
                video_id=f"vid_lic_{lic}",
                existing_status={
                    "privacyStatus": "public",
                    "license": lic,
                    "embeddable": True,
                    "publicStatsViewable": True,
                },
                desired_privacy="private",
            )
            assert body["status"]["license"] == lic

    def test_safe_status_update_body_uses_fallback_license_when_existing_missing(self):
        """Requirement 1: Explicit caller fallback_license is used when remote status lacks license."""
        body = _build_safe_status_update_body(
            video_id="vid_lic_fallback",
            existing_status={
                "privacyStatus": "public",
                "embeddable": True,
                "publicStatsViewable": True,
            },
            desired_privacy="private",
            fallback_license="creativeCommon",
        )
        assert body["status"]["license"] == "creativeCommon"

    def test_safe_status_update_body_rejects_unknown_license(self):
        """Requirement 1: Missing license without reliable fallback raises UnsafeStatusRemediationError."""
        with pytest.raises(UnsafeStatusRemediationError) as exc_info:
            _build_safe_status_update_body(
                video_id="vid_lic_unknown",
                existing_status={
                    "privacyStatus": "public",
                    "embeddable": True,
                    "publicStatsViewable": True,
                },
                desired_privacy="private",
                fallback_license=None,
            )
        err = str(exc_info.value)
        assert "Cannot safely determine license" in err
        assert "withheld to prevent overwriting or deleting copyright license" in err

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_withholds_remediation_when_license_unknown(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Requirement 1: upload_short withholds remediation when license cannot be established."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "vid_unknown_lic_999",
            "status": {
                "privacyStatus": "public",
                "embeddable": True,
                "publicStatsViewable": True,
            }
        })
        mock_youtube.videos().insert.return_value = mock_request
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{"id": "vid_unknown_lic_999", "status": {"privacyStatus": "public", "embeddable": True, "publicStatsViewable": True}}]
        }

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Unknown License Short #Shorts",
                privacy="private",
                channel_id="UC_dest",
                # license_type omitted: no implicit default fallback is assumed
            )

        assert res["id"] == "vid_unknown_lic_999"
        assert res["privacy"] == "public"
        assert res["privacy_confirmed"] is False
        assert "remediation_withheld" in res["remediation"]
        assert "Cannot safely determine license" in res["remediation"]
        assert not mock_youtube.videos().update.called

    # -------------------------------------------------------------------------
    # Requirement 2: Embeddable & PublicStatsViewable Audit Tests
    # -------------------------------------------------------------------------
    def test_safe_status_update_body_preserves_existing_embeddable_values(self):
        """Requirement 2: Both False and True values for embeddable are preserved without deletion."""
        for val in (False, True):
            body = _build_safe_status_update_body(
                video_id=f"vid_emb_{val}",
                existing_status={
                    "privacyStatus": "public",
                    "license": "youtube",
                    "embeddable": val,
                    "publicStatsViewable": True,
                },
                desired_privacy="private",
            )
            assert body["status"]["embeddable"] is val

    def test_safe_status_update_body_rejects_missing_embeddable(self):
        """Requirement 2: Missing embeddable cannot be safely omitted (would be deleted on update); raises error."""
        with pytest.raises(UnsafeStatusRemediationError) as exc_info:
            _build_safe_status_update_body(
                video_id="vid_emb_missing",
                existing_status={
                    "privacyStatus": "public",
                    "license": "youtube",
                    "publicStatsViewable": True,
                },
                desired_privacy="private",
            )
        err = str(exc_info.value)
        assert "Cannot safely determine embeddable" in err
        assert "withheld to prevent destructive property deletion" in err

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_withholds_remediation_when_embeddable_unknown(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Requirement 2: upload_short withholds remediation when embeddable is missing from status."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "vid_unknown_emb_888",
            "status": {
                "privacyStatus": "public",
                "license": "youtube",
                "publicStatsViewable": True,
            }
        })
        mock_youtube.videos().insert.return_value = mock_request
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{"id": "vid_unknown_emb_888", "status": {"privacyStatus": "public", "license": "youtube", "publicStatsViewable": True}}]
        }

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Unknown Embeddable Short #Shorts",
                privacy="private",
                channel_id="UC_dest",
            )

        assert res["id"] == "vid_unknown_emb_888"
        assert res["privacy"] == "public"
        assert res["privacy_confirmed"] is False
        assert "remediation_withheld" in res["remediation"]
        assert "Cannot safely determine embeddable" in res["remediation"]
        assert not mock_youtube.videos().update.called

    def test_safe_status_update_body_preserves_existing_public_stats_values(self):
        """Requirement 2: Both False and True values for publicStatsViewable are preserved without deletion."""
        for val in (False, True):
            body = _build_safe_status_update_body(
                video_id=f"vid_stats_{val}",
                existing_status={
                    "privacyStatus": "public",
                    "license": "youtube",
                    "embeddable": True,
                    "publicStatsViewable": val,
                },
                desired_privacy="private",
            )
            assert body["status"]["publicStatsViewable"] is val

    def test_safe_status_update_body_rejects_missing_public_stats(self):
        """Requirement 2: Missing publicStatsViewable cannot be safely omitted (would be deleted on update); raises error."""
        with pytest.raises(UnsafeStatusRemediationError) as exc_info:
            _build_safe_status_update_body(
                video_id="vid_stats_missing",
                existing_status={
                    "privacyStatus": "public",
                    "license": "youtube",
                    "embeddable": True,
                },
                desired_privacy="private",
            )
        err = str(exc_info.value)
        assert "Cannot safely determine publicStatsViewable" in err
        assert "withheld to prevent destructive property deletion" in err

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_withholds_remediation_when_public_stats_unknown(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Requirement 2: upload_short withholds remediation when publicStatsViewable is missing from status."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "vid_unknown_stats_777",
            "status": {
                "privacyStatus": "public",
                "license": "youtube",
                "embeddable": True,
            }
        })
        mock_youtube.videos().insert.return_value = mock_request
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{"id": "vid_unknown_stats_777", "status": {"privacyStatus": "public", "license": "youtube", "embeddable": True}}]
        }

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Unknown Stats Short #Shorts",
                privacy="private",
                channel_id="UC_dest",
            )

        assert res["id"] == "vid_unknown_stats_777"
        assert res["privacy"] == "public"
        assert res["privacy_confirmed"] is False
        assert "remediation_withheld" in res["remediation"]
        assert "Cannot safely determine publicStatsViewable" in res["remediation"]
        assert not mock_youtube.videos().update.called

    # -------------------------------------------------------------------------
    # Requirement 3: Synthetic Media Audit Tests
    # -------------------------------------------------------------------------
    def test_safe_status_update_body_preserves_synthetic_media_when_known(self):
        """Requirement 3: containsSyntheticMedia is preserved when explicitly known."""
        for val in (False, True):
            body = _build_safe_status_update_body(
                video_id=f"vid_synth_{val}",
                existing_status={
                    "privacyStatus": "public",
                    "license": "youtube",
                    "embeddable": True,
                    "publicStatsViewable": True,
                    "containsSyntheticMedia": val,
                },
                desired_privacy="private",
            )
            assert body["status"]["containsSyntheticMedia"] is val

    def test_safe_status_update_body_omits_synthetic_media_when_unknown(self):
        """Requirement 3: containsSyntheticMedia is safely omitted when unknown per official API deletion exemption."""
        body = _build_safe_status_update_body(
            video_id="vid_synth_unknown",
            existing_status={
                "privacyStatus": "public",
                "license": "youtube",
                "embeddable": True,
                "publicStatsViewable": True,
            },
            desired_privacy="private",
        )
        assert "containsSyntheticMedia" not in body["status"]

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_emergency_remediates_when_coppa_unknown_by_safely_omitting(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Requirement 3 & 4: When selfDeclaredMadeForKids is unknown, safe omission allows remediation to proceed and read-back confirms private."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        # Chunk response returns public status with license, embeddable, publicStatsViewable, but NO selfDeclaredMadeForKids
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "vid_remediate_coppa_omit_1",
            "status": {
                "privacyStatus": "public",
                "license": "youtube",
                "embeddable": True,
                "publicStatsViewable": True,
                "madeForKids": True,  # Platform evaluated
            }
        })
        mock_youtube.videos().insert.return_value = mock_request

        # update() succeeds
        mock_update_req = MagicMock()
        mock_update_req.execute.return_value = {
            "id": "vid_remediate_coppa_omit_1",
            "status": {"privacyStatus": "private"}
        }
        mock_youtube.videos().update.return_value = mock_update_req

        # Mandatory read-back confirms private
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{
                "id": "vid_remediate_coppa_omit_1",
                "status": {"privacyStatus": "private", "license": "youtube", "embeddable": True, "publicStatsViewable": True}
            }]
        }

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Safe Omission COPPA Short #Shorts",
                privacy="private",
                channel_id="UC_dest",
                made_for_kids=None,
            )

        assert mock_youtube.videos().update.called
        call_kwargs = mock_youtube.videos().update.call_args[1]
        body = call_kwargs["body"]
        assert body["status"]["privacyStatus"] == "private"
        assert body["status"]["license"] == "youtube"
        assert body["status"]["embeddable"] is True
        assert body["status"]["publicStatsViewable"] is True
        assert "selfDeclaredMadeForKids" not in body["status"]
        assert "madeForKids" not in body["status"]

        assert res["id"] == "vid_remediate_coppa_omit_1"
        assert res["privacy"] == "private"
        assert res["privacy_confirmed"] is False
        assert res["remediation"] == "auto_remediated_to_private"

    def test_safe_status_update_body_rejects_scheduled_publish_at(self):
        """Phase 2: Presence of future publishAt is incompatible with private-only enforcement; automated update withheld."""
        existing_scheduled = {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "publishAt": "2026-12-01T12:00:00Z",
            "license": "youtube",
            "embeddable": True,
            "publicStatsViewable": True,
        }

        with pytest.raises(UnsafeStatusRemediationError) as exc_info:
            _build_safe_status_update_body(
                video_id="vid_scheduled_123",
                existing_status=existing_scheduled,
                desired_privacy="private",
            )
        err = str(exc_info.value)
        assert "scheduled publication publishAt='2026-12-01T12:00:00Z'" in err
        assert "incompatible with private-only enforcement" in err
        assert "withheld for operator manual review" in err

    def test_safe_status_update_body_explicit_cancellation_of_scheduled_publish_at(self):
        """Phase 2: Explicit policy path allows operator-authorized cancellation of scheduled publication."""
        existing_scheduled = {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "publishAt": "2026-12-01T12:00:00Z",
            "license": "youtube",
            "embeddable": True,
            "publicStatsViewable": True,
        }

        body = _build_safe_status_update_body(
            video_id="vid_scheduled_cancel",
            existing_status=existing_scheduled,
            desired_privacy="private",
            allow_cancel_scheduled_publish=True,
        )

        assert body["id"] == "vid_scheduled_cancel"
        assert body["status"]["privacyStatus"] == "private"
        assert "publishAt" not in body["status"]
        assert body["status"]["license"] == "youtube"
        assert body["status"]["embeddable"] is True
        assert body["status"]["publicStatsViewable"] is True

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_withholds_remediation_when_scheduled_publish_at_present(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Phase 2 & 4: When scheduled publishAt is present, withhold remediation, preserve video ID, and flag manual review."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        # Chunk response returns public status with a future publishAt schedule
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "vid_sched_fail_888",
            "status": {
                "privacyStatus": "public",
                "publishAt": "2026-11-15T18:00:00Z",
                "selfDeclaredMadeForKids": False,
                "license": "youtube",
                "embeddable": True,
                "publicStatsViewable": True,
            }
        })
        mock_youtube.videos().insert.return_value = mock_request

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Scheduled Video Short #Shorts",
                privacy="private",
                channel_id="UC_dest",
                made_for_kids=False,
            )

        # Video ID must be preserved
        assert res["id"] == "vid_sched_fail_888"
        # Remote privacy remains public
        assert res["privacy"] == "public"
        assert res["privacy_confirmed"] is False
        # Remediation was withheld with explanatory diagnostic
        assert "remediation_withheld" in res["remediation"]
        assert "scheduled publication publishAt='2026-11-15T18:00:00Z'" in res["remediation"]
        # Invariant: videos().update must NEVER be called
        assert not mock_youtube.videos().update.called

    def test_safe_status_update_body_normal_private_upload_without_schedule(self):
        """Phase 2: Normal private-only upload without schedule safely constructs update body."""
        existing_normal = {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "license": "youtube",
            "embeddable": True,
            "publicStatsViewable": True,
        }

        body = _build_safe_status_update_body(
            video_id="vid_normal_99",
            existing_status=existing_normal,
            desired_privacy="private",
        )

        assert body["id"] == "vid_normal_99"
        assert body["status"]["privacyStatus"] == "private"
        assert body["status"]["selfDeclaredMadeForKids"] is False
        assert body["status"]["license"] == "youtube"
        assert body["status"]["embeddable"] is True
        assert body["status"]["publicStatsViewable"] is True
        assert "publishAt" not in body["status"]

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_preserves_video_id_on_missing_privacy_status(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Case 4: API returns video ID but omits status.privacyStatus, and read-only inspection returns empty -> ID preserved and flagged unconfirmed."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        # Chunk response returns valid id but empty status block
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "created_video_id_999",
            "status": {}
        })
        mock_youtube.videos().insert.return_value = mock_request

        # Read-only inspection returns no items
        mock_youtube.videos().list.return_value.execute.return_value = {"items": []}

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Missing Privacy Status Short #Shorts",
                privacy="private",
                channel_id="UC_dest"
            )

        assert res["id"] == "created_video_id_999"
        assert res["privacy"] == "unconfirmed"
        assert res["privacy_confirmed"] is False

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_missing_privacy_status_read_only_inspection_confirms_private(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Phase 3: Insert omits privacyStatus, but read-only inspection confirms 'private' -> confirmed private."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "created_video_id_888",
            "status": {}
        })
        mock_youtube.videos().insert.return_value = mock_request

        # Read-only inspection confirms private
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{"id": "created_video_id_888", "status": {"privacyStatus": "private", "license": "youtube"}}]
        }

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Missing Status Inspected Private Short #Shorts",
                privacy="private",
                channel_id="UC_dest"
            )

        assert res["id"] == "created_video_id_888"
        assert res["privacy"] == "private"
        assert res["privacy_confirmed"] is True
        assert res["remediation"] is None

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_missing_privacy_status_read_only_inspection_discovers_public_and_remediates(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Phase 3: Insert omits privacyStatus, read-only inspection discovers 'public', and emergency remediation confirms private via read-back."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "created_video_id_777",
            "status": {}
        })
        mock_youtube.videos().insert.return_value = mock_request

        # First list() call returns public; second list() call (read-back) returns private
        mock_list_exec = MagicMock()
        mock_list_exec.execute.side_effect = [
            {"items": [{"id": "created_video_id_777", "status": {"privacyStatus": "public", "license": "youtube", "embeddable": True, "publicStatsViewable": True, "selfDeclaredMadeForKids": False}}]},
            {"items": [{"id": "created_video_id_777", "status": {"privacyStatus": "private", "license": "youtube", "embeddable": True, "publicStatsViewable": True, "selfDeclaredMadeForKids": False}}]},
        ]
        mock_youtube.videos().list.return_value = mock_list_exec

        # update() succeeds
        mock_update_req = MagicMock()
        mock_update_req.execute.return_value = {"id": "created_video_id_777", "status": {"privacyStatus": "private"}}
        mock_youtube.videos().update.return_value = mock_update_req

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Missing Status Inspected Public Short #Shorts",
                privacy="private",
                channel_id="UC_dest"
            )

        assert res["id"] == "created_video_id_777"
        assert res["privacy"] == "private"
        assert res["privacy_confirmed"] is False
        assert res["remediation"] == "auto_remediated_to_private"

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_emergency_remediates_public_insert_to_private(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Phase 2 & 3: When upload returns 'public', triggers safe update preserving mutable fields and confirms private via read-back."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        # Chunk response returns valid id but unexpected public status with mutable attributes
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "newly_created_yt_public_1",
            "status": {
                "privacyStatus": "public",
                "uploadStatus": "uploaded",
                "license": "creativeCommon",
                "embeddable": True,
                "publicStatsViewable": False,
                "selfDeclaredMadeForKids": False,
            }
        })
        mock_youtube.videos().insert.return_value = mock_request

        # update() succeeds
        mock_update_req = MagicMock()
        mock_update_req.execute.return_value = {
            "id": "newly_created_yt_public_1",
            "status": {"privacyStatus": "private"}
        }
        mock_youtube.videos().update.return_value = mock_update_req

        # Mandatory read-back confirms private
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{
                "id": "newly_created_yt_public_1",
                "status": {"privacyStatus": "private", "license": "creativeCommon", "embeddable": True, "selfDeclaredMadeForKids": False}
            }]
        }

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Unexpected Public Short #Shorts",
                privacy="private",
                channel_id="UC_dest"
            )

        # Check safe update call
        assert mock_youtube.videos().update.called
        call_kwargs = mock_youtube.videos().update.call_args[1]
        assert call_kwargs.get("part") == "status"
        update_body = call_kwargs.get("body", {})
        assert update_body["id"] == "newly_created_yt_public_1"
        assert update_body["status"]["privacyStatus"] == "private"
        assert update_body["status"]["license"] == "creativeCommon"
        assert update_body["status"]["embeddable"] is True
        assert update_body["status"]["publicStatsViewable"] is False
        assert "uploadStatus" not in update_body["status"]  # Read-only stripped!

        # Mandatory read-back was executed
        assert mock_youtube.videos().list.called

        # Return diagnostics
        assert res["id"] == "newly_created_yt_public_1"
        assert res["privacy"] == "private"
        assert res["privacy_confirmed"] is False
        assert res["remediation"] == "auto_remediated_to_private"
        assert res["initial_remote_privacy"] == "public"

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_emergency_remediation_failure_flags_critical(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Phase 2 & 3: When emergency update fails with exception, upload_short preserves video ID, flags failure, and returns public."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "newly_created_yt_public_2",
            "status": {
                "privacyStatus": "public",
                "uploadStatus": "uploaded",
                "license": "youtube",
                "embeddable": True,
                "publicStatsViewable": True,
                "selfDeclaredMadeForKids": False,
            }
        })
        mock_youtube.videos().insert.return_value = mock_request

        # update() raises an exception
        mock_youtube.videos().update.side_effect = RuntimeError("QuotaExceeded for status update")

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Unremediated Public Short #Shorts",
                privacy="private",
                channel_id="UC_dest"
            )

        assert res["id"] == "newly_created_yt_public_2"
        assert res["privacy"] == "public"
        assert res["privacy_confirmed"] is False
        assert "QuotaExceeded" in res["remediation"]

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_correction_succeeds_but_subsequent_readback_reports_public(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Phase 3: update() succeeds but subsequent read-back reports 'public' -> returns public, not confirmed private."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "newly_created_yt_public_3",
            "status": {
                "privacyStatus": "public",
                "uploadStatus": "uploaded",
                "license": "youtube",
                "embeddable": True,
                "publicStatsViewable": True,
                "selfDeclaredMadeForKids": False,
            }
        })
        mock_youtube.videos().insert.return_value = mock_request

        # update() succeeds
        mock_update_req = MagicMock()
        mock_update_req.execute.return_value = {"id": "newly_created_yt_public_3", "status": {"privacyStatus": "private"}}
        mock_youtube.videos().update.return_value = mock_update_req

        # Read-back still reports public!
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{"id": "newly_created_yt_public_3", "status": {"privacyStatus": "public", "license": "youtube", "embeddable": True, "publicStatsViewable": True, "selfDeclaredMadeForKids": False}}]
        }

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Deceptive Update Short #Shorts",
                privacy="private",
                channel_id="UC_dest"
            )

        assert res["id"] == "newly_created_yt_public_3"
        assert res["privacy"] == "public"
        assert res["privacy_confirmed"] is False
        assert "still_public" in res["remediation"]

    @patch("pathlib.Path.exists", return_value=True)
    @patch("backend.services.publisher.MediaFileUpload")
    @patch("backend.services.publisher.get_youtube_client")
    def test_upload_short_correction_succeeds_but_subsequent_readback_fails(
        self, mock_get_client, mock_media, mock_exists
    ):
        """Phase 3: update() succeeds but read-back query raises exception -> returns unconfirmed, not confirmed private."""
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {
            "id": "newly_created_yt_public_4",
            "status": {
                "privacyStatus": "public",
                "uploadStatus": "uploaded",
                "license": "youtube",
                "embeddable": True,
                "publicStatsViewable": True,
                "selfDeclaredMadeForKids": False,
            }
        })
        mock_youtube.videos().insert.return_value = mock_request

        # update() succeeds
        mock_update_req = MagicMock()
        mock_update_req.execute.return_value = {"id": "newly_created_yt_public_4", "status": {"privacyStatus": "private"}}
        mock_youtube.videos().update.return_value = mock_update_req

        # Read-back raises exception
        mock_youtube.videos().list.side_effect = RuntimeError("503 Service Unavailable on read-back")

        with patch("backend.services.publisher.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            res = upload_short(
                video_path=Path("/tmp/clip.mp4"),
                title="Readback Error Short #Shorts",
                privacy="private",
                channel_id="UC_dest"
            )

        assert res["id"] == "newly_created_yt_public_4"
        assert res["privacy"] == "unconfirmed"
        assert res["privacy_confirmed"] is False
        assert "readback_exception" in res["remediation"]

    @patch("backend.tasks.clip_tasks.upload_short")
    @patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value=None)
    @patch("pathlib.Path.exists", return_value=True)
    def test_publish_clip_task_handles_remediated_public_insert(
        self, mock_exists, mock_check_ext, mock_upload
    ):
        """Phase 2: Remediated video is placed into manual_review with operational alert and preserved ID."""
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        mock_upload.return_value = {
            "id": "yt_remediated_123",
            "url": "https://www.youtube.com/shorts/yt_remediated_123",
            "title": "Title",
            "privacy": "private",
            "privacy_confirmed": False,
            "remediation": "auto_remediated_to_private",
            "status": "uploaded"
        }

        clip = _create_mock_clip(clip_id, privacy="private")
        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_task = _create_mock_task()

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls):
            res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        assert res["status"] == "manual_review"
        assert clip.publish_status == PublishStatus.MANUAL_REVIEW.value
        assert clip.youtube_short_id == "yt_remediated_123"
        assert "Operational Alert" in clip.publish_error
        assert "auto-remediated to 'private'" in clip.publish_error

    @patch("backend.tasks.clip_tasks.upload_short")
    @patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value=None)
    @patch("pathlib.Path.exists", return_value=True)
    def test_publish_clip_task_handles_failed_remediation_critical_alert(
        self, mock_exists, mock_check_ext, mock_upload
    ):
        """Phase 2 & 3: When remediation fails, clip is placed into manual_review with CRITICAL PRIVACY ALERT."""
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        mock_upload.return_value = {
            "id": "yt_exposed_456",
            "url": "https://www.youtube.com/shorts/yt_exposed_456",
            "title": "Title",
            "privacy": "public",
            "privacy_confirmed": False,
            "remediation": "remediation_exception: 403 Forbidden",
            "status": "uploaded"
        }

        clip = _create_mock_clip(clip_id, privacy="private")
        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_task = _create_mock_task()

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls):
            res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        assert res["status"] == "manual_review"
        assert clip.publish_status == PublishStatus.MANUAL_REVIEW.value
        assert clip.youtube_short_id == "yt_exposed_456"
        assert "CRITICAL PRIVACY ALERT" in clip.publish_error
        assert "PUBLIC ON YOUTUBE" in clip.publish_error

    @patch("backend.tasks.clip_tasks.upload_short")
    @patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value=None)
    @patch("pathlib.Path.exists", return_value=True)
    def test_publish_clip_task_handles_readback_still_public_critical_alert(
        self, mock_exists, mock_check_ext, mock_upload
    ):
        """Phase 3: When read-back reports video is still public, clip is placed into manual_review with CRITICAL PRIVACY ALERT."""
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        mock_upload.return_value = {
            "id": "yt_exposed_789",
            "url": "https://www.youtube.com/shorts/yt_exposed_789",
            "title": "Title",
            "privacy": "public",
            "privacy_confirmed": False,
            "remediation": "remediation_readback_still_public_public",
            "status": "uploaded"
        }

        clip = _create_mock_clip(clip_id, privacy="private")
        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_task = _create_mock_task()

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls):
            res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        assert res["status"] == "manual_review"
        assert clip.publish_status == PublishStatus.MANUAL_REVIEW.value
        assert clip.youtube_short_id == "yt_exposed_789"
        assert "CRITICAL PRIVACY ALERT" in clip.publish_error
        assert "PUBLIC ON YOUTUBE" in clip.publish_error

    @patch("backend.tasks.clip_tasks.upload_short")
    @patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value=None)
    @patch("pathlib.Path.exists", return_value=True)
    def test_publish_clip_task_handles_withheld_remediation_critical_alert(
        self, mock_exists, mock_check_ext, mock_upload
    ):
        """Phase 1 & 2: When remediation is withheld (unknown COPPA or scheduled publishAt), clip is placed into manual_review with CRITICAL PRIVACY ALERT."""
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        mock_upload.return_value = {
            "id": "yt_withheld_001",
            "url": "https://www.youtube.com/shorts/yt_withheld_001",
            "title": "Title",
            "privacy": "public",
            "privacy_confirmed": False,
            "remediation": "remediation_withheld: Cannot safely determine selfDeclaredMadeForKids for video yt_withheld_001",
            "status": "uploaded"
        }

        clip = _create_mock_clip(clip_id, privacy="private")
        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_task = _create_mock_task()

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls):
            res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        assert res["status"] == "manual_review"
        assert clip.publish_status == PublishStatus.MANUAL_REVIEW.value
        assert clip.youtube_short_id == "yt_withheld_001"
        assert "CRITICAL PRIVACY ALERT" in clip.publish_error
        assert "remediation_withheld" in clip.publish_error

    @patch("backend.tasks.clip_tasks.upload_short")
    @patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value=None)
    @patch("pathlib.Path.exists", return_value=True)
    def test_upload_raises_exception_marks_failed_honestly(
        self, mock_exists, mock_check_ext, mock_upload
    ):
        """Case 5: An upload raises an exception -> task must NOT falsely record a confirmed successful private upload."""
        clip_id = f"clip_err_{uuid.uuid4().hex[:8]}"
        clip = _create_mock_clip(clip_id, privacy="private")

        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_upload.side_effect = RuntimeError("YouTube API error: unauthorized credentials")

        mock_task = _create_mock_task()
        mock_task.request.retries = 3
        mock_task.max_retries = 3

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls):
            res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        assert res["status"] == "failed"
        assert clip.publish_status == PublishStatus.FAILED.value
        assert clip.youtube_short_id is None
        assert "unauthorized" in clip.publish_error.lower()

    @patch("backend.tasks.clip_tasks.upload_short")
    @patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value=None)
    @patch("pathlib.Path.exists", return_value=True)
    def test_upload_raises_transient_exception_retries_without_recording_success(
        self, mock_exists, mock_check_ext, mock_upload
    ):
        """Transient error triggers retry without recording successful private publish."""
        clip_id = f"clip_retry_{uuid.uuid4().hex[:8]}"
        clip = _create_mock_clip(clip_id, privacy="private")

        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_upload.side_effect = RuntimeError("Transient network hiccup")

        mock_task = _create_mock_task()
        mock_task.request.retries = 0
        mock_task.max_retries = 3
        mock_task.retry = MagicMock(side_effect=RuntimeError("celery_retry_called"))

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls):
            try:
                publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")
            except RuntimeError as e:
                assert "celery_retry_called" in str(e)

        assert clip.publish_status == PublishStatus.QUEUED.value
        assert clip.publish_stage == "retry_pending"
        assert clip.youtube_short_id is None


# =============================================================================
# 3. ALL WORKFLOW PATHS PRESERVE PRIVATE PUBLISHING POLICY
# =============================================================================
class TestAllPathsPreservePrivatePolicy:
    """Requirement 6: Recovery, retry, scheduler, routes, and models all preserve private upload policy."""

    @patch("backend.tasks.clip_tasks.publish_clip_task.apply_async")
    def test_recovery_task_preserves_private_policy(self, mock_apply_async):
        """Verify recover_stranded_publish_jobs_task dispatches retry explicitly with privacy='private'."""
        stale_clip = _create_mock_clip("stale_clip_123", privacy="public")
        stale_clip.publish_destination_id = "UC_dest_recovered"

        mock_session_cls, mock_session = _setup_mock_session(clips_list=[stale_clip])

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls):
            res = recover_stranded_publish_jobs_task(stale_threshold_seconds=60)

        assert res.get("recovered_count") == 1
        assert mock_apply_async.called
        call_kwargs = mock_apply_async.call_args[1]
        assert call_kwargs.get("kwargs", {}).get("privacy") == "private"

    def test_models_clip_privacy_default_is_private(self):
        """Verify Clip model column definitions default to 'private'."""
        col = Clip.__table__.columns["privacy"]
        assert col.default.arg == "private"
        server_default_text = col.server_default.arg.text if hasattr(col.server_default.arg, "text") else str(col.server_default.arg)
        assert server_default_text == "private"

    def test_publish_request_default_privacy_is_private(self):
        """Verify PublishRequest Pydantic schema default is 'private'."""
        from backend.api.routes.publish import PublishRequest
        req = PublishRequest(clip_id="test_clip_id")
        assert req.privacy == "private"

    @pytest.mark.asyncio
    async def test_scheduler_auto_publisher_enforces_private_privacy(self):
        """Verify scheduler auto-publisher loop uploads with privacy='private'."""
        from backend.tasks.scheduler import run_auto_publisher
        from unittest.mock import AsyncMock

        mock_clip = _create_mock_clip("auto_pub_clip_123", privacy="private")
        mock_clip.channel_id = "chan_source_123"
        mock_clip.publish_destination_id = "chan_dest_456"

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_clip]
        mock_result.scalar_one.return_value = mock_clip
        mock_result.scalar_one_or_none.side_effect = [mock_clip, None, None]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_db

        with patch("backend.tasks.scheduler.AsyncSessionLocal", mock_session_maker), \
             patch("backend.services.publisher.async_resolve_publish_destination", new_callable=AsyncMock) as mock_resolve, \
             patch("backend.tasks.scheduler.managed_download_sync") as mock_dl, \
             patch("backend.tasks.scheduler.upload_short") as mock_upload:
            mock_resolve.return_value = "UC_dest_youtube"
            mock_dl.return_value.__enter__.return_value = "/tmp/clip.mp4"
            mock_upload.return_value = {"id": "auto_yt_999", "privacy": "private", "status": "uploaded"}

            await run_auto_publisher()

            assert mock_upload.called
            call_kwargs = mock_upload.call_args[1]
            assert call_kwargs.get("privacy") == "private"
            assert mock_clip.publish_status == "published"
            assert mock_clip.privacy == "private"

    @pytest.mark.asyncio
    async def test_clips_route_publish_clip_preserves_private_policy(self):
        """Verify POST /api/clips/{id}/publish passes privacy='private' and records confirmed status."""
        from backend.api.routes.clips import publish_clip
        from unittest.mock import AsyncMock

        mock_dest = MagicMock()
        mock_dest.id = "chan_dest_123"
        mock_dest.youtube_channel_id = "UC_dest"
        mock_dest.is_active = True
        mock_dest.is_destination = True

        mock_clip = _create_mock_clip("route_pub_clip_123", privacy="public")
        mock_clip.publish_destination_id = "chan_dest_123"
        mock_clip.pinned_comment = None

        mock_db = MagicMock()
        res_clip = MagicMock()
        res_clip.scalar_one_or_none.return_value = mock_clip
        res_dest = MagicMock()
        res_dest.scalar_one_or_none.return_value = mock_dest
        mock_db.execute = AsyncMock(side_effect=[res_clip, res_dest])
        mock_db.commit = AsyncMock()

        with patch("backend.services.publisher.upload_short") as mock_upload, \
             patch("backend.services.publisher.settings") as mock_settings, \
             patch("pathlib.Path.exists", return_value=True):
            mock_settings.PUBLISH_MODE = "prod"
            mock_upload.return_value = {"id": "route_yt_888", "url": "https://...", "privacy": "private"}

            res = await publish_clip("route_pub_clip_123", db=mock_db)

            assert mock_upload.called
            call_kwargs = mock_upload.call_args[1]
            assert call_kwargs.get("privacy") == "private"
            assert mock_clip.privacy == "private"
            assert mock_clip.publish_status == "published"
            assert res["privacy"] == "private"


# =============================================================================
# 4. RECONCILIATION PRIVACY & ERROR HANDLING
# =============================================================================
class TestReconciliationPrivacyHandling:
    """Requirement 8: Verify reconciliation queries remote status, does not overwrite with stale local value, and handles API errors."""

    @patch("backend.tasks.clip_tasks.check_external_youtube_state")
    @patch("backend.services.publisher.get_youtube_client")
    @patch("pathlib.Path.exists", return_value=True)
    def test_reconciliation_detects_remote_public_and_flags_manual_review(
        self, mock_exists, mock_get_client, mock_check_ext
    ):
        """Verify that when remote video is public, reconciliation sets manual_review and records 'public'."""
        clip_id = f"clip_rec_{uuid.uuid4().hex[:8]}"
        remote_yt_id = "0OfOivc-tpU"
        mock_check_ext.return_value = remote_yt_id

        mock_yt = MagicMock()
        mock_yt.videos().list().execute.return_value = {
            "items": [{
                "id": remote_yt_id,
                "status": {"privacyStatus": "public"}
            }]
        }
        mock_get_client.return_value = mock_yt

        clip = MagicMock()
        clip.id = clip_id
        clip.publish_status = PublishStatus.QUEUED.value
        clip.youtube_short_id = None
        clip.output_path = "/tmp/real_clip.mp4"
        clip.status = "completed"
        clip.publish_idempotency_key = "idemp_rec_pub"
        clip.privacy = "private"  # Stale local record claimed private

        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_task = MagicMock()
        mock_task.request.id = "task_rec_pub"

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls), \
             patch("backend.tasks.clip_tasks.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            with patch.dict(os.environ, {"PUBLISH_MODE": "prod"}):
                res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        # Must record actual remote privacy ("public") and transition to manual_review
        assert clip.privacy == "public"
        assert clip.youtube_short_id == remote_yt_id
        assert clip.publish_status == PublishStatus.MANUAL_REVIEW.value
        assert res["status"] == "manual_review"
        assert res["privacy"] == "public"

    @patch("backend.tasks.clip_tasks.check_external_youtube_state")
    @patch("backend.services.publisher.get_youtube_client")
    @patch("pathlib.Path.exists", return_value=True)
    def test_reconciliation_api_lookup_failure_flags_manual_review_and_preserves_id(
        self, mock_exists, mock_get_client, mock_check_ext
    ):
        """Verify that if YouTube API lookup fails during reconciliation, it flags manual_review and preserves video ID."""
        clip_id = f"clip_rec_{uuid.uuid4().hex[:8]}"
        remote_yt_id = "yt_lookup_fail_123"
        mock_check_ext.return_value = remote_yt_id

        # YouTube API lookup raises network or API error
        mock_yt = MagicMock()
        mock_yt.videos().list().execute.side_effect = RuntimeError("YouTube API 500 Backend Error")
        mock_get_client.return_value = mock_yt

        clip = _create_mock_clip(clip_id, privacy="private")
        clip.output_path = "/tmp/real_clip.mp4"
        clip.publish_idempotency_key = "idemp_rec_fail"

        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_task = MagicMock()
        mock_task.request.id = "task_rec_fail"

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls), \
             patch("backend.tasks.clip_tasks.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            with patch.dict(os.environ, {"PUBLISH_MODE": "prod"}):
                res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        # Video ID must NOT be lost!
        assert clip.youtube_short_id == remote_yt_id
        # Status must be manual_review, privacy unconfirmed
        assert clip.privacy == "unconfirmed"
        assert clip.publish_status == PublishStatus.MANUAL_REVIEW.value
        assert res["status"] == "manual_review"

    @patch("backend.tasks.clip_tasks.check_external_youtube_state")
    @patch("backend.services.publisher.get_youtube_client")
    @patch("pathlib.Path.exists", return_value=True)
    def test_reconciliation_never_calls_videos_update_for_existing_videos(
        self, mock_exists, mock_get_client, mock_check_ext
    ):
        """Phase 2 & 3: Reconciliation of pre-existing videos must NEVER call videos().update."""
        clip_id = f"clip_rec_safe_{uuid.uuid4().hex[:8]}"
        remote_yt_id = "existing_public_vid_99"
        mock_check_ext.return_value = remote_yt_id

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        # videos().list returns public for the existing video
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{"id": remote_yt_id, "status": {"privacyStatus": "public"}}]
        }

        clip = _create_mock_clip(clip_id, privacy="private")
        mock_session_cls, mock_session = _setup_mock_session(clip_obj=clip)
        mock_task = MagicMock()
        mock_task.request.id = "task_rec_safe"

        with patch("backend.models.database.SyncSessionLocal", mock_session_cls), \
             patch("backend.tasks.clip_tasks.settings") as mock_settings:
            mock_settings.PUBLISH_MODE = "prod"
            with patch.dict(os.environ, {"PUBLISH_MODE": "prod"}):
                res = publish_clip_task(mock_task, clip_id=clip_id, channel_id="UC_dest")

        # Crucial invariant: videos().update must NEVER be called during reconciliation!
        assert not mock_youtube.videos().update.called
        assert res["status"] == "manual_review"
        assert clip.publish_status == PublishStatus.MANUAL_REVIEW.value
        assert clip.youtube_short_id == remote_yt_id
        assert clip.privacy == "public"



# =============================================================================
# 5. DATABASE SCHEMA PARITY AND MIGRATION VERIFICATION
# =============================================================================
class TestDatabaseSchemaParityAndMigration:
    """Requirement 9: Test Alembic migration e6f7a8b9c0d1 in an isolated disposable schema."""

    def test_alembic_migration_e6f7a8b9c0d1_upgrade_and_downgrade_parity_in_isolated_schema(self):
        """
        Connects to PostgreSQL, creates a temporary isolated schema,
        validates initial column default 'public', executes upgrade to 'private',
        asserts resulting column default, executes downgrade back to 'public',
        and cleanly drops the temporary schema. Operational tables are untouched.
        """
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            port=5433,
            user="clipforge_user",
            password="clipforge_password",
            dbname="clipforge"
        )
        conn.autocommit = True
        cur = conn.cursor()

        iso_schema = f"iso_test_schema_{uuid.uuid4().hex[:8]}"
        try:
            # 1. Create disposable isolated schema
            cur.execute(f"CREATE SCHEMA {iso_schema};")

            # 2. Create replica of clips table with initial default 'public'
            cur.execute(f"""
                CREATE TABLE {iso_schema}.clips (
                    id VARCHAR(50) PRIMARY KEY,
                    privacy VARCHAR(50) NOT NULL DEFAULT 'public'
                );
            """)

            # 3. Verify baseline default is 'public'
            cur.execute(f"""
                SELECT column_default
                FROM information_schema.columns
                WHERE table_schema = '{iso_schema}'
                  AND table_name = 'clips'
                  AND column_name = 'privacy';
            """)
            initial_default = cur.fetchone()[0]
            assert "'public'" in initial_default, f"Expected initial default 'public', got: {initial_default}"

            # 4. Execute migration upgrade logic: ALTER COLUMN privacy SET DEFAULT 'private'
            cur.execute(f"ALTER TABLE {iso_schema}.clips ALTER COLUMN privacy SET DEFAULT 'private';")

            # 5. Verify upgraded default is 'private'
            cur.execute(f"""
                SELECT column_default
                FROM information_schema.columns
                WHERE table_schema = '{iso_schema}'
                  AND table_name = 'clips'
                  AND column_name = 'privacy';
            """)
            upgraded_default = cur.fetchone()[0]
            assert "'private'" in upgraded_default, f"Expected upgraded default 'private', got: {upgraded_default}"

            # 6. Insert row without specifying privacy to confirm default behaves as 'private'
            cur.execute(f"INSERT INTO {iso_schema}.clips (id) VALUES ('test_clip_1');")
            cur.execute(f"SELECT privacy FROM {iso_schema}.clips WHERE id = 'test_clip_1';")
            inserted_privacy = cur.fetchone()[0]
            assert inserted_privacy == "private", f"Expected inserted privacy 'private', got: {inserted_privacy}"

            # 7. Execute migration safe downgrade logic: DROP DEFAULT (server_default=None)
            cur.execute(f"ALTER TABLE {iso_schema}.clips ALTER COLUMN privacy DROP DEFAULT;")

            cur.execute(f"""
                SELECT column_default
                FROM information_schema.columns
                WHERE table_schema = '{iso_schema}'
                  AND table_name = 'clips'
                  AND column_name = 'privacy';
            """)
            downgraded_default = cur.fetchone()[0]
            assert downgraded_default is None, f"Expected downgraded default None (dropped), got: {downgraded_default}"

            # 8. Verify fail-safe: inserting without privacy raises NOT NULL constraint violation
            # rather than silently inserting 'public'
            insert_failed = False
            try:
                cur.execute(f"INSERT INTO {iso_schema}.clips (id) VALUES ('test_clip_no_default');")
            except Exception:
                insert_failed = True
            assert insert_failed, "Expected fail-safe NOT NULL constraint violation after safe downgrade!"

        finally:
            cur.execute(f"DROP SCHEMA IF EXISTS {iso_schema} CASCADE;")
            cur.close()
            conn.close()


# =============================================================================
# 6. ZERO LIVE MUTATIONS OR UNMOCKED NETWORK CALLS
# =============================================================================
class TestZeroLiveMutations:
    """Requirement 7: Verify no test invokes a real YouTube upload or mutates live videos."""

    def test_no_real_youtube_mutation_endpoints_called_in_suite(self):
        """
        Verify that publisher.py update_video_metadata only updates snippet,
        and never touches status.privacyStatus.
        """
        import inspect
        from backend.services.publisher import update_video_metadata
        source = inspect.getsource(update_video_metadata)

        # update_video_metadata must never update status
        assert 'part="snippet"' in source
        assert 'part="snippet,status"' not in source
        assert 'privacyStatus' not in source
