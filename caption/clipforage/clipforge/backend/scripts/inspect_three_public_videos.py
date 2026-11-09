import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from backend.services.publisher import get_youtube_client

channel_id = "UCH90024qrJHA4amGRxnTldw"
yt = get_youtube_client(channel_id)
ids = ["39w4TLjreFU", "L3ihlJVo_3A", "FoNMm4F9qIM"]
resp = yt.videos().list(part="snippet,status", id=",".join(ids)).execute()

for item in resp.get("items", []):
    vid_id = item["id"]
    snippet = item["snippet"]
    status = item["status"]
    print("=" * 60)
    print(f"Video ID: {vid_id}")
    print(f"Channel ID: {snippet.get('channelId')}")
    print(f"Matches ClipSee: {snippet.get('channelId') == channel_id}")
    print(f"Title: {snippet.get('title')}")
    print(f"Description length: {len(snippet.get('description', ''))}")
    print(f"Category ID: {snippet.get('categoryId')}")
    print(f"Current Privacy: {status.get('privacyStatus')}")
