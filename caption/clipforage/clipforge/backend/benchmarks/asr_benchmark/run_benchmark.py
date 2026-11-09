"""
ClipForge — Two-Model ASR Benchmark Runner
OpenAI Whisper Base vs. Cactus-Compute Whistle

Controlled, reproducible benchmarking on CPU.
Measures:
- Cold start & warm start loading times
- Inference execution duration
- Real-Time Factor (RTF = inference_time / audio_duration)
- Peak RAM usage & CPU utilization via psutil
- Word-level timestamps & confidence/probability scores
- Baseline vs. Keyword-Biased transcription in Cactus Whistle
"""

import os
import sys
import time
import json
import gc
import psutil
import soundfile as sf
import numpy as np

# Ensure benchmark isolated environment and caches
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")

os.makedirs(RESULTS_DIR, exist_ok=True)

# Audio Files
VIDEOS = {
    "video1": {
        "id": "video1_cleantech",
        "title": "How to generate videos with AI for Movies and Products! | Wan vs Seedance",
        "category": "Clean Technical Explanation",
        "audio_path": os.path.join(DATA_DIR, "audio_video1_cleantech.wav"),
        "keywords": [
            "Wan", "Seedance", "ComfyUI", "LoRA", "HuggingFace", "diffusion", 
            "checkpoint", "upscaling", "keyframes", "rendering", "motion",
            "prompt", "latent", "FLUX", "Midjourney", "Kling", "Luma"
        ]
    },
    "video2": {
        "id": "video2_podcast",
        "title": "What is a podcast?",
        "category": "Multi-Speaker Podcast",
        "audio_path": os.path.join(DATA_DIR, "audio_video2_podcast.wav"),
        "keywords": [
            "podcast", "podcasting", "podcasts", "RSS", "feed", "episodes", 
            "subscribers", "iTunes", "Spotify", "microphone", "broadcasting",
            "audio", "syndication", "Apple", "Google", "download"
        ]
    },
    "video3": {
        "id": "video3_indian_tech",
        "title": "Kimi K3 Is INSANE! Can It Beat Claude?",
        "category": "Difficult Indian-English Technical Content",
        "audio_path": os.path.join(DATA_DIR, "audio_video3_indian_tech.wav"),
        "keywords": [
            "Kimi", "Claude", "Sonnet", "Moonshot", "SWE-bench", "tokens", 
            "reasoning", "benchmark", "context window", "OpenAI", "API",
            "coding", "Python", "agentic", "pricing", "deepseek", "Chinese"
        ]
    }
}

class ResourceMonitor:
    def __init__(self):
        self.process = psutil.Process()
        self.initial_ram = self.process.memory_info().rss
        self.peak_ram = self.initial_ram

    def reset_peak(self):
        self.peak_ram = self.process.memory_info().rss

    def update(self):
        current = self.process.memory_info().rss
        if current > self.peak_ram:
            self.peak_ram = current
        return current

    def get_peak_mb(self):
        self.update()
        return round(self.peak_ram / (1024 * 1024), 2)


def get_audio_duration(file_path):
    info = sf.info(file_path)
    return info.duration, info.samplerate, info.channels


def run_whisper_benchmark():
    print("\n" + "="*70)
    print("BENCHMARKING MODEL A: OpenAI Whisper Base (Multilingual, CPU)")
    print("="*70)
    
    import whisper
    
    monitor = ResourceMonitor()
    results = {}
    
    weights_path = os.path.join(CACHE_DIR, "whisper", "base.pt")
    download_root = os.path.join(CACHE_DIR, "whisper")

    # 1. Cold Load
    print("[Whisper] Cold model loading...")
    gc.collect()
    start_ram = monitor.process.memory_info().rss
    t0 = time.time()
    model = whisper.load_model("base", device="cpu", download_root=download_root)
    cold_load_time = time.time() - t0
    peak_cold_ram = monitor.get_peak_mb()
    print(f"[Whisper] Cold load completed in {cold_load_time:.3f}s (RAM: {peak_cold_ram} MB)")

    # 2. Warm Load
    print("[Whisper] Warm model loading...")
    gc.collect()
    t0 = time.time()
    model_warm = whisper.load_model("base", device="cpu", download_root=download_root)
    warm_load_time = time.time() - t0
    del model_warm
    gc.collect()
    print(f"[Whisper] Warm load completed in {warm_load_time:.3f}s")

    results["loading"] = {
        "cold_load_time_s": round(cold_load_time, 4),
        "warm_load_time_s": round(warm_load_time, 4),
        "peak_ram_mb": peak_cold_ram
    }
    results["runs"] = {}

    for vid_key, vid_info in VIDEOS.items():
        audio_path = vid_info["audio_path"]
        duration, sr, ch = get_audio_duration(audio_path)
        print(f"\n--- Transcribing {vid_info['id']} ({duration:.2f}s, {sr}Hz, {ch}ch) ---")

        # Determine repetitions: 3 warm runs for video2 (short), 1 warm run for long videos
        repeat_count = 3 if vid_key == "video2" else 1
        
        run_times = []
        full_transcript = None
        first_run_res = None

        for r in range(repeat_count + 1):
            run_type = "cold" if r == 0 else f"warm_run_{r}"
            monitor.reset_peak()
            cpu_before = psutil.cpu_percent(interval=None)
            
            t_prep_start = time.time()
            # Audio prep
            audio = whisper.load_audio(audio_path)
            audio = whisper.pad_or_trim(audio)
            t_prep_end = time.time()
            prep_duration = t_prep_end - t_prep_start

            t_infer_start = time.time()
            # Full transcribe with word_timestamps
            res = model.transcribe(
                audio_path,
                fp16=False,
                language="en",
                word_timestamps=True,
                verbose=False
            )
            t_infer_end = time.time()
            infer_duration = t_infer_end - t_infer_start
            cpu_after = psutil.cpu_percent(interval=None)
            peak_ram = monitor.get_peak_mb()

            rtf = infer_duration / duration
            print(f"[{vid_key}][{run_type}] Prep: {prep_duration:.2f}s | Infer: {infer_duration:.2f}s | RTF: {rtf:.4f} | Peak RAM: {peak_ram} MB")
            
            if r == 0:
                first_run_res = {
                    "run_type": run_type,
                    "prep_time_s": round(prep_duration, 4),
                    "infer_time_s": round(infer_duration, 4),
                    "total_time_s": round(prep_duration + infer_duration, 4),
                    "rtf": round(rtf, 4),
                    "peak_ram_mb": peak_ram
                }
                full_transcript = res
            else:
                run_times.append({
                    "run_type": run_type,
                    "infer_time_s": round(infer_duration, 4),
                    "rtf": round(rtf, 4),
                    "peak_ram_mb": peak_ram
                })

        # Process words and segments
        words_list = []
        for seg in full_transcript.get("segments", []):
            for w in seg.get("words", []):
                words_list.append({
                    "word": w.get("word", "").strip(),
                    "start": round(float(w.get("start", 0.0)), 3),
                    "end": round(float(w.get("end", 0.0)), 3),
                    "probability": round(float(w.get("probability", 1.0)), 4)
                })

        text_out = full_transcript.get("text", "").strip()

        # Save raw transcripts
        json_path = os.path.join(RESULTS_DIR, f"whisper_{vid_key}.json")
        txt_path = os.path.join(RESULTS_DIR, f"whisper_{vid_key}.txt")
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "model": "OpenAI Whisper Base",
                "video_id": vid_info["id"],
                "duration_s": duration,
                "text": text_out,
                "words_count": len(words_list),
                "words": words_list,
                "segments": full_transcript.get("segments", [])
            }, f, indent=2, ensure_ascii=False)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text_out)

        results["runs"][vid_key] = {
            "duration_s": round(duration, 2),
            "cold_run": first_run_res,
            "warm_runs": run_times,
            "avg_warm_infer_time_s": round(np.mean([x["infer_time_s"] for x in run_times]), 4) if run_times else first_run_res["infer_time_s"],
            "avg_warm_rtf": round(np.mean([x["rtf"] for x in run_times]), 4) if run_times else first_run_res["rtf"],
            "words_detected": len(words_list),
            "text_length": len(text_out)
        }

    return results


def run_whistle_benchmark():
    print("\n" + "="*70)
    print("BENCHMARKING MODEL B: Cactus-Compute Whistle (Needle runtime, CPU)")
    print("="*70)
    
    import needle
    
    monitor = ResourceMonitor()
    results = {}
    
    # 1. Cold Load
    print("[Whistle] Cold model loading...")
    gc.collect()
    t0 = time.time()
    whistle_model = needle.Whistle()
    cold_load_time = time.time() - t0
    peak_cold_ram = monitor.get_peak_mb()
    print(f"[Whistle] Cold load completed in {cold_load_time:.3f}s (RAM: {peak_cold_ram} MB)")

    # 2. Warm Load
    print("[Whistle] Warm model check...")
    t0 = time.time()
    whistle_model_warm = needle.Whistle()
    warm_load_time = time.time() - t0
    print(f"[Whistle] Warm load completed in {warm_load_time:.3f}s")

    results["loading"] = {
        "cold_load_time_s": round(cold_load_time, 4),
        "warm_load_time_s": round(warm_load_time, 4),
        "peak_ram_mb": peak_cold_ram
    }
    results["runs"] = {}
    results["keyword_biased_runs"] = {}

    for vid_key, vid_info in VIDEOS.items():
        audio_path = vid_info["audio_path"]
        duration, sr, ch = get_audio_duration(audio_path)
        print(f"\n--- Transcribing {vid_info['id']} ({duration:.2f}s, {sr}Hz, {ch}ch) ---")

        # Part A: Baseline Runs
        repeat_count = 3 if vid_key == "video2" else 1
        run_times = []
        full_transcript = None
        first_run_res = None

        for r in range(repeat_count + 1):
            run_type = "cold" if r == 0 else f"warm_run_{r}"
            monitor.reset_peak()

            t_infer_start = time.time()
            res = whistle_model.transcribe(
                audio_path,
                language="en",
                word_timestamps=True
            )
            t_infer_end = time.time()
            infer_duration = t_infer_end - t_infer_start
            peak_ram = monitor.get_peak_mb()

            rtf = infer_duration / duration
            print(f"[{vid_key}][baseline][{run_type}] Infer: {infer_duration:.2f}s | RTF: {rtf:.4f} | Peak RAM: {peak_ram} MB")

            if r == 0:
                first_run_res = {
                    "run_type": run_type,
                    "infer_time_s": round(infer_duration, 4),
                    "rtf": round(rtf, 4),
                    "peak_ram_mb": peak_ram
                }
                full_transcript = res
            else:
                run_times.append({
                    "run_type": run_type,
                    "infer_time_s": round(infer_duration, 4),
                    "rtf": round(rtf, 4),
                    "peak_ram_mb": peak_ram
                })

        text_out = full_transcript.get("text", "").strip()
        words_list = full_transcript.get("words", [])

        # Save baseline raw transcripts
        json_path = os.path.join(RESULTS_DIR, f"whistle_{vid_key}.json")
        txt_path = os.path.join(RESULTS_DIR, f"whistle_{vid_key}.txt")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "model": "Cactus-Compute Whistle (Baseline)",
                "video_id": vid_info["id"],
                "duration_s": duration,
                "text": text_out,
                "words_count": len(words_list),
                "words": words_list,
                "ttft_ms": full_transcript.get("ttft_ms", 0.0),
                "decode_tps": full_transcript.get("decode_tps", 0.0)
            }, f, indent=2, ensure_ascii=False)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text_out)

        results["runs"][vid_key] = {
            "duration_s": round(duration, 2),
            "cold_run": first_run_res,
            "warm_runs": run_times,
            "avg_warm_infer_time_s": round(np.mean([x["infer_time_s"] for x in run_times]), 4) if run_times else first_run_res["infer_time_s"],
            "avg_warm_rtf": round(np.mean([x["rtf"] for x in run_times]), 4) if run_times else first_run_res["rtf"],
            "words_detected": len(words_list),
            "text_length": len(text_out)
        }

        # Part B: Phase 9 Keyword-Biased Experiment
        print(f"[Whistle] Running keyword-biased experiment on {vid_key} with {len(vid_info['keywords'])} keywords...")
        t_bias_start = time.time()
        res_biased = whistle_model.transcribe(
            audio_path,
            language="en",
            keywords=vid_info["keywords"],
            word_timestamps=True
        )
        t_bias_end = time.time()
        bias_duration = t_bias_end - t_bias_start
        bias_rtf = bias_duration / duration
        print(f"[{vid_key}][biased] Infer: {bias_duration:.2f}s | RTF: {bias_rtf:.4f}")

        text_biased = res_biased.get("text", "").strip()
        words_biased = res_biased.get("words", [])

        # Save biased raw transcripts
        json_bias_path = os.path.join(RESULTS_DIR, f"whistle_biased_{vid_key}.json")
        txt_bias_path = os.path.join(RESULTS_DIR, f"whistle_biased_{vid_key}.txt")

        with open(json_bias_path, "w", encoding="utf-8") as f:
            json.dump({
                "model": "Cactus-Compute Whistle (Keyword-Biased)",
                "video_id": vid_info["id"],
                "keywords_provided": vid_info["keywords"],
                "duration_s": duration,
                "text": text_biased,
                "words_count": len(words_biased),
                "words": words_biased,
                "ttft_ms": res_biased.get("ttft_ms", 0.0),
                "decode_tps": res_biased.get("decode_tps", 0.0)
            }, f, indent=2, ensure_ascii=False)

        with open(txt_bias_path, "w", encoding="utf-8") as f:
            f.write(text_biased)

        results["keyword_biased_runs"][vid_key] = {
            "keywords": vid_info["keywords"],
            "infer_time_s": round(bias_duration, 4),
            "rtf": round(bias_rtf, 4),
            "words_detected": len(words_biased),
            "text_length": len(text_biased)
        }

    return results


def main():
    print("="*70)
    print("STARTING CLIPFORGE ASR BENCHMARK EXPERIMENT")
    print("="*70)
    
    total_t0 = time.time()

    # Step 1: Run Whisper
    whisper_res = run_whisper_benchmark()

    # Step 2: Run Whistle
    whistle_res = run_whistle_benchmark()

    # Consolidate raw benchmark performance data
    benchmark_data = {
        "benchmark_metadata": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "device": "Intel Core 5 210H (8 cores, 12 threads) CPU",
            "os": "Windows 11 (64-bit)",
            "whisper_version": "openai-whisper 20250625",
            "whisper_model": "base (multilingual, 74M params, 139MB)",
            "whistle_version": "cactus-needle 3.2.9 / Whistle 2.0.0",
            "whistle_model": "whistle.cact (16.9MB)",
            "test_videos": VIDEOS
        },
        "whisper": whisper_res,
        "whistle": whistle_res,
        "total_experiment_duration_s": round(time.time() - total_t0, 2)
    }

    out_metrics_path = os.path.join(RESULTS_DIR, "performance_metrics.json")
    with open(out_metrics_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    print("\n" + "="*70)
    print(f"BENCHMARK COMPLETED IN {benchmark_data['total_experiment_duration_s']}s")
    print(f"Performance metrics saved to {out_metrics_path}")
    print("="*70)

if __name__ == "__main__":
    main()
