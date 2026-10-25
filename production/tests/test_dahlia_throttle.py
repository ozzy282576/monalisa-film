"""No real API calls or real sleeps. Verify quotas are respected, not bypassed."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'production'))
sys.path.insert(0,str(ROOT/'production/dahlia'))
import agnes_video as agnes
from throttle import RequestGate,BudgetExhausted


class FakeClock:
    def __init__(self):self.now=0.0;self.waits=[]
    def clock(self):return self.now
    def sleep(self,seconds):self.waits.append(seconds);self.now+=seconds


class ThrottleTests(unittest.TestCase):
    def test_creation_requests_are_spaced(self):
        time=FakeClock();gate=RequestGate(75,time.clock,time.sleep);calls=[]
        for _ in range(4):gate.acquire_creation(500);calls.append(time.clock())
        self.assertEqual(calls,[0,75,150,225])

    def test_retry_after_is_shared(self):
        time=FakeClock();gate=RequestGate(75,time.clock,time.sleep)
        gate.acquire_creation(500);gate.defer(180)
        gate.wait_unblocked(500)
        self.assertEqual(time.clock(),180)
        gate.acquire_creation(500)
        self.assertEqual(time.clock(),180)
        gate.acquire_creation(500)
        self.assertEqual(time.clock(),255)

    def test_does_not_ignore_cooldown_when_budget_too_short(self):
        time=FakeClock();gate=RequestGate(75,time.clock,time.sleep);gate.defer(200)
        with self.assertRaises(BudgetExhausted):gate.acquire_creation(100)
        self.assertEqual(time.waits,[])

    def test_rejects_configuration_above_free_video_rate(self):
        with self.assertRaises(ValueError):RequestGate(30)

    def test_retry_after_headers(self):
        self.assertEqual(agnes.parse_retry_after('120'),120)
        self.assertEqual(agnes.parse_retry_after('Wed, 09 Sep 2026 00:02:00 GMT',now=1788912000),120)
        self.assertIsNone(agnes.parse_retry_after('not a date'))

    def test_http_result_preserves_old_unpacking_contract(self):
        response=agnes.HttpResult(429,{'error':'rate limited'},'body',130)
        code,body,text=response
        self.assertEqual((code,body,text),(429,{'error':'rate limited'},'body'))
        self.assertEqual(response.retry_after,130)

    def test_rejected_create_is_typed_and_not_blindly_retried(self):
        response=agnes.HttpResult(429,{'error':{'message':'free video RPM exceeded'}},'',120)
        with patch.object(agnes,'http_json',return_value=response) as request:
            with self.assertRaises(agnes.RateLimited) as raised:
                agnes.create_task('https://example.invalid','test-key',{},retries=1,retry_delay=75)
        self.assertEqual(raised.exception.retry_after,120)
        self.assertEqual(request.call_count,1)

    def test_poll_honors_server_cooldown_and_notifies_shared_gate(self):
        responses=[agnes.HttpResult(429,{'error':'rate'},'',120),
                   agnes.HttpResult(200,{'status':'completed','metadata':{'url':'https://example.invalid/v.mp4'}},'')]
        time=FakeClock();cooldowns=[]
        with patch.object(agnes,'http_json',side_effect=responses), \
             patch.object(agnes.time,'monotonic',side_effect=time.clock), \
             patch.object(agnes.time,'sleep',side_effect=time.sleep):
            _,url=agnes.poll_task('https://example.invalid','test-key','agnes-video-v2.0','video_test',None,
                                 interval=25,timeout=1000,max_failures=5,rate_limit_callback=cooldowns.append)
        self.assertEqual(time.waits,[120]);self.assertEqual(cooldowns,[120])
        self.assertEqual(url,'https://example.invalid/v.mp4')


if __name__=='__main__':unittest.main()
