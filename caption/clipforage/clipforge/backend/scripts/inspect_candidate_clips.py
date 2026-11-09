import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from backend.models.database import SyncSessionLocal
from backend.models.models import Video, Clip

vids = ['UBHOWXL4Apg', 'Cm45rJ_ayA4', 'MjDUTSOsUMg', '-rPzGJH1acU', 'bBlahWRZ2Yw', 'm5hidzW-_i0']
with SyncSessionLocal() as s:
    for vid in vids:
        v = s.query(Video).filter_by(youtube_id=vid).first()
        print(f"\n=== Video: {vid} | {v.title[:50]} (DB: {v.id}) ===")
        clips = s.query(Clip).filter_by(video_id=v.id).order_by(Clip.created_at.asc()).all()
        for i, c in enumerate(clips):
            print(f"  Clip [{i+1}] ID={c.id}")
            print(f"     Score: {getattr(c, 'score', None)} | Duration: {c.duration:.1f}s | Path: {c.output_path}")
            print(f"     Title: {c.title}")
            print(f"     PubStatus: {c.publish_status} | ShortID: {c.youtube_short_id}")
