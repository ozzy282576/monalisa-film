import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('generation', ROOT / 'scripts/generate.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class GenerationTests(unittest.TestCase):
    def test_story_contract(self):
        story = json.loads((ROOT / 'storyboard.json').read_text())
        self.assertEqual([s['id'] for s in story], [f'{i:02}' for i in range(1,16)])
        self.assertEqual(sum(int(s['seconds']) for s in story), 180)
        self.assertTrue(all(s['visual_review'] == 'pending' for s in story))

    def execute(self, response, initial=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'work').mkdir()
            (root / 'storyboard.json').write_text((ROOT / 'storyboard.json').read_text())
            if initial:
                (root / 'work/state.json').write_text(json.dumps(initial))
            with patch.multiple(g, ROOT=root, WORK=root/'work', CLIPS=root/'clips'), \
                 patch.dict('os.environ', {'AGNES_API_KEY': 'unit-test-not-a-real-key'}), \
                 patch.object(g, 'api', side_effect=response) as api, \
                 patch.object(g.time, 'sleep') as sleep, patch('builtins.print'):
                with self.assertRaises(SystemExit):
                    g.main()
                state = json.loads((root / 'work/state.json').read_text())
                return api.call_count, sleep.call_args_list, state

    def test_fifty_rejections_stop_without_next_scene(self):
        calls, sleeps, state = self.execute(HTTPError('https://example.invalid', 429, 'busy', {}, None))
        self.assertEqual(calls, 50)
        self.assertEqual(len(sleeps), 50)
        self.assertTrue(all(c.args == (75,) for c in sleeps))
        self.assertEqual(state['01']['tries'], 50)
        self.assertNotIn('02', state)

    def test_ambiguous_submission_does_not_duplicate(self):
        calls, _, state = self.execute(TimeoutError())
        self.assertEqual(calls, 1)
        self.assertEqual(state['01']['status'], 'submission_uncertain')

    def test_resume_preserves_attempt_budget(self):
        calls, _, state = self.execute(HTTPError('https://example.invalid', 429, 'busy', {}, None),
                                      {'01': {'tries':49, 'status':'create_rejected'}})
        self.assertEqual(calls, 1)
        self.assertEqual(state['01']['tries'], 50)

    def test_missing_video_id_stops(self):
        calls, _, state = self.execute([{'id':'task-not-video-id'}])
        self.assertEqual(calls, 1)
        self.assertEqual(state['01']['status'], 'submission_uncertain')


if __name__ == '__main__':
    unittest.main()
