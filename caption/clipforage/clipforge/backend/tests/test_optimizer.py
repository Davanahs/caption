import pytest
from unittest.mock import patch
from backend.services.auto_optimizer import _build_reoptimize_prompt

def test_build_reoptimize_prompt_formatting():
    with patch("backend.services.ab_testing_engine.get_winning_patterns") as mock_patterns:
        mock_patterns.return_value = {
            "top_performing": [{"title": "Epic Top Title", "analytics_view_score": 9.5}],
            "bottom_performing": [{"title": "Boring Title", "analytics_view_score": 1.2}],
        }
        prompt = _build_reoptimize_prompt(
            current_title="My Initial Clip Title",
            current_tags=["viral", "shorts"],
            transcript="This is the full transcript segment of the speech.",
            view_score=4.5,
            views=250,
            likes=5,
            comments=1,
            engagement_rate=2.4,
        )
        assert "Epic Top Title" in prompt
        assert "Boring Title" in prompt
        assert "My Initial Clip Title" in prompt
        assert "ViewScore: 4.5/10" in prompt
        assert "Very low views" in prompt
