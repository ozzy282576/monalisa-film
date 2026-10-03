"""Tests for finalize_film: audio build, label/subtitle burn, and approval gate."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import normalize_assemble as na
import finalize_film as ff


def have_ffmpeg():
    return shutil.which(na.FFMPEG) or Path(na.FFMPEG).exists()


@unittest.skipUnless(have_ffmpeg(), 'ffmpeg not available')
class FinalizeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='fin'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_build_audio_pads_to_180(self):
        vo = self.tmp / 'vo'
        vo.mkdir(exist_ok=True)
        ids = ['%02d' % i for i in range(1, 16)]
        for sid in ids:
            subprocess.run([na.FFMPEG, '-y', '-v', 'error', '-f', 'lavfi',
                            '-i', 'sine=frequency=440:duration=3', str(vo / ('%s.mp3' % sid))],
                           check=True, capture_output=True)
        out = self.tmp / 'vo180.wav'
        ff.build_audio(vo, str(out), ids)
        p = na.probe(out)
        self.assertAlmostEqual(p['duration'], 180.0, delta=0.2)

    def test_label_and_subtitle_burn_filters_valid(self):
        if not (ff.has_filter('drawtext') and ff.has_filter('subtitles')):
            self.skipTest('local ffmpeg lacks drawtext/subtitles (runner apt build has them)')
        srt = self.tmp / 't.srt'
        srt.write_text('1\n00:00:00,200 --> 00:00:02,000\n七十七条生命，一天之内消逝。\n\n')
        vf = ff.build_vf(str(srt), label=True)
        self.assertTrue(any(f.startswith('subtitles=') for f in vf))
        self.assertTrue(any(f.startswith('drawtext=') for f in vf))
        out = self.tmp / 'burn.mp4'
        r = subprocess.run([na.FFMPEG, '-y', '-v', 'error', '-f', 'lavfi',
                            '-i', 'testsrc=duration=2:size=1280x720:rate=25',
                            '-vf', ','.join(vf), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(out)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_finalize_blocked_without_full_approval(self):
        approval = self.tmp / 'appr.json'
        approval.write_text(json.dumps({'approved': ['01']}))
        with self.assertRaises(SystemExit):
            ff.finalize(self.tmp / 'clips', self.tmp / 'norm', self.tmp / 'o.mp4', approval)


if __name__ == '__main__':
    unittest.main()
