# Deliverable F: Database Models, Alembic Migrations & Storage Architecture Report
**Audit Item:** `CLIPFORGE-FULL-SYSTEM-AUDIT-001`  
**Subsystem:** Persistence Layer, Schema Governance, Storage Lifecycle & Data Integrity  
**Auditor:** Teamwork Worker M2 (Backend, DB & Celery Audit Deliverables Author)  
**Date of Audit:** 2026-11-03 / 2026-11-04  
**Target Codebase:** `d:\automation video clips\clipforge`  
**Integrity Mode:** Benchmark / Read-Only Inspection  
**Classification:** Authoritative Technical Deliverable  

---

## 1. Executive Summary & Database Architecture

The ClipForge persistence layer is engineered on **PostgreSQL**, utilizing **SQLAlchemy 2.0** declarative ORM models and governed by an **Alembic** migration versioning DAG.

### 1.1 Dual-Engine Architecture (`backend/models/database.py`)
To prevent event loop blocking and handle both async web requests and synchronous worker execution, the database layer operates dual engines:
- **Asynchronous Engine (`engine`):** `postgresql+asyncpg://...` used by FastAPI routes, async background sweeps, and WebSocket streams. Session factory: `async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)`.
- **Synchronous Engine (`sync_engine`):** `postgresql+psycopg2://...` used by Celery task workers, Alembic migrations, and offline CLI tooling. Session factory: `sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)`.
- **Pool Sizing & Health Checks:** Both engines are configured with `pool_size=5`, `max_overflow=5`, `pool_timeout=30`, and `pool_pre_ping=True`. `pool_pre_ping=True` actively issues a test query before checking out a connection, preventing stale connection exceptions after database restarts or idle timeouts.
- **Windows Console Crash Prevention:** `echo=False` is strictly enforced. Enabling SQLAlchemy engine echo on Windows environments causes console encoding crashes (`cp1252` character decoding failures on formatted SQL strings).

### 1.2 Key Subsystem Metrics
- **SQLAlchemy Declarative Models:** **31** declarative models declared in `backend/models/models.py`.
- **Alembic Linear Migrations:** **26** linear migration scripts spanning from base `34087f10bf78` to current head `e6f7a8b9c0d1`. Zero divergent branches, zero multiple heads.
- **Product Invariant Verification:** **100% Absence of Captions/Subtitles**. Zero caption columns in active models. Explicit historical purge verified in migration `47b0881f6e9b`.
- **Storage Subsystem:** Local filesystem (`LocalStorageProvider`) with S3 abstraction (`S3StorageProvider`), cryptographic volume identification (`.clipforge_volume_token`), headroom reservation (`StorageReservationCoordinator`), and safe quarantine staging (`.storage_quarantine/`).

---

## 2. Comprehensive Inventory of SQLAlchemy Models (31 Models)

All models inherit from `Base = declarative_base()` and are defined in `backend/models/models.py`.

| # | Model Class | Table Name | Owning Domain | Primary Key | Foreign Key References & Cascades | Key Columns, Types & Constraints |
|---|---|---|---|---|---|---|
| 1 | `Video` | `videos` | Ingestion / Media | `id` (String UUID) | `upload_batch_id` -> `upload_batches.id` (RESTRICT) | `youtube_id` (String), `title` (String), `local_path` (String), `duration` (Float), `channel_id` (String unconstrained), `transcription_status` (String), `reservation_state` (String) |
| 2 | `StorageReservationCoordinator` | `storage_reservation_coordinators` | Storage Safety | `id` (String UUID) | None | `volume_id` (String), `cluster_id` (String), `total_reserved_bytes` (BigInteger), `headroom_bytes` (BigInteger), `active_leases_count` (Integer) |
| 3 | `UploadBatch` | `upload_batches` | Upload Studio | `id` (String UUID) | None | `title` (String), `batch_status` (String), `total_videos` (Integer), `processed_videos` (Integer), `total_size_bytes` (BigInteger), `storage_state` (String) |
| 4 | `Clip` | `clips` | Clip Lifecycle | `id` (String UUID) | `video_id` (String unconstrained) | `start_time` (Float), `end_time` (Float), `duration` (Float), `score` (Float), `publish_status` (String), `privacy` (String, default='private'), `youtube_short_id` (String) |
| 5 | `Job` | `jobs` | Task Orchestration | `id` (String UUID) | `video_id` (String unconstrained) | `status` (String), `progress` (Float), `current_step` (String), `celery_task_id` (String), `config` (JSON), `is_test` (Boolean, Index) |
| 6 | `VideoDecision` | `video_decisions` | Channel Automation | `id` (String UUID) | `channel_id` -> `channels.id` (ON DELETE CASCADE) | `youtube_id` (String), `video_title` (String), `status` (String: pending/approved/rejected), `target_duration` (Integer), `clip_mode` (String), `expires_at` (DateTime), `is_test` (Boolean) |
| 7 | `Channel` | `channels` | Channel Governance | `id` (String UUID) | `publish_destination_id` -> `channels.id` (ON DELETE SET NULL) | `youtube_channel_id` (String Unique), `channel_name` (String), `auto_clip` (Boolean), `auto_publish` (Boolean), `auto_pilot` (Boolean), `is_destination` (Boolean), `is_test` (Boolean, Index) |
| 8 | `ChannelDestination` | `channel_destinations` | Multi-Account | `id` (String UUID) | `source_channel_id` -> `channels.id` (CASCADE), `destination_channel_id` -> `channels.id` (CASCADE) | UniqueConstraint(`source_channel_id`, `destination_channel_id`), `is_default` (Boolean) |
| 9 | `PublishTarget` | `publish_targets` | Multi-Account | `id` (String UUID) | `clip_id` -> `clips.id` (CASCADE), `destination_id` -> `channels.id` (CASCADE) | UniqueConstraint(`clip_id`, `destination_id`), `status` (String), `privacy` (String, default='public' — discrepancy), `youtube_video_id` (String) |
| 10 | `VideoMetadata` | `video_metadata` | SEO & Publishing | `video_id` (String UUID) | None | `title` (String), `description` (Text), `tags` (JSON), `hashtags` (JSON), `thumbnail_url` (String) |
| 11 | `VideoAnalytics` | `video_analytics` | Performance | `id` (String UUID) | `video_id` -> `videos.id` (ON DELETE CASCADE) | `views` (Integer), `likes` (Integer), `comments` (Integer), `retention_rate` (Float), `recorded_at` (DateTime) |
| 12 | `OptimizationLog` | `optimization_logs` | Performance | `id` (String UUID) | None | `video_id` (String), `field_changed` (String), `old_value` (Text), `new_value` (Text), `reason` (Text), `applied_at` (DateTime) |
| 13 | `VideoTrackingQueue` | `video_tracking_queues` | Performance | `id` (String UUID) | `clip_id` -> `clips.id` (ON DELETE CASCADE) | `check_count` (Integer), `next_check_at` (DateTime), `status` (String), `is_active` (Boolean) |
| 14 | `PublishRecord` | `publish_records` | Audit / Publishing | `id` (String UUID) | `clip_id` -> `clips.id` (ON DELETE CASCADE) | `channel_id` (String), `external_id` (String), `published_at` (DateTime), `status` (String), `error` (Text) |
| 15 | `ContentAnalysis` | `content_analyses` | AI Understanding | `clip_id` (String UUID) | None | `niche` (String), `topic` (String), `emotions` (JSON), `hook_type` (String), `sentiment_score` (Float), `analysis_json` (JSON) |
| 16 | `SEOAnalysis` | `seo_analyses` | SEO Intelligence | `clip_id` (String UUID) | None | `title_score` (Float), `tag_relevance` (Float), `search_volume_score` (Float), `recommendations` (JSON) |
| 17 | `ClipRetention` | `clip_retentions` | Predictive AI | `id` (String UUID) | `clip_id` -> `clips.id` (ON DELETE CASCADE) | `retention_curve` (JSON), `average_predicted_drop` (Float), `weak_moments` (JSON) |
| 18 | `OptimizationContext` | `optimization_contexts` | Performance | `video_id` (String UUID) | None | `niche` (String), `top_performing_tags` (JSON), `optimal_duration_range` (JSON) |
| 19 | `PipelineMetrics` | `pipeline_metrics` | Observability | `id` (String UUID) | None | `step_name` (String), `duration_seconds` (Float), `success` (Boolean), `error_message` (Text), `recorded_at` (DateTime) |
| 20 | `ArtifactRecord` | `artifact_records` | Storage Lifecycle | `id` (String UUID) | None | `owner_type` (String), `owner_id` (String), `artifact_type` (String), `storage_key` (String), `backend` (String), `checksum` (String), `retention_policy` (String) |
| 21 | `ABExperiment` | `ab_experiments` | Growth Hacking | `id` (String UUID) | None | `clip_id` (String), `variant_a_title` (String), `variant_b_title` (String), `active_variant` (String), `vsi_score_a` (Float), `vsi_score_b` (Float) |
| 22 | `TaskExecution` | `task_executions` | Distributed Safety | `id` (String UUID) | `job_id` -> `jobs.id` (SET NULL), `clip_id` -> `clips.id` (SET NULL) | `operation` (String), `status` (String), `attempt` (Integer), `worker_id` (String), `idempotency_key` (String Unique), `last_heartbeat` (DateTime) |
| 23 | `SFXPack` | `sfx_packs` | Audio Post-Prod | `id` (String UUID) | None | `pack_name` (String), `category` (String), `description` (Text), `is_builtin` (Boolean) |
| 24 | `SFXAsset` | `sfx_assets` | Audio Post-Prod | `id` (String UUID) | `pack_id` -> `sfx_packs.id` (ON DELETE CASCADE) | `asset_name` (String), `duration` (Float), `storage_key` (String), `waveform_peaks` (JSON) |
| 25 | `ClipVariant` | `clip_variants` | Artifacts | `id` (String UUID) | `clip_id` -> `clips.id` (ON DELETE CASCADE) | `variant_type` (String), `output_path` (String), `duration` (Float), `status` (String), `variant_metadata` (JSON) |
| 26 | `ClipSFXPlan` | `clip_sfx_plans` | Audio Post-Prod | `id` (String UUID) | `clip_id` -> `clips.id` (ON DELETE CASCADE) | `plan_data` (JSON), `status` (String), `audio_mix_volume` (Float), `version` (Integer) |
| 27 | `VisualAsset` | `visual_assets` | B-Roll / Stock | `id` (String UUID) | None | `provider` (String: Pexels), `provider_asset_id` (String), `storage_key` (String), `duration` (Float), `resolution` (String) |
| 28 | `ClipVisualPlan` | `clip_visual_plans` | B-Roll Overlays | `id` (String UUID) | `clip_id` -> `clips.id` (ON DELETE CASCADE) | `overlay_segments` (JSON), `status` (String), `opacity` (Float), `scale_mode` (String) |
| 29 | `ClipHookPlan` | `clip_hook_plans` | Kinetic Hooks | `id` (String UUID) | `clip_id` -> `clips.id` (ON DELETE CASCADE) | `hook_type` (String), `hook_text` (String), `voiceover_url` (String), `zoom_factor` (Float), `status` (String) |
| 30 | `DubbingPlan` | `dubbing_plans` | Localization | `id` (String UUID) | `clip_id` -> `clips.id` (ON DELETE CASCADE) | `target_language` (String), `voice_provider` (String), `voice_id` (String), `is_voice_clone` (Boolean), `status` (String) |
| 31 | `DubbingSegment` | `dubbing_segments` | Localization | `id` (String UUID) | `plan_id` -> `dubbing_plans.id` (ON DELETE CASCADE) | `start_time` (Float), `end_time` (Float), `source_text` (Text), `translated_text` (Text), `audio_path` (String) |

---

## 3. Alembic Migration History & Linearity Verification

All 26 Alembic migrations located in `backend/alembic/versions/` were parsed and traced. The dependency graph forms a **strictly linear DAG with exactly one base revision and one head revision**:

```
[34087f10bf78] (Initial Postgres Schema)
      ↓
[5952a2dc05fe] (remove_caption_fields)
      ↓
[c21f5976f7ab] (add_video_pipeline_status)
      ↓
[753b8565da5b] (add_publishrecord)
      ↓
[37b1149c0734] (add_artifactrecord_for_phase_6)
      ↓
[7cab6f619fe6] (add_branding_fields_to_channel)
      ↓
[47b0881f6e9b] (add_taskexecution_schema & drop legacy caption columns)
      ↓
[e89c62f18286] (phase_12_broll)
      ↓
[caa3dd74cb85] (add_clip_hook_plan)
      ↓
[9015834ae299] (phase14_ab_thumbnails)
      ↓
[56f271e8c933] (add_auto_pilot_to_channels)
      ↓
[7bf7d87f0907] (add_dubbing_models)
      ↓
[a94463c56fb5] (add_config_to_jobs)
      ↓
[d7546ac12261] (add_destination_fields_to_channel)
      ↓
[04511958a388] (add_publish_destination_id_to_clip)
      ↓
[3d39d71a2820] (add_publish_destination_id_to_channel)
      ↓
[e1a2b3c4d5e6] (add_multi_destination_phase1)
      ↓
[f1b2c3d4e5f6] (add_upload_studio_phase1)
      ↓
[f2a3b4c5d6e7] (add_upload_studio_phase2)
      ↓
[f3b4c5d6e7f8] (add_clip_publishing_phase3)
      ↓
[f4c5d6e7f8a9] (add_channel_profiles_and_video_decisions)
      ↓
[a1b2c3d4e5f6] (add_is_test_to_jobs)
      ↓
[b2c3d4e5f6a7] (add_is_test_to_channels)
      ↓
[c3d4e5f6a7b8] (add_publishing_settings_and_stats_to_channels)
      ↓
[d4e5f6a7b8c9] (cascade_clip_foreign_keys)
      ↓
[e6f7a8b9c0d1] (update_clip_privacy_server_default_to_private) [HEAD]
```

### 3.1 Migration Linearity Audit Table
| # | Revision ID | Down Revision | Migration File Name | Target Tables / Changes |
|---|---|---|---|---|
| 1 | `34087f10bf78` | *None (Base)* | `34087f10bf78_initial_postgres.py` | Creates core baseline tables (`videos`, `clips`, `jobs`, `channels`, etc.) |
| 2 | `5952a2dc05fe` | `34087f10bf78` | `5952a2dc05fe_remove_caption_fields.py` | Initial purge of caption styling columns |
| 3 | `c21f5976f7ab` | `5952a2dc05fe` | `c21f5976f7ab_add_video_pipeline_status.py` | Adds `transcription_status` and pipeline checkpoints to `videos` |
| 4 | `753b8565da5b` | `c21f5976f7ab` | `753b8565da5b_add_publishrecord.py` | Adds `publish_records` audit table |
| 5 | `37b1149c0734` | `753b8565da5b` | `37b1149c0734_add_artifactrecord_for_phase_6.py` | Adds `artifact_records` for storage lifecycle and retention |
| 6 | `7cab6f619fe6` | `37b1149c0734` | `7cab6f619fe6_add_branding_fields_to_channel.py` | Adds `default_tags`, `branding_rules` to `channels` |
| 7 | `47b0881f6e9b` | `7cab6f619fe6` | `47b0881f6e9b_add_taskexecution_schema.py` | Creates `task_executions` table; drops remaining legacy caption columns |
| 8 | `e89c62f18286` | `47b0881f6e9b` | `e89c62f18286_phase_12_broll.py` | Creates `visual_assets` and `clip_visual_plans` |
| 9 | `caa3dd74cb85` | `e89c62f18286` | `caa3dd74cb85_add_clip_hook_plan.py` | Creates `clip_hook_plans` table |
| 10 | `9015834ae299` | `caa3dd74cb85` | `9015834ae299_phase14_ab_thumbnails.py` | Creates `ab_experiments` table |
| 11 | `56f271e8c933` | `9015834ae299` | `56f271e8c933_add_auto_pilot_to_channels.py` | Adds `auto_pilot` boolean flag to `channels` |
| 12 | `7bf7d87f0907` | `56f271e8c933` | `7bf7d87f0907_add_dubbing_models.py` | Creates `dubbing_plans` and `dubbing_segments` |
| 13 | `a94463c56fb5` | `7bf7d87f0907` | `a94463c56fb5_add_config_to_jobs.py` | Adds `config` JSON column to `jobs` |
| 14 | `d7546ac12261` | `a94463c56fb5` | `d7546ac12261_add_destination_fields_to_channel.py` | Adds `is_destination`, `credentials_path` to `channels` |
| 15 | `04511958a388` | `d7546ac12261` | `04511958a388_add_publish_destination_id_to_clip.py` | Adds `publish_destination_id` to `clips` |
| 16 | `3d39d71a2820` | `04511958a388` | `3d39d71a2820_add_publish_destination_id_to_channel.py` | Adds `publish_destination_id` self-referential FK to `channels` |
| 17 | `e1a2b3c4d5e6` | `3d39d71a2820` | `e1a2b3c4d5e6_add_multi_destination_phase1.py` | Creates `channel_destinations` and `publish_targets` |
| 18 | `f1b2c3d4e5f6` | `e1a2b3c4d5e6` | `f1b2c3d4e5f6_add_upload_studio_phase1.py` | Creates `upload_batches` and `storage_reservation_coordinators` |
| 19 | `f2a3b4c5d6e7` | `f1b2c3d4e5f6` | `f2a3b4c5d6e7_add_upload_studio_phase2.py` | Adds chunk upload tracking to `upload_batches` |
| 20 | `f3b4c5d6e7f8` | `f2a3b4c5d6e7` | `f3b4c5d6e7f8_add_clip_publishing_phase3.py` | Adds scheduling fields and privacy flags to `publish_targets` |
| 21 | `f4c5d6e7f8a9` | `f3b4c5d6e7f8` | `f4c5d6e7f8a9_add_channel_profiles_and_video_decisions.py` | Creates `video_decisions` table for auto-pilot workflow |
| 22 | `a1b2c3d4e5f6` | `f4c5d6e7f8a9` | `a1b2c3d4e5f6_add_is_test_to_jobs.py` | Adds `is_test` indexed column to `jobs` |
| 23 | `b2c3d4e5f6a7` | `a1b2c3d4e5f6` | `b2c3d4e5f6a7_add_is_test_to_channels.py` | Adds `is_test` indexed column to `channels` and `video_decisions` |
| 24 | `c3d4e5f6a7b8` | `b2c3d4e5f6a7` | `c3d4e5f6a7b8_add_publishing_settings_and_stats_to_channels.py` | Adds publishing cooldowns and cached statistics to `channels` |
| 25 | `d4e5f6a7b8c9` | `c3d4e5f6a7b8` | `d4e5f6a7b8c9_cascade_clip_foreign_keys.py` | Enforces `ON DELETE CASCADE` from `clips.id` to all child plan tables |
| 26 | `e6f7a8b9c0d1` | `d4e5f6a7b8c9` | `e6f7a8b9c0d1_update_clip_privacy_server_default.py` | Updates `clips.privacy` server default to `'private'` [HEAD] |

---

## 4. Schema Integrity, Foreign Keys & Technical Debt

### 4.1 Unconstrained Foreign Keys on Core Entities
- **`clips.video_id`:** Defined as `sa.Column('video_id', sa.String(), nullable=False)` in `models.py:233` without a database-level `sa.ForeignKey('videos.id')`.
  - *Risk Analysis:* If a `Video` record is deleted directly via raw SQL or external database administration tool, associated `Clip` rows become orphaned. Deletion through FastAPI routes (`backend/api/routes/videos.py`) performs application-level cascaded cleanup, but the schema lacks referential integrity enforcement at the PostgreSQL catalog level.
- **`jobs.video_id`:** Similarly declared as an unconstrained `String` in `models.py:284`.
- **`videos.channel_id`:** Declared as an unconstrained `String(100)` in `models.py:186`, not linked via foreign key to `channels.id`.

### 4.2 Cascaded Referential Integrity on Child Entities
Migration `d4e5f6a7b8c9_cascade_clip_foreign_keys.py` successfully established PostgreSQL foreign keys with `ON DELETE CASCADE` from `clips.id` to:
- `clip_variants.clip_id`
- `clip_retentions.clip_id`
- `clip_sfx_plans.clip_id`
- `clip_visual_plans.clip_id`
- `clip_hook_plans.clip_id`
- `dubbing_plans.clip_id`
- `video_tracking_queues.clip_id`
- `publish_records.clip_id`
- `task_executions.clip_id` (configured with `ON DELETE SET NULL` to preserve execution history)

### 4.3 Privacy Default Discrepancy
- **`Clip.privacy`:** Server default was updated to `'private'` in migration `e6f7a8b9c0d1`, and Python model default is `"private"`.
- **`PublishTarget.privacy`:** Declared in `backend/models/models.py:417` as `mapped_column(String(50), default="public")`.
  - *Runtime Mitigation:* In worker execution (`clip_tasks.py:795`), the task hardcodes `target_privacy = "private"`, which overrides the model default before calling `upload_short()`. However, direct ORM queries or standalone creation of `PublishTarget` records could instantiate with `"public"`.
  - *Remediation:* Align `PublishTarget.privacy` default in `models.py:417` to `"private"` and add an Alembic migration enforcing `server_default='private'`.

### 4.4 Migration Verification of Caption Purge
Migration `47b0881f6e9b` performed an explicit destructive purge of all legacy subtitle and caption columns:
- `op.drop_column('clips', 'caption')`
- `op.drop_column('clips', 'caption_style')`
- `op.drop_column('clips', 'caption_duration')`
- `op.drop_column('clips', 'caption_font_size')`
- `op.drop_column('metadata', 'caption_path')`
Direct inspection of `backend/models/models.py` confirms that zero caption or subtitle columns remain. Furthermore, `backend/models/hook.py:55` explicitly documents:
> `"Content metadata only. MUST NOT be rendered as a subtitle/caption."`

---

## 5. Storage Lifecycle, Isolation & Quarantine Architecture

The storage layer (`backend/core/storage.py`, `backend/core/storage_identity.py`) manages media assets across local NVMe storage and remote S3/MinIO buckets.

### 5.1 Storage Providers & Path Traversal Guards
- **`LocalStorageProvider`:** Implements local file storage anchored at `settings.UPLOAD_DIR` and `settings.OUTPUT_DIR`.
  - *Path Traversal Guard (`backend/core/storage.py:70-74`):* Method `_resolve_path(key)` resolves paths using `Path.resolve()` and explicitly validates `str(resolved).startswith(str(base))`. Any attempt to use `../` or relative paths escaping the storage root immediately raises `ValueError("Path traversal detected")`.
- **`S3StorageProvider`:** Integrates with AWS S3 / MinIO via `boto3`, applying client-side checksum verification and multipart streaming for large video binaries.

### 5.2 Storage Quarantine Safety Lifecycle
To prevent accidental data loss and maintain zero-mutation preview guarantees during storage cleanup, ClipForge implements a multi-stage quarantine protocol (`backend/api/routes/clips.py:431-630`):
1. **Preview Phase (`GET /api/clips/cleanup/preview`):** Queries candidates below `score_threshold` (default 60.0) older than `older_than_days` (default 7). Calculates total bytes and generates an HMAC-SHA256 preview token. **Zero files or rows are modified.**
2. **Execute Phase (`POST /api/clips/cleanup/execute`):** Validates HMAC token signature and expiration.
3. **Quarantine Staging:** Files are moved from `outputs/` into `outputs/.storage_quarantine/{clip_id}/` rather than immediate unlinking.
4. **Access Suppression:** FastAPI security route `GET /outputs/.storage_quarantine/{rest:path}` (`main.py:154`) intercepts any direct HTTP requests and returns `HTTP 404 Not Found`.
5. **Reconciliation:** Deleted clip storage is deducted from `StorageReservationCoordinator` active headroom.

### 5.3 Cryptographic Volume Identity
- **Volume Token (`.clipforge_volume_token`):** Created at the root of `UPLOAD_DIR` and `OUTPUT_DIR` containing an HMAC-SHA256 signature generated from `STORAGE_IDENTITY_SECRET`.
- **Fail-Closed Secret Validation:** `resolve_storage_identity_secret` fails closed if `STORAGE_IDENTITY_SECRET` or `SECRET_KEY` matches known insecure placeholders (`"secret"`, `"changeme"`, `"dev"`) or is shorter than 16 characters.

---

## 6. Database Operational Behavior & Session Correctness

### 6.1 Transaction Scoping & Session Safety
- **FastAPI Endpoints:** Handlers use `async with get_async_db() as db:` context managers. Sessions automatically commit or rollback on exceptions, preventing connection leaks.
- **Celery Tasks:** Workers use `with get_sync_db() as db:` context managers. Sessions are committed and closed within the task boundary before returning control to the worker pool.
- **Deadlock Avoidance:** High-concurrency operations (such as `task_executions` claiming) execute atomic `INSERT ... ON CONFLICT (idempotency_key) DO NOTHING` statements rather than SELECT-then-INSERT blocks, eliminating race conditions.

---

## 7. Database & Storage Backlog Recommendations

### Recommendation DB-001: Foreign Key Hardening on `clips.video_id` and `jobs.video_id`
- **Category:** Data Integrity / Technical Debt
- **Severity:** P2 Medium
- **Approach Comparison:**
  - *Approach A (No Change):* Rely on FastAPI application-level cascaded cleanup. Leaves database vulnerable to orphaned records if direct SQL operations occur.
  - *Approach B (Recommended Minimal Fix):* Add Alembic migration adding `sa.ForeignKey('videos.id', ondelete='CASCADE')` to `clips.video_id` and `jobs.video_id`. Pre-migration check verifies zero existing orphaned rows.
  - *Approach C (Soft Deletes):* Implement `is_deleted` flags across `videos` and `clips`. Adds query complexity and violates simple workstation architecture.
- **Estimated Size:** S (1 Alembic migration script + test verification).

### Recommendation DB-002: Model Default Alignment for `PublishTarget.privacy`
- **Category:** Technical Debt
- **Severity:** P3 Low
- **Approach Comparison:**
  - *Approach A (No Change):* Rely on worker override in `clip_tasks.py:795`.
  - *Approach B (Recommended Minimal Fix):* Update `backend/models/models.py:417` `default="private"` and add migration setting `server_default='private'` on `publish_targets.privacy`.
- **Estimated Size:** XS (1 line in `models.py` + 1 migration script).

---

*Report compiled and certified by Teamwork Worker M2 for the ClipForge Full-System Forensic Audit.*
