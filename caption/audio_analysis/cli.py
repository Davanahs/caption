"""
Command-line Interface for the Praat Parselmouth Audio Analyzer.
Usage:
  python cli.py <audio_path> [options]

Outputs a clean, structured JSON report summarizing pitch, intensity, pauses, and metadata.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

from analyzer import AudioAnalysisConfig, AudioAnalyzer


def parse_intervals(intervals_arg: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    if not intervals_arg:
        return None

    # Check if argument is a file path
    if os.path.exists(intervals_arg):
        try:
            with open(intervals_arg, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "intervals" in data:
                    return data["intervals"]
                elif isinstance(data, dict) and "blocks" in data:
                    # Compatibility with caption block schema
                    return [
                        {"start": b.get("start", 0), "end": b.get("end", 0), "label": b.get("text", "")}
                        for b in data["blocks"]
                    ]
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to load intervals from file '{intervals_arg}': {e}\n")
            return None

    # Try parsing as inline JSON string
    try:
        parsed = json.loads(intervals_arg)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        sys.stderr.write(f"Warning: Could not parse intervals as JSON: '{intervals_arg}'\n")

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Acoustic audio analysis tool using Praat and Parselmouth. Calculates pitch, intensity, and pauses."
    )
    parser.add_argument(
        "audio_path",
        help="Path to the audio file to analyze (.wav, .mp3, etc.)",
    )
    parser.add_argument(
        "--pitch-floor",
        type=float,
        default=75.0,
        help="Minimum pitch bound in Hz (default: 75.0 Hz).",
    )
    parser.add_argument(
        "--pitch-ceiling",
        type=float,
        default=500.0,
        help="Maximum pitch bound in Hz (default: 500.0 Hz).",
    )
    parser.add_argument(
        "--silence-threshold-db",
        type=float,
        default=-25.0,
        help="Silence threshold in dB relative to peak intensity (default: -25.0 dB).",
    )
    parser.add_argument(
        "--min-pause-duration",
        type=float,
        default=0.25,
        help="Minimum pause duration in seconds to register as silence (default: 0.25 s).",
    )
    parser.add_argument(
        "--min-sounding-duration",
        type=float,
        default=0.10,
        help="Minimum duration in seconds for a sounding segment (default: 0.10 s).",
    )
    parser.add_argument(
        "--include-timeseries",
        action="store_true",
        help="Include full pitch and intensity time-series arrays in the JSON report.",
    )
    parser.add_argument(
        "--intervals",
        type=str,
        default=None,
        help="Inline JSON array or path to JSON file defining intervals (e.g. word boundaries: '[{\"start\": 0.1, \"end\": 0.5, \"word\": \"HELLO\"}]').",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Optional path to write the JSON report to disk instead of stdout.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output minified JSON instead of pretty-printed JSON.",
    )

    args = parser.parse_args()

    config = AudioAnalysisConfig(
        pitch_floor=args.pitch_floor,
        pitch_ceiling=args.pitch_ceiling,
        silence_threshold_db=args.silence_threshold_db,
        min_pause_duration=args.min_pause_duration,
        min_sounding_duration=args.min_sounding_duration,
        include_timeseries=args.include_timeseries,
    )

    intervals = parse_intervals(args.intervals)
    analyzer = AudioAnalyzer(config=config)
    report = analyzer.analyze_file(args.audio_path, intervals=intervals)

    indent = None if args.compact else 2
    json_output = json.dumps(report, indent=indent)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_output)
            sys.stderr.write(f"Report written to '{args.output}'\n")
        except OSError as e:
            sys.stderr.write(f"Error writing to output file '{args.output}': {e}\n")
            print(json_output)
            return 1
    else:
        print(json_output)

    return 0 if report.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
