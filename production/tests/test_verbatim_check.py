"""逐字听检的比对逻辑：字错率、覆盖率、差异定位。

这些函数决定"配音念的字和剧本一字不差"这句话能不能被证伪，所以离线就能测，
不用等 ASR。守的是两件事：

* 完全一致必须报 0（否则好片子会被冤枉）；
* 真的念错必须报出来（否则这份检查就是个摆设——参考项目第一版"没声音却出片"
  就是因为检查只看了容器字段，从不测量）。
"""
import json
import os
import sys
import wave
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "production"))
import verbatim_check  # noqa: E402

SCRIPT = "一九四七年一月十五日，洛杉矶。她只有二十二岁。"


class NormalizeTests(unittest.TestCase):
    def test_digits_become_spoken_chinese(self):
        self.assertEqual(verbatim_check.chinese_number(0), "零")
        self.assertEqual(verbatim_check.chinese_number(7), "七")
        self.assertEqual(verbatim_check.chinese_number(15), "十五")
        self.assertEqual(verbatim_check.chinese_number(22), "二十二")
        self.assertEqual(verbatim_check.chinese_number(1947), "一九四七")

    def test_punctuation_and_case_are_ignored(self):
        self.assertEqual(verbatim_check.normalize("她，只有二十二岁。"),
                         verbatim_check.normalize("她只有二十二岁"))
        self.assertEqual(verbatim_check.normalize("22岁"), "二十二岁")
        self.assertEqual(verbatim_check.normalize("ABC"), "abc")

    def test_years_are_spelled_digit_by_digit(self):
        self.assertIn("一九四七", verbatim_check.normalize("1947年"))

    def test_normalize_percent_and_decimal_read_the_way_people_say_them(self):
        """99.96% 念作「百分之九十九点九六」，不能被拆成「九十九 九十六」。"""
        self.assertEqual(verbatim_check.normalize("99.96%"), "百分之九十九点九六")
        self.assertEqual(verbatim_check.normalize("排除99.96%的人"),
                         verbatim_check.normalize("排除百分之九十九点九六的人"))
        self.assertEqual(verbatim_check.normalize("3.5"), "三点五")

    def test_normalize_folds_traditional_into_simplified_when_zhconv_is_present(self):
        """whisper 有时整段吐繁体；繁简差异不是错字（2026-09-21 吉尔戈 N05：0.31 → 0.10）。"""
        try:
            import zhconv  # noqa: F401
        except ImportError:
            self.skipTest("没装 zhconv，繁简折叠退化为原样返回")
        self.assertEqual(verbatim_check.normalize("跟蹤小組馬上撿走"),
                         verbatim_check.normalize("跟踪小组马上捡走"))


class ErrorRateTests(unittest.TestCase):
    def test_a_verbatim_match_scores_zero(self):
        expected = verbatim_check.normalize(SCRIPT)
        self.assertEqual(verbatim_check.character_error_rate(expected, expected), 0.0)
        self.assertEqual(verbatim_check.match_coverage(expected, expected), 1.0)

    def test_one_wrong_character_is_counted(self):
        """二十二岁 念成 二十三岁：一个字错，CER 应该是 1/字数。"""
        expected = verbatim_check.normalize("她只有二十二岁")
        heard = verbatim_check.normalize("她只有二十三岁")
        self.assertEqual(verbatim_check.character_error_rate(expected, heard),
                         round(1 / len(expected), 4))
        self.assertLess(verbatim_check.match_coverage(expected, heard), 1.0)

    def test_a_dropped_character_is_counted(self):
        expected = verbatim_check.normalize("她只有二十二岁")
        heard = verbatim_check.normalize("她只有十二岁")
        self.assertEqual(verbatim_check.character_error_rate(expected, heard),
                         round(1 / len(expected), 4))

    def test_completely_different_text_is_a_full_miss(self):
        expected = verbatim_check.normalize("洛杉矶")
        self.assertEqual(verbatim_check.match_coverage(expected, "今天天气不错"), 0.0)

    def test_empty_expected_is_not_a_crash(self):
        self.assertEqual(verbatim_check.character_error_rate("", ""), 0.0)
        self.assertEqual(verbatim_check.character_error_rate("", "有声音"), 1.0)
        self.assertEqual(verbatim_check.match_coverage("", ""), 1.0)

    def test_edit_distance_is_symmetric_for_substitutions(self):
        self.assertEqual(verbatim_check.levenshtein("黑色大丽花", "黑色大丽化"), 1)
        self.assertEqual(verbatim_check.levenshtein("黑色大丽花", "黑色大丽花"), 0)
        self.assertEqual(verbatim_check.levenshtein("abc", "abcdef"), 3)


class DiffSpanTests(unittest.TestCase):
    def test_the_wrong_character_is_pointed_out(self):
        spans = verbatim_check.diff_spans(verbatim_check.normalize("她只有二十二岁"),
                                          verbatim_check.normalize("她只有二十三岁"))
        self.assertTrue(spans, "有差异却没列出差异位置")
        joined = "".join(span["script"] for span in spans)
        heard = "".join(span["heard"] for span in spans)
        self.assertIn("二", joined)
        self.assertIn("三", heard)

    def test_a_verbatim_match_has_no_spans(self):
        text = verbatim_check.normalize(SCRIPT)
        self.assertEqual(verbatim_check.diff_spans(text, text), [])


class VerdictTests(unittest.TestCase):
    def setUp(self):
        self.chapters = [{"id": "N01", "text": "她只有二十二岁，一九四七年一月十五日。",
                          "start": 0.6, "end": 28.2},
                         {"id": "N02", "text": "警方把指纹通过照片传真传给联邦调查局。",
                          "start": 29.3, "end": 61.0}]

    def test_a_clean_read_passes(self):
        transcripts = {row["id"]: row["text"] for row in self.chapters}
        result = verbatim_check.compare(self.chapters, transcripts, 0.15)
        self.assertEqual(result["failing"], [])
        self.assertEqual(result["max_cer"], 0.0)
        self.assertTrue(all(row["verdict"] == "ok" for row in result["chapters"]))

    def test_a_garbled_chapter_is_sent_to_a_human(self):
        transcripts = {row["id"]: row["text"] for row in self.chapters}
        transcripts["N02"] = "今天天气不错哈"          # 念成了别的东西
        result = verbatim_check.compare(self.chapters, transcripts, 0.15)
        self.assertEqual(result["failing"], ["N02"])
        self.assertEqual(result["chapters"][1]["verdict"], "needs_human_listen")
        self.assertGreater(result["max_cer"], 0.15)

    def test_a_missing_transcript_is_treated_as_heard_nothing(self):
        """转写器某一段没吐字：不能当成通过，必须报出来。"""
        result = verbatim_check.compare(self.chapters, {"N01": "她只有二十二岁"}, 0.15)
        self.assertIn("N02", result["failing"])
        self.assertEqual(result["chapters"][1]["heard_chars"], 0)


class ModelCacheTests(unittest.TestCase):
    """模型缓存目录：自托管 runner 靠这个避免每个 job 重下 500 MB。

    默认落在本次运行的 work 里，行为与以前完全一样；设了 WHISPER_CACHE_DIR
    就指向常驻目录。写错这一处不会报错、只会默默变慢/卡在下模型上，所以要钉住。
    """

    def test_defaults_to_the_run_work_dir(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WHISPER_CACHE_DIR", None)
            self.assertEqual(
                verbatim_check.model_cache_dir(Path("/tmp/run")),
                Path("/tmp/run/model-cache"),
            )

    def test_env_override_wins(self):
        with mock.patch.dict(os.environ, {"WHISPER_CACHE_DIR": "/home/u/.cache/whisper"}):
            self.assertEqual(
                verbatim_check.model_cache_dir(Path("/tmp/run")),
                Path("/home/u/.cache/whisper"),
            )

    def test_transcribe_downloads_into_the_cache_dir(self):
        """转写那一步真的用这个目录，而不是又写死 work/model-cache。"""
        source = Path(verbatim_check.__file__).read_text(encoding="utf-8")
        self.assertIn("download_root=str(cache)", source,
                      "transcribe() 没有用 model_cache_dir()，改回写死了")
        self.assertIn('os.environ.setdefault("HF_HOME", str(cache))', source,
                      "HF_HOME 也要跟着走常驻目录，否则元数据缓存仍在 work 里")


class EndToEndTests(unittest.TestCase):
    """跑完整的 main()：切片 → 转写（用假转写器顶替）→ 比对 → 出报告。

    ASR 在沙箱里装不上（连不上 Hugging Face），但除转写之外每一步都能离线测，
    包括"不合格要以非 0 退出"和"报告要写得出来"。
    """
    @classmethod
    def setUpClass(cls):
        import shutil

        if not shutil.which("ffmpeg"):
            raise unittest.SkipTest("切音频需要 ffmpeg")

    def setUp(self):
        import tempfile

        import numpy as np

        self.directory = Path(tempfile.mkdtemp(prefix="verbatim-"))
        self.project = self.directory / "project"
        (self.project / "delivery").mkdir(parents=True)
        self.chapters = [{"id": f"N0{index}", "text": f"第{index}段解说词，一共八个字。",
                          "start": 0.5 + (index - 1) * 2.0, "end": 0.5 + (index - 1) * 2.0 + 1.5}
                         for index in range(1, 4)]
        (self.project / "story.json").write_text(
            json.dumps({"chapters": self.chapters}, ensure_ascii=False), encoding="utf-8")
        (self.project / "delivery" / "narration-timing.json").write_text(
            json.dumps(self.chapters, ensure_ascii=False), encoding="utf-8")

        # 一段 8 秒的合成音当"成片"（要装得下三章 + 前后 padding）：切片逻辑只要能按时间切出正确长度即可
        rate = 48000
        tone = (0.2 * np.sin(2 * np.pi * 220 * np.arange(rate * 8) / rate) * 32767).astype("<i2")
        film = self.directory / "film.wav"
        with wave.open(str(film), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(rate)
            writer.writeframes(tone.tobytes())
        self.film = film
        self.work = self.directory / "work"

    def _run(self, transcripts):
        original = verbatim_check.transcribe

        def fake(paths, model_size, language, work):
            self.assertEqual(model_size, "small")
            self.assertNotIn("initial_prompt", "".join(paths))   # 只是占位断言
            return {cid: transcripts.get(cid, "") for cid in paths}

        verbatim_check.transcribe = fake
        try:
            return verbatim_check.main([
                "--film", str(self.film), "--project", str(self.project),
                "--work", str(self.work), "--model", "small", "--max-cer", "0.15",
            ])
        finally:
            verbatim_check.transcribe = original

    def test_a_clean_read_passes_and_writes_a_report(self):
        exit_code = self._run({row["id"]: row["text"] for row in self.chapters})
        self.assertEqual(exit_code, 0)
        report = json.loads((self.work / "verbatim-check.json").read_text(encoding="utf-8"))
        self.assertEqual(report["film_pass"]["failing"], [])
        self.assertEqual(report["film_pass"]["max_cer"], 0.0)
        self.assertIn("无 initial_prompt", report["method"])
        for row in report["film_pass"]["chapters"]:
            self.assertTrue((self.work / f"{row['id']}-film.wav").is_file(),
                            "没有为每一章切出音频")

    def test_a_garbled_chapter_fails_the_check_but_still_reports(self):
        """报告必须写出来（人要看差异在哪），但退出码非 0（不许当成通过）。"""
        transcripts = {row["id"]: row["text"] for row in self.chapters}
        transcripts["N02"] = "今天天气不错"
        exit_code = self._run(transcripts)
        self.assertEqual(exit_code, 1)
        report = json.loads((self.work / "verbatim-check.json").read_text(encoding="utf-8"))
        self.assertEqual(report["film_pass"]["failing"], ["N02"])
        self.assertTrue(report["film_pass"]["chapters"][1]["diff"],
                        "报了差异却没列出差异位置，人没法复核")

    def test_slices_are_cut_with_padding(self):
        import wave

        self._run({row["id"]: row["text"] for row in self.chapters})
        for row in self.chapters:
            with wave.open(str(self.work / f"{row['id']}-film.wav")) as reader:
                seconds = reader.getnframes() / reader.getframerate()
            expected = (row["end"] + verbatim_check.PAD_SECONDS) - max(
                0.0, row["start"] - verbatim_check.PAD_SECONDS)
            self.assertAlmostEqual(seconds, expected, delta=0.05,
                                   msg=f"{row['id']} 切片长度不对")


class ProvenanceTests(unittest.TestCase):
    def test_script_and_manifest_must_agree(self):
        """文字来源不一致时必须在读剧本这一步就炸，不能拿错的基准去比对。"""
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            (project / "audio").mkdir()
            (project / "story.json").write_text(
                '{"chapters":[{"id":"N01","text":"甲"}]}', encoding="utf-8")
            (project / "audio" / "manifest.json").write_text(
                '{"clips":[{"id":"N01","text":"乙"}]}', encoding="utf-8")
            (project / "delivery").mkdir()
            (project / "delivery" / "narration-timing.json").write_text(
                '[{"id":"N01","start":0.0,"end":1.0}]', encoding="utf-8")
            with self.assertRaises(verbatim_check.VerdictError):
                verbatim_check.load_chapters(project, None)

    def test_timings_are_read_from_the_measured_report(self):
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            (project / "story.json").write_text(
                '{"chapters":[{"id":"N01","text":"甲"}]}', encoding="utf-8")
            (project / "delivery").mkdir()
            (project / "delivery" / "narration-timing.json").write_text(
                '[{"id":"N01","start":0.6,"end":28.2}]', encoding="utf-8")
            chapters = verbatim_check.load_chapters(project, None)
            self.assertEqual(chapters[0]["start"], 0.6)
            self.assertEqual(chapters[0]["text"], "甲")


if __name__ == "__main__":
    unittest.main()
