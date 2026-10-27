"""混音必须换机器也能复现——这是把混音从 ffmpeg 滤镜链搬进 numpy 的全部理由。

旧版用 ``adelay -> amix -> sidechaincompress -> amix -> loudnorm`` 一条滤镜链混音，
结果依赖 ffmpeg 的内部测量，换一个版本就是另一组数字（第一版成片因此没声音却
照样出片）。新版在 numpy 里显式算：解说按采样点落轨、配乐用本地包络闪避、
响度按显式 RMS 目标归一。

所以这里不是"测一遍能跑"，而是**拿仓库里真实的六段配音重混一遍**（走真实命令行，
和 run_project.sh 的调用方式一致），要求量出来的电平与交付时记录的
`delivery/audio-report.json` 一致（±0.05 dB）。数字漂移了，说明又有人把测量
交回给 ffmpeg 了。
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "production" / "dahlia"
REPORT = PROJECT / "delivery" / "audio-report.json"
TOLERANCE_DB = 0.05


class MixReproducibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("ffmpeg"):
            raise unittest.SkipTest("ffmpeg is required to decode the narration mp3s")
        if not (PROJECT / "audio" / "N01.mp3").is_file():
            raise unittest.SkipTest("缺少参考项目的六段配音")
        cls.work = Path(tempfile.mkdtemp(prefix="dahlia-mix-"))
        cls.output = cls.work / "soundtrack.wav"
        command = [sys.executable, str(PROJECT / "build_audio.py"),
                   "--project", str(PROJECT / "story.json"),
                   "--audio", str(PROJECT / "audio"),
                   "--work", str(cls.work),
                   "--output", str(cls.output)]
        cls.result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)

    def test_build_audio_runs_clean(self):
        self.assertEqual(self.result.returncode, 0,
                         f"build_audio.py 失败：{self.result.stderr[-800:]}")
        self.assertTrue(self.output.is_file(), "混音没有产出文件")

    def test_rebuilding_the_soundtrack_reproduces_the_delivered_levels(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr[-800:])
        fresh = json.loads((self.work / "audio-report.json").read_text(encoding="utf-8"))
        recorded = json.loads(REPORT.read_text(encoding="utf-8"))

        for key in ("rms_dbfs", "peak_dbfs"):
            delta = abs(fresh[key] - recorded[key])
            self.assertLessEqual(delta, TOLERANCE_DB,
                                 f"{key} 漂移 {delta:.3f} dB：{fresh[key]} != {recorded[key]}")
        self.assertEqual(fresh["silent_fraction"], recorded["silent_fraction"],
                         "静音占比变了，混音结果不再是同一个")

        by_id = {row["id"]: row["rms_dbfs"] for row in fresh["chapters"]}
        for row in recorded["chapters"]:
            delta = abs(by_id[row["id"]] - row["rms_dbfs"])
            self.assertLessEqual(delta, TOLERANCE_DB,
                                 f"{row['id']} 漂移 {delta:.3f} dB："
                                 f"{by_id[row['id']]} != {row['rms_dbfs']}")

    def test_the_rebuilt_mix_still_passes_the_silence_gate(self):
        """复现出来的混音必须仍然过闸门——复现一个无声的混音没有意义。"""
        self.assertEqual(self.result.returncode, 0, self.result.stderr[-800:])
        sys.path.insert(0, str(PROJECT))
        import build_audio

        recorded = json.loads(REPORT.read_text(encoding="utf-8"))
        report = build_audio.measure(
            self.output,
            chapters=[{"id": row["id"], "start": row["start"], "end": row["end"]}
                      for row in recorded["chapters"]],
        )
        build_audio.assert_audible(report)   # 不达标会抛 AudioBuildError
        self.assertLess(report["rms_dbfs"], -5.0, "混音电平异常高，检查归一")


if __name__ == "__main__":
    unittest.main()
