import subprocess
import json
import logging
from pathlib import Path
from backend.models.retention import RetentionPoint, DropoffRisk, RetentionAnalysis
import math

logger = logging.getLogger(__name__)

class ViralityPredictor:
    def __init__(self):
        # We can configure weights and thresholds here
        self.audio_weight = 0.4
        self.motion_weight = 0.4
        self.scene_weight = 0.2

    def get_duration(self, video_path: Path) -> float:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
        ]
        try:
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
            return float(output.strip())
        except Exception as e:
            logger.error(f"Error getting duration: {e}")
            return 0.0

    def get_audio_rms(self, video_path: Path, duration: float) -> list[float]:
        # astats reset=1 calculates stats per frame (which for audio is usually a short block)
        # However, astats on long audio can be slow. A faster way is using silencedetect 
        # or ebur128, or simply volume detect. But to get it per second, we can use `asetpts` and `astats`.
        # Even simpler: just use `showvolume`? No, ffprobe can extract RMS per second using `astats`.
        # To make it exactly 1 per second:
        safe_path = str(video_path).replace('\\', '/').replace(':', '\\:')
        cmd = [
            "ffprobe", "-v", "error", "-f", "lavfi",
            f"amovie='{safe_path}',asetnsamples=n=44100,astats=metadata=1:reset=1",
            "-show_entries", "frame_tags=lavfi.astats.Overall.RMS_level",
            "-of", "json"
        ]
        # We expect around `duration` number of frames if sample rate is 44100 and we group by 44100 samples
        try:
            output = subprocess.check_output(cmd, text=True)
            data = json.loads(output)
            frames = data.get("frames", [])
            rms_per_sec = []
            for f in frames:
                tags = f.get("tags", {})
                rms = tags.get("lavfi.astats.Overall.RMS_level", "-inf")
                if rms == "-inf":
                    rms_per_sec.append(-100.0)
                else:
                    rms_per_sec.append(float(rms))
            
            # Interpolate to match exact seconds if mismatch
            sec_len = math.ceil(duration)
            result = []
            if not rms_per_sec:
                return [-100.0] * sec_len
            
            for s in range(sec_len):
                if s < len(rms_per_sec):
                    result.append(rms_per_sec[s])
                else:
                    result.append(rms_per_sec[-1])
            return result
        except Exception as e:
            logger.error(f"Error getting audio RMS: {e}")
            return [-100.0] * math.ceil(duration)

    def get_video_motion(self, video_path: Path, duration: float) -> list[float]:
        safe_path = str(video_path).replace('\\', '/').replace(':', '\\:')
        cmd = [
            "ffprobe", "-v", "error", "-f", "lavfi",
            f"movie='{safe_path}',select='gte(scene,0)'", 
            "-show_entries", "frame=pkt_pts_time:frame_tags=lavfi.scene_score",
            "-of", "json"
        ]
        
        try:
            output = subprocess.check_output(cmd, text=True)
            data = json.loads(output)
            frames = data.get("frames", [])
            
            sec_len = math.ceil(duration)
            motion_per_sec = [0.0] * sec_len
            count_per_sec = [0] * sec_len
            
            for f in frames:
                t = float(f.get("pkt_pts_time", 0.0))
                tags = f.get("tags", {})
                score = float(tags.get("lavfi.scene_score", 0.0))
                s_idx = min(int(t), sec_len - 1)
                motion_per_sec[s_idx] += score
                count_per_sec[s_idx] += 1
                
            for i in range(sec_len):
                if count_per_sec[i] > 0:
                    motion_per_sec[i] /= count_per_sec[i]
            
            return motion_per_sec
        except Exception as e:
            logger.error(f"Error getting video motion: {e}")
            return [0.0] * math.ceil(duration)

    def analyze_video(self, video_path: Path, clip_id: str) -> RetentionAnalysis:
        duration = self.get_duration(video_path)
        if duration <= 0:
            return RetentionAnalysis(clip_id=clip_id, duration=0, analysis_version="v1.0-heuristic", points=[], risks=[])
            
        sec_len = math.ceil(duration)
        audio_rms = self.get_audio_rms(video_path, duration)
        video_motion = self.get_video_motion(video_path, duration)
        
        points = []
        for s in range(sec_len):
            # Audio score mapping (-100 to 0) -> (0 to 100)
            a_rms = audio_rms[s]
            # Normal conversation is around -20 to -10 RMS. Silence is -50+.
            # Let's map -50 (score 0) to -10 (score 100)
            a_score = max(0.0, min(100.0, (a_rms + 50) * (100.0 / 40.0)))
            
            # Motion score mapping (0 to 1.0) -> (0 to 100)
            v_mot = video_motion[s]
            # Typically scene scores are low (0.01 - 0.1 for subtle motion).
            # We map 0.05 to 100.
            m_score = max(0.0, min(100.0, v_mot * (100.0 / 0.05)))
            
            # Simple combined score
            retention = self.audio_weight * a_score + self.motion_weight * m_score + self.scene_weight * 50.0 # Placeholder for scene activity
            
            risk_level = 'low'
            if retention < 30:
                risk_level = 'critical'
            elif retention < 70:
                risk_level = 'high'
            elif retention < 85:
                risk_level = 'medium'
                
            points.append(RetentionPoint(
                timestamp=s,
                retention_score=round(retention, 2),
                audio_score=round(a_score, 2),
                motion_score=round(m_score, 2),
                scene_activity_score=50.0,
                risk_level=risk_level
            ))

        # Build contiguous dropoff risks
        risks = []
        current_risk = None
        
        for p in points:
            if p.retention_score < 70:
                if not current_risk:
                    current_risk = {
                        "start_time": float(p.timestamp),
                        "end_time": float(p.timestamp + 1),
                        "scores": [p.retention_score],
                        "audio_scores": [p.audio_score]
                    }
                else:
                    current_risk["end_time"] = float(p.timestamp + 1)
                    current_risk["scores"].append(p.retention_score)
                    current_risk["audio_scores"].append(p.audio_score)
            else:
                if current_risk:
                    # Finalize risk
                    avg_score = sum(current_risk["scores"]) / len(current_risk["scores"])
                    avg_audio = sum(current_risk["audio_scores"]) / len(current_risk["audio_scores"])
                    
                    sev = 'high' if avg_score < 30 else 'medium'
                    reason = 'silence' if avg_audio < 20 else 'low_visual_motion'
                    
                    interventions = ["zoom_push"]
                    if avg_audio < 20:
                        interventions.append("sfx_opportunity")
                        
                    risks.append(DropoffRisk(
                        start_time=min(duration, current_risk["start_time"]),
                        end_time=min(duration, current_risk["end_time"]),
                        severity=sev,
                        primary_reason=reason,
                        contributing_reasons=[],
                        confidence=0.8,
                        suggested_intervention_types=interventions
                    ))
                    current_risk = None
                    
        if current_risk:
            avg_score = sum(current_risk["scores"]) / len(current_risk["scores"])
            avg_audio = sum(current_risk["audio_scores"]) / len(current_risk["audio_scores"])
            sev = 'high' if avg_score < 30 else 'medium'
            reason = 'silence' if avg_audio < 20 else 'low_visual_motion'
            interventions = ["zoom_push"]
            if avg_audio < 20:
                interventions.append("sfx_opportunity")
            risks.append(DropoffRisk(
                start_time=min(duration, current_risk["start_time"]),
                end_time=min(duration, current_risk["end_time"]),
                severity=sev,
                primary_reason=reason,
                contributing_reasons=[],
                confidence=0.8,
                suggested_intervention_types=interventions
            ))

        return RetentionAnalysis(
            clip_id=clip_id,
            duration=duration,
            analysis_version="v1.0-heuristic",
            points=points,
            risks=risks
        )

    def analyze_clip(self, video_path: str | Path, clip_id: str = "") -> RetentionAnalysis:
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found at: {path}")
        return self.analyze_video(path, clip_id)
