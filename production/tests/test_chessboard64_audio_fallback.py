"""Offline guarantees for the runner-side Edge-TTS narration path."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "chessboard64" / "generate_edge_audio.py"
spec = importlib.util.spec_from_file_location("generate_edge_audio", SCRIPT)
assert spec and spec.loader
edge_audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(edge_audio)


class EdgeAudioFallbackTests(unittest.TestCase):
    def test_default_voice_is_low_male_mandarin_with_suspense_pitch(self):
        self.assertEqual(edge_audio.DEFAULT_VOICE, "zh-CN-YunjianNeural")
        self.assertEqual(edge_audio.DEFAULT_PITCH, "-8Hz")

    def test_retry_waits_follow_requested_escalation(self):
        self.assertEqual([edge_audio.retry_delay(i) for i in range(1, 5)], [20, 25, 30, 35])
        self.assertEqual(edge_audio.retry_delay(30), 120)

    def test_transient_failure_retries_then_atomically_publishes_mp3(self):
        calls = []
        request_args = []

        class FakeCommunicate:
            def __init__(self, *, text, voice, rate, pitch):
                request_args.append((text, voice, rate, pitch))

            async def save(self, path):
                calls.append(path)
                if len(calls) == 1:
                    raise OSError("temporary service outage")
                Path(path).write_bytes(b"fake-mp3" * 1024)

        fake_module = types.SimpleNamespace(Communicate=FakeCommunicate)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "N01.mp3"
            with patch.dict(sys.modules, {"edge_tts": fake_module}), \
                 patch("asyncio.sleep", new_callable=AsyncMock) as sleep:
                asyncio.run(edge_audio.synthesize(
                    "旁白", destination, "zh-CN-YunjianNeural", "-8Hz", 3))
                sleep.assert_awaited_once_with(20)
            self.assertTrue(destination.is_file())
            self.assertGreaterEqual(destination.stat().st_size, 4096)
            self.assertEqual(len(calls), 2)
            self.assertEqual(request_args, [
                ("旁白", "zh-CN-YunjianNeural", "+0%", "-8Hz"),
                ("旁白", "zh-CN-YunjianNeural", "+0%", "-8Hz"),
            ])
            self.assertFalse((Path(tmp) / "N01.part.mp3").exists())

    def test_failed_synthesis_does_not_leave_a_partial_destination(self):
        class FailingCommunicate:
            def __init__(self, **_kwargs):
                pass

            async def save(self, path):
                Path(path).write_bytes(b"partial")
                raise OSError("service unavailable")

        fake_module = types.SimpleNamespace(Communicate=FailingCommunicate)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "N02.mp3"
            with patch.dict(sys.modules, {"edge_tts": fake_module}), \
                 patch("asyncio.sleep", new_callable=AsyncMock):
                with self.assertRaisesRegex(RuntimeError, "after 2 attempts"):
                    asyncio.run(edge_audio.synthesize(
                        "旁白", destination, "zh-CN-YunjianNeural", "-8Hz", 2))
            self.assertFalse(destination.exists())
            self.assertFalse((Path(tmp) / "N02.part.mp3").exists())


if __name__ == "__main__":
    unittest.main()
