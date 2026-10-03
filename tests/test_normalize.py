"""Real-media tests for normalize_assemble using a local static ffmpeg.

They build synthetic 12.25s @24fps sources and assert the pipeline yields
exactly 12.000s / 25fps / 300 frames per clip and 180.000s / 4500 frames for the
concatenated master, and that assembly is blocked without full approval.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import normalize_assemble as na


def have_ffmpeg():
    return shutil.which(na.FFMPEG) or Path(na.FFMPEG).exists()


@unittest.skipUnless(have_ffmpeg(), 'ffmpeg not available')
class NormalizeAssembleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='normtest'))
        cls.src = cls.tmp / 'src.mp4'
        subprocess.run([na.FFMPEG, '-y', '-v', 'error', '-f', 'lavfi',
                        '-i', 'testsrc=duration=12.25:size=1280x720:rate=24',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(cls.src)],
                       check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_source_is_raw_24fps(self):
        p = na.probe(self.src)
        self.assertEqual(p['fps'], 24)
        self.assertAlmostEqual(p['duration'], 12.25, delta=0.1)

    def test_normalize_to_exact_12s_25fps_300f(self):
        dst = self.tmp / 'n01.mp4'
        res = na.normalize_clip(self.src, dst)
        self.assertTrue(res['ok'], res['reasons'])
        self.assertEqual(res['probe']['frames'], 300)
        self.assertEqual(res['probe']['fps'], 25)
        self.assertAlmostEqual(res['probe']['duration'], 12.0, delta=0.05)

    def test_assemble_blocked_without_full_approval(self):
        norm = self.tmp / 'norm_blocked'
        norm.mkdir(exist_ok=True)
        n = na.normalize_clip(self.src, norm / '01.mp4')
        self.assertTrue(n['ok'])
        approval = self.tmp / 'appr_blocked.json'
        approval.write_text(json.dumps({'approved': ['01']}))
        with self.assertRaises(SystemExit):
            na.assemble(norm, self.tmp / 'blocked.mp4', approval)

    def test_assemble_15_to_180s_4500f(self):
        norm = self.tmp / 'norm'
        norm.mkdir(exist_ok=True)
        one = na.normalize_clip(self.src, norm / 't.mp4')
        self.assertTrue(one['ok'])
        for i in range(1, 16):
            shutil.copy(norm / 't.mp4', norm / ('%02d.mp4' % i))
        approval = self.tmp / 'appr.json'
        approval.write_text(json.dumps({'approved': ['%02d' % i for i in range(1, 16)]}))
        out = self.tmp / 'film.mp4'
        res = na.assemble(norm, out, approval)
        self.assertTrue(res['ok'], res['reasons'])
        self.assertEqual(res['probe']['frames'], 4500)
        self.assertAlmostEqual(res['probe']['duration'], 180.0, delta=0.1)


if __name__ == '__main__':
    unittest.main()
