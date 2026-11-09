import json
from backend.models.database import SyncSessionLocal
from backend.models.models import Clip, PublishTarget, Channel

with SyncSessionLocal() as s:
    c1 = s.query(Clip).filter_by(id="988b9d0d-1244-4e57-9771-f3d0b1d552d9").first()
    if c1:
        c1.title = "Software Engineer Salary vs Cost of Living: Which City Wins? 🏙️"
        c1.description = "Software Engineer Salary vs Cost of Living: Which City Wins? Real tech pay breakdown. #Shorts #tech #coding"
        c1.tags = json.dumps(["software engineer", "salary", "cost of living", "tech jobs", "coding"])
        c1.privacy = "private"
    
    c2 = s.query(Clip).filter_by(id="f9bedd47-4eb4-411d-ab9d-6fff5205ce5a").first()
    if c2:
        c2.youtube_short_id = None
        c2.publish_status = "draft"
        c2.privacy = "private"

    # Ensure all candidate clips have privacy='private'
    clip_ids = [
        "ab96872a-e81f-482d-98eb-2024919e3bbb", # Batch A1
        "988b9d0d-1244-4e57-9771-f3d0b1d552d9", # Batch A2
        "a0dfbe13-bb91-4a60-bb7a-dcbdf02c1466", # Batch A3
        "b1b8af97-d7b9-4873-baf0-e0013f2660a1", # Batch B1
        "f9bedd47-4eb4-411d-ab9d-6fff5205ce5a", # Batch B2
        "295a2da3-7a04-4a85-90d8-1e981d84b534", # Batch B3
    ]
    for cid in clip_ids:
        cl = s.query(Clip).filter_by(id=cid).first()
        if cl:
            cl.privacy = "private"
            # Also reset any existing targets to pending with private
            tgts = s.query(PublishTarget).filter_by(clip_id=cid).all()
            for t in tgts:
                t.status = "pending"
                t.privacy = "private"
                t.youtube_video_id = None
    s.commit()
    print("Cleaned and prepared all candidate clips for private publishing.")
