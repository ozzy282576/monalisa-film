"""Run with the media venv: python -m unittest discover -s production/tests -p test_dahlia_edit.py."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'production/dahlia'))
import render


class EditTests(unittest.TestCase):
    def test_exact_contiguous_three_minute_edl(self):
        project=json.loads((ROOT/'production/dahlia/story.json').read_text())
        durations=[25.68,29.52,23.36,24.56,25.28,27.84]
        cursor=.6;rows=[]
        for chapter,duration in zip(project['chapters'],durations):
            rows.append({'id':chapter['id'],'start':cursor,'end':cursor+duration/.93,
                         'raw_duration':duration,'tempo':.93})
            cursor+=duration/.93+1.08
        edl=render.make_edl(project,rows)
        self.assertEqual(edl[0]['start_frame'],0)
        self.assertEqual(edl[-1]['end_frame'],5400)
        self.assertEqual(sum(e['end_frame']-e['start_frame'] for e in edl),5400)
        for a,b in zip(edl,edl[1:]):self.assertEqual(a['end_frame'],b['start_frame'])
        used={e['id'] for e in edl if e['kind']=='agnes'}
        expected={s['id'] for s in project['shots'] if s['kind']=='agnes'}
        self.assertEqual(used,expected)

    def test_caption_splitting_preserves_all_text(self):
        project=json.loads((ROOT/'production/dahlia/story.json').read_text())
        for chapter in project['chapters']:
            clauses=render.caption_clauses(chapter['text'])
            self.assertEqual(''.join(clauses),chapter['text'])
            self.assertTrue(all(0<len(c)<=24 for c in clauses))

    def test_ass_clock_carries_to_next_minute(self):
        self.assertEqual(render.ass_time(59.999),'0:01:00.00')
        self.assertEqual(render.ass_time(180),'0:03:00.00')


if __name__=='__main__':unittest.main()
