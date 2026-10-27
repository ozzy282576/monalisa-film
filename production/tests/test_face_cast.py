"""露脸模式静态闸门（``production/face_cast.py``）的自检。

事故出处：在《雨夜屠夫林过云》之前，流水线是"不露脸"的（凶嫌只给背影与手），
所以没有任何机制管"人物的脸"。用户改规则之后，同一个模型没有人物记忆——
提示词一换，脸就换；两个角色描述写得像，就撞脸。这里守的是其中可机器化的那半：

1. **跨镜头一致**：每个角色的面容 token 必须逐字节出现在它的每个露脸镜头提示词里
   （token 只有一个来源，照抄才谈得上"同一个人"）；
2. **角色之间不同**：token 不许完全相同、也不许"复制粘贴改几个字"（相似度 ≥0.90 直接红）；
3. **登记才能露脸**：声明了的镜头必须存在、角色 id 必须存在；没声明却带上 token 要给警告。

画面闸门（抽帧、检脸、相似度）需要成片与检测器，不在离线自检里跑——
但 ``check_frames`` 的窗口解析、报告结构在这里做无检测器的冒烟测试。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "production"))

import face_cast  # noqa: E402

FACE_A = ("a 27-year-old Hong Kong Chinese man, long narrow face with a high forehead, "
          "thick straight eyebrows over small deep-set eyes, straight nose, thin lips, "
          "short black hair parted on the left, faint stubble")
FACE_B = ("a 31-year-old Hong Kong Chinese woman, round face with full cheeks, "
          "soft arched eyebrows over wide almond eyes, small upturned nose, "
          "full lips, shoulder-length wavy black hair, fair skin")


def shot(shot_id: str, prompt: str, kind: str = "agnes") -> dict:
    return {"id": shot_id, "kind": kind, "start": 0, "duration": 4, "prompt": prompt}


def build_project(root: Path, *, mode: str = "face", shots: list[dict] | None = None,
                  characters: list[dict] | None = None, faces: dict | None = None) -> Path:
    project = root / "production" / "demo"
    project.mkdir(parents=True, exist_ok=True)
    story = {
        "title": "测试", "fps": 30,
        "shots": shots if shots is not None else [
            shot("S01", f"Night street, {FACE_A}, walking away; camera stays fixed"),
            shot("S02", "rain on a window, empty room"),
            shot("S03", f"Archive room, {FACE_B}, reading a file"),
        ],
    }
    cast = {
        "mode": mode,
        "characters": characters if characters is not None else [
            {"id": "C1", "name": "司机", "role": "suspect", "face": FACE_A, "seed": 11},
            {"id": "C2", "name": "女记者", "role": "witness", "face": FACE_B, "seed": 22},
        ],
        "shots": faces if faces is not None else {"S01": ["C1"], "S03": ["C2"]},
    }
    (project / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
    (project / "cast.json").write_text(json.dumps(cast, ensure_ascii=False, indent=2), encoding="utf-8")
    return project


class PromptGateTests(unittest.TestCase):
    def test_clean_project_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            report = face_cast.check_prompts(project)
            self.assertEqual(report["errors"], [])
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(len(report["face_shots"]), 2)

    def test_missing_token_in_prompt_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shots = [shot("S01", "Night street, a man walking away; camera stays fixed")]
            project = build_project(Path(tmp), shots=shots, characters=[
                {"id": "C1", "name": "司机", "face": FACE_A}], faces={"S01": ["C1"]})
            report = face_cast.check_prompts(project)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("没有角色 C1 的 face token" in e for e in report["errors"]), report["errors"])

    def test_identical_face_tokens_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp), characters=[
                {"id": "C1", "name": "甲", "face": FACE_A},
                {"id": "C2", "name": "乙", "face": FACE_A},
            ], faces={"S01": ["C1"], "S03": ["C2"]}, shots=[
                shot("S01", f"x {FACE_A}"), shot("S03", f"y {FACE_A}")])
            report = face_cast.check_prompts(project)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("完全相同" in e for e in report["errors"]), report["errors"])

    def test_copy_paste_face_tokens_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            near = FACE_A.replace("long narrow face", "long narrow facial shape")
            project = build_project(Path(tmp), characters=[
                {"id": "C1", "name": "甲", "face": FACE_A},
                {"id": "C2", "name": "乙", "face": near},
            ], faces={"S01": ["C1"]}, shots=[shot("S01", f"x {FACE_A}"), shot("S03", "empty")])
            report = face_cast.check_prompts(project)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("相似度" in e and "撞脸" in e for e in report["errors"]), report["errors"])

    def test_unknown_shot_or_character_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp), faces={"S99": ["C1"], "S01": ["C9"]})
            report = face_cast.check_prompts(project)
            self.assertEqual(report["status"], "FAIL")
            joined = " ".join(report["errors"])
            self.assertIn("S99", joined)
            self.assertIn("C9", joined)

    def test_stray_token_in_undeclared_shot_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shots = [shot("S01", f"x {FACE_A}"), shot("S02", f"someone {FACE_B} in profile")]
            project = build_project(Path(tmp), shots=shots, faces={"S01": ["C1"]})
            report = face_cast.check_prompts(project)
            self.assertEqual(report["status"], "PASS")
            self.assertTrue(any("没在 cast.json 里声明" in w for w in report["warnings"]), report["warnings"])

    def test_other_characters_token_in_shot_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shots = [shot("S01", f"{FACE_A} and also {FACE_B} in the room")]
            project = build_project(Path(tmp), shots=shots, faces={"S01": ["C1"]})
            report = face_cast.check_prompts(project)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("出现了角色 C2 的 face token" in e for e in report["errors"]), report["errors"])

    def test_silhouette_mode_with_faces_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp), mode="silhouette", faces={"S01": ["C1"]})
            report = face_cast.check_prompts(project)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("silhouette" in e for e in report["errors"]), report["errors"])

    def test_short_face_token_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shots = [shot("S01", "a man with a short face")]
            project = build_project(Path(tmp), shots=shots,
                                    characters=[{"id": "C1", "name": "甲", "face": "a short face"}],
                                    faces={"S01": ["C1"]})
            report = face_cast.check_prompts(project)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("face token 只有" in e for e in report["errors"]), report["errors"])

    def test_init_writes_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "production" / "newone"
            self.assertEqual(face_cast.cmd_init(project, force=False), 0)
            data = json.loads((project / "cast.json").read_text(encoding="utf-8"))
            self.assertEqual(data["mode"], "face")
            self.assertTrue((project / "cast").is_dir())


class FrameGateSmokeTests(unittest.TestCase):
    """无检测器/无成片时也要给出可解释的报告，不许崩。"""

    def test_check_frames_skips_in_silhouette_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp), mode="silhouette", faces={},
                                    shots=[shot("S01", "rain on an empty street")])
            film = Path(tmp) / "fake.mp4"
            film.write_bytes(b"not a real film")
            report = face_cast.check_frames(project, film, Path(tmp) / "delivery")
            self.assertEqual(report["status"], "SKIP")

    def test_check_frames_reports_missing_film(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            report = face_cast.check_frames(project, Path(tmp) / "nope.mp4", Path(tmp) / "delivery")
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("找不到成片" in e for e in report["errors"]))

    def test_descriptor_math_is_sane(self) -> None:
        """相似度的算术本身要靠谱：同一块脸 ≈1.0，不同两块明显更低。"""
        from PIL import Image
        import random

        with tempfile.TemporaryDirectory() as tmp:
            random.seed(7)
            image = Image.new("L", (240, 120))
            pixels = image.load()
            for y in range(120):
                for x in range(240):
                    pixels[x, y] = 40 + (x % 37) * 3 + (y % 11)
            first = Path(tmp) / "a.png"
            image.save(first)
            image2 = Image.new("L", (240, 120))
            pixels2 = image2.load()
            for y in range(120):
                for x in range(240):
                    pixels2[x, y] = 200 - (y % 29) * 4 - (x % 7)
            second = Path(tmp) / "b.png"
            image2.save(second)

            box = (10, 10, 80, 80)
            left = face_cast._face_descriptor(first, box)
            same = face_cast._face_descriptor(first, box)
            different = face_cast._face_descriptor(second, box)
            self.assertAlmostEqual(face_cast._cosine(left, same), 1.0, places=4)
            self.assertLess(face_cast._cosine(left, different), 0.9)

    def test_shot_windows_fall_back_to_story_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            story = json.loads((project / "story.json").read_text(encoding="utf-8"))
            windows = face_cast._shot_windows(project, story)
            self.assertEqual(windows["S01"], (0.0, 4.0))


if __name__ == "__main__":
    unittest.main()
