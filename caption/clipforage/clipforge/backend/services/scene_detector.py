"""
Scene Detector — PySceneDetect based camera cut and visual activity analyzer
"""
from pathlib import Path
def detect_scenes(video_path: Path) -> list[tuple[float, float]]:
    video_path = Path(video_path)
    """
    Detect camera cuts (scene changes) in the video.
    Returns a list of (start_seconds, end_seconds) for each scene.
    """
    try:
        from scenedetect import detect, ContentDetector
        print(f"[SceneDetect] Running scene detection on {video_path.name}...")
        # ContentDetector detects abrupt changes (camera cuts) using color/intensity shifts
        scene_list = detect(str(video_path), ContentDetector(threshold=27.0))
        
        scenes = []
        for start_t, end_t in scene_list:
            scenes.append((start_t.get_seconds(), end_t.get_seconds()))
            
        print(f"[SceneDetect] Detected {len(scenes)} scenes in {video_path.name}.")
        return scenes
    except Exception as e:
        print(f"[SceneDetect] Scene detection skipped or unavailable: {e}")
        return []
