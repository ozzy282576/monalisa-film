from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps
from pathlib import Path
import subprocess, math, json, os

ROOT = Path(__file__).parent
ASSETS = ROOT / 'assets'
OUT_DIR = ASSETS / 'final-frames'
BUILD = Path('/tmp/mcgrory-build')
OUT_DIR.mkdir(parents=True, exist_ok=True)
BUILD.mkdir(parents=True, exist_ok=True)
FONT = '/tmp/video-build/NotoSC.ttf'
W, H = 1080, 1920
CAPTIONS = [
'一宗已被判无罪的谋杀案，四十多年后为何重回法庭？',
'这不是虚构剧情，而是英国丹尼斯·麦格罗里案。',
'1975年，十五岁的杰奎琳·蒙哥马利在伦敦遇害。',
'当年的审判以无罪告终，案件似乎走到尽头。',
'多年后，警方重新翻查旧案，旧证物仍被保存。',
'DNA技术进步，让当年生物样本得以再次检验。',
'检方称，结果支持麦格罗里曾与杰奎琳有性接触。',
'但案件证据不止DNA，警方也重新梳理旧案材料。',
'一页从杰奎琳日记撕下的纸，在他被捕时于口袋中发现。',
'警方照片记录了他身上的伤痕，他解释是遭人袭击。',
'这些细节都要在法庭上逐项检验，而非猎奇。',
'英国没有简单废除“一罪不二审”，而是设立严格例外。',
'严重案件须出现新的、有说服力的证据，才可能重审。',
'上诉法院还会审查证据，并衡量公共利益。',
'复核后，检方申请重审，法院最终批准。',
'2022年，麦格罗里再次接受陪审团审判。',
'同年十二月，陪审团裁定他强奸、谋杀罪名成立。',
'2023年一月，他被判终身监禁。',
'最低服刑期为二十五年。',
'这不是DNA单独定罪，而是多种证据拼成的证据链。',
'迟来的判决，无法把杰奎琳的生命还给她。',
'但冷案重启，终于给出了法律上的答案。',
'新技术让旧证物再次开口，也要求程序更严谨。',
'这，就是跨越近半世纪案件留下的回响。',
]
SOURCES = [
 'assets/shot-01-dossier.jpg', 'assets/shot-02-courtroom.jpg', 'assets/shot-03-street.jpg', 'assets/shot-04-window.jpg',
 'assets/shot-08-archive.jpg', 'assets/shot-10-modern-lab.jpg', 'assets/scene-04-dna.jpg', 'assets/shot-07-old-file.jpg',
 'assets/scene-03-diary.jpg', 'assets/scene-02-casefile.jpg', 'assets/shot-09-lab-old.jpg', 'assets/scene-05-court.jpg',
 'assets/shot-08-archive.jpg', 'assets/scene-05-court.jpg', 'assets/shot-07-old-file.jpg', 'assets/shot-02-courtroom.jpg',
 'assets/scene-06-verdict.jpg', 'assets/shot-02-courtroom.jpg', 'assets/scene-04-dna.jpg', 'assets/shot-09-lab-old.jpg',
 'assets/shot-06-empty-room.jpg', 'assets/shot-03-street.jpg', 'assets/shot-10-modern-lab.jpg', 'assets/scene-05-court.jpg'
]
# The later images use close-in crops and reframing, creating 24 distinct visual cuts from the generated still set.
CROPS = {
 12: (0.08, 0.08, 0.86, 0.85), 13: (0.12, 0.12, 0.88, 0.88),
 14: (0.16, 0.05, 0.90, 0.82), 15: (0.08, 0.18, 0.86, 0.94),
 16: (0.14, 0.10, 0.90, 0.87), 17: (0.10, 0.06, 0.84, 0.80),
 18: (0.18, 0.14, 0.92, 0.92), 19: (0.05, 0.12, 0.81, 0.88),
 20: (0.16, 0.08, 0.90, 0.84), 21: (0.10, 0.16, 0.88, 0.94),
 22: (0.14, 0.08, 0.92, 0.88), 23: (0.06, 0.10, 0.82, 0.86),
}
font = ImageFont.truetype(FONT, 55)
title_font = ImageFont.truetype(FONT, 88)
small_font = ImageFont.truetype(FONT, 34)

def fit_crop(im, box=None):
    if box:
        w,h=im.size; im=im.crop((int(w*box[0]), int(h*box[1]), int(w*box[2]), int(h*box[3])))
    return ImageOps.fit(im.convert('RGB'), (W,H), method=Image.Resampling.LANCZOS, centering=(0.5,0.47))

def wrap(draw, text, f, max_width):
    lines=[]; cur=''
    for ch in text:
        if draw.textbbox((0,0), cur+ch, font=f, stroke_width=0)[2] <= max_width or not cur:
            cur+=ch
        else:
            lines.append(cur); cur=ch
    if cur: lines.append(cur)
    return lines

def text_with_outline(draw, xy, text, f, fill, outline=(10,8,5), sw=4, anchor=None):
    draw.text(xy, text, font=f, fill=fill, stroke_width=sw, stroke_fill=outline, anchor=anchor)

# narration is 113.93 seconds; distribute caption windows by their spoken character load.
ffmpeg = subprocess.check_output(['/tmp/videotools/bin/python','-c','import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'], text=True).strip()
probe = subprocess.run([ffmpeg,'-hide_banner','-i',str(ROOT/'audio/narration-final.mp3'),'-f','null','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
import re
m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe.stderr)
voice_seconds=int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)) if m else 113.93
weights=[len(x) + 2.0*x.count('，') + 3.0*x.count('？') + 2.0*x.count('。') for x in CAPTIONS]
scale=voice_seconds/sum(weights)
times=[]; now=0.0
for w in weights:
    end=now+w*scale
    times.append((now,end)); now=end

for i,(src,caption) in enumerate(zip(SOURCES,CAPTIONS),1):
    im=Image.open(ROOT/src)
    box=CROPS.get(i)
    im=fit_crop(im,box)
    # Warm cinematic finish consistent with the reference's historical reenactment style.
    im=ImageEnhance.Color(im).enhance(0.82)
    overlay=Image.new('RGB',(W,H),(0,0,0)); od=ImageDraw.Draw(overlay)
    for y in range(1260,H):
        alpha=int(130*(y-1260)/(H-1260))
        od.line((0,y,W,y), fill=(0,0,0), width=1)
    im=Image.blend(im,overlay,0.22)
    d=ImageDraw.Draw(im)
    lines=wrap(d,caption,font,970)
    line_h=70
    base_y=1535-(len(lines)-1)*line_h/2
    for j,line in enumerate(lines):
        d.text((W//2,base_y+j*line_h),line,font=font,fill=(255,220,72),stroke_width=5,stroke_fill=(14,10,7),anchor='mm')
    if i==1:
        d.rounded_rectangle((72,180,704,318),radius=18,fill=(24,18,11))
        text_with_outline(d,(104,203),'迟来的证据',title_font,(255,229,146),sw=2)
        d.text((107,328),'英国冷案档案  /  DENNIS McGRORY',font=small_font,fill=(246,238,216),stroke_width=2,stroke_fill=(10,8,5))
    out=OUT_DIR/f'frame-{i:02d}.jpg'
    im.save(out,quality=91,optimize=True)

# End slate: verified-source note, six seconds, no invented quotes or case imagery.
end=fit_crop(Image.open(ROOT/'assets/scene-06-verdict.jpg'))
end=ImageEnhance.Color(end).enhance(0.55)
shade=Image.new('RGB',(W,H),(7,8,8));end=Image.blend(end,shade,0.56);d=ImageDraw.Draw(end)
d.text((W//2,690),'迟来的证据',font=title_font,fill=(255,224,105),stroke_width=3,stroke_fill=(5,5,5),anchor='mm')
d.text((W//2,835),'司法仍须经得起质疑',font=font,fill=(255,255,245),stroke_width=3,stroke_fill=(5,5,5),anchor='mm')
d.text((W//2,1310),'史实来源：英国检察署 CPS',font=small_font,fill=(255,255,255),stroke_width=2,stroke_fill=(0,0,0),anchor='mm')
d.text((W//2,1370),'McGrory double jeopardy',font=small_font,fill=(250,230,180),stroke_width=2,stroke_fill=(0,0,0),anchor='mm')
d.text((W//2,1450),'画面为 AI 情景示意，并非真实案发照片',font=small_font,fill=(245,240,230),stroke_width=2,stroke_fill=(0,0,0),anchor='mm')
end.save(OUT_DIR/'frame-25-source.jpg',quality=91,optimize=True)

# Generate 24 short Ken-Burns clips; image cuts follow each subtitle line.
segment_paths=[]
for i,(start,endtime) in enumerate(times,1):
    dur=endtime-start
    src=OUT_DIR/f'frame-{i:02d}.jpg'
    seg=BUILD/f'part-{i:02d}.mp4'
    # alternate gentle zoom direction to keep the still montage alive
    z="min(zoom+0.00016,1.035)" if i%2 else "max(zoom-0.00010,1.0)"
    vf=f"zoompan=z='{z}':d=1:s={W}x{H}:fps=30:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',format=yuv420p"
    subprocess.run([ffmpeg,'-y','-loglevel','error','-loop','1','-framerate','30','-i',str(src),'-t',f'{dur:.4f}','-vf',vf,'-an','-c:v','libx264','-preset','fast','-crf','25','-pix_fmt','yuv420p','-r','30',str(seg)],check=True)
    segment_paths.append(seg)
endseg=BUILD/'part-25.mp4'
subprocess.run([ffmpeg,'-y','-loglevel','error','-loop','1','-framerate','30','-i',str(OUT_DIR/'frame-25-source.jpg'),'-t','6.07','-vf',f'scale={W}:{H},format=yuv420p','-an','-c:v','libx264','-preset','fast','-crf','25','-pix_fmt','yuv420p','-r','30',str(endseg)],check=True)
segment_paths.append(endseg)
concat=BUILD/'concat.txt'
concat.write_text(''.join(f"file '{p.as_posix()}'\n" for p in segment_paths))
joined=BUILD/'joined.mp4'
subprocess.run([ffmpeg,'-y','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(joined)],check=True)
final=ROOT/'Dennis-McGrory-2min-vertical.mp4'
subprocess.run([ffmpeg,'-y','-loglevel','error','-i',str(joined),'-i',str(ROOT/'audio/narration-final.mp3'),'-t','120','-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','112k','-movflags','+faststart',str(final)],check=True)
# Export compact SRT for independent subtitle use.
def srt_time(seconds):
    ms=round(seconds*1000); h=ms//3600000;ms%=3600000;mi=ms//60000;ms%=60000;se=ms//1000;ms%=1000
    return f'{h:02}:{mi:02}:{se:02},{ms:03}'
srt=[]
for n,(caption,(a,b)) in enumerate(zip(CAPTIONS,times),1):
    srt += [str(n),f'{srt_time(a)} --> {srt_time(b)}',caption,'']
(ROOT/'Dennis-McGrory-zh-CN.srt').write_text('\n'.join(srt),encoding='utf-8')
print('Video:',final,'duration',120,'voice',round(voice_seconds,2),'shots',len(SOURCES),'frames',len(list(OUT_DIR.glob('*.jpg'))))
