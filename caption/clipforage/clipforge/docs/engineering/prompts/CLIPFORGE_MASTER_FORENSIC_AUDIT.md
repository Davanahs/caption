# CLIPFORGE — MASTER FORENSIC AUDIT, AUTOMATION REPAIR, PROJECT MEMORY & CHANNEL MANAGEMENT

**Project:** ClipForge / ClipForge Upload Studio  
**Expected root:** `D:\automation video clips\clipforge`  
**Environment:** Windows, Docker, FastAPI, Next.js, PostgreSQL, Redis, Celery  
**Execution mode:** Investigate → inventory → diagnose → implement → verify → document → hand off.

## Mission

Work on the existing ClipForge repository. Do not start a new project or replace the existing architecture.

Complete these workstreams in order:

1. Establish durable project memory and add mandatory context-continuity rules to `AGENTS.md`.
2. Inventory every backend API endpoint and document exactly where it is defined, what it does, and which frontend actions use it.
3. Inventory every frontend page, interactive control, API call, and user action, including controls with missing or incorrect backend connections.
4. Forensically investigate and fix two user-observed automation defects:
   - More than one video cannot be selected for processing.
   - Clicking **Start Processing** shows a notification, but the Dashboard does not show the actual processing.
5. Find and document other confirmed frontend/backend inconsistencies, disconnected endpoints, missing handlers, incorrect contracts, and state-management issues.
6. Implement the pending **My YouTube Channels** management experience after inspecting the existing OAuth and publishing architecture.
7. Run appropriate tests, perform two-pass verification, and update all project records and the two final inventories.

---

[Archived from current active master prompt for project continuity governance and multi-agent fidelity]
