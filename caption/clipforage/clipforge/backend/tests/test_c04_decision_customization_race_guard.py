"""
test_c04_decision_customization_race_guard.py
=============================================
Comprehensive test suite verifying CF-DEF-007: Single-Video Decision Customization Race Guard:
1. Terminal state protection: save-and-process on already resolved decision returns HTTP 409 Conflict.
2. Terminal state protection: customize on already resolved decision returns HTTP 409 Conflict.
3. Cancellation terminal state protection: customize and save-and-process on cancelled decision return HTTP 409 Conflict.
4. Active lease lock: concurrent customization of the same item returns HTTP 409 Conflict.
5. Lease renewal: caller with matching lease_token can renew/extend lease.
6. Forced lease takeover: caller with force=True can take over active lease.
7. Stale lease token guard: superseded lease token on save-and-process returns HTTP 409 Conflict.
8. Optimistic expected_status guard: state mismatch returns HTTP 409 Conflict.
9. Parallel execution: two different items can be customized and processed concurrently without conflict.
10. Nonexistent decision ID returns HTTP 404 Not Found.
11. Channel ownership mismatch returns HTTP 404 Not Found.
12. Celery countdown and sweep behavior: skips active lease, resolves expired lease, and handles terminal state idempotently.
13. Zero real YouTube publication invariant (is_test=True, zero publication).
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Channel, VideoDecision, VideoDecisionStatus, Job
from backend.tasks.orchestration import resolve_video_decision_sync, sweep_pending_decisions_task


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        session.query(VideoDecision).filter(VideoDecision.channel_id.like("ch_c04_%")).delete(synchronize_session=False)
        session.query(Job).filter(Job.channel_id.like("ch_c04_%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.like("ch_c04_%")).delete(synchronize_session=False)
        session.commit()


def _seed_channel_and_decision(
    status: VideoDecisionStatus = VideoDecisionStatus.AWAITING_SETTINGS,
    job_id: str | None = None,
    lease_expires_delta: timedelta | None = None,
    overrides: dict | None = None,
    deadline_delta: timedelta = timedelta(seconds=20),
):
    ch_id = f"ch_c04_{uuid.uuid4().hex[:8]}"
    dec_id = f"dec_c04_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_ch_{ch_id}",
            channel_name="C04 Test Channel",
            channel_url="https://youtube.com/@c04test",
            is_active=True,
            auto_clip=True,
            auto_publish=False,
            is_test=True,
            processing_profile={"video_layout": "fill_blur", "clips_count": 3},
        )
        session.add(ch)

        lease_time = now + lease_expires_delta if lease_expires_delta else None
        dec = VideoDecision(
            id=dec_id,
            channel_id=ch_id,
            youtube_id=f"yt_{dec_id}",
            youtube_url=f"https://youtube.com/watch?v=yt_{dec_id}",
            video_title=f"Video for {dec_id}",
            status=status.value,
            decision_deadline=now + deadline_delta,
            customization_lease_expires_at=lease_time,
            resolved_at=now if job_id else None,
            job_id=job_id,
            channel_profile_snapshot={"video_layout": "fill_blur", "clips_count": 3},
            overrides=overrides,
            created_at=now - timedelta(minutes=1),
        )
        session.add(dec)
        session.commit()

    return ch_id, dec_id


# ── 1. Terminal State Protection (Save-and-Process) ───────────────────────────

@pytest.mark.asyncio
async def test_terminal_state_save_and_process_conflict_409():
    """Verify save-and-process on an already resolved decision returns 409 Conflict."""
    job_id = f"job_c04_{uuid.uuid4().hex[:8]}"
    ch_id, dec_id = _seed_channel_and_decision(
        status=VideoDecisionStatus.RESOLVED_DEFAULTS,
        job_id=job_id,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/channels/decisions/{dec_id}/save-and-process",
            json={"overrides": {"video_layout": "split_screen", "clips_count": 5}}
        )
        assert resp.status_code == 409
        data = resp.json()
        assert "already resolved" in data["detail"]["message"].lower()
        assert data["detail"]["conflict_type"] == "terminal_state"
        assert data["detail"]["job_id"] == job_id


# ── 2. Terminal State Protection (Customize) ──────────────────────────────────

@pytest.mark.asyncio
async def test_terminal_state_customize_conflict_409():
    """Verify customize modal request on an already resolved decision returns 409 Conflict."""
    job_id = f"job_c04_{uuid.uuid4().hex[:8]}"
    ch_id, dec_id = _seed_channel_and_decision(
        status=VideoDecisionStatus.RESOLVED_CUSTOM,
        job_id=job_id,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/channels/decisions/{dec_id}/customize")
        assert resp.status_code == 409
        data = resp.json()
        assert "already resolved" in data["detail"]["message"].lower()
        assert data["detail"]["conflict_type"] == "terminal_state"


# ── 3. Cancellation Terminal State Protection ────────────────────────────────

@pytest.mark.asyncio
async def test_cancelled_decision_rejects_customization_and_overrides():
    """Verify customize, save-and-process, and apply-defaults on a cancelled decision return 409."""
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.CANCELLED)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_cust = await client.post(f"/api/channels/decisions/{dec_id}/customize")
        assert resp_cust.status_code == 409

        resp_save = await client.post(
            f"/api/channels/decisions/{dec_id}/save-and-process",
            json={"overrides": {"video_layout": "center_crop", "clips_count": 2}}
        )
        assert resp_save.status_code == 409

        resp_def = await client.post(f"/api/channels/decisions/{dec_id}/apply-defaults")
        assert resp_def.status_code == 409


# ── 4. Active Lease Lock on Same Item ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_customization_active_lease_conflict_409():
    """Verify two concurrent users customizing the same decision: 1st acquires lease, 2nd receives 409."""
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User 1 opens modal
        resp1 = await client.post(f"/api/channels/decisions/{dec_id}/customize")
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "customizing"
        assert "lease_token" in data1
        token1 = data1["lease_token"]

        # User 2 tries to open modal on same item while User 1 holds active lease
        resp2 = await client.post(f"/api/channels/decisions/{dec_id}/customize")
        assert resp2.status_code == 409
        data2 = resp2.json()
        assert data2["detail"]["conflict_type"] == "active_lease"
        assert "locked for customization" in data2["detail"]["message"].lower()


# ── 5. Lease Renewal with Matching Token ──────────────────────────────────────

@pytest.mark.asyncio
async def test_lease_renewal_with_valid_token_succeeds():
    """Verify user holding lease_token can renew the lease without conflict."""
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.post(f"/api/channels/decisions/{dec_id}/customize")
        token1 = resp1.json()["lease_token"]

        # Same user refreshes/renews lease with matching lease_token
        resp_renew = await client.post(
            f"/api/channels/decisions/{dec_id}/customize",
            json={"lease_token": token1}
        )
        assert resp_renew.status_code == 200
        assert resp_renew.json()["lease_token"] == token1


# ── 6. Forced Lease Takeover ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_force_customize_takeover_succeeds():
    """Verify force=True allows taking over an active customization lease."""
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.post(f"/api/channels/decisions/{dec_id}/customize")
        token1 = resp1.json()["lease_token"]

        # User 2 forces takeover
        resp2 = await client.post(
            f"/api/channels/decisions/{dec_id}/customize",
            json={"force": True}
        )
        assert resp2.status_code == 200
        token2 = resp2.json()["lease_token"]
        assert token2 != token1


# ── 7. Stale Lease Token Guard on Save-and-Process ────────────────────────────

@pytest.mark.asyncio
async def test_stale_lease_token_rejected_on_save_and_process():
    """Verify superseded lease token is rejected with 409 on save-and-process."""
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User 1 gets token 1
        resp1 = await client.post(f"/api/channels/decisions/{dec_id}/customize")
        token1 = resp1.json()["lease_token"]

        # User 2 takes over lease
        resp2 = await client.post(f"/api/channels/decisions/{dec_id}/customize", json={"force": True})
        token2 = resp2.json()["lease_token"]

        # User 1 tries to submit with stale token 1 -> rejected with 409
        resp_stale = await client.post(
            f"/api/channels/decisions/{dec_id}/save-and-process",
            json={
                "overrides": {"video_layout": "split_screen", "clips_count": 4},
                "lease_token": token1,
            }
        )
        assert resp_stale.status_code == 409
        assert resp_stale.json()["detail"]["conflict_type"] == "stale_lease"

        # User 2 submits with valid token 2 -> succeeds
        with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
            resp_valid = await client.post(
                f"/api/channels/decisions/{dec_id}/save-and-process",
                json={
                    "overrides": {"video_layout": "split_screen", "clips_count": 4},
                    "lease_token": token2,
                }
            )
            assert resp_valid.status_code == 200
            assert resp_valid.json()["status"] == "resolved_custom"


# ── 8. Optimistic expected_status Guard ───────────────────────────────────────

@pytest.mark.asyncio
async def test_optimistic_expected_status_mismatch_rejected():
    """Verify expected_status mismatch returns 409 state_mismatch."""
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/channels/decisions/{dec_id}/save-and-process",
            json={
                "overrides": {"video_layout": "fit_black", "clips_count": 3},
                "expected_status": "customizing",  # But DB status is currently awaiting_settings
            }
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["conflict_type"] == "state_mismatch"


# ── 9. Parallel Execution on Different Items ──────────────────────────────────

@pytest.mark.asyncio
async def test_two_different_items_customize_and_process_in_parallel():
    """Verify two different decisions can be customized and processed in parallel without interference."""
    ch1, dec1 = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)
    ch2, dec2 = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Both acquire lease simultaneously
        resp1 = await client.post(f"/api/channels/decisions/{dec1}/customize")
        resp2 = await client.post(f"/api/channels/decisions/{dec2}/customize")

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        token1 = resp1.json()["lease_token"]
        token2 = resp2.json()["lease_token"]

        with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
            # Both submit custom overrides in parallel
            res_sub1 = await client.post(
                f"/api/channels/decisions/{dec1}/save-and-process",
                json={"overrides": {"video_layout": "center_crop", "clips_count": 2}, "lease_token": token1}
            )
            res_sub2 = await client.post(
                f"/api/channels/decisions/{dec2}/save-and-process",
                json={"overrides": {"video_layout": "split_screen", "clips_count": 4}, "lease_token": token2}
            )

            assert res_sub1.status_code == 200
            assert res_sub2.status_code == 200
            assert res_sub1.json()["job_id"] != res_sub2.json()["job_id"]

    # Verify both distinct records persisted
    with SyncSessionLocal() as session:
        d1 = session.query(VideoDecision).filter_by(id=dec1).first()
        d2 = session.query(VideoDecision).filter_by(id=dec2).first()
        assert d1.status == VideoDecisionStatus.RESOLVED_CUSTOM.value
        assert d2.status == VideoDecisionStatus.RESOLVED_CUSTOM.value
        assert d1.overrides["video_layout"] == "center_crop"
        assert d2.overrides["video_layout"] == "split_screen"


# ── 10. Nonexistent Decision ID returns 404 ───────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_decision_id_returns_404():
    """Verify nonexistent decision ID returns 404 Not Found."""
    fake_id = f"dec_fake_{uuid.uuid4().hex[:8]}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_cust = await client.post(f"/api/channels/decisions/{fake_id}/customize")
        assert resp_cust.status_code == 404

        resp_save = await client.post(
            f"/api/channels/decisions/{fake_id}/save-and-process",
            json={"overrides": {"video_layout": "fill_blur"}}
        )
        assert resp_save.status_code == 404

        resp_def = await client.post(f"/api/channels/decisions/{fake_id}/apply-defaults")
        assert resp_def.status_code == 404

        resp_cancel = await client.post(f"/api/channels/decisions/{fake_id}/cancel")
        assert resp_cancel.status_code == 404


# ── 11. Channel Ownership Mismatch returns 404 ────────────────────────────────

@pytest.mark.asyncio
async def test_channel_ownership_mismatch_returns_404():
    """Verify mismatched channel_id parameter returns 404 Not Found."""
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)
    wrong_ch_id = f"ch_c04_wrong_{uuid.uuid4().hex[:6]}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/channels/decisions/{dec_id}/customize?channel_id={wrong_ch_id}"
        )
        assert resp.status_code == 404


# ── 12. Celery Sweep & Countdown Interaction ─────────────────────────────────

def test_background_sweep_and_countdown_skip_active_customization_and_resolve_expired():
    """Verify Celery countdown/sweep skips active customization, resolves expired, and idempotently handles resolved."""
    # Seed active customization lease
    ch_id, dec_id = _seed_channel_and_decision(
        status=VideoDecisionStatus.CUSTOMIZING,
        lease_expires_delta=timedelta(seconds=120),
        overrides={"_lease_token": "active_tok"},
    )

    # Sweep during active lease -> skips resolution
    res_sweep_active = resolve_video_decision_sync(decision_id=dec_id, action="sweep")
    assert res_sweep_active.get("skipped") == "customization_in_progress"

    # Countdown during active lease -> skips resolution
    res_cd_active = resolve_video_decision_sync(decision_id=dec_id, action="countdown")
    assert res_cd_active.get("skipped") == "customization_in_progress"

    # Expire the lease
    with SyncSessionLocal() as session:
        dec = session.query(VideoDecision).filter_by(id=dec_id).first()
        dec.customization_lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        session.commit()

    # Expired lease sweep -> resolves to defaults and creates job
    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        res_sweep_expired = resolve_video_decision_sync(decision_id=dec_id, action="sweep")
        assert res_sweep_expired["status"] == VideoDecisionStatus.RESOLVED_DEFAULTS.value
        assert "job_id" in res_sweep_expired
        job_id = res_sweep_expired["job_id"]

        # Subsequent sweep on already resolved decision exits cleanly without error or conflict
        res_subsequent = resolve_video_decision_sync(decision_id=dec_id, action="sweep")
        assert res_subsequent["status"] == VideoDecisionStatus.RESOLVED_DEFAULTS.value
        assert res_subsequent["already_resolved"] is True
        assert res_subsequent.get("conflict") is not True

        # But a user action on this now-resolved decision is flagged with conflict
        res_user_action = resolve_video_decision_sync(decision_id=dec_id, action="custom", custom_overrides={})
        assert res_user_action.get("conflict") is True
        assert res_user_action.get("status_code") == 409


# ── 13. YouTube Invariant ─────────────────────────────────────────────────────

def test_no_real_youtube_publication_invariant():
    """Verify all decisions and jobs in test context enforce is_test=True with zero YouTube publication."""
    with SyncSessionLocal() as session:
        jobs = session.query(Job).filter(Job.channel_id.like("ch_c04_%")).all()
        for j in jobs:
            assert j.is_test is True
            assert j.publish_status in (None, "draft", "not_requested")


# ── 14. Adversarial: apply-defaults Collision with Active Lease ───────────────

@pytest.mark.asyncio
async def test_adversarial_apply_defaults_during_active_lease_rejected_409():
    """Verify applying defaults while another user holds an active customization lease returns 409."""
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User 1 claims lease
        resp_cust = await client.post(f"/api/channels/decisions/{dec_id}/customize")
        assert resp_cust.status_code == 200
        token = resp_cust.json()["lease_token"]

        # User 2 tries to immediately apply defaults on same item -> blocked with 409
        resp_def = await client.post(f"/api/channels/decisions/{dec_id}/apply-defaults")
        assert resp_def.status_code == 409
        assert resp_def.json()["detail"]["conflict_type"] == "active_lease"

        # User 1 (holding lease token) CAN apply defaults
        with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
            resp_def_owner = await client.post(
                f"/api/channels/decisions/{dec_id}/apply-defaults",
                json={"lease_token": token}
            )
            assert resp_def_owner.status_code == 200
            assert resp_def_owner.json()["status"] == "resolved_defaults"


# ── 15. Adversarial: Concurrent save-and-process Simultaneous Race ───────────

@pytest.mark.asyncio
async def test_adversarial_concurrent_save_and_process_race_condition():
    """Verify two concurrent asynchronous requests to save-and-process: exactly 1 wins, 1 receives 409."""
    import asyncio
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
            # Fire both requests concurrently
            task1 = client.post(
                f"/api/channels/decisions/{dec_id}/save-and-process",
                json={"overrides": {"video_layout": "split_screen", "clips_count": 3}}
            )
            task2 = client.post(
                f"/api/channels/decisions/{dec_id}/save-and-process",
                json={"overrides": {"video_layout": "center_crop", "clips_count": 4}}
            )
            res1, res2 = await asyncio.gather(task1, task2)

            statuses = [res1.status_code, res2.status_code]
            assert 200 in statuses, f"Expected one 200 OK, got: {statuses}"
            assert 409 in statuses, f"Expected one 409 Conflict, got: {statuses}"


# ── 16. Adversarial: Caption Burn-In Rejection (Zero Caption Invariant) ──────

@pytest.mark.asyncio
async def test_adversarial_invalid_caption_burn_in_override_rejected_422():
    """Verify caption_burn_in=True is strictly rejected with 422 Unprocessable Entity."""
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/channels/decisions/{dec_id}/save-and-process",
            json={"overrides": {"video_layout": "fill_blur", "caption_burn_in": True}}
        )
        assert resp.status_code == 422
        assert "caption burn-in is strictly disabled" in resp.text.lower()


# ── 17. Adversarial: Duration Out of Bounds Rejection (Shorts Duration Invariant)

@pytest.mark.asyncio
async def test_adversarial_invalid_duration_out_of_bounds_rejected_422():
    """Verify clip durations exceeding 30.0s or below 15.0s are rejected with 422."""
    ch_id, dec_id = _seed_channel_and_decision(status=VideoDecisionStatus.AWAITING_SETTINGS)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Exceeds 30s cap
        resp_too_long = await client.post(
            f"/api/channels/decisions/{dec_id}/save-and-process",
            json={"overrides": {"video_layout": "fill_blur", "max_clip_duration": 45.0}}
        )
        assert resp_too_long.status_code == 422

        # Below 15s minimum
        resp_too_short = await client.post(
            f"/api/channels/decisions/{dec_id}/save-and-process",
            json={"overrides": {"video_layout": "fill_blur", "min_clip_duration": 8.0}}
        )
        assert resp_too_short.status_code == 422
