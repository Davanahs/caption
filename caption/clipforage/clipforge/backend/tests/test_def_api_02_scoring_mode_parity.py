import pytest
from pydantic import ValidationError
from backend.api.routes.channels import ChannelProcessingProfile, DEFAULT_PROCESSING_PROFILE

def test_def_api_02_scoring_mode_parity():
    # 1. Default scoring_mode is 'ai'
    profile_default = ChannelProcessingProfile()
    assert profile_default.scoring_mode == "ai"
    assert DEFAULT_PROCESSING_PROFILE["scoring_mode"] == "ai"

    # 2. Explicit 'ai' is accepted
    profile_ai = ChannelProcessingProfile(scoring_mode="ai")
    assert profile_ai.scoring_mode == "ai"

    # 3. 'heuristic' is rejected per PREREQ-008 zero-heuristic policy
    with pytest.raises(ValidationError):
        ChannelProcessingProfile(scoring_mode="heuristic")

    # 4. Arbitrary invalid values rejected
    for invalid in ["random", "fallback", "test", ""]:
        with pytest.raises(ValidationError):
            ChannelProcessingProfile(scoring_mode=invalid)
