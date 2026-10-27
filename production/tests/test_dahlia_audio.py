"""The silence gate: a soundtrack that cannot be measured as audible must not ship."""
import math
import shutil
import sys
import unittest
import wave
from pathlib import Path
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "production/dahlia"))
import build_audio  # noqa: E402


def write_wav(path: Path, samples: np.ndarray, rate: int = 48000) -> Path:
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(np.int16(np.clip(samples, -1.0, 1.0) * 32767.0).tobytes())
    return path


class AudioGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("ffmpeg"):
            raise unittest.SkipTest("ffmpeg is required to decode audio for measurement")

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix="dahlia-audio-"))

    def test_audible_tone_passes_the_gate(self):
        rate = 48000
        t = np.arange(rate * 2) / rate
        tone = 0.1 * np.sin(2 * math.pi * 440 * t)
        path = write_wav(self.directory / "tone.wav", tone, rate)
        report = build_audio.measure(path, chapters=[{"id": "N01", "start": 0.0, "end": 2.0}])
        self.assertLess(report["rms_dbfs"], -5.0)
        self.assertGreater(report["rms_dbfs"], -35.0)
        self.assertEqual(report["silent_fraction"], 0.0)
        self.assertEqual(report["chapters"][0]["rms_dbfs"], report["rms_dbfs"])
        build_audio.assert_audible(report)

    def test_silent_file_is_rejected(self):
        path = write_wav(self.directory / "silence.wav", np.zeros(48000 * 2))
        report = build_audio.measure(path, chapters=[{"id": "N01", "start": 0.0, "end": 2.0}])
        self.assertLess(report["rms_dbfs"], build_audio.MIN_MIX_RMS_DBFS)
        with self.assertRaises(build_audio.AudioBuildError):
            build_audio.assert_audible(report)

    def test_a_silent_chapter_inside_a_loud_mix_is_rejected(self):
        rate = 48000
        t = np.arange(rate * 4) / rate
        tone = 0.1 * np.sin(2 * math.pi * 440 * t)
        tone[rate * 2:] = 0.0  # second half falls silent
        path = write_wav(self.directory / "half.wav", tone, rate)
        report = build_audio.measure(path, chapters=[{"id": "N02", "start": 2.0, "end": 4.0}])
        with self.assertRaises(build_audio.AudioBuildError):
            build_audio.assert_audible(report)

    def test_envelope_follows_the_signal(self):
        rate = 48000
        level = np.zeros(rate * 2, dtype=np.float32)
        level[rate:] = 1.0
        envelope = build_audio.envelope(level, rate)
        self.assertLess(envelope[1000], 0.2)
        self.assertGreater(envelope[-1000], 0.5)


if __name__ == "__main__":
    unittest.main()
