#!/usr/bin/env python3
"""Generate a short video with the Agnes Video V2.0 API.

Docs: https://agnes-ai.com/en/docs/agnes-video-v20

Flow (asynchronous task API):
  1. POST {base}/v1/videos                      -> task with video_id / task_id
  2. GET  {base}/agnesapi?video_id=<VIDEO_ID>   -> poll until status == completed
     (falls back to GET {base}/v1/videos/<TASK_ID> if the first endpoint 404s)
  3. download metadata.url                      -> <output>.mp4 (+ <output>.json sidecar)

Standard library only, so it runs on a bare GitHub Actions runner without pip.
The API key is read from the AGNES_API_KEY environment variable and is never printed.

Examples:
  # text-to-video, ~5 s, 16:9 720p
  AGNES_API_KEY=... python production/agnes_video.py \
      --prompt "A cinematic shot of a cat walking on the beach at sunset" \
      --output output/cat.mp4

  # image-to-video (the image must be a publicly reachable URL)
  python production/agnes_video.py --prompt "She slowly turns and looks at the camera" \
      --image https://example.com/portrait.png --output output/turn.mp4

  # keyframe animation (2+ images: first = start frame, last = end frame)
  python production/agnes_video.py --prompt "Smooth cinematic transition between the keyframes" \
      --image https://example.com/k1.png --image https://example.com/k2.png --output output/kf.mp4

  # inspect the request without calling the API
  python production/agnes_video.py --prompt "..." --seconds 10 --aspect 9:16 --dry-run
"""
from __future__ import annotations

import argparse
import email.utils
import datetime
import http.client
import json
import os
import shutil
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

DEFAULT_BASE_URL = "https://apihub.agnes-ai.com"
DEFAULT_MODEL = "agnes-video-v2.0"
MAX_FRAMES = 441  # API limit; num_frames must also satisfy 8n + 1
USER_AGENT = "agnes-video-cli/1.0 (+https://github.com/32r4e2q-hub/desktop-tutorial)"

# Requested sizes are only hints: the API snaps them to its nearest 480p/720p/1080p
# preset and reports the real output size in `size` / `metadata.size_mapping`.
SIZE_PRESETS = {
    "16:9": {"480p": (832, 448), "720p": (1280, 720), "1080p": (1920, 1080)},
    "9:16": {"480p": (448, 832), "720p": (720, 1280), "1080p": (1080, 1920)},
    "1:1": {"480p": (480, 480), "720p": (720, 720), "1080p": (1080, 1080)},
    "4:3": {"480p": (640, 480), "720p": (960, 720), "1080p": (1440, 1080)},
    "3:4": {"480p": (480, 640), "720p": (720, 960), "1080p": (1080, 1440)},
}
COMPLETED_STATES = {"completed", "complete", "succeeded", "success", "done", "finished"}
FAILED_STATES = {"failed", "failure", "error", "cancelled", "canceled", "expired", "rejected"}


class Fatal(Exception):
    """Unrecoverable error: report and exit 1."""


class TransientError(Exception):
    """Network-level failure that is worth retrying."""


class RateLimited(Fatal):
    """A rejected request, not a created task. Preserve the server's cooldown."""
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


def parse_retry_after(value, now=None):
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (ValueError, TypeError):
        try:
            when = email.utils.parsedate_to_datetime(str(value))
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
            current = time.time() if now is None else now
            return max(0.0, when.timestamp() - current)
        except (TypeError, ValueError, OverflowError):
            return None


class HttpResult(tuple):
    """Compatible three-tuple plus optional Retry-After metadata."""
    def __new__(cls, code, body, text, retry_after=None):
        obj = super().__new__(cls, (code, body, text))
        obj.retry_after = retry_after
        return obj


def log(message: str) -> None:
    print(time.strftime("[%H:%M:%S] ") + message, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- frames / size

def snap_frames(frames: float) -> int:
    """Nearest value satisfying the 8n+1 rule, clamped to [9, MAX_FRAMES]."""
    n = max(1, int(round((frames - 1) / 8)))
    return min(8 * n + 1, MAX_FRAMES)


def frames_for_duration(seconds: float, fps: float) -> int:
    return snap_frames(seconds * fps)


def frames_type(value: str) -> int:
    frames = int(value)
    if frames < 1 or frames > MAX_FRAMES or (frames - 1) % 8:
        raise argparse.ArgumentTypeError(
            f"num_frames must be 8n+1 and <= {MAX_FRAMES} (e.g. 81, 121, 241, 441); got {frames}"
        )
    return frames


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(f"expected a positive number, got {value}")
    return number


def frame_rate_type(value: str) -> float:
    number = float(value)
    if not 1 <= number <= 60:
        raise argparse.ArgumentTypeError(f"frame_rate must be between 1 and 60, got {value}")
    return number


# --------------------------------------------------------------------------- request payload

def build_payload(args: argparse.Namespace) -> dict:
    if args.num_frames is not None:
        frames = args.num_frames
    else:
        frames = frames_for_duration(args.seconds, args.frame_rate)
        if args.seconds * args.frame_rate > MAX_FRAMES:
            log(
                f"warning: {args.seconds:g}s at {args.frame_rate:g} fps exceeds the {MAX_FRAMES}-frame "
                f"limit; using {MAX_FRAMES} frames (~{MAX_FRAMES / args.frame_rate:.1f}s)"
            )

    if args.width or args.height:
        if not (args.width and args.height):
            raise Fatal("--width and --height must be given together")
        width, height = args.width, args.height
    else:
        width, height = SIZE_PRESETS[args.aspect][args.resolution]

    fps: Any = int(args.frame_rate) if float(args.frame_rate).is_integer() else args.frame_rate
    payload: dict = {
        "model": args.model,
        "prompt": args.prompt.strip(),
        "width": width,
        "height": height,
        "num_frames": frames,
        "frame_rate": fps,
    }
    if not payload["prompt"]:
        raise Fatal("--prompt must not be empty")
    if args.negative_prompt:
        payload["negative_prompt"] = args.negative_prompt.strip()
    if args.seed is not None:
        payload["seed"] = args.seed
    if args.steps is not None:
        payload["num_inference_steps"] = args.steps

    images = [url.strip() for url in (args.image or []) if url and url.strip()]
    for url in images:
        if not url.startswith(("http://", "https://")):
            raise Fatal(f"image must be a publicly reachable http(s) URL, got: {url[:80]}")
    mode = args.mode
    if mode == "keyframes" and len(images) < 2:
        raise Fatal("--mode keyframes needs at least two --image URLs (start frame and end frame)")

    if len(images) == 1:
        payload["image"] = images[0]  # plain image-to-video
        if mode:
            payload["mode"] = mode
    elif images:
        payload["extra_body"] = {"image": images, "mode": mode or "keyframes"}
    elif mode:
        payload["mode"] = mode
    return payload


# --------------------------------------------------------------------------- HTTP helpers

def http_json(method: str, url: str, api_key: str, payload: Optional[dict] = None, timeout: float = 60):
    """Return (status_code, parsed_json_or_None, raw_text). Raises TransientError on network failure."""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json", "User-Agent": USER_AGENT}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            code, raw = response.status, response.read()
            retry_after = parse_retry_after(response.headers.get('Retry-After'))
    except urllib.error.HTTPError as exc:  # HTTP error responses still carry a useful body
        code, raw = exc.code, exc.read()
        retry_after = parse_retry_after(exc.headers.get('Retry-After')) if exc.headers else None
    except (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError, http.client.HTTPException) as exc:
        raise TransientError(f"{type(exc).__name__}: {exc}") from exc

    text = raw.decode("utf-8", "replace")
    try:
        body = json.loads(text) if text.strip() else None
    except ValueError:
        body = None
    return HttpResult(code, body, text, retry_after)


def describe_error(body: Any, text: str, code: int) -> str:
    if isinstance(body, dict):
        err = body.get("error") or body.get("detail") or body.get("message")
        if isinstance(err, dict):
            message = err.get("message") or err.get("msg") or json.dumps(err, ensure_ascii=False)
            err_code = err.get("code") or err.get("type")
            return f"{message} (code={err_code})" if err_code else str(message)
        if err:
            return str(err)
    snippet = " ".join(text.split())[:300]
    return snippet or f"HTTP {code}"


def find_video_url(body: dict) -> Optional[str]:
    candidates = []
    metadata = body.get("metadata")
    if isinstance(metadata, dict):
        candidates += [metadata.get("url"), metadata.get("video_url")]
    candidates += [body.get("url"), body.get("video_url")]
    for key in ("output", "data", "result"):
        nested = body.get(key)
        if isinstance(nested, dict):
            candidates += [nested.get("url"), nested.get("video_url")]
        elif isinstance(nested, str):
            candidates.append(nested)
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
            return candidate
    return None


# --------------------------------------------------------------------------- API calls

def create_task(base_url: str, api_key: str, payload: dict, retries: int, retry_delay: float) -> dict:
    url = f"{base_url}/v1/videos"
    delay = retry_delay
    for attempt in range(1, retries + 1):
        problem = None
        rate_limited = False
        retry_after = None
        try:
            response = http_json("POST", url, api_key, payload, timeout=120)
            code, body, text = response
            retry_after = getattr(response, 'retry_after', None)
        except TransientError as exc:
            problem = f"network error: {exc}"
        else:
            if 200 <= code < 300 and isinstance(body, dict):
                return body
            detail = describe_error(body, text, code)
            if code in (401, 403):
                raise Fatal(f"Authentication failed (HTTP {code}): {detail}. Check AGNES_API_KEY.")
            if code in (400, 404, 405, 413, 422):
                raise Fatal(f"Request rejected (HTTP {code}): {detail}")
            if code == 429 or code >= 500:
                rate_limited = code == 429
                problem = f"HTTP {code}: {detail}"
            else:
                raise Fatal(f"Unexpected response (HTTP {code}): {detail}")
        if attempt == retries:
            message = f"Could not create video task after {retries} attempts; last problem: {problem}"
            if rate_limited:
                raise RateLimited(message, retry_after)
            raise Fatal(message)
        wait = max(delay, retry_after or 0)
        log(f"create task: {problem}; retry {attempt}/{retries - 1} in {wait:g}s")
        time.sleep(wait)
        delay = min(delay * 2, 60)
    raise Fatal("Could not create video task")  # unreachable, keeps type checkers happy


def poll_task(
    base_url: str,
    api_key: str,
    model: str,
    video_id: str,
    task_id: Optional[str],
    interval: float,
    timeout: float,
    max_failures: int,
    before_request=None,
    rate_limit_callback=None,
):
    primary = f"{base_url}/agnesapi?" + urllib.parse.urlencode({"video_id": video_id, "model_name": model})
    legacy = f"{base_url}/v1/videos/{urllib.parse.quote(task_id, safe='')}" if task_id else None
    url = primary
    started = time.monotonic()
    deadline = started + timeout
    failures = 0
    last_line = None

    while True:
        sleep_delay = interval
        if before_request:
            before_request()
        try:
            response = http_json("GET", url, api_key, timeout=60)
            code, body, text = response
            if code == 429:
                sleep_delay = max(60, interval * 2, getattr(response, 'retry_after', None) or 0)
                if rate_limit_callback:
                    rate_limit_callback(sleep_delay)
        except TransientError as exc:
            failures += 1
            log(f"poll: network error ({exc}) [{failures}/{max_failures}]")
        else:
            if 200 <= code < 300 and isinstance(body, dict):
                failures = 0
                state = str(body.get("status") or "").lower()
                progress = body.get("progress")
                line = f"status={state or 'unknown'}" + (f" progress={progress}%" if progress is not None else "")
                if line != last_line:
                    log(f"{line} (elapsed {int(time.monotonic() - started)}s)")
                    last_line = line
                video_url = find_video_url(body)
                if state in COMPLETED_STATES or (not state and video_url):
                    if video_url:
                        return body, video_url
                    log("poll: status is completed but no video URL yet; waiting")
                elif state in FAILED_STATES:
                    raise Fatal(f"Video task {state}: {describe_error(body, text, code)}")
            elif code in (400, 404) and legacy:
                # Not found on this endpoint: try the other one (and count it, so a task that
                # never shows up on either endpoint still fails after max_failures).
                failures += 1
                if url == primary:
                    log(f"poll: /agnesapi returned HTTP {code}; falling back to legacy /v1/videos/<task_id>")
                    url = legacy
                else:
                    log(f"poll: legacy endpoint returned HTTP {code}; retrying /agnesapi")
                    url = primary
            elif code in (401, 403):
                raise Fatal(f"Authentication failed while polling (HTTP {code}): {describe_error(body, text, code)}")
            else:
                failures += 1
                log(f"poll: HTTP {code}: {describe_error(body, text, code)} [{failures}/{max_failures}]")

        if failures >= max_failures:
            raise Fatal(f"Gave up after {failures} consecutive polling failures (video_id={video_id})")
        if time.monotonic() >= deadline:
            raise Fatal(f"Timed out after {timeout:g}s waiting for video_id={video_id} (last: {last_line})")
        time.sleep(sleep_delay)


def download(url: str, dest: Path, retries: int, retry_delay: float) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    delay = retry_delay
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=300) as response, partial.open("wb") as handle:
                shutil.copyfileobj(response, handle, 1 << 18)
            size = partial.stat().st_size
            if size < 1024:
                raise TransientError(f"downloaded file is only {size} bytes")
            partial.replace(dest)
            return size
        except (TransientError, OSError, http.client.HTTPException) as exc:
            log(f"download attempt {attempt}/{retries} failed: {exc}")
            if attempt < retries:
                time.sleep(delay)
                delay = min(delay * 2, 60)
    raise Fatal(f"Could not download {url}")


# --------------------------------------------------------------------------- reporting

def write_sidecar(dest: Path, payload: dict, created: dict, final: dict, video_url: str, size_bytes: int) -> Path:
    sidecar = dest.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "file": str(dest),
                "file_bytes": size_bytes,
                "video_url": video_url,
                "request": payload,
                "create_response": created,
                "final_response": final,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return sidecar


def report_to_github(payload: dict, final: dict, video_url: str, dest: Path, size_bytes: int) -> None:
    size = str(final.get("size") or f"{payload['width']}x{payload['height']}")
    seconds = str(final.get("seconds") or f"{payload['num_frames'] / payload['frame_rate']:.1f}")

    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as handle:
            handle.write(f"video_url={video_url}\n")
            handle.write(f"video_path={dest}\n")
            handle.write(f"size={size}\n")
            handle.write(f"seconds={seconds}\n")

    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        prompt = " ".join(payload["prompt"].split()).replace("|", "\\|")[:500]
        mapping = (final.get("metadata") or {}).get("size_mapping") or {}
        note = mapping.get("message") or ""
        rows = [
            ("Prompt", prompt),
            ("Output", f"`{dest}` ({size_bytes / 1e6:.2f} MB)"),
            ("Size", size + (f" — {note}" if note else "")),
            ("Duration", f"{seconds} s ({payload['num_frames']} frames @ {payload['frame_rate']} fps)"),
            ("Task", str(final.get("task_id") or final.get("id") or "")),
            ("Video URL", video_url),
        ]
        with open(summary_file, "a", encoding="utf-8") as handle:
            handle.write("## Agnes video\n\n| | |\n|---|---|\n")
            for key, value in rows:
                handle.write(f"| {key} | {value} |\n")
            handle.write("\n")


# --------------------------------------------------------------------------- CLI

def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a video with the Agnes Video V2.0 API (text-to-video, image-to-video, keyframes).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    content = parser.add_argument_group("content")
    content.add_argument("--prompt", required=True, help="what should happen in the video (English is most reliable)")
    content.add_argument("--negative-prompt", default="", help="things to avoid")
    content.add_argument(
        "--image",
        action="append",
        metavar="URL",
        help="public image URL; one = image-to-video, two or more = keyframe animation (repeatable)",
    )
    content.add_argument("--mode", choices=["ti2vid", "keyframes"], help="explicit generation mode (auto by default)")
    content.add_argument("--seed", type=int, help="fixed seed for reproducible results")
    content.add_argument("--steps", type=int, help="num_inference_steps (leave unset for the API default)")

    shape = parser.add_argument_group("duration and size")
    shape.add_argument("--seconds", type=positive_float, default=5.0, help="target duration in seconds (max ~18)")
    shape.add_argument("--num-frames", type=frames_type, help="exact frame count (8n+1, <= 441); overrides --seconds")
    shape.add_argument("--frame-rate", type=frame_rate_type, default=24, help="frames per second (1-60)")
    shape.add_argument("--aspect", choices=sorted(SIZE_PRESETS), default="16:9", help="aspect ratio preset")
    shape.add_argument("--resolution", choices=["480p", "720p", "1080p"], default="720p", help="resolution tier")
    shape.add_argument("--width", type=int, help="explicit width (with --height); overrides the presets")
    shape.add_argument("--height", type=int, help="explicit height (with --width); overrides the presets")

    runtime = parser.add_argument_group("runtime")
    runtime.add_argument("--output", type=Path, default=Path("output/agnes_video.mp4"), help="where to save the MP4")
    runtime.add_argument("--model", default=DEFAULT_MODEL, help="model name")
    runtime.add_argument(
        "--base-url",
        default=os.environ.get("AGNES_BASE_URL", DEFAULT_BASE_URL),
        help="API gateway (env AGNES_BASE_URL)",
    )
    runtime.add_argument("--poll-interval", type=positive_float, default=5.0, help="seconds between status checks")
    runtime.add_argument("--timeout", type=positive_float, default=1800.0, help="max seconds to wait for the video")
    runtime.add_argument("--max-poll-failures", type=int, default=24, help="consecutive poll errors before giving up")
    runtime.add_argument("--retry-delay", type=positive_float, default=5.0, help="initial back-off for create/download retries")
    runtime.add_argument("--dry-run", action="store_true", help="print the request payload and exit without calling the API")
    return parser.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    try:
        payload = build_payload(args)
        log("request payload: " + json.dumps(payload, ensure_ascii=False))
        log(
            f"requested ~{payload['num_frames'] / payload['frame_rate']:.1f}s @ {payload['frame_rate']} fps, "
            f"{payload['width']}x{payload['height']} (the API may snap the size to its nearest preset)"
        )
        if args.dry_run:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        api_key = os.environ.get("AGNES_API_KEY", "").strip()
        if not api_key:
            raise Fatal("AGNES_API_KEY is not set (create one at https://platform.agnes-ai.com/settings/apiKeys)")
        base_url = args.base_url.rstrip("/")
        dest: Path = args.output
        if dest.suffix.lower() != ".mp4":
            dest = dest.with_suffix(".mp4")

        created = create_task(base_url, api_key, payload, retries=4, retry_delay=args.retry_delay)
        video_id = created.get("video_id") or created.get("id") or created.get("task_id")
        task_id = created.get("task_id") or created.get("id")
        if not video_id:
            raise Fatal("create response has no video_id/task_id: " + json.dumps(created, ensure_ascii=False)[:500])
        log(
            f"task created: video_id={video_id} task_id={task_id} status={created.get('status')} "
            f"size={created.get('size')} seconds={created.get('seconds')}"
        )

        final, video_url = poll_task(
            base_url,
            api_key,
            args.model,
            str(video_id),
            str(task_id) if task_id else None,
            interval=args.poll_interval,
            timeout=args.timeout,
            max_failures=args.max_poll_failures,
        )
        log(f"video ready: {video_url}")
        size_bytes = download(video_url, dest, retries=4, retry_delay=args.retry_delay)
        log(f"saved {dest} ({size_bytes / 1e6:.2f} MB)")
        sidecar = write_sidecar(dest, payload, created, final, video_url, size_bytes)
        log(f"task details written to {sidecar}")
        report_to_github(payload, final, video_url, dest, size_bytes)
        print(dest)
        return 0
    except Fatal as exc:
        log(f"error: {exc}")
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error::{exc}")
        return 1
    except KeyboardInterrupt:
        log("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
