"""
Audio Analysis Module using Praat and Parselmouth.
Provides fundamental frequency (F0/pitch), intensity (dB), and pause/silence extraction.

Assumptions & Default Settings:
  - Default Pitch Floor: 75.0 Hz (standard Praat baseline for general male/female speech).
  - Default Pitch Ceiling: 500.0 Hz (configurable for higher or lower registers).
  - Pitch Method: Autocorrelation (To Pitch (ac) in Praat).
  - Silence Threshold: -25.0 dB relative to peak intensity.
  - Minimum Pause Duration: 0.25 seconds (250 ms standard speech boundary).
  - Minimum Sounding Duration: 0.10 seconds (100 ms).
"""

import os
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import parselmouth
from parselmouth.praat import call as praat_call


@dataclass
class AudioAnalysisConfig:
    pitch_floor: float = 75.0
    pitch_ceiling: float = 500.0
    time_step: Optional[float] = None
    silence_threshold_db: float = -25.0  # Relative to peak intensity
    min_pause_duration: float = 0.25      # Seconds
    min_sounding_duration: float = 0.10   # Seconds
    include_timeseries: bool = False      # If False, omits raw sample arrays to keep JSON compact


class AudioAnalyzer:
    """
    Local, deterministic acoustic speech analyzer wrapping Praat via Parselmouth.
    Does not require external APIs, cloud connectivity, or machine learning models.
    """

    def __init__(self, config: Optional[AudioAnalysisConfig] = None):
        self.config = config or AudioAnalysisConfig()

    def analyze_file(
        self,
        audio_path: str,
        intervals: Optional[List[Dict[str, Any]]] = None,
        override_config: Optional[AudioAnalysisConfig] = None,
    ) -> Dict[str, Any]:
        """
        Analyze an audio file from disk. Handles missing, invalid, or empty files gracefully.
        """
        start_wall_time = time.perf_counter()
        cfg = override_config or self.config

        # 1. Basic File Path Validations
        if not audio_path or not isinstance(audio_path, str):
            return self._build_error_response(
                audio_path=str(audio_path),
                error_type="InvalidPathError",
                error_message="The provided audio path is empty or not a valid string.",
                duration_seconds=time.perf_counter() - start_wall_time,
            )

        if not os.path.exists(audio_path):
            return self._build_error_response(
                audio_path=audio_path,
                error_type="FileNotFoundError",
                error_message=f"Audio file does not exist at path: '{audio_path}'",
                duration_seconds=time.perf_counter() - start_wall_time,
            )

        try:
            file_size_bytes = os.path.getsize(audio_path)
            if file_size_bytes == 0:
                return self._build_error_response(
                    audio_path=audio_path,
                    error_type="EmptyFileError",
                    error_message=f"Audio file '{audio_path}' is empty (0 bytes).",
                    duration_seconds=time.perf_counter() - start_wall_time,
                )
        except OSError as e:
            return self._build_error_response(
                audio_path=audio_path,
                error_type="FileAccessError",
                error_message=f"Cannot read file metadata: {e}",
                duration_seconds=time.perf_counter() - start_wall_time,
            )

        # 2. Load Sound via Parselmouth
        try:
            sound = parselmouth.Sound(audio_path)
        except parselmouth.PraatError as pe:
            return self._build_error_response(
                audio_path=audio_path,
                error_type="InvalidAudioFormatError",
                error_message=f"Praat failed to read '{audio_path}'. File may be corrupt or an unsupported format: {pe}",
                duration_seconds=time.perf_counter() - start_wall_time,
            )
        except Exception as e:
            return self._build_error_response(
                audio_path=audio_path,
                error_type="AudioLoadException",
                error_message=f"Unexpected failure reading audio file '{audio_path}': {e}",
                duration_seconds=time.perf_counter() - start_wall_time,
            )

        # 3. Analyze loaded sound
        result = self.analyze_sound(sound, intervals=intervals, config=cfg)
        result["file_path"] = audio_path
        result["file_size_bytes"] = file_size_bytes
        result["analysis_duration_seconds"] = round(time.perf_counter() - start_wall_time, 4)
        return result

    def analyze_sound(
        self,
        sound: parselmouth.Sound,
        intervals: Optional[List[Dict[str, Any]]] = None,
        config: Optional[AudioAnalysisConfig] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a parselmouth.Sound instance.
        """
        cfg = config or self.config
        duration = float(sound.duration)
        sample_rate = int(sound.sampling_frequency)
        n_samples = int(sound.n_samples)

        report: Dict[str, Any] = {
            "status": "success",
            "audio_metadata": {
                "duration_seconds": round(duration, 4),
                "sample_rate_hz": sample_rate,
                "n_samples": n_samples,
                "n_channels": int(sound.n_channels),
            },
            "configuration": {
                "pitch_floor_hz": cfg.pitch_floor,
                "pitch_ceiling_hz": cfg.pitch_ceiling,
                "time_step": cfg.time_step,
                "silence_threshold_db": cfg.silence_threshold_db,
                "min_pause_duration_seconds": cfg.min_pause_duration,
                "min_sounding_duration_seconds": cfg.min_sounding_duration,
            },
            "pitch_analysis": {},
            "intensity_analysis": {},
            "pause_analysis": {},
            "interval_summaries": None,
            "errors": [],
        }

        # Check for pure silence / zero-amplitude
        peak_amp = float(np.max(np.abs(sound.values))) if n_samples > 0 else 0.0
        is_pure_silence = peak_amp < 1e-6

        # 1. Pitch Extraction
        pitch_obj = None
        pitch_times = np.array([])
        pitch_values = np.array([])
        if is_pure_silence:
            report["pitch_analysis"] = {
                "reliable": True,
                "status": "all_unvoiced_silent",
                "total_frames": 0,
                "voiced_frames": 0,
                "voiced_fraction": 0.0,
                "statistics_hz": None,
                "note": "Input signal amplitude is zero or below noise floor. No voiced frames exist.",
            }
        else:
            try:
                pitch_obj = sound.to_pitch_ac(
                    time_step=cfg.time_step,
                    pitch_floor=cfg.pitch_floor,
                    pitch_ceiling=cfg.pitch_ceiling,
                )
                pitch_times = np.array(pitch_obj.xs())
                pitch_values = np.array(pitch_obj.selected_array["frequency"])
                report["pitch_analysis"] = self._compute_pitch_stats(pitch_times, pitch_values, cfg)
            except parselmouth.PraatError as pe:
                report["pitch_analysis"] = {
                    "reliable": False,
                    "status": "pitch_extraction_failed",
                    "error": str(pe),
                    "statistics_hz": None,
                    "note": "Praat could not extract pitch. The audio clip may be too short for the chosen pitch floor.",
                }
                report["errors"].append(f"Pitch extraction error: {pe}")

        # 2. Intensity Extraction
        intensity_obj = None
        intensity_times = np.array([])
        intensity_values = np.array([])
        try:
            # Use sensible floor for intensity
            effective_pitch_floor = cfg.pitch_floor if duration >= (3.0 / cfg.pitch_floor) else 150.0
            intensity_obj = sound.to_intensity(minimum_pitch=effective_pitch_floor)
            intensity_times = np.array(intensity_obj.xs())
            intensity_values = np.array(intensity_obj.values[0])
            report["intensity_analysis"] = self._compute_intensity_stats(
                intensity_times, intensity_values, is_pure_silence, cfg
            )
        except parselmouth.PraatError as pe:
            report["intensity_analysis"] = {
                "reliable": False,
                "status": "intensity_extraction_failed",
                "error": str(pe),
                "statistics_db": None,
            }
            report["errors"].append(f"Intensity extraction error: {pe}")

        # 3. Pause & Silence Detection
        if is_pure_silence:
            report["pause_analysis"] = {
                "reliable": True,
                "total_pause_duration_seconds": round(duration, 4),
                "pause_count": 1,
                "sounding_duration_seconds": 0.0,
                "phonation_ratio": 0.0,
                "pause_intervals": [
                    {
                        "start": 0.0,
                        "end": round(duration, 4),
                        "duration": round(duration, 4),
                    }
                ],
                "sounding_intervals": [],
                "note": "Complete audio duration is silent.",
            }
        elif duration < cfg.min_pause_duration:
            report["pause_analysis"] = {
                "reliable": True,
                "total_pause_duration_seconds": 0.0,
                "pause_count": 0,
                "sounding_duration_seconds": round(duration, 4),
                "phonation_ratio": 1.0,
                "pause_intervals": [],
                "sounding_intervals": [
                    {
                        "start": 0.0,
                        "end": round(duration, 4),
                        "duration": round(duration, 4),
                    }
                ],
                "note": f"Audio duration ({duration:.3f}s) is shorter than minimum pause threshold ({cfg.min_pause_duration}s).",
            }
        else:
            report["pause_analysis"] = self._compute_pauses(sound, duration, cfg)

        # 4. Optional Interval Summaries (e.g. for words or phrases)
        if intervals and len(intervals) > 0:
            report["interval_summaries"] = self._compute_interval_summaries(
                pitch_times, pitch_values, intensity_times, intensity_values, intervals
            )

        # 5. Raw Time-Series (Optional)
        if cfg.include_timeseries:
            report["timeseries"] = {
                "pitch": {
                    "times": [round(float(t), 4) for t in pitch_times],
                    "f0_hz": [None if v <= 0 else round(float(v), 2) for v in pitch_values],
                },
                "intensity": {
                    "times": [round(float(t), 4) for t in intensity_times],
                    "intensity_db": [round(float(v), 2) for v in intensity_values],
                },
            }

        return report

    def _compute_pitch_stats(
        self, times: np.ndarray, values: np.ndarray, cfg: AudioAnalysisConfig
    ) -> Dict[str, Any]:
        total_frames = len(values)
        if total_frames == 0:
            return {
                "reliable": False,
                "status": "no_frames",
                "total_frames": 0,
                "voiced_frames": 0,
                "voiced_fraction": 0.0,
                "statistics_hz": None,
                "note": "No frames extracted.",
            }

        voiced_mask = values > 0
        voiced_values = values[voiced_mask]
        voiced_count = int(np.sum(voiced_mask))
        voiced_fraction = round(float(voiced_count / total_frames), 4)

        if voiced_count == 0:
            return {
                "reliable": True,
                "status": "all_unvoiced",
                "total_frames": total_frames,
                "voiced_frames": 0,
                "voiced_fraction": 0.0,
                "statistics_hz": None,
                "note": "All analyzed frames were unvoiced (whispering, unvoiced fricatives, or silence).",
            }

        # Calculate robust parametric and non-parametric statistics
        mean_f0 = float(np.mean(voiced_values))
        std_f0 = float(np.std(voiced_values))
        min_f0 = float(np.min(voiced_values))
        max_f0 = float(np.max(voiced_values))
        median_f0 = float(np.median(voiced_values))
        p25_f0 = float(np.percentile(voiced_values, 25))
        p75_f0 = float(np.percentile(voiced_values, 75))

        return {
            "reliable": True,
            "status": "voiced_speech_detected",
            "total_frames": total_frames,
            "voiced_frames": voiced_count,
            "unvoiced_frames": total_frames - voiced_count,
            "voiced_fraction": voiced_fraction,
            "statistics_hz": {
                "mean": round(mean_f0, 2),
                "std": round(std_f0, 2),
                "min": round(min_f0, 2),
                "max": round(max_f0, 2),
                "median": round(median_f0, 2),
                "p25": round(p25_f0, 2),
                "p75": round(p75_f0, 2),
                "interquartile_range": round(p75_f0 - p25_f0, 2),
            },
        }

    def _compute_intensity_stats(
        self, times: np.ndarray, values: np.ndarray, is_pure_silence: bool, cfg: AudioAnalysisConfig
    ) -> Dict[str, Any]:
        total_frames = len(values)
        if total_frames == 0 or is_pure_silence:
            return {
                "reliable": True,
                "status": "silent_or_empty",
                "total_frames": total_frames,
                "statistics_db": {
                    "mean": -300.0 if is_pure_silence else None,
                    "std": 0.0 if is_pure_silence else None,
                    "min": -300.0 if is_pure_silence else None,
                    "max": -300.0 if is_pure_silence else None,
                    "median": -300.0 if is_pure_silence else None,
                },
            }

        # Praat assigns -300 dB to complete zeroes
        valid_mask = values > -150.0
        active_values = values[valid_mask] if np.any(valid_mask) else values

        mean_db = float(np.mean(active_values))
        std_db = float(np.std(active_values))
        min_db = float(np.min(active_values))
        max_db = float(np.max(active_values))
        median_db = float(np.median(active_values))

        return {
            "reliable": True,
            "status": "valid",
            "total_frames": total_frames,
            "statistics_db": {
                "mean": round(mean_db, 2),
                "std": round(std_db, 2),
                "min": round(min_db, 2),
                "max": round(max_db, 2),
                "median": round(median_db, 2),
                "dynamic_range_db": round(max_db - min_db, 2),
            },
        }

    def _compute_pauses(
        self, sound: parselmouth.Sound, duration: float, cfg: AudioAnalysisConfig
    ) -> Dict[str, Any]:
        """
        Calculates pause/sounding intervals using Praat's standard TextGrid silences algorithm.
        """
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=parselmouth.PraatWarning)
                tg = praat_call(
                    sound,
                    "To TextGrid (silences)...",
                    cfg.pitch_floor,
                    0.0,  # Auto time step
                    cfg.silence_threshold_db,
                    cfg.min_pause_duration,
                    cfg.min_sounding_duration,
                    "silent",
                    "sounding",
                )

            n_intervals = praat_call(tg, "Get number of intervals...", 1)
            pause_intervals = []
            sounding_intervals = []
            total_pause_dur = 0.0
            total_sounding_dur = 0.0

            for i in range(1, n_intervals + 1):
                label = praat_call(tg, "Get label of interval...", 1, i)
                start_t = float(praat_call(tg, "Get start time of interval...", 1, i))
                end_t = float(praat_call(tg, "Get end time of interval...", 1, i))
                interval_dur = round(end_t - start_t, 4)

                item = {
                    "start": round(start_t, 4),
                    "end": round(end_t, 4),
                    "duration": interval_dur,
                }

                if label == "silent":
                    pause_intervals.append(item)
                    total_pause_dur += interval_dur
                elif label == "sounding":
                    sounding_intervals.append(item)
                    total_sounding_dur += interval_dur

            phonation_ratio = round(total_sounding_dur / max(duration, 0.001), 4)

            return {
                "reliable": True,
                "total_pause_duration_seconds": round(total_pause_dur, 4),
                "pause_count": len(pause_intervals),
                "sounding_duration_seconds": round(total_sounding_dur, 4),
                "sounding_interval_count": len(sounding_intervals),
                "phonation_ratio": min(1.0, phonation_ratio),
                "pause_intervals": pause_intervals,
                "sounding_intervals": sounding_intervals,
            }

        except parselmouth.PraatError as pe:
            return {
                "reliable": False,
                "error": str(pe),
                "total_pause_duration_seconds": 0.0,
                "pause_count": 0,
                "sounding_duration_seconds": round(duration, 4),
                "phonation_ratio": 1.0,
                "pause_intervals": [],
                "sounding_intervals": [{"start": 0.0, "end": round(duration, 4), "duration": round(duration, 4)}],
            }

    def _compute_interval_summaries(
        self,
        pitch_times: np.ndarray,
        pitch_values: np.ndarray,
        intensity_times: np.ndarray,
        intensity_values: np.ndarray,
        intervals: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Calculates acoustic summary (pitch and intensity) for arbitrary time intervals (e.g. word boundaries).
        """
        summaries = []

        for idx, inter in enumerate(intervals):
            start_t = float(inter.get("start", 0.0))
            end_t = float(inter.get("end", start_t))
            label = inter.get("label") or inter.get("word") or f"interval_{idx + 1}"

            summary: Dict[str, Any] = {
                "label": label,
                "start": round(start_t, 4),
                "end": round(end_t, 4),
                "duration": round(max(0.0, end_t - start_t), 4),
                "pitch": None,
                "intensity": None,
            }

            # Pitch in interval
            if len(pitch_times) > 0 and len(pitch_values) > 0 and end_t > start_t:
                p_mask = (pitch_times >= start_t) & (pitch_times <= end_t)
                p_vals = pitch_values[p_mask]
                if len(p_vals) > 0:
                    voiced_mask = p_vals > 0
                    voiced_p = p_vals[voiced_mask]
                    if len(voiced_p) > 0:
                        summary["pitch"] = {
                            "voiced_fraction": round(float(len(voiced_p) / len(p_vals)), 4),
                            "mean_hz": round(float(np.mean(voiced_p)), 2),
                            "max_hz": round(float(np.max(voiced_p)), 2),
                            "min_hz": round(float(np.min(voiced_p)), 2),
                            "std_hz": round(float(np.std(voiced_p)), 2),
                        }
                    else:
                        summary["pitch"] = {
                            "voiced_fraction": 0.0,
                            "mean_hz": None,
                            "max_hz": None,
                            "min_hz": None,
                            "std_hz": None,
                        }

            # Intensity in interval
            if len(intensity_times) > 0 and len(intensity_values) > 0 and end_t > start_t:
                i_mask = (intensity_times >= start_t) & (intensity_times <= end_t)
                i_vals = intensity_values[i_mask]
                if len(i_vals) > 0:
                    valid_i = i_vals[i_vals > -150.0]
                    target_i = valid_i if len(valid_i) > 0 else i_vals
                    summary["intensity"] = {
                        "mean_db": round(float(np.mean(target_i)), 2),
                        "max_db": round(float(np.max(target_i)), 2),
                        "min_db": round(float(np.min(target_i)), 2),
                        "std_db": round(float(np.std(target_i)), 2),
                    }

            summaries.append(summary)

        return summaries

    def _build_error_response(
        self, audio_path: str, error_type: str, error_message: str, duration_seconds: float
    ) -> Dict[str, Any]:
        return {
            "status": "error",
            "file_path": audio_path,
            "error_type": error_type,
            "error_message": error_message,
            "audio_metadata": None,
            "pitch_analysis": None,
            "intensity_analysis": None,
            "pause_analysis": None,
            "analysis_duration_seconds": round(duration_seconds, 4),
        }
