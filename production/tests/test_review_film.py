"""审片工具的冻结帧复核：别把慢速运镜当成冻结帧，也别把真静止放过去。

参考片一审报了「35 处画面冻结超过 1 秒」，人工复核后 22 处是慢速 AI 素材被
16x16 的严阈值（0.6/255 灰阶）误判。所以 ``review_film.py`` 检出之后会用
64x64 再量一次并给出 ``verdict``。这两个函数就是那道复核，必须守着：

* 真静止（信息卡、档案照、片尾卡）要判成 ``static``，否则每次审片都在喊狼来了；
* 有微动的画面要判成 ``micro_motion``，否则真冻结会被当成"设计如此"放过去。
"""
import json
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "production"))

try:
    import review_film  # noqa: E402  - 顶层 import av，没装 PyAV 就整份跳过
except ImportError as error:  # pragma: no cover - 取决于环境
    review_film = None
    IMPORT_ERROR = error
else:
    IMPORT_ERROR = None


def card() -> Image.Image:
    """一张信息卡：深色底 + 几行浅色文字条，参考片里 6 张资料卡就长这样。"""
    frame = np.full((270, 480, 3), 18, dtype=np.uint8)
    frame[40:60, 60:420] = 210
    frame[90:100, 60:340] = 150
    frame[130:140, 60:380] = 150
    return Image.fromarray(frame)


def textured_frame() -> Image.Image:
    """一帧有纹理的实拍/AI 画面（参考片的 agnes 素材都是这种）。"""
    grains = np.random.default_rng(7).integers(0, 256, (68, 120), dtype=np.uint8)
    grainy = np.repeat(np.repeat(grains, 4, axis=0), 4, axis=1)[:270, :480]
    return Image.fromarray(grainy).filter(ImageFilter.GaussianBlur(1.2))


def shifted(image: Image.Image, pixels: int) -> Image.Image:
    return Image.fromarray(np.roll(np.asarray(image, dtype=np.uint8), pixels, axis=1))


class FrozenFrameTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if review_film is None:
            raise unittest.SkipTest(f"PyAV 未安装，跳过审片复核测试：{IMPORT_ERROR}")

    def test_identical_frames_are_perfectly_still(self):
        image = card()
        self.assertEqual(review_film.frame_delta(image, image.copy()), 0.0)

    def test_a_slow_pan_over_footage_is_micro_motion_not_a_freeze(self):
        """有纹理的画面慢速横移 1 像素：16x16 几乎看不出，64x64 必须判成微动。"""
        before = textured_frame()
        self.assertGreater(review_film.frame_delta(before, shifted(before, 1)),
                           review_film.TRIAGE_STATIC_DELTA)

    def test_a_flat_info_card_that_nudges_is_still_read_as_static(self):
        """资料卡只有几块纯色，横移 1 像素在 64x64 上仍然接近静止。"""
        before = card()
        self.assertLess(review_film.frame_delta(before, shifted(before, 1)),
                        review_film.TRIAGE_STATIC_DELTA)

    def test_triage_score_ignores_a_hard_cut_inside_the_window(self):
        """窗口里夹一次硬切：最大值会飙到 100+，中位数不受影响。

        第一版复核取的就是最大值，结果 13 张信息卡里有 12 张被误判成"有微动"。
        """
        deltas = [0.05] * 29 + [118.0]
        self.assertGreater(max(deltas), 100.0)
        self.assertAlmostEqual(review_film.triage_score(deltas), 0.05)
        self.assertEqual(review_film.frozen_verdict(review_film.triage_score(deltas)), "static")
        self.assertEqual(review_film.triage_score([]), 0.0)

    def test_threshold_sits_in_the_gap_measured_on_the_delivered_film(self):
        """阈值必须落在参考片实测出的两个簇中间，不许凭感觉调。

        数据来自 production/dahlia/delivery/frozen-triage-calibration.json：
        13 个真静止窗口的中位数 ≤ 0.08，22 个微动窗口的中位数 ≥ 0.21。
        """
        path = ROOT / "production" / "dahlia" / "delivery" / "frozen-triage-calibration.json"
        if not path.is_file():
            self.skipTest("缺标定数据（在成片上跑一遍 review_film.py 才有）")
        data = json.loads(path.read_text(encoding="utf-8"))
        threshold = review_film.TRIAGE_STATIC_DELTA
        self.assertGreater(threshold, data["cluster_static_max"],
                           "阈值低于静止簇上限，信息卡会被判成微动")
        self.assertLess(threshold, data["cluster_micro_min"],
                        "阈值高于微动簇下限，真冻结会被当成设计如此放行")
        self.assertEqual(data["misclassified_by_current_threshold"], 0,
                         "当前阈值在参考片上就有误判，重新标定")

    def test_verdict_separates_still_cards_from_micro_motion(self):
        self.assertEqual(review_film.frozen_verdict(0.0), "static")
        self.assertEqual(review_film.frozen_verdict(0.14), "static")
        self.assertEqual(review_film.frozen_verdict(0.15), "micro_motion")
        self.assertEqual(review_film.frozen_verdict(1.12), "micro_motion")

    def test_the_two_metrics_measure_different_things(self):
        """初筛 16x16 / 阈值 0.6，复核 64x64 / 阈值 0.15——不是同一个量，别直接比大小。

        16x16 把画面糊成 256 个格子，帧间差整体被压小，所以阈值更小；
        64x64 保留细节，微动才量得出来。复核的签名必须比初筛细，否则复核没有意义。
        """
        self.assertGreater(review_film.TRIAGE_SIGNATURE_SIZE,
                           review_film.FROZEN_SIGNATURE_SIZE)
        self.assertGreater(review_film.FROZEN_TOLERANCE, 0.0)
        self.assertGreater(review_film.TRIAGE_STATIC_DELTA, 0.0)


if __name__ == "__main__":
    unittest.main()
