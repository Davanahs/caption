"""
Phase 13 Verification Script
Tests: HookAnalyzer, HookPlanner, VoiceoverEngine, SFXMixer integration, model validation.
"""
import sys
import os
import json
import asyncio
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models.hook import (
    HookOpportunity, HookOpportunityType, HookConcept, HookStyle,
    DeliveryMode, VoiceoverSegment, VoiceoverPlan, VoiceoverArtifact,
    HookPlan, DuckingPolicy
)
from backend.models.layout import ZoomIntervention

PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        print(f"  ❌ {label} — {detail}")

# ──── 1. Model Validation ────
print("\n═══ 1. Pydantic Model Validation ═══")

opp = HookOpportunity(
    id="test-opp-1",
    clip_id="test-clip",
    start_time=0.0,
    end_time=3.0,
    opportunity_type=HookOpportunityType.OPENING_HOOK,
    hook_objective="Capture attention",
    confidence=0.9,
    reason="Opening hook test",
    priority=100
)
check("HookOpportunity creates successfully", opp.id == "test-opp-1")
check("HookOpportunity type is correct", opp.opportunity_type == HookOpportunityType.OPENING_HOOK)

# Validate time constraint
try:
    bad = HookOpportunity(
        id="bad", clip_id="x", start_time=5.0, end_time=3.0,
        opportunity_type=HookOpportunityType.OPENING_HOOK,
        hook_objective="x", confidence=0.5, reason="x"
    )
    check("HookOpportunity rejects end < start", False, "Should have raised")
except Exception:
    check("HookOpportunity rejects end < start", True)

concept = HookConcept(
    opportunity_id="test-opp-1",
    hook_style=HookStyle.CURIOSITY,
    hook_text="Wait, you need to see this!",
    target_duration=2.5,
    delivery_mode=DeliveryMode.COMBINED,
    confidence=0.85
)
check("HookConcept creates successfully", concept.hook_style == HookStyle.CURIOSITY)

vo_art = VoiceoverArtifact(
    artifact_id="vo-1", storage_key="/tmp/vo.wav",
    provider="mock_voice", duration=2.5, sample_rate=44100, format="wav"
)
check("VoiceoverArtifact creates with storage_key", vo_art.storage_key == "/tmp/vo.wav")
check("VoiceoverArtifact has artifact_id", vo_art.artifact_id == "vo-1")

segment = VoiceoverSegment(
    source_text="Hook text", start_time=0.0, end_time=2.5,
    voice_id="narrator_1", speaking_rate=1.1, gain=1.2,
    fade_in=0.1, fade_out=0.1,
    ducking_policy=DuckingPolicy.MODERATE, confidence=0.9
)
check("VoiceoverSegment creates successfully", segment.ducking_policy == DuckingPolicy.MODERATE)

# Validate fade constraint
try:
    bad_seg = VoiceoverSegment(
        source_text="x", start_time=0.0, end_time=1.0,
        voice_id="x", fade_in=0.8, fade_out=0.8, confidence=0.5
    )
    check("VoiceoverSegment rejects fades > duration", False, "Should have raised")
except Exception:
    check("VoiceoverSegment rejects fades > duration", True)

zoom = ZoomIntervention(start_time=0.0, end_time=2.5, zoom_factor=1.2)
check("ZoomIntervention creates", zoom.zoom_factor == 1.2)

vo_plan = VoiceoverPlan(clip_id="test-clip", segments=[segment])
check("VoiceoverPlan creates with segments", len(vo_plan.segments) == 1)

plan = HookPlan(
    clip_id="test-clip",
    opportunities=[opp],
    concepts=[concept],
    voiceover_plan=vo_plan,
    visual_interventions=[zoom]
)
check("HookPlan creates with all components", len(plan.visual_interventions) == 1)
check("HookPlan has no caption/subtitle field", not hasattr(plan, 'subtitles') and not hasattr(plan, 'captions'))

# ──── 2. HookAnalyzer ────
print("\n═══ 2. HookAnalyzer ═══")

from backend.models.database import SyncSessionLocal
from backend.models.models import Clip
from backend.services.hook_analyzer import hook_analyzer

with SyncSessionLocal() as session:
    clip = session.query(Clip).filter_by(id="9190e97f-4cfc-4311-8825-25fd73446b86").first()
    if clip:
        duration = clip.end_time - clip.start_time
        opps = hook_analyzer.analyze_clip_for_hooks(
            clip=clip,
            transcript_text=None,
            content_analysis=None,
            retention_data=None,
            clip_duration=duration
        )
        check("HookAnalyzer returns opportunities", len(opps) > 0)
        check("First opportunity is opening hook", opps[0].opportunity_type in [HookOpportunityType.OPENING_HOOK, HookOpportunityType.RETENTION_RISK])
        check("Opportunity times are bounded", all(o.end_time <= duration for o in opps))
        check("Opportunity times are non-negative", all(o.start_time >= 0 for o in opps))
    else:
        check("Test clip exists", False, "Clip 9190e97f not found")

# ──── 3. HookPlanner ────
print("\n═══ 3. HookPlanner ═══")

from backend.services.hook_planner import hook_planner

if opps:
    generated_plan = hook_planner.generate_hook_plan(
        clip_id="9190e97f-4cfc-4311-8825-25fd73446b86",
        opportunities=opps
    )
    check("HookPlanner generates plan", generated_plan is not None)
    check("Plan has concepts", len(generated_plan.concepts) > 0)
    check("Plan has visual interventions", len(generated_plan.visual_interventions) > 0)
    check("Plan has voiceover plan", generated_plan.voiceover_plan is not None)
    check("Plan has deterministic hash", generated_plan.plan_hash is not None and len(generated_plan.plan_hash) == 64)
    check("Visual zoom bounded ≤ 1.5x", all(z.zoom_factor <= 1.5 for z in generated_plan.visual_interventions))

    # Verify no caption/subtitle contamination
    plan_json_str = generated_plan.model_dump_json()
    check("No 'subtitle' in plan JSON", "subtitle" not in plan_json_str.lower())
    check("No '.srt' in plan JSON", ".srt" not in plan_json_str.lower())
    check("No 'caption' in plan JSON", "caption" not in plan_json_str.lower())

# ──── 4. VoiceoverEngine (MockVoiceProvider) ────
print("\n═══ 4. VoiceoverEngine (MockVoiceProvider) ═══")

from backend.services.voiceover_engine import voiceover_engine

async def test_voiceover():
    with tempfile.TemporaryDirectory() as td:
        seg = VoiceoverSegment(
            source_text="This is a test hook",
            start_time=0.0, end_time=2.0,
            voice_id="mock_narrator_1",
            speaking_rate=1.0, gain=1.0,
            fade_in=0.1, fade_out=0.1,
            ducking_policy=DuckingPolicy.MODERATE,
            confidence=0.9
        )
        arts = await voiceover_engine.execute_plan("test-clip", [seg], Path(td))
        check("VoiceoverEngine returns artifacts", len(arts) == 1)
        art = arts[0]
        check("Artifact has artifact_id", bool(art.artifact_id))
        check("Artifact has storage_key", bool(art.storage_key))
        check("Artifact provider is mock_voice", art.provider == "mock_voice")
        check("Artifact duration > 0", art.duration > 0)
        check("Generated file exists on disk", Path(art.storage_key).exists())
        
        fsize = Path(art.storage_key).stat().st_size
        check("Generated file is non-empty", fsize > 0, f"Size: {fsize}")
        
        return art

loop = asyncio.new_event_loop()
vo_artifact = loop.run_until_complete(test_voiceover())
loop.close()
check("MOCK VOICE VERIFIED (not real voice)", vo_artifact.provider == "mock_voice")

# ──── 5. SFXMixer accepts VoiceoverPlan ────
print("\n═══ 5. SFXMixer Integration ═══")

from backend.services.sfx_mixer import SFXMixer

check("SFXMixer.build_ffmpeg_command accepts voiceover_plan param",
      'voiceover_plan' in SFXMixer.build_ffmpeg_command.__code__.co_varnames)

# Test with empty plan (passthrough)
async def test_mixer_passthrough():
    cmd = await SFXMixer.build_ffmpeg_command(
        video_input_path="dummy.mp4",
        sfx_plan=None,
        output_path="out.mp4",
        artifact_manager=None,
        voiceover_plan=None
    )
    return cmd

loop2 = asyncio.new_event_loop()
passthrough_cmd = loop2.run_until_complete(test_mixer_passthrough())
loop2.close()
check("SFXMixer passthrough returns copy command", "copy" in passthrough_cmd)

# ──── 6. LayoutEngine ZoomIntervention ────
print("\n═══ 6. LayoutEngine ZoomIntervention ═══")

from backend.services.layout_engine import LayoutEngine

plan = LayoutEngine.create_vertical_plan(1920, 1080)
plan.regions[0].zoom_interventions = [ZoomIntervention(start_time=0.0, end_time=2.5, zoom_factor=1.2)]
filtergraph = LayoutEngine.build_render_graph(plan, [Path("dummy.mp4")])
check("Filtergraph contains zoom crop", "zoomed_" in filtergraph)
check("Filtergraph references zoom factor", "1.2" in filtergraph)
check("Filtergraph has no subtitle/caption filter", "subtitles" not in filtergraph and "drawtext" not in filtergraph)

# ──── 7. Database Schema ────
print("\n═══ 7. Database Schema ═══")

from backend.models.models import ClipHookPlan
check("ClipHookPlan model exists", ClipHookPlan is not None)
check("ClipHookPlan has clip_id", hasattr(ClipHookPlan, 'clip_id'))
check("ClipHookPlan has plan_json", hasattr(ClipHookPlan, 'plan_json'))
check("ClipHookPlan has plan_hash", hasattr(ClipHookPlan, 'plan_hash'))

with SyncSessionLocal() as session:
    from sqlalchemy import text
    result = session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'clip_hook_plans'"))
    cols = [r[0] for r in result.fetchall()]
    check("clip_hook_plans table exists in DB", len(cols) > 0, f"Columns: {cols}")
    check("clip_hook_plans has clip_id column", "clip_id" in cols)
    check("clip_hook_plans has plan_json column", "plan_json" in cols)

# ──── 8. API Routes ────
print("\n═══ 8. API Routes ═══")

with open("backend/api/routes/clips.py") as f:
    routes_text = f.read()

check("GET /{clip_id}/hook route exists", "get_hook_plan" in routes_text)
check("POST /{clip_id}/hook/plan route exists", "generate_hook_plan_endpoint" in routes_text)
check("POST /{clip_id}/hook/apply route exists", "apply_hook_plan_endpoint" in routes_text)

# ──── Summary ────
print(f"\n{'═'*50}")
print(f"Phase 13 Verification: {PASS} passed, {FAIL} failed")
print(f"{'═'*50}")

if FAIL > 0:
    print("⚠️  Some tests failed. Review above for details.")
    sys.exit(1)
else:
    print("✅ All Phase 13 verification checks passed!")
    sys.exit(0)
