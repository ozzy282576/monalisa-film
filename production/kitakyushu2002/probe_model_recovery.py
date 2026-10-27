#!/usr/bin/env python3
"""目标模型（默认 ``agnes-video-v2.0``）是否恢复的专用探针。

背景（2026-10-10/11 实测）：v2.0 在 10-10 06:03Z 被网关下线（503「No available
channel」），免费流量被迫挤进 2.5-flash 的抽签排队（23 抽 1 中、76 抽 0 中都见过）。
v2.0 健康时整片 5–15 分钟跑完——所以「它恢复了吗」值得定期一问。

三样测量，全部写进收据 ``delivery/model-recovery-probe.json``：

1. ``GET /v1/models``：目标模型在不在网关清单里（不花额度）；
2. 用 **v2.0 老形状**（width/height/num_frames/frame_rate，当年 dahlia 出片的形状）创建一次；
3. 用**现在免费档形状**（size/mode/seconds/aspect_ratio）创建一次。

判读：
- 503「no available channel」= 仍下线；
- 400 = 通道活着、只是形状不对 → **已恢复**（模型在路由、在做字段校验）；
- 2xx = 完全恢复（会真建一个任务，探针只花这一单的额度，可接受）。

400/503 不建任务、不花额度；两次创建之间隔 ≥80 秒（免费额度约 1 次/分钟）。
沙箱连不上 Agnes API，本脚本只在 GitHub Actions runner 上跑。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "production"))
sys.path.insert(0, str(HERE))

import agnes_video as agnes  # noqa: E402

RECEIPT = HERE / "delivery" / "model-recovery-probe.json"
REQUEST = HERE / "PROBE_REQUEST"
GAP_SECONDS = float(os.environ.get("AGNES_PROBE_GAP", "80"))
DEFAULT_TARGET = "agnes-video-v2.0"
PROBE_PROMPT = ("A quiet rural road between rice fields at dusk, slow camera push-in, "
                "soft light, no people, no text.")


def legacy_payload(model: str) -> dict:
    """v2.0 当年出片的请求形状（见 production/agnes_video.py::build_payload）。"""
    return {"model": model, "prompt": PROBE_PROMPT, "width": 1280, "height": 720,
            "num_frames": 120, "frame_rate": 24}


def current_payload(model: str) -> dict:
    """现在免费档（2.5 系列）验证过的形状。"""
    return {"model": model, "prompt": PROBE_PROMPT, "seconds": "5", "size": "720P",
            "aspect_ratio": "16:9", "mode": "text", "n": 1, "seed": 7}


def target_model() -> str:
    model = os.environ.get("AGNES_VIDEO_MODEL", "").strip()
    if model:
        return model
    if REQUEST.is_file():
        try:
            model = str(json.loads(REQUEST.read_text(encoding="utf-8")).get("model", "")).strip()
        except Exception:
            model = ""
    return model or DEFAULT_TARGET


def main() -> int:
    key = os.environ.get("AGNES_API_KEY", "").strip()
    base = os.environ.get("AGNES_BASE_URL", agnes.DEFAULT_BASE_URL).rstrip("/")
    model = target_model()
    receipt = {"model": model, "base": base,
               "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "api_key_present": bool(key), "listed": None, "attempts": []}

    try:  # 1) 网关清单，不花额度
        code, body, text = agnes.http_json("GET", base + "/v1/models", key, timeout=30)
        ids = [str(x.get("id")) for x in (body or {}).get("data", [])
               if isinstance(x, dict) and x.get("id")] if isinstance(body, dict) else []
        receipt.update(listed_http_status=code, listed=model in ids,
                       model_count=len(ids), models=ids[:40])
        print("PROBE_LISTED %s -> HTTP %s listed=%s" % (model, code, model in ids), flush=True)
    except Exception as exc:
        receipt["listed_error"] = str(exc)[:300]

    if key:
        for shape, body in (("legacy_v2_shape", legacy_payload(model)),
                            ("current_free_shape", current_payload(model))):
            entry = {"shape": shape, "fields": sorted(body)}
            try:
                code, rbody, text = agnes.http_json(
                    "POST", base + "/v1/videos", key, body, timeout=120)
            except Exception as exc:
                code, rbody, text = None, None, "%s: %s" % (type(exc).__name__, exc)
            entry.update(http_status=code,
                         body_excerpt=" ".join(str(text or "").split())[:600])
            if isinstance(rbody, dict):
                entry["video_id"] = rbody.get("video_id") or rbody.get("id")
            receipt["attempts"].append(entry)
            print("PROBE_CREATE %s -> HTTP %s: %s" % (shape, code, entry["body_excerpt"][:200]),
                  flush=True)
            time.sleep(GAP_SECONDS)

    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print("PROBE_RECEIPT " + str(RECEIPT.relative_to(ROOT)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
