#!/usr/bin/env python3
"""露脸模式的角色脸一致性工具：静态闸门 + 画面闸门。

为什么要有这个工具
------------------
从《雨夜屠夫林过云》起，出片规则变了：**可以露脸**。但用户同时定了三条铁律——

1. **每个人物一张不同的脸**：不能所有角色都长成同一张 AI 脸；
2. **同一个人物跨镜头必须是同一张脸**：这一镜是他、下一镜还得是他；
3. 三条都要能被检查，不是"尽量"。

AI 视频模型没有人物记忆：换个镜头重写提示词，脸就漂了；把两个角色的描述写得
相近，观众立刻分不清谁是谁。本工具把这件事拆成两道可执行的闸门：

* ``check-prompts``（**静态闸门**，不需要模型，秒级）
  读 ``production/<slug>/cast.json`` 与 ``story.json``：
  - 每个角色的"面容 token"必须**逐字节**出现在它出现的每一个镜头提示词里；
  - 同一角色的 token 只有一个来源，天然保证跨镜头一致；
  - 不同角色的 token 必须不同，且不能"只改几个字"（防复制粘贴导致撞脸）；
  - 声明要露脸却查不到 token、或者某镜头偷偷带上了别角色的 token，都算错。

* ``check-frames``（**画面闸门**，需要成片 + 人检测器）
  按 EDL（``delivery/edit-decision-list.json``，缺失时退回 ``story.json`` 计划时间）
  逐镜抽帧、检脸、裁脸，产出：
  - 每个角色一张**人脸接触表**（人眼判决用）；
  - 同角色跨镜头相似度（低于阈值 → "可能换脸了"）；
  - 跨角色相似度（高于阈值 → "可能撞脸了"）；
  - ``delivery/face-cast-report.json``（机器只是分诊，最终由人签字）。

用法
----
    # 1) 开新项目后先生成角色谱骨架
    python3 production/face_cast.py init --project production/ripper1888

    # 2) 生成素材之前跑静态闸门（几毫秒）
    python3 production/face_cast.py check-prompts --project production/ripper1888

    # 3) 出片之后跑画面闸门（在 runner 上跑，沙箱没装 mediapipe 时自动退到 OpenCV）
    python3 production/face_cast.py check-frames --project production/ripper1888 \\
        --film "交付/xxx.mp4" --out production/ripper1888/delivery

    # 4) 只处理某几个角色 / 限制镜头数（快速抽查）
    python3 production/face_cast.py check-frames --project production/ripper1888 \\
        --film "交付/xxx.mp4" --characters C1 --limit 6

退出码：``0`` = 通过（可能有 warning），``1`` = 有 error，``2`` = 用法/文件错误。

定妆照与图生视频
----------------
``agnes_video.py`` 支持 ``--image``（图生视频）与 ``--seed``。推荐路线：

1. 用一张**定妆照**（本项目 ``cast/<角色>.png``，最好由 Agnes 生成后人工挑一张）
   作为该角色所有镜头的 ``--image`` 参考；
2. 每个角色的所有镜头**复用同一个 seed**；
3. 提示词里内嵌 cast.json 里那条面容 token（本工具会检查做到没做到）；
4. 定妆照要能被 Agnes 取到：把文件提交进公开仓库，用
   ``https://raw.githubusercontent.com/<owner>/<repo>/<branch>/production/<slug>/cast/<角色>.png``
   作为 ``--image`` 的 URL（写进 cast.json 的 ``portrait_url`` 字段，本工具会核对格式）。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent          # production/
ROOT = HERE.parent                              # repo root

MODES = ("face", "silhouette")
ROLE_HINTS = ("suspect", "victim", "witness", "police", "reporter", "narrator", "other")
MIN_FACE_TOKEN_CHARS = 24          # 低于这个长度基本不可能描述清楚一张脸
GOOD_FACE_TOKEN_CHARS = 60         # 建议长度
URL_PREFIXES = ("https://",)

# 画面闸门的两个阈值（都只是"分诊"，不是判决）
WITHIN_CHAR_WARN = 0.45            # 同角色跨镜头相似度低于它 → 提示可能换脸
ACROSS_CHAR_WARN = 0.80            # 不同角色相似度高于它 → 提示可能撞脸


# --------------------------------------------------------------------------- 基础读写

def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def project_paths(project: Path) -> tuple[Path, Path, Path]:
    return project / "story.json", project / "cast.json", project / "delivery"


def agnes_shots(story: dict) -> dict[str, dict]:
    return {shot["id"]: shot for shot in story.get("shots", []) if shot.get("kind") == "agnes"}


def _token_bigrams(text: str) -> set[str]:
    cleaned = re.sub(r"[\s，。、,.]+", "", text)
    return {cleaned[i:i + 2] for i in range(max(0, len(cleaned) - 1))}


def token_similarity(left: str, right: str) -> float:
    """两段面容 token 的字符二元组 Jaccard 相似度（0–1，越高越像）。"""
    a, b = _token_bigrams(left), _token_bigrams(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# --------------------------------------------------------------------------- 静态闸门

def check_prompts(project: Path) -> dict:
    """检查 cast.json 与 story.json 的一致性；返回可写盘的报告 dict。"""
    story_file, cast_file, _ = project_paths(project)
    errors: list[str] = []
    warnings: list[str] = []
    report: dict = {
        "gate": "check-prompts",
        "project": str(project),
        "errors": errors,
        "warnings": warnings,
        "characters": [],
        "face_shots": [],
    }

    if not story_file.is_file():
        errors.append(f"缺 {story_file}：静态闸门需要分镜表才能对照提示词")
        report["status"] = "FAIL"
        return report
    story = load_json(story_file)
    shots = agnes_shots(story)

    if not cast_file.is_file():
        errors.append(
            f"缺 {cast_file}：露脸模式必须写角色谱（mode=face）。"
            "先跑 python3 production/face_cast.py init --project <项目目录>")
        report["status"] = "FAIL"
        return report

    cast = load_json(cast_file)
    mode = cast.get("mode", "silhouette")
    report["mode"] = mode
    if mode not in MODES:
        errors.append(f"cast.json 的 mode 只能是 {'/'.join(MODES)}，现在是 {mode!r}")
        mode = "silhouette"

    characters = cast.get("characters") or []
    by_id: dict[str, dict] = {}
    for index, character in enumerate(characters, start=1):
        cid = str(character.get("id") or f"#{index}")
        if cid in by_id:
            errors.append(f"角色 id 重复：{cid}")
            continue
        by_id[cid] = character
        face = (character.get("face") or "").strip()
        name = (character.get("name") or "").strip()
        if not name:
            errors.append(f"角色 {cid} 缺 name")
        if not face:
            errors.append(f"角色 {cid} 缺 face（面容 token）")
        else:
            if len(face) < MIN_FACE_TOKEN_CHARS:
                errors.append(
                    f"角色 {cid} 的 face token 只有 {len(face)} 字（<{MIN_FACE_TOKEN_CHARS}）："
                    "描述不够细，模型每次都会画成另一张脸")
            elif len(face) < GOOD_FACE_TOKEN_CHARS:
                warnings.append(
                    f"角色 {cid} 的 face token 偏短（{len(face)} 字），建议 ≥{GOOD_FACE_TOKEN_CHARS} 字："
                    "脸型/眉眼/鼻口/发型/年龄各写一句")
        role = character.get("role")
        if role and role not in ROLE_HINTS:
            warnings.append(f"角色 {cid} 的 role={role!r} 不在建议清单 {ROLE_HINTS} 里（只是提示）")
        portrait = character.get("portrait")
        if portrait:
            portrait_path = (project / portrait) if not Path(portrait).is_absolute() else Path(portrait)
            if not portrait_path.is_file():
                warnings.append(f"角色 {cid} 声明了定妆照 {portrait}，但文件不存在（图生视频会取不到参考）")
        portrait_url = character.get("portrait_url")
        if portrait_url and not str(portrait_url).startswith(URL_PREFIXES):
            errors.append(f"角色 {cid} 的 portrait_url 必须是公开 https 地址（Agnes 只在服务器侧取图）")

    # 面容 token 必须彼此不同：同脸 = 撞脸
    ids = [cid for cid in by_id]
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            lface = (by_id[left].get("face") or "").strip()
            rface = (by_id[right].get("face") or "").strip()
            if not lface or not rface:
                continue
            if lface == rface:
                errors.append(f"角色 {left} 与 {right} 的 face token 完全相同：两个人的脸会一模一样")
            else:
                similarity = token_similarity(lface, rface)
                if similarity >= 0.9:
                    errors.append(
                        f"角色 {left} 与 {right} 的 face token 相似度 {similarity:.2f}（≥0.90）："
                        "疑似复制粘贴改几个字，人物会撞脸")
                elif similarity >= 0.75:
                    warnings.append(
                        f"角色 {left} 与 {right} 的 face token 相似度 {similarity:.2f}，"
                        "建议把脸型/五官/年龄差异再拉大一点")

    shots_map = cast.get("shots") or {}
    if mode == "silhouette" and shots_map:
        errors.append("mode=silhouette（不露脸）却写了 shots 映射：要么改 mode=face，要么删掉映射")
    if mode == "face" and not shots_map:
        warnings.append("mode=face 但 shots 是空的：本片没有任何镜头声明露脸")

    for shot_id, declared in sorted(shots_map.items()):
        declared_ids = [str(x) for x in (declared or [])]
        if shot_id not in shots:
            errors.append(f"cast.json 声明了镜头 {shot_id}，但 story.json 里没有这个 Agnes 镜头")
            continue
        if not declared_ids:
            errors.append(f"镜头 {shot_id} 的声明是空列表：删掉它，或写上角色 id")
            continue
        prompt = shots[shot_id].get("prompt", "")
        for cid in declared_ids:
            character = by_id.get(cid)
            if character is None:
                errors.append(f"镜头 {shot_id} 引用了不存在的角色 {cid}")
                continue
            face = (character.get("face") or "").strip()
            if face and face not in prompt:
                errors.append(
                    f"镜头 {shot_id} 的提示词里没有角色 {cid} 的 face token（必须逐字节照抄）："
                    "跨镜头同一张脸靠的就是这段文字")
            # 不许夹带别角色的 token
            for other in ids:
                if other == cid:
                    continue
                other_face = (by_id[other].get("face") or "").strip()
                if other_face and other_face in prompt:
                    errors.append(
                        f"镜头 {shot_id} 声明的是 {cid}，但提示词里出现了角色 {other} 的 face token："
                        "镜头里会莫名多出另一张脸")
        report["face_shots"].append({
            "shot": shot_id,
            "characters": declared_ids,
            "prompt_chars": len(prompt),
        })

    # 反向检查：没声明的镜头里混进了 token
    declared_shots = set(shots_map)
    for shot_id, shot in sorted(shots.items()):
        if shot_id in declared_shots:
            continue
        prompt = shot.get("prompt", "")
        for cid in ids:
            face = (by_id[cid].get("face") or "").strip()
            if face and face in prompt:
                warnings.append(
                    f"镜头 {shot_id} 的提示词带了角色 {cid} 的 face token，但没在 cast.json 里声明："
                    "要么补声明，要么删掉（露脸镜头必须登记）")

    for cid in ids:
        character = by_id[cid]
        report["characters"].append({
            "id": cid,
            "name": character.get("name"),
            "role": character.get("role"),
            "face_token_chars": len((character.get("face") or "").strip()),
            "portrait": character.get("portrait"),
            "portrait_url": character.get("portrait_url"),
            "seed": character.get("seed"),
        })

    report["status"] = "FAIL" if errors else "PASS"
    return report


# --------------------------------------------------------------------------- 画面闸门

def _shot_windows(project: Path, story: dict) -> dict[str, tuple[float, float]]:
    """每个 Agnes 镜头的成片时间窗（秒）：优先用真实 EDL，缺失时退回计划时间。"""
    fps = float(story.get("fps") or 30)
    edl_file = project / "delivery" / "edit-decision-list.json"
    windows: dict[str, tuple[float, float]] = {}
    if edl_file.is_file():
        edl = load_json(edl_file)
        if isinstance(edl, list):
            for segment in edl:
                if str(segment.get("kind")) != "agnes" or "start_frame" not in segment:
                    continue
                windows[str(segment["id"])] = (
                    float(segment["start_frame"]) / fps,
                    float(segment["end_frame"]) / fps,
                )
    if windows:
        return windows
    for shot in story.get("shots", []):
        if shot.get("kind") != "agnes":
            continue
        start = float(shot.get("start") or 0)
        duration = float(shot.get("duration") or 4)
        windows[shot["id"]] = (start, start + duration)
    return windows


def _make_detector() -> tuple[str | None, object | None, list[str]]:
    """优先 mediapipe（与全帧审计同一套）；沙箱里没装时退到 OpenCV Haar。

    返回 ``(检测器名, 检测器, 失败原因列表)``——两个都没有时把原因写进报告，
    不许静默降级（本仓库的规矩：能力缺失要如实标注）。
    """
    reasons: list[str] = []
    try:
        import mediapipe as mp  # type: ignore
        detector = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
        return "mediapipe", detector, reasons
    except Exception as exc:                     # noqa: BLE001 - 缺依赖是预期情况
        reasons.append(f"mediapipe 不可用（{type(exc).__name__}: {exc}）")
    try:
        import cv2  # type: ignore
        if not hasattr(cv2, "CascadeClassifier"):
            reasons.append("OpenCV 这个构建没有 CascadeClassifier（opencv-python-headless 精简版没有；"
                           "装 mediapipe，或换成完整版 opencv-python）")
        else:
            cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(str(cascade_path))
            if not detector.empty():
                return "opencv-haar", detector, reasons
            reasons.append(f"OpenCV 缺少 Haar 模型文件（{cascade_path}）")
    except Exception as exc:                     # noqa: BLE001
        reasons.append(f"OpenCV 不可用（{type(exc).__name__}: {exc}）")
    return None, None, reasons


def _detect_faces(kind: str, detector, image_path: Path) -> list[tuple[int, int, int, int, float]]:
    """返回 [(x, y, w, h, score)]（像素坐标）。"""
    import numpy as np  # local import：只有画面闸门才需要
    from PIL import Image

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        array = np.asarray(rgb)
    if kind == "mediapipe":
        result = detector.process(array)
        boxes = []
        for detection in (result.detections or []):
            box = detection.location_data.relative_bounding_box
            x = max(0, int(box.xmin * width))
            y = max(0, int(box.ymin * height))
            w = min(width - x, int(box.width * width))
            h = min(height - y, int(box.height * height))
            if w > 0 and h > 0:
                boxes.append((x, y, w, h, float(detection.score[0] if detection.score else 0.0)))
        return boxes
    if kind == "opencv-haar":
        import cv2  # type: ignore
        gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
        found = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(48, 48))
        return [(int(x), int(y), int(w), int(h), 1.0) for (x, y, w, h) in found]
    return []


def _face_descriptor(image_path: Path, box: tuple[int, int, int, int], size: int = 64):
    """把人脸裁出来缩成 64×64 灰度并去均值（余弦相似度只用这一小段）。"""
    import numpy as np
    from PIL import Image

    x, y, w, h = box
    with Image.open(image_path) as image:
        crop = image.convert("L").crop((x, y, x + w, y + h)).resize((size, size))
        vector = np.asarray(crop, dtype="float32").reshape(-1)
    vector -= vector.mean()
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def _cosine(left, right) -> float:
    return float(max(-1.0, min(1.0, float(left @ right))))


def _grab_frame(film: Path, seconds: float, out_path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    command = [ffmpeg, "-v", "error", "-ss", f"{seconds:.3f}", "-i", str(film),
               "-frames:v", "1", "-q:v", "3", str(out_path), "-y"]
    done = subprocess.run(command, capture_output=True)
    return done.returncode == 0 and out_path.is_file()


def _contact_sheet(crops: list[tuple[str, Path]], out_path: Path, columns: int = 4, cell: int = 260) -> None:
    from PIL import Image, ImageDraw

    if not crops:
        return
    import math as _math
    rows = _math.ceil(len(crops) / columns)
    sheet = Image.new("RGB", (columns * cell, rows * cell), (12, 14, 18))
    draw = ImageDraw.Draw(sheet)
    for index, (label, path) in enumerate(crops):
        column, row = index % columns, index // columns
        with Image.open(path) as image:
            thumb = image.convert("RGB")
            thumb.thumbnail((cell - 12, cell - 34))
            sheet.paste(thumb, (column * cell + 6, row * cell + 6))
        draw.text((column * cell + 8, row * cell + cell - 26), label[:28], fill=(220, 220, 220))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=88)


def check_frames(project: Path, film: Path, out_dir: Path, samples: int = 3,
                 only: list[str] | None = None, limit: int | None = None) -> dict:
    """逐镜抽帧、检脸、裁脸、算相似度；产出接触表与报告。"""
    story_file, cast_file, _ = project_paths(project)
    errors: list[str] = []
    warnings: list[str] = []
    report: dict = {
        "gate": "check-frames",
        "project": str(project),
        "film": str(film),
        "errors": errors,
        "warnings": warnings,
        "characters": {},
        "cross_character": [],
        "shots": [],
        "human_review": "pending",
    }
    if not cast_file.is_file():
        errors.append(f"缺 {cast_file}：先跑 check-prompts 的准备工作（face_cast.py init）")
        report["status"] = "FAIL"
        return report
    cast = load_json(cast_file)
    if cast.get("mode", "silhouette") != "face":
        report["status"] = "SKIP"
        report["note"] = "cast.json 的 mode 不是 face（本片不露脸），画面闸门无事可做"
        return report
    if not film.is_file():
        errors.append(f"找不到成片 {film}")
        report["status"] = "FAIL"
        return report

    story = load_json(story_file)
    shots = agnes_shots(story)
    windows = _shot_windows(project, story)
    by_id = {str(c["id"]): c for c in cast.get("characters") or []}
    shots_map = {str(k): [str(x) for x in v] for k, v in (cast.get("shots") or {}).items()}
    if only:
        shots_map = {k: v for k, v in shots_map.items() if any(c in only for c in v)}
    if limit:
        shots_map = dict(list(sorted(shots_map.items()))[:limit])

    kind, detector, reasons = _make_detector()
    report["detector"] = kind or "none"
    if reasons:
        report["detector_reasons"] = reasons
    if detector is None:
        warnings.append("没有人脸检测器：只出中间帧接触表，不做相似度分诊。原因："
                        + "；".join(reasons or ["未知"]))
    if not shutil.which("ffmpeg"):
        errors.append("找不到 ffmpeg：画面闸门需要它抽帧")
        report["status"] = "FAIL"
        return report

    work = out_dir / "face-cast"
    work.mkdir(parents=True, exist_ok=True)
    crops_by_character: dict[str, list[tuple[str, Path]]] = {cid: [] for cid in by_id}
    descriptors: dict[str, list[tuple[str, object]]] = {cid: [] for cid in by_id}

    with tempfile.TemporaryDirectory(prefix="face-cast-") as tmp:
        tmpdir = Path(tmp)
        for shot_id, declared in sorted(shots_map.items()):
            if shot_id not in windows:
                errors.append(f"镜头 {shot_id} 没有时间窗（story.json 与 EDL 里都查不到）")
                continue
            start, end = windows[shot_id]
            duration = max(0.2, end - start)
            stamps = [start + duration * (i + 1) / (samples + 1) for i in range(samples)]
            shot_entry = {"shot": shot_id, "characters": declared, "frames": []}
            for index, stamp in enumerate(stamps):
                frame_path = tmpdir / f"{shot_id}-{index}.jpg"
                if not _grab_frame(film, stamp, frame_path):
                    errors.append(f"抽帧失败：{shot_id} @ {stamp:.2f}s")
                    continue
                boxes = _detect_faces(kind, detector, frame_path) if detector is not None else []
                if not boxes:
                    shot_entry["frames"].append({"seconds": round(stamp, 3), "faces": 0})
                    continue
                boxes.sort(key=lambda box: box[2] * box[3], reverse=True)
                x, y, w, h, score = boxes[0]
                shot_entry["frames"].append({
                    "seconds": round(stamp, 3), "faces": len(boxes), "score": round(score, 3),
                    "bbox": [x, y, w, h],
                })
                for cid in declared:
                    if cid not in by_id:
                        continue
                    crop_path = work / cid / f"{shot_id}-{index}.jpg"
                    crop_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        from PIL import Image
                        with Image.open(frame_path) as image:
                            image.crop((x, y, x + w, y + h)).save(crop_path, quality=90)
                    except Exception as exc:      # pragma: no cover - 只防裁图意外
                        warnings.append(f"裁脸失败 {shot_id}#{index}：{exc}")
                        continue
                    crops_by_character.setdefault(cid, []).append((f"{shot_id}#{index}", crop_path))
                    if detector is not None:
                        descriptors.setdefault(cid, []).append(
                            (f"{shot_id}#{index}", _face_descriptor(frame_path, (x, y, w, h))))
            if not declared:
                continue
            declared_faces = [f for f in shot_entry["frames"] if f.get("faces")]
            if not declared_faces:
                warnings.append(
                    f"镜头 {shot_id} 声明了 {','.join(declared)} 要露脸，但抽帧里没检到人脸："
                    "要么构图没露出来，要么检测器在暗光/侧脸下失效——请人工看一眼")
            report["shots"].append(shot_entry)

    for cid, crops in crops_by_character.items():
        if not crops:
            continue
        _contact_sheet(crops, work / f"{cid}.jpg")
        rows = descriptors.get(cid, [])
        entry = {
            "contact_sheet": str((work / f"{cid}.jpg").relative_to(out_dir.parent)),
            "crops": len(crops),
            "shots": sorted({label.split('#')[0] for label, _ in crops}),
        }
        if len(rows) >= 2:
            scores = [_cosine(rows[i][1], rows[j][1])
                      for i in range(len(rows)) for j in range(i + 1, len(rows))]
            scores.sort()
            entry["within_min"] = round(scores[0], 3)
            entry["within_median"] = round(scores[len(scores) // 2], 3)
            if scores[0] < WITHIN_CHAR_WARN:
                warnings.append(
                    f"角色 {cid} 跨镜头最低相似度 {scores[0]:.2f}（<{WITHIN_CHAR_WARN}）："
                    "可能出现了换脸，请对照接触表人工确认")
        report["characters"][cid] = entry

    ids = [cid for cid in by_id if descriptors.get(cid)]
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            best = None
            for _, lvec in descriptors[left]:
                for _, rvec in descriptors[right]:
                    score = _cosine(lvec, rvec)
                    best = score if best is None else max(best, score)
            if best is None:
                continue
            report["cross_character"].append({"pair": [left, right], "max_similarity": round(best, 3)})
            if best > ACROSS_CHAR_WARN:
                warnings.append(
                    f"角色 {left} 与 {right} 的跨角色最高相似度 {best:.2f}（>{ACROSS_CHAR_WARN}）："
                    "可能撞脸，观众会分不清，请对照两张接触表确认")

    report["status"] = "FAIL" if errors else "REVIEW"
    report["note"] = ("机器只做分诊：相似度对光照/角度很敏感，最终必须人眼看每个角色的接触表，"
                      "确认「同一个人跨镜头还是他、不同角色一眼能分辨」。")
    return report


# --------------------------------------------------------------------------- init

CAST_SKELETON = {
    "mode": "face",
    "_comment": ("露脸模式规则：① 每个角色一条不同的 face token（≥60 字，逐字节复用）；"
                 "② 同一角色的所有镜头都照抄它；③ 不同角色的 token 不许雷同。"
                 "改完跑：python3 production/face_cast.py check-prompts --project <本项目>"),
    "characters": [
        {
            "id": "C1",
            "name": "「角色名」",
            "role": "suspect",
            "age": 0,
            "gender": "male",
            "face": ("（把这张脸写死，逐字复用；建议 60 字以上：年龄+脸型+眉眼+鼻口+发型+肤色）"),
            "portrait": "cast/C1.png",
            "portrait_url": "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/production/<slug>/cast/C1.png",
            "seed": 0,
        }
    ],
    "shots": {},
}


def cmd_init(project: Path, force: bool) -> int:
    cast_file = project / "cast.json"
    if cast_file.exists() and not force:
        print(f"已存在 {cast_file}（要覆盖加 --force）")
        return 0
    project.mkdir(parents=True, exist_ok=True)
    cast_file.write_text(json.dumps(CAST_SKELETON, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (project / "cast").mkdir(exist_ok=True)
    (project / "cast" / ".gitkeep").write_text("", encoding="utf-8")
    print(f"已写 {cast_file}（mode=face 骨架）与 {project}/cast/（放定妆照）")
    return 0


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="露脸模式：角色脸一致性闸门")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="生成 cast.json 骨架")
    init_parser.add_argument("--project", type=Path, required=True)
    init_parser.add_argument("--force", action="store_true")

    prompts_parser = sub.add_parser("check-prompts", help="静态闸门：token 一致性（不需要模型）")
    prompts_parser.add_argument("--project", type=Path, required=True)
    prompts_parser.add_argument("--report", type=Path, default=None)

    frames_parser = sub.add_parser("check-frames", help="画面闸门：抽帧检脸 + 接触表 + 相似度分诊")
    frames_parser.add_argument("--project", type=Path, required=True)
    frames_parser.add_argument("--film", type=Path, required=True)
    frames_parser.add_argument("--out", type=Path, default=None, help="默认 <project>/delivery")
    frames_parser.add_argument("--samples", type=int, default=3, help="每镜抽几帧（默认 3）")
    frames_parser.add_argument("--characters", default=None, help="只查这些角色，逗号分隔")
    frames_parser.add_argument("--limit", type=int, default=None, help="只查前 N 个露脸镜头")

    args = parser.parse_args(argv)

    if args.command == "init":
        return cmd_init(args.project, args.force)

    if args.command == "check-prompts":
        report = check_prompts(args.project)
        out = args.report or (args.project / "delivery" / "face-cast-prompts.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for line in report["errors"]:
            print(f"ERROR  {line}")
        for line in report["warnings"]:
            print(f"WARN   {line}")
        print(f"静态闸门：{report['status']}（角色 {len(report['characters'])} 个 · "
              f"露脸镜头 {len(report['face_shots'])} 个）→ {out}")
        return 0 if report["status"] == "PASS" else 1

    if args.command == "check-frames":
        out_dir = args.out or (args.project / "delivery")
        only = [x.strip() for x in args.characters.split(",")] if args.characters else None
        report = check_frames(args.project, args.film, out_dir, samples=args.samples,
                              only=only, limit=args.limit)
        out = out_dir / "face-cast-report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for line in report.get("errors", []):
            print(f"ERROR  {line}")
        for line in report.get("warnings", []):
            print(f"WARN   {line}")
        print(f"画面闸门：{report['status']}（检测器 {report.get('detector')}）→ {out}")
        return 0 if report["status"] in ("REVIEW", "SKIP") else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
