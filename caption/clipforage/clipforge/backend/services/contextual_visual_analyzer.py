import uuid
import re
from typing import List
from backend.models.broll import VisualOpportunity, OpportunityType

class ContextualVisualAnalyzer:
    """
    Analyzes the transcript to find visual opportunities (B-roll hooks).
    This is a deterministic mock since we don't have an actual LLM integrated here yet,
    similar to how the AutoSFX system works.
    """

    # Simple keyword mapping for mock generation
    KEYWORD_MAPPINGS = {
        "money": ("finance, money, cash", OpportunityType.ILLUSTRATIVE),
        "fast": ("speed, quick, blur", OpportunityType.EMPHASIS),
        "code": ("programming, computer, code", OpportunityType.EXPLANATORY),
        "AI": ("artificial intelligence, robot, futuristic", OpportunityType.CONCEPT),
        "happy": ("smiling person, joy, success", OpportunityType.PERSON),
        "nature": ("forest, outdoors, landscape", OpportunityType.ENVIRONMENT),
        "fire": ("fire, explosion, intense", OpportunityType.EMPHASIS)
    }

    @staticmethod
    def extract_opportunities(transcript: list[dict], clip_start_time: float, clip_end_time: float) -> List[VisualOpportunity]:
        """
        Takes a list of word dictionaries (from transcriber) and returns visual opportunities.
        """
        opportunities = []
        if not transcript:
            return opportunities
            
        for word_info in transcript:
            word = word_info.get("word", "").lower().strip(".,!?\"'")
            t_start = word_info.get("start", 0.0)
            t_end = word_info.get("end", t_start + 0.5)

            # Map keyword to an opportunity
            for key, (concept, opp_type) in ContextualVisualAnalyzer.KEYWORD_MAPPINGS.items():
                if key.lower() in word:
                    # Found an opportunity
                    # Make it a 2-second B-roll clip centered around the word, bounded by the clip times
                    broll_start = max(clip_start_time, t_start - 0.5)
                    broll_end = min(clip_end_time, t_start + 1.5)
                    
                    if broll_end - broll_start >= 1.0:
                        opportunities.append(
                            VisualOpportunity(
                                id=str(uuid.uuid4()),
                                start_time=broll_start,
                                end_time=broll_end,
                                concept=concept,
                                opportunity_type=opp_type,
                                confidence=0.85,
                                reason=f"Detected keyword '{key}' in transcript.",
                                preferred_visual_type="video" if opp_type != OpportunityType.DIAGRAM else "image"
                            )
                        )
                        break # Only one opportunity per word
                        
        # If no keywords matched but we have some duration, just add a random contextual one
        if not opportunities and clip_end_time - clip_start_time > 3.0:
             opportunities.append(
                VisualOpportunity(
                    id=str(uuid.uuid4()),
                    start_time=clip_start_time + 0.5,
                    end_time=min(clip_end_time, clip_start_time + 3.5),
                    concept="generic context",
                    opportunity_type=OpportunityType.CONTEXTUAL,
                    confidence=0.5,
                    reason="Fallback contextual B-roll",
                    preferred_visual_type="video"
                )
             )
        
        return opportunities
