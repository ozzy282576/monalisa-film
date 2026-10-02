"""Consecutive frames at native 24fps in named risk intervals. No generation/API calls."""
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/details-v1'
OUT.mkdir(parents=True,exist_ok=True)
TMP=ROOT/'work/detail-frames'
TMP.mkdir(parents=True,exist_ok=True)
plan=json.loads((ROOT/'review/detail-plan.json').read_text())
originals={i['id']:i for i in json.loads((ROOT/'review/evidence/manifest.json').read_text())}
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
manifest=[]
for item in plan['clips']:
    sid=item['id']; clip=ROOT/'clips'/f'{sid}.mp4'
    digest=hashlib.sha256(clip.read_bytes()).hexdigest()
    if digest!=originals[sid]['sha256']:
        raise SystemExit('Source hash mismatch: '+sid)
    p=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-of','json',str(clip)]))
    v=p['streams'][0]
    if v['avg_frame_rate']!='24/1':
        raise SystemExit('Unexpected native FPS')
    count=round(item['seconds']*24)
    x,y,w,h=item['crop']
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(item['start']),'-i',str(clip),
        '-vf',f'crop={w}:{h}:{x}:{y}','-frames:v',str(count),'-fps_mode','passthrough',
        str(TMP/f'{sid}-%03d.png')],check=True)
    for page in range((count+11)//12):
        sheet=Image.new('RGB',(1440,1568),'#171717');draw=ImageDraw.Draw(sheet)
        for slot in range(12):
            n=page*12+slot
            if n>=count:break
            im=Image.open(TMP/f'{sid}-{n+1:03}.png').convert('RGB')
            im.thumbnail((480,360))
            px=(slot%3)*480;py=(slot//3)*392
            sheet.paste(im,(px+(480-im.width)//2,py+30+(360-im.height)//2))
            draw.text((px+6,py+4),f'{sid} t={item["start"]+n/24:.3f}s f={round(item["start"]*24)+n}',font=font,fill='white')
        sheet.save(OUT/f'{sid}-{page+1}.jpg',quality=94)
    manifest.append(dict(item,source_sha256=digest,consecutive_frame_count=count,approval='pending',
        limitation='This covers only the named 2-second interval and ROI, not the entire clip.'))
    print(f'::notice title=Detail {sid}::48 consecutive native-frame crops extracted; visual review pending.')
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
