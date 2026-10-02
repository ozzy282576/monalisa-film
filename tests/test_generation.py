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
    def test_200_budget_continues_from_50_across_windows_without_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'work').mkdir()
            state = {'11': {'tries':50, 'status':'exhausted', 'prior_batches':[{'tries':50}]}}
            item = {'id':'11', 'prompt':'unit-test'}
            with patch.multiple(g, ROOT=root, WORK=root/'work', CLIPS=root/'clips', MAX_TRIES=200), \
                 patch.object(g, 'api', side_effect=HTTPError('https://example.invalid',503,'busy',{},None)) as api, \
                 patch.object(g.time,'sleep') as sleep, patch('builtins.print'):
                for expected in (100,150,200,200):
                    g.collect_one(item,state,'fake',create_window=50)
                    self.assertEqual(state['11']['tries'],expected)
                self.assertEqual(api.call_count,150)
                self.assertEqual(sleep.call_count,150)
                self.assertTrue(all(call.args==(75,) for call in sleep.call_args_list))
                self.assertEqual(state['11']['status'],'exhausted')
                self.assertEqual(state['11']['prior_batches'],[{'tries':50}])

    def test_checkpoint_window_polls_existing_task_before_new_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'work').mkdir()
            state = {'11':{'tries':50,'status':'polling','video_id':'existing-task'}}
            responses=[{'status':'failed'},HTTPError('https://example.invalid',503,'busy',{},None)]
            with patch.multiple(g, ROOT=root,WORK=root/'work',CLIPS=root/'clips',MAX_TRIES=200), \
                 patch.object(g,'api',side_effect=responses) as api, patch.object(g.time,'sleep'), patch('builtins.print'):
                g.collect_one({'id':'11','prompt':'unit-test'},state,'fake',create_window=1)
                self.assertEqual(api.call_args_list[0].args[0],'GET')
                self.assertEqual(api.call_args_list[1].args[0],'POST')
                self.assertEqual(api.call_count,2)
                self.assertEqual(state['11']['tries'],51)

    def test_retry_batch_renews_only_selected_scene_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {sid: {'tries':50, 'status':'exhausted', 'http_code':503} for sid in ('01','07')}
            with patch.object(g, 'CLIPS', Path(tmp)), patch.object(g, 'save'):
                g.prepare_retry_batch(state, '01', 'batch-1')
                self.assertEqual(state['01']['tries'], 0)
                self.assertEqual(state['01']['prior_batches'][0]['tries'], 50)
                self.assertEqual(state['07']['tries'], 50)
                state['01'].update(tries=50, status='exhausted')
                g.prepare_retry_batch(state, '01', 'batch-1')
                self.assertEqual(state['01']['tries'], 50)
                self.assertEqual(len(state['01']['prior_batches']), 1)

    def test_retry_keeps_downloaded_fifteen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'15.mp4').write_bytes(b'raw')
            state = {'15': {'tries':50, 'status':'downloaded'}}
            with patch.object(g, 'CLIPS', root), patch.object(g, 'save') as save:
                g.prepare_retry_batch(state, '15', 'batch-1')
                save.assert_not_called()
                self.assertEqual(state['15']['tries'], 50)

    def test_retry_never_resets_active_or_uncertain_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            for values in ({'video_id':'known-task','status':'polling'}, {'status':'submission_uncertain'}):
                state = {'15':dict(tries=50, **values)}
                with patch.object(g, 'CLIPS', Path(tmp)), patch.object(g, 'save') as save:
                    g.prepare_retry_batch(state, '15', 'batch-1')
                    save.assert_not_called()
                    self.assertEqual(state['15']['tries'], 50)

    def test_downloaded_clip_skips_qc(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '01.mp4').write_bytes(b'raw-unchecked')
            state = {'01': {'status': 'downloaded', 'tries': 1}}
            with patch.object(g, 'CLIPS', root), patch.object(g, 'qc') as qc, patch.object(g, 'api') as api:
                g.collect_one({'id':'01'}, state, 'fake')
                qc.assert_not_called()
                api.assert_not_called()

    def test_batch_review_waits_for_all_fifteen(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(g, 'CLIPS', Path(tmp)), patch.object(g, 'qc') as qc:
                with self.assertRaises(SystemExit):
                    g.review_and_repair([{'id':f'{i:02}'} for i in range(1,16)], {}, 'fake')
                qc.assert_not_called()

    def test_auth_rejection_stops_immediately(self):
        calls, sleeps, state = self.execute(HTTPError('https://example.invalid', 401, 'unauthorized', {}, None))
        self.assertEqual(calls, 1)
        self.assertEqual(len(sleeps), 0)
        self.assertEqual(state['01']['http_code'], 401)

    def test_story_contract(self):
        story = json.loads((ROOT / 'storyboard.json').read_text())
        self.assertEqual([s['id'] for s in story], [f'{i:02}' for i in range(1,16)])
        self.assertEqual(sum(int(s['seconds']) for s in story), 180)
        self.assertTrue(all(s['visual_review'] == 'pending' for s in story))

    def execute(self, response, initial=None, scene=None, expect_exit=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'work').mkdir()
            (root / 'storyboard.json').write_text((ROOT / 'storyboard.json').read_text())
            if initial:
                (root / 'work/state.json').write_text(json.dumps(initial))
            with patch.multiple(g, ROOT=root, WORK=root/'work', CLIPS=root/'clips'), \
                 patch.dict('os.environ', {'AGNES_API_KEY': 'unit-test-not-a-real-key'}), \
                 patch.object(g, 'api', side_effect=response) as api, \
                 patch.object(g.time, 'sleep') as sleep, patch('builtins.print'), patch('sys.argv', ['generate.py'] + (['--scene', scene] if scene else [])):
                if expect_exit:
                    with self.assertRaises(SystemExit):
                        g.main()
                else:
                    g.main()
                state = json.loads((root / 'work/state.json').read_text())
                return api.call_count, sleep.call_args_list, state

    def test_fifty_rejections_per_scene_continue_through_all_fifteen(self):
        calls, sleeps, state = self.execute(HTTPError('https://example.invalid', 503, 'busy', {}, None), expect_exit=False)
        self.assertEqual(calls, 750)
        self.assertEqual(len(sleeps), 750)
        self.assertTrue(all(c.args == (75,) for c in sleeps))
        self.assertEqual(len(state), 15)
        self.assertTrue(all(st['tries'] == 50 and st['status'] == 'exhausted' for st in state.values()))

    def test_exhausted_first_scene_does_not_block_second(self):
        calls, _, state = self.execute(HTTPError('https://example.invalid', 503, 'busy', {}, None),
            {'01': {'tries':50, 'status':'create_rejected'}}, expect_exit=False)
        self.assertEqual(calls, 700)
        self.assertEqual(state['01']['tries'], 50)
        self.assertEqual(state['02']['tries'], 50)
        self.assertEqual(state['15']['tries'], 50)

    def test_ambiguous_submission_does_not_duplicate(self):
        calls, _, state = self.execute(TimeoutError())
        self.assertEqual(calls, 1)
        self.assertEqual(state['01']['status'], 'submission_uncertain')

    def test_resume_preserves_attempt_budget(self):
        calls, _, state = self.execute(HTTPError('https://example.invalid', 429, 'busy', {}, None),
                                      {'01': {'tries':49, 'status':'create_rejected'}}, scene='01', expect_exit=False)
        self.assertEqual(calls, 1)
        self.assertEqual(state['01']['tries'], 50)

    def test_missing_video_id_stops(self):
        calls, _, state = self.execute([{'id':'task-not-video-id'}])
        self.assertEqual(calls, 1)
        self.assertEqual(state['01']['status'], 'submission_uncertain')


if __name__ == '__main__':
    unittest.main()
