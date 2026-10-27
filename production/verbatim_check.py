#!/usr/bin/env python3
"""成片逐字听检：把成片里的解说转写成文字，与剧本逐字比对。

为什么要有这个工具
------------------
《制作过程.md》里一直挂着一条"没做完"：**逐字听检**。静音闸门能证明"有声、电平正常、
每段都有声、没中途丢声"，但证明不了"配音念的字和剧本一字不差"——而中文 TTS 念错字、
吞字、把「二十二岁」念成「二十三岁」这类事故，恰恰是出片后才看得出来的。

仓库里已有的 ``align_audio.py`` 不能拿来当这个证据，有两个原因：

1. 它把剧本文字当 ``initial_prompt`` 喂给了模型（``initial_prompt=row['text']``）。
   用"先告诉模型答案、再让模型复述答案"来证明音频与剧本一致，是循环论证；
2. 它转写的是分段的配音 wav，不是成片。段落有没有放错位置，它管不着。

所以这个工具刻意做得更硬：

* **不给 initial_prompt**，模型没被暗示过答案；
* 转写对象是**最终成片**按章节时间切出来的音频——验的是"成片第 N 章里念的字，
  是不是剧本第 N 章的字"，顺带把"段落放错位置"也验了；
* 可选再跑一遍**干净的配音文件**（``--narration``）做对照：如果成片里字错率高、
  配音文件里很低，那是音乐/混音干扰 ASR；如果两边都高，那才是真有问题。

它报告**字错率（CER，编辑距离 / 剧本字数）**与**覆盖率**（匹配上的字占剧本字数的比例），
超阈值就要求人工听那一段，并且以非 0 退出。转写器装不上时**直接失败**，不静默通过——
静默通过正是第一版成片"没声音却出片"的病根。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import wave
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

RATE = 48000
DIGITS = "零一二三四五六七八九"
DEFAULT_MODEL = "small"
DEFAULT_MAX_CER = 0.15
DEFAULT_LANGUAGE = "zh"
PAD_SECONDS = 0.25          # 章节前后多留一点，避免把第一个字/最后一个字切掉


class VerdictError(RuntimeError):
    """转写器不可用或字错率超阈值。"""


def chinese_number(value: int) -> str:
    """把阿拉伯数字换成汉字，好跟 ASR 转出来的读法对齐（22 -> 二十二）。"""
    if value < 10:
        return DIGITS[value]
    if value < 100:
        tens, ones = divmod(value, 10)
        return ("" if tens == 1 else DIGITS[tens]) + "十" + (DIGITS[ones] if ones else "")
    return "".join(DIGITS[int(character)] for character in str(value))


def to_simplified(text: str) -> str:
    """繁体 → 简体。whisper 对普通话音频有时整段吐繁体（2026-09-21 吉尔戈 N05：頓/頭/薩/隨/進/蹤…），
    逐字比对会把每个繁简对都记成一个错字（那一章 CER 0.31 → 转简体后 0.10）。
    有 zhconv 就转，没有就原样返回——不让一个可选依赖把听检整个拖死。"""
    try:
        import zhconv  # type: ignore
    except ImportError:
        return text
    return zhconv.convert(text, "zh-cn")


def normalize(text: str) -> str:
    """只保留汉字与字母、数字转汉字、繁体转简体、统一小写：比对的是"念出来的字"，不是标点。"""
    import re

    text = to_simplified(text)
    text = re.sub(r"(\d{4})(?=年)", lambda m: "".join(DIGITS[int(c)] for c in m.group(1)), text)
    # 99.96% → 百分之九十九点九六；3.5 → 三点五（ASR 会把念出来的百分数/小数写回阿拉伯数字）
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%",
                  lambda m: "百分之" + _spoken_number(m.group(1)), text)
    text = re.sub(r"\d+\.\d+", lambda m: _spoken_number(m.group(0)), text)
    text = re.sub(r"\d+", lambda m: chinese_number(int(m.group(0))), text)
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z]", text)).lower()


def _spoken_number(token: str) -> str:
    """'99.96' → 九十九点九六；'42' → 四十二。"""
    whole, _, frac = token.partition(".")
    spoken = chinese_number(int(whole))
    if frac:
        spoken += "点" + "".join(DIGITS[int(c)] for c in frac)
    return spoken


def levenshtein(left: str, right: str) -> int:
    """编辑距离。章节文本百来个字，O(n*m) 的 DP 足够。"""
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, character in enumerate(left, start=1):
        current = [i]
        for j, other in enumerate(right, start=1):
            current.append(min(previous[j] + 1,                      # 删
                               current[j - 1] + 1,                   # 插
                               previous[j - 1] + (character != other)))  # 替
        previous = current
    return previous[-1]


def character_error_rate(expected: str, recognized: str) -> float:
    """CER = 编辑距离 / 剧本字数。0 表示逐字一致。"""
    if not expected:
        return 0.0 if not recognized else 1.0
    return round(levenshtein(expected, recognized) / len(expected), 4)


def match_coverage(expected: str, recognized: str) -> float:
    """剧本里有多少比例的字在转写结果里找到了连续匹配（与 align_audio.py 同口径）。"""
    if not expected:
        return 1.0
    matcher = SequenceMatcher(None, expected, recognized, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return round(matched / len(expected), 4)


def diff_spans(expected: str, recognized: str, limit: int = 6) -> list[dict]:
    """把不一致的地方列出来交给人看：工具说"有差异"，人要知道差在哪。"""
    spans = []
    matcher = SequenceMatcher(None, expected, recognized, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or len(spans) >= limit:
            continue
        spans.append({"at": i1, "kind": tag,
                      "script": expected[i1:i2], "heard": recognized[j1:j2]})
    return spans


def decode_audio(film: Path, work: Path) -> np.ndarray:
    """把成片解码成 48 kHz 单声道 float，区间 [-1, 1]。"""
    raw = work / "film.pcm"
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-hide_banner", "-y", "-i", str(film),
         "-ac", "1", "-ar", str(RATE), "-f", "s16le", str(raw)],
        check=True,
    )
    samples = np.frombuffer(raw.read_bytes(), dtype="<i2").astype(np.float32) / 32768.0
    raw.unlink(missing_ok=True)
    return samples


def write_wav(path: Path, samples: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(RATE)
        writer.writeframes((clipped * 32767.0).astype("<i2").tobytes())
    return path


def load_chapters(project: Path, timing: Path | None) -> list[dict]:
    """章节文本来自 story.json，时间轴来自出片时的实测报告——两者都不是猜的。"""
    story = json.loads((project / "story.json").read_text(encoding="utf-8"))
    texts = {row["id"]: row["text"] for row in story["chapters"]}

    manifest = project / "audio" / "manifest.json"
    if manifest.is_file():
        for row in json.loads(manifest.read_text(encoding="utf-8"))["clips"]:
            if texts.get(row["id"]) != row["text"]:
                raise VerdictError(f"{row['id']}: 剧本与配音清单的文字不一致，先修再听检")

    timing_path = timing
    if timing_path is None:
        for candidate in (project / "delivery" / "narration-timing.json",
                          project / "delivery" / "final-audio-report.json"):
            if candidate.is_file():
                timing_path = candidate
                break
    if timing_path is None or not timing_path.is_file():
        raise VerdictError(f"找不到章节时间轴（{project}/delivery/ 下应有 "
                           "narration-timing.json 或 final-audio-report.json）")

    rows = json.loads(timing_path.read_text(encoding="utf-8"))
    if isinstance(rows, dict):          # final-audio-report.json 的形状
        rows = rows.get("chapters", [])

    chapters = []
    for row in rows:
        cid = row["id"]
        if cid not in texts:
            continue
        chapters.append({"id": cid, "text": texts[cid],
                         "start": float(row["start"]), "end": float(row["end"])})
    if not chapters:
        raise VerdictError("时间轴里没有任何可用章节")
    return chapters


def model_cache_dir(work: Path) -> Path:
    """模型往哪儿下。默认落在本次运行的 work 里——**等于每次出片都要重下一遍**。

    自托管 runner 可以设环境变量 ``WHISPER_CACHE_DIR`` 指向一个常驻目录
    （例如 ``~/.cache/whisper``），small 模型（约 500 MB）就只下一次、之后每个 job
    直接复用。家里的网络连 Hugging Face 本来就慢，让每个 job 重下 500 MB 是纯粹的浪费，
    也最容易把出片卡在下载这一步上。
    """
    override = os.environ.get("WHISPER_CACHE_DIR")
    return Path(override) if override else work / "model-cache"


def transcribe(paths: dict[str, Path], model_size: str, language: str,
               work: Path) -> dict[str, str]:
    """转写。**刻意不给 initial_prompt**：模型不该事先知道剧本写了什么。"""
    work.mkdir(parents=True, exist_ok=True)
    cache = model_cache_dir(work)
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache))
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "15")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "90")
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:      # 装不上就明说，不许"没做检查却说通过了"
        raise VerdictError(f"faster-whisper 不可用，逐字听检没做成（不是通过）：{error}") from error

    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=4,
                         download_root=str(cache))
    transcripts: dict[str, str] = {}
    for cid, path in paths.items():
        segments, info = model.transcribe(str(path), language=language, beam_size=5,
                                          vad_filter=True)
        text = "".join(segment.text for segment in segments)
        transcripts[cid] = text
        print(f"TRANSCRIBED {cid}: {len(text)} chars / "
              f"lang={getattr(info, 'language', '?')}", flush=True)
    return transcripts


def compare(chapters: list[dict], transcripts: dict[str, str], max_cer: float) -> dict:
    rows = []
    for chapter in chapters:
        cid = chapter["id"]
        expected = normalize(chapter["text"])
        heard = normalize(transcripts.get(cid, ""))
        rate = character_error_rate(expected, heard)
        rows.append({
            "id": cid,
            "start": round(chapter["start"], 3),
            "end": round(chapter["end"], 3),
            "script_chars": len(expected),
            "heard_chars": len(heard),
            "character_error_rate": rate,
            "match_coverage": match_coverage(expected, heard),
            "verdict": "ok" if rate <= max_cer else "needs_human_listen",
            "diff": diff_spans(expected, heard),
            "transcript": transcripts.get(cid, ""),
        })
    failing = [row["id"] for row in rows if row["verdict"] != "ok"]
    return {"chapters": rows,
            "max_cer": max((row["character_error_rate"] for row in rows), default=0.0),
            "failing": failing}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--film", type=Path, required=True, help="成片路径")
    parser.add_argument("--project", type=Path, required=True, help="项目目录 production/<slug>")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--timing", type=Path, default=None, help="章节时间轴（默认自动找）")
    parser.add_argument("--narration", type=Path, default=None,
                        help="干净的配音目录；给了就顺带跑一遍对照组")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="whisper 模型，默认 small")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--max-cer", type=float, default=DEFAULT_MAX_CER,
                        help=f"字错率上限，超过就要求人工听（默认 {DEFAULT_MAX_CER}）")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args(argv)

    if not args.film.is_file():
        raise SystemExit(f"找不到成片：{args.film}")
    args.work.mkdir(parents=True, exist_ok=True)

    chapters = load_chapters(args.project, args.timing)
    print(f"DECODE {args.film}", flush=True)
    samples = decode_audio(args.film, args.work)

    film_paths: dict[str, Path] = {}
    for chapter in chapters:
        start = max(0.0, chapter["start"] - PAD_SECONDS)
        end = min(len(samples) / RATE, chapter["end"] + PAD_SECONDS)
        film_paths[chapter["id"]] = write_wav(
            args.work / f"{chapter['id']}-film.wav",
            samples[int(start * RATE):int(end * RATE)],
        )
    print(f"SLICES {len(film_paths)} 段，开始转写（模型 {args.model}，不给提示词）", flush=True)
    film_result = compare(chapters, transcribe(film_paths, args.model, args.language,
                                               args.work), args.max_cer)

    control = None
    if args.narration:
        control_paths = {}
        for chapter in chapters:
            for suffix in (".wav", ".mp3"):
                candidate = args.narration / f"{chapter['id']}{suffix}"
                if candidate.is_file():
                    control_paths[chapter["id"]] = candidate
                    break
        if control_paths:
            control = compare(chapters, transcribe(control_paths, args.model, args.language,
                                                   args.work), args.max_cer)

    digest = hashlib.sha256()
    with args.film.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    report = {
        "film": args.film.name,
        # 报告自带成片 SHA-256：换片后一眼能看出这份听检是不是对应该版本。
        "film_sha256": digest.hexdigest(),
        "film_bytes": args.film.stat().st_size,
        "project": str(args.project),
        "method": f"faster-whisper {args.model}，无 initial_prompt；转写对象为最终成片按章节切出的音频",
        "max_cer_allowed": args.max_cer,
        "film_pass": film_result,
        "narration_control": control,
        "note": ("CER = 编辑距离 / 剧本字数。ASR 本身也会错，所以 'needs_human_listen' 的意思是"
                 "\"这一段的差异需要人耳裁决\"，不等于\"配音一定错了\"；"
                 "对照组（干净配音）字错率明显低于成片时，差异多半来自音乐干扰 ASR。"),
    }
    out = args.report or args.work / "verbatim-check.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"听检结果：{out}")
    for row in film_result["chapters"]:
        control_row = None
        if control:
            control_row = next((r for r in control["chapters"] if r["id"] == row["id"]), None)
        extra = f"，对照组 CER {control_row['character_error_rate']}" if control_row else ""
        print(f"    {row['id']}  CER {row['character_error_rate']:.3f} / "
              f"覆盖率 {row['match_coverage']:.2f} / {row['verdict']}{extra}")
    print(f"  最大字错率 {film_result['max_cer']:.3f}（上限 {args.max_cer}）")
    if film_result["failing"]:
        print("  需人工听：" + "、".join(film_result["failing"]), flush=True)
        return 1
    print("  六段全部落在字错率上限内")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
