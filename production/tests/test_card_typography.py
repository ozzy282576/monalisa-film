"""卡片排字闸门：一行字不许越出画面（对仓库里每个新式项目生效）。

事故出处（2026-10-06，狂犬病那部）：片尾卡问句「医学史最该被记住的，是勇气，还是验证勇气的证据？」
有 25 个全角字，``centered()`` 按固定 96 px 居中排出来约 2304 px 宽，画面只有 1920 px
—— 两端各被裁掉约两个字，成片 174–180 秒每一帧都如此。三道自动闸门全绿：
逐帧审计只量黑帧、冻结、帧间差异和人脸/手，**从不量文字有没有溢出画面**。
所以这条闸门只能靠"把卡片真画出来、量安全带上有没有像素"来做。

守三件事（对每个"有 presentation.end_card 的项目"）：

1. 引擎必须带排字闸门本身（``fit_size`` / ``CARD_TEXT_MAX_WIDTH``）——
   有人把自适应缩号改回固定字号，这里会红；
2. 真画一次片尾卡与每张信息卡，左右各 100 px 的安全带里不许出现文字像素
   （已验证判别力：把 ``centered`` 换回不缩号的旧写法，安全带最亮像素 243 > 阈值 120）；
3. 缩号要有边界：该缩的必须缩、缩完不得超过安全宽、不得缩到比副题字号还小
   （那说明该改文案而不是继续缩号），本来放得下的不许乱缩。

没有中文字体时跳过 —— 本仓库拒绝用缺字的字体出片；渲染与离线自检都会装 ``fonts-noto-cjk``。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ROOT / "production"
SAFE_BAND = 100          # 左右安全带宽度（px）：文字不许进
EDGE_THRESHOLD = 120     # 安全带里超过这个灰度就算有字（背景噪声/辉光 ≈ 40）
LEGIBLE_FLOOR = 60       # 主标题缩到这个字号以下就不叫标题了：该改文案
SUBTITLE_SIZE = 46       # 片尾卡第二行的字号（模板布局里的值）


def project_render_modules():
    """找出所有"新式"项目：story.json 里有 presentation.end_card，且目录里有 render.py。"""
    for project in sorted(p for p in PRODUCTION.iterdir() if p.is_dir()):
        story = project / "story.json"
        render = project / "render.py"
        if not (story.is_file() and render.is_file()):
            continue
        try:
            presentation = json.loads(story.read_text(encoding="utf-8")).get("presentation") or {}
        except (ValueError, OSError):
            continue
        if presentation.get("end_card"):
            yield project, presentation, render


def load_project_render(project: Path):
    """按路径加载某个项目的 render.py（仓库里多个项目同名模块，必须隔离）。"""
    stashed = {name: sys.modules.pop(name) for name in ("render", "media", "build_audio")
               if name in sys.modules}
    path_snapshot = list(sys.path)
    spec = importlib.util.spec_from_file_location(f"{project.name}_render", project / "render.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        for name in ("media", "build_audio"):
            sys.modules.pop(name, None)     # 本项目带进来的依赖副本不要留在全局
        sys.modules.update(stashed)         # 别的项目的同名模块原样放回
        sys.path[:] = path_snapshot
    return module


class CardTypographyTests(unittest.TestCase):
    def setUp(self):
        self.cases = list(project_render_modules())
        if not self.cases:
            self.skipTest("仓库里还没有带 presentation.end_card 的项目")

    @staticmethod
    def font_available(render, serif: bool) -> bool:
        try:
            render.find_font(serif)
        except RuntimeError:
            return False
        return True

    def render_card(self, render, sid: str, presentation: dict, tmp: str) -> np.ndarray:
        path = render.card_image(sid, "", Path(tmp), presentation)
        return np.asarray(Image.open(path).convert("L"), dtype=int)

    def test_engine_carries_the_typography_gate(self):
        """有人把自适应缩号删回固定字号，这里必须红——否则闸门就是摆设。"""
        for project, _presentation, _path in self.cases:
            with self.subTest(project=project.name):
                render = load_project_render(project)
                self.assertTrue(hasattr(render, "fit_size"),
                                f"{project.name}/render.py 没有 fit_size：卡片排字闸门被删了？")
                self.assertIsInstance(getattr(render, "CARD_TEXT_MAX_WIDTH", None), int,
                                      f"{project.name}/render.py 没有 CARD_TEXT_MAX_WIDTH 安全宽")

    def test_cards_keep_text_inside_the_frame(self):
        if not all(self.font_available(load_project_render(p), s)
                   for p, _e, _r in self.cases for s in (True, False)):
            self.skipTest("缺少中文 Noto CJK 字体（渲染工作流会装 fonts-noto-cjk）")
        for project, presentation, _path in self.cases:
            render = load_project_render(project)
            card_ids = ["END", *(presentation.get("cards") or {})]
            with tempfile.TemporaryDirectory() as tmp:
                for sid in card_ids:
                    with self.subTest(project=project.name, card=sid):
                        pixels = self.render_card(render, sid, presentation, tmp)
                        self.assertEqual(pixels.shape, (1080, 1920))
                        self.assertGreater(pixels.max(), 200, f"{sid} 卡片上一个字都没有，闸门等于没测")
                        band = np.concatenate([pixels[:, :SAFE_BAND].ravel(),
                                               pixels[:, -SAFE_BAND:].ravel()])
                        self.assertLess(int(band.max()), EDGE_THRESHOLD,
                                        f"{project.name} 的 {sid} 卡有字落进左右 {SAFE_BAND} px 安全带："
                                        "检查 render.centered / fit_size")

    def test_shrinking_has_bounds(self):
        if not all(self.font_available(load_project_render(p), True) for p, _e, _r in self.cases):
            self.skipTest("缺少中文 Noto CJK 字体（渲染工作流会装 fonts-noto-cjk）")
        for project, presentation, _path in self.cases:
            render = load_project_render(project)
            draw = ImageDraw.Draw(Image.new("RGB", (1920, 1080)))
            question = presentation["end_card"][0]
            requested = 96
            natural = render.text_width(draw, question, requested, serif=True)
            fitted = render.fit_size(draw, question, requested, render.CARD_TEXT_MAX_WIDTH, serif=True)
            with self.subTest(project=project.name):
                self.assertLessEqual(render.text_width(draw, question, fitted, serif=True),
                                     render.CARD_TEXT_MAX_WIDTH)
                if natural > render.CARD_TEXT_MAX_WIDTH:
                    self.assertLess(fitted, requested, "放不下却不缩号，字会被裁掉")
                    self.assertGreaterEqual(fitted, LEGIBLE_FLOOR,
                                            f"主标题被缩到 {fitted} px，已不比 {SUBTITLE_SIZE} px 的副题大："
                                            "该改文案（build_story.py 的 END_CARD）而不是继续缩号")
                else:
                    self.assertEqual(fitted, requested, "放得下就不该乱缩号")


if __name__ == "__main__":
    unittest.main()
