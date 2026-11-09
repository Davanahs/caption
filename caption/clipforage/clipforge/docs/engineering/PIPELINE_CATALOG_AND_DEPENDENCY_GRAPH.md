# ClipForge Pipeline Catalog & Dependency Graph

**Document Type:** Authoritative Architecture Pipeline & Dependency Specification  
**Governing Standard:** `MASTER_ENGINEERING_RULEBOOK.md` & `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md`  
**Repository Root:** `d:\automation video clips\clipforge`  
**Active Phase:** Phase 0.1 (Baseline Reconciliation & Tracking)  
**Last Updated:** 2026-10-13  

---

## 1. End-to-End Processing Architecture

```mermaid
flowchart TD
    subgraph Intake_Layer [Stage 1: Intake & Media Validation (L4)]
        YT_IN[YouTube URL / Channels] -->|yt-dlp| DL_TASK[download_task]
        STD_IN[Upload Studio Chunk Stream] -->|RFC 7233| VAL_IN[output_validator]
    end

    subgraph Orchestration_Layer [Stage 2: Orchestration & Queue (L5)]
        JOB_REC[Job Record Created: status=queued]
        CELERY_DISP[Celery Task Dispatch: start_video_processing_task]
        JOB_REC --> CELERY_DISP
        DL_TASK --> JOB_REC
        VAL_IN --> JOB_REC
    end

    subgraph Audio_Analysis_Layer [Stage 3: Audio & Moment Analysis (L7)]
        AUD_EX[extract_audio_task: 16kHz mono]
        TR_TASK[transcribe_task: Whisper / Groq]
        CAND_TASK[candidate_generation_task]
        SCOR_TASK[scoring_task: AI / Heuristic]
        
        CELERY_DISP --> AUD_EX --> TR_TASK --> CAND_TASK --> SCOR_TASK
    end

    subgraph Video_Cutting_Layer [Stage 4: Core Video Processing (L6)]
        CHORD_HDR[Celery Chord: Parallel Clip Workers]
        REFR_TASK[reframe_task: 9:16 Visual Layouts]
        REND_TASK[render_task: FFmpeg Multi-core]
        VAL_OUT[output_validation_task: Duration <= 30s]
        
        SCOR_TASK --> CHORD_HDR
        CHORD_HDR --> REFR_TASK --> REND_TASK --> VAL_OUT
    end

    subgraph Aggregation_Layer [Stage 5: Aggregation & Artifact Durability (L3, L5)]
        AGG_BODY[job_completion_aggregation_task]
        VAL_OUT --> AGG_BODY
        AGG_BODY -->|All Clips Pass| JOB_COMP[Job.status = completed]
        AGG_BODY -->|Partial Failures| JOB_FAIL[Job.status = completed_with_failures]
    end

    subgraph Publishing_Layer [Stage 6: Publishing & Tracking (L8)]
        DEST_RES[Destination Selection: Channel / Default]
        PUB_TASK[publish_clip_task: YouTube Data API v3]
        TRACK_Q[VideoTrackingQueue: Post-publish SEO & A/B]
        
        JOB_COMP -.->|Manual or Auto| DEST_RES --> PUB_TASK --> TRACK_Q
    end
```

---

## 2. Stage-by-Stage Processing Trace

| Stage | Input | Responsible Module / Function | Output | Database Entities | Artifacts on Disk | State Transitions | Upstream Dependencies | Downstream Consumers | Verified Status |
|---|---|---|---|---|---|---|---|---|---|
| **1. Intake & Validation** | YouTube URL or uploaded file chunks (<=10MB) | `backend/services/downloader.py`, `backend/tasks/video_tasks.py` (`download_task`), `backend/api/routes/studio.py` | Source MP4 video validated via FFprobe | `Video`, `UploadBatch`, `BatchVideoItem` | `uploads/<video_id>/source.mp4` | `Video.status`: `downloading` -> `validating` -> `ready` | L1 (Config), L3 (Storage Quota) | Stage 2 (Orchestration) | `VERIFIED` |
| **2. Job Dispatch & Queue** | Validated source video ID, configuration options | `backend/tasks/orchestration.py` (`start_video_processing_task`), `backend/models/db_sync.py` | Queued Celery processing pipeline | `Job` | None | `Job.status`: `pending` -> `processing` (progress: 10%) | Stage 1 (Intake) | Stage 3 (Analysis) | `VERIFIED` |
| **3. Audio Extraction & Transcription** | `source.mp4` | `backend/tasks/audio_tasks.py` (`extract_audio_task`, `transcribe_task`), `backend/services/transcriber.py` | 16kHz mono audio, word-level timestamp transcript | `Job` (progress: 25%) | `uploads/<video_id>/audio.mp3` | `Job.current_step`: `transcribing` | Stage 2 (Job Dispatch) | Stage 4 (Moment Scoring) | `VERIFIED` |
| **4. Moment Analysis & Scoring** | Transcript JSON, scene changes | `backend/tasks/analysis_tasks.py` (`candidate_generation_task`, `scoring_task`), `backend/services/clip_scorer.py` | Top N candidate time intervals (15.0s–30.0s) | `Clip` records created (`draft`) | None | `Job.current_step`: `analyzing` -> `selecting` (progress: 50%) | Stage 3 (Transcription) | Stage 5 (Video Cutting Chord) | `VERIFIED` |
| **5. Reframe & Rendering Chord** | Source video + candidate intervals + layout mode | `backend/tasks/video_tasks.py` (`reframe_task`, `render_task`), `backend/services/reframe_engine.py`, `backend/services/layout_engine.py` | 9:16 vertical MP4 video (H.264 / AAC) | `Clip.status`: `rendering` -> `completed` | `outputs/<video_id>/clips/<clip_id>/final.mp4` | Parallel clip progress (progress: 50%..85%) | Stage 4 (Candidate Selection) | Stage 6 (Validation & Aggregation) | `VERIFIED` |
| **6. Output Validation** | Rendered `final.mp4` | `backend/tasks/video_tasks.py` (`output_validation_task`), `backend/services/output_validator.py` | Verified MP4: duration <= 30.0s, vertical aspect, non-empty audio | `Clip` record updated | `outputs/<video_id>/clips/<clip_id>/thumb_a.jpg` | `Clip.status`: `completed` or `failed` | Stage 5 (Render) | Stage 7 (Job Aggregation) | `VERIFIED` |
| **7. Job Aggregation** | Results of chord header subtasks | `backend/tasks/orchestration.py` (`job_completion_aggregation_task`, `handle_pipeline_failure_task`) | Terminal job state, released disk reservations | `Job` record terminalized | None | `Job.status`: `completed`, `completed_with_failures`, or `failed` (progress: 100%) | Stage 6 (All Clips Validated) | Stage 8 (Publishing) | `VERIFIED` |
| **8. Multi-Destination Publishing** | Completed clip ID, destination channel ID, metadata | `backend/tasks/clip_tasks.py` (`publish_clip_task`), `backend/services/publisher.py` | Published YouTube Short, tracking entry | `PublishRecord`, `Clip.published_at` | `tokens/youtube_token_{id}.json` | `Clip.publish_status`: `publishing` -> `published` | Stage 7 (Completed Job) | Stage 9 (Post-Publish Tracking) | `VERIFIED` (Mock publisher verified; live uploads blocked by policy) |
| **9. Post-Publish Tracking & SEO** | YouTube Short ID, initial stats | `backend/services/auto_optimizer.py`, `backend/tasks/clip_tasks.py` (`track_and_optimize_clips`) | 48-hour velocity tracking, A/B title swaps | `seo_analyses`, `ab_test_experiments` | None | Periodic evaluation | Stage 8 (Published Short) | Feedback to prompt memory | `PARTIALLY VERIFIED` |

---

## 3. Strict Product Invariants Enforced in Pipeline

1. **Duration Cap Invariant (Shorts <= 30.0s):**
   - Validated at candidate generation: candidate window bounded between `15.0s` and `30.0s`.
   - Validated post-render in `output_validator.py`: any clip exceeding `30.0s` is rejected as failed.
2. **Zero Caption / Subtitle Burn-In Invariant:**
   - Word-level transcript generated by Whisper / Groq is reserved strictly for moment scoring, semantic analysis, and title/description metadata synthesis.
   - FFmpeg command generators in `clip_cutter.py`, `reframe_engine.py`, and `layout_engine.py` are strictly prohibited from including `subtitles=`, `ass=`, or `drawtext=` subtitle overlay filters.
3. **Decoupled Publishing Lifecycle Invariant:**
   - Processing completion transitions Job to `completed` and Clip to `draft` (or `ready`).
   - Processing never automatically publishes without deliberate user configuration or explicit scheduled job initiation.
4. **Storage Durability & Single Reservation Release:**
   - Intake reserves `1.5x` estimated video size on disk.
   - Reservations are tracked in database models (`UploadBatch`, `BatchVideoItem`).
   - Cleaning or deletion cannot release reservations more than once; source media cannot be wiped while referencing active jobs exist.
