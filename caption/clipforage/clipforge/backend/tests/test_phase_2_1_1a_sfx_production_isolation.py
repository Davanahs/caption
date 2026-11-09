"""
test_phase_2_1_1a_sfx_production_isolation.py
=============================================
Authoritative Regression Test Suite for Phase 2.1.1A / Phase 2.1.1A.1:
Trusted Test-Context Enforcement & SFX Fallback Production Isolation

Required Regression Cases:
1. A verified test job permits synthetic fallback when the asset library is empty.
2. A verified test channel permits fallback only where the existing contract explicitly treats it as authoritative.
3. A production clip with a normal UUID and Job.is_test=False is denied fallback.
4. A production clip whose ID begins with test_sfx_, test_fixture_, p21_test_ or another recognized
   test prefix is still denied when authoritative context identifies it as production.
5. A missing clip or missing job/channel context fails closed.
6. Conflicting job and channel test flags fail closed unless the existing documented contract
   specifies an unambiguous authoritative source.
7. No untrusted API or task parameter can turn a production clip into a test fixture.
8. Existing synthetic-asset filtering and normal eligible-asset planning remain functional.
9. Repeated requests do not introduce duplicate synthetic assets or orphaned artifact records.
10. Subprocess failure paths cleanly abort without leaving orphaned records.
"""

import os
import json
import uuid
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest
from sqlalchemy import select

from backend.models.database import SyncSessionLocal, engine, AsyncSessionLocal
from backend.models.models import (
    Clip, Video, Job, Channel, ClipSFXPlan, ClipRetention, SFXAsset, ArtifactRecord,
    ArtifactType, ArtifactStatus
)
from backend.models.sfx import SFXPlan
from backend.services.sfx_planner import SFXPlanner

TEST_PREFIX = "test_sfx_iso_"


@pytest.fixture(autouse=True)
async def cleanup_test_records():
    """Wipes test database records before and after every test."""
    def _clean():
        with SyncSessionLocal() as session:
            session.query(ClipSFXPlan).filter(ClipSFXPlan.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(ClipRetention).filter(ClipRetention.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(Clip).filter(Clip.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(Video).filter(Video.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(Job).filter(Job.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(Channel).filter(Channel.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(SFXAsset).filter(
                (SFXAsset.id.like(f"{TEST_PREFIX}%")) | 
                (SFXAsset.name.like("sample_%")) | 
                (SFXAsset.name == "trace_tone")
            ).delete(synchronize_session=False)
            session.query(ArtifactRecord).filter(
                (ArtifactRecord.id.like(f"{TEST_PREFIX}%")) | 
                (ArtifactRecord.storage_key.like("mock_sfx/%"))
            ).delete(synchronize_session=False)
            session.commit()

    _clean()
    yield
    await engine.dispose()
    _clean()


def seed_clip_with_retention(
    clip_id: str,
    is_test: bool = False,
    channel_id: str = None,
    with_job: bool = True,
    job_is_test: bool = None,
    channel_is_test: bool = None,
    with_channel: bool = True
) -> tuple[str, str]:
    """Helper to seed an isolated clip with retention data, channel, and job context. Returns (clip_id, video_id)."""
    with SyncSessionLocal() as session:
        chan_is_test = is_test if channel_is_test is None else channel_is_test
        j_is_test = is_test if job_is_test is None else job_is_test

        chan_id = None
        if with_channel:
            chan_id = channel_id or f"{TEST_PREFIX}chan_{uuid.uuid4().hex[:8]}"
            ch = session.query(Channel).filter_by(id=chan_id).first()
            if not ch:
                ch = Channel(
                    id=chan_id,
                    youtube_channel_id=f"UC_{uuid.uuid4().hex[:8]}",
                    channel_name=f"{'Test' if chan_is_test else 'Production'} Channel",
                    channel_url="https://youtube.com/channel/example",
                    is_test=chan_is_test
                )
                session.add(ch)

        vid_id = f"{TEST_PREFIX}vid_{uuid.uuid4().hex[:8]}"
        video = Video(
            id=vid_id,
            youtube_id=f"yt_{uuid.uuid4().hex[:8]}",
            title=f"{'Test' if is_test else 'Production'} Video",
            channel_id=chan_id,
            local_path="/tmp/dummy.mp4"
        )
        session.add(video)

        if with_job:
            job = Job(
                id=f"{TEST_PREFIX}job_{uuid.uuid4().hex[:8]}",
                video_id=vid_id,
                channel_id=chan_id,
                is_test=j_is_test
            )
            session.add(job)

        clip = Clip(
            id=clip_id,
            video_id=vid_id,
            title="SFX Evaluation Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            score=8.5,
            publish_status="draft",
            output_path="/tmp/dummy.mp4"
        )
        session.add(clip)

        retention = ClipRetention(
            clip_id=clip_id,
            overall_score=7.5,
            analysis_json=json.dumps([{
                "start_time": 1.0,
                "end_time": 3.0,
                "severity": "high",
                "reason": "Audience dropoff due to low audio engagement",
                "suggested_intervention_types": ["sfx_opportunity"]
            }])
        )
        session.add(retention)
        session.commit()
        return clip_id, vid_id


# =============================================================================
# CASE 1: Verified Test Job Permits Synthetic Fallback
# =============================================================================
@pytest.mark.asyncio
async def test_verified_test_job_permits_synthetic_fallback():
    """
    Case 1: A verified test job (Job.is_test=True, no channel context) permits synthetic fallback
    when the asset library is empty, generating placeholder assets and returning a valid plan.
    """
    clip_id = f"{TEST_PREFIX}clip_job_auth_{uuid.uuid4().hex[:8]}"
    seed_clip_with_retention(clip_id, is_test=True, with_job=True, with_channel=False)

    planner = SFXPlanner()
    async with AsyncSessionLocal() as async_session:
        assets_res = await async_session.execute(select(SFXAsset))
        initial_assets = len(assets_res.scalars().all())

        plan = await planner.generate_plan(clip_id=clip_id, db=async_session)
        assert isinstance(plan, SFXPlan)
        assert plan.clip_id == clip_id
        assert len(plan.placements) >= 1
        assert plan.placements[0].category in ["impact", "whoosh", "ambience"]

        assets_res_after = await async_session.execute(select(SFXAsset))
        after_assets = len(assets_res_after.scalars().all())
        assert after_assets > initial_assets

        art_res = await async_session.execute(
            select(ArtifactRecord).where(
                ArtifactRecord.owner_id == clip_id,
                ArtifactRecord.artifact_type == ArtifactType.AUDIO_SFX.value
            )
        )
        assert len(art_res.scalars().all()) >= 1


# =============================================================================
# CASE 2: Verified Test Channel Permits Fallback
# =============================================================================
@pytest.mark.asyncio
async def test_verified_test_channel_permits_fallback():
    """
    Case 2: A verified test channel (Channel.is_test=True, no job context) permits synthetic fallback
    when the asset library is empty.
    """
    clip_id = f"{TEST_PREFIX}clip_chan_auth_{uuid.uuid4().hex[:8]}"
    seed_clip_with_retention(clip_id, is_test=True, with_job=False, with_channel=True)

    planner = SFXPlanner()
    async with AsyncSessionLocal() as async_session:
        assets_res = await async_session.execute(select(SFXAsset))
        initial_assets = len(assets_res.scalars().all())

        plan = await planner.generate_plan(clip_id=clip_id, db=async_session)
        assert isinstance(plan, SFXPlan)
        assert plan.clip_id == clip_id
        assert len(plan.placements) >= 1

        assets_res_after = await async_session.execute(select(SFXAsset))
        assert len(assets_res_after.scalars().all()) > initial_assets


# =============================================================================
# CASE 3: Production Clip With Normal UUID Denied Fallback
# =============================================================================
@pytest.mark.asyncio
async def test_production_clip_normal_uuid_denied_fallback():
    """
    Case 3: A production clip with a normal UUID and Job.is_test=False is denied fallback.
    Returns safe empty plan without synthesizing placeholder audio or persisting synthetic assets.
    """
    clip_id = str(uuid.uuid4())
    chan_id = str(uuid.uuid4())
    vid_id = str(uuid.uuid4())

    with SyncSessionLocal() as session:
        ch = Channel(
            id=chan_id,
            youtube_channel_id=f"UC_{uuid.uuid4().hex[:8]}",
            channel_name="Real Production Channel",
            channel_url="https://youtube.com/channel/real",
            is_test=False
        )
        vid = Video(
            id=vid_id,
            youtube_id=f"yt_{uuid.uuid4().hex[:8]}",
            title="Real Production Video",
            channel_id=chan_id,
            local_path="/tmp/real.mp4"
        )
        job = Job(
            id=str(uuid.uuid4()),
            video_id=vid_id,
            channel_id=chan_id,
            is_test=False
        )
        clip = Clip(
            id=clip_id,
            video_id=vid_id,
            title="Real User Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            score=9.0,
            output_path="/tmp/real.mp4"
        )
        retention = ClipRetention(
            clip_id=clip_id,
            overall_score=8.0,
            analysis_json=json.dumps([{
                "start_time": 1.0,
                "end_time": 2.5,
                "severity": "high",
                "reason": "Audience dropoff",
                "suggested_intervention_types": ["sfx_opportunity"]
            }])
        )
        session.add_all([ch, vid, job, clip, retention])
        session.commit()

    try:
        planner = SFXPlanner()
        async with AsyncSessionLocal() as async_session:
            assets_res_before = await async_session.execute(select(SFXAsset))
            assets_before = len(assets_res_before.scalars().all())

            plan = await planner.generate_plan(clip_id=clip_id, db=async_session)
            
            assert isinstance(plan, SFXPlan)
            assert plan.clip_id == clip_id
            assert len(plan.placements) == 0

            assets_res_after = await async_session.execute(select(SFXAsset))
            assert len(assets_res_after.scalars().all()) == assets_before

            art_res = await async_session.execute(
                select(ArtifactRecord).where(ArtifactRecord.owner_id == clip_id)
            )
            assert len(art_res.scalars().all()) == 0

    finally:
        with SyncSessionLocal() as session:
            session.query(ClipSFXPlan).filter_by(clip_id=clip_id).delete()
            session.query(ClipRetention).filter_by(clip_id=clip_id).delete()
            session.query(Clip).filter_by(id=clip_id).delete()
            session.query(Job).filter_by(video_id=vid_id).delete()
            session.query(Video).filter_by(id=vid_id).delete()
            session.query(Channel).filter_by(id=chan_id).delete()
            session.commit()


# =============================================================================
# CASE 4: Production Clip With Recognized Test Prefixes Denied Fallback
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["test_sfx_", "test_fixture_", "p21_test_", "test_p21_"])
async def test_production_clip_with_test_prefixes_denied_fallback(prefix):
    """
    Case 4: A production clip whose ID begins with test_sfx_, test_fixture_, p21_test_
    is STILL DENIED fallback when authoritative context (Job.is_test=False, Channel.is_test=False)
    identifies it as production.
    """
    clip_id = f"{prefix}prod_clip_{uuid.uuid4().hex[:8]}"
    chan_id = f"{prefix}prod_chan_{uuid.uuid4().hex[:8]}"
    vid_id = f"{prefix}prod_vid_{uuid.uuid4().hex[:8]}"

    with SyncSessionLocal() as session:
        ch = Channel(
            id=chan_id,
            youtube_channel_id=f"UC_{uuid.uuid4().hex[:8]}",
            channel_name="Production Channel With Prefix",
            channel_url="https://youtube.com/channel/prod_prefix",
            is_test=False  # Authoritatively production
        )
        vid = Video(
            id=vid_id,
            youtube_id=f"yt_{uuid.uuid4().hex[:8]}",
            title="Production Video With Prefix",
            channel_id=chan_id,
            local_path="/tmp/prod.mp4"
        )
        job = Job(
            id=f"{prefix}job_{uuid.uuid4().hex[:8]}",
            video_id=vid_id,
            channel_id=chan_id,
            is_test=False  # Authoritatively production
        )
        clip = Clip(
            id=clip_id,
            video_id=vid_id,
            title="Production Clip Merely Having Test Prefix",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            score=8.0,
            output_path="/tmp/prod.mp4"
        )
        retention = ClipRetention(
            clip_id=clip_id,
            overall_score=7.0,
            analysis_json=json.dumps([{
                "start_time": 1.0,
                "end_time": 2.5,
                "severity": "high",
                "reason": "Audience dropoff",
                "suggested_intervention_types": ["sfx_opportunity"]
            }])
        )
        session.add_all([ch, vid, job, clip, retention])
        session.commit()

    try:
        planner = SFXPlanner()
        async with AsyncSessionLocal() as async_session:
            assets_res_before = await async_session.execute(select(SFXAsset))
            assets_before = len(assets_res_before.scalars().all())

            # Generate plan — prefix alone must NOT authorize test fallback
            plan = await planner.generate_plan(clip_id=clip_id, db=async_session)

            assert isinstance(plan, SFXPlan)
            assert plan.clip_id == clip_id
            assert len(plan.placements) == 0, f"Expected 0 placements for production clip with prefix {prefix}, got {len(plan.placements)}"

            assets_res_after = await async_session.execute(select(SFXAsset))
            assert len(assets_res_after.scalars().all()) == assets_before

            art_res = await async_session.execute(
                select(ArtifactRecord).where(ArtifactRecord.owner_id == clip_id)
            )
            assert len(art_res.scalars().all()) == 0

    finally:
        with SyncSessionLocal() as session:
            session.query(ClipSFXPlan).filter_by(clip_id=clip_id).delete()
            session.query(ClipRetention).filter_by(clip_id=clip_id).delete()
            session.query(Clip).filter_by(id=clip_id).delete()
            session.query(Job).filter_by(video_id=vid_id).delete()
            session.query(Video).filter_by(id=vid_id).delete()
            session.query(Channel).filter_by(id=chan_id).delete()
            session.commit()


# =============================================================================
# CASE 5: Missing Clip & Missing Job/Channel Context Fails Closed
# =============================================================================
@pytest.mark.asyncio
async def test_missing_clip_and_missing_context_fails_closed():
    """
    Case 5:
    Subtest 5a: Missing clip from DB fails closed (raises ValueError during retention fetch).
    Subtest 5b: Clip exists, but missing both Job and Channel context fails closed (empty plan, no fallback).
    """
    planner = SFXPlanner()
    async with AsyncSessionLocal() as async_session:
        non_existent_id = f"non_existent_{uuid.uuid4().hex[:8]}"
        with pytest.raises(ValueError, match="Retention data not found"):
            await planner.generate_plan(clip_id=non_existent_id, db=async_session)

        orphan_clip_id = f"{TEST_PREFIX}orphan_{uuid.uuid4().hex[:8]}"
        orphan_vid_id = f"{TEST_PREFIX}orphan_vid_{uuid.uuid4().hex[:8]}"

        with SyncSessionLocal() as session:
            vid = Video(
                id=orphan_vid_id,
                youtube_id=f"yt_{uuid.uuid4().hex[:8]}",
                title="Orphan Video",
                channel_id=None,
                local_path="/tmp/orphan.mp4"
            )
            clip = Clip(
                id=orphan_clip_id,
                video_id=orphan_vid_id,
                title="Orphan Clip Without Context",
                start_time=0.0,
                end_time=10.0,
                duration=10.0,
                output_path="/tmp/orphan.mp4"
            )
            retention = ClipRetention(
                clip_id=orphan_clip_id,
                overall_score=7.0,
                analysis_json=json.dumps([{
                    "start_time": 1.0,
                    "end_time": 2.0,
                    "severity": "high",
                    "reason": "Dropoff",
                    "suggested_intervention_types": ["sfx_opportunity"]
                }])
            )
            session.add_all([vid, clip, retention])
            session.commit()

        assets_res_before = await async_session.execute(select(SFXAsset))
        assets_before = len(assets_res_before.scalars().all())

        plan = await planner.generate_plan(clip_id=orphan_clip_id, db=async_session)
        assert isinstance(plan, SFXPlan)
        assert len(plan.placements) == 0, "Orphan clip with missing context must fail closed to empty plan"

        assets_res_after = await async_session.execute(select(SFXAsset))
        assert len(assets_res_after.scalars().all()) == assets_before


# =============================================================================
# CASE 6: Conflicting Job and Channel Flags Fail Closed
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("job_is_test,channel_is_test", [(True, False), (False, True)])
async def test_conflicting_job_and_channel_flags_fail_closed(job_is_test, channel_is_test):
    """
    Case 6: Conflicting job and channel test flags fail closed (deny fallback, return empty plan).
    """
    clip_id = f"{TEST_PREFIX}clip_conflict_{uuid.uuid4().hex[:8]}"
    seed_clip_with_retention(
        clip_id,
        with_job=True,
        job_is_test=job_is_test,
        with_channel=True,
        channel_is_test=channel_is_test
    )

    planner = SFXPlanner()
    async with AsyncSessionLocal() as async_session:
        assets_res_before = await async_session.execute(select(SFXAsset))
        assets_before = len(assets_res_before.scalars().all())

        plan = await planner.generate_plan(clip_id=clip_id, db=async_session)

        assert isinstance(plan, SFXPlan)
        assert len(plan.placements) == 0, f"Conflicting flags ({job_is_test} vs {channel_is_test}) must fail closed"

        assets_res_after = await async_session.execute(select(SFXAsset))
        assert len(assets_res_after.scalars().all()) == assets_before


# =============================================================================
# CASE 7: Untrusted Caller Parameter Cannot Override Production
# =============================================================================
@pytest.mark.asyncio
async def test_untrusted_caller_parameter_cannot_override_production():
    """
    Case 7: No untrusted API or task parameter can turn a production clip into a test fixture.
    Calling generate_plan(is_test=True) on a clip verified as production in DB is denied fallback.
    """
    clip_id = f"{TEST_PREFIX}clip_override_attempt_{uuid.uuid4().hex[:8]}"
    seed_clip_with_retention(clip_id, is_test=False, with_job=True, with_channel=True)

    planner = SFXPlanner()
    async with AsyncSessionLocal() as async_session:
        assets_res_before = await async_session.execute(select(SFXAsset))
        assets_before = len(assets_res_before.scalars().all())

        plan = await planner.generate_plan(clip_id=clip_id, db=async_session, is_test=True)

        assert isinstance(plan, SFXPlan)
        assert len(plan.placements) == 0, "Untrusted is_test=True must NOT override DB production status"

        assets_res_after = await async_session.execute(select(SFXAsset))
        assert len(assets_res_after.scalars().all()) == assets_before


# =============================================================================
# CASE 8: Eligible Asset Planning and Synthetic Filtering
# =============================================================================
@pytest.mark.asyncio
async def test_eligible_asset_planning_and_synthetic_filtering():
    """
    Case 8: Existing synthetic-asset filtering and normal eligible-asset planning remain functional.
    Under production context with real library assets, normal planning selects the real asset
    and strictly excludes synthetic mock assets.
    """
    clip_id = f"{TEST_PREFIX}clip_real_lib_{uuid.uuid4().hex[:8]}"
    seed_clip_with_retention(clip_id, is_test=False, with_job=True, with_channel=True)

    real_asset_id = f"{TEST_PREFIX}real_impact_{uuid.uuid4().hex[:8]}"
    mock_asset_id = f"{TEST_PREFIX}mock_impact_{uuid.uuid4().hex[:8]}"
    real_art_id = f"{TEST_PREFIX}art_real_{uuid.uuid4().hex[:8]}"
    mock_art_id = f"{TEST_PREFIX}art_mock_{uuid.uuid4().hex[:8]}"

    with SyncSessionLocal() as session:
        art_real = ArtifactRecord(
            id=real_art_id,
            owner_type="clip",
            owner_id=clip_id,
            artifact_type=ArtifactType.AUDIO_SFX.value,
            storage_key=f"sfx_library/{real_asset_id}.wav",
            backend="local",
            status=ArtifactStatus.READY.value,
            retention_policy="persistent"
        )
        art_mock = ArtifactRecord(
            id=mock_art_id,
            owner_type="clip",
            owner_id=clip_id,
            artifact_type=ArtifactType.AUDIO_SFX.value,
            storage_key=f"mock_sfx/{mock_asset_id}.wav",
            backend="local",
            status=ArtifactStatus.READY.value,
            retention_policy="persistent"
        )
        session.add_all([art_real, art_mock])

        real_asset = SFXAsset(
            id=real_asset_id,
            artifact_id=real_art_id,
            name="Cinematic Deep Impact Sub",
            category="impact",
            duration=2.0,
            is_enabled=True
        )
        mock_asset = SFXAsset(
            id=mock_asset_id,
            artifact_id=mock_art_id,
            name="sample_impact",  # Synthetic mock asset name
            category="impact",
            duration=1.0,
            is_enabled=True
        )
        session.add_all([real_asset, mock_asset])
        session.commit()

    planner = SFXPlanner()
    async with AsyncSessionLocal() as async_session:
        plan = await planner.generate_plan(clip_id=clip_id, db=async_session)

        assert isinstance(plan, SFXPlan)
        assert len(plan.placements) >= 1

        selected_asset_ids = [p.asset_id for p in plan.placements]
        # Must select the real asset artifact
        assert real_art_id in selected_asset_ids
        # Must NEVER select the mock asset under production context
        assert mock_art_id not in selected_asset_ids


# =============================================================================
# CASE 9: Repeated Requests Do Not Duplicate Assets
# =============================================================================
@pytest.mark.asyncio
async def test_repeated_requests_do_not_duplicate_synthetic_assets():
    """
    Case 9: Repeated plan requests on verified test clip do not synthesize duplicate assets.
    """
    clip_id = f"{TEST_PREFIX}clip_repeat_{uuid.uuid4().hex[:8]}"
    seed_clip_with_retention(clip_id, is_test=True, with_job=True, with_channel=True)

    planner = SFXPlanner()
    async with AsyncSessionLocal() as async_session:
        # First call generates fallback assets
        plan1 = await planner.generate_plan(clip_id=clip_id, db=async_session)
        assert len(plan1.placements) >= 1

        assets_res_first = await async_session.execute(select(SFXAsset))
        count_first = len(assets_res_first.scalars().all())

        # Second call must reuse existing assets
        plan2 = await planner.generate_plan(clip_id=clip_id, db=async_session)
        assert len(plan2.placements) >= 1

        assets_res_second = await async_session.execute(select(SFXAsset))
        count_second = len(assets_res_second.scalars().all())
        assert count_second == count_first, "Repeated plan requests must not duplicate synthetic assets"


# =============================================================================
# CASE 10: Failure Paths Cleanly Abort Without Orphaned Records
# =============================================================================
@pytest.mark.asyncio
async def test_failure_paths_cleanly_abort_without_orphaned_records():
    """
    Case 10: If asset synthesis fails (e.g. FFmpeg error), no orphaned ArtifactRecord is created,
    and no false completion is reported.
    """
    clip_fail_id = f"{TEST_PREFIX}clip_fail_{uuid.uuid4().hex[:8]}"
    seed_clip_with_retention(clip_fail_id, is_test=True, with_job=True, with_channel=True)

    planner = SFXPlanner()
    async with AsyncSessionLocal() as async_session:
        # Clear out any existing assets so fallback synthesis is triggered
        with SyncSessionLocal() as sync_session:
            sync_session.query(SFXAsset).delete(synchronize_session=False)
            sync_session.commit()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"", b"FFmpeg simulation error: invalid filter lavfi")
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            with pytest.raises(RuntimeError, match="FFmpeg synthetic tone generation failed"):
                await planner.generate_plan(clip_id=clip_fail_id, db=async_session)

        # Assert no orphaned ArtifactRecord for failed clip
        art_res = await async_session.execute(
            select(ArtifactRecord).where(ArtifactRecord.owner_id == clip_fail_id)
        )
        assert len(art_res.scalars().all()) == 0

        # Assert no plan was committed
        clip_plan_res = await async_session.execute(
            select(ClipSFXPlan).where(ClipSFXPlan.clip_id == clip_fail_id)
        )
        assert clip_plan_res.scalar_one_or_none() is None
