#!/usr/bin/env bash
# 本项目专用出片器：视频/图片/音频二进制只留在 work 与 Actions artifact，不提交进 Git。
set -euo pipefail

HERE="production/chessboard64"
WORK="work/chessboard64"
BRANCH="arena/56672981-monalisa-film"
SKIP_ASR="${1:-false}"
FILM_NAME="${2:-六十四格_国际象棋盘杀手_三分钟_带声音.mp4}"
OUT="$WORK/$FILM_NAME"

mkdir -p "$WORK" "$HERE/delivery"
echo "=== 六十四格 / branch=$BRANCH / output=$OUT ==="

# 只校验完整计划，不调用付费路线；片段与旁白均按收据从外部存储按需恢复。
python3 "$HERE/generate_cogvideox.py" --validate
python3 -u "$HERE/fetch_sources.py" --dest "$WORK/clips"
python3 -u "$HERE/fetch_audio.py" --dest "$HERE/audio"

# 确保字幕与切点来自当前脚本对应的真实停顿表；切点偏离时 fail closed。
if [ ! -f "$HERE/audio/clause-times.json" ]; then
  echo "缺少 audio/clause-times.json；先用收紧后的真实旁白跑 clause_times.py 与 plan_cuts.py。" >&2
  exit 1
fi
python3 "$HERE/clause_times.py" --check-cuts

EXTRA=()
[ "$SKIP_ASR" = "true" ] && EXTRA+=("--skip-asr")
python3 -u "$HERE/render.py" \
  --sources "$WORK/clips" --work "$WORK/render" --output "$OUT" \
  --project "$HERE/story.json" --results "$HERE/results.json" --audio "$HERE/audio" \
  "${EXTRA[@]}"

# 只把文本报告与字幕放进 Git；任何 MP4/JPG/PNG/MP3 都只保留在 work / artifact。
python3 - "$OUT" "$WORK/render" "$HERE/delivery" <<'PY'
import hashlib, json, os, shutil, sys
from pathlib import Path
film, work, delivery = map(Path, sys.argv[1:])
delivery.mkdir(parents=True, exist_ok=True)
allowed = {
    'technical-report.json', 'audio-report.json', 'final-audio-report.json',
    'alignment-report.json', 'caption-timing.json', 'narration-timing.json',
    'edit-decision-list.json', 'captions.srt', 'mix-report.json',
}
for name in allowed:
    src = work / name
    if src.is_file():
        shutil.copyfile(src, delivery / name)
sha = hashlib.sha256(film.read_bytes()).hexdigest()
tech_path = work / 'technical-report.json'
tech = json.loads(tech_path.read_text()) if tech_path.exists() else {}
manifest = {
    'project': 'chessboard64',
    'film_name': film.name,
    'sha256': sha,
    'bytes': film.stat().st_size,
    'media_storage': 'GitHub Actions artifact only; never committed to Git',
    'artifact_name': 'chessboard64-film-' + os.environ.get('GITHUB_RUN_ID', 'local'),
    'technical_report': tech,
}
(delivery / 'render-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print('RENDER_MANIFEST', json.dumps({k: manifest[k] for k in ('film_name','sha256','bytes')}, ensure_ascii=False))
PY

# Text-only delivery receipts are useful for audit; this allowlist deliberately excludes all media.
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
REPORTS=()
for name in render-manifest.json technical-report.json audio-report.json final-audio-report.json \
            alignment-report.json caption-timing.json narration-timing.json edit-decision-list.json captions.srt; do
  [ -f "$HERE/delivery/$name" ] && REPORTS+=("$HERE/delivery/$name")
done
if [ "${#REPORTS[@]}" -gt 0 ]; then git add -f "${REPORTS[@]}"; fi
if ! git diff --cached --quiet; then
  git commit -m "chessboard64: publish text-only render receipts"
  git push origin "HEAD:$BRANCH"
fi

echo "JOB_DONE $OUT"
