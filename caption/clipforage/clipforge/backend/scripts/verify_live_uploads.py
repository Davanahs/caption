import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from backend.services.publisher import get_youtube_client

yt = get_youtube_client("UCH90024qrJHA4amGRxnTldw")
ids = ["YpHobheDpk8", "kkXWbXZI_iM", "0OfOivc-tpU", "39w4TLjreFU", "L3ihlJVo_3A", "FoNMm4F9qIM"]
resp = yt.videos().list(part="snippet,status", id=",".join(ids)).execute()

print("=== VERIFICATION OF PUBLISHED VIDEOS ON YOUTUBE ===")
for item in resp.get("items", []):
    vid_id = item["id"]
    privacy = item["status"]["privacyStatus"]
    title = item["snippet"]["title"]
    pub_at = item["snippet"]["publishedAt"]
    print(f"ID: {vid_id} | Privacy: {privacy} | Uploaded: {pub_at} | Title: {title}")
