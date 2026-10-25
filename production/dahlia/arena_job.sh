#!/usr/bin/env bash
# The real render job. Invoked by .github/workflows/arena-runner.yml.
#
# Everything lives in this script (not in the workflow file) so the pipeline can
# be changed and re-run without touching .github/workflows again: this GitHub
# authorization cannot write workflow files, but it can write this script.
set -euo pipefail

BRANCH="arena/01a085be-desktop-tutorial"
FILM="work/dahlia/黑色大丽花_三分钟_带声音.mp4"
DELIVERY="交付/黑色大丽花_三分钟_带声音.mp4"

echo "=== 1/6 install media tools and fonts ==="
sudo apt-get update -qq
sudo apt-get install -y -qq ffmpeg fonts-noto-cjk
ffmpeg -hide_banner -version | head -1

echo "=== 2/6 install python dependencies ==="
# Ubuntu 24.04 marks the system Python as externally managed, so plain pip
# installs can be refused; fall back to --break-system-packages on this
# disposable runner rather than failing the whole render.
DEPS=("pillow>=10,<13" "numpy>=1.26,<3" "faster-whisper>=1.1,<2")
python3 -m pip install --upgrade pip || true
if ! python3 -m pip install --quiet "${DEPS[@]}"; then
  python3 -m pip install --quiet --break-system-packages "${DEPS[@]}"
fi
python3 -c "import PIL, numpy; print('deps ok', numpy.__version__)"

echo "=== 3/6 validate the plan and narration provenance ==="
python3 production/dahlia/generate.py --validate

echo "=== 4/6 restore the verified Agnes footage (no regeneration) ==="
python3 -u production/dahlia/fetch_sources.py --dest work/dahlia/clips

echo "=== 5/6 render the cut with measured audio ==="
python3 -u production/dahlia/render.py \
  --sources work/dahlia/clips \
  --work work/dahlia \
  --output "$FILM"

echo "=== 6/6 publish the film and the measured reports back to the branch ==="
mkdir -p 交付 production/dahlia/delivery
cp "$FILM" "$DELIVERY"
for f in technical-report.json audio-report.json final-audio-report.json \
         alignment-report.json caption-timing.json narration-timing.json \
         edit-decision-list.json final-contact.jpg captions.srt; do
  [ -f "work/dahlia/$f" ] && cp "work/dahlia/$f" production/dahlia/delivery/ || echo "skip $f"
done

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -f "$DELIVERY" production/dahlia/delivery
if git diff --cached --quiet; then
  echo "No changes to publish"
else
  git commit -m "Deliver the three-minute cut with measured audio"
  git push origin "HEAD:$BRANCH"
  echo "PUBLISHED_COMMIT $(git rev-parse HEAD)"
fi

echo "=== summary ==="
ls -la "$DELIVERY"
python3 - <<'PY'
import json
from pathlib import Path
for name in ("production/dahlia/delivery/final-audio-report.json",
             "production/dahlia/delivery/technical-report.json"):
    path = Path(name)
    if not path.exists():
        continue
    data = json.loads(path.read_text())
    print(name, "->", json.dumps(
        {k: data.get(k) for k in ("duration", "audio_codec", "sample_rate",
                                  "audio_channels", "rms_dbfs", "peak_dbfs",
                                  "silent_fraction", "bytes")},
        ensure_ascii=False))
PY
echo "JOB_DONE"
