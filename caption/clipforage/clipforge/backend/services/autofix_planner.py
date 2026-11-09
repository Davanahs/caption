import copy
from backend.models.layout import LayoutPlan, ZoomIntervention, LayoutMode
from backend.models.retention import DropoffRisk
from typing import List
import logging

logger = logging.getLogger(__name__)

class AutoFixPlanner:
    def __init__(self, default_zoom_factor: float = 1.15):
        self.default_zoom_factor = default_zoom_factor
        
    def generate_plan(self, original_plan: LayoutPlan, risks: List[DropoffRisk]) -> LayoutPlan:
        """
        Creates a new variant of the LayoutPlan that applies zoom interventions
        during identified dropoff risk zones.
        """
        new_plan = copy.deepcopy(original_plan)
        
        has_zoom = False
        for risk in risks:
            # We only act on risks that have "zoom_push" suggested
            if "zoom_push" not in risk.suggested_intervention_types:
                continue
                
            # Create a ZoomIntervention
            intervention = ZoomIntervention(
                start_time=risk.start_time,
                end_time=risk.end_time,
                zoom_factor=self.default_zoom_factor
            )
            
            # Apply to all regions in the plan
            for region in new_plan.regions:
                region.zoom_interventions.append(intervention)
                has_zoom = True

        if has_zoom and new_plan.mode == LayoutMode.CENTER_CROP:
            new_plan.mode = LayoutMode.STATIC_WIDE
                
        return new_plan
