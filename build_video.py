from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps
from pathlib import Path
import subprocess, re, math

ROOT=Path(__file__).parent
ASSETS=ROOT/'assets'
OUT=ASSETS/'final-frames'
BUILD=Path('/tmp/mcgrory-build')
OUT.mkdir(parents=True,exist_ok=True); BUILD.mkdir(parents=True,exist_ok=True)
FONT='/tmp/video-build/NotoSC.ttf'; W,H=1080,1920
CAPTIONS=[
'一宗已经判无罪的谋杀案，四十多年后为何重回法庭？',
'这不是虚构剧情，而是英国丹尼斯麦格罗里案。',
'一九七五年，十五岁的杰奎琳蒙哥马利在伦敦遇害。',
'当年的审判以无罪告终，案件似乎走到尽头。',
'多年后，警方重新翻查旧案，保存证物仍在。',
'基因检测技术进步，让当年生物样本得以再次检验。',
'检方称，结果支持麦格罗里曾与杰奎琳有性接触。',
'但案件证据不止基因检测，警方也重新梳理旧案材料。',
'一页从杰奎琳日记撕下的纸，在他被捕时于口袋中发现。',
'警方旧照片记录了他身上的伤痕，他称自己遭人袭击。',
'这些细节必须在法庭上逐项检验，而不是猎奇。',
'英国没有简单废除一罪不二审，而是设立严格例外。',
'严重案件须出现新的有力证据，才可能申请重审。',
'上诉法院还须审查证据，并衡量是否符合公共利益。',
'检方复核后提出申请，法院最终批准再次审理。',
'二〇二二年，麦格罗里再次接受陪审团审判。',
'同年十二月，陪审团裁定他强奸与谋杀罪名成立。',
'二〇二三年一月，法院判处他终身监禁。',
'最低服刑期为二十五年。',
'这不是基因检测单独定罪，而是多种证据组成的证据链。',
'迟来的判决，无法把杰奎琳的生命还给她。',
'但冷案重启，终于给出了法律上的答案。',
'新技术让旧证物再次开口，也要求审判程序更严谨。',
'这就是跨越近半世纪案件留下的回响。'
]
# Every story shot uses its own unique clean, text-free illustration or photograph.
SOURCES=[
'clean-01-case-desk.jpg','clean-10-courtroom.jpg','clean-02-islington.jpg','clean-04-bedroom.jpg',
'clean-12-police-desk.jpg','clean-07-laboratory.jpg','clean-06-evidence.jpg','clean-11-fingerprints.jpg',
'clean-19-evidence-table.jpg','clean-03-detective.jpg','clean-17-gavel.jpg','clean-14-court-steps.jpg',
'clean-05-archive.jpg','clean-16-stairwell.jpg','clean-09-courthouse.jpg','clean-20-jury-room.jpg',
'vector-stills/vector-01-scales.jpg','clean-18-prison-gate.jpg','clean-13-calendar.jpg','clean-08-helix.jpg',
'vector-stills/vector-04-open-door.jpg','vector-stills/vector-02-time.jpg','vector-stills/vector-03-evidence-chain.jpg','clean-15-glass-slide.jpg'
]
assert len(SOURCES)==24 and len(set(SOURCES))==24, 'Every image must be unique.'

subtitle_font=ImageFont.truetype(FONT,54)
title_font=ImageFont.truetype(FONT,92)
small_font=ImageFont.truetype(FONT,38)

def cover_crop(im,box=None):
    if box:
        w,h=im.size; im=im.crop((int(w*box[0]),int(h*box[1]),int(w*box[2]),int(h*box[3])))
    return ImageOps.fit(im.convert('RGB'),(W,H),method=Image.Resampling.LANCZOS,centering=(.5,.47))
def wrap_cn(draw,text,font,max_chars=16):
    return [text[i:i+max_chars] for i in range(0,len(text),max_chars)]
def darken_lower(im):
    im=im.convert('RGBA')
    grad=Image.new('RGBA',(W,H),(0,0,0,0)); gd=ImageDraw.Draw(grad)
    for y in range(1280,H):
        a=int(195*(y-1280)/(H-1280))
        gd.line((0,y,W,y),fill=(5,5,4,a),width=1)
    return Image.alpha_composite(im,grad).convert('RGB')
def subtitle(draw,text):
    lines=wrap_cn(draw,text,subtitle_font,16)
    lineh=77
    center_y=1555
    first=center_y-(len(lines)-1)*lineh/2
    for j,line in enumerate(lines):
        draw.text((W/2,first+j*lineh),line,font=subtitle_font,fill=(255,222,89),stroke_width=6,stroke_fill=(9,8,6),anchor='mm')

def srt_time(sec):
    ms=round(sec*1000); h=ms//3600000;ms%=3600000;mi=ms//60000;ms%=60000;ss=ms//1000;ms%=1000
    return f'{h:02}:{mi:02}:{ss:02},{ms:03}'

ffmpeg=subprocess.check_output(['/tmp/videotools/bin/python','-c','import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],text=True).strip()
probe=subprocess.run([ffmpeg,'-hide_banner','-i',str(ROOT/'audio/narration-final.mp3'),'-f','null','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe.stderr)
source_audio=float(m.group(1))*3600+float(m.group(2))*60+float(m.group(3)) if m else 104.69
voice_seconds=source_audio/.92
end_seconds=120-voice_seconds
weights=[len(t)+1.3*t.count('，')+2*t.count('？')+1.8*t.count('。') for t in CAPTIONS]
scale=voice_seconds/sum(weights); timings=[]; cursor=0.0
for weight in weights:
    nxt=cursor+weight*scale; timings.append((cursor,nxt)); cursor=nxt

for i,(name,caption) in enumerate(zip(SOURCES,CAPTIONS),1):
    im=cover_crop(Image.open(ASSETS/name))
    im=ImageEnhance.Color(im).enhance(.82)
    im=darken_lower(im)
    d=ImageDraw.Draw(im)
    subtitle(d,caption)
    if i==1:
        d.rounded_rectangle((70,175,690,315),radius=22,fill=(23,18,12))
        d.text((105,190),'迟来的证据',font=title_font,fill=(255,231,164),stroke_width=3,stroke_fill=(8,7,5))
        d.text((110,315),'丹尼斯麦格罗里案',font=small_font,fill=(249,241,218),stroke_width=3,stroke_fill=(8,7,5))
    im.save(OUT/f'frame-{i:02d}.jpg',quality=91,optimize=True)

# Fully Chinese end slate, with no Latin letters or Arabic numerals.
end=cover_crop(Image.open(ASSETS/'vector-stills/vector-06-end-slate.jpg'))
end=ImageEnhance.Color(end).enhance(.65)
end=Image.blend(end,Image.new('RGB',(W,H),(7,8,8)),.5)
d=ImageDraw.Draw(end)
d.text((W/2,680),'迟来的证据',font=title_font,fill=(255,226,115),stroke_width=4,stroke_fill=(4,4,4),anchor='mm')
d.text((W/2,830),'司法仍须经得起质疑',font=subtitle_font,fill=(255,250,237),stroke_width=4,stroke_fill=(4,4,4),anchor='mm')
d.text((W/2,1300),'史实依据：英国检察署公开案件资料',font=small_font,fill=(255,246,222),stroke_width=3,stroke_fill=(4,4,4),anchor='mm')
d.text((W/2,1390),'画面为人工智能生成的情景示意',font=small_font,fill=(255,246,222),stroke_width=3,stroke_fill=(4,4,4),anchor='mm')
end.save(OUT/'frame-25-source.jpg',quality=91,optimize=True)

parts=[]
for i,(a,b) in enumerate(timings,1):
    duration=b-a; img=OUT/f'frame-{i:02d}.jpg'; seg=BUILD/f'part-{i:02d}.mp4'
    z="min(zoom+0.00012,1.028)" if i%2 else "max(zoom-0.00008,1.0)"
    vf=f"zoompan=z='{z}':d=1:s={W}x{H}:fps=30:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',format=yuv420p"
    subprocess.run([ffmpeg,'-y','-loglevel','error','-loop','1','-framerate','30','-i',str(img),'-t',f'{duration:.5f}','-vf',vf,'-an','-c:v','libx264','-preset','fast','-crf','25','-pix_fmt','yuv420p','-r','30',str(seg)],check=True)
    parts.append(seg)
endseg=BUILD/'part-end.mp4'
subprocess.run([ffmpeg,'-y','-loglevel','error','-loop','1','-framerate','30','-i',str(OUT/'frame-25-source.jpg'),'-t',f'{end_seconds:.5f}','-vf',f'scale={W}:{H},format=yuv420p','-an','-c:v','libx264','-preset','fast','-crf','25','-pix_fmt','yuv420p','-r','30',str(endseg)],check=True)
parts.append(endseg)
concat=BUILD/'concat.txt'; concat.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts))
joined=BUILD/'joined.mp4'
subprocess.run([ffmpeg,'-y','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(joined)],check=True)
final=ROOT/'Dennis-McGrory-2min-vertical.mp4'
subprocess.run([ffmpeg,'-y','-loglevel','error','-i',str(joined),'-i',str(ROOT/'audio/narration-final.mp3'),'-af','atempo=0.92','-t','120','-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','112k','-movflags','+faststart',str(final)],check=True)
srt=[]
for n,(caption,(a,b)) in enumerate(zip(CAPTIONS,timings),1): srt += [str(n),f'{srt_time(a)} --> {srt_time(b)}',caption,'']
(ROOT/'Dennis-McGrory-zh-CN.srt').write_text('\n'.join(srt),encoding='utf-8')
print(f'Created {final}; source audio {source_audio:.2f}s; slowed voice {voice_seconds:.2f}s; end slate {end_seconds:.2f}s; scenes {len(SOURCES)}')
