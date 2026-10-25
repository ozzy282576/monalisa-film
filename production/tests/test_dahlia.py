"""Offline production-plan, provenance and subtitle-timing tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'production/dahlia'))
import generate as generator
from align_audio import aligned_cues,normalize


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.project=json.loads((ROOT/'production/dahlia/story.json').read_text())

    def test_complete_plan_and_model(self):
        generator.validate(self.project)
        self.assertEqual(sum(s['kind']=='agnes' for s in self.project['shots']),23)
        self.assertEqual(sum(s['kind']=='graphic' for s in self.project['shots']),6)
        self.assertEqual(sum(s['kind']=='archive' for s in self.project['shots']),1)
        for shot in self.project['shots']:
            if shot['kind']=='agnes':
                self.assertEqual(generator.full_payload(self.project,shot)['model'],'agnes-video-v2.0')

    def test_existing_first_clip_will_be_reused(self):
        path=ROOT/'production/dahlia/results.json'
        if not path.exists():self.skipTest('No production receipt yet')
        result=json.loads(path.read_text())['shots']['S01']
        wanted=generator.request_hash(self.project,self.project['shots'][0])
        self.assertTrue(generator.cached_result_matches(result,wanted))
        self.assertFalse(generator.cached_result_matches(result,'different-request'))
        self.assertFalse(generator.cached_result_matches({**result,'sha256':None},wanted))
        all_results=json.loads(path.read_text())['shots']
        for shot in self.project['shots']:
            if shot['kind']!='agnes':continue
            existing=all_results.get(shot['id'],{})
            if existing.get('status')=='completed':
                self.assertTrue(generator.cached_result_matches(existing,generator.request_hash(self.project,shot)),shot['id'])

    def test_audio_is_bound_to_the_reviewed_script(self):
        root=ROOT/'production/dahlia/audio'
        manifest=json.loads((root/'manifest.json').read_text())
        self.assertEqual(manifest['voice_id'],'voice-00')
        self.assertEqual(len(manifest['clips']),6)
        for c,record in zip(self.project['chapters'],manifest['clips']):
            self.assertEqual(c['id'],record['id']);self.assertEqual(c['text'],record['text'])
            self.assertEqual(hashlib.sha256((root/record['file']).read_bytes()).hexdigest(),record['sha256'])

    def test_no_contradictory_folder_prompt(self):
        text=next(s['prompt'] for s in self.project['shots'] if s['id']=='S26').lower()
        self.assertIn('open',text);self.assertNotIn('closed case folder',text)

    def test_numeral_normalization(self):
        self.assertEqual(normalize('1947年1月15日，22岁，56分钟。'),'一九四七年一月十五日二十二岁五十六分钟')

    def test_asr_alignment_retains_correct_script(self):
        row={'text':'她只有二十二岁。','raw_duration':4,'start':20,'tempo':1}
        words=[{'word':'她','start':.2,'end':.6},{'word':'只有','start':.6,'end':1.2},
               {'word':'22岁','start':1.3,'end':2.8}]
        cues,coverage=aligned_cues(row,['她只有二十二岁。'],words)
        self.assertEqual(coverage,1)
        self.assertEqual(cues[0]['text'],row['text'])
        self.assertGreaterEqual(cues[0]['start'],20)
        bad,coverage=aligned_cues(row,['她只有二十二岁。'],[{'word':'无关','start':0,'end':1}])
        self.assertIsNone(bad);self.assertLess(coverage,.75)


if __name__=='__main__':unittest.main()
