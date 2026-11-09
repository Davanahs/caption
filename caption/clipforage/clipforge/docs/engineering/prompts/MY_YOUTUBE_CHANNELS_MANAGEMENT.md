# Implementation Specification & Prompt Archive: My YouTube Channels Management

**Task:** My YouTube Channels Management Experience (`/youtube-channels`)  
**Specification Reference:** CLIPFORGE MASTER ENGINEERING TASK — PART F  
**Status:** In Progress / Implementing  
**Created:** 2026-10-13  
**Authors/Origin:** Antigravity Engineering System  

---

## 1. Scope & Objective

Implement a dedicated channel-management experience at `/youtube-channels` in ClipForge, with full backend support, database schema alignment, OAuth account authorization with credential isolation, channel-level analytics, customizable publishing settings, and seamless publishing destination harmonization.

Users must be able to:
1. Connect multiple YouTube channels via OAuth without token collision.
2. View connected publishing destinations, channel avatars, subscriber/video/view counts, and freshness.
3. Refresh cached channel statistics on-demand with honest scoping (bounded Shorts scan, likes scope).
4. Configure persistent default publishing settings (privacy, tags, category, license, made-for-kids, branding metadata).
5. Designate a default publishing channel transactionally.
6. Disconnect a channel safely without deleting historical clips, jobs, or publish history.
7. Maintain strict three-way separation:
   - **Publishing Destinations:** YouTube channels ClipForge is authorized to publish to.
   - **Monitored Source Channels:** Channels from which ClipForge discovers videos to clip.
   - **Synthetic Test Channels:** Fixtures used in testing (`is_test = true`), never exposed in user UI.

---

## 2. Architectural Components & Deliverables

### A. Database Model & Migration
- Forward Migration: `c3d4e5f6a7b8_add_publishing_settings_and_stats_to_channels.py` (revises `b2c3d4e5f6a7`).
- Target Table: `channels`
- Added Columns:
  - `publishing_settings: JSON | None`
  - `cached_stats: JSON | None`
- Invariant: Zero plaintext credentials or tokens in database JSON fields.

### B. OAuth & Multi-Channel Token Isolation
- Token File Scheme: `tokens/youtube_token_{youtube_channel_id}.json` with primary fallback `tokens/youtube_token.json`.
- Account Selection: Google OAuth flow configured with `prompt="select_account consent"` to allow linking multiple distinct Google accounts.
- Server-side Identity Verification: On callback exchange, API verifies `channels().list(mine=True)` and validates the exact channel ID before token persistence.
- `clipse` Channel Preservation: Channel `UCH90024qrJHA4amGRxnTldw` (`clipse`) preserved as default destination.

### C. Backend Management API
Router: `backend/api/routes/youtube_channels.py` mounted at `/api/youtube-channels` in `backend/main.py`.
- `GET /api/youtube-channels/` — Lists all verified, non-test publishing destinations with cached stats, settings, and authorization status.
- `POST /api/youtube-channels/{channel_id}/refresh` — Live refresh of stats via YouTube Data API v3; bounded and failure-tolerant.
- `PATCH /api/youtube-channels/{channel_id}/settings` — Validates and persists publishing settings.
- `POST /api/youtube-channels/{channel_id}/set-default` — Transactionally sets a single default destination.
- `POST /api/youtube-channels/{channel_id}/disconnect` — Disconnects destination, archives credentials, clears default, retains historical jobs/clips.
- `GET /api/youtube-channels/oauth-url` — Generates OAuth URL with state and account selection prompt.
- `POST /api/youtube-channels/connect` — Exchanges OAuth code, verifies identity, registers destination.

### D. Analytics & Stats Methodology
- Official channel statistics: `subscriberCount`, `videoCount`, `viewCount` from `channels().list(part="statistics")`.
- Shorts Detection: Bounded scan of channel's uploads playlist (`playlistItems().list` up to 50 recent videos), inspecting duration `<= 60s` and `#Shorts` tags.
- Honest Labeling: Labeled explicitly as "Shorts detected in recent uploads" with scan window documented.
- Likes Metric: Aggregated sum of scanned uploads, labeled as "Likes in scanned uploads".
- Failure Resilience: Stale valid cached data preserved if API refresh encounters errors or quota exhaustion.

### E. Frontend Management Experience
- Page Route: `frontend/app/youtube-channels/page.tsx`
- Navigation: Added to `frontend/components/Sidebar.tsx` as `My YouTube Channels`.
- API Client: Typed interfaces and methods in `frontend/lib/api.ts`.
- Modals:
  - Connect Channel Modal (Google OAuth flow with prompt selection and manual redirect URL fallback).
  - Channel Settings Modal (Privacy, Category, Tags, License, Made-for-Kids, Age Restriction, Branding).
  - Disconnect Confirmation Modal (Warning about revoking publishing eligibility while preserving history).

---

## 3. Invariants & Constraints
1. **Zero Auto-Publishing:** Decoupled completely from video intake and clipping pipelines.
2. **Zero Caption/Subtitle Burn-In:** Strict enforcement of subtitle freeze.
3. **Storage & Task Integrity:** Preserves 1.5x disk reservations and Celery worker health.
4. **Test Isolation:** Pytest tests tag records with `is_test = true` and tear down properly.
5. **Reversible & Safe Operations:** No destructive operations against production channels or real YouTube accounts during testing.
