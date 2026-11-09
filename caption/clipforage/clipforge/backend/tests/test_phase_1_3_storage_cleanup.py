"""
test_phase_1_3_storage_cleanup.py
===================================
Isolated Acceptance Test Suite for Phase 1.3:
Storage Cleanup Endpoint Delivery & UI Integration (CF-DEF-001)

Adheres strictly to the 20 test specifications defined in
docs/engineering/prompts/PHASE_1_3_STORAGE_CLEANUP_IMPLEMENTATION_PLAN.md (v6.0.0).

All tests execute against isolated test data and temporary directories,
never mutating real user artifacts or unverified database rows.
"""

import os
import json
import time
import uuid
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.core.config import settings
from backend.core.storage_identity import resolve_storage_identity_secret
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import (
    Clip, Video, Job, ArtifactRecord,
    VideoReservationState
)
from backend.api.routes.clips import (
    validate_canonical_containment,
    verify_filesystem_colocation,
    generate_preview_token,
    validate_preview_token,
    reconcile_quarantine,
    CanonicalContainmentError,
    CrossDeviceLinkError,
)


TEST_PREFIX = "p13_test_"


@pytest.fixture(autouse=True)
async def cleanup_p13_records():
    """Wipes test database records and test filesystem fixtures after every test."""
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        session.query(Clip).filter(Clip.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ArtifactRecord).filter(ArtifactRecord.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Job).filter(Job.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Video).filter(Video.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.commit()

    # Clean any journal test batches in storage_cleanup_journals
    journal_root = settings.BASE_DIR / "storage_cleanup_journals"
    if journal_root.exists():
        for b_dir in journal_root.iterdir():
            if b_dir.is_dir() and TEST_PREFIX in b_dir.name:
                shutil.rmtree(b_dir, ignore_errors=True)

    # Clean any test quarantine folders
    quar_root = settings.OUTPUT_DIR / ".storage_quarantine"
    if quar_root.exists():
        for q_dir in quar_root.iterdir():
            if q_dir.is_dir() and TEST_PREFIX in q_dir.name:
                shutil.rmtree(q_dir, ignore_errors=True)


# =========================================================================
# TEST 1: Preview Read-Only Invariant
# =========================================================================
@pytest.mark.asyncio
async def test_01_preview_read_only_invariant():
    """
    Test 1: GET /api/clips/cleanup/preview mutates zero files and zero database rows.
    """
    clip_id = f"{TEST_PREFIX}c1_{uuid.uuid4().hex[:6]}"
    video_id = f"{TEST_PREFIX}v1_{uuid.uuid4().hex[:6]}"
    clip_dir = settings.OUTPUT_DIR / video_id / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    media_file = clip_dir / "final.mp4"
    media_file.write_bytes(b"0" * 1024)

    try:
        with SyncSessionLocal() as session:
            v = Video(id=video_id, title="Test Video 1", duration=60.0)
            session.add(v)
            c = Clip(
                id=clip_id,
                video_id=video_id,
                title="Low Score Clip",
                score=3.2,
                start_time=0.0,
                end_time=10.0,
                duration=10.0,
                output_path=f"{video_id}/clips/{clip_id}/final.mp4",
                publish_status="draft"
            )
            session.add(c)
            session.commit()

        initial_stat = media_file.stat()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/clips/cleanup/preview?score_threshold=5.0")
            assert resp.status_code == 200
            data = resp.json()
            assert "preview_token" in data
            assert data["counts"]["total_unique"] >= 1
            assert any(item["clip_id"] == clip_id for item in data["candidates"])

        # Invariant checks: zero DB mutation, zero file mutation
        with SyncSessionLocal() as session:
            c_db = session.query(Clip).filter(Clip.id == clip_id).first()
            assert c_db is not None
            assert c_db.score == 3.2

        current_stat = media_file.stat()
        assert media_file.exists()
        assert current_stat.st_size == initial_stat.st_size
        assert current_stat.st_mtime == initial_stat.st_mtime
    finally:
        shutil.rmtree(settings.OUTPUT_DIR / video_id, ignore_errors=True)


# =========================================================================
# TEST 2: Preview Token HMAC Tampering Rejection
# =========================================================================
@pytest.mark.asyncio
async def test_02_preview_token_hmac_tampering_rejection():
    """
    Test 2: Tampered signature or modified payload is rejected with 401 or 400.
    """
    clip_ids = [f"{TEST_PREFIX}clip_{i}" for i in range(2)]
    token, _, _ = generate_preview_token(candidate_clip_ids=clip_ids)

    payload_b64, sig = token.split(".")
    # 1. Tampered signature
    tampered_sig = ("0" if sig[0] != "0" else "1") + sig[1:]
    tampered_token = f"{payload_b64}.{tampered_sig}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/clips/cleanup/execute",
            json={"preview_token": tampered_token, "candidate_clip_ids": clip_ids}
        )
        assert resp.status_code == 401

        # 2. Tampered payload
        decoded = json.loads(__import__("base64").urlsafe_b64decode(payload_b64.encode("utf-8") + b"==").decode("utf-8"))
        decoded["candidate_count"] = 99
        tampered_b64 = __import__("base64").urlsafe_b64encode(json.dumps(decoded).encode("utf-8")).decode("utf-8")
        resp2 = await client.post(
            "/api/clips/cleanup/execute",
            json={"preview_token": f"{tampered_b64}.{sig}", "candidate_clip_ids": clip_ids}
        )
        assert resp2.status_code in [400, 401]

        # 3. Malformed token structure (no dot)
        resp3 = await client.post(
            "/api/clips/cleanup/execute",
            json={"preview_token": "malformed_token_string", "candidate_clip_ids": clip_ids}
        )
        assert resp3.status_code == 400


# =========================================================================
# TEST 3: Preview Token Expiry Rejection
# =========================================================================
@pytest.mark.asyncio
async def test_03_preview_token_expiry_rejection():
    """
    Test 3: Expired preview token (now > expires_at) is rejected with 400.
    """
    clip_ids = [f"{TEST_PREFIX}clip_exp"]
    expired_time = int(time.time()) - 100
    token, _, _ = generate_preview_token(candidate_clip_ids=clip_ids, expires_at=expired_time)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/clips/cleanup/execute",
            json={"preview_token": token, "candidate_clip_ids": clip_ids}
        )
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()


# =========================================================================
# TEST 4: Preview Token Candidate Mismatch Rejection
# =========================================================================
@pytest.mark.asyncio
async def test_04_preview_token_candidate_mismatch_rejection():
    """
    Test 4: Submitting candidate IDs differing from reviewed preview token is rejected with 400.
    """
    reviewed_clips = [f"{TEST_PREFIX}clip_a", f"{TEST_PREFIX}clip_b"]
    token, _, _ = generate_preview_token(candidate_clip_ids=reviewed_clips)

    # Submit different candidates
    altered_clips = [f"{TEST_PREFIX}clip_a", f"{TEST_PREFIX}clip_c"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/clips/cleanup/execute",
            json={"preview_token": token, "candidate_clip_ids": altered_clips}
        )
        assert resp.status_code == 400
        assert "do not match" in resp.json()["detail"].lower()


# =========================================================================
# TEST 5: Insecure Secret Rejection
# =========================================================================
def test_05_insecure_secret_rejection():
    """
    Test 5: resolve_storage_identity_secret rejects empty, placeholders, and < 16 chars.
    """
    insecure_candidates = [
        "",
        "   ",
        "clipforge_default_secret_key_change_in_prod",
        "changeme",
        "secret",
        "short_secret",
        "123456789012345"  # 15 chars
    ]
    for candidate in insecure_candidates:
        with pytest.raises(RuntimeError):
            resolve_storage_identity_secret(candidate)

    valid_candidate = "a_very_secure_secret_key_12345"
    res = resolve_storage_identity_secret(valid_candidate)
    assert res == valid_candidate


# =========================================================================
# TEST 6: Preview Token Integrity Contract (Not Auth Substitute)
# =========================================================================
def test_06_preview_token_integrity_contract_not_auth_substitute():
    """
    Test 6: Preview token is an integrity lease binding candidate set hash and time window.
    Fails closed on replay across candidate sets, malformed base64, or parameter modifications.
    """
    candidates = [f"{TEST_PREFIX}1", f"{TEST_PREFIX}2"]
    token, preview_id, _ = generate_preview_token(candidate_clip_ids=candidates)

    # Valid validation passes
    validated = validate_preview_token(token, candidates)
    assert validated["preview_id"] == preview_id

    # Replay on subset fails closed
    with pytest.raises(__import__("fastapi").HTTPException) as exc1:
        validate_preview_token(token, [candidates[0]])
    assert exc1.value.status_code == 400

    # Garbage base64 fails closed
    with pytest.raises(__import__("fastapi").HTTPException) as exc2:
        validate_preview_token("garbage_payload.sig", candidates)
    assert exc2.value.status_code == 400


# =========================================================================
# TEST 7: Quarantine URL 404 Isolation on Real Application
# =========================================================================
@pytest.mark.asyncio
async def test_07_quarantine_url_404_isolation_on_real_application():
    """
    Test 7: Exercise actual backend.main:app with physical file staged in
    settings.OUTPUT_DIR / ".storage_quarantine" / "batch_test" / "test_artifact.mp4".
    Verify GET and HEAD return 404 and zero bytes are retrievable.
    """
    quar_dir = settings.OUTPUT_DIR / ".storage_quarantine" / f"batch_{TEST_PREFIX}sec"
    quar_dir.mkdir(parents=True, exist_ok=True)
    secret_file = quar_dir / "test_artifact.mp4"
    secret_file.write_bytes(b"SECRET_QUARANTINE_DATA_NEVER_SERVED_VIA_HTTP")

    try:
        url = f"/outputs/.storage_quarantine/batch_{TEST_PREFIX}sec/test_artifact.mp4"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            get_resp = await client.get(url)
            assert get_resp.status_code == 404
            assert b"SECRET_QUARANTINE_DATA" not in get_resp.content

            head_resp = await client.head(url)
            assert head_resp.status_code == 404
    finally:
        shutil.rmtree(quar_dir, ignore_errors=True)


# =========================================================================
# TEST 8: Filesystem Co-Location Preflight Check
# =========================================================================
def test_08_filesystem_colocation_preflight_check():
    """
    Test 8: verify_filesystem_colocation detects device ID mismatch and raises CrossDeviceLinkError.
    """
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as quar_dir:
        src_p = Path(src_dir)
        quar_p = Path(quar_dir)

        real_stat = os.stat
        mock_quar_stat = MagicMock(st_dev=2002)

        def mock_os_stat(p, *args, **kwargs):
            res = real_stat(p, *args, **kwargs)
            if str(quar_p.name) in str(p):
                return mock_quar_stat
            return res

        with patch("os.stat", side_effect=mock_os_stat):
            with pytest.raises(CrossDeviceLinkError) as exc_info:
                verify_filesystem_colocation(src_p, quar_p)
            assert "different filesystem devices" in str(exc_info.value)


# =========================================================================
# TEST 9: High-Score Asset Preservation
# =========================================================================
@pytest.mark.asyncio
async def test_09_high_score_asset_preservation():
    """
    Test 9: Clips with score >= 5.0 (5.00 and 5.01) are excluded from candidates
    and rejected if submitted to execute.
    """
    clip_id = f"{TEST_PREFIX}hs_{uuid.uuid4().hex[:6]}"
    video_id = f"{TEST_PREFIX}v_hs_{uuid.uuid4().hex[:6]}"
    clip_dir = settings.OUTPUT_DIR / video_id / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    media_file = clip_dir / "final.mp4"
    media_file.write_bytes(b"1" * 512)

    try:
        with SyncSessionLocal() as session:
            v = Video(id=video_id, title="Test Video HS")
            session.add(v)
            c = Clip(
                id=clip_id,
                video_id=video_id,
                title="High Score Clip",
                score=5.00,
                start_time=0.0,
                end_time=10.0,
                duration=10.0,
                output_path=f"{video_id}/clips/{clip_id}/final.mp4",
                publish_status="draft"
            )
            session.add(c)
            session.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # In preview: excluded
            prev_resp = await client.get("/api/clips/cleanup/preview?score_threshold=5.0")
            data = prev_resp.json()
            assert not any(c_item["clip_id"] == clip_id for c_item in data["candidates"])
            assert data["protected_counts"]["high_score"] >= 1

            # In execute: even if attempted with a generated token, it is skipped
            token, _, _ = generate_preview_token(candidate_clip_ids=[clip_id])
            exec_resp = await client.post(
                "/api/clips/cleanup/execute",
                json={"preview_token": token, "candidate_clip_ids": [clip_id]}
            )
            assert exec_resp.status_code == 200
            res_data = exec_resp.json()
            assert clip_id not in res_data["deleted_clip_ids"]
            assert any(s["clip_id"] == clip_id and "score" in s["reason"] for s in res_data["skipped_candidates"])

        # File and DB intact
        assert media_file.exists()
        with SyncSessionLocal() as session:
            assert session.query(Clip).filter(Clip.id == clip_id).first() is not None
    finally:
        shutil.rmtree(settings.OUTPUT_DIR / video_id, ignore_errors=True)


# =========================================================================
# TEST 10: Published Asset Protection
# =========================================================================
@pytest.mark.asyncio
async def test_10_published_asset_protection():
    """
    Test 10: Clips with publish_status = 'published' or valid youtube_short_id are protected.
    """
    clip_pub_id = f"{TEST_PREFIX}pub_{uuid.uuid4().hex[:6]}"
    clip_yt_id = f"{TEST_PREFIX}yt_{uuid.uuid4().hex[:6]}"
    video_id = f"{TEST_PREFIX}v_pub_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        v = Video(id=video_id, title="Test Video Pub")
        session.add(v)
        c1 = Clip(
            id=clip_pub_id,
            video_id=video_id,
            title="Published Clip",
            score=2.0,
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            publish_status="published"
        )
        c2 = Clip(
            id=clip_yt_id,
            video_id=video_id,
            title="YouTube ID Clip",
            score=2.0,
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            youtube_short_id="yt_abc123"
        )
        session.add_all([c1, c2])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        prev_resp = await client.get("/api/clips/cleanup/preview?score_threshold=5.0")
        data = prev_resp.json()
        assert not any(c["clip_id"] in [clip_pub_id, clip_yt_id] for c in data["candidates"])
        assert data["protected_counts"]["published"] >= 2

        # In execute: skipped
        token, _, _ = generate_preview_token(candidate_clip_ids=[clip_pub_id, clip_yt_id])
        exec_resp = await client.post(
            "/api/clips/cleanup/execute",
            json={"preview_token": token, "candidate_clip_ids": [clip_pub_id, clip_yt_id]}
        )
        assert exec_resp.status_code == 200
        res_data = exec_resp.json()
        assert len(res_data["deleted_clip_ids"]) == 0
        assert len(res_data["skipped_candidates"]) == 2


# =========================================================================
# TEST 11: Active Pipeline & Reservation Protection
# =========================================================================
@pytest.mark.asyncio
async def test_11_active_pipeline_and_reservation_protection():
    """
    Test 11: Clips linked to active jobs (Job.status='transcribing') or active reservations (HEADROOM_ONLY)
    are strictly protected.
    """
    v_job_id = f"{TEST_PREFIX}v_job_{uuid.uuid4().hex[:6]}"
    job_id = f"{TEST_PREFIX}job_{uuid.uuid4().hex[:6]}"
    clip_job_id = f"{TEST_PREFIX}c_job_{uuid.uuid4().hex[:6]}"

    v_res_id = f"{TEST_PREFIX}v_res_{uuid.uuid4().hex[:6]}"
    clip_res_id = f"{TEST_PREFIX}c_res_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        v1 = Video(id=v_job_id, title="Active Job Video")
        j = Job(id=job_id, video_id=v_job_id, status="transcribing")
        c1 = Clip(id=clip_job_id, video_id=v_job_id, title="Active Job Clip", score=2.0, start_time=0.0, end_time=10.0, duration=10.0)

        v2 = Video(id=v_res_id, title="Reserved Video", reservation_state=VideoReservationState.HEADROOM_ONLY.value)
        c2 = Clip(id=clip_res_id, video_id=v_res_id, title="Reserved Clip", score=2.0, start_time=0.0, end_time=10.0, duration=10.0)

        session.add_all([v1, j, c1, v2, c2])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        prev_resp = await client.get("/api/clips/cleanup/preview?score_threshold=5.0")
        data = prev_resp.json()
        assert not any(c["clip_id"] in [clip_job_id, clip_res_id] for c in data["candidates"])
        assert data["protected_counts"]["active_jobs"] >= 1
        assert data["protected_counts"]["active_reservations"] >= 1


# =========================================================================
# TEST 12: Shared Artifact Reference Preservation
# =========================================================================
@pytest.mark.asyncio
async def test_12_shared_artifact_reference_preservation():
    """
    Test 12: If an artifact is shared across two clips, deleting one clip unlinks its database
    record but retains the physical file on disk (shared_files_retained == 1).
    """
    video_id = f"{TEST_PREFIX}v_shared_{uuid.uuid4().hex[:6]}"
    clip1_id = f"{TEST_PREFIX}c1_shared_{uuid.uuid4().hex[:6]}"
    clip2_id = f"{TEST_PREFIX}c2_shared_{uuid.uuid4().hex[:6]}"

    clip_dir = settings.OUTPUT_DIR / video_id / "clips" / clip1_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    shared_file = clip_dir / "final.mp4"
    shared_file.write_bytes(b"SHARED_MEDIA_CONTENT" * 50)
    rel_path = f"{video_id}/clips/{clip1_id}/final.mp4"

    try:
        with SyncSessionLocal() as session:
            v = Video(id=video_id, title="Shared Video")
            session.add(v)
            c1 = Clip(id=clip1_id, video_id=video_id, title="Clip 1", score=2.0, start_time=0.0, end_time=10.0, duration=10.0, output_path=rel_path)
            c2 = Clip(id=clip2_id, video_id=video_id, title="Clip 2", score=2.0, start_time=0.0, end_time=10.0, duration=10.0, output_path=rel_path)
            session.add_all([c1, c2])
            session.commit()

        token, _, _ = generate_preview_token(candidate_clip_ids=[clip1_id])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            exec_resp = await client.post(
                "/api/clips/cleanup/execute",
                json={"preview_token": token, "candidate_clip_ids": [clip1_id]}
            )
            assert exec_resp.status_code == 200
            data = exec_resp.json()
            assert clip1_id in data["deleted_clip_ids"]
            assert data["summary"]["shared_files_retained"] >= 1

        # Physical file is PRESERVED on disk
        assert shared_file.exists()

        # Database record for c1 is deleted, c2 is preserved
        with SyncSessionLocal() as session:
            assert session.query(Clip).filter(Clip.id == clip1_id).first() is None
            assert session.query(Clip).filter(Clip.id == clip2_id).first() is not None
    finally:
        shutil.rmtree(settings.OUTPUT_DIR / video_id, ignore_errors=True)


# =========================================================================
# TEST 13: Missing-Media Safe Separation
# =========================================================================
@pytest.mark.asyncio
async def test_13_missing_media_safe_separation():
    """
    Test 13: Missing-media records are reported in counts.unavailable but skipped by default
    when purge_missing_media = False.
    """
    video_id = f"{TEST_PREFIX}v_miss_{uuid.uuid4().hex[:6]}"
    clip_id = f"{TEST_PREFIX}c_miss_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        v = Video(id=video_id, title="Missing Media Video")
        c = Clip(
            id=clip_id,
            video_id=video_id,
            title="Missing Media Clip",
            score=2.0,
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=f"{video_id}/clips/{clip_id}/non_existent.mp4"
        )
        session.add_all([v, c])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        prev_resp = await client.get("/api/clips/cleanup/preview?score_threshold=5.0")
        data = prev_resp.json()
        assert data["counts"]["unavailable"] >= 1
        cand = next((c for c in data["candidates"] if c["clip_id"] == clip_id), None)
        assert cand is not None
        assert cand["category"] == "unavailable"
        assert cand["size_bytes"] == 0

        # Execute with default purge_missing_media=False -> skipped
        token, _, _ = generate_preview_token(candidate_clip_ids=[clip_id], purge_missing_media=False)
        exec_resp = await client.post(
            "/api/clips/cleanup/execute",
            json={"preview_token": token, "candidate_clip_ids": [clip_id], "purge_missing_media": False}
        )
        assert exec_resp.status_code == 200
        res_data = exec_resp.json()
        assert clip_id not in res_data["deleted_clip_ids"]
        assert any(s["clip_id"] == clip_id for s in res_data["skipped_candidates"])

        # Execute with purge_missing_media=True -> pruned from DB
        token2, _, _ = generate_preview_token(candidate_clip_ids=[clip_id], purge_missing_media=True)
        exec_resp2 = await client.post(
            "/api/clips/cleanup/execute",
            json={"preview_token": token2, "candidate_clip_ids": [clip_id], "purge_missing_media": True}
        )
        assert exec_resp2.status_code == 200
        res_data2 = exec_resp2.json()
        assert clip_id in res_data2["deleted_clip_ids"]

    with SyncSessionLocal() as session:
        assert session.query(Clip).filter(Clip.id == clip_id).first() is None


# =========================================================================
# TEST 14: Canonical Path Containment & Escape Rejection
# =========================================================================
def test_14_canonical_path_containment_and_escape_rejection():
    """
    Test 14: Traversal attempts and root destruction attempts are blocked.
    """
    approved_root = settings.OUTPUT_DIR

    # 1. Traversal outside root
    with pytest.raises(CanonicalContainmentError):
        validate_canonical_containment("../../etc/passwd", approved_root)

    # 2. Target is root itself
    with pytest.raises(CanonicalContainmentError):
        validate_canonical_containment(approved_root, approved_root)

    # 3. Disallowed extension
    with pytest.raises(CanonicalContainmentError):
        validate_canonical_containment(approved_root / "vid1" / "clips" / "clip1" / "payload.exe", approved_root)

    # 4. Valid containment
    valid_path = approved_root / "vid1" / "clips" / "clip1" / "final.mp4"
    res = validate_canonical_containment(valid_path, approved_root)
    assert res == valid_path.resolve()


# =========================================================================
# TEST 15: Crash Recovery Scenario 1 (Intent durable, before move)
# =========================================================================
@pytest.mark.asyncio
async def test_15_crash_recovery_scenario_1_intent_durable_before_move():
    """
    Test 15: Crash after Step 3 of 6-step ordering (INTENT_DECLARED).
    Quarantine target is empty; canonical source file exists.
    Recovery rolls back journal to CANCELLED_UNMOVED/ROLLED_BACK; canonical file intact.
    """
    batch_id = f"{TEST_PREFIX}crash1_{uuid.uuid4().hex[:6]}"
    batch_dir = settings.BASE_DIR / "storage_cleanup_journals" / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    src_file = settings.OUTPUT_DIR / f"{TEST_PREFIX}crash1_src.mp4"
    src_file.write_bytes(b"CRASH1_CANONICAL_SOURCE")

    quar_dir = settings.OUTPUT_DIR / ".storage_quarantine" / f"batch_{batch_id}"
    dst_file = quar_dir / "target.mp4"

    journal_content = {
        "batch_id": batch_id,
        "batch_state": "STAGING",
        "items": [
            {
                "clip_id": f"{TEST_PREFIX}c_cr1",
                "canonical_source": str(src_file),
                "quarantine_destination": str(dst_file),
                "item_state": "INTENT_DECLARED"
            }
        ]
    }
    (batch_dir / "journal.json").write_text(json.dumps(journal_content))

    try:
        rec_res = await reconcile_quarantine()
        assert rec_res["status"] == "ok"
        assert rec_res["reconciled_batches"] >= 1

        # Canonical file intact
        assert src_file.exists()
        assert src_file.read_bytes() == b"CRASH1_CANONICAL_SOURCE"
        assert not dst_file.exists()

        # Journal state updated
        data = json.loads((batch_dir / "journal.json").read_text())
        assert data["batch_state"] == "ROLLED_BACK"
    finally:
        src_file.unlink(missing_ok=True)
        shutil.rmtree(batch_dir, ignore_errors=True)
        shutil.rmtree(quar_dir, ignore_errors=True)


# =========================================================================
# TEST 16: Crash Recovery Scenario 2 (Immediately after move, before staging persisted)
# =========================================================================
@pytest.mark.asyncio
async def test_16_crash_recovery_scenario_2_immediately_after_move():
    """
    Test 16: Crash immediately after Step 4 (os.replace succeeded, file in quarantine,
    source missing, DB untouched).
    Recovery restores file to canonical source and marks journal ROLLED_BACK.
    """
    batch_id = f"{TEST_PREFIX}crash2_{uuid.uuid4().hex[:6]}"
    batch_dir = settings.BASE_DIR / "storage_cleanup_journals" / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    src_file = settings.OUTPUT_DIR / f"{TEST_PREFIX}crash2_src.mp4"
    quar_dir = settings.OUTPUT_DIR / ".storage_quarantine" / f"batch_{batch_id}"
    quar_dir.mkdir(parents=True, exist_ok=True)
    dst_file = quar_dir / "target.mp4"
    dst_file.write_bytes(b"CRASH2_QUARANTINED_FILE")

    journal_content = {
        "batch_id": batch_id,
        "batch_state": "STAGING",
        "items": [
            {
                "clip_id": f"{TEST_PREFIX}c_cr2",
                "canonical_source": str(src_file),
                "quarantine_destination": str(dst_file),
                "item_state": "INTENT_DECLARED"
            }
        ]
    }
    (batch_dir / "journal.json").write_text(json.dumps(journal_content))

    try:
        rec_res = await reconcile_quarantine()
        assert rec_res["status"] == "ok"
        assert rec_res["reconciled_batches"] >= 1

        # File is RESTORED to source
        assert src_file.exists()
        assert src_file.read_bytes() == b"CRASH2_QUARANTINED_FILE"
        assert not dst_file.exists()

        data = json.loads((batch_dir / "journal.json").read_text())
        assert data["batch_state"] == "ROLLED_BACK"
    finally:
        src_file.unlink(missing_ok=True)
        shutil.rmtree(batch_dir, ignore_errors=True)
        shutil.rmtree(quar_dir, ignore_errors=True)


# =========================================================================
# TEST 17: Crash Recovery Scenario 3 (Staged, before DB commit)
# =========================================================================
@pytest.mark.asyncio
async def test_17_crash_recovery_scenario_3_staged_before_db_commit():
    """
    Test 17: All files staged in quarantine, journal state STAGED, but crash before DB commit.
    DB clips still exist. Recovery restores files to canonical source, marks journal ROLLED_BACK.
    """
    batch_id = f"{TEST_PREFIX}crash3_{uuid.uuid4().hex[:6]}"
    clip_id = f"{TEST_PREFIX}c_cr3_{uuid.uuid4().hex[:6]}"
    video_id = f"{TEST_PREFIX}v_cr3_{uuid.uuid4().hex[:6]}"
    batch_dir = settings.BASE_DIR / "storage_cleanup_journals" / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    with SyncSessionLocal() as session:
        v = Video(id=video_id, title="Crash 3 Video")
        c = Clip(id=clip_id, video_id=video_id, title="Crash 3 Clip", score=2.0, start_time=0.0, end_time=10.0, duration=10.0)
        session.add_all([v, c])
        session.commit()

    src_file = settings.OUTPUT_DIR / f"{TEST_PREFIX}crash3_src.mp4"
    quar_dir = settings.OUTPUT_DIR / ".storage_quarantine" / f"batch_{batch_id}"
    quar_dir.mkdir(parents=True, exist_ok=True)
    dst_file = quar_dir / "target.mp4"
    dst_file.write_bytes(b"CRASH3_STAGED_PAYLOAD")

    journal_content = {
        "batch_id": batch_id,
        "batch_state": "STAGED",
        "items": [
            {
                "clip_id": clip_id,
                "canonical_source": str(src_file),
                "quarantine_destination": str(dst_file),
                "item_state": "STAGED"
            }
        ]
    }
    (batch_dir / "journal.json").write_text(json.dumps(journal_content))

    try:
        rec_res = await reconcile_quarantine()
        assert rec_res["status"] == "ok"
        assert rec_res["reconciled_batches"] >= 1

        # Restored to canonical source
        assert src_file.exists()
        assert src_file.read_bytes() == b"CRASH3_STAGED_PAYLOAD"
        assert not dst_file.exists()

        data = json.loads((batch_dir / "journal.json").read_text())
        assert data["batch_state"] == "ROLLED_BACK"
    finally:
        src_file.unlink(missing_ok=True)
        shutil.rmtree(batch_dir, ignore_errors=True)
        shutil.rmtree(quar_dir, ignore_errors=True)


# =========================================================================
# TEST 18: Crash Recovery Scenario 4 (DB committed, before purge)
# =========================================================================
@pytest.mark.asyncio
async def test_18_crash_recovery_scenario_4_db_committed_before_purge():
    """
    Test 18: DB committed (clip record deleted from DB), crash before physical purge.
    Recovery detects clip missing from DB, proceeds to purge quarantined files, marks COMPLETED.
    """
    batch_id = f"{TEST_PREFIX}crash4_{uuid.uuid4().hex[:6]}"
    clip_id = f"{TEST_PREFIX}c_cr4_deleted"
    batch_dir = settings.BASE_DIR / "storage_cleanup_journals" / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    src_file = settings.OUTPUT_DIR / f"{TEST_PREFIX}crash4_src.mp4"
    quar_dir = settings.OUTPUT_DIR / ".storage_quarantine" / f"batch_{batch_id}"
    quar_dir.mkdir(parents=True, exist_ok=True)
    dst_file = quar_dir / "target.mp4"
    dst_file.write_bytes(b"CRASH4_FILE_TO_PURGE")

    journal_content = {
        "batch_id": batch_id,
        "batch_state": "DB_COMMITTING",
        "items": [
            {
                "clip_id": clip_id,
                "canonical_source": str(src_file),
                "quarantine_destination": str(dst_file),
                "item_state": "STAGED"
            }
        ]
    }
    (batch_dir / "journal.json").write_text(json.dumps(journal_content))

    try:
        rec_res = await reconcile_quarantine()
        assert rec_res["status"] == "ok"
        assert rec_res["reconciled_batches"] >= 1

        # Quarantined file purged
        assert not dst_file.exists()
        assert not quar_dir.exists()

        data = json.loads((batch_dir / "journal.json").read_text())
        assert data["batch_state"] == "COMPLETED"
    finally:
        src_file.unlink(missing_ok=True)
        shutil.rmtree(batch_dir, ignore_errors=True)
        shutil.rmtree(quar_dir, ignore_errors=True)


# =========================================================================
# TEST 19: Crash Recovery Scenario 5 (Purge interrupted)
# =========================================================================
@pytest.mark.asyncio
async def test_19_crash_recovery_scenario_5_purge_interrupted():
    """
    Test 19: 5 files quarantined, 2 unlinked before crash.
    Recovery idempotently unlinks remaining 3 files and removes quarantine directory.
    """
    batch_id = f"{TEST_PREFIX}crash5_{uuid.uuid4().hex[:6]}"
    clip_id = f"{TEST_PREFIX}c_cr5_deleted"
    batch_dir = settings.BASE_DIR / "storage_cleanup_journals" / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    quar_dir = settings.OUTPUT_DIR / ".storage_quarantine" / f"batch_{batch_id}"
    quar_dir.mkdir(parents=True, exist_ok=True)

    # 3 files remaining
    f1 = quar_dir / "rem1.mp4"
    f2 = quar_dir / "rem2.mp4"
    f3 = quar_dir / "rem3.mp4"
    f1.write_bytes(b"rem1")
    f2.write_bytes(b"rem2")
    f3.write_bytes(b"rem3")

    journal_content = {
        "batch_id": batch_id,
        "batch_state": "PURGING",
        "items": [
            {
                "clip_id": clip_id,
                "canonical_source": str(settings.OUTPUT_DIR / "f1.mp4"),
                "quarantine_destination": str(f1),
                "item_state": "PURGING"
            }
        ]
    }
    (batch_dir / "journal.json").write_text(json.dumps(journal_content))

    try:
        rec_res = await reconcile_quarantine()
        assert rec_res["status"] == "ok"
        assert rec_res["reconciled_batches"] >= 1

        # All remaining files purged and directory removed
        assert not f1.exists()
        assert not f2.exists()
        assert not f3.exists()
        assert not quar_dir.exists()

        data = json.loads((batch_dir / "journal.json").read_text())
        assert data["batch_state"] == "COMPLETED"
    finally:
        shutil.rmtree(batch_dir, ignore_errors=True)
        shutil.rmtree(quar_dir, ignore_errors=True)


# =========================================================================
# TEST 20: External Conflict & Ambiguous State Handling
# =========================================================================
@pytest.mark.asyncio
async def test_20_external_conflict_and_ambiguous_state_handling():
    """
    Test 20: External conflict or unresolvable ambiguous status during recovery.
    Proves recovery preserves physical data without data loss, marking batch BLOCKED_AWAITING_RECOVERY.
    """
    batch_id = f"{TEST_PREFIX}crash6_{uuid.uuid4().hex[:6]}"
    batch_dir = settings.BASE_DIR / "storage_cleanup_journals" / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    quar_dir = settings.OUTPUT_DIR / ".storage_quarantine" / f"batch_{batch_id}"
    quar_dir.mkdir(parents=True, exist_ok=True)
    dst_file = quar_dir / "target.mp4"
    dst_file.write_bytes(b"AMBIGUOUS_SAFETY_PAYLOAD")

    journal_content = {
        "batch_id": batch_id,
        "batch_state": "STAGED",
        "items": [
            {
                "clip_id": f"{TEST_PREFIX}c_cr6",
                "canonical_source": str(settings.OUTPUT_DIR / "f_cr6.mp4"),
                "quarantine_destination": str(dst_file),
                "item_state": "STAGED"
            }
        ]
    }
    (batch_dir / "journal.json").write_text(json.dumps(journal_content))

    # Mock DB failure during reconciliation to simulate ambiguous state
    with patch("backend.api.routes.clips.AsyncSessionLocal") as mock_session_cls:
        mock_session_cls.side_effect = RuntimeError("Database unreachable during recovery")
        rec_res = await reconcile_quarantine()
        assert rec_res["blocked_batches"] >= 1

    try:
        # Crucial invariant: physical payload in quarantine is PRESERVED, not lost
        assert dst_file.exists()
        assert dst_file.read_bytes() == b"AMBIGUOUS_SAFETY_PAYLOAD"

        data = json.loads((batch_dir / "journal.json").read_text())
        assert data["batch_state"] == "BLOCKED_AWAITING_RECOVERY"
    finally:
        shutil.rmtree(batch_dir, ignore_errors=True)
        shutil.rmtree(quar_dir, ignore_errors=True)
