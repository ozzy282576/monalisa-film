#!/usr/bin/env python3
"""问出后继视频模型的 payload 形状：先抄文档，再试候选，把证据写回分支。

为什么需要它（2026-10-10 实测）：`agnes-video-v2.0` 被网关下线后换用 `agnes-video-2.5`，
创建请求立刻报

    HTTP 400: width is a forbidden field

共享实现 `production/agnes_video.py::build_payload()` 总是把 `width` / `height` 填进 payload
（由 aspect + resolution 换算而来），而新模型不收这两个字段。沙箱连不上 Agnes API，
只能在 runner 上试；而供应商的校验一次只报**一个**字段，一个个试要一轮 Actions 才掉一层皮：

    第 1 轮：width 被拒 → 换 size，报 num_frames 被拒；resolution 不是允许字段
    第 2 轮：negative_prompt 不是允许字段；duration/seconds 传小数会让它
             「Failed to read request body」（invalid_json），根本走不到字段校验

所以本脚本先做**不花额度**的一步：抓 agnes-ai.com 的文档页，把请求体字段的原文摘回来；
再按「最可能是对的」顺序试候选形状。400 不创建任务、不花额度；
一旦某个候选返回 2xx 就停下（形状对了，任务留给正式生成那一轮去建）。

    AGNES_API_KEY=... python3 production/kitakyushu2002/probe_payload_schema.py

输出 `production/kitakyushu2002/delivery/payload-schema-probe.json`：
`winner` 是 `generate.py::full_payload()` 该用的形状，`docs` 是文档原文摘录。
"""
from __future__ import annotations

import html as html_module
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "production"))
sys.path.insert(0, str(HERE))

import agnes_video as agnes  # noqa: E402
import generate  # noqa: E402

RECEIPT = HERE / "delivery" / "payload-schema-probe.json"
# 免费额度约 1 次/分钟：第一轮探针用 8 秒间隔连发，第三发就撞上
# 「You've reached the API rate limit for free users」，后面 6 个候选全被 429 挡住、
# 一个答案都没问到。间隔必须按分钟算。
GAP_SECONDS = float(os.environ.get("AGNES_PROBE_GAP", "80"))
DOCS_START = os.environ.get("AGNES_DOCS_URL", "https://agnes-ai.com/en/docs")
BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
FIELD_WORDS = ("negative_prompt", "aspect_ratio", "frame_rate", "num_frames", "resolution",
               "duration", "seconds", "size", "width", "height", "image", "seed", "prompt",
               "model", "forbidden", "allowed", "request field", "parameter", "request body",
               "seconds", "fps", "1080", "720")


def fetch(url: str, api_key: str | None = None, timeout: float = 30.0):
    """抓一个页面/端点，返回 (status, text)。抓不到也不抛——探针不能因为一个 404 就整轮丢掉。"""
    headers = {"User-Agent": BROWSER_UA, "Accept": "text/html,application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", html_module.unescape(text))


def relevant_lines(text: str, limit: int = 140) -> list:
    """只留提到请求字段的行：整页 HTML 塞进收据会把仓库撑大，也把有用的句子淹掉。"""
    kept = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if 3 < len(line) < 300 and any(word in line.lower() for word in FIELD_WORDS):
            if line not in kept:
                kept.append(line)
        if len(kept) >= limit:
            break
    return kept


def probe_docs(base_url: str, model: str, api_key: str) -> dict:
    """不花额度的一步：把供应商文档里关于请求体字段的原文摘回来。"""
    out: dict = {"start": DOCS_START, "pages": [], "endpoints": []}
    status, body = fetch(DOCS_START)
    out["start_status"] = status
    links: list = []
    if status == 200:
        links = sorted({href for href in re.findall(r'href="([^"]+)"', body)
                        if "docs" in href and "video" in href.lower()})
        out["video_links"] = links[:25]
        out["index_relevant"] = relevant_lines(strip_html(body), 60)
    else:
        out["start_error"] = body[:300]
    for href in links[:4]:
        url = href if href.startswith("http") else "https://agnes-ai.com" + href
        page_status, text = fetch(url)
        page = {"url": url, "http_status": page_status}
        if page_status == 200:
            page["relevant"] = relevant_lines(strip_html(text))
        else:
            page["error"] = " ".join(text.split())[:300]
        out["pages"].append(page)
        print(f"PROBE_DOC {url} -> {page_status} ({len(page.get('relevant', []))} lines)", flush=True)
    # 网关自己也可能吐模型元数据 / OpenAPI
    for path in (f"/v1/models/{model}", "/openapi.json", "/v1/videos/schema", "/docs"):
        endpoint_status, text = fetch(base_url + path, api_key=api_key)
        entry = {"url": base_url + path, "http_status": endpoint_status}
        if endpoint_status == 200:
            entry["excerpt"] = " ".join(text.split())[:2000]
        else:
            entry["excerpt"] = " ".join(text.split())[:300]
        out["endpoints"].append(entry)
        print(f"PROBE_ENDPOINT {path} -> {endpoint_status}", flush=True)
    return out


def candidates(base: dict) -> dict:
    """按「最可能是对的」排序；键名就是要写回 generate.py 的形状名。

    第三轮已经从官方文档（收据 docs 段）拿到了权威答案，`generate.py::full_payload()`
    现在直接按文档拼：seconds 是字符串、size 是档位、mode 必填、露脸镜头用 keyframe+first_frame。
    这里保留几个「文档没写死、只能实测」的变体，万一某个字段仍被拒可以马上定位：
    第一个候选就是 generate.py 当前真实在用的形状。
    """
    current = dict(base)
    variants = {"as_implemented": current}
    first_frame = current.get("first_frame")
    if current.get("mode") == "keyframe" and first_frame:
        # 文档说 keyframe 保首/尾帧、reference 只当风格/内容参考；露脸镜头要的是前者，
        # 这里备一个 reference 变体，万一 keyframe 被拒还有退路。
        variants["reference_mode"] = {**{k: v for k, v in current.items() if k != "first_frame"},
                                      "mode": "reference", "images": [first_frame]}
    variants["no_seed"] = {k: v for k, v in current.items() if k != "seed"}
    variants["no_n"] = {k: v for k, v in current.items() if k != "n"}
    variants["tier_720p"] = {**current, "size": "720P"}
    variants["seconds_5"] = {**current, "seconds": "5"}
    return variants


def main() -> int:
    key = os.environ.get("AGNES_API_KEY", "").strip()
    base_url = os.environ.get("AGNES_BASE_URL", agnes.DEFAULT_BASE_URL).rstrip("/")
    project = json.loads((HERE / "story.json").read_text(encoding="utf-8"))
    model = os.environ.get("AGNES_VIDEO_MODEL", generate.MODEL).strip() or generate.MODEL
    shot = next(s for s in project["shots"] if s["id"] == os.environ.get("PROBE_SHOT", "S01"))
    payload = generate.full_payload(project, shot)
    payload["model"] = model

    receipt = {"model": model, "base": base_url, "shot": shot["id"],
               "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "api_key_present": bool(key), "attempts": [], "winner": None}
    receipt["docs"] = probe_docs(base_url, model, key or None)

    if not key:
        receipt["error"] = "AGNES_API_KEY is unavailable"
    else:
        for name, body in candidates(payload).items():
            entry = {"shape": name, "fields": sorted(body),
                     "payload": {k: v for k, v in body.items() if k != "prompt"}}
            try:
                code, response_body, text = agnes.http_json(
                    "POST", base_url + "/v1/videos", key, body, timeout=120)
            except Exception as exc:  # 网络层失败也要记下来
                code, response_body, text = None, None, f"{type(exc).__name__}: {exc}"
            entry.update(http_status=code, body_excerpt=" ".join(str(text or "").split())[:1500])
            if isinstance(response_body, dict):
                entry["video_id"] = response_body.get("video_id") or response_body.get("id")
                entry["task_id"] = response_body.get("task_id")
            if code == 429:
                # 429 是限流，不是「这个形状不行」：等一个间隔原地重试一次。
                print(f"PROBE_RATE_LIMITED {name}; waiting {GAP_SECONDS:g}s then retrying once",
                      flush=True)
                time.sleep(GAP_SECONDS)
                entry["retried"] = True
                try:
                    code, response_body, text = agnes.http_json(
                        "POST", base_url + "/v1/videos", key, body, timeout=120)
                except Exception as exc:
                    code, response_body, text = None, None, f"{type(exc).__name__}: {exc}"
                entry.update(http_status=code, body_excerpt=" ".join(str(text or "").split())[:1500])
            receipt["attempts"].append(entry)
            print(f"PROBE_SHAPE {name} -> HTTP {code}: {entry['body_excerpt'][:200]}", flush=True)
            if code is not None and 200 <= code < 300:
                receipt["winner"] = name
                print(f"PROBE_WINNER {name}", flush=True)
                break
            time.sleep(GAP_SECONDS)

    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PROBE_RECEIPT " + str(RECEIPT.relative_to(ROOT)))
    return 0 if receipt["winner"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
