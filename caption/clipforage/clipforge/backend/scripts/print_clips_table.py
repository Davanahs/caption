import json

data = json.load(open("backend/scripts/twenty_eight_clips_classification.json", encoding="utf-8"))
print("| Source Video ID | Clip ID | Rank | Score | Duration | File Size | Classification | YouTube Short |")
print("|---|---|---|---|---|---|---|---|")
for c in data:
    short_link = f"[`{c['youtube_short_id']}`](https://www.youtube.com/shorts/{c['youtube_short_id']})" if c.get("youtube_short_id") else "—"
    cls_str = "Published" if c.get("youtube_short_id") else "Valid & Ready (Excluded)"
    print(f"| `{c['video_youtube_id']}` | `{c['clip_id']}` | #{c['rank_in_video']} | {c['score']} | {c['duration']}s | {c['file_size_mb']} MB | {cls_str} | {short_link} |")
