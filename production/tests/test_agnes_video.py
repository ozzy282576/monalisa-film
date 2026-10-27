#!/usr/bin/env python3
"""Offline tests for production/agnes_video.py.

A small in-process HTTP server imitates the Agnes gateway (create task, poll with
transient errors and simplified responses, legacy fallback, video download), so the
whole CLI flow can be exercised without network access or an API key.

Run:  python3 production/tests/test_agnes_video.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PRODUCTION_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PRODUCTION_DIR / "agnes_video.py"
sys.path.insert(0, str(PRODUCTION_DIR))

import agnes_video  # noqa: E402

API_KEY = "test-key"
FAKE_VIDEO = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 32  # 8 KB, > the 1 KB sanity floor


class MockAgnes(BaseHTTPRequestHandler):
    """Scriptable stand-in for apihub.agnes-ai.com."""

    poll_script: list = []  # queue of (status_code, body) for the poll endpoint
    requests: list = []
    create_failures = 0  # how many 503s to return before accepting the task
    primary_404 = False  # make /agnesapi 404 so the client must use /v1/videos/<task_id>

    def log_message(self, *_args):  # keep test output clean
        pass

    def _send(self, code, body=None, raw=None, ctype="application/json"):
        data = raw if raw is not None else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        return self.headers.get("Authorization") == f"Bearer {API_KEY}"

    def completed_body(self):
        host, port = self.server.server_address[:2]
        return {
            "id": "task_1",
            "task_id": "task_1",
            "video_id": "video_1",
            "status": "completed",
            "progress": 100,
            "seconds": "5.0",
            "size": "1280x720",
            "metadata": {
                "size_mapping": {"adjusted": False, "message": "kept 720p/16:9"},
                "url": f"http://{host}:{port}/out.mp4",
            },
        }

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        type(self).requests.append(("POST", self.path, payload))
        if not self._authorized():
            return self._send(401, {"error": {"message": "invalid api key", "code": "unauthorized"}})
        if self.path != "/v1/videos":
            return self._send(404, {"error": "not found"})
        if type(self).create_failures > 0:
            type(self).create_failures -= 1
            return self._send(503, {"error": {"message": "service busy"}})
        frames = payload.get("num_frames")
        if not isinstance(frames, int) or (frames - 1) % 8 or frames > 441:
            return self._send(400, {"error": {"message": "num_frames must follow 8n+1"}})
        return self._send(
            200,
            {
                "id": "task_1",
                "task_id": "task_1",
                "video_id": "video_1",
                "object": "video",
                "model": payload.get("model"),
                "status": "queued",
                "progress": 0,
                "created_at": 1,
                "seconds": f"{frames / payload['frame_rate']:.1f}",
                "size": f"{payload['width']}x{payload['height']}",
            },
        )

    def do_GET(self):
        type(self).requests.append(("GET", self.path, None))
        parsed = urlparse(self.path)
        if parsed.path == "/out.mp4":
            return self._send(200, raw=FAKE_VIDEO, ctype="video/mp4")
        if not self._authorized():
            return self._send(401, {"error": {"message": "invalid api key"}})
        if parsed.path == "/agnesapi":
            if type(self).primary_404:
                return self._send(404, {"error": {"message": "video not found"}})
            query = parse_qs(parsed.query)
            if query.get("video_id") != ["video_1"]:
                return self._send(404, {"error": {"message": "unknown video_id"}})
            return self._next_poll_response()
        if parsed.path == "/v1/videos/task_1":
            return self._next_poll_response()
        return self._send(404, {"error": "not found"})

    def _next_poll_response(self):
        if type(self).poll_script:
            code, body = type(self).poll_script.pop(0)
        else:
            code, body = 200, self.completed_body()
        if body == "COMPLETED":
            body = self.completed_body()
        return self._send(code, body)


def run_cli(*args, base_url=None, api_key=API_KEY, cwd=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
    env.pop("AGNES_BASE_URL", None)
    if api_key is not None:
        env["AGNES_API_KEY"] = api_key
    else:
        env.pop("AGNES_API_KEY", None)
    cmd = [sys.executable, str(SCRIPT), *args]
    if base_url:
        cmd += ["--base-url", base_url, "--poll-interval", "0.02", "--retry-delay", "0.02"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env, cwd=cwd)


class FrameMathTests(unittest.TestCase):
    def test_duration_to_frames_follows_8n_plus_1(self):
        self.assertEqual(agnes_video.frames_for_duration(5, 24), 121)
        self.assertEqual(agnes_video.frames_for_duration(10, 24), 241)
        self.assertEqual(agnes_video.frames_for_duration(3, 24), 73)
        self.assertEqual(agnes_video.frames_for_duration(18.4, 24), 441)
        self.assertEqual(agnes_video.frames_for_duration(100, 24), 441)  # clamped
        self.assertEqual(agnes_video.frames_for_duration(0.1, 24), 9)  # floor
        for seconds in (1, 2.5, 7, 12.34, 18):
            frames = agnes_video.frames_for_duration(seconds, 30)
            self.assertEqual((frames - 1) % 8, 0)
            self.assertLessEqual(frames, 441)

    def test_explicit_frames_are_validated(self):
        for bad in ("100", "0", "449", "8"):
            with self.assertRaises(Exception):
                agnes_video.frames_type(bad)
        self.assertEqual(agnes_video.frames_type("441"), 441)


class DryRunPayloadTests(unittest.TestCase):
    def payload(self, *args):
        result = run_cli("--dry-run", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_text_to_video_defaults(self):
        payload = self.payload("--prompt", "  a cat on the beach  ")
        self.assertEqual(payload["model"], "agnes-video-v2.0")
        self.assertEqual(payload["prompt"], "a cat on the beach")
        self.assertEqual((payload["width"], payload["height"]), (1280, 720))
        self.assertEqual(payload["num_frames"], 121)
        self.assertEqual(payload["frame_rate"], 24)
        self.assertNotIn("image", payload)
        self.assertNotIn("extra_body", payload)

    def test_single_image_is_image_to_video(self):
        payload = self.payload("--prompt", "p", "--image", "https://x/a.png", "--aspect", "9:16", "--seconds", "10")
        self.assertEqual(payload["image"], "https://x/a.png")
        self.assertEqual((payload["width"], payload["height"]), (720, 1280))
        self.assertEqual(payload["num_frames"], 241)
        self.assertNotIn("extra_body", payload)

    def test_multiple_images_become_keyframes(self):
        payload = self.payload("--prompt", "p", "--image", "https://x/1.png", "--image", "https://x/2.png")
        self.assertNotIn("image", payload)
        self.assertEqual(payload["extra_body"], {"image": ["https://x/1.png", "https://x/2.png"], "mode": "keyframes"})

    def test_optional_fields_and_overrides(self):
        payload = self.payload(
            "--prompt", "p", "--negative-prompt", "blurry", "--seed", "7", "--steps", "30",
            "--width", "1024", "--height", "576", "--num-frames", "81", "--frame-rate", "30",
        )
        self.assertEqual(payload["negative_prompt"], "blurry")
        self.assertEqual(payload["seed"], 7)
        self.assertEqual(payload["num_inference_steps"], 30)
        self.assertEqual((payload["width"], payload["height"]), (1024, 576))
        self.assertEqual(payload["num_frames"], 81)
        self.assertEqual(payload["frame_rate"], 30)

    def test_invalid_inputs_are_rejected(self):
        self.assertEqual(run_cli("--dry-run", "--prompt", "p", "--num-frames", "100").returncode, 2)
        self.assertEqual(run_cli("--dry-run", "--prompt", "p", "--frame-rate", "90").returncode, 2)
        self.assertEqual(run_cli("--dry-run", "--prompt", "p", "--image", "/local/file.png").returncode, 1)
        self.assertEqual(run_cli("--dry-run", "--prompt", "p", "--mode", "keyframes", "--image", "https://x/1.png").returncode, 1)
        self.assertEqual(run_cli("--dry-run", "--prompt", "p", "--width", "640").returncode, 1)


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockAgnes)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address[:2]
        cls.base_url = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        MockAgnes.poll_script = []
        MockAgnes.requests = []
        MockAgnes.create_failures = 0
        MockAgnes.primary_404 = False
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "clip.mp4"

    def tearDown(self):
        self.tmp.cleanup()

    def test_happy_path_with_transient_errors(self):
        MockAgnes.create_failures = 1  # first POST -> 503, then accepted
        MockAgnes.poll_script = [
            (503, {"error": {"message": "busy"}}),
            (200, {"status": "in_progress"}),  # simplified body without progress
            (200, {"status": "in_progress", "progress": 50}),
            (500, {"error": "hiccup"}),
            (200, "COMPLETED"),
        ]
        result = run_cli("--prompt", "a cat", "--output", str(self.out), base_url=self.base_url)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.out))
        self.assertEqual(self.out.read_bytes(), FAKE_VIDEO)

        sidecar = json.loads(self.out.with_suffix(".json").read_text())
        self.assertEqual(sidecar["final_response"]["status"], "completed")
        self.assertEqual(sidecar["request"]["num_frames"], 121)
        self.assertEqual(sidecar["file_bytes"], len(FAKE_VIDEO))
        self.assertTrue(sidecar["video_url"].endswith("/out.mp4"))

        posts = [r for r in MockAgnes.requests if r[0] == "POST"]
        self.assertEqual(len(posts), 2)  # one 503 + one success
        self.assertEqual(posts[-1][2]["prompt"], "a cat")
        polls = [r[1] for r in MockAgnes.requests if r[0] == "GET" and r[1].startswith("/agnesapi")]
        self.assertTrue(all("video_id=video_1" in p and "model_name=agnes-video-v2.0" in p for p in polls))
        self.assertIn("status=in_progress progress=50%", result.stderr)
        self.assertNotIn(API_KEY, result.stderr + result.stdout)

    def test_legacy_endpoint_fallback(self):
        MockAgnes.primary_404 = True
        MockAgnes.poll_script = [(200, {"status": "queued", "progress": 0}), (200, "COMPLETED")]
        result = run_cli("--prompt", "a dog", "--output", str(self.out), base_url=self.base_url)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("falling back to legacy", result.stderr)
        self.assertTrue(any(r[1] == "/v1/videos/task_1" for r in MockAgnes.requests))
        self.assertEqual(self.out.read_bytes(), FAKE_VIDEO)

    def test_failed_task_reports_reason(self):
        MockAgnes.poll_script = [(200, {"status": "in_progress", "progress": 10}),
                                 (200, {"status": "failed", "error": {"message": "content policy", "code": "moderation"}})]
        result = run_cli("--prompt", "x", "--output", str(self.out), base_url=self.base_url)
        self.assertEqual(result.returncode, 1)
        self.assertIn("content policy", result.stderr)
        self.assertFalse(self.out.exists())

    def test_bad_api_key_fails_fast(self):
        result = run_cli("--prompt", "x", "--output", str(self.out), base_url=self.base_url, api_key="wrong")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Authentication failed", result.stderr)
        self.assertEqual(len([r for r in MockAgnes.requests if r[0] == "POST"]), 1)  # no pointless retries

    def test_missing_api_key(self):
        result = run_cli("--prompt", "x", "--output", str(self.out), base_url=self.base_url, api_key=None)
        self.assertEqual(result.returncode, 1)
        self.assertIn("AGNES_API_KEY", result.stderr)
        self.assertEqual(MockAgnes.requests, [])

    def test_github_outputs_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = Path(tmp) / "out.txt"
            summary = Path(tmp) / "summary.md"
            env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
            env.update({"AGNES_API_KEY": API_KEY, "GITHUB_OUTPUT": str(outputs), "GITHUB_STEP_SUMMARY": str(summary)})
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--prompt", "a | pipe", "--output", str(self.out),
                 "--base-url", self.base_url, "--poll-interval", "0.02"],
                capture_output=True, text=True, timeout=60, env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"video_path={self.out}\n", outputs.read_text())
            self.assertIn("size=1280x720\n", outputs.read_text())
            self.assertIn("| Prompt | a \\| pipe |", summary.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
