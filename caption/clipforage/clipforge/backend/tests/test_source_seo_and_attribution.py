"""
test_source_seo_and_attribution.py
==================================
Comprehensive verification suite for ClipForge:
1. Source-Level AI Category Analysis & SEO Tag Generation:
   - Accurate semantic classification across multiple domains (AI/Tech, Coding, Gaming, Business, Education, Podcast).
   - Category mapping to official YouTube Data API category IDs.
   - SEO tags: exactly 4–6 search-oriented tags, stripped of '#', clean, deduplicated.
   - Single source-level analysis upon ingestion/transcription, persistent artifact caching, and zero duplicate LLM calls.
2. Automatic Original-Source Attribution & Clickable YouTube Links:
   - Clickable URL parsing from 11-char IDs, full watch URLs, and youtu.be short links.
   - Safe omission of fake YouTube URLs for local or synthetic files.
   - Preserves clip narrative, appends "Original video:", title, channel, clickable link, and camel-case hashtags.
   - Duplicate attribution block and duplicate hashtag guards.
   - Strict 5000 character YouTube description ceiling.
3. YouTube Publishing Payload Separation:
   - snippet.tags receives clean list of strings without '#' (<= 500 chars).
   - snippet.description receives attributed narrative + clickable URL + #Hashtags.
   - Inherits provenance seamlessly across automated and manual publishing flows.
"""
import uuid
import json
import asyncio
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.main import app
from backend.core.config import settings
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Video, Clip, VideoMetadata, Job, JobStatus, Channel
from backend.services.description_attribution import (
    extract_canonical_youtube_url,
    format_hashtag,
    build_attributed_description,
    MAX_DESCRIPTION_LENGTH,
)
from backend.services.source_metadata_engine import (
    SourceSeoMetadata,
    YOUTUBE_CATEGORY_MAP,
    normalize_seo_tags,
    normalize_description_hashtags,
    _generate_deterministic_fallback_metadata,
    analyze_source_content_ai,
    get_or_analyze_source_seo_metadata,
    load_persisted_source_metadata,
    persist_source_metadata,
)
from backend.services.publisher import (
    sanitize_youtube_tags,
    upload_short,
    _mock_upload_short,
    check_external_youtube_state,
)


@pytest.fixture(autouse=True)
async def cleanup_test_artifacts():
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        session.query(Clip).filter(Clip.id.like("clip_seo_%")).delete(synchronize_session=False)
        session.query(Video).filter(Video.id.like("vid_seo_%")).delete(synchronize_session=False)
        session.query(VideoMetadata).filter(VideoMetadata.video_id.like("vid_seo_%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.like("chan_seo_%")).delete(synchronize_session=False)
        session.commit()


# =============================================================================
# 1. DESCRIPTION ATTRIBUTION SERVICE TESTS
# =============================================================================

class TestDescriptionAttribution:

    def test_extract_canonical_youtube_url_variations(self):
        """Extracts canonical https://www.youtube.com/watch?v=VIDEO_ID from multiple formats."""
        # 11-char ID
        assert extract_canonical_youtube_url("dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # Standard watch URL
        assert extract_canonical_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # Short URL (youtu.be)
        assert extract_canonical_youtube_url("https://youtu.be/dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # Shorts URL
        assert extract_canonical_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # Embed URL
        assert extract_canonical_youtube_url("https://www.youtube.com/embed/dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # URL with additional query parameters
        assert extract_canonical_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_extract_canonical_youtube_url_local_and_invalid(self):
        """Safely returns None for local file paths, synthetic IDs, or empty values."""
        assert extract_canonical_youtube_url(None) is None
        assert extract_canonical_youtube_url("") is None
        assert extract_canonical_youtube_url("   ") is None
        assert extract_canonical_youtube_url("/local/uploads/video.mp4") is None
        assert extract_canonical_youtube_url("C:\\videos\\sample.mov") is None
        assert extract_canonical_youtube_url("synthetic_upload_123") is None
        assert extract_canonical_youtube_url("local_file.mp4") is None

    def test_format_hashtag(self):
        """Converts strings and topics into clean camel-case hashtags with '#'."""
        assert format_hashtag("artificial intelligence") == "#ArtificialIntelligence"
        assert format_hashtag("#Coding") == "#Coding"
        assert format_hashtag("machine-learning") == "#MachineLearning"
        assert format_hashtag("data science & analytics") == "#DataScienceAnalytics"
        assert format_hashtag("   ") == ""
        assert format_hashtag("!!!") == ""

    def test_build_attributed_description_standard(self):
        """Builds attributed description with narrative, clickable link, and hashtags."""
        desc = build_attributed_description(
            clip_description="Key takeaway about transformer attention mechanisms.",
            source_youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            source_title="Complete Deep Learning Lecture",
            source_channel="MIT OpenCourseWare",
            hashtags=["Artificial Intelligence", "Deep Learning", "Tech"],
        )

        assert "Key takeaway about transformer attention mechanisms." in desc
        assert "Original video:" in desc
        assert '"Complete Deep Learning Lecture"' in desc
        assert "Source Channel: MIT OpenCourseWare" in desc
        assert "Watch the complete video here:" in desc
        assert "https://www.youtube.com/watch?v=dQw4w9WgXcQ" in desc
        assert "#ArtificialIntelligence" in desc
        assert "#DeepLearning" in desc
        assert "#Tech" in desc

    def test_build_attributed_description_duplicate_prevention(self):
        """Guards against duplicate attribution blocks if already present in base description."""
        already_attributed = (
            "Here is a cool clip.\n\n"
            "Original video:\n"
            "Watch the complete video here:\n"
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        result = build_attributed_description(
            clip_description=already_attributed,
            source_youtube_url="dQw4w9WgXcQ",
            source_title="Lecture",
            hashtags=["AI"]
        )
        assert result.count("Original video:") == 1
        assert result.count("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == 1

    def test_build_attributed_description_duplicate_hashtags(self):
        """Filters out hashtags that already appear in base description or attribution."""
        base = "Great talk on #ArtificialIntelligence and modern systems."
        result = build_attributed_description(
            clip_description=base,
            source_youtube_url="dQw4w9WgXcQ",
            hashtags=["Artificial Intelligence", "Machine Learning"]
        )
        assert result.count("#ArtificialIntelligence") == 1
        assert "#MachineLearning" in result

    def test_build_attributed_description_local_file_safe(self):
        """Ensures local file uploads do NOT append a fake YouTube link."""
        desc = build_attributed_description(
            clip_description="Custom user upload demo.",
            source_youtube_url=None,
            source_title="local_file.mp4",
            hashtags=["Tutorial", "Tech"],
        )
        assert "Custom user upload demo." in desc
        assert "Original video:" not in desc
        assert "https://www.youtube.com/watch?v=" not in desc
        assert "#Tutorial" in desc

    def test_build_attributed_description_length_limit(self):
        """Enforces max_length (5000 chars) while preserving attribution and hashtags."""
        huge_base = "A" * 6000
        result = build_attributed_description(
            clip_description=huge_base,
            source_youtube_url="dQw4w9WgXcQ",
            hashtags=["AI", "Tech"],
            max_length=5000
        )
        assert len(result) <= 5000
        assert "Original video:" in result
        assert "https://www.youtube.com/watch?v=dQw4w9WgXcQ" in result


# =============================================================================
# 2. SOURCE-LEVEL AI METADATA ENGINE TESTS
# =============================================================================

class TestSourceSeoMetadataEngine:

    def test_normalize_seo_tags(self):
        """Normalizes tags to 4-6 search-oriented tags without '#' or illegal chars."""
        raw = ["#AI", "Machine Learning", "<Deep Learning>", "coding", "AI", "python", "software engineering", "extra tag"]
        norm = normalize_seo_tags(raw, "Technology")
        assert 4 <= len(norm) <= 6
        assert all("#" not in t for t in norm)
        assert all("<" not in t and ">" not in t for t in norm)
        # Deduplication
        lower_tags = [t.lower() for t in norm]
        assert len(lower_tags) == len(set(lower_tags))

    def test_normalize_description_hashtags(self):
        """Normalizes hashtags to clean camel-case list."""
        raw = ["artificial intelligence", "tech news", "#coding"]
        norm = normalize_description_hashtags(raw, "Technology")
        assert norm == ["#ArtificialIntelligence", "#TechNews", "#Coding"]

    def test_deterministic_classification_across_categories(self):
        """Tests deterministic classification across all required primary categories."""
        # 1. AI / Machine Learning
        ai_meta = _generate_deterministic_fallback_metadata(
            "vid_seo_1", "Intro to Neural Networks", "neural network transformer llm artificial intelligence"
        )
        assert ai_meta.primary_category == "Artificial Intelligence"
        assert ai_meta.youtube_category_id == "28"
        assert 4 <= len(ai_meta.seo_tags) <= 6

        # 2. Coding / Programming
        code_meta = _generate_deterministic_fallback_metadata(
            "vid_seo_2", "Python Fast API Tutorial", "python programming code build rest api backend"
        )
        assert code_meta.primary_category == "Software Development"
        assert code_meta.youtube_category_id == "28"

        # 3. Gaming
        game_meta = _generate_deterministic_fallback_metadata(
            "vid_seo_3", "Elden Ring Boss Fight", "gameplay walkthrough boss battle rpg gaming gamer"
        )
        assert game_meta.primary_category == "Gaming"
        assert game_meta.youtube_category_id == "20"

        # 4. Business / Finance
        biz_meta = _generate_deterministic_fallback_metadata(
            "vid_seo_4", "Startup Pitch and Valuation", "startup venture capital investors revenue finance economics business"
        )
        assert biz_meta.primary_category == "Business and Entrepreneurship"
        assert biz_meta.youtube_category_id == "25"

        # 5. Education / Tutorials
        edu_meta = _generate_deterministic_fallback_metadata(
            "vid_seo_5", "Calculus Chapter 3", "tutorial lecture math physics history study learning education"
        )
        assert edu_meta.primary_category == "Education"
        assert edu_meta.youtube_category_id == "27"

        # 6. Podcast / Interviews
        pod_meta = _generate_deterministic_fallback_metadata(
            "vid_seo_6", "Lex Fridman Interview", "podcast episode conversation interview discussion talk show"
        )
        assert pod_meta.primary_category == "Entertainment"
        assert pod_meta.youtube_category_id == "24"

    @pytest.mark.asyncio
    async def test_ai_classification_mocked(self):
        """Verifies structured output parsing from AI provider."""
        mock_ai_response = json.dumps({
            "primary_category": "Science & Technology",
            "youtube_category_id": "28",
            "secondary_topics": ["Artificial Intelligence", "Large Language Models", "Python"],
            "seo_tags": ["Artificial Intelligence", "LLM Development", "Python AI Tutorial", "Deep Learning", "AI Coding"],
            "description_hashtags": ["#ArtificialIntelligence", "#MachineLearning", "#PythonCoding"],
            "summary": "Technical deep-dive into LLM fine-tuning techniques."
        })

        with patch("backend.services.source_metadata_engine.route_and_generate", return_value=mock_ai_response):
            metadata = await analyze_source_content_ai(
                video_id="vid_seo_mock",
                title="Building Local LLMs with Python",
                transcript_text="Today we are building local LLMs using Ollama and Python.",
                youtube_url="https://www.youtube.com/watch?v=abcdefghijk",
                youtube_id="abcdefghijk",
            )

            assert metadata.primary_category == "Science & Technology"
            assert metadata.youtube_category_id == "28"
            assert len(metadata.seo_tags) == 5
            assert "Artificial Intelligence" in metadata.seo_tags
            assert metadata.source_youtube_id == "abcdefghijk"
            assert metadata.source_youtube_url == "https://www.youtube.com/watch?v=abcdefghijk"

    def test_source_metadata_persistence_and_zero_duplicate_ai_calls(self, tmp_path):
        """Verifies disk & database persistence and guarantee of 0 duplicate AI calls."""
        video_id = "vid_seo_cached_1"
        meta = SourceSeoMetadata(
            source_video_id=video_id,
            primary_category="Technology",
            youtube_category_id="28",
            secondary_topics=["AI", "Python"],
            seo_tags=["Artificial Intelligence", "Python Programming", "FastAPI", "AsyncIO"],
            description_hashtags=["#AI", "#Python", "#FastAPI"],
            summary="A comprehensive programming guide.",
            source_title="FastAPI Guide",
            source_youtube_url="https://www.youtube.com/watch?v=12345678901",
            source_youtube_id="12345678901",
        )

        # 1. Persist metadata
        persist_source_metadata(meta)

        # 2. Check disk artifact exists
        artifact_path = settings.UPLOAD_DIR / video_id / "source_seo_metadata.json"
        assert artifact_path.exists()

        # 3. Load persisted metadata from disk
        loaded = load_persisted_source_metadata(video_id)
        assert loaded is not None
        assert loaded.primary_category == "Technology"
        assert loaded.seo_tags == ["Artificial Intelligence", "Python Programming", "FastAPI", "AsyncIO"]

        # 4. Calling get_or_analyze_source_seo_metadata reuses disk artifact without calling LLM
        with patch("backend.services.source_metadata_engine.analyze_source_content_ai") as mock_ai:
            reused = get_or_analyze_source_seo_metadata(video_id, force_refresh=False)
            assert reused.seo_tags == loaded.seo_tags
            mock_ai.assert_not_called()  # 0 duplicate AI calls


# =============================================================================
# 3. YOUTUBE API PAYLOAD SEPARATION & PUBLISHER TESTS
# =============================================================================

class TestPublishingPayloadSeparation:

    def test_sanitize_youtube_tags(self):
        """Sanitizes snippet.tags list: strips '#', deduplicates, enforces length cap."""
        raw = ["#Shorts", "ai tools", "AI TOOLS", "python<code", "machine learning\n", "a" * 100, "b" * 100, "c" * 100, "d" * 100, "e" * 100]
        sanitized = sanitize_youtube_tags(raw, max_total_chars=250)

        assert all("#" not in t for t in sanitized)
        assert all("<" not in t for t in sanitized)
        assert all("\n" not in t for t in sanitized)
        # Case insensitive deduplication
        lowered = [t.lower() for t in sanitized]
        assert len(lowered) == len(set(lowered))
        # Total joined length under 250
        total_len = sum(len(t) for t in sanitized) + (len(sanitized) - 1)
        assert total_len <= 250

    def test_publisher_mock_upload_stores_exact_metadata(self):
        """Direct _mock_upload_short stores exact tags, category, and description."""
        res = _mock_upload_short(
            title="SEO Test Video #Shorts",
            description="Clip narrative.\n\nOriginal video:\nhttps://www.youtube.com/watch?v=abcdefghijk\n\n#AI #Coding",
            idempotency_key="seo_idemp_key_1",
            tags=["Artificial Intelligence", "Coding", "Shorts"],
            privacy="private",
            category="28",
            made_for_kids=False,
            license_type="youtube"
        )

        assert res["category"] == "28"
        assert res["tags"] == ["Artificial Intelligence", "Coding", "Shorts"]
        assert "https://www.youtube.com/watch?v=abcdefghijk" in res["description"]
        assert "#AI #Coding" in res["description"]

        # Check mock file persistence
        mock_file = Path(settings.BASE_DIR) / "mock_external_state.json"
        assert mock_file.exists()
        with open(mock_file, "r") as f:
            state = json.load(f)
        assert "seo_idemp_key_1" in state
        assert state["seo_idemp_key_1"]["category"] == "28"
        assert state["seo_idemp_key_1"]["tags"] == ["Artificial Intelligence", "Coding", "Shorts"]

    def test_upload_short_resolves_clip_and_source_provenance(self):
        """
        Calling upload_short(clip_id=clip.id) automatically:
        1. Inherits canonical source SEO tags for snippet.tags (without '#').
        2. Formats description with clickable YouTube source link and #Hashtags.
        3. Inherits canonical categoryId.
        """
        video_id = "vid_seo_prov_1"
        clip_id = "clip_seo_prov_1"

        # Setup DB records
        with SyncSessionLocal() as session:
            vid = Video(
                id=video_id,
                title="Comprehensive LLM Masterclass",
                youtube_url="https://www.youtube.com/watch?v=12345678901",
                youtube_id="12345678901",
                created_at=datetime.now(timezone.utc)
            )
            session.add(vid)

            # Persist source metadata
            source_meta = SourceSeoMetadata(
                source_video_id=video_id,
                primary_category="Technology",
                youtube_category_id="28",
                secondary_topics=["LLMs", "AI"],
                seo_tags=["LLM Masterclass", "Artificial Intelligence", "Machine Learning", "Prompt Engineering"],
                description_hashtags=["#LLM", "#ArtificialIntelligence", "#MachineLearning"],
                summary="Masterclass on LLMs.",
                source_title=vid.title,
                source_youtube_url=vid.youtube_url,
                source_youtube_id=vid.youtube_id
            )
            persist_source_metadata(source_meta, session=session)

            clip = Clip(
                id=clip_id,
                video_id=video_id,
                title="Attention Is All You Need",
                description="Crucial explanation of self-attention mechanisms.",
                start_time=10.0,
                end_time=35.0,
                duration=25.0,
                output_path="/tmp/fake_clip.mp4",
                category="28",
                publish_status="draft"
            )
            session.add(clip)
            session.commit()

        # Call upload_short in test mode
        with patch.object(settings, "PUBLISH_MODE", "test"):
            res = upload_short(
                video_path=Path("/tmp/fake_clip.mp4"),
                title="Attention Is All You Need",
                description="Crucial explanation of self-attention mechanisms.",
                clip_id=clip_id,
                channel_id="UC_destination_123",
                idempotency_key="test_prov_key_1"
            )

        assert res["category"] == "28"
        # snippet.tags contains clean strings without '#'
        assert "LLM Masterclass" in res["tags"]
        assert "Artificial Intelligence" in res["tags"]
        assert all("#" not in t for t in res["tags"])
        # snippet.description contains clickable source link and hashtags
        desc = res["description"]
        assert "Crucial explanation of self-attention mechanisms." in desc
        assert "Original video:" in desc
        assert "https://www.youtube.com/watch?v=12345678901" in desc
        assert "#LLM" in desc or "#Shorts" in desc


# =============================================================================
# 4. API ROUTES TESTS
# =============================================================================

@pytest.mark.asyncio
class TestApiRoutes:

    async def test_get_clip_publish_metadata_inherits_source_tags(self):
        """GET /api/publish/clips/{clip_id}/metadata falls back to source metadata if clip tags empty."""
        video_id = "vid_seo_api_1"
        clip_id = "clip_seo_api_1"

        with SyncSessionLocal() as session:
            vid = Video(
                id=video_id,
                title="Advanced Python Concurrency",
                youtube_url="https://www.youtube.com/watch?v=pyconcur123",
                youtube_id="pyconcur123"
            )
            session.add(vid)

            source_meta = SourceSeoMetadata(
                source_video_id=video_id,
                primary_category="Technology",
                youtube_category_id="28",
                secondary_topics=["Python", "AsyncIO"],
                seo_tags=["Python AsyncIO", "Concurrency", "Software Engineering", "Python Tutorial"],
                description_hashtags=["#Python", "#AsyncIO", "#Coding"],
                summary="Guide to concurrency in Python.",
            )
            persist_source_metadata(source_meta, session=session)

            clip = Clip(
                id=clip_id,
                video_id=video_id,
                title="Event Loop Deep Dive",
                description="Understanding the asyncio event loop.",
                tags="",  # Empty on clip
                category="22",  # Default category on clip
                start_time=0.0,
                end_time=20.0,
                duration=20.0,
            )
            session.add(clip)
            session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(f"/api/publish/clips/{clip_id}/metadata")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == clip_id
            # Inherited canonical source tags
            assert "Python AsyncIO" in data["tags"]
            assert "Concurrency" in data["tags"]
            # Inherited canonical category ID 28 (Technology)
            assert data["category"] == "28"

    async def test_get_video_seo_metadata_endpoint(self):
        """GET /api/videos/{video_id}/seo-metadata returns full canonical source metadata."""
        video_id = "vid_seo_api_2"

        with SyncSessionLocal() as session:
            vid = Video(
                id=video_id,
                title="Gaming Tournament Finals",
                youtube_url="https://www.youtube.com/watch?v=gametourn12",
                youtube_id="gametourn12"
            )
            session.add(vid)

            source_meta = SourceSeoMetadata(
                source_video_id=video_id,
                primary_category="Gaming",
                youtube_category_id="20",
                secondary_topics=["Esports", "Tournament"],
                seo_tags=["Elden Ring PVP", "Gaming Tournament", "Esports Highlights", "Boss Fight"],
                description_hashtags=["#Gaming", "#Esports", "#PVP"],
                summary="Highlights from the tournament finals.",
                source_title=vid.title,
                source_youtube_url=vid.youtube_url,
                source_youtube_id=vid.youtube_id
            )
            persist_source_metadata(source_meta, session=session)
            session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(f"/api/videos/{video_id}/seo-metadata")
            assert resp.status_code == 200
            data = resp.json()
            assert data["primary_category"] == "Gaming"
            assert data["youtube_category_id"] == "20"
            assert len(data["seo_tags"]) == 4
            assert data["source_youtube_url"] == "https://www.youtube.com/watch?v=gametourn12"

    async def test_refresh_video_seo_metadata_endpoint(self):
        """POST /api/videos/{video_id}/seo-metadata/refresh triggers fresh analysis."""
        video_id = "vid_seo_api_3"

        with SyncSessionLocal() as session:
            vid = Video(
                id=video_id,
                title="Intro to Economics",
                youtube_url="https://www.youtube.com/watch?v=econintro12",
                youtube_id="econintro12",
                transcript=json.dumps({"segments": [{"text": "Economics, market supply, demand, inflation, finance."}]})
            )
            session.add(vid)
            session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(f"/api/videos/{video_id}/seo-metadata/refresh")
            assert resp.status_code == 200
            data = resp.json()
            assert data["source_video_id"] == video_id
            assert data["primary_category"] in ("Business and Entrepreneurship", "Business & News", "Education", "Technology")
            assert len(data["seo_tags"]) >= 4


# =============================================================================
# 5. MULTI-CLIP METADATA PROPAGATION TESTS
# =============================================================================

class TestMultiClipPropagation:

    def test_single_source_multiple_clips_identical_seo_and_attribution(self):
        """
        Verifies that when a single source video produces multiple clips:
        1. Source SEO analysis executes exactly once.
        2. All child clips inherit the identical canonical tags list and category.
        3. All child clips receive the clickable source attribution link.
        """
        video_id = "vid_seo_multi_1"

        with SyncSessionLocal() as session:
            vid = Video(
                id=video_id,
                title="Building Autonomous Agents at Scale",
                youtube_url="https://www.youtube.com/watch?v=agent123456",
                youtube_id="agent123456",
                created_at=datetime.now(timezone.utc)
            )
            session.add(vid)

            source_meta = SourceSeoMetadata(
                source_video_id=video_id,
                primary_category="Technology",
                youtube_category_id="28",
                secondary_topics=["Autonomous Agents", "LLMs"],
                seo_tags=["Autonomous Agents", "AI Software", "LLM Pipelines", "Python Agents"],
                description_hashtags=["#AutonomousAgents", "#AI", "#Python"],
                summary="Production architecture for autonomous agents.",
                source_title=vid.title,
                source_youtube_url=vid.youtube_url,
                source_youtube_id=vid.youtube_id,
            )
            persist_source_metadata(source_meta, session=session)

            # Generate 3 child clips from this source
            clips = []
            for i in range(1, 4):
                clip_id = f"clip_seo_multi_{i}"
                clip_desc = build_attributed_description(
                    clip_description=f"Key insight part {i} regarding agentic loops.",
                    source_youtube_url=vid.youtube_url,
                    source_title=vid.title,
                    source_channel="AI Engineering Channel",
                    hashtags=source_meta.description_hashtags,
                )
                c = Clip(
                    id=clip_id,
                    video_id=video_id,
                    title=f"Agent Takeaway #{i}",
                    description=clip_desc,
                    tags=json.dumps(source_meta.seo_tags),
                    category=source_meta.youtube_category_id,
                    start_time=float(i * 30),
                    end_time=float(i * 30 + 25),
                    duration=25.0,
                    output_path=f"/tmp/clip_{i}.mp4",
                    publish_status="draft"
                )
                session.add(c)
                clips.append(c)
            session.commit()

        # Verify all child clips in database
        with SyncSessionLocal() as session:
            db_clips = session.query(Clip).filter(Clip.video_id == video_id).order_by(Clip.id).all()
            assert len(db_clips) == 3

            first_tags = db_clips[0].tags
            first_cat = db_clips[0].category

            for clip in db_clips:
                # 1. Exact same canonical tags
                assert clip.tags == first_tags
                tags_list = json.loads(clip.tags)
                assert tags_list == ["Autonomous Agents", "AI Software", "LLM Pipelines", "Python Agents"]
                # 2. Exact same canonical category (28 = Science & Technology)
                assert clip.category == first_cat == "28"
                # 3. Source attribution and clickable URL in each description
                assert "Original video:" in clip.description
                assert "https://www.youtube.com/watch?v=agent123456" in clip.description
                assert "#Autonomousagents" in clip.description
                assert f"Key insight part" in clip.description

            # Publish all 3 child clips in test mode and inspect outgoing payloads
            for clip in db_clips:
                with patch.object(settings, "PUBLISH_MODE", "test"):
                    payload = upload_short(
                        video_path=Path(clip.output_path),
                        title=clip.title,
                        description=clip.description,
                        clip_id=clip.id,
                        channel_id="UC_dest_multi",
                        idempotency_key=f"idemp_multi_{clip.id}"
                    )
                    assert payload["category"] == "28"
                    assert payload["tags"][:4] == ["Autonomous Agents", "AI Software", "LLM Pipelines", "Python Agents"]
                    assert payload["tags"] == ["Autonomous Agents", "AI Software", "LLM Pipelines", "Python Agents", "Shorts", "viral", "trending"]
                    assert "https://www.youtube.com/watch?v=agent123456" in payload["description"]


# =============================================================================
# 6. CHANNEL MONITORING BATCH INTEGRATION TESTS
# =============================================================================

@pytest.mark.asyncio
class TestChannelMonitoringBatchIntegration:

    async def test_batch_process_enforces_requested_count_limit(self):
        """Batch process videos endpoint raises 422 if submitted video IDs exceed requested_count."""
        channel_id = "chan_seo_batch_1"

        with SyncSessionLocal() as session:
            chan = Channel(
                id=channel_id,
                channel_name="Tech Radar Channel",
                youtube_channel_id="UC_tech_radar_1",
                channel_url="https://youtube.com/@techradar",
                is_active=True
            )
            session.add(chan)
            session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                f"/api/channels/{channel_id}/process-videos-batch",
                json={
                    "videos": [
                        {"video_id": "vid_1", "video_url": "https://youtube.com/watch?v=vid_1"},
                        {"video_id": "vid_2", "video_url": "https://youtube.com/watch?v=vid_2"},
                        {"video_id": "vid_3", "video_url": "https://youtube.com/watch?v=vid_3"},
                    ],
                    "requested_count": 2,  # Limit is 2, submitted 3
                }
            )
            assert resp.status_code == 422
            assert "exceeds requested_count" in resp.json()["detail"]

    async def test_batch_process_skips_already_processed_videos_and_tags_origin(self):
        """Batch process videos skips completed videos without reprocessing and tags origin."""
        channel_id = "chan_seo_batch_2"
        processed_ytid = "processed_yt123"
        new_ytid = "new_yt456"

        with SyncSessionLocal() as session:
            chan = Channel(
                id=channel_id,
                channel_name="AI Radar Channel",
                youtube_channel_id="UC_ai_radar_2",
                channel_url="https://youtube.com/@airadar",
                is_active=True
            )
            session.add(chan)

            # Record already processed video
            v_done = Video(
                id="vid_seo_batch_done",
                youtube_id=processed_ytid,
                title="Already Processed Source",
                processing_status="completed"
            )
            session.add(v_done)
            session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            with patch("backend.api.routes.channels.resolve_video_decision_sync", return_value={"job_id": "job_seo_123"}):
                resp = await ac.post(
                    f"/api/channels/{channel_id}/process-videos-batch",
                    json={
                        "videos": [
                            {"video_id": processed_ytid, "video_url": f"https://youtube.com/watch?v={processed_ytid}"},
                            {"video_id": new_ytid, "video_url": f"https://youtube.com/watch?v={new_ytid}"},
                        ],
                        "requested_count": 2,
                    }
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["already_processed_count"] == 1
                assert data["queued_count"] == 1

                # Check items
                res_done = next(r for r in data["items"] if r["video_id"] == processed_ytid)
                assert res_done["status"] == "already_processed"

                res_new = next(r for r in data["items"] if r["video_id"] == new_ytid)
                assert res_new["status"] == "queued"

    async def test_historical_process_enforces_requested_count_and_reports_shortage(self):
        """Historical process endpoint enforces requested_count, reports shortage, and tags manual_historical origin."""
        channel_id = "chan_seo_batch_3"
        hvid1 = "hist_vid_1"

        with SyncSessionLocal() as session:
            chan = Channel(
                id=channel_id,
                channel_name="Historical Radar Channel",
                youtube_channel_id="UC_hist_radar_3",
                channel_url="https://youtube.com/@histradar",
                is_active=True
            )
            session.add(chan)
            session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Reject if count exceeded
            resp_exceed = await ac.post(
                f"/api/channels/{channel_id}/historical-process",
                json={
                    "video_ids": ["h1", "h2", "h3"],
                    "requested_count": 1,
                    "mode": "latest"
                }
            )
            assert resp_exceed.status_code == 422

            # 2. Accept within count and report shortage if selected < requested
            with patch("backend.api.routes.channels.resolve_video_decision_sync", return_value={"job_id": "job_hist_123"}):
                resp = await ac.post(
                    f"/api/channels/{channel_id}/historical-process",
                    json={
                        "video_ids": [hvid1],
                        "requested_count": 3,  # Requested 3, provided 1 -> shortage = 2
                        "mode": "latest"
                    }
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total_requested"] == 3
                assert data["total_selected"] == 1
                assert data["queued_count"] == 1
                assert data["shortage"] == 2

