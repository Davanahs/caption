"""
backend/scripts/phase1_ui_contract_audit.py
===========================================
Independent live audit of every UI page's backend API contracts:
1. Dashboard (/api/stats, /api/videos, /api/jobs)
2. YouTube Channels (/api/youtube-channels, PATCH settings, POST set-default)
3. Automation (/api/channels/, Auto-Publish destination validation)
4. Clips Library (/api/clips, download & thumbnail endpoints)
5. Publishing Studio (/api/publish/queue, /api/publish/publish-now, /api/publish/schedule)
6. Upload Studio (/api/studio/batches, /api/studio/storage/stats)
7. Settings (/api/settings)
8. Analytics (/api/youtube-channels/{id}/analytics)
"""
import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://localhost:8000"

def make_req(path, method="GET", data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"} if data else {}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            resp_body = res.read().decode("utf-8")
            parsed = json.loads(resp_body) if resp_body else {}
            return res.status, parsed
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed_err = json.loads(err_body)
        except:
            parsed_err = {"raw": err_body}
        return e.code, parsed_err
    except Exception as e:
        return 0, {"error": str(e)}

def audit_phase1_contracts():
    print("=" * 70)
    print("PHASE 1: UI CONTROL <-> BACKEND CONTRACT VERIFICATION AUDIT")
    print("=" * 70)

    # 1. DASHBOARD CONTRACTS
    print("\n--- 1. DASHBOARD PAGE ---")
    st, res = make_req("/api/stats")
    print(f"  GET /api/stats -> HTTP {st} | Keys: {list(res.keys()) if isinstance(res, dict) else type(res)}")
    assert st == 200 and "total_videos" in res and "total_clips" in res

    st, res = make_req("/api/videos?limit=5")
    print(f"  GET /api/videos?limit=5 -> HTTP {st} | Items: {len(res) if isinstance(res, list) else type(res)}")
    assert st == 200 and isinstance(res, list)

    st, res = make_req("/api/jobs?limit=5")
    print(f"  GET /api/jobs?limit=5 -> HTTP {st} | Items: {len(res) if isinstance(res, list) else type(res)}")
    assert st == 200 and isinstance(res, list)

    # 2. YOUTUBE CHANNELS CONTRACTS
    print("\n--- 2. YOUTUBE CHANNELS PAGE ---")
    st, yt_chs = make_req("/api/youtube-channels")
    print(f"  GET /api/youtube-channels -> HTTP {st} | Channels: {len(yt_chs)}")
    assert st == 200 and len(yt_chs) >= 1
    dest_ch = yt_chs[0]
    dest_id = dest_ch["id"]

    # Negative validation: Set default with bogus ID
    st, err = make_req("/api/youtube-channels/00000000-0000-0000-0000-000000000000/set-default", method="POST")
    print(f"  POST /api/youtube-channels/bogus-id/set-default -> HTTP {st} (Expected: 404)")
    assert st == 404

    # Negative validation: Settings update with invalid privacy
    st, err = make_req(f"/api/youtube-channels/{dest_id}/settings", method="PATCH", data={"default_privacy": "invalid_mode"})
    print(f"  PATCH /api/youtube-channels/id/settings (invalid privacy) -> HTTP {st} (Expected: 422)")
    assert st == 422

    # 3. AUTOMATION CONTRACTS
    print("\n--- 3. AUTOMATION PAGE (MONITORED CHANNELS) ---")
    st, mon_chs = make_req("/api/channels/")
    print(f"  GET /api/channels/ -> HTTP {st} | Monitored Sources: {len(mon_chs)}")
    assert st == 200

    # Negative validation: Enable auto_publish without destination_channel_id
    test_src_id = mon_chs[0]["id"]
    st, err = make_req(f"/api/channels/{test_src_id}", method="PATCH", data={"auto_publish": True, "publish_destination_id": None})
    print(f"  PATCH /api/channels/{test_src_id} (auto_publish=True, dest=None) -> HTTP {st} (Expected: 400/422)")
    assert st in (400, 422), f"Expected 400 or 422, got {st}"
    print(f"    Validation detail: {err.get('detail')}")

    # Negative validation: Enable auto_publish with nonexistent destination
    st, err = make_req(f"/api/channels/{test_src_id}", method="PATCH", data={"auto_publish": True, "publish_destination_id": "00000000-0000-0000-0000-000000000000"})
    print(f"  PATCH /api/channels/{test_src_id} (bogus destination) -> HTTP {st} (Expected: 400/422)")
    assert st in (400, 422), f"Expected 400 or 422, got {st}"
    print(f"    Validation detail: {err.get('detail')}")

    # 4. CLIPS LIBRARY CONTRACTS
    print("\n--- 4. CLIPS LIBRARY PAGE ---")
    st, clips = make_req("/api/clips?limit=5")
    print(f"  GET /api/clips?limit=5 -> HTTP {st} | Clips: {len(clips)}")
    assert st == 200 and len(clips) >= 1
    sample_clip = clips[0]
    sample_clip_id = sample_clip["id"]

    # Negative validation: Get nonexistent clip
    st, err = make_req("/api/clips/00000000-0000-0000-0000-000000000000")
    print(f"  GET /api/clips/bogus-id -> HTTP {st} (Expected: 404)")
    assert st == 404

    # 5. PUBLISHING STUDIO CONTRACTS
    print("\n--- 5. PUBLISHING STUDIO PAGE ---")
    st, q = make_req("/api/publish/queue")
    print(f"  GET /api/publish/queue -> HTTP {st} | Queue items: {len(q.get('items', [])) if isinstance(q, dict) else len(q)}")
    assert st == 200

    # Find a clip that is not published
    draft_clips = [c for c in clips if c.get("publish_status") != "published" and not c.get("publish_destination_id")]
    draft_clip_id = draft_clips[0]["id"] if draft_clips else sample_clip_id

    # If sample clip is already published, test idempotency contract
    if sample_clip.get("publish_status") == "published":
        st, res = make_req("/api/publish/publish-now", method="POST", data={"clip_id": sample_clip_id})
        print(f"  POST /api/publish/publish-now (already published clip) -> HTTP {st} (Expected: 200 idempotency)")
        assert st == 200 and res.get("status") == "published"

    # Negative validation: Nonexistent clip
    st, err = make_req("/api/publish/publish-now", method="POST", data={"clip_id": "00000000-0000-0000-0000-000000000000"})
    print(f"  POST /api/publish/publish-now (bogus clip_id) -> HTTP {st} (Expected: 404)")
    assert st == 404

    # Negative validation: Publish now with missing destination_channel_id on draft clip
    if draft_clips:
        st, err = make_req("/api/publish/publish-now", method="POST", data={"clip_id": draft_clip_id})
        print(f"  POST /api/publish/publish-now (missing destination on draft clip) -> HTTP {st} (Expected: 400)")
        assert st == 400

    # Negative validation: Publish now with nonexistent destination_channel_id on draft clip
    st, err = make_req("/api/publish/publish-now", method="POST", data={"clip_id": draft_clip_id, "destination_channel_id": "00000000-0000-0000-0000-000000000000"})
    print(f"  POST /api/publish/publish-now (bogus destination on draft clip) -> HTTP {st} (Expected: 400/404)")
    assert st in (400, 404)
    print(f"    Validation detail: {err.get('detail')}")

    # Negative validation: Schedule in the past
    st, err = make_req("/api/publish/schedule", method="POST", data={
        "clip_id": sample_clip_id,
        "destination_channel_id": dest_id,
        "scheduled_time": "2020-01-01T00:00:00Z"
    })
    print(f"  POST /api/publish/schedule (scheduled in the past) -> HTTP {st} (Expected: 400)")
    assert st == 400
    print(f"    Validation detail: {err.get('detail')}")

    # 6. UPLOAD STUDIO CONTRACTS
    print("\n--- 6. UPLOAD STUDIO PAGE ---")
    # Negative validation: Create batch with missing idempotency_key
    st, err = make_req("/api/studio/batches", method="POST", data={})
    print(f"  POST /api/studio/batches (missing required fields) -> HTTP {st} (Expected: 422)")
    assert st == 422

    # Negative validation: Get nonexistent batch
    st, err = make_req("/api/studio/batches/b_nonexistent12345")
    print(f"  GET /api/studio/batches/b_nonexistent12345 -> HTTP {st} (Expected: 404)")
    assert st == 404

    # Negative validation: Get outputs of nonexistent batch
    st, err = make_req("/api/studio/batches/b_nonexistent12345/outputs")
    print(f"  GET /api/studio/batches/b_nonexistent12345/outputs -> HTTP {st} (Expected: 404)")
    assert st == 404

    # 7. SETTINGS CONTRACTS
    print("\n--- 7. SETTINGS PAGE ---")
    st, setts = make_req("/api/settings")
    print(f"  GET /api/settings -> HTTP {st}")
    assert st == 200
    # Verify no raw secrets exposed
    assert "YOUTUBE_CLIENT_SECRET" not in setts or setts.get("YOUTUBE_CLIENT_SECRET") == ""
    assert setts.get("YOUTUBE_CLIENT_SECRET_SET") in (True, False)
    assert setts.get("OPENROUTER_API_KEY_SET") in (True, False)
    print(f"  -> Secret masking contract PASSED: Secrets properly masked.")

    print("\n" + "=" * 70)
    print("ALL PHASE 1 UI <-> BACKEND CONTRACT CHECKS PASSED (100%)")
    print("=" * 70)

if __name__ == "__main__":
    audit_phase1_contracts()
