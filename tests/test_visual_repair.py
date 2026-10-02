import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('init_visual_repair',ROOT/'scripts/init_visual_repair.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class VisualRepairTests(unittest.TestCase):
    def fixture(self, root, expected=None):
        for folder in ('clips','work','review'):
            (root/folder).mkdir()
        (root/'clips/01.mp4').write_bytes(b'reviewed-original')
        digest=expected or hashlib.sha256(b'reviewed-original').hexdigest()
        (root/'review/repair-plan.json').write_text(json.dumps({'revision':'v1','clips':[{
            'id':'01','source_sha256':digest,'prompt':'corrected shot'}]}))
        (root/'work/state.json').write_text(json.dumps({'01':{
            'status':'downloaded','tries':17,'video_id':'old-completed-task'},
            '02':{'status':'downloaded','tries':3}}))
        (root/'storyboard.json').write_text(json.dumps([{'id':'01','prompt':'old shot'},{'id':'02','prompt':'unchanged'}]))
        (root/'work/qc-01.json').write_text('{"machine_qc":"pass"}')

    def test_preserves_source_and_does_not_reset_candidate_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.fixture(root)
            m.prepare(root,'01')
            self.assertEqual((root/'work/rejected/v1/01.mp4').read_bytes(),b'reviewed-original')
            self.assertFalse((root/'clips/01.mp4').exists())
            self.assertFalse((root/'work/qc-01.json').exists())
            state=json.loads((root/'work/state.json').read_text())
            self.assertEqual(state['01']['tries'],0)
            self.assertNotIn('video_id',state['01'])
            self.assertEqual(state['01']['previous_generation']['tries'],17)
            self.assertEqual(state['02']['tries'],3)
            state['01'].update(tries=50,status='exhausted')
            (root/'work/state.json').write_text(json.dumps(state))
            m.prepare(root,'01')
            self.assertEqual(json.loads((root/'work/state.json').read_text())['01']['tries'],50)

    def test_refuses_unreviewed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.fixture(root,expected='incorrect-hash')
            with self.assertRaises(SystemExit):
                m.prepare(root,'01')
            self.assertEqual((root/'clips/01.mp4').read_bytes(),b'reviewed-original')

    def test_no_final_approvals_in_initial_review(self):
        report=json.loads((ROOT/'review/findings.json').read_text())
        self.assertEqual(len(report['clips']),15)
        self.assertTrue(all(not x['final_visual_approval'] for x in report['clips']))
        self.assertEqual([x['id'] for x in report['clips'] if x['decision']=='redo'],['01','07','10','11','12','13'])


if __name__=='__main__':
    unittest.main()
