"""
Acoustic Audio Analysis Benchmark Runner.
Measures analysis execution duration, baseline RAM, and peak process RAM
for 10-second, 30-second, and 60-second audio clips across multiple iterations.
"""

import ctypes
import json
import os
import platform
import shutil
import tempfile
import time
import tracemalloc
from ctypes import wintypes
from typing import Any, Dict, List, Tuple

import numpy as np
import parselmouth

from analyzer import AudioAnalysisConfig, AudioAnalyzer


# Windows Process Memory Structures
class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def get_process_memory_mb() -> Tuple[float, float]:
    """Returns (current_working_set_mb, peak_working_set_mb) on Windows."""
    try:
        fn = ctypes.windll.kernel32.K32GetProcessMemoryInfo
        fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        fn.restype = wintypes.BOOL

        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if fn(handle, ctypes.byref(pmc), pmc.cb):
            return (
                round(pmc.WorkingSetSize / (1024 * 1024), 2),
                round(pmc.PeakWorkingSetSize / (1024 * 1024), 2),
            )
    except Exception:
        pass
    return (0.0, 0.0)


def generate_speech_like_signal(duration_seconds: float, sample_rate: int = 16000) -> np.ndarray:
    """
    Generates a realistic synthetic speech signal containing:
      - Alternating voiced speech (1.2s to 2.0s bursts) with 140-190 Hz harmonics.
      - Realistic silence gaps (0.3s to 0.5s).
      - Dynamic amplitude envelopes.
    Explicitly labeled as [SYNTHETIC BENCHMARK SIGNAL].
    """
    total_samples = int(duration_seconds * sample_rate)
    signal = np.zeros(total_samples, dtype=np.float32)

    cursor = 0
    np.random.seed(42)

    while cursor < total_samples:
        # Voiced burst duration: 1.2 to 2.0 seconds
        burst_dur = min(np.random.uniform(1.2, 2.0), (total_samples - cursor) / sample_rate)
        n_burst = int(burst_dur * sample_rate)
        if n_burst <= 0:
            break

        t = np.linspace(0, burst_dur, n_burst, endpoint=False)
        base_f0 = np.random.uniform(130.0, 180.0)
        # Formant-like harmonic structure with slight pitch vibrato
        f0_contour = base_f0 + 10.0 * np.sin(2 * np.pi * 3.5 * t)
        phase = 2 * np.pi * np.cumsum(f0_contour) / sample_rate

        burst = (
            0.50 * np.sin(phase)
            + 0.25 * np.sin(2 * phase)
            + 0.15 * np.sin(3 * phase)
            + 0.08 * np.sin(4 * phase)
        )
        # Hann window envelope to avoid harsh transient clicks
        window = np.hanning(n_burst)
        burst = burst * window

        signal[cursor : cursor + n_burst] = burst
        cursor += n_burst

        # Pause duration: 0.3 to 0.5 seconds
        pause_dur = min(np.random.uniform(0.3, 0.5), (total_samples - cursor) / sample_rate)
        n_pause = int(pause_dur * sample_rate)
        cursor += n_pause

    return signal


def run_benchmark(iterations: int = 5) -> Dict[str, Any]:
    temp_dir = tempfile.mkdtemp(prefix="benchmark_parselmouth_")
    durations = [10.0, 30.0, 60.0]
    clip_files = {}

    print("================================================================================")
    print("      PRAAT / PARSELMOUTH AUDIO ANALYSIS FEASIBILITY BENCHMARK                 ")
    print("================================================================================")
    print(f"OS: {platform.system()} {platform.release()} ({platform.architecture()[0]})")
    print(f"Machine Processor: {platform.processor()}")
    print(f"Python Executable: {platform.python_implementation()} {platform.python_version()}")
    print(f"Parselmouth Version: {parselmouth.__version__}")
    print(f"Test Iterations per Clip: {iterations}")
    print("--------------------------------------------------------------------------------")

    # Generate test files
    print("\nGenerating synthetic speech-like audio test clips [SYNTHETIC TEST SIGNALS]...")
    for dur in durations:
        fname = os.path.join(temp_dir, f"benchmark_{int(dur)}s.wav")
        sig = generate_speech_like_signal(dur, sample_rate=16000)
        parselmouth.Sound(sig, sampling_frequency=16000).save(fname, "WAV")
        size_kb = os.path.getsize(fname) / 1024
        clip_files[dur] = fname
        print(f"  • Created {int(dur)}s test clip: {fname} ({size_kb:.1f} KB)")

    analyzer = AudioAnalyzer()
    benchmark_results: Dict[str, Any] = {
        "system_info": {
            "os": f"{platform.system()} {platform.release()}",
            "os_architecture": platform.architecture()[0],
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "parselmouth_version": parselmouth.__version__,
        },
        "results_by_duration": {},
    }

    baseline_ws_mb, _ = get_process_memory_mb()

    for dur in durations:
        file_path = clip_files[dur]
        print(f"\nBenchmarking {int(dur)}s Audio Clip ({iterations} iterations)...")

        execution_times: List[float] = []
        peak_memories_mb: List[float] = []
        python_heaps_mb: List[float] = []

        for i in range(iterations):
            tracemalloc.start()
            t0 = time.perf_counter()
            report = analyzer.analyze_file(file_path)
            t_elapsed = time.perf_counter() - t0
            current_heap, peak_heap = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            _, peak_ws = get_process_memory_mb()

            execution_times.append(t_elapsed)
            peak_memories_mb.append(peak_ws)
            python_heaps_mb.append(peak_heap / (1024 * 1024))

            print(
                f"  Iter #{i + 1}: duration = {t_elapsed * 1000:.1f} ms | "
                f"Peak OS WorkingSet = {peak_ws:.1f} MB | "
                f"Peak Python Heap = {peak_heap / (1024 * 1024):.2f} MB"
            )

        mean_time = float(np.mean(execution_times))
        std_time = float(np.std(execution_times))
        min_time = float(np.min(execution_times))
        max_time = float(np.max(execution_times))
        peak_ws_max = float(np.max(peak_memories_mb))
        mean_heap = float(np.mean(python_heaps_mb))
        rtf = mean_time / dur  # Real-time factor (lower is faster)

        benchmark_results["results_by_duration"][f"{int(dur)}s"] = {
            "audio_duration_seconds": dur,
            "iterations": iterations,
            "mean_execution_seconds": round(mean_time, 4),
            "std_execution_seconds": round(std_time, 4),
            "min_execution_seconds": round(min_time, 4),
            "max_execution_seconds": round(max_time, 4),
            "mean_execution_ms": round(mean_time * 1000, 2),
            "real_time_factor": round(rtf, 5),
            "real_time_multiplier": round(1.0 / rtf, 1) if rtf > 0 else 0,
            "baseline_working_set_mb": baseline_ws_mb,
            "peak_working_set_mb": peak_ws_max,
            "mean_peak_python_heap_mb": round(mean_heap, 2),
            "extracted_features_summary": {
                "voiced_fraction": report.get("pitch_analysis", {}).get("voiced_fraction"),
                "mean_f0_hz": report.get("pitch_analysis", {}).get("statistics_hz", {}).get("mean"),
                "mean_intensity_db": report.get("intensity_analysis", {}).get("statistics_db", {}).get("mean"),
                "detected_pauses": report.get("pause_analysis", {}).get("pause_count"),
            },
        }

    # Clean up temp test files
    shutil.rmtree(temp_dir, ignore_errors=True)

    # Print summary table
    print("\n================================================================================")
    print("                           BENCHMARK SUMMARY TABLE                              ")
    print("================================================================================")
    print(
        f"{'Audio Clip':<12} | {'Mean Latency':<14} | {'Min - Max':<18} | {'RTF':<10} | {'Speedup':<12} | {'Peak OS RAM':<12}"
    )
    print("-" * 88)
    for dur_key, res in benchmark_results["results_by_duration"].items():
        mean_ms = f"{res['mean_execution_ms']:.1f} ms"
        min_max = f"{res['min_execution_seconds'] * 1000:.0f} - {res['max_execution_seconds'] * 1000:.0f} ms"
        rtf_str = f"{res['real_time_factor']:.4f}x"
        speedup = f"{res['real_time_multiplier']}x real-time"
        peak_ram = f"{res['peak_working_set_mb']:.1f} MB"
        print(f"{dur_key:<12} | {mean_ms:<14} | {min_max:<18} | {rtf_str:<10} | {speedup:<12} | {peak_ram:<12}")
    print("================================================================================")

    # Save benchmark results to JSON
    output_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_results, f, indent=2)
    print(f"\nDetailed benchmark report saved to: {output_path}")

    return benchmark_results


if __name__ == "__main__":
    run_benchmark(iterations=5)
