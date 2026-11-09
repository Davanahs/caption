import hashlib
import json
import logging
from typing import List, Optional
from datetime import datetime, timezone
from backend.models.hook import (
    HookOpportunity, HookConcept, HookPlan, HookStyle, DeliveryMode,
    VoiceoverPlan, VoiceoverSegment, DuckingPolicy
)
from backend.models.layout import ZoomIntervention

logger = logging.getLogger(__name__)

class HookPlanner:
    def __init__(self):
        self.planner_version = "1.0.0"

    def generate_hook_plan(
        self,
        clip_id: str,
        opportunities: List[HookOpportunity],
        source_analysis_version: Optional[str] = None
    ) -> HookPlan:
        
        concepts = []
        visual_interventions = []
        vo_segments = []
        
        for opp in opportunities:
            # Deterministic selection for demonstration/safety
            # A real LLM call here would be strictly validated against these limits
            
            # Select style based on opportunity type
            style = HookStyle.CURIOSITY
            if opp.opportunity_type == "retention_risk":
                style = HookStyle.URGENCY
            elif opp.opportunity_type == "value_statement":
                style = HookStyle.DIRECT_VALUE
                
            # Determine content
            hook_text = f"Wait, you need to see this! ({style.value})"
            target_duration = min(2.5, opp.end_time - opp.start_time)
            if target_duration < 0.5:
                continue # Skip if too short
            
            concept = HookConcept(
                opportunity_id=opp.id,
                hook_style=style,
                hook_text=hook_text,
                target_duration=target_duration,
                delivery_mode=DeliveryMode.COMBINED,
                confidence=0.85,
                planner_version=self.planner_version
            )
            concepts.append(concept)
            
            # Visual Intervention: Zoom/Punch-in
            # Bound the zoom to 1.2x
            zoom = ZoomIntervention(
                start_time=opp.start_time,
                end_time=opp.start_time + target_duration,
                zoom_factor=1.2
            )
            visual_interventions.append(zoom)
            
            # Voiceover Segment
            vo = VoiceoverSegment(
                source_text=hook_text,
                start_time=opp.start_time,
                end_time=opp.start_time + target_duration,
                voice_id="mock_narrator_1",
                speaking_rate=1.1,
                gain=1.2,
                fade_in=0.1,
                fade_out=0.1,
                ducking_policy=DuckingPolicy.MODERATE,
                confidence=0.9
            )
            vo_segments.append(vo)

        vo_plan = VoiceoverPlan(
            clip_id=clip_id,
            planner_version=self.planner_version,
            analysis_version=source_analysis_version,
            segments=vo_segments,
            generated_timestamp=datetime.now(timezone.utc).timestamp()
        )

        plan = HookPlan(
            clip_id=clip_id,
            planner_version=self.planner_version,
            source_analysis_version=source_analysis_version,
            opportunities=opportunities,
            concepts=concepts,
            voiceover_plan=vo_plan,
            visual_interventions=visual_interventions
        )
        
        # Calculate deterministic hash
        plan_dict = plan.model_dump(exclude={'plan_hash': True, 'voiceover_plan': {'generated_timestamp'}})
        plan.plan_hash = hashlib.sha256(json.dumps(plan_dict, sort_keys=True, default=str).encode()).hexdigest()
        vo_plan.plan_hash = plan.plan_hash
        
        return plan

hook_planner = HookPlanner()
