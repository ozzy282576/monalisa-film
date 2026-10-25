#!/usr/bin/env python3
"""Deterministic three-minute cloud edit; generated footage is never replaced by fixtures.

Requires the planned Agnes clips, a sourced archival portrait, and six selected narration recordings.
Outputs an explicitly unreviewed first cut, technical report, EDL, captions and QA sheet.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from media import probe
from build_audio import build_soundtrack, measure, assert_audible

FPS = 30
DURATION = 180.0
INTRO = 0.6
GAP = 1.08
OUTRO = 6.0
RATE = 48000
# Raw-audio editorial anchors, reviewed against the recordings' measured pauses.
# A cue can return to a previously introduced prop/portrait; it never samples an unrelated scene.
CUTS = {
    'N01': [(0,'S01',''), (4.0,'S02',''), (9.9,'S03',''), (14.7,'S04',''), (18.8,'S05','')],
    'N02': [(0,'S06',''), (2.75,'S07',''), (4.6,'S08',''), (7.55,'S09','portrait_a'),
            (11.2,'S06','fingerprint_b'), (14.0,'S08','archive'), (17.4,'S10',''),
            (22.0,'S09','portrait_b'), (26.0,'S11','')],
    'N03': [(0,'S11',''), (6.1,'S12',''), (8.6,'S13',''), (11.05,'S14',''), (16.9,'S15','')],
    'N04': [(0,'S16',''), (5.8,'S17',''), (8.1,'S18',''), (15.1,'S19',''), (21.8,'S20','')],
    'N05': [(0,'S21',''), (2.85,'S22',''), (5.25,'S23',''), (13.1,'S24',''),
            (16.6,'S25',''), (19.8,'S23','truth')],
    'N06': [(0,'S26',''), (7.65,'S27',''), (13.45,'S28',''), (18.0,'S29',''), (23.75,'S30','')],
}


def run(args, capture=False):
    return subprocess.run([str(x) for x in args], check=True, capture_output=capture, text=capture)


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def find_font(serif=False):
    candidates = []
    if serif:
        candidates += [ROOT/'.cache/fonts/NotoSerifCJKsc-Regular.otf', Path('/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc')]
    candidates += [ROOT/'.cache/fonts/NotoSansCJKsc-Regular.otf', Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
    for p in candidates:
        if p.exists(): return p
    raise RuntimeError('A Chinese Noto CJK font is required; refusing to render missing glyphs')


def font(size, serif=False):
    path=find_font(serif)
    return ImageFont.truetype(str(path), size, index=2 if path.suffix=='.ttc' else 0)


def centered(draw, text, y, size, color, x=960, serif=False):
    f=font(size,serif); box=draw.textbbox((0,0),text,font=f)
    draw.text((x-(box[2]-box[0])/2,y),text,font=f,fill=color)


def card_image(sid, variant, directory):
    directory.mkdir(parents=True,exist_ok=True)
    dest=directory/f'{sid}-{variant or "base"}.jpg'
    if dest.exists():return dest
    rng=np.random.default_rng(1947+int(sid[1:]) if sid.startswith('S') else 1947)
    y,x=np.mgrid[0:1080,0:1920]
    glow=np.clip(1-((x-940)/1200)**2-((y-510)/850)**2,0,1)
    grain=rng.normal(0,1.2,(1080,1920))
    bg=np.stack([22+glow*16+grain,25+glow*15+grain,24+glow*10+grain],axis=-1)
    im=Image.fromarray(np.uint8(np.clip(bg,0,255)),'RGB');d=ImageDraw.Draw(im)
    if sid=='END':
        centered(d,'伊丽莎白 · 肖特',342,105,'#ede8db',serif=True)
        centered(d,'她只有二十二岁',498,48,'#b7aa82')
        centered(d,'真实的人，不只是一个案件的名字。',668,31,'#a6aaa0')
        centered(d,'资料：FBI Black Dahlia  /  原创解说 · AI情景重现',895,21,'#7f897d')
    else:
        d.rounded_rectangle((169,104,1751,954),radius=6,fill='#0d1210')
        # Physical-paper palette connects the cards to the generated walnut desks and case folders.
        paper=np.stack([218+grain,212+grain,192+grain],axis=-1)
        patch=Image.fromarray(np.uint8(np.clip(paper[119:939,184:1736],0,255)),'RGB')
        im.paste(patch,(184,119));d=ImageDraw.Draw(im)
        d.text((265,180),'案件档案  /  LOS ANGELES · 1947',font=font(24),fill='#5d6456')
        d.line((265,236,1655,236),fill='#929781',width=2)
        headings={
            'S03':('发现现场','1947年1月15日 · 洛杉矶','一名年轻女子遇害'),
            'S08':('56分钟','指纹确认身份','伊丽莎白 · 肖特，22岁'),
            'S11':('警方征集线索','1947年1月9日 — 15日','最后已知行踪：比尔特莫尔酒店'),
            'S14':('消失的六天','01.09                         01.15','未能补齐的行踪'),
            'S18':('没有匹配','匿名信上的指纹','寄信者身份仍未证实'),
            'S23':('线索 ≠ 定论','身份  ·  地点  ·  作案过程','需要证据连接，而不是传闻'),
        }
        title,line1,line2=headings[sid]
        if variant=='archive':title,line1,line2='旧档案','认出了她的身份','却没有给出凶手的身份'
        if variant=='truth':title,line1,line2='故事 ≠ 事实','一个讲得通的推测','不等于一个被证明的结论'
        centered(d,title,302,108,'#2c3a32',serif=True)
        centered(d,line1,486,49,'#475648')
        if sid=='S14':
            for a in range(554,1370,30):d.line((a,611,a+14,611),fill='#8b784d',width=4)
            for a in (535,1385):d.ellipse((a-9,602,a+9,620),fill='#6c674a')
            centered(d,'行踪缺口',629,28,'#7e6b47')
        else:d.line((855,628,1065,628),fill='#958358',width=3)
        centered(d,line2,720,38,'#5c6656')
        d.text((265,875),'资料摘要与示意图 · 并非原始档案影像',font=font(21),fill='#75806c')
    im.save(dest,quality=93)
    return dest


def archive_image(variant,directory):
    """Use the identified bulletin portrait instead of the unsuitable generated face."""
    directory.mkdir(parents=True,exist_ok=True)
    dest=directory/f'archival-portrait-{variant or "base"}.jpg'
    if dest.exists():return dest
    im=Image.new('RGB',(1920,1080),'#1b211d');d=ImageDraw.Draw(im)
    source=HERE/'assets/elizabeth_short_archival.jpg'
    portrait=Image.open(source).convert('RGB')
    if variant=='portrait_b':
        w,h=portrait.size
        portrait=portrait.crop((int(w*.04),int(h*.02),int(w*.97),int(h*.92)))
    portrait.thumbnail((710,810),Image.Resampling.LANCZOS)
    scale=min(710/portrait.width,810/portrait.height)
    portrait=portrait.resize((round(portrait.width*scale),round(portrait.height*scale)),Image.Resampling.LANCZOS)
    x=200+(710-portrait.width)//2;y=125+(810-portrait.height)//2
    d.rectangle((x-12,y-12,x+portrait.width+12,y+portrait.height+12),fill='#cfc6ac')
    im.paste(portrait,(x,y));d=ImageDraw.Draw(im)
    centered(d,'她的名字',316,34,'#b7aa82',x=1330)
    centered(d,'伊丽莎白 · 肖特',400,72,'#ede8db',x=1330,serif=True)
    centered(d,'22岁',536,90,'#d4c69d',x=1330)
    d.line((1240,695,1420,695),fill='#8e8466',width=2)
    centered(d,'档案照片 · 非AI生成人像',747,28,'#a7b09f',x=1330)
    centered(d,'来源：1947年1月21日洛杉矶警方调查通告',942,23,'#84917d')
    im.save(dest,quality=94)
    return dest


def fingerprint_overlay(directory,width,height):
    """Controlled diagram covers an incorrect generated pattern; not evidence imagery."""
    directory.mkdir(parents=True,exist_ok=True)
    dest=directory/f'fingerprint-diagram-{width}x{height}.png'
    if dest.exists():return dest
    im=Image.new('RGBA',(1920,1080),(0,0,0,0));d=ImageDraw.Draw(im)
    d.rounded_rectangle((130,150,1790,930),radius=14,fill=(22,29,24,250))
    d.rounded_rectangle((160,180,940,900),radius=5,fill=(220,212,191,255))
    # A generic whorl icon. No real person's biometric data is reproduced.
    cx,cy=550,520
    for radius in range(12,232,10):
        points=[]
        for t in np.linspace(0,2*math.pi,360):
            x=cx+radius*.76*math.cos(t)+math.sin(t*2)*radius*.09
            y=cy+radius*1.18*math.sin(t)+math.cos(t)*radius*.04
            points.append((x,y))
        d.line(points,fill=(60,73,59,245),width=3)
    centered(d,'指纹样式示意',810,28,(84,91,75,255),x=550)
    centered(d,'指纹与身份比对',330,66,(235,230,213,255),x=1345,serif=True)
    centered(d,'旧档案中的记录',490,42,(204,191,151,255),x=1345)
    d.line((1240,605,1450,605),fill=(147,137,105,255),width=3)
    centered(d,'仅说明鉴定过程',690,32,(167,179,155,255),x=1345)
    centered(d,'非当年证物图像',752,26,(143,157,133,255),x=1345)
    if (width,height)!=(1920,1080):im=im.resize((width,height),Image.Resampling.LANCZOS)
    im.save(dest)
    return dest


def audio_layout(chapters, audio_root, work, manifest):
    directory=work/'audio';directory.mkdir(parents=True,exist_ok=True)
    files=[];durations=[];waves=[]
    by_id={row['id']:row for row in manifest['clips']}
    for c in chapters:
        src=audio_root/(c['id']+'.mp3')
        receipt=by_id[c['id']]
        if receipt['text']!=c['text'] or digest(src)!=receipt['sha256']:
            raise RuntimeError('Narration text/file provenance mismatch: '+c['id'])
        dest=directory/(c['id']+'.wav')
        run(['ffmpeg','-v','error','-y','-i',src,'-ac','1','-ar',RATE,'-c:a','pcm_s16le',dest])
        with wave.open(str(dest),'rb') as f:
            samples=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
        durations.append(len(samples)/RATE);waves.append(samples);files.append(dest)
    usable=DURATION-INTRO-OUTRO-GAP*(len(chapters)-1)
    tempo=sum(durations)/usable
    if not .86<=tempo<=1.1:raise RuntimeError(f'Narration would need excessive retiming: {tempo}')
    start=INTRO;rows=[]
    for c,d,path,samples in zip(chapters,durations,files,waves):
        rows.append({'id':c['id'],'start':start,'end':start+d/tempo,'raw_duration':d,
                     'tempo':tempo,'path':str(path),'text':c['text']})
        start+=d/tempo+GAP
    if abs(rows[-1]['end']-(DURATION-OUTRO))>.001:raise RuntimeError('Narration layout mismatch')
    return rows,waves


def caption_clauses(text):
    raw=re.findall(r'[^，。！？；：、]+[，。！？；：、]?',text)
    result=[]
    for part in raw:
        while len(part)>24:
            result.append(part[:22]);part=part[22:]
        if part.strip():result.append(part.strip())
    return result


def captions_for(row, samples):
    """Pause-aware proportional alignment, not a claim of word-level ASR accuracy."""
    clauses=caption_clauses(row['text']);hop=960
    pad=(-len(samples))%hop
    blocks=np.pad(samples,(0,pad)).reshape(-1,hop)
    rms=np.sqrt(np.mean(blocks*blocks,axis=1))
    active=(rms>.009).astype(float)
    clock=np.cumsum(active+.04)
    weights=[max(1,len(re.sub(r'[^\u3400-\u9fffA-Za-z0-9]','',c))) for c in clauses]
    expected=np.cumsum(weights)/sum(weights)
    silences=[];begin=None
    for i,a in enumerate(active):
        if not a and begin is None:begin=i
        if a and begin is not None:
            if (i-begin)*.02>=.14:silences.append(((begin+i)*.01,(i-begin)*.02))
            begin=None
    bounds=[0.0]
    for fraction in expected[:-1]:
        t=float(np.searchsorted(clock,clock[-1]*fraction))*.02
        candidates=[(t,0.0)]+[(center,d) for center,d in silences if abs(center-t)<.6]
        candidates=[(p,d) for p,d in candidates if p>bounds[-1]+.16]
        if candidates:t=min(candidates,key=lambda p:abs(p[0]-t)-min(.25,p[1]*.35))[0]
        bounds.append(max(bounds[-1]+.17,min(row['raw_duration']-.18,t)))
    bounds.append(row['raw_duration'])
    cues=[]
    for text,a,b in zip(clauses,bounds,bounds[1:]):
        cues.append({'start':row['start']+a/row['tempo'],'end':row['start']+b/row['tempo'],'text':text})
    return cues


def make_edl(project, narration):
    by_id={s['id']:s for s in project['shots']};edl=[]
    for i,row in enumerate(narration):
        entries=CUTS[row['id']]
        chapter_end=narration[i+1]['start'] if i+1<len(narration) else 176.2
        for j,(raw_start,sid,variant) in enumerate(entries):
            start=row['start']+raw_start/row['tempo']
            if not edl:start=0
            end=(row['start']+entries[j+1][0]/row['tempo']) if j+1<len(entries) else chapter_end
            a=round(start*FPS);b=round(end*FPS)
            record={'id':sid,'variant':variant,'kind':by_id[sid]['kind'],'start_frame':a,'end_frame':b,
                    'narration_id':row['id'],'purpose':by_id[sid]['purpose']}
            if edl and edl[-1]['id']==sid and edl[-1]['variant']==variant and edl[-1]['end_frame']==a:
                edl[-1]['end_frame']=b
            else:edl.append(record)
    edl.append({'id':'END','kind':'graphic','variant':'','start_frame':round(176.2*FPS),'end_frame':5400,
                'narration_id':'N06','purpose':'姓名与年龄收尾；明确未解，不虚构凶手'})
    if edl[0]['start_frame']!=0 or edl[-1]['end_frame']!=5400:raise RuntimeError('EDL duration is not 180s')
    for left,right in zip(edl,edl[1:]):
        if left['end_frame']!=right['start_frame']:raise RuntimeError('EDL gap/overlap')
    for e in edl:
        if e['end_frame']<=e['start_frame']:raise RuntimeError('Empty editorial segment')
    return edl


def ass_time(s):
    centis=round(s*100);h,centis=divmod(centis,360000);m,centis=divmod(centis,6000);sec,cs=divmod(centis,100)
    return f'{h}:{m:02d}:{sec:02d}.{cs:02d}'


def safe_text(text):
    return text.replace('\\','/').replace('{','（').replace('}','）').replace('\n',' ')


def write_subtitles(path,cues,edl):
    text='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Noto Sans CJK SC,43,&H00FFFFFF,&H000000FF,&H00141410,&H99000000,1,0,0,0,100,100,1,0,1,2.3,0.8,2,80,80,42,1
Style: Label,Noto Sans CJK SC,23,&H60E9E4D4,&H000000FF,&H00262621,&H99000000,0,0,0,0,100,100,1,0,1,1,0,9,60,60,36,1
Style: Title,Noto Serif CJK SC,102,&H00EBE8DE,&H000000FF,&H00141B17,&H99000000,0,0,0,0,100,100,4,0,1,1,2,7,104,104,205,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    for cue in cues:
        caption=safe_text(cue['text'])
        for key in ['五十六分钟','伊丽莎白·肖特','二十二岁','黑色大丽花','没有血迹','没有匹配','仍未侦破']:
            if key in caption:caption=caption.replace(key,r'{\c&H0076DDF2&}'+key+r'{\c&H00FFFFFF&}')
        text+=f"Dialogue: 1,{ass_time(cue['start'])},{ass_time(cue['end'])},Caption,,0,0,0,,{{\\q2\\fad(45,45)}}{caption}\n"
    for entry in edl:
        if entry['id']=='END':continue
        label={'agnes':'AI情景重现 · 非历史影像','archive':'档案照片 · 来源：警方调查通告',
               'graphic':'资料摘要与示意图'}[entry['kind']]
        if entry['id']=='S06':label='指纹图解 · 非原始证物图像'
        if entry['id']=='S07':label='影像传输的AI示意 · 非设备实拍'
        if entry['id']=='S12':label='酒店外景为AI示意 · 非实地影像'
        if entry['id']=='S29':label='AI生活意象 · 非本人档案影像'
        if entry['id']=='S30':label='AI象征画面 · 非案件证物'
        text+=f"Dialogue: 0,{ass_time(entry['start_frame']/FPS)},{ass_time(entry['end_frame']/FPS)},Label,,0,0,0,,{label}\n"
    text+='Dialogue: 2,0:00:00.35,0:00:04.70,Title,,0,0,0,,{\\fad(500,550)}黑色大丽花\\N{\\fs41\\fsp6}消失的六天\n'
    path.write_text(text)
    srt=path.with_suffix('.srt')
    def clock(s):
        ms=round(s*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);sec,ms=divmod(ms,1000)
        return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'
    srt.write_text('\n'.join(f"{i}\n{clock(c['start'])} --> {clock(c['end'])}\n{c['text']}\n" for i,c in enumerate(cues,1)))


def write_sfx(path,edl):
    rng=np.random.default_rng(19470115);out=np.zeros((round(DURATION*RATE),2),dtype=np.float32)
    events=[]
    for source,kind in [('S06','paper'),('S07','machine'),('S10','press'),('S21','phone'),('S25','paper')]:
        first=next(e for e in edl if e['id']==source)
        events.append((max(0,first['start_frame']/FPS-.18),kind))
    for start,kind in events:
        duration={'paper':.7,'machine':1.1,'press':1.5,'phone':1.3,'keys':1.1}[kind]
        t=np.arange(round(duration*RATE))/RATE
        if kind=='phone':
            pulse=(np.sin(2*np.pi*18*t)>0).astype(float)
            signal=(np.sin(2*np.pi*430*t)+.45*np.sin(2*np.pi*580*t))*pulse*.05
        elif kind in ('machine','press','keys'):
            interval=.13 if kind=='keys' else .08
            beat=np.mod(t,interval)
            signal=rng.normal(0,1,len(t))*np.exp(-beat*160)*.08
        else:
            noise=rng.normal(0,1,len(t));signal=np.convolve(noise,np.ones(8)/8,'same')*.13
        signal*=np.minimum(np.clip(t/.06,0,1),np.clip((duration-t)/.18,0,1))
        i=round(start*RATE);n=min(len(signal),len(out)-i)
        out[i:i+n,0]+=signal[:n]*.93;out[i:i+n,1]+=signal[:n]*1.07
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(RATE)
        f.writeframes(np.int16(np.clip(out,-1,1)*32767).tobytes())


def render_segment(entry,index,sources,graphics,segments,width,height,checks):
    target=segments/f'{index:03d}.mp4';frames=entry['end_frame']-entry['start_frame'];duration=frames/FPS
    cmd=['ffmpeg','-y','-v','error','-threads','2'];sid=entry['id'];variant=entry['variant']
    if entry['kind'] in ('graphic','archive'):
        picture=archive_image(variant,graphics) if entry['kind']=='archive' else card_image(sid,variant,graphics)
        cmd+=['-loop','1','-framerate',str(FPS),'-i',str(picture)]
        # Restrained paper drift rather than a static slide or artificial fast transition.
        vf=f"scale={width}:{height},zoompan=z='min(1.025,1+0.00011*on)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={FPS}"
    else:
        source=sources/(sid+'.mp4');info=checks[sid]
        length=info['duration'];a=.12;b=length-.12
        if variant=='portrait_a':a=.05;b=length/2
        elif variant=='portrait_b':a=length/2;b=length-.04
        elif sid=='S06' and variant=='fingerprint_b':a=3.2;b=min(length-.08,6.4)
        elif sid=='S06':a=.12;b=min(3.05,length-.12)
        # Windows chosen after inspecting the real generated contact sheets.
        # Avoid the late leaf-like pattern on the envelope and late invented text.
        if sid=='S21':a=3.8;b=length-.12  # Use the receiver-lifting action, not the static lead-in.
        if sid=='S13':a=1.4;b=length-.12  # Keep only the reviewed rear-view portion.
        if sid=='S17':a=0.0;b=min(2.0,length)
        if sid=='S25':a=0.0;b=min(2.7,length)
        if sid=='S12':a=0.0;b=min(2.15,length)
        available=b-a
        take=min(available,duration)
        factor=duration/take
        if factor>1.33:raise RuntimeError(f'{sid}/{variant}: requires excessive slow motion ({factor:.2f})')
        cmd+=['-ss',f'{a:.6f}','-t',f'{take:.6f}','-i',str(source)]
        tighter=''
        if sid=='S02':
            cw=math.floor(info['width']/1.24/2)*2;ch=math.floor(info['height']/1.24/2)*2
            cy=max(0,round(info['height']*.43-ch/2))
            tighter=f'crop={cw}:{ch}:0:{cy},'
        vf=(f'setpts=(PTS-STARTPTS)*{factor:.9f},'+tighter+f'scale={width}:{height}:force_original_aspect_ratio=increase,'
            f'crop={width}:{height},setsar=1,fps={FPS},eq=saturation=0.92:contrast=1.025:brightness=-0.006,'
            f'tpad=stop_mode=clone:stop_duration=0.2,trim=end_frame={frames}')
        entry.update(source_in=a,source_out=a+take,time_stretch=factor)
    if entry['start_frame']==0:vf+=',fade=t=in:st=0:d=0.25'
    if sid=='END':vf+=f',fade=t=in:st=0:d=0.2,fade=t=out:st={duration-.8:.6f}:d=0.8'
    if sid=='S30':vf+=f',fade=t=out:st={duration-.18:.6f}:d=0.18'
    if sid=='S06':
        overlay=fingerprint_overlay(graphics,width,height)
        cmd+=['-loop','1','-framerate',str(FPS),'-i',str(overlay),'-filter_complex_threads','1',
              '-filter_complex',f'[0:v]{vf},boxblur=18:2[under];[1:v]format=rgba[diagram];[under][diagram]overlay=shortest=1,format=yuv420p[fixed]',
              '-map','[fixed]']
        entry['visual_correction']='Generated pattern obscured; explicitly labeled generic fingerprint diagram added'
    else:cmd+=['-vf',vf+',format=yuv420p']
    cmd+=['-an','-frames:v',str(frames),'-c:v','libx264','-preset','veryfast',
          '-crf','21','-maxrate','4000k','-bufsize','8000k','-r',str(FPS),'-g','60','-pix_fmt','yuv420p',str(target)]
    run(cmd);return target


def mix_audio(narration,music,sfx,path,report_path=None):
    """Build the soundtrack with the measured, deterministic mixer.

    The previous single-graph ffmpeg mix (adelay/amix/sidechaincompress/
    loudnorm) was never verified by measurement, so an inaudible result could
    pass every delivery gate. ``build_audio`` mixes in numpy and refuses to
    return a soundtrack it cannot measure as audible.
    """
    return build_soundtrack(narration,music,sfx,path,duration=DURATION,report_path=report_path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sources',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--project',type=Path,default=HERE/'story.json')
    parser.add_argument('--results',type=Path,default=HERE/'results.json')
    parser.add_argument('--audio',type=Path,default=HERE/'audio')
    parser.add_argument('--width',type=int,default=1920)
    parser.add_argument('--height',type=int,default=1080)
    parser.add_argument('--skip-asr',action='store_true',help='Use labeled pause-aware caption timing (for offline smoke tests)')
    args=parser.parse_args();work=args.work;work.mkdir(parents=True,exist_ok=True)
    project=json.loads(args.project.read_text());results=json.loads(args.results.read_text())
    if results.get('model')!='agnes-video-v2.0':raise RuntimeError('Only the requested Agnes model is allowed')
    from generate import request_hash
    audio_manifest=json.loads((args.audio/'manifest.json').read_text())
    checks={}
    for shot in project['shots']:
        if shot['kind']!='agnes':continue
        sid=shot['id'];source=args.sources/(sid+'.mp4');receipt=results['shots'].get(sid,{})
        if (receipt.get('status')!='completed' or receipt.get('request_hash')!=request_hash(project,shot)
                or not source.exists() or digest(source)!=receipt.get('sha256')):
            raise RuntimeError(f'Missing or unverified Agnes footage: {sid}; refusing to substitute an image/slideshow')
        checks[sid]=probe(source)
    narration,waves=audio_layout(project['chapters'],args.audio,work,audio_manifest)
    edl=make_edl(project,narration)
    from align_audio import transcribe_on_runner, aligned_cues
    asr={} if args.skip_asr else transcribe_on_runner(narration,work)
    cues=[];alignment=[]
    for row,samples in zip(narration,waves):
        aligned=None;coverage=0.0
        if row['id'] in asr:
            aligned,coverage=aligned_cues(row,caption_clauses(row['text']),asr[row['id']]['words'])
        cues.extend(aligned if aligned else captions_for(row,samples))
        alignment.append({'id':row['id'],'method':'ASR-assisted' if aligned else 'pause-aware estimate',
                          'character_match_coverage':coverage})
    (work/'alignment-report.json').write_text(json.dumps(alignment,ensure_ascii=False,indent=2))
    subtitle=work/'captions.ass';write_subtitles(subtitle,cues,edl)
    (work/'caption-timing.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2))
    segments=work/'segments';segments.mkdir(exist_ok=True)
    outputs=[]
    for i,entry in enumerate(edl):
        outputs.append(render_segment(entry,i,args.sources,work/'graphics',segments,args.width,args.height,checks))
        print(f'RENDER_SEGMENT {i+1}/{len(edl)} {entry["id"]}',flush=True)
    concat=work/'concat.txt';concat.write_text(''.join(f"file '{p.resolve().as_posix()}'\n" for p in outputs))
    image_track=work/'image-track.mp4'
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',concat,'-c','copy',image_track])
    sys.path.insert(0,str(ROOT/'电影解说工具包'))
    from generate_horror_bgm import generate_horror_bgm
    music=work/'score.wav';generate_horror_bgm(music,DURATION)
    effects=work/'effects.wav';write_sfx(effects,edl)
    mixed=work/'mix.wav'
    mix_report=mix_audio(narration,music,effects,mixed,report_path=work/'audio-report.json')
    print('SOUNDTRACK_MEASURED '+json.dumps({k:mix_report[k] for k in
          ('rms_dbfs','peak_dbfs','silent_fraction')},ensure_ascii=False),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    font_directory=find_font().parent
    vf=f"subtitles=filename='{subtitle.resolve().as_posix()}':fontsdir='{font_directory.as_posix()}'"
    run(['ffmpeg','-y','-v','error','-threads','2','-i',image_track,'-i',mixed,'-map','0:v:0','-map','1:a:0',
         '-vf',vf,'-c:v','libx264','-preset','fast','-crf','21','-maxrate','4000k','-bufsize','8000k',
         '-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','160k','-ar','48000','-t','180',
         '-movflags','+faststart',args.output])
    info=probe(args.output)
    if (abs(info['duration']-180)>.12 or info.get('audio_channels')!=2 or info.get('frames')!=5400
            or info.get('width')!=args.width or info.get('height')!=args.height or abs(info.get('fps',0)-30)>.01):
        raise RuntimeError(f'Final technical validation failed: {info}')
    run(['ffmpeg','-v','error','-threads','2','-i',args.output,'-map','0:v:0','-map','0:a:0','-f','null','-'])
    # Listening gate: the delivered MP4 must measure as audible, not merely
    # carry an AAC stream. This is what the first cut never checked.
    final_audio=measure(args.output,chapters=narration)
    final_audio['measured_on']='delivered mp4'
    (work/'final-audio-report.json').write_text(json.dumps(final_audio,ensure_ascii=False,indent=2)+'\n')
    try:
        assert_audible(final_audio)
    except Exception as exc:
        raise RuntimeError(f'Delivered video is not audibly mixed: {exc}') from exc
    print('FINAL_AUDIO_MEASURED '+json.dumps({k:final_audio[k] for k in
          ('rms_dbfs','peak_dbfs','silent_fraction','quietest_window_dbfs')},ensure_ascii=False),flush=True)
    preview=work/'final-contact.jpg'
    run(['ffmpeg','-y','-v','error','-i',args.output,'-vf','fps=1/6,scale=320:180,tile=5x6',
         '-frames:v','1','-q:v','3',preview])
    technical={**info,'sha256':digest(args.output),'decoded_ok':True,'status':'audio_verified_cut',
               'visual_review':'pending','caption_alignment':alignment,
               'narration_voice_id':audio_manifest['voice_id'],'narration_tempo':narration[0]['tempo'],
               'editorial_segments':len(edl),'source_clips':len(checks),'archival_portrait':True,
               'output':args.output.name,
               'soundtrack_mix':{k:mix_report[k] for k in
                                 ('rms_dbfs','peak_dbfs','silent_fraction','target_rms_dbfs')},
               'delivered_audio':{k:final_audio[k] for k in
                                  ('rms_dbfs','peak_dbfs','silent_fraction','quietest_window_dbfs')},
               'audio_listening_review':'measured (level + per-chapter + silence gate); '
                                        'not a substitute for human word-level listening',
               'note':'Audio is measured as audible on the delivered file; visual and '
                      'word-level review are still pending, so this is not a final sign-off.'}
    (work/'technical-report.json').write_text(json.dumps(technical,ensure_ascii=False,indent=2)+'\n')
    (work/'edit-decision-list.json').write_text(json.dumps(edl,ensure_ascii=False,indent=2)+'\n')
    (work/'narration-timing.json').write_text(json.dumps(narration,ensure_ascii=False,indent=2)+'\n')
    print('RENDER_COMPLETE '+json.dumps(technical,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
