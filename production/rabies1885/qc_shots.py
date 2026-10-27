#!/usr/bin/env python3
"""镜头自动检验：把「看起来有没有问题」变成能复查的数字。

用法（需要 qc 环境里的 cv2 / mediapipe）::

    work/rabies1885/qc-env/bin/python production/rabies1885/qc_shots.py

Agnes 生成的镜头只回传接触表（``qa/Sxx.jpg``，4×4 网格、每秒 2 帧、共 14 帧），
媒体文件本身不进仓库。所以本脚本就在这 14 格上做检验，跑一遍约 20 秒/镜：

=========  ============================================================
检验项     判定
=========  ============================================================
黑帧       任一格亮度 < 12（画面整个黑掉）
冻结       相邻格差异 < 0.4 的占比 ≥ 50%（镜头是静止的，Agnes 镜头不该静止）
中途换场   相邻格差异 > 5 倍中位差异（一镜之内场景跳变，AI 典型事故）
露脸       BlazeFace 检出置信度 ≥ 0.75 且框宽 > 6%；多格持续出现或 ≥ 0.9 才算硬伤（单格转 WARN，并把区域裁到 qa/faces/ 给人眼看）
手         MediaPipe Hands 检出——手是 AI 最容易畸变的部位，检出即需人眼确认
手存疑     肤色占比高但检测器认不出手（可能畸变，需人眼确认）
风格跑偏   亮度 / 反差 / 色温 / 颗粒 偏离参考片实测值（参考 ``style_lab`` 的量）
=========  ============================================================

前三项是硬伤（FAIL），后面几项是需要人眼的 WARN——脚本不替人下结论，
它只把该看的东西挑出来，38 个镜头缩到几个。

产出 ``qc.json``（机器读）与 ``qc-report.md``（人读）。
参考片基准来自 ``production/style_lab/runs/20261004-073904-monalisa_180_web/reference_metrics.json``。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
QA = HERE / "qa"
GRID = (4, 4)                      # 接触表网格：4 列 × 4 行
SAMPLE_FPS = 2                     # 与 media.py 的 fps=2 一致
REFERENCE = ROOT / "production/style_lab/runs/20261004-073904-monalisa_180_web/reference_metrics.json"

# 参考片实测值（style_lab 量出来的），允许偏离的倍率
# 三条基准线都是「同一管线」量出来的（2 fps / 384×216 / JPEG q3 的接触表），所以能直接比：
#   参考片 monalisa_180_web：亮度 85–97 · 反差 55–82 · 色温 +15~+33 · 颗粒 10–13 · 运动 17–29
#   已出片吉尔戈 38 镜    ：亮度中位 84（23–146）· 反差 44 · 颗粒 8.2 · 运动 16.4
#   已出片黑色大丽花 24 镜：亮度中位 56（23–76） · 反差 47 · 颗粒 5.3 · 运动 16.3
# 颗粒对尺度敏感（缩小就把高频抹平了），所以不能拿 style_lab 在全分辨率上量到的 13.21 直接比，
# 必须让参考片走一遍同样的 ffmpeg 管线——上面三行就是这么量出来的。
BANDS = {
    # 指标         警戒下限  警戒上限  硬伤下限  硬伤上限
    "brightness": (45.0, 125.0, 30.0, 160.0),   # 低于 30 = 画面基本是黑的
    "contrast":   (30.0, 90.0, 18.0, 120.0),    # 低于 18 = 画面被压平
    "warmth":     (8.0, 45.0, -5.0, 70.0),
    "grain":      (4.5, 20.0, 2.0, 30.0),
    "motion":     (7.0, 45.0, 2.5, 60.0),       # 低于 2.5 = 镜头是静止的
}
LABEL = {"brightness": "亮度", "contrast": "反差", "warmth": "色温",
         "grain": "颗粒", "motion": "运动"}
BLACK_LEVEL = 12.0                 # 单帧亮度低于此值 = 黑帧
FREEZE_DIFF = 0.4                  # 相邻帧差异低于此值 = 没动
CUT_FACTOR = 5.0                   # 超过中位差异的这么多倍 = 中途换场


def tiles(sheet: Path):
    """把接触表切成 16 格；丢掉没内容的格子（7 秒 × 2 fps = 14 帧，最后两格是空的）。"""
    img = cv2.imread(str(sheet))
    if img is None:
        return []
    h, w = img.shape[:2]
    tw, th = w // GRID[0], h // GRID[1]
    out = []
    for row in range(GRID[1]):
        for col in range(GRID[0]):
            tile = img[row*th:(row+1)*th, col*tw:(col+1)*tw]
            if float(tile.mean()) > 1.5:                     # 空网格是全黑
                out.append(tile)
    return out


def metrics(tile):
    gray = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY).astype(np.float32)
    b, g, r = (tile[:, :, i].astype(np.float32) for i in range(3))
    blur = cv2.blur(gray, (3, 3))
    # 肤色占比：YCbCr 经验区间（用来判断「人物皮肤大面积出现」）
    ycc = cv2.cvtColor(tile, cv2.COLOR_BGR2YCrCb)
    skin = ((ycc[:, :, 1] > 133) & (ycc[:, :, 1] < 173) &
            (ycc[:, :, 2] > 77) & (ycc[:, :, 2] < 127) &
            (ycc[:, :, 0] > 60)).mean()
    return {
        "brightness": float(gray.mean()),
        "contrast": float(gray.std()),
        "warmth": float(r.mean() - b.mean()),
        "grain": float((gray - blur).std()),
        "skin_ratio": float(skin),
        "gray": gray,
    }


def detect(tile, face_detector, hand_detector, face_cascade):
    """人脸（BlazeFace + Haar 交叉验证）与手（MediaPipe Hands）。"""
    rgb = cv2.cvtColor(tile, cv2.COLOR_BGR2RGB)
    h, w = tile.shape[:2]
    faces = []
    result = face_detector.process(rgb)
    if result.detections:
        for det in result.detections:
            box = det.location_data.relative_bounding_box
            faces.append({"score": float(det.score[0]), "width": float(box.width),
                          "height": float(box.height),
                          "x": float(box.xmin), "y": float(box.ymin)})
    haar = []
    gray = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
    for (_, _, bw, _) in face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(18, 18)):
        haar.append(float(bw) / w)
    hands = []
    hand_result = hand_detector.process(rgb)
    if hand_result.multi_hand_landmarks:
        for lm in hand_result.multi_hand_landmarks:
            pts = np.array([[p.x, p.y] for p in lm.landmark])
            # 手掌宽高比 + 食指/中指长度比：粗略判断手型有没有长歪
            palm_w = np.linalg.norm(pts[5] - pts[17])
            palm_h = np.linalg.norm(pts[0] - pts[9])
            index = np.linalg.norm(pts[5] - pts[8])
            middle = np.linalg.norm(pts[9] - pts[12])
            hands.append({"palm_aspect": float(palm_w / max(palm_h, 1e-6)),
                          "index_middle": float(index / max(middle, 1e-6))})
    return faces, haar, hands


def crop_faces(sid, frames, faces, out=None):
    """把疑似人脸的区域裁出来，供人眼复核（检测器会误报，裁剪图才是证据）。"""
    out = out or (QA / "faces")
    out.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in faces:
        tile = frames[f.get("tile", 0)]
        h, w = tile.shape[:2]
        x0 = max(int(f["x"] * w) - 6, 0); y0 = max(int(f["y"] * h) - 6, 0)
        x1 = min(int((f["x"] + f["width"]) * w) + 6, w)
        y1 = min(int((f["y"] + f["height"]) * h) + 6, h)
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        crop = cv2.resize(tile[y0:y1, x0:x1], (160, 160))
        dest = out / f"{sid}-t{f.get('tile', 0):02d}-{f['score']:.2f}.jpg"
        cv2.imwrite(str(dest), crop, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        saved.append(str(dest))
    return saved


def motion(a, b):
    return float(np.abs(a["gray"] - b["gray"]).mean())


def analyse(sid: str, sheet: Path, detectors):
    frames = tiles(sheet)
    if not frames:
        return {"shot": sid, "verdict": "FAIL", "reasons": ["接触表是空的或读不出来"],
                "frames": 0}
    face_detector, hand_detector, face_cascade = detectors
    stats = [metrics(t) for t in frames]
    faces_all, haar_all, hands_all = [], [], []
    for idx, tile in enumerate(frames):
        f, hha, hs = detect(tile, face_detector, hand_detector, face_cascade)
        for face in f:
            face["tile"] = idx
        faces_all += f
        haar_all += hha
        hands_all += hs
    diffs = [motion(stats[i], stats[i+1]) for i in range(len(stats)-1)]
    med = float(np.median(diffs)) if diffs else 0.0

    brightness = float(np.mean([s["brightness"] for s in stats]))
    contrast = float(np.mean([s["contrast"] for s in stats]))
    warmth = float(np.mean([s["warmth"] for s in stats]))
    grain = float(np.mean([s["grain"] for s in stats]))
    skin = float(max(s["skin_ratio"] for s in stats))
    darkest = float(min(s["brightness"] for s in stats))

    reasons, warnings = [], []
    # —— 硬伤 ——
    if darkest < BLACK_LEVEL:
        reasons.append(f"黑帧：最暗一格亮度 {darkest:.1f}")
    frozen = [d for d in diffs if d < FREEZE_DIFF]
    if diffs and len(frozen) / len(diffs) >= 0.5:
        reasons.append(f"镜头几乎静止：{len(frozen)}/{len(diffs)} 个相邻帧差异 < {FREEZE_DIFF}")
    if diffs and med > 0:
        spikes = [d for d in diffs if d > CUT_FACTOR * med]
        if spikes:
            reasons.append(f"疑似中途换场：{len(spikes)} 处跳变（最大 {max(diffs):.1f} vs 中位 {med:.1f}）")
    # 阈值是校准出来的：按 0.6/3% 判，S01（画面里只有一条狗的剪影、没有任何人）也报了 6 格，
    # 全是误报。改成 0.75/6%，并要求「多格持续出现」或「0.9 以上」才判 FAIL，单格转 WARN。
    sure = [f for f in faces_all if f["score"] >= 0.75 and f["width"] >= 0.06]
    strong = [f for f in sure if f["score"] >= 0.9]
    if len(sure) >= 3 or strong:
        reasons.append(f"检出正脸：{len(sure)} 格（最高置信度 {max(f['score'] for f in sure):.2f}，"
                       f"最大框宽 {max(f['width'] for f in sure)*100:.0f}%）")
        crop_faces(sid, frames, [f for f in faces_all if f["score"] >= 0.6])
    elif sure:
        warnings.append(f"疑似正脸：{len(sure)} 格（最高 {max(f['score'] for f in sure):.2f}）——"
                        f"已裁到 qa/faces/，需人眼确认")
        crop_faces(sid, frames, [f for f in faces_all if f["score"] >= 0.6])
    # —— 需要人眼 ——
    if hands_all:
        warnings.append(f"画面里有手（{len(hands_all)} 处检出）：手指是 AI 最容易畸变的部位，需人眼确认")
    # 暖调画面里这个数会虚高（木墙、琥珀灯光都落在肤色区间），所以阈值定在 0.5，只做提示
    if skin > 0.5 and not hands_all and not sure:
        warnings.append(f"肤色占比 {skin*100:.0f}% 但没检出手或脸：暖调画面这个数会偏高，仅供参考")
    if haar_all and not sure:
        warnings.append(f"Haar 级联在 {len(haar_all)} 格里像人脸（BlazeFace 未确认）：可能是侧脸或雕像，需人眼确认")
    for key, value in (("brightness", brightness), ("contrast", contrast),
                       ("warmth", warmth), ("grain", grain), ("motion", med)):
        warn_lo, warn_hi, fail_lo, fail_hi = BANDS[key]
        if not (fail_lo <= value <= fail_hi):
            reasons.append(f"{LABEL[key]}越过硬线：{value:.1f}（硬线 {fail_lo}–{fail_hi}）")
        elif not (warn_lo <= value <= warn_hi):
            warnings.append(f"{LABEL[key]}在警戒区外：{value:.1f}（正常 {warn_lo}–{warn_hi}）")

    verdict = "FAIL" if reasons else ("WARN" if warnings else "PASS")
    return {
        "shot": sid, "verdict": verdict, "reasons": reasons, "warnings": warnings,
        "frames": len(frames),
        "brightness": round(brightness, 1), "contrast": round(contrast, 1),
        "warmth": round(warmth, 1), "grain": round(grain, 2),
        "motion_median": round(med, 2), "motion_max": round(max(diffs), 2) if diffs else 0.0,
        "skin_ratio": round(skin, 3),
        "faces": len(faces_all), "faces_sure": len(sure),
        "haar_hits": len(haar_all), "hands": len(hands_all),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="*", help="只检验这几个镜头，例如 --only S03 S07")
    args = parser.parse_args()

    sheets = sorted(QA.glob("S*.jpg"))
    if args.only:
        sheets = [p for p in sheets if p.stem in set(args.only)]
    if not sheets:
        print("qa/ 里还没有接触表"); return 1

    face_detector = mp.solutions.face_detection.FaceDetection(
        model_selection=1, min_detection_confidence=0.4)
    hand_detector = mp.solutions.hands.Hands(
        static_image_mode=True, max_num_hands=2, min_detection_confidence=0.4)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    story = json.loads((HERE / "story.json").read_text(encoding="utf-8"))
    purposes = {s["id"]: s.get("purpose", "") for s in story["shots"]}
    results = {}
    with face_detector, hand_detector:
        for sheet in sheets:
            sid = sheet.stem
            record = analyse(sid, sheet, (face_detector, hand_detector, face_cascade))
            record["purpose"] = purposes.get(sid, "")
            results[sid] = record
            print(f"{sid} {record['verdict']:4s} 亮度 {record.get('brightness',0):5.1f} "
                  f"反差 {record.get('contrast',0):5.1f} 色温 {record.get('warmth',0):5.1f} "
                  f"颗粒 {record.get('grain',0):5.2f} 运动 {record.get('motion_median',0):5.2f} "
                  f"| {'; '.join(record['reasons'] + record['warnings'])[:90]}")

    (HERE / "qc.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")

    lines = ["# 镜头自动检验", "",
             "同管线基准（2 fps / 384×216 接触表）：参考片 亮度 85–97 · 反差 55–82 · 色温 +15~+33 · "
             "颗粒 10–13 · 运动 17–29；已出片狂犬病 亮度中位 61 · 反差 40 · 颗粒 6.4 · 运动 18.2；"
             "吉尔戈 亮度中位 84 · 反差 44；黑色大丽花 亮度中位 56 · 反差 47。",
             "",
             "| 镜头 | 判定 | 亮度 | 反差 | 色温 | 颗粒 | 运动中位 | 人脸 | 手 | 说明 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for sid, r in results.items():
        notes = "; ".join(r["reasons"] + r["warnings"]) or "—"
        lines.append(f"| {sid} | **{r['verdict']}** | {r.get('brightness','—')} | "
                     f"{r.get('contrast','—')} | {r.get('warmth','—')} | {r.get('grain','—')} | "
                     f"{r.get('motion_median','—')} | {r.get('faces_sure','—')} | {r.get('hands','—')} | {notes} |")
    fails = [s for s, r in results.items() if r["verdict"] == "FAIL"]
    warns = [s for s, r in results.items() if r["verdict"] == "WARN"]
    lines += ["", f"共 {len(results)} 镜：PASS {len(results)-len(fails)-len(warns)} · "
                  f"WARN {len(warns)} · FAIL {len(fails)}", ""]
    if fails:
        lines.append("**要重做**：" + "、".join(fails))
    if warns:
        lines.append("**要人眼确认**：" + "、".join(warns))
    lines += ["", "判定口径写在 `qc_shots.py` 的模块说明里；脚本只挑出该看的，不替人下结论。"]
    (HERE / "qc-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n已写 qc.json 与 qc-report.md：FAIL {len(fails)} · WARN {len(warns)} · "
          f"PASS {len(results)-len(fails)-len(warns)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
