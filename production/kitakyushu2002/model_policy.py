#!/usr/bin/env python3
"""本片用哪个视频模型、哪个分辨率档位 —— `generate.py` 与 `render.py` 共用的**唯一出处**。

为什么单独开一个模块，而不是让 render.py 去 import generate.py：

1. **名字会撞**：仓库里每个项目都有一个 `generate.py`（dahlia / gilgo / kitakyushu2002 / …）。
   离线测试跑起来时 `sys.path` 上先出现的是别的项目那份，实测报
   `ImportError: cannot import name 'MODEL' from 'generate' (production/dahlia/generate.py)`，
   连带把 `test_card_typography.py` 也弄红（它按文件路径加载每个项目的 render.py）。
2. **跨进程**：render.py 是被 generate.py 用 subprocess 起的另一个进程，
   去 import 一个「运行时会被 payload 覆盖的变量」本身就不成立。

所以：默认值写在这里，谁要用谁 import；`ALLOWED_MODELS` 是出片闸门认的白名单。
"""
import os

# 2026-10-10 实测（收据 production/kitakyushu2002/delivery/provider-probe.json）：
#   * agnes-video-v2.0 已被网关下线（GET /v1/models 里已无此模型）
#   * 主档 agnes-video-2.5 要余额：两把 key 都是 403「Insufficient user quota, remaining: ＄0.000000」
#   * agnes-video-2.5-flash **不吃余额**，但只认 720P（400「size must be one of 720P」）
# 本片定型走免费方案：flash + 720P，由 render.py 放大到 1920×1080 出片。
FREE_MODEL = "agnes-video-2.5-flash"
PAID_MODEL = "agnes-video-2.5"
# 2026-10-11 用户拍板：38 镜全部改走智谱免费档（仓库 jeong2000 流水线实测一轮 3–4 分钟）；
# Agnes 已出的 3 镜留作 backup_agnes_shots 备用。cogvideox-flash 是智谱免费档模型名。
COGVIDEOX_MODEL = "cogvideox-flash"

MODEL = os.environ.get("AGNES_VIDEO_MODEL", FREE_MODEL).strip() or FREE_MODEL
SIZE_TIER = os.environ.get("AGNES_VIDEO_SIZE", "720P" if MODEL == FREE_MODEL else "1080P").strip()

# 出片闸门认这三个：换档时不用改代码，但也不允许混进来一个没人审过的模型。
ALLOWED_MODELS = (FREE_MODEL, PAID_MODEL, COGVIDEOX_MODEL)

# 红线提示词（单一出处）。2026-10-11 从 generate.py 迁来：两条生成路线
# （Agnes generate.py / 智谱 generate_cogvideox.py）都必须把同一段红线附进每次
# 请求的提示词，而本模块正是为「每个项目一份同名文件会串味」而存在的共享点
# （render.py 早已从这里取 ALLOWED_MODELS）。generate.py 保留再导出，对外名称不变。
PROMPT_GUARDRAILS = ('Avoid: readable text, letters, signage or subtitles on screen; watermarks and logos; '
                     'blood, wounds, corpses or body bags; the likeness of any identifiable real person; '
                     'flat 2D cartoon or comic shading; duplicated identical faces or a face that morphs '
                     'mid-shot; morphing objects, jitter, flicker, whip pans and jump cuts.')

# 文档《Parameter Restrictions》：size 只能是档位名，传像素（1920x1080）会 400。
SUPPORTED_SIZES = ("720P", "1080P", "1K", "2K")
# mode 是必填字段，只有这三种。
SUPPORTED_MODES = ("text", "keyframe", "reference")
