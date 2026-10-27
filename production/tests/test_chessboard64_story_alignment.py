"""Regression checks for narration-to-picture alignment and prompt contracts."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "chessboard64"
sys.path.insert(0, str(PROJECT))
import build_story  # noqa: E402

STORY = json.loads((PROJECT / "story.json").read_text(encoding="utf-8"))


class StoryAlignmentTests(unittest.TestCase):
    def test_story_source_is_exactly_38_dynamic_shots_and_7_cards(self):
        shots = STORY["shots"]
        self.assertEqual(len(shots), 45)
        self.assertEqual(sum(s["kind"] == "cogvideo" for s in shots), 38)
        self.assertEqual(sum(s["kind"] == "graphic" for s in shots), 7)
        for shot, source_row in zip(shots, build_story.SHOTS):
            kind, purpose, camera, prompt_or_graphic, characters, sfx_note = source_row
            self.assertEqual(shot["kind"], kind, shot["id"])
            self.assertEqual(shot["purpose"], purpose, shot["id"])
            self.assertEqual(shot["camera"], camera, shot["id"])
            self.assertEqual(shot["prompt"], prompt_or_graphic if kind == "cogvideo" else "", shot["id"])
            self.assertEqual(shot["graphic"], prompt_or_graphic if kind == "graphic" else "", shot["id"])
            self.assertEqual(shot["characters"], characters, shot["id"])
            self.assertEqual(shot["sfx_note"], sfx_note, shot["id"])
        self.assertEqual(STORY["character_settings"], build_story.CHARACTER_SETTINGS)
        self.assertEqual(STORY["presentation"]["cards"], build_story.presentation()["cards"])

    def test_every_dynamic_prompt_has_style_roles_and_negative_suffix(self):
        for shot in STORY["shots"]:
            if shot["kind"] != "cogvideo":
                continue
            prompt = build_story.compose_prompt(STORY, shot)
            self.assertTrue(prompt.startswith("【STYLE】"), shot["id"])
            self.assertIn("【NEGATIVE】", prompt, shot["id"])
            self.assertTrue(prompt.rstrip().endswith("."), shot["id"])
            self.assertLessEqual(len(prompt), 2600, shot["id"])
            if shot["characters"]:
                for character in shot["characters"]:
                    self.assertIn(f"【角色设定：{character}】", prompt, shot["id"])

    def test_known_narration_mismatches_have_matching_revised_visuals(self):
        expectations = {
            "S04": "媒体报道中的绰号",
            "S05": "六十四格来自他的自述",
            "S06": "法院认定四十八起谋杀",
            "S09": "在莫斯科受审",
            "S10": "成年后在超市做理货员",
            "S11": "下班后常去的比察公园",
            "S12": "石桌、棋友与日常对弈",
            "S13": "公开报道所述的邀约方式",
            "S14": "熟悉棋友的印象与六十三个记号",
            "S15": "按他的说法，棋盘几乎被填满",
            "S16": "2002年公开报道记载",
            "S17": "幸存者在二〇〇二年向警方报告",
            "S24": "衣袋里的地铁票",
            "S25": "车站监控显示两人同行",
            "S26": "纸条与地铁票进入证据链",
            "S29": "地铁票追到比察公园",
            "S34": "陪审团认定四十八起谋杀",
            "S35": "法院认定三起未遂并判处终身监禁",
            "S38": "每个数字都要说明来源",
        }
        shots = {s["id"]: s for s in STORY["shots"]}
        for sid, phrase in expectations.items():
            self.assertIn(phrase, shots[sid]["purpose"], sid)
        self.assertEqual(shots["S10"]["kind"], "cogvideo")
        self.assertEqual(shots["S16"]["kind"], "graphic")
        self.assertEqual(STORY["presentation"]["cards"]["S16"],
                         ["2002年 · 公开报道", "一位女性幸存者曾向警方报告", "不呈现她的具体经历"])
        self.assertEqual(STORY["presentation"]["cards"]["S33"][1],
                         "警方发现与棋盘记号相关的证物")
        self.assertEqual(STORY["presentation"]["cards"]["S39"][1], "受害者不是数字")

    def test_2002_source_card_is_explicit_and_non_sensational(self):
        shot = {s["id"]: s for s in STORY["shots"]}["S16"]
        self.assertEqual(shot["kind"], "graphic")
        self.assertIn("2002年", shot["graphic"])
        self.assertIn("公开报道", shot["graphic"])
        self.assertIn("不呈现她的具体经历", shot["graphic"])
        self.assertEqual(shot["characters"], [])

    def test_moving_people_are_prompted_with_forward_natural_gait(self):
        shots = {s["id"]: s for s in STORY["shots"]}
        for sid in ("S01", "S02", "S10", "S11", "S25", "S32", "S44"):
            prompt = shots[sid]["prompt"].lower()
            self.assertTrue("forward" in prompt or "toward" in prompt, sid)
            self.assertTrue("heel-to-toe" in prompt or "direction of travel" in prompt, sid)


if __name__ == "__main__":
    unittest.main()
