import logging
import uuid
from typing import List, Optional
from backend.models.hook import HookOpportunity, HookOpportunityType
from backend.models.models import Clip, ContentAnalysis, ClipRetention
from backend.models.retention import RetentionAnalysis

logger = logging.getLogger(__name__)

class HookAnalyzer:
    def __init__(self):
        pass

    def analyze_clip_for_hooks(
        self,
        clip: Clip,
        transcript_text: Optional[str],
        content_analysis: Optional[ContentAnalysis],
        retention_data: Optional[RetentionAnalysis],
        clip_duration: float
    ) -> List[HookOpportunity]:
        opportunities = []

        # 1. Always evaluate the opening (0-3s)
        # If there is retention data indicating a dropoff in the first 5 seconds, prioritize it
        has_retention_risk = False
        if retention_data and retention_data.risks:
            for risk in retention_data.risks:
                if risk.start_time <= 5.0 and risk.severity in ["high", "medium"]:
                    has_retention_risk = True
                    break
        
        opening_type = HookOpportunityType.RETENTION_RISK if has_retention_risk else HookOpportunityType.OPENING_HOOK
        confidence = 0.9 if has_retention_risk else 0.7
        
        opening_opp = HookOpportunity(
            id=str(uuid.uuid4()),
            clip_id=clip.id,
            start_time=0.0,
            end_time=min(3.0, clip_duration),
            opportunity_type=opening_type,
            source_text=transcript_text[:100] if transcript_text else None,
            hook_objective="Capture immediate attention to prevent scroll.",
            confidence=confidence,
            reason="Retention risk in opening seconds." if has_retention_risk else "Default opening hook opportunity.",
            priority=100
        )
        opportunities.append(opening_opp)

        # 2. Look at content analysis (if available) for key statements
        if content_analysis and content_analysis.analysis_json:
            import json
            try:
                data = json.loads(content_analysis.analysis_json)
                topics = data.get("topics", [])
                if topics and clip_duration > 10.0:
                    # Let's say we find a transition or strong topic around 5-10s
                    mid_opp = HookOpportunity(
                        id=str(uuid.uuid4()),
                        clip_id=clip.id,
                        start_time=min(5.0, clip_duration - 2.0),
                        end_time=min(8.0, clip_duration),
                        opportunity_type=HookOpportunityType.VALUE_STATEMENT,
                        source_text="Topic: " + str(topics[0]),
                        hook_objective="Re-engage viewer with core value.",
                        confidence=0.8,
                        reason="Content analysis indicates primary topic discussion.",
                        priority=50
                    )
                    opportunities.append(mid_opp)
            except Exception as e:
                logger.warning(f"Failed to parse content analysis for hook analyzer: {e}")

        return opportunities

hook_analyzer = HookAnalyzer()
