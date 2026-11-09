"""
Automated Test Suite for Praat Parselmouth Audio Analysis Engine.

Validates:
  1. Normal voiced speech simulation (harmonic signal).
  2. Pure silent audio file.
  3. Very short audio clip (<0.04s).
  4. Missing, empty, and invalid file paths.
  5. Audio clip with deliberate pauses.
  6. Unvoiced noise (verifies missing/unvoiced pitch handling).
  7. Interval-based acoustic summaries (simulating word timestamps).

All test audio signals generated in this suite are synthetic and explicitly
labeled as [SYNTHETIC TEST SIGNAL] in compliance with test guidelines.
"""

import os
import shutil
import tempfile
import unittest
import numpy as np
import parselmouth

from analyzer import AudioAnalysisConfig, AudioAnalyzer


class TestAudioAnalyzer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="test_audio_parselmouth_")
        cls.sample_rate = 16000

        # 1. Synthetic Voiced Speech Simulation (150 Hz harmonic tone with formant-like decay)
        t_voiced = np.linspace(0, 2.0, int(cls.sample_rate * 2.0), endpoint=False)
        voiced_signal = (
            0.5 * np.sin(2 * np.pi * 150 * t_voiced)
            + 0.25 * np.sin(2 * np.pi * 300 * t_voiced)
            + 0.12 * np.sin(2 * np.pi * 450 * t_voiced)
        )
        cls.voiced_path = os.path.join(cls.test_dir, "synthetic_voiced_speech.wav")
        parselmouth.Sound(voiced_signal, sampling_frequency=cls.sample_rate).save(
            cls.voiced_path, "WAV"
        )

        # 2. Synthetic Pure Silent Audio (2.0s of exact zeroes)
        silent_signal = np.zeros(int(cls.sample_rate * 2.0))
        cls.silent_path = os.path.join(cls.test_dir, "synthetic_silent.wav")
        parselmouth.Sound(silent_signal, sampling_frequency=cls.sample_rate).save(
            cls.silent_path, "WAV"
        )

        # 3. Synthetic Very Short Audio Clip (25 ms)
        t_short = np.linspace(0, 0.025, int(cls.sample_rate * 0.025), endpoint=False)
        short_signal = 0.5 * np.sin(2 * np.pi * 200 * t_short)
        cls.short_path = os.path.join(cls.test_dir, "synthetic_short_25ms.wav")
        parselmouth.Sound(short_signal, sampling_frequency=cls.sample_rate).save(
            cls.short_path, "WAV"
        )

        # 4. Synthetic Clip with Deliberate Pauses (1.0s speech + 0.6s silence + 1.0s speech)
        t_part1 = np.linspace(0, 1.0, int(cls.sample_rate * 1.0), endpoint=False)
        part1 = 0.5 * np.sin(2 * np.pi * 180 * t_part1)
        silence_gap = np.zeros(int(cls.sample_rate * 0.6))
        t_part2 = np.linspace(0, 1.0, int(cls.sample_rate * 1.0), endpoint=False)
        part2 = 0.5 * np.sin(2 * np.pi * 180 * t_part2)
        paused_signal = np.concatenate([part1, silence_gap, part2])
        cls.paused_path = os.path.join(cls.test_dir, "synthetic_with_pauses.wav")
        parselmouth.Sound(paused_signal, sampling_frequency=cls.sample_rate).save(
            cls.paused_path, "WAV"
        )

        # 5. Synthetic Unvoiced Audio (Pure Gaussian White Noise, no harmonic pitch)
        np.random.seed(42)
        noise_signal = np.random.normal(0, 0.05, int(cls.sample_rate * 1.5))
        cls.noise_path = os.path.join(cls.test_dir, "synthetic_unvoiced_noise.wav")
        parselmouth.Sound(noise_signal, sampling_frequency=cls.sample_rate).save(
            cls.noise_path, "WAV"
        )

        # 6. Invalid Corrupt File (text file renamed to .wav)
        cls.corrupt_path = os.path.join(cls.test_dir, "corrupt_fake.wav")
        with open(cls.corrupt_path, "w", encoding="utf-8") as f:
            f.write("This is not a valid RIFF/WAV audio file header.")

        # 7. Empty File (0 bytes)
        cls.empty_path = os.path.join(cls.test_dir, "empty_0bytes.wav")
        with open(cls.empty_path, "wb") as f:
            pass

        cls.analyzer = AudioAnalyzer()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_normal_speech_simulation(self):
        """[SYNTHETIC TEST SIGNAL] Validates fundamental frequency and intensity on a harmonic voiced signal."""
        res = self.analyzer.analyze_file(self.voiced_path)
        self.assertEqual(res["status"], "success")
        self.assertAlmostEqual(res["audio_metadata"]["duration_seconds"], 2.0, places=2)
        self.assertEqual(res["audio_metadata"]["sample_rate_hz"], 16000)

        pitch = res["pitch_analysis"]
        self.assertTrue(pitch["reliable"])
        self.assertGreater(pitch["voiced_fraction"], 0.85)
        # 150 Hz harmonic input should detect ~150 Hz mean
        stats = pitch["statistics_hz"]
        self.assertIsNotNone(stats)
        self.assertAlmostEqual(stats["mean"], 150.0, delta=5.0)

        intensity = res["intensity_analysis"]
        self.assertTrue(intensity["reliable"])
        self.assertGreater(intensity["statistics_db"]["mean"], 50.0)

    def test_silent_audio_file(self):
        """[SYNTHETIC TEST SIGNAL] Validates behavior on a pure zero-amplitude silent file."""
        res = self.analyzer.analyze_file(self.silent_path)
        self.assertEqual(res["status"], "success")
        self.assertAlmostEqual(res["audio_metadata"]["duration_seconds"], 2.0, places=2)

        # Pitch should register 0 voiced frames without error
        pitch = res["pitch_analysis"]
        self.assertTrue(pitch["reliable"])
        self.assertEqual(pitch["voiced_fraction"], 0.0)
        self.assertIsNone(pitch["statistics_hz"])

        # Pauses should detect the entire audio as a pause
        pauses = res["pause_analysis"]
        self.assertTrue(pauses["reliable"])
        self.assertEqual(pauses["pause_count"], 1)
        self.assertAlmostEqual(pauses["total_pause_duration_seconds"], 2.0, places=2)

    def test_very_short_audio_clip(self):
        """[SYNTHETIC TEST SIGNAL] Validates that ultra-short clips (<0.04s) do not crash the engine."""
        res = self.analyzer.analyze_file(self.short_path)
        self.assertEqual(res["status"], "success")
        self.assertAlmostEqual(res["audio_metadata"]["duration_seconds"], 0.025, places=3)
        # Should complete gracefully even if Praat cannot fit pitch window
        self.assertIn("pitch_analysis", res)
        self.assertIn("intensity_analysis", res)

    def test_invalid_and_missing_files(self):
        """Validates graceful error handling for missing, empty, and corrupt audio files."""
        # Non-existent file
        res_missing = self.analyzer.analyze_file(os.path.join(self.test_dir, "does_not_exist.wav"))
        self.assertEqual(res_missing["status"], "error")
        self.assertEqual(res_missing["error_type"], "FileNotFoundError")

        # Empty 0-byte file
        res_empty = self.analyzer.analyze_file(self.empty_path)
        self.assertEqual(res_empty["status"], "error")
        self.assertEqual(res_empty["error_type"], "EmptyFileError")

        # Corrupted non-audio file
        res_corrupt = self.analyzer.analyze_file(self.corrupt_path)
        self.assertEqual(res_corrupt["status"], "error")
        self.assertEqual(res_corrupt["error_type"], "InvalidAudioFormatError")

    def test_clip_with_pauses(self):
        """[SYNTHETIC TEST SIGNAL] Validates detection of silence gaps between speech segments."""
        res = self.analyzer.analyze_file(self.paused_path)
        self.assertEqual(res["status"], "success")
        self.assertAlmostEqual(res["audio_metadata"]["duration_seconds"], 2.6, delta=0.05)

        pauses = res["pause_analysis"]
        self.assertTrue(pauses["reliable"])
        self.assertGreaterEqual(pauses["pause_count"], 1)
        # The pause gap is 0.6s
        self.assertAlmostEqual(pauses["total_pause_duration_seconds"], 0.6, delta=0.15)
        # Phonation ratio should be around (2.0 / 2.6) ~ 0.77
        self.assertGreater(pauses["phonation_ratio"], 0.65)
        self.assertLess(pauses["phonation_ratio"], 0.90)

    def test_missing_unvoiced_pitch(self):
        """[SYNTHETIC TEST SIGNAL] Validates unvoiced noise where pitch cannot be calculated reliably."""
        res = self.analyzer.analyze_file(self.noise_path)
        self.assertEqual(res["status"], "success")

        pitch = res["pitch_analysis"]
        # Gaussian white noise should have near-zero or zero voiced frames
        self.assertLess(pitch.get("voiced_fraction", 0.0), 0.15)
        if pitch.get("voiced_fraction") == 0.0:
            self.assertIsNone(pitch["statistics_hz"])

    def test_interval_summaries(self):
        """Validates extracting acoustic features over specific word/phrase intervals."""
        intervals = [
            {"start": 0.2, "end": 0.8, "word": "FIRST_WORD"},
            {"start": 1.1, "end": 1.7, "word": "SECOND_WORD"},
        ]
        res = self.analyzer.analyze_file(self.voiced_path, intervals=intervals)
        self.assertEqual(res["status"], "success")
        summaries = res.get("interval_summaries")
        self.assertIsNotNone(summaries)
        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0]["label"], "FIRST_WORD")
        self.assertAlmostEqual(summaries[0]["pitch"]["mean_hz"], 150.0, delta=5.0)
        self.assertIsNotNone(summaries[0]["intensity"]["mean_db"])


if __name__ == "__main__":
    unittest.main()
