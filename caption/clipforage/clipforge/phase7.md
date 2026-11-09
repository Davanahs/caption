# Phase 7: Copyright Mitigation & Automated Audio Replacement Pipeline

## 🎯 Goal
Build a YouTube private-first publishing workflow that uploads videos as private/unlisted, polls YouTube Content ID APIs for copyright claims, and automatically swaps flagged background audio tracks with royalty-free AI audio before releasing Shorts to public status.

---

## 🛠️ Implementation Tasks

### 1. Private-First Upload Policy
- **Target File:** `backend/services/publisher.py`
- Modify `publish_to_youtube`:
  - Force `privacyStatus` payload to `private` or `unlisted` during initial upload pass.
  - Set custom video metadata, category, and tags.
  - Record upload timestamp and `youtube_video_id` in database with `copyright_status = "checking"`.

### 2. Content ID Claim Polling Engine
- **Target Files:** `backend/services/copyright_verifier.py` (NEW), `backend/tasks/pipeline_tasks.py`
- Create `CopyrightVerifier` service using YouTube Data API v3 (`videos.list(part="contentDetails,status")`):
  - Polls YouTube API at 5-minute intervals post-upload.
  - Checks `contentDetails.licensingInfo` and `status.rejectionReason`.
  - Scans for Content ID audio/video claim strikes or monetization blocks.

### 3. Automated Audio Swap & Release Workflow
- **Target Files:** `backend/services/copyright_verifier.py`, `backend/services/publisher.py`
- **If 0 claims detected after 15 minutes:**
  - Automatically mutate video status to `public` via YouTube API update (`copyright_status = "clean"`).
- **If background audio claim detected:**
  - Automatically isolate speech track using Whisper stem separation, remix speech over a clean royalty-free background audio track (`./audio_library/royalty_free_ambient.mp3`), update the YouTube video stream, and re-trigger Content ID verification pass.

---

## 🧪 Verification & Acceptance Criteria

1. **Automated Audio Swap Test:** Simulate a YouTube audio copyright claim. Verify pipeline automatically strips background music, overlays royalty-free audio, and re-uploads clean video.
2. **Private Upload Test:** Publish a clip. Verify it appears on YouTube Creator Studio as Private during initial upload.
3. **Clean Release Test:** Mock a clean Content ID check. Verify video automatically updates to Public status after verification window.
