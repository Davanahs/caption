"""
Phase 2 Comprehensive Test Suite:
- PREREQ-007: Shorts Duration Ceiling & Duration Consistency (15s - 60s)
- PREREQ-008: AI-Provider Reliability & Zero Heuristic Fallback
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
from pydantic import ValidationError

from backend.api.routes.videos import validate_clip_mode_and_duration
from backend.services.llm_router import is_ai_provider_configured, route_and_generate
from backend.services.clip_scorer import ai_score_candidates
from backend.services.output_validator import validate_video_output, OutputValidatorError
from backend.api.routes.channels import ChannelProcessingProfile


class TestPhase2DurationValidation:
    """Tests PREREQ-007 duration bounds enforcement."""

    def test_duration_accepts_valid_bounds(self):
        with patch("backend.services.llm_router.is_ai_provider_configured", return_value=True):
            for dur in [15, 30, 45, 49, 60]:
                mode = validate_clip_mode_and_duration("ai_highlights", max_clip_duration=dur, target_duration=None)
                assert mode == "ai_highlights"
                mode_split = validate_clip_mode_and_duration("equal_split", max_clip_duration=None, target_duration=float(dur))
                assert mode_split == "equal_split"

    def test_duration_rejects_sub_15s(self):
        with patch("backend.services.llm_router.is_ai_provider_configured", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                validate_clip_mode_and_duration("ai_highlights", max_clip_duration=14, target_duration=None)
            assert exc_info.value.status_code == 400
            assert "between 15 and 60" in exc_info.value.detail

            with pytest.raises(HTTPException) as exc_info2:
                validate_clip_mode_and_duration("equal_split", max_clip_duration=None, target_duration=10.0)
            assert exc_info2.value.status_code == 400
            assert "between 15.0 and 60.0" in exc_info2.value.detail

    def test_duration_rejects_over_60s(self):
        with patch("backend.services.llm_router.is_ai_provider_configured", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                validate_clip_mode_and_duration("ai_highlights", max_clip_duration=61, target_duration=None)
            assert exc_info.value.status_code == 400
            assert "between 15 and 60" in exc_info.value.detail

            with pytest.raises(HTTPException) as exc_info2:
                validate_clip_mode_and_duration("equal_split", max_clip_duration=None, target_duration=90.0)
            assert exc_info2.value.status_code == 400

    def test_invalid_clip_mode_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_clip_mode_and_duration("random_mode", max_clip_duration=30, target_duration=None)
        assert exc_info.value.status_code == 400
        assert "Invalid clip_mode" in exc_info.value.detail

    def test_channel_profile_duration_bounds(self):
        # Valid profile with 60s ceiling
        profile = ChannelProcessingProfile(
            min_clip_duration=15.0,
            max_clip_duration=60.0,
            target_duration=49.0,
            scoring_mode="ai"
        )
        assert profile.max_clip_duration == 60.0

        # Reject duration over 60s
        with pytest.raises(ValidationError):
            ChannelProcessingProfile(max_clip_duration=65.0)

        # Reject duration under 15s
        with pytest.raises(ValidationError):
            ChannelProcessingProfile(min_clip_duration=10.0)

        # Reject heuristic scoring_mode
        with pytest.raises(ValidationError):
            ChannelProcessingProfile(scoring_mode="heuristic")


class TestPhase2OutputValidatorDurations:
    """Tests output_validator shorts ceiling up to 60s with tolerance."""

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    @patch("subprocess.run")
    def test_validator_accepts_up_to_60s(self, mock_run, mock_stat, mock_exists):
        mock_stat.return_value = MagicMock(st_size=1024)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"format": {"duration": "59.8"}, "streams": [{"codec_type": "video", "width": 1080, "height": 1920}, {"codec_type": "audio"}]}'
        )
        res = validate_video_output("dummy.mp4", max_duration=60.0, expected_duration=60.0, duration_tolerance=1.5)
        assert res is True

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    @patch("subprocess.run")
    def test_validator_rejects_exceeding_shorts_limit(self, mock_run, mock_stat, mock_exists):
        mock_stat.return_value = MagicMock(st_size=1024)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"format": {"duration": "62.5"}, "streams": [{"codec_type": "video", "width": 1080, "height": 1920}]}'
        )
        with pytest.raises(OutputValidatorError) as exc_info:
            validate_video_output("dummy.mp4", max_duration=60.0)
        assert "exceeds maximum Shorts duration limit of 60.0s" in str(exc_info.value)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    @patch("subprocess.run")
    def test_validator_enforces_expected_duration_tolerance(self, mock_run, mock_stat, mock_exists):
        # Expected 49s, probe returns 52s (exceeds 1.5s tolerance)
        mock_stat.return_value = MagicMock(st_size=1024)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"format": {"duration": "52.0"}, "streams": [{"codec_type": "video", "width": 1080, "height": 1920}]}'
        )
        with pytest.raises(OutputValidatorError) as exc_info:
            validate_video_output("dummy.mp4", max_duration=60.0, expected_duration=49.0, duration_tolerance=1.5)
        assert "Duration mismatch" in str(exc_info.value)


class TestPhase2AIReliabilityAndZeroFallback:
    """Tests PREREQ-008: AI intake gating, router failover, and zero heuristic fallback."""

    def test_ai_highlights_intake_rejected_without_ai_key(self):
        with patch("backend.services.llm_router.is_ai_provider_configured", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                validate_clip_mode_and_duration("ai_highlights", max_clip_duration=30, target_duration=None)
            assert exc_info.value.status_code == 503
            assert "No AI provider configured" in exc_info.value.detail

    def test_equal_split_intake_accepted_without_ai_key(self):
        with patch("backend.services.llm_router.is_ai_provider_configured", return_value=False):
            mode = validate_clip_mode_and_duration("equal_split", max_clip_duration=None, target_duration=30.0)
            assert mode == "equal_split"

    @pytest.mark.asyncio
    async def test_zero_heuristic_fallback_on_scoring_failure(self):
        """When AI scoring fails, it must raise RuntimeError and NEVER return heuristic fallback."""
        candidates = [
            {"start": 10.0, "end": 40.0, "duration": 30.0, "text": "Segment A", "score": 0.5},
            {"start": 45.0, "end": 75.0, "duration": 30.0, "text": "Segment B", "score": 0.5},
        ]
        with patch("backend.services.clip_scorer.route_and_generate", side_effect=Exception("API connection refused")):
            with pytest.raises(RuntimeError) as exc_info:
                await ai_score_candidates(candidates, top_n=2)
            assert "AI candidate scoring failed" in str(exc_info.value)
            assert "Heuristic scoring fallback is strictly forbidden" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_zero_heuristic_fallback_on_empty_response(self):
        """When LLM returns empty/invalid list, it must raise RuntimeError, not fabricate scores."""
        candidates = [
            {"start": 10.0, "end": 40.0, "duration": 30.0, "text": "Segment A", "score": 0.5},
        ]
        with patch("backend.services.clip_scorer.route_and_generate", return_value="   "):
            with pytest.raises(RuntimeError) as exc_info:
                await ai_score_candidates(candidates, top_n=1)
            assert "Cloud AI provider returned empty or invalid response" in str(exc_info.value)
            assert "Heuristic scoring fallback is strictly forbidden" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_router_failover_to_nvidia(self):
        """When OpenRouter fails, router automatically fails over to Nvidia NIM."""
        with patch("backend.core.config.settings.OPENROUTER_API_KEY", "fake-openrouter-key"), \
             patch("backend.core.config.settings.NVIDIA_API_KEY", "fake-nvidia-key"), \
             patch("backend.core.config.settings.OPENROUTER_MODEL", "meta-llama/llama-3-8b"), \
             patch("backend.core.config.settings.NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct"), \
             patch("backend.services.llm_router.get_ranked_openrouter_models", AsyncMock(return_value=[])), \
             patch("backend.services.llm_router.query_openrouter", side_effect=Exception("OpenRouter connection error")), \
             patch("backend.services.llm_router.query_nvidia_nim", AsyncMock(return_value="Nvidia response successfully generated")):

            result = await route_and_generate("Test prompt")
            assert result == "Nvidia response successfully generated"
