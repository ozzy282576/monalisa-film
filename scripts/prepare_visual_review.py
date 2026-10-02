"""Extract real video evidence; never mark visual QA as passed automatically."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'review' / 'evidence'
TMP = ROOT / 'work' / 'dense-frames'
OUT.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)


def extract(args):
    path, second, dest = args
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(second),'-i',str(path),
                    '-frames:v','1',str(dest)], check=True)


report = []
for i in range(1,16):
    sid = f'{i:02}'
    clip = ROOT / 'clips' / f'{sid}.mp4'
    data = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams',
                      '-show_format','-of','json',str(clip)]))
    times = [round(.25 + j*.5,2) for j in range(24)]
    paths = [TMP/f'{sid}-{j:02}.png' for j in range(24)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(extract, [(clip,t,p) for t,p in zip(times,paths)]))
    for half in range(2):
        sheet = Image.new('RGB',(1920,1584),'#171717')
        draw = ImageDraw.Draw(sheet)
        for slot in range(12):
            j = half*12+slot
            with Image.open(paths[j]) as im:
                im.thumbnail((640,360))
                x=(slot%3)*640
                y=(slot//3)*396
                sheet.paste(im,(x,y+32))
                draw.text((x+8,y+4),f'CLIP {sid} | requested t={times[j]:05.2f}s',font=font,fill='white')
        sheet.save(OUT/f'{sid}-{half+1}.jpg',quality=93)
    source_qc = ROOT / 'work' / f'qc-{sid}.json'
    report.append({'id':sid,'sha256':hashlib.sha256(clip.read_bytes()).hexdigest(),
       'bytes':clip.stat().st_size,'probe':data,'sample_times':times,
       'machine_report':json.loads(source_qc.read_text()) if source_qc.exists() else None,
       'visual_review':'pending','scope':'24 accurately sought samples; not an exhaustive frame-by-frame review'})
    print(f'::notice title=Evidence {sid}::24 full-shot samples prepared; visual review pending.')
(OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
