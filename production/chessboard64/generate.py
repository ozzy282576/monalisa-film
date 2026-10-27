#!/usr/bin/env python3
"""本项目的兼容入口：所有生成只走智谱 CogVideoX-Flash 免费档。

仓库的共享渲染器、素材恢复器与进度页按惯例从 ``generate.py`` 导入 ``request_hash``；
本文件只把这些调用转接到唯一生产引擎 ``generate_cogvideox.py``，不再包含或启动 Agnes/付费路线。

用法：
  python3 production/chessboard64/generate.py --validate
  python3 production/chessboard64/generate.py --publish --payload '{}'
"""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from generate_cogvideox import MODEL, full_payload, main, request_hash, validate  # noqa: E402,F401

if __name__ == "__main__":
    raise SystemExit(main())
