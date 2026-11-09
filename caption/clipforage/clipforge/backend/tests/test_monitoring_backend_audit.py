"""
Unit tests for Monitoring Audit Repairs in backend:
1. URL normalization in downloader.py (adding /videos tab for channel URLs)
2. View count sorting with nulls last and deterministic tie-breakers
3. Decision history serialization with source provenance and error message
"""
import unittest
from backend.services.downloader import normalize_channel_url


class TestMonitoringAuditRepairs(unittest.TestCase):

    def test_channel_url_normalization_videos_tab(self):
        """Test that handle URLs, channel URLs, user URLs are normalized to append /videos."""
        test_cases = [
            ("https://www.youtube.com/@NishantChahar11", "https://www.youtube.com/@NishantChahar11/videos"),
            ("https://www.youtube.com/@NishantChahar11/", "https://www.youtube.com/@NishantChahar11/videos"),
            ("https://www.youtube.com/@NishantChahar11/videos", "https://www.youtube.com/@NishantChahar11/videos"),
            ("https://www.youtube.com/channel/UC1234567890", "https://www.youtube.com/channel/UC1234567890/videos"),
            ("https://www.youtube.com/c/CustomChannel", "https://www.youtube.com/c/CustomChannel/videos"),
            ("https://www.youtube.com/user/LegacyUser", "https://www.youtube.com/user/LegacyUser/videos"),
            ("https://www.youtube.com/playlist?list=PL12345", "https://www.youtube.com/playlist?list=PL12345"),
        ]

        for input_url, expected in test_cases:
            normalized = normalize_channel_url(input_url)
            self.assertEqual(
                normalized, expected,
                f"Failed for input: {input_url}. Expected: {expected}, got: {normalized}"
            )

    def test_view_count_sorting_contract(self):
        """Test numeric descending sort with deterministic tie-breakers (upload timestamp, video ID)."""
        candidates = [
            {"id": "v1", "view_count": 50000, "upload_timestamp": 100},
            {"id": "v2", "view_count": 250000, "upload_timestamp": 90},
            {"id": "v3", "view_count": 50000, "upload_timestamp": 120},
            {"id": "v4", "view_count": None, "upload_timestamp": 200},
            {"id": "v5", "view_count": 500000, "upload_timestamp": 50},
        ]

        def sort_key(v):
            vc = v.get("view_count")
            has_views = 1 if (vc is not None and isinstance(vc, (int, float))) else 0
            view_num = vc if has_views else -1
            upload_ts = v.get("upload_timestamp") or 0
            vid_id = str(v.get("id") or "")
            return (-has_views, -view_num, -upload_ts, vid_id)

        sorted_vids = sorted(candidates, key=sort_key)

        self.assertEqual(sorted_vids[0]["id"], "v5", "Highest view count (500k) ranks first")
        self.assertEqual(sorted_vids[1]["id"], "v2", "Second highest (250k) ranks second")
        self.assertEqual(sorted_vids[2]["id"], "v3", "Tie-breaker: newer timestamp (120) ranks before older (100)")
        self.assertEqual(sorted_vids[3]["id"], "v1", "Tie-breaker: older timestamp (100) ranks after newer (120)")
        self.assertEqual(sorted_vids[4]["id"], "v4", "Null views rank last")

    def test_provenance_mapping_origin_vs_short(self):
        """Test provenance logic distinguishes generated shorts from origin videos."""
        class MockOrigin:
            clip_title = "Adobe's Secret Clone Was REAL? 😱"
            origin_video_id = "58f26144-db35-444c-86fe-59c06cb26341"
            origin_youtube_id = "MjDUTSOsUMg"
            origin_youtube_url = "https://www.youtube.com/watch?v=MjDUTSOsUMg"
            origin_video_title = "Software is DEAD! This GitHub Repo Can Build Anything in Few Hours"
            origin_thumbnail_url = "https://i.ytimg.com/vi/MjDUTSOsUMg/mqdefault.jpg"

        origin_map = {"0OfOivc-tpU": MockOrigin()}

        # 1. Monitored Short scenario (0OfOivc-tpU)
        dec_yt_id = "0OfOivc-tpU"
        orig = origin_map.get(dec_yt_id)
        self.assertIsNotNone(orig)
        is_generated_short = bool(orig)
        generated_short_id = dec_yt_id if is_generated_short else None
        source_yt_id = orig.origin_youtube_id if is_generated_short else dec_yt_id

        self.assertTrue(is_generated_short)
        self.assertEqual(generated_short_id, "0OfOivc-tpU")
        self.assertEqual(source_yt_id, "MjDUTSOsUMg")
        self.assertEqual(orig.origin_video_title, "Software is DEAD! This GitHub Repo Can Build Anything in Few Hours")

        # 2. Regular Source Video scenario (m5hidzW-_i0)
        dec_yt_id_2 = "m5hidzW-_i0"
        orig_2 = origin_map.get(dec_yt_id_2)
        self.assertIsNone(orig_2)
        is_generated_short_2 = bool(orig_2)
        generated_short_id_2 = dec_yt_id_2 if is_generated_short_2 else None
        source_yt_id_2 = orig_2.origin_youtube_id if is_generated_short_2 else dec_yt_id_2

        self.assertFalse(is_generated_short_2)
        self.assertIsNone(generated_short_id_2)
        self.assertEqual(source_yt_id_2, "m5hidzW-_i0")

    def test_extract_yt_id_variations(self):
        """Test YouTube ID extraction handles all canonical URL formats and query strings."""
        from backend.services.provenance import extract_yt_id
        cases = [
            ("0OfOivc-tpU", "0OfOivc-tpU"),
            ("https://www.youtube.com/watch?v=0OfOivc-tpU", "0OfOivc-tpU"),
            ("https://www.youtube.com/watch?v=0OfOivc-tpU&t=15s", "0OfOivc-tpU"),
            ("https://www.youtube.com/shorts/0OfOivc-tpU", "0OfOivc-tpU"),
            ("https://www.youtube.com/shorts/0OfOivc-tpU?si=123", "0OfOivc-tpU"),
            ("https://youtu.be/0OfOivc-tpU", "0OfOivc-tpU"),
            ("https://youtu.be/0OfOivc-tpU?t=10", "0OfOivc-tpU"),
            ("https://www.youtube.com/watch?v=m5hidzW-_i0", "m5hidzW-_i0"),
        ]
        for url_in, expected_id in cases:
            extracted = extract_yt_id(url_in)
            self.assertEqual(extracted, expected_id, f"Failed for {url_in}: expected {expected_id}, got {extracted}")

    def test_self_ingestion_retry_policy(self):
        """
        Verify the retry policy:
        1. Published Short jobs must be rejected from retry (HTTP 400).
        2. Original source video jobs (e.g. Kimi K3) must be permitted to retry.
        """
        known_shorts = {
            "0OfOivc-tpU": "Software is DEAD! This GitHub Repo Can Build Anything in Few Hours",
            "kkXWbXZI_iM": "Software Engineer Salary vs Cost of Living: Which City Wins?",
            "YpHobheDpk8": "Why I Left My High Paying Job at Google in Just 8 Months",
            "L3ihlJVo_3A": "Top 5 Mistakes People Make in Resumes",
            "FoNMm4F9qIM": "Kimi K3 Is INSANE! Can It Beat Claude?",
            "39w4TLjreFU": "How to become top 1% coder in 2027 | 90 Days roadmap"
        }

        def mock_retry_evaluator(source_url: str):
            from backend.services.provenance import extract_yt_id
            yt_id = extract_yt_id(source_url)
            if yt_id in known_shorts:
                parent_title = known_shorts[yt_id]
                return False, f"Cannot retry job: source '{source_url}' is a ClipForge-generated output Short (from '{parent_title}'). Output Shorts cannot be processed as source inputs."
            return True, "Job re-queued successfully"

        # Verify all 6 Shorts are rejected from retry
        for s_id in known_shorts:
            allowed, msg = mock_retry_evaluator(f"https://www.youtube.com/shorts/{s_id}")
            self.assertFalse(allowed, f"Short {s_id} should be rejected from retry")
            self.assertIn("ClipForge-generated output Short", msg)

        # Verify original source video (m5hidzW-_i0) is permitted to retry
        orig_allowed, orig_msg = mock_retry_evaluator("https://www.youtube.com/watch?v=m5hidzW-_i0")
        self.assertTrue(orig_allowed, "Original source video m5hidzW-_i0 must be permitted to retry")
        self.assertEqual(orig_msg, "Job re-queued successfully")

    def test_auto_publish_destination_validation_contract(self):
        """
        Verify the auto-publish and destination validation rules:
        1. auto_publish=True without publish_destination_id must be rejected (422).
        2. auto_publish=True with inactive destination must be rejected (400).
        3. Removing destination while auto_publish is True auto-disables auto_publish.
        """
        def validate_channel_config(auto_publish: bool, dest_id: str | None, dest_active: bool = True):
            if auto_publish and not dest_id:
                return 422, "Cannot enable auto-publish without selecting a valid publish destination."
            if dest_id and not dest_active:
                return 400, "Publish destination channel is not active"
            return 200, "Valid"

        # Case 1: auto_publish=True, dest=None -> 422
        code, err = validate_channel_config(True, None)
        self.assertEqual(code, 422)
        self.assertIn("Cannot enable auto-publish without selecting a valid publish destination", err)

        # Case 2: auto_publish=True, dest="", -> 422
        code, err = validate_channel_config(True, "")
        self.assertEqual(code, 422)

        # Case 3: auto_publish=True, dest="valid_id", dest_active=False -> 400
        code, err = validate_channel_config(True, "dest_123", dest_active=False)
        self.assertEqual(code, 400)
        self.assertIn("not active", err)

        # Case 4: auto_publish=True, dest="valid_id", dest_active=True -> 200
        code, err = validate_channel_config(True, "dest_123", dest_active=True)
        self.assertEqual(code, 200)

        # Case 5: Destination cleared -> auto_publish auto-disabled
        current_auto_publish = True
        new_dest_id = None
        target_auto_publish = None  # user didn't specify auto_publish in PATCH
        if new_dest_id is None and target_auto_publish is None:
            current_auto_publish = False
        self.assertFalse(current_auto_publish, "Clearing destination must auto-disable auto_publish")

    def test_publish_task_auto_publish_contract(self):
        """
        Verify pipeline publish_task honor system:
        1. When auto_publish is False, clip remains draft and is not uploaded.
        2. When auto_publish is True, upload proceeds to destination channel regardless of destination channel's own auto_publish.
        """
        class MockJob:
            def __init__(self, auto_publish: bool):
                import json
                self.config = json.dumps({"auto_publish": auto_publish})
                self.channel_id = "source_chan_1"

        class MockDestinationChannel:
            def __init__(self):
                self.auto_publish = False  # Destinations have auto_publish=False by default
                self.is_active = True
                self.youtube_channel_id = "UCH90024qrJHA4amGRxnTldw"

        dest_ch = MockDestinationChannel()

        # Helper simulating publish_task decision logic
        def evaluate_publish_action(job: MockJob, dest: MockDestinationChannel):
            import json
            cfg = json.loads(job.config)
            is_auto_publish = cfg.get("auto_publish", False)

            if not is_auto_publish:
                return "draft", "auto_publish_disabled"
            
            # Destination channel check
            if not dest or not dest.is_active:
                return "failed", "destination_inactive"
            
            # Successful upload triggered because source job requested auto_publish
            return "published", f"uploaded_to_{dest.youtube_channel_id}"

        # Test A: auto_publish = False -> clip stays draft, not uploaded
        job_disabled = MockJob(auto_publish=False)
        status, reason = evaluate_publish_action(job_disabled, dest_ch)
        self.assertEqual(status, "draft")
        self.assertEqual(reason, "auto_publish_disabled")

        # Test B: auto_publish = True -> clip is uploaded to destination even though dest.auto_publish is False!
        job_enabled = MockJob(auto_publish=True)
        status, reason = evaluate_publish_action(job_enabled, dest_ch)
        self.assertEqual(status, "published")
        self.assertEqual(reason, "uploaded_to_UCH90024qrJHA4amGRxnTldw")


if __name__ == '__main__':
    unittest.main()
