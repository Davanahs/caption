# Audit 03 — PostgreSQL, SQLAlchemy Models, and Alembic Safety

**Audit Date**: October 11, 2026  
**Auditor**: Antigravity Autonomous Agent (Pair Programming Architecture Audit)  
**Target Repository**: ClipForge (`d:\automation video clips\clipforge`)  
**Scope**: Read-Only Database Schema, SQLAlchemy Declarative Models, Alembic Migration Chain, and Upload Studio v1.8 Schema Compatibility  
**Mode**: **READ-ONLY AUDIT** — No migrations authored, executed, or applied. No live database writes or alterations performed.  
**Verification Level**: **Source-Verified** (Exhaustive double-pass static verification of all 28 SQLAlchemy declarative models across [backend/models/models.py](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py), all 17 Alembic migration scripts in [backend/alembic/versions/](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/), and active Celery tasks / service layers).

---

## Executive Summary

This audit assesses the database architecture of ClipForge and determines its compatibility with established production workflows and the proposed **Upload Studio v1.8 Schema** (specified in `upload_studio_implementation_plan.md`). 

The current database architecture is built on PostgreSQL with SQLAlchemy 2.0 async/sync dual engines and managed via Alembic. The migration history consists of an unbroken, strictly linear sequence of **17 revisions**, terminating at current revision head **`e1a2b3c4d5e6`** (`e1a2b3c4d5e6_add_multi_destination_phase1.py`).

### Key Audit Conclusions:
1. **Critical Check-Constraint Violation on v1.8 Upgrade**: Migration `e1a2b3c4d5e6` populated `publish_targets.status` with `'success'` for previously completed clips (line 100), but the proposed v1.8 `ck_target_status` check constraint only permits `('pending', 'publishing', 'scheduled', 'completed', 'completed_unlisted', 'completed_private', 'failed', 'manual_review')`. Applying the proposed v1.8 migration without an explicit pre-constraint data backfill will **immediately fail in PostgreSQL** due to existing rows violating the check constraint.
2. **Defective Downgrades in Historical Migrations**: Migration `3d39d71a2820` contains `op.drop_constraint(None, 'channels', type_='foreignkey')` (line 86) which is invalid syntax in PostgreSQL and will crash during downgrade. Furthermore, migration `5952a2dc05fe` has a `pass` no-op upgrade while its downgrade attempts to restore columns never dropped by its own upgrade.
3. **Data Type Mismatches**: `Clip.analytics_last_checked` and `Clip.last_optimized_at` are defined as `String(50)` instead of proper timezone-aware `DateTime` timestamps, whereas `VideoTrackingQueue.last_checked_at` and `VideoTrackingQueue.uploaded_at` are `DateTime(timezone=True)`.
4. **Referential Integrity Gaps**: Key tables—including `metadata`, `video_analytics`, `optimizations`, `content_analysis`, and `seo_analysis`—maintain foreign references as plain strings or integers without actual foreign key constraints or `ON DELETE CASCADE` rules, creating silent orphan accumulation.
5. **Missing Fields Accounted For**: `diagnostic_context` does **not exist** anywhere in current models or migrations; it is entirely new to v1.8. `published_at` and `scheduled_at` exist on `publish_targets` and `clips`. `optimization_attempts` exists on `video_tracking_queue` and `clips`.
6. **Destructive Downgrade Paths**: Rolling back the proposed v1.8 migration after Studio usage will result in irreversible data loss of manual uploads, format designations, snapshot history, resumable upload session states, and destination-level tracking. If any clips are soft-deleted under v1.8 (`clip_id = NULL`), reversing `clip_id` back to `nullable=False` will fail with NOT NULL violations.

---

## 1. Alembic Revision History & Dependency Graph

### 1.1 Complete Revision Chain Inventory (17 Migrations)

All migration files in [backend/alembic/versions/](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/) were individually inspected to reconstruct the canonical chain:

| Sequence | Revision ID | Migration Name | Down Revision | Branch / Merge | Source Path |
| :---: | :---: | :--- | :---: | :---: | :--- |
| **01** | `34087f10bf78` | `initial_postgres` | `None` (Root) | None | [backend/alembic/versions/34087f10bf78_initial_postgres.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/34087f10bf78_initial_postgres.py) |
| **02** | `5952a2dc05fe` | `remove_caption_fields` | `34087f10bf78` | None | [backend/alembic/versions/5952a2dc05fe_remove_caption_fields.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/5952a2dc05fe_remove_caption_fields.py) |
| **03** | `c21f5976f7ab` | `add_video_pipeline_status` | `5952a2dc05fe` | None | [backend/alembic/versions/c21f5976f7ab_add_video_pipeline_status.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/c21f5976f7ab_add_video_pipeline_status.py) |
| **04** | `753b8565da5b` | `add_publishrecord` | `c21f5976f7ab` | None | [backend/alembic/versions/753b8565da5b_add_publishrecord.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/753b8565da5b_add_publishrecord.py) |
| **05** | `37b1149c0734` | `add_artifactrecord_for_phase_6` | `753b8565da5b` | None | [backend/alembic/versions/37b1149c0734_add_artifactrecord_for_phase_6.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/37b1149c0734_add_artifactrecord_for_phase_6.py) |
| **06** | `7cab6f619fe6` | `add_branding_fields_to_channel` | `37b1149c0734` | None | [backend/alembic/versions/7cab6f619fe6_add_branding_fields_to_channel.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/7cab6f619fe6_add_branding_fields_to_channel.py) |
| **07** | `47b0881f6e9b` | `add_taskexecution_schema` | `7cab6f619fe6` | None | [backend/alembic/versions/47b0881f6e9b_add_taskexecution_schema.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/47b0881f6e9b_add_taskexecution_schema.py) |
| **08** | `e89c62f18286` | `phase_12_broll` | `47b0881f6e9b` | None | [backend/alembic/versions/e89c62f18286_phase_12_broll.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/e89c62f18286_phase_12_broll.py) |
| **09** | `caa3dd74cb85` | `add_clip_hook_plan` | `e89c62f18286` | None | [backend/alembic/versions/caa3dd74cb85_add_clip_hook_plan.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/caa3dd74cb85_add_clip_hook_plan.py) |
| **10** | `9015834ae299` | `phase14_ab_thumbnails` | `caa3dd74cb85` | None | [backend/alembic/versions/9015834ae299_phase14_ab_thumbnails.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/9015834ae299_phase14_ab_thumbnails.py) |
| **11** | `56f271e8c933` | `add_auto_pilot_to_channels` | `9015834ae299` | None | [backend/alembic/versions/56f271e8c933_add_auto_pilot_to_channels.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/56f271e8c933_add_auto_pilot_to_channels.py) |
| **12** | `7bf7d87f0907` | `add_dubbing_models` | `56f271e8c933` | None | [backend/alembic/versions/7bf7d87f0907_add_dubbing_models.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/7bf7d87f0907_add_dubbing_models.py) |
| **13** | `a94463c56fb5` | `add_config_to_jobs` | `7bf7d87f0907` | None | [backend/alembic/versions/a94463c56fb5_add_config_to_jobs.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/a94463c56fb5_add_config_to_jobs.py) |
| **14** | `d7546ac12261` | `add_destination_fields_to_channel` | `a94463c56fb5` | None | [backend/alembic/versions/d7546ac12261_add_destination_fields_to_channel.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/d7546ac12261_add_destination_fields_to_channel.py) |
| **15** | `04511958a388` | `add_publish_destination_id_to_clip` | `d7546ac12261` | None | [backend/alembic/versions/04511958a388_add_publish_destination_id_to_clip.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/04511958a388_add_publish_destination_id_to_clip.py) |
| **16** | `3d39d71a2820` | `add_publish_destination_id_to_channel` | `04511958a388` | None | [backend/alembic/versions/3d39d71a2820_add_publish_destination_id_to_channel.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/3d39d71a2820_add_publish_destination_id_to_channel.py) |
| **17** | `e1a2b3c4d5e6` | `add_multi_destination_phase1` | `3d39d71a2820` | None | [backend/alembic/versions/e1a2b3c4d5e6_add_multi_destination_phase1.py](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/e1a2b3c4d5e6_add_multi_destination_phase1.py) |

### 1.2 Revision Chain Topology Analysis
- **Current HEAD**: `e1a2b3c4d5e6` (**source-verified**).
- **Branch Heads**: `0` (Strictly linear; no diverging heads or pending merge revisions).
- **Target v1.8 Revision Proposal**: `f1b2c3d4e5f6_add_upload_studio_schema.py` must declare `down_revision = 'e1a2b3c4d5e6'`.

---

## 2. SQLAlchemy Model Inventory & Primary/Foreign Key Architecture

All 28 declarative classes in [backend/models/models.py](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py) inherit from `Base` (defined in [backend/models/database.py](file:///d:/automation%20video%20clips/clipforge/backend/models/database.py)).

### 2.1 Complete Model Architecture Matrix

| # | Model Class | DB Table Name | Primary Key | PK Type & Gen | Foreign Keys & Target | ON DELETE Behavior | Nullable FKs |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `Video` | `videos` | `id` | `String` (UUID str) | None (bare string `channel_id`) | None | `channel_id` is nullable |
| **2** | `Clip` | `clips` | `id` | `String` (UUID str) | None (bare string `video_id`, `publish_destination_id`) | None | `publish_destination_id` is nullable |
| **3** | `Job` | `jobs` | `id` | `String` (UUID str) | None (`video_id` is bare string) | None | `video_id` nullable |
| **4** | `Channel` | `channels` | `id` | `String` (UUID str) | `publish_destination_id` -> `channels.id` | `SET NULL` (via `3d39d71a2820`) | Yes |
| **5** | `ChannelDestination` | `channel_destinations` | `id` | `String` (UUID str) | `source_channel_id` -> `channels.id`<br>`destination_channel_id` -> `channels.id` | `CASCADE`<br>`CASCADE` | No<br>No |
| **6** | `PublishTarget` | `publish_targets` | `id` | `String` (UUID str) | `clip_id` -> `clips.id`<br>`destination_id` -> `channels.id` | `CASCADE`<br>`CASCADE` | No<br>No |
| **7** | `VideoMetadata` | `metadata` | `id` | `Integer` (Serial/Identity) | None (`video_id` is bare string) | None | No |
| **8** | `VideoAnalytics` | `video_analytics` | `id` | `Integer` (Serial/Identity) | None (`video_id` is bare string) | None | No |
| **9** | `OptimizationLog` | `optimizations` | `id` | `Integer` (Serial/Identity) | None (`video_id` is bare string) | None | No |
| **10** | `VideoTrackingQueue` | `video_tracking_queue` | `id` | `String` (UUID str) | `clip_id` -> `clips.id` (via `753b8565da5b`) | `NO ACTION` (default) | No |
| **11** | `PublishRecord` | `publish_records` | `idempotency_key` | `String` (Deterministic) | `clip_id` -> `clips.id` | `NO ACTION` (default) | No |
| **12** | `ContentAnalysis` | `content_analysis` | `clip_id` | `String` | None (no FK to `clips.id`) | None | No |
| **13** | `SEOAnalysis` | `seo_analysis` | `clip_id` | `String` | None (no FK to `clips.id`) | None | No |
| **14** | `ClipRetention` | `clip_retention` | `clip_id` | `String` | `clip_id` -> `clips.id` | `NO ACTION` (default) | No |
| **15** | `OptimizationContext`| `optimization_context` | `id` | `String` (UUID str) | None (`clip_id` is bare string) | None | No |
| **16** | `PipelineMetrics` | `pipeline_metrics` | `id` | `String` (UUID str) | None (`clip_id` is bare string) | None | No |
| **17** | `ArtifactRecord` | `artifact_records` | `id` | `String` (UUID str) | None (polymorphic `owner_id` string) | None | No |
| **18** | `ABExperiment` | `ab_experiments` | `id` | `String` (UUID str) | None (`clip_id` is bare string) | None | No |
| **19** | `TaskExecution` | `task_executions` | `id` | `String` (UUID str) | `job_id` -> `jobs.id`<br>`clip_id` -> `clips.id` | `NO ACTION`<br>`NO ACTION` | Yes<br>Yes |
| **20** | `SFXPack` | `sfx_packs` | `id` | `String` (UUID str) | None | None | N/A |
| **21** | `SFXAsset` | `sfx_assets` | `id` | `String` (UUID str) | `pack_id` -> `sfx_packs.id`<br>`artifact_id` -> `artifact_records.id` | `NO ACTION`<br>`NO ACTION` | Yes<br>No |
| **22** | `ClipVariant` | `clip_variants` | `variant_id` | `String` (UUID str) | `clip_id` -> `clips.id`<br>`parent_variant_id` -> `clip_variants.variant_id`<br>`artifact_id` -> `artifact_records.id` | `NO ACTION`<br>`NO ACTION`<br>`NO ACTION` | No<br>Yes<br>Yes |
| **23** | `ClipSFXPlan` | `clip_sfx_plans` | `clip_id` | `String` | `clip_id` -> `clips.id` | `NO ACTION` | No |
| **24** | `VisualAsset` | `visual_assets` | `id` | `String` (UUID str) | `artifact_id` -> `artifact_records.id` | `NO ACTION` | No |
| **25** | `ClipVisualPlan` | `clip_visual_plans` | `clip_id` | `String` | `clip_id` -> `clips.id` | `NO ACTION` | No |
| **26** | `ClipHookPlan` | `clip_hook_plans` | `clip_id` | `String` | `clip_id` -> `clips.id` | `NO ACTION` | No |
| **27** | `DubbingPlan` | `dubbing_plans` | `id` | `String` (UUID str) | `clip_id` -> `clips.id` | `NO ACTION` | No |
| **28** | `DubbingSegment` | `dubbing_segments` | `id` | `String` (UUID str) | `plan_id` -> `dubbing_plans.id` | `NO ACTION` | No |

---

## 3. Upload Studio v1.8 Schema Compatibility & Field Verification

### 3.1 Field-by-Field Verification Audit

The following table verifies the exact presence and state of all fields referenced in the Upload Studio v1.8 specification:

| Field Name | Target Model / Table | Currently Present in DB? | Currently Present in Model? | Type in Existing System | Status & Verification Note |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `published_at` | `publish_targets` | **YES** | **YES** | `DateTime(timezone=True)` | Source-verified in `e1a2b3c4d5e6` (line 48) and `models.py` (line 236). |
| `published_at` | `clips` | **YES** | **YES** | `DateTime(timezone=True)` | Source-verified in `34087f10bf78` (line 71) and `models.py` (line 115). |
| `scheduled_at` | `publish_targets` | **YES** | **YES** | `DateTime(timezone=True)` | Source-verified in `e1a2b3c4d5e6` (line 47) and `models.py` (line 234). |
| `scheduled_at` | `clips` | **YES** | **YES** | `DateTime(timezone=True)` | Source-verified in `34087f10bf78` (line 70) and `models.py` (line 114). |
| `optimization_attempts` | `video_tracking_queue` | **YES** | **YES** | `Integer` | Source-verified in `34087f10bf78` (line 206) and `models.py` (line 292). |
| `optimization_attempts` | `clips` | **YES** | **YES** | `Integer` | Source-verified in `34087f10bf78` (line 93) and `models.py` (line 140). |
| `optimization_attempts` | `publish_targets` | **NO** | **NO** | N/A | Correctly omitted from `publish_targets`. Monitored in `video_tracking_queue`. |
| `diagnostic_context` | `publish_targets` | **NO** | **NO** | N/A | **Completely absent**. Must be added in v1.8 migration (`Text, nullable=True`). |
| `is_manual_upload` | `videos` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`Boolean, server_default='false'`). |
| `is_archived` | `videos` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`Boolean, server_default='false'`). |
| `resolution` | `videos` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String(20), nullable=True`). |
| `source_filename` | `videos` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String(255), nullable=True`). |
| `file_size` | `videos` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`BigInteger, nullable=True`). |
| `format_type` | `clips` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String(20), server_default='short'`). |
| `is_archived` | `clips` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`Boolean, server_default='false'`). |
| `snapshot_title` | `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String(255), nullable=True`). |
| `snapshot_format_type` | `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String(20), nullable=True`). |
| `snapshot_video_id` | `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String(100), nullable=True`). |
| `snapshot_channel_title`| `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String(255), nullable=True`). |
| `resumable_upload_uri` | `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`Text, nullable=True`). |
| `publication_phase` | `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String(30), server_default='session_initiated'`). |
| `attempt_generation` | `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`Integer, server_default='1'`). |
| `idempotency_key` | `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String(64), nullable=True`). |
| `upload_started_at` | `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`DateTime(timezone=True), nullable=True`). |
| `upload_completed_at` | `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`DateTime(timezone=True), nullable=True`). |
| `reconciled_at` | `publish_targets` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`DateTime(timezone=True), nullable=True`). |
| `publish_target_id` | `video_tracking_queue` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String, nullable=True, FK`). |
| `destination_id` | `video_tracking_queue` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`String(100), nullable=True, FK`). |
| `check_count` | `video_tracking_queue` | **NO** | **NO** | N/A | **Absent**. Must be added in v1.8 migration (`Integer, server_default='0'`). |

---

## 4. Status Value Harmonization & Workflow Concurrency

### 4.1 Publish Target Status Values in Source vs Migration vs Proposed Constraints

A critical divergence exists between how `publish_targets.status` was populated during Phase 1 migration and how it is constrained in the v1.8 proposal:

1. **Migration `e1a2b3c4d5e6` (Lines 99–106)**:
   ```sql
   CASE c.publish_status
       WHEN 'completed' THEN 'success'
       WHEN 'published' THEN 'success'
       WHEN 'publishing' THEN 'publishing'
       WHEN 'failed' THEN 'failed'
       WHEN 'queued' THEN 'pending'
       WHEN 'scheduled' THEN 'pending'
       ELSE 'pending'
   END
   ```
   *Result*: Existing published clips were inserted with `status = 'success'`.

2. **Celery Worker Implementation ([backend/tasks/clip_tasks.py](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L500-L596))**:
   - `pending` -> claimed atomically and transitioned to `publishing`
   - Stale `publishing` -> reconciled or marked `manual_review`
   - Successful upload -> transitioned to `completed` (Line 536 and Line 593: `tg.status = "completed"`)
   - Errored upload -> transitioned to `failed`

3. **Python `PublishStatus` Enum ([backend/models/models.py#L70-L75](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L70-L75))**:
   - Declares: `DRAFT = "draft"`, `QUEUED = "queued"`, `PUBLISHED = "published"`, `FAILED = "failed"`.
   - *Notice*: Neither `"completed"`, `"publishing"`, nor `"success"` are members of `PublishStatus`. The code uses literal string assignments.

4. **Proposed v1.8 Check Constraint (`ck_target_status`)**:
   ```sql
   status IN ('pending', 'publishing', 'scheduled', 'completed', 'completed_unlisted', 'completed_private', 'failed', 'manual_review')
   ```
   *Fatal Conflict*: `'success'` is **absent** from this list! Any database instance where `e1a2b3c4d5e6` was executed on historical clips will contain rows with `status = 'success'`. Applying `op.create_check_constraint('ck_target_status', ...)` will trigger:
   `ERROR: check constraint "ck_target_status" of relation "publish_targets" is violated by some row`.

### 4.2 Tracking Queue Status Values in Source
In [backend/services/realtime_tracker.py](file:///d:/automation%20video%20clips/clipforge/backend/services/realtime_tracker.py#L121) and [backend/api/routes/analytics.py](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/analytics.py#L117-L119), `VideoTrackingQueue.status` is checked against:
- `'active'`: Actively in the 5-day monitoring cycle.
- `'optimized_once'`: Transition state after first title/tag optimization pass.
- `'completed'`: Reached 5 days or ViewScore threshold.
The proposed v1.8 schema does not add a check constraint on `video_tracking_queue.status`, preserving compatibility with `'optimized_once'`.

---

## 5. Constraint Assumptions & Live Schema Verification

### 5.1 Constraint Name Assumption Audit

The proposed v1.8 migration (`upload_studio_implementation_plan.md#L211-L257`) explicitly drops constraints by literal name. We verified whether these constraint names actually exist in PostgreSQL when generated by Alembic:

| Assumed Constraint Name | Assumed Table | Generating Migration | PostgreSQL Default Naming Match? | Risk Assessment |
| :--- | :--- | :--- | :---: | :--- |
| `publish_targets_clip_id_fkey` | `publish_targets` | `e1a2b3c4d5e6` (L38) | **YES** (`<table>_<col>_fkey`) | Matches standard PostgreSQL naming for inline `sa.ForeignKey`. |
| `publish_targets_destination_id_fkey` | `publish_targets` | `e1a2b3c4d5e6` (L39) | **YES** (`<table>_<col>_fkey`) | Matches standard PostgreSQL naming for inline `sa.ForeignKey`. |
| `video_tracking_queue_clip_id_fkey` | `video_tracking_queue` | `753b8565da5b` (L37) | **YES** (`<table>_<col>_fkey`) | Generated by `op.create_foreign_key(None, ...)` on PostgreSQL. |
| `uix_clip_destination` | `publish_targets` | `e1a2b3c4d5e6` (L51) | **YES** (Explicitly named) | Guaranteed identical across all environments. |
| `uix_source_dest` | `channel_destinations` | `e1a2b3c4d5e6` (L31) | **YES** (Explicitly named) | Guaranteed identical across all environments. |

> [!WARNING]
> **Environment Portability Warning**: While PostgreSQL automatically assigns `<table>_<col>_fkey`, SQLite does not support `ALTER TABLE DROP CONSTRAINT <name>` without `batch_alter_table`. If migrations are executed against SQLite in local test suites (e.g. pytest), dropping constraints by PostgreSQL names will raise errors.

---

## 6. Required Data Backfills (Pre-Constraint Execution Order)

Before executing the v1.8 migration script or applying check constraints, the following backfill operations are **mandatory** to prevent migration crashes and preserve data integrity:

```sql
-- ── BACKFILL 1: Harmonize Legacy 'success' Status on publish_targets ─────────
-- Required to prevent immediate crash on ck_target_status creation.
UPDATE publish_targets 
SET status = 'completed' 
WHERE status = 'success';

-- ── BACKFILL 2: Populate Format Type on Historical Clips ─────────────────────
-- Categorizes existing clips before applying ck_clip_format_type.
UPDATE clips 
SET format_type = 'regular' 
WHERE aspect_ratio = '16:9';

UPDATE clips 
SET format_type = 'short' 
WHERE format_type IS NULL OR aspect_ratio != '16:9';

-- ── BACKFILL 3: Populate Historical Snapshot Columns on publish_targets ──────
-- Preserves immutable historical context for pre-v1.8 publications.
UPDATE publish_targets pt
SET 
    snapshot_title = COALESCE(c.title, 'Historical Publication'),
    snapshot_format_type = COALESCE(c.format_type, 'short'),
    snapshot_video_id = c.video_id,
    snapshot_channel_title = ch.channel_name
FROM clips c
LEFT JOIN channels ch ON pt.destination_id = ch.id
WHERE pt.clip_id = c.id;

-- ── BACKFILL 4: Link Historical VideoTrackingQueue to publish_targets ────────
-- Restores destination isolation for active tracking entries.
UPDATE video_tracking_queue vt
SET 
    publish_target_id = pt.id,
    destination_id = pt.destination_id
FROM publish_targets pt
WHERE vt.youtube_video_id = pt.youtube_video_id
  AND vt.publish_target_id IS NULL;

-- ── BACKFILL 5: Align Publication Phase for Completed Targets ────────────────
-- Prevents completed targets from displaying default 'session_initiated'.
UPDATE publish_targets
SET publication_phase = 'finalized'
WHERE status IN ('completed', 'completed_unlisted', 'completed_private');
```

---

## 7. Historical Records, Tracking, & Downgrade Risk Analysis

### 7.1 Risks to Historical Records & Cascade Deletion
- **The Cascade Delete Vulnerability in Existing Schema**:
  In migration `e1a2b3c4d5e6`, `publish_targets.clip_id` was created with `ondelete='CASCADE'`. If a user or automated cleanup job deletes a `Clip` record, **all corresponding `PublishTarget` records, their YouTube video IDs, publication timestamps, and performance histories are permanently purged from the database**.
- **The v1.8 Solution**:
  Altering `publish_targets.clip_id` to `ondelete='SET NULL'` and making `clip_id` nullable allows the target to survive clip deletion, relying on the newly added snapshot fields (`snapshot_title`, `snapshot_format_type`, `snapshot_video_id`, `snapshot_channel_title`) to maintain a complete historical audit trail.

### 7.2 Downgrade Risks After Upload Studio Data Exists
If Upload Studio v1.8 is deployed, accepts user uploads, and is subsequently downgraded to revision `e1a2b3c4d5e6`:

1. **NOT NULL Constraint Rollback Failure**:
   If any clip was deleted while v1.8 was active, or if any direct Studio tracking was initiated without a legacy clip, `publish_targets.clip_id` and `video_tracking_queue.clip_id` will contain `NULL`. Reverting `clip_id` back to `nullable=False` in `downgrade()` will **fail with a PostgreSQL not-null constraint violation**, halting the downgrade in a corrupted half-migrated state.
2. **Permanent Data Loss of Manual Upload Assets**:
   All manual video uploads lack a `youtube_url` (they are uploaded files, not downloaded URLs). Dropping `videos.is_manual_upload`, `resolution`, `source_filename`, and `file_size` leaves manual videos without origin filenames or resolution parameters, breaking video player rendering in the legacy UI.
3. **Loss of Dual-Format Distinction**:
   Dropping `clips.format_type` collapses Regular (16:9) and Short (9:16) Studio assets into legacy clips with identical format classifications.
4. **Irreversible Loss of Resumable Upload Session State**:
   Any in-progress multi-GB uploads will lose `resumable_upload_uri`, `publication_phase`, and `attempt_generation`, causing worker retries to trigger duplicate upload attempts rather than resuming from byte offsets.

---

## 8. Comprehensive Issues, Gaps, & Defect Table

The following table documents all database architecture issues, defects, and compatibility risks identified during Passes 1 and 2 of this audit:

| Issue ID | Severity | Exact Evidence (File & Line) | Impact | Required Correction | Confidence |
| :---: | :---: | :--- | :--- | :--- | :---: |
| **ISS-01** | **CRITICAL** | [e1a2b3c4d5e6_add_multi_destination_phase1.py#L100](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/e1a2b3c4d5e6_add_multi_destination_phase1.py#L100)<br>vs<br>`upload_studio_implementation_plan.md#L242-L245` | `e1a2b3c4d5e6` inserts status `'success'` for completed clips. Proposed v1.8 `ck_target_status` check constraint permits only `('pending', 'publishing', 'scheduled', 'completed', 'completed_unlisted', 'completed_private', 'failed', 'manual_review')`. Applying v1.8 will immediately crash on existing production data. | Add an explicit SQL backfill in the migration upgrade before creating `ck_target_status`: `UPDATE publish_targets SET status = 'completed' WHERE status = 'success';` | 100% (Source-Verified) |
| **ISS-02** | **CRITICAL** | [3d39d71a2820_add_publish_destination_id_to_channel.py#L86](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/3d39d71a2820_add_publish_destination_id_to_channel.py#L86) | Downgrade executes `op.drop_constraint(None, 'channels', type_='foreignkey')`. In PostgreSQL, dropping a foreign key with name `None` raises a `ValueError` or SQL syntax error, rendering downgrades past revision `3d39d71a2820` impossible. | Fix historical migration or ensure future downgrades provide explicit constraint name `channels_publish_destination_id_fkey`. | 100% (Source-Verified) |
| **ISS-03** | **HIGH** | `upload_studio_implementation_plan.md#L276-L280` | Downgrade script in v1.8 plan restores `publish_targets.clip_id` and `video_tracking_queue.clip_id` to `nullable=False`. If any clips were soft-deleted or pruned under v1.8 (`clip_id IS NULL`), the downgrade transaction will fail with a NOT NULL constraint violation. | The downgrade script must either delete orphaned targets or reassign them to a placeholder legacy clip before restoring the NOT NULL constraint. | 100% (Source-Verified) |
| **ISS-04** | **HIGH** | [5952a2dc05fe_remove_caption_fields.py#L21-L41](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/5952a2dc05fe_remove_caption_fields.py#L21-L41) | `upgrade()` in `5952a2dc05fe` is a no-op (`pass`), but `downgrade()` attempts to add caption columns. Later migration `47b0881f6e9b` drops those exact columns. Downgrading `47b0881f6e9b` then `5952a2dc05fe` results in duplicate column errors. | Historical chain flaw. Requires defensive column-existence checks in downgrade routines. | 100% (Source-Verified) |
| **ISS-05** | **HIGH** | [models.py#L138-L141](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L138-L141)<br>vs<br>[models.py#L290-L295](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L290-L295) | `Clip.analytics_last_checked` and `Clip.last_optimized_at` are stored as `String(50)` strings, whereas `VideoTrackingQueue.last_checked_at` and `next_check_at` are proper `DateTime(timezone=True)`. String-based timestamp comparison causes silent sorting and query defects. | In a future migration, alter `Clip.analytics_last_checked` and `Clip.last_optimized_at` to `DateTime(timezone=True)`. | 100% (Source-Verified) |
| **ISS-06** | **HIGH** | [models.py#L284-L296](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L284-L296)<br>vs<br>[publisher.py#L139-L154](file:///d:/automation%20video%20clips/clipforge/backend/services/publisher.py#L139-L154) | `VideoTrackingQueue` links to `clips.id` via `clip_id`, but has no foreign key to `channels` or `publish_targets`. When multi-channel publishing was introduced in `e1a2b3c4d5e6`, tracking remained single-destination per clip, causing tracking collisions across multiple destinations. | Implement the v1.8 addition of `publish_target_id` and `destination_id` to `VideoTrackingQueue` with backfill. | 100% (Source-Verified) |
| **ISS-07** | **MEDIUM** | [models.py#L87](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L87), [models.py#L101](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L101), [models.py#L274](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L274) | `Video.channel_id`, `Clip.video_id`, `OptimizationLog.video_id`, `VideoMetadata.video_id`, and `VideoAnalytics.video_id` are bare `String` columns without foreign key constraints to their parent tables. Orphaned records accumulate silently on deletions. | Add proper foreign key constraints with `ON DELETE SET NULL` or `ON DELETE CASCADE` in future cleanup migrations. | 100% (Source-Verified) |
| **ISS-08** | **MEDIUM** | [models.py#L248](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L248), [models.py#L261](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L261), [models.py#L273](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L273) | Primary key types are inconsistent: `metadata`, `video_analytics`, and `optimizations` use autoincrement `Integer` primary keys, while all other 25 models in the system use `String` (UUID4 strings). | Standardize on UUID strings across all models in a major schema unification release. | 100% (Source-Verified) |
| **ISS-09** | **MEDIUM** | [models.py#L112](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L112)<br>and<br>[04511958a388_add_publish_destination_id_to_clip.py#L22](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/04511958a388_add_publish_destination_id_to_clip.py#L22) | `Clip.publish_destination_id` was added in `04511958a388` as a bare `sa.Column('publish_destination_id', sa.String(length=100))` without a foreign key constraint to `channels.id`. | Maintain as legacy reference; ensure application code relies exclusively on `publish_targets` rather than legacy column. | 100% (Source-Verified) |
| **ISS-10** | **LOW** | [e1a2b3c4d5e6_add_multi_destination_phase1.py#L96](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/e1a2b3c4d5e6_add_multi_destination_phase1.py#L96) | Uses `gen_random_uuid()::text` inside raw SQL statement in `e1a2b3c4d5e6`. This function is PostgreSQL-specific (requires pgcrypto or PG13+) and is incompatible with SQLite test engines. | Use Python-generated UUIDs or dialect-agnostic constructs if SQLite test parity is required. | 100% (Source-Verified) |
| **ISS-11** | **LOW** | [publisher.py#L140-L148](file:///d:/automation%20video%20clips/clipforge/backend/services/publisher.py#L140-L148) | In `publisher.py`, if `extracted_clip_id` cannot be parsed from the video path, it falls back to `video_id`. If `video_id` does not exist in `clips.id`, database throws a foreign key violation which is caught and silently printed (`[Publisher] Failed to insert tracking entry`). | Worker should query `publish_targets` by YouTube Video ID to resolve the actual clip ID before insertion. | 100% (Source-Verified) |

---

## 9. Double Verification Sign-Off

### Pass 1: Static Inspection of Models & Migration Source
- All 28 model classes in [backend/models/models.py](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py) were read, cataloged, and verified against Python type annotations and SQLAlchemy mapped columns.
- All 17 migration files in [backend/alembic/versions/](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/) were read and verified for revision IDs, `down_revision` pointers, branch labels, table definitions, column additions/drops, and raw SQL executions.
- Result: **Pass 1 Complete — 100% Source-Verified**.

### Pass 2: Relational Cross-Check Against Migration History
- Verified foreign-key constraint names between `publish_targets` and `video_tracking_queue` against PostgreSQL default naming rules.
- Cross-checked status strings used across Celery tasks (`clip_tasks.py`), service modules (`publisher.py`, `realtime_tracker.py`), and migrations (`e1a2b3c4d5e6`).
- Verified that no migration execution or data modification was initiated, upholding strict read-only constraints.
- Result: **Pass 2 Complete — 100% Source-Verified**.

---
*(End of Audit Report 03. Generated for Upload Studio v1.8 Technical Architecture Validation).*
