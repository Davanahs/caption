"""
audit_and_classify_28_clips.py
==============================
Performs a rigorous, evidence-based classification of all 28 clips generated
from the 6 monitored source videos.
"""
import sys
import io
import os
import json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from backend.models.database import SyncSessionLocal
from backend.models.models import Video, Clip, Channel, PublishRecord

SOURCE_YOUTUBE_IDS = [
    "UBHOWXL4Apg",
    "Cm45rJ_ayA4",
    "MjDUTSOsUMg",
    "-rPzGJH1acU",
    "bBlahWRZ2Yw",
    "m5hidzW-_i0"
]

SIX_PUBLISHED_SHORT_IDS = {
    "UBHOWXL4Apg": "YpHobheDpk8",
    "Cm45rJ_ayA4": "kkXWbXZI_iM",
    "MjDUTSOsUMg": "0OfOivc-tpU",
    "-rPzGJH1acU": "39w4TLjreFU",
    "bBlahWRZ2Yw": "L3ihlJVo_3A",
    "m5hidzW-_i0": "FoNMm4F9qIM"
}

def audit_clips():
    print("=" * 80)
    print("PHASE 2: DETAILED AUDIT AND CLASSIFICATION OF ALL 28 GENERATED CLIPS")
    print("=" * 80)

    classification_counts = {
        "Already published successfully": 0,
        "Valid and ready (intentionally excluded by 1-clip-per-video policy)": 0,
        "Queued for publication": 0,
        "Failed or invalid": 0,
        "Blocked by eligibility rule": 0
    }

    detailed_inventory = []

    with SyncSessionLocal() as s:
        for vid in SOURCE_YOUTUBE_IDS:
            v = s.query(Video).filter_by(youtube_id=vid).first()
            if not v:
                print(f"ERROR: Video {vid} not found in database!")
                continue
            
            clips = s.query(Clip).filter_by(video_id=v.id).order_by(Clip.score.desc()).all()
            expected_short_id = SIX_PUBLISHED_SHORT_IDS[vid]
            print(f"\nSource Video: {vid} | '{v.title[:45]}' | Total Clips: {len(clips)}")

            for rank, c in enumerate(clips, 1):
                p = Path(c.output_path)
                file_exists = p.exists()
                file_size_mb = (p.stat().st_size / (1024 * 1024)) if file_exists else 0.0

                # Classification logic
                if c.youtube_short_id == expected_short_id:
                    classification = "Already published successfully"
                    notes = f"Selected as top clip (Rank #{rank}, Score={c.score}); published as YouTube Short {expected_short_id}"
                elif c.publish_status == "queued":
                    classification = "Queued for publication"
                    notes = "In publish queue"
                elif not file_exists or file_size_mb == 0:
                    classification = "Failed or invalid"
                    notes = f"Media file missing at {c.output_path}"
                elif c.duration > 60.0 or c.duration < 5.0:
                    classification = "Blocked by eligibility rule"
                    notes = f"Duration {c.duration}s outside YouTube Shorts limits [5s, 60s]"
                else:
                    classification = "Valid and ready (intentionally excluded by 1-clip-per-video policy)"
                    notes = f"Valid media artifact ({file_size_mb:.2f}MB, {c.duration:.1f}s), score={c.score}. Preserved on disk for future manual or drip publishing."

                classification_counts[classification] += 1

                detailed_inventory.append({
                    "video_youtube_id": vid,
                    "video_title": v.title,
                    "clip_id": c.id,
                    "rank_in_video": rank,
                    "score": c.score,
                    "duration": round(c.duration, 1),
                    "title": c.title,
                    "file_path": c.output_path,
                    "file_exists": file_exists,
                    "file_size_mb": round(file_size_mb, 2),
                    "publish_status": c.publish_status,
                    "youtube_short_id": c.youtube_short_id,
                    "classification": classification,
                    "notes": notes
                })

                status_tag = f"[{classification}]"
                print(f"  Clip #{rank} (ID: {c.id[:8]}..) | Score: {c.score} | Dur: {c.duration:.1f}s | Size: {file_size_mb:.1f}MB | {status_tag}")
                print(f"     Title: {c.title}")
                print(f"     Path: {c.output_path}")
                print(f"     Notes: {notes}")

    print("\n" + "=" * 80)
    print("SUMMARY CLASSIFICATION MATRIX")
    print("=" * 80)
    for cat, count in classification_counts.items():
        print(f"  {cat}: {count} clips")
    print(f"  TOTAL CLIPS AUDITED: {len(detailed_inventory)}")

    # Write out JSON audit log
    out_path = Path("backend/scripts/twenty_eight_clips_classification.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(detailed_inventory, f, indent=2)
    print(f"\nDetailed classification inventory saved to {out_path}")

if __name__ == "__main__":
    audit_clips()
