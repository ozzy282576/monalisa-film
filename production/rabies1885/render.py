#!/usr/bin/env python3
"""狂犬病疫苗：一百四十年前那场赌局 —— 确定性三分钟成片（模板由 production/templates/render.py 生成，内容不写在这里）。

只接受 results.json 里登记过、SHA-256 对得上的 Agnes 动画片段 + 六段收紧后的配音；
缺任何一段都直接报错，绝不用静帧/幻灯片顶替。输出成片、EDL、字幕、音频测量报告和 QA 接触表。

本文件里只有两样东西是"这部片子的"：``CUTS``（切点，按 audio/clause-times.json 对出来）和
``WINDOWS`` / ``TIGHTER_CROPS``（看片后的镜头修正）。信息卡文案、片头/片尾卡、字幕高亮词、
逐镜标签、音效事件全部从 story.json 的 ``presentation`` 块读（由 build_story.py 写入），
所以 build_story.py 是唯一的内容源。
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
END_CARD = 6.0      # 片尾卡时长：与 OUTRO 一致，旁白结束后完整静置六秒；见 make_edl
END_AT = DURATION - END_CARD
TOTAL_FRAMES = round(DURATION * FPS)
# 切点 = 收紧后配音（audio/N0x.mp3）里的秒数，取自 clause_times.py 对出来的分句边界
# （每个切点都要落在分句起点前的 0.35 s 停顿窗里：[clause_start-0.35, clause_start]，用
#  `python3 production/rabies1885/clause_times.py --check-cuts` 校验）。
# 镜头按成片顺序编号，每个镜头只出现一次（make_edl 有断言守着）。
# 脚手架给的是 4 秒均匀网格，只是起点；拿到配音后必须按 clause-times 重对。
CUTS = {
    'N01': [(0,'S01',''), (3.30,'S02',''), (5.00,'S03',''), (8.90,'S04',''), (10.20,'S05',''), (12.10,'S06',''), (15.10,'S07',''), (19.10,'S08','')],
    'N02': [(0,'S09',''), (4.70,'S10',''), (10.80,'S11',''), (15.20,'S12',''), (19.00,'S13',''), (22.30,'S14',''), (24.20,'S15','')],
    'N03': [(0,'S16',''), (1.80,'S17',''), (5.30,'S18',''), (9.10,'S19',''), (11.30,'S20',''), (13.80,'S21',''), (16.20,'S22',''), (19.00,'S23','')],
    'N04': [(0,'S24',''), (1.15,'S25',''), (4.80,'S26',''), (8.00,'S27',''), (10.00,'S28',''), (14.50,'S29',''), (16.50,'S30','')],
    'N05': [(0,'S31',''), (1.00,'S32',''), (4.00,'S33',''), (5.80,'S34',''), (8.45,'S35',''), (12.35,'S36',''), (14.60,'S37',''), (16.50,'S38','')],
    'N06': [(0,'S39',''), (3.90,'S40',''), (6.55,'S41',''), (9.20,'S42',''), (15.70,'S43',''), (17.80,'S44',''), (24.56,'S45','')],
}

# 看片后的镜头修正。S22 的源片后段让背影略微转向，故只取始终背对镜头、
# 蓝灰夜景与烛光都可辨的前 4.3 秒；4.7 秒成片段仅作 1.12×平滑延时。
# S18 的源片在约 3.5 秒才完整落到下腿绷带；从 1.1 秒开始取景，保留开头肩上单手，
# 同时让绷带在最终镜头后半段有明确、可读的停留，不让它只在切出前一闪而过。
WINDOWS = {'S22': (0.12, 4.3), 'S18': (1.10, 5.00)}
# 看片后只裁掉已确认的边缘/后段越界内容；不伪造画面、也不替换源片。
# S02 provider still exposed an unintended dial; retain only its lower pendulum compartment.
# S18 的重新生成已到达下腿绷带，但左缘带入成人躯干；裁掉躯干边缘，保留单手与绷带。
# S45 的源片在后段拉远露出房间；居中下方裁取持续只有针管、无字疫苗瓶和桌面的区域。
TIGHTER_CROPS = {
    'S02': (3.4, 0.50, 0.80),
    'S18': (1.20, 0.64, 0.55),
    'S45': (1.60, 0.50, 0.69),
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


# 卡片安全排字宽度：1920 宽的画面两侧各留 130 px；信息卡还要落在纸面 (184–1736) 之内。
# 2026-10-06 实测：片尾卡问句「医学史最该被记住的，是勇气，还是验证勇气的证据？」按 96 px
# 排出来约 2304 px 宽，两端各被裁掉约两个字（成片 174–180 s 可见）——自动审计只量帧间差异、
# 黑帧和冻结，从不量文字有没有溢出画面，所以只有排字闸门或人眼能发现。
CARD_TEXT_MAX_WIDTH = 1660
CARD_PAPER_TEXT_MAX_WIDTH = 1500


def text_width(draw, text, size, serif=False):
    box=draw.textbbox((0,0),text,font=font(size,serif))
    return box[2]-box[0]


def fit_size(draw, text, size, max_width, serif=False, floor=20):
    """把一行字缩到 max_width 以内；缩到 floor 仍放不下就报错，绝不画出被裁掉的文字。"""
    width=text_width(draw,text,size,serif)
    if width<=max_width:return size
    guess=max(floor,int(size*max_width/width))
    while guess>floor and text_width(draw,text,guess,serif)>max_width:guess-=1
    if text_width(draw,text,guess,serif)>max_width:
        raise RuntimeError(f'卡片文案一行放不下，缩到 {floor}px 仍然超出 {max_width}px：{text!r}')
    return guess


def centered(draw, text, y, size, color, x=960, serif=False, max_width=CARD_TEXT_MAX_WIDTH):
    size=fit_size(draw,text,size,max_width,serif)
    f=font(size,serif); box=draw.textbbox((0,0),text,font=f)
    draw.text((x-(box[2]-box[0])/2,y),text,font=f,fill=color)


def card_image(sid, variant, directory, presentation):
    directory.mkdir(parents=True,exist_ok=True)
    dest=directory/f'{sid}-{variant or "base"}.jpg'
    if dest.exists():return dest
    rng=np.random.default_rng(2023+int(sid[1:]) if sid.startswith("S") else 2023)
    y,x=np.mgrid[0:1080,0:1920]
    glow=np.clip(1-((x-940)/1200)**2-((y-510)/850)**2,0,1)
    grain=rng.normal(0,1.2,(1080,1920))
    bg=np.stack([22+glow*16+grain,25+glow*15+grain,24+glow*10+grain],axis=-1)
    im=Image.fromarray(np.uint8(np.clip(bg,0,255)),'RGB');d=ImageDraw.Draw(im)
    if sid=='END':
        lines=presentation.get('end_card') or []
        if len(lines)<2:raise RuntimeError('片尾卡缺文案：在 build_story.py 的 END_CARD 里写 2–4 行')
        layout=[(342,96,'#ede8db',True),(498,46,'#b7aa82',False),(668,34,'#a6aaa0',False),(895,21,'#7f897d',False)]
        for line,(y,size,color,serif) in zip(lines,layout):
            centered(d,line,y,size,color,serif=serif)
    else:
        d.rounded_rectangle((169,104,1751,954),radius=6,fill='#0d1210')
        # Physical-paper palette connects the cards to the generated walnut desks and case folders.
        paper=np.stack([218+grain,212+grain,192+grain],axis=-1)
        patch=Image.fromarray(np.uint8(np.clip(paper[119:939,184:1736],0,255)),'RGB')
        im.paste(patch,(184,119));d=ImageDraw.Draw(im)
        d.text((265,180),presentation.get('card_header') or '资料卡',font=font(24),fill='#5d6456')
        d.line((265,236,1655,236),fill='#929781',width=2)
        cards=presentation.get('cards') or {}
        if sid not in cards:raise RuntimeError(f'信息卡 {sid} 没有文案：在 build_story.py 的 CARDS 里补 (大标题, 第一行, 第二行)')
        title,line1,line2=cards[sid]
        centered(d,title,302,108,'#2c3a32',serif=True,max_width=CARD_PAPER_TEXT_MAX_WIDTH)
        centered(d,line1,486,49,'#475648',max_width=CARD_PAPER_TEXT_MAX_WIDTH)
        d.line((855,628,1065,628),fill='#958358',width=3)
        centered(d,line2,720,38,'#5c6656',max_width=CARD_PAPER_TEXT_MAX_WIDTH)
        d.text((265,875),presentation.get('card_footer') or '资料摘要与示意图 · 并非原始档案影像',font=font(21),fill='#75806c')
    im.save(dest,quality=93)
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


CLAUSE_TIMES=Path(__file__).with_name('audio')/'clause-times.json'


def captions_from_clause_times(row):
    """clause_times.py 对出来的分句边界（能量包络 DP + 停顿吸附，audio/clause-times.json）。

    与 N03 的 whisper 词级时间互相印证到 ±0.15 s；比 captions_for 的按字数比例估计准
    （后者在 N05 里最多早了 1.8 s）。对不上（分句文本改过、音频时长变了）就返回 None，退回估计。"""
    if not CLAUSE_TIMES.exists():return None
    entry=json.loads(CLAUSE_TIMES.read_text()).get(row['id'])
    if not entry or abs(float(entry['duration'])-row['raw_duration'])>.06:return None
    strip=lambda t:re.sub(r'[^\u3400-\u9fffA-Za-z0-9]','',t)
    pieces=[(strip(c['text']),float(c['start']),float(c['end'])) for c in entry['clauses']]
    spans=[];pointer=0
    for text in caption_clauses(row['text']):
        key=strip(text)
        if not key:continue
        consumed='';a=b=None
        while pointer<len(pieces) and len(consumed)<len(key):
            piece,start,end=pieces[pointer]
            if not key.startswith(consumed+piece):return None
            consumed+=piece;a=start if a is None else a;b=end;pointer+=1
        if consumed!=key:return None
        spans.append((text,a,b))
    if pointer!=len(pieces):return None
    cues=[];last_end=row['start']
    for i,(text,a,b) in enumerate(spans):
        start=max(last_end,row['start']+max(0,a-.09)/row['tempo'])
        end=row['start']+min(row['raw_duration'],b+.15)/row['tempo']
        if i+1<len(spans):end=min(end,row['start']+max(0,spans[i+1][1]-.09)/row['tempo'])
        if end<=start:return None
        cues.append({'start':start,'end':end,'text':text});last_end=end
    return cues


MIN_CAPTION_SECONDS=1.0   # 短句（「恐水、」「治，」）按 ASR 边界只有 0.4–0.7 秒，来不及读
CAPTION_GAP=0.05          # 相邻两条之间至少留 50 ms，避免叠字


def merge_short_captions(cues,short=1.2,max_chars=20,max_seconds=4.0,max_gap=0.4):
    """把连着出现的短句并成一条：「恐水、」「痉挛、」「窒息，」各 0.6 秒不如合成一条 2 秒。

    判断用的是**原始**时长，不是并过之后的时长——否则并到一半自己变长了，
    后面的短句就吞不进来了。只在间隔短、字数够、总时长够短时才并，
    所以跨章之间那 1 秒静音天然把两章隔开。
    """
    visible=lambda t:re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]','',t)
    durs=[c['end']-c['start'] for c in cues]
    out=[];i=0
    while i<len(cues):
        j=i;text=cues[i]['text']
        while (durs[i]<short and j+1<len(cues) and durs[j+1]<short
               and 0<=cues[j+1]['start']-cues[j]['end']<max_gap
               and len(visible(text+cues[j+1]['text']))<=max_chars
               and cues[j+1]['end']-cues[i]['start']<=max_seconds):
            j+=1;text+=cues[j]['text']
        out.append({'start':cues[i]['start'],'end':cues[j]['end'],'text':text})
        i=j+1
    return out


def enforce_min_duration(cues,minimum=MIN_CAPTION_SECONDS,gap=CAPTION_GAP,borrow=0.3):
    """把每条字幕撑到至少 ``minimum`` 秒，三次机会，每次都不许把邻居压垮：

    1. 往后延，但不能压到下一条的起点；
    2. 不够就往前借，但不能压到上一条的终点；
    3. 还不够就让长邻居各让出最多 ``borrow`` 秒（长句少显示 0.3 秒无感，
       短句从 0.4 秒变成 1 秒才读得完）。
    """
    for i,cue in enumerate(cues):
        if cue['end']-cue['start']>=minimum:continue
        limit=(cues[i+1]['start']-gap) if i+1<len(cues) else cue['end']+1.0
        floor=(cues[i-1]['end']+gap) if i>0 else 0.0
        end=min(limit,cue['start']+minimum)
        start=max(floor,min(cue['start'],end-minimum))
        shortfall=minimum-(end-start)
        if shortfall>0 and i+1<len(cues):
            room=(cues[i+1]['end']-cues[i+1]['start'])-0.4
            take=min(shortfall,room,borrow)
            if take>0:cues[i+1]['start']+=take;end+=take;shortfall-=take
        if shortfall>0 and i>0:
            room=(cues[i-1]['end']-cues[i-1]['start'])-0.4
            take=min(shortfall,room,borrow)
            if take>0:cues[i-1]['end']-=take;start-=take
        cue['start'],cue['end']=start,max(end,start+0.2)
    return cues


def make_edl(project, narration):
    by_id={s['id']:s for s in project['shots']};edl=[]
    for i,row in enumerate(narration):
        entries=CUTS[row['id']]
        chapter_end=narration[i+1]['start'] if i+1<len(narration) else END_AT
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
    edl.append({'id':'END','kind':'graphic','variant':'','start_frame':round(END_AT*FPS),'end_frame':TOTAL_FRAMES,
                'narration_id':narration[-1]['id'],'purpose':'片尾卡：把互动问题留在屏幕上，附资料来源'})
    if edl[0]['start_frame']!=0 or edl[-1]['end_frame']!=TOTAL_FRAMES:raise RuntimeError('EDL duration is not 180s')
    used=[e['id'] for e in edl if e['id']!='END']
    if len(used)!=len(set(used)):raise RuntimeError('本片规定每个镜头只用一次，CUTS 里有重复镜头: '+
                                                   ','.join(sorted({x for x in used if used.count(x)>1})))
    if set(used)!=set(by_id):raise RuntimeError('CUTS 没有用到全部镜头: '+','.join(sorted(set(by_id)-set(used))))
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


def write_subtitles(path,cues,edl,presentation):
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
        for key in presentation.get('caption_keywords') or []:
            if key in caption:caption=caption.replace(key,r'{\c&H0076DDF2&}'+key+r'{\c&H00FFFFFF&}')
        text+=f"Dialogue: 1,{ass_time(cue['start'])},{ass_time(cue['end'])},Caption,,0,0,0,,{{\\q2\\fad(45,45)}}{caption}\n"
    for entry in edl:
        if entry['id']=='END':continue
        label={'agnes':'AI动画情景重现 · 非新闻影像','archive':'档案照片',
               'graphic':'资料摘要与示意图 · 非原始档案'}[entry['kind']]
        label=(presentation.get('label_overrides') or {}).get(entry['id'],label)
        text+=f"Dialogue: 0,{ass_time(entry['start_frame']/FPS)},{ass_time(entry['end_frame']/FPS)},Label,,0,0,0,,{label}\n"
    title_lines=[safe_text(x) for x in (presentation.get('title_card') or []) if x]
    if title_lines:
        first=title_lines[0];rest=('\\N{\\fs41\\fsp6}'+title_lines[1]) if len(title_lines)>1 else ''
        text+=f'Dialogue: 2,0:00:00.35,0:00:04.70,Title,,0,0,0,,{{\\fad(500,550)}}{first}{rest}\n'
    path.write_text(text)
    srt=path.with_suffix('.srt')
    def clock(s):
        ms=round(s*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);sec,ms=divmod(ms,1000)
        return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'
    srt.write_text('\n'.join(f"{i}\n{clock(c['start'])} --> {clock(c['end'])}\n{c['text']}\n" for i,c in enumerate(cues,1)))


def write_sfx(path,edl,presentation):
    rng=np.random.default_rng(20260921);out=np.zeros((round(DURATION*RATE),2),dtype=np.float32)
    events=[]
    for source,kind in presentation.get('sfx_events') or []:
        if kind not in ('paper','machine','press','phone','keys'):raise RuntimeError(f'未知音效类型 {kind}（可用：paper/machine/press/phone/keys）')
        first=next((e for e in edl if e['id']==source),None)
        if first is None:raise RuntimeError(f'音效事件指向不存在的镜头 {source}')
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


def render_segment(entry,index,sources,graphics,segments,width,height,checks,presentation,last_shot):
    target=segments/f'{index:03d}.mp4';frames=entry['end_frame']-entry['start_frame'];duration=frames/FPS
    cmd=['ffmpeg','-y','-v','error','-threads','2'];sid=entry['id'];variant=entry['variant']
    if entry['kind'] in ('graphic','archive'):
        if entry['kind']=='archive':raise RuntimeError('这条流水线不支持档案照片镜头：所有画面都是 Agnes 动画或信息卡（要用档案照片请照 production/dahlia 的 archive_image 加）')
        picture=card_image(sid,variant,graphics,presentation)
        cmd+=['-loop','1','-framerate',str(FPS),'-i',str(picture)]
        # Restrained paper drift rather than a static slide or artificial fast transition.
        vf=f"scale={width}:{height},zoompan=z='min(1.025,1+0.00011*on)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={FPS}"
    else:
        source=sources/(sid+'.mp4');info=checks[sid]
        length=info['duration'];a=.12;b=length-.12
        # 本片的镜头时间窗：默认整段可用；看过 qa/ 接触表后若某镜头前/后段有畸变，在 WINDOWS 里收窄。
        if sid in WINDOWS:
            wa,wb=WINDOWS[sid];a=max(a,wa);b=min(b,wb if wb is not None else b)
        available=b-a
        take=min(available,duration)
        factor=duration/take
        if factor>1.33:raise RuntimeError(f'{sid}/{variant}: requires excessive slow motion ({factor:.2f})')
        cmd+=['-ss',f'{a:.6f}','-t',f'{take:.6f}','-i',str(source)]
        tighter=''
        if sid in TIGHTER_CROPS:
            # 轻微推近，裁掉画面边缘的问题区域（比例 1.15–1.3），中心点按 (cx,cy) 比例给
            zoom,cx,cy=TIGHTER_CROPS[sid]
            cw=math.floor(info['width']/zoom/2)*2;ch=math.floor(info['height']/zoom/2)*2
            x0=min(max(0,round(info['width']*cx-cw/2)),info['width']-cw);y0=min(max(0,round(info['height']*cy-ch/2)),info['height']-ch)
            tighter=f'crop={cw}:{ch}:{x0}:{y0},'
        vf=(f'setpts=(PTS-STARTPTS)*{factor:.9f},'+tighter+f'scale={width}:{height}:force_original_aspect_ratio=increase,'
            f'crop={width}:{height},setsar=1,fps={FPS},eq=saturation=0.92:contrast=1.025:brightness=-0.006,'
            f'tpad=stop_mode=clone:stop_duration=0.2,trim=end_frame={frames}')
        entry.update(source_in=a,source_out=a+take,time_stretch=factor)
    if entry['start_frame']==0:vf+=',fade=t=in:st=0:d=0.25'
    if sid=='END':vf+=f',fade=t=in:st=0:d=0.2,fade=t=out:st={duration-.8:.6f}:d=0.8'
    if sid==last_shot:vf+=f',fade=t=out:st={duration-.18:.6f}:d=0.18'
    cmd+=['-vf',vf+',format=yuv420p']
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
    presentation=project.get('presentation') or {}
    if not presentation.get('cards') and any(s['kind']=='graphic' for s in project['shots']):
        raise RuntimeError('story.json 缺 presentation.cards：先在 build_story.py 里写 CARDS 再跑 build()')
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
        clause_timed=None if aligned else captions_from_clause_times(row)
        cues.extend(aligned or clause_timed or captions_for(row,samples))
        alignment.append({'id':row['id'],
                          'method':'ASR-assisted' if aligned else 'clause-times DP' if clause_timed else 'pause-aware estimate',
                          'character_match_coverage':coverage})
    cues=enforce_min_duration(merge_short_captions(cues))
    (work/'alignment-report.json').write_text(json.dumps(alignment,ensure_ascii=False,indent=2))
    subtitle=work/'captions.ass';write_subtitles(subtitle,cues,edl,presentation)
    (work/'caption-timing.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2))
    segments=work/'segments';segments.mkdir(exist_ok=True)
    outputs=[];last_shot=edl[-2]['id']
    for i,entry in enumerate(edl):
        outputs.append(render_segment(entry,i,args.sources,work/'graphics',segments,args.width,args.height,checks,presentation,last_shot))
        print(f'RENDER_SEGMENT {i+1}/{len(edl)} {entry["id"]}',flush=True)
    concat=work/'concat.txt';concat.write_text(''.join(f"file '{p.resolve().as_posix()}'\n" for p in outputs))
    image_track=work/'image-track.mp4'
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',concat,'-c','copy',image_track])
    sys.path.insert(0,str(ROOT/'电影解说工具包'))
    from generate_horror_bgm import generate_horror_bgm
    music=work/'score.wav';generate_horror_bgm(music,DURATION)
    effects=work/'effects.wav';write_sfx(effects,edl,presentation)
    mixed=work/'mix.wav'
    mix_report=mix_audio(narration,music,effects,mixed,report_path=work/'audio-report.json')
    print('SOUNDTRACK_MEASURED '+json.dumps({k:mix_report[k] for k in
          ('rms_dbfs','peak_dbfs','silent_fraction')},ensure_ascii=False),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    font_directory=find_font().parent
    vf=f"subtitles=filename='{subtitle.resolve().as_posix()}':fontsdir='{font_directory.as_posix()}'"
    run(['ffmpeg','-y','-v','error','-threads','2','-i',image_track,'-i',mixed,'-map','0:v:0','-map','1:a:0',
         '-vf',vf,'-c:v','libx264','-preset','fast','-crf','21','-maxrate','4000k','-bufsize','8000k',
         '-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','160k','-ar','48000','-t',f'{DURATION:g}',
         '-movflags','+faststart',args.output])
    info=probe(args.output)
    if (abs(info['duration']-DURATION)>.12 or info.get('audio_channels')!=2 or info.get('frames')!=TOTAL_FRAMES
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
               'editorial_segments':len(edl),'source_clips':len(checks),'archival_portrait':False,'unique_shots_no_reuse':True,
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
