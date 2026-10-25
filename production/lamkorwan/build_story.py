#!/usr/bin/env python3
"""《雨夜屠夫林过云：一卷菲林里的四条人命》的全部内容源：解说词、45 镜分镜、信息卡文案、字幕高亮词、发布文案。

这是这部片子**唯一需要动脑写的文件**（模板来自 production/templates/build_story.py，
样板是 production/rabies1885/build_story.py —— 一部出片、听检、全帧 QC 与人工语义签收都跑完的成片）。

用法::

    python3 production/lamkorwan/build_story.py            # 写 story.json（含 presentation 块）+ audio/manifest.json 的逐字文本
    python3 production/lamkorwan/build_story.py --script   # 生成 抖音脚本.md（3 标题 / 核心爆点 / 四列分镜表 / 金句）
    python3 production/lamkorwan/build_story.py --publish  # 生成 抖音发布文案.md（标题 / 介绍 / 提问读者一句话 / 话题）

本片内容边界（用户上传的文案 + 公开报道核对后的版本）：

- 事实以 HK01、思考香港、NOWnews、香港教育城阅读平台、百度百科「雨夜屠夫案」等公开报道为准，
  每条都能指到下面 SOURCES 里的一个链接；来源之间打架的细节（被捕日 17/18 日、冲印店在尖沙咀还是旺角、
  发现照片的具体日子）在片中一律用「八月」「尖沙咀一间相铺」这类不会写错的写法，差异记在 事实边界 里。
- 画面是「写实 3D 动画情景重现」，不是图片轮播；凶嫌只以背影、剪影、手出现；受害者不以任何人像出现；
  不展示遗体、血腥或侵害过程，不重演作案。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "story.json"
MANIFEST = HERE / "audio" / "manifest.json"

TITLE = "雨夜屠夫林过云：一卷菲林里的四条人命"

# 全片统一的画面风格前缀（英文）。用户要求「真实 3D 动画」而不是图片视频，
# 所以这里钉死写实向的 CGI 情景重现，而不是 2D 手绘；后半句
# （人物只给背影/剪影/手、无文字、单一运镜）是流水线规则，别删。
# 注意：style_prefix 参与全部 Agnes 镜头的 request_hash，开工后改一个字 = 38 镜全部重做。
STYLE_PREFIX = (
    "Photorealistic cinematic 3D animated reenactment, high-end CGI feature-film render (volumetric light, "
    "physically based materials, shallow depth of field, subtle 35mm film grain) of Hong Kong in 1982: "
    "rain-soaked neon streets, period-correct 1980s taxis, saloon cars, shopfronts and interiors, humid air, "
    "wet asphalt and puddle reflections, sodium street lamps and coloured neon as practical lights, restrained "
    "cold teal and amber colour grading, slow-burn true-crime documentary mood, not stylised, not a drawing, "
    "not a cartoon; horizontal 16:9 widescreen cinematic composition; every character is shown only from behind, "
    "in silhouette, or as hands and props - never a clear frontal face, never a recognisable likeness; absolutely "
    "no readable text, letters, numbers, logos, license plates or brand marks anywhere inside the frame; one "
    "single continuous smooth slow camera move per shot exactly as directed. "
)

NEGATIVE_PROMPT = (
    "readable text, letters, numbers, words, signage writing, invented headlines, logos, brand marks, watermark, "
    "subtitles, on-screen caption, photorealistic frontal face, recognizable real person likeness, face close-up, "
    "detailed eyes, flat 2D cartoon, cel-shaded illustration, hand-drawn sketch, watercolour, comic panel, "
    "low-poly, waxy plastic skin, doll-like figure, blood, gore, wound, corpse, body bag, body parts, dismemberment, "
    "autopsy, surgery, weapon attack, strangling, assault, violence, nudity, erotic content, horror monster, ghost, "
    "jump scare, distorted anatomy, deformed hands, extra fingers, extra limbs, duplicated people, changing face, "
    "morphing objects, teleportation, jitter, flicker, whip pan, fast zoom, jump cut, split screen, collage"
)

# 事实边界与红线：每一条都会印在 抖音脚本.md 的「发布前自查」里。
PRINCIPLES = [
    "全部 Agnes 镜头为写实 3D 动画情景重现，画面常驻标注「AI动画情景重现 · 非新闻影像」，不冒充庭审、监控、档案或证物照片",
    "不展示遗体、血腥或侵害过程；不重现作案动作；杀害方式只写到「勒死」这一层，不写细节",
    "凶嫌林过云只以背影、剪影、手部出现，不用 AI 生成的脸冒充本人；画面里不出现可辨识的真人面孔",
    "四名受害者不以任何人像出现，只用信息卡与象征物致意；姓名与年龄只写在信息卡和字幕里",
    "每一句事实都能指到 sources 里的一条公开报道；来源冲突的细节用不会写错的写法（例如「八月」而不是具体某日）",
    "一九八三年四月八日的裁决是「四项谋杀罪名成立、判处死刑（依例绞刑）」，一九八四年八月由港督会同行政局赦免死刑、改判终身监禁；本片不说「已释放」或「已出狱」",
    "所有中文姓名、日期、字幕后期添加，不交给视频模型拼写",
    "人工检视 qa/ 接触表，露脸、畸变、伪文字、中途换场的镜头用 {\"only\":\"Sxx\"} 重生成，不直接进成片",
]

# 每条事实的公开来源。usage 写清「这条来源支撑了哪几句话」。
SOURCES = [
    {"id": 1, "url": "https://www.hk01.com/熱爆話題/142876/",
     "usage": "支撑：四名受害人的年龄与职业（二十二岁陈凤兰、三十一岁收银员陈云洁、二十九岁清洁工梁秀云、十七岁学生梁惠心）；"
              "冲印公司职员发现菲林相片可疑后报警、警方在尖沙咀冲印店埋伏等林过云取相时拘捕；"
              "到土瓜湾单位搜出女性器官标本、人体特写相片、肢解过程录影带；四项谋杀罪成、死刑、后改终身监禁、现时仍在服刑"},
    {"id": 2, "url": "https://www.thinkhk.com/article/2018-02/12/25498.html",
     "usage": "支撑：一九八二年二月三日凌晨林过云将陈凤兰载回土瓜湾住所勒死、肢解、留性器官制成标本，其余部分弃于城门河一带；"
              "同年五月至七月三度犯案；冲印公司职员认出影像与肢解案有关后报警；一九八二年八月十八日拘捕；翌年三月在高等法院开审"},
    {"id": 3, "url": "https://www.nownews.com/news/6094095",
     "usage": "支撑：一九八二年二月十一日警方在沙田城门河发现女性头颅与一双女子手臂，全案曝光；"
              "一九八二年二月至七月共四名女性遇害，作案多在雨夜、以的士载至僻静处；"
              "冲印店职员报警后警方埋伏、八月十八日拘捕；住所搜出女性器官标本、部分残肢、手术器材、照片与录影带及受害人物品；"
              "一九八三年三月三日起开审；五名精神科医生评估后多数认为无明显精神病"},
    {"id": 4, "url": "https://reader.hkedcity.net/bookshelf/4817/OEBPS/Chapter.xhtml",
     "usage": "支撑：因多在雨夜犯案而有「雨夜屠夫」之称；二十七岁的的士司机；一九八二年二月至七月杀害四名女子；"
              "一九八二年八月十八日在冲印店被捕；被判终身监禁"},
    {"id": 5, "url": "https://baike.baidu.com/item/香港奇案实录·雨夜屠夫/12508322",
     "usage": "支撑：案件于一九八三年三月三日起开审、经二十日审讯；四月八日由七名男性组成的陪审团一致通过四项谋杀罪名成立，判处绞刑；"
              "香港自一九六六年十一月十六日后再未执行死刑，故至一九八四年八月由港督会同行政局赦免死刑、改判终身监禁"},
    {"id": 6, "url": "https://factpedia.org/index.php?title=林過雲",
     "usage": "支撑：一九八二年二月三日、五月二十九日、六月十七日、七月二日四起案件的日期；"
              "林过云住处无黑房、习惯把菲林拿到尖沙咀冲印店冲洗；放大机故障、底片转到分店人手冲晒后被发现；八月十八日取相时被捕"},
    {"id": 7, "url": "https://zhuanlan.zhihu.com/p/66480044",
     "usage": "支撑：判决时林过云镇定如常；一九八四年八月依惯例改判终身监禁"},
]

# 六段解说：(章节 id, 章节标题, 逐字解说词)。六段合计 ≈ 760–800 字。
CHAPTERS = [
    ("N01", "黄金开头：从城门河里捞起来的东西",
     "一九八二年二月，香港的雨夜。有人从沙田城门河里，捞起一颗人头和一双女人的手臂——这起案子，让整个香港慌了。"
     "但真正钉死凶手的，不是目击者，不是指纹，而是一卷送去冲印店的菲林。今天讲雨夜屠夫林过云：一个夜班出租车司机，和四条人命。"),
    ("N02", "他是谁：土瓜湾旧唐楼里的夜的士司机",
     "林过云，二十七岁，夜班的士司机，住在土瓜湾一栋旧唐楼里。白天他几乎不出现，入夜才开车上街。"
     "凌晨的尖沙咀，搭车的大多是下班回家的女人。从二月到七月，四名女子坐上他的车，再没有下车："
     "二十二岁的陈凤兰，三十一岁的陈云洁，二十九岁的梁秀云，还有十七岁的梁惠心。"),
    ("N03", "四个月，四条人命，和一台摄录机",
     "作案几乎都挑在雨夜。他把车开到僻静处，然后在车里勒死对方。四个月里，香港连着发生四起命案，"
     "警方一开始并不确定它们出自同一双手——因为现场几乎没有留下什么。而林过云做了一件他自以为很聪明的事："
     "他把整个过程拍了下来，照片和录像带，整整齐齐收在家里。"),
    ("N04", "冲印店：坏掉的放大机",
     "转折点是一间冲印店。林过云家里没有暗房，习惯把菲林拿到尖沙咀一间相铺冲洗。一九八二年八月，"
     "他想放大一批相片，偏巧放大机坏了，底片被转到分店，由人手冲晒。店员把照片看清楚的那一刻，"
     "就知道这不是普通摄影——画面里的东西，和报纸上正在报道的那宗案子，太像了。负责人报了警。"),
    ("N05", "他们等的，是他自己回来取相",
     "警方没有立刻上门。他们让店员照常打电话，通知客人来取相——因为底片还在店里，来取的人只能是他。"
     "八月十八日，林过云走进冲印店，埋伏的探员一拥而上。同一天，警方搜查他在土瓜湾贵州街的住所："
     "照片、录像带、手术器材，一件一件被翻出来。四起互不相干的命案，从此串成一条线。"),
    ("N06", "法庭、死刑，和那卷留在证据里的菲林",
     "一九八三年三月，案件在高等法院开审。争的是：他到底有没有精神病。五名精神科医生评估过他，"
     "陪审团最终不接受这个说法。四月八日，四项谋杀罪名成立，判处死刑。但香港多年没有执行死刑——"
     "一九八四年八月，港督会同行政局赦免死刑，改判终身监禁。他想让全世界看见自己的作品，"
     "把他送上法庭的，正是那卷菲林。你觉得，如果那台放大机没有坏，这个案子还会被揭开吗？"),
]

# 每一镜：(id, kind, 运镜, 叙事职责, 衔接方式, 英文提示词 或 信息卡说明, 音效/备注)
# kind = "agnes"（AI 动画）或 "graphic"（信息卡；文案写在下面的 CARDS 里，这里只写它的作用）。
# 45 镜按成片顺序编号 S01–S45，每镜只用一次；本片 38 agnes + 7 张信息卡。
SHOTS = [
    # ---------------- N01（8 镜：7 agnes + 1 卡）----------------
    ("S01", "agnes", "低机位贴水面极慢前推", "开场钩子：雨夜城门河上的勘查灯光", "硬切到九龙街景",
     "Night: rain hammering a river surface beside a low stone embankment outside Sha Tin, 1982; a single police "
     "torch beam sweeps slowly across the black water from left to right, lighting ripples, rain rings and a few "
     "floating reeds; camera skims just above the water and moves forward very slowly. Framed on this one stretch "
     "of water from the first frame to the last; no people, no boats, no bridge, no buildings, no skyline, no "
     "readable text; hold on this single view for the full clip, no cut, no scene change, no camera relocation.",
     "暴雨、水面拍击、远处勘查人声"),
    ("S02", "agnes", "贴地极低机位沿路面缓慢前推", "交代年代与城市：一九八二年的雨夜街面", "雨幕遮挡 → 切",
     "Extreme low night shot in rainy 1982 Hong Kong: the frame is filled edge to edge by rain-lashed black "
     "asphalt, shallow puddles and blurred painted lane markings; heavy rain strikes the road, and a few long "
     "smeared reflections of distant amber light slide slowly across the wet surface; the top edge of the frame "
     "is only rain haze and darkness. The camera sits thirty centimetres above the road and creeps forward very "
     "slowly. Fill the entire frame with road surface and rain haze only; there are no buildings, no shopfronts, "
     "no awnings, no neon, no signboards, no vehicles, no people, no readable text anywhere in the frame; hold on "
     "this single view for the full clip, no cut, no scene change, no camera relocation.",
     "雨声、远处车流、霓虹电流声"),
    ("S03", "agnes", "俯拍缓慢推近木桌上的档案与地图", "警方在查，但线索是散的", "切",
     "Interior of a 1980s Hong Kong police office at night, walls on three sides: a bare bulb over a scarred "
     "wooden desk covered with closed case folders, a folded district map and a black rotary telephone; cigarette "
     "smoke drifts through the light; camera looks down at the desk and pushes in very slowly. Framed on this one "
     "desk from the first frame to the last; no people, no windows, no view outside, no readable text or numbers; "
     "hold on this single view for the full clip, no cut, no scene change, no camera relocation.",
     "钟表滴答、纸张翻动"),
    ("S04", "agnes", "从暗房门口缓慢推向工作台上的菲林", "引入冲印店与菲林", "胶片划过 → 切",
     "Interior of an old Hong Kong photo laboratory at night, walls on three sides: deep red safelight, a "
     "stainless developing tray, a film developing tank and a small stack of 35mm film cassettes on the worktop, "
     "wet tongs beside them; camera pushes in very slowly towards the film cassettes. Framed on this one worktop "
     "from the first frame to the last; no people, no windows, no view outside, no readable text or labels; hold "
     "on this single view for the full clip, no cut, no scene change, no camera relocation.",
     "暗房设备轻微嗡鸣"),
    ("S05", "graphic", "信息卡：案件名片", "把案名、年代、规模钉在屏幕上", "停留 1 秒 → 切",
     "案件名片", "低频一记重音"),
    ("S06", "agnes", "微距缓慢横移过举在灯前的菲林条", "点题：一卷菲林", "黑场",
     "Extreme close-up of a single strip of 35mm photographic film held up against a bare warm lamp in a dark "
     "room, the frames dark and unreadable, dust and fine scratches catching the light, glow through the sprocket "
     "holes; camera glides slowly sideways along the film strip. Framed on this one film strip from the first "
     "frame to the last; no hands, no people, nothing else in frame, no readable text or numbers; hold on this "
     "single view for the full clip, no cut, no scene change, no camera relocation.",
     "胶片转动、雨声压低"),
    ("S07", "agnes", "后座视角缓慢推近后视镜与雨刷", "夜班的士：案发空间（只做暗示）", "切",
     "Interior of a 1980s Hong Kong taxi at night seen from the rear seat: the windscreen wipers sweep steadily, "
     "rain streams down the glass, the rear-view mirror holds only dark street reflections, a clipboard and a "
     "small hanging charm sway gently above the dashboard; camera pushes in very slowly towards the mirror. "
     "Framed on this interior from the first frame to the last; the driver stays out of frame, no visible face, "
     "no passenger, no readable text or licence numbers; hold on this single view for the full clip, no cut, no "
     "scene change, no camera relocation.",
     "雨刷节奏、发动机低鸣"),
    ("S08", "agnes", "长焦固定机位，雨幕里的车灯缓慢横移", "收束第一幕，转入案件", "快速切黑",
     "Night, heavy rain, 1982: seen from very low above wet asphalt, two small red tail lights glow through thick "
     "rain haze in the upper middle of the frame while long smeared reflections of two amber lamps slide across "
     "the puddles below; everything beyond the tail lights dissolves into dark rain. The camera holds a long lens "
     "and drifts slowly to the right. Fill the frame only with wet road, puddles, rain and light haze; there are "
     "no buildings, no shopfronts, no awnings, no signs, no vehicles other than the distant tail lights, no "
     "people, no readable text anywhere in the frame; hold on this single view for the full clip, no cut, no "
     "scene change, no camera relocation.",
     "车灯渐远、雨声不散"),
    # ---------------- N02（7 镜：5 agnes + 2 卡）----------------
    ("S09", "graphic", "信息卡：四名受害者", "把四个名字与年龄庄重地列出来", "停留 1 秒 → 切",
     "四名受害者信息卡", "三声低沉敲击"),
    ("S10", "agnes", "仰拍缓慢上摇旧唐楼外墙", "他的住处：土瓜湾旧唐楼", "切",
     "Exterior of a weathered 1980s Hong Kong tenement block at night in the rain: stained concrete, closed iron "
     "grilles, box air-conditioners, laundry poles, water running down the wall; camera tilts slowly upward from "
     "the ground floor towards the upper windows. Framed on this one wall from the first frame to the last; no "
     "people, no lit interiors, no readable signs or flat numbers, no skyline; hold on this single view for the "
     "full clip, no cut, no scene change, no camera relocation.",
     "雨打铁窗、远处狗吠"),
    ("S11", "agnes", "乘客席视角：方向盘上的双手与侧窗雨水", "夜班的士司机的日常", "切",
     "Interior of a 1980s Hong Kong taxi at night, seen from the front passenger seat and framed low across the "
     "cab: the driver's two hands in dark sleeves gripping the worn thin-rimmed steering wheel, his forearms and "
     "torso ending at the chest, everything above the chest outside the top of the frame; a strip of dark "
     "dashboard and the driver's side window with rain running down it fill the rest, with only a smear of "
     "out-of-focus amber street light beyond the glass. The camera is inside the cab at seat height and drifts "
     "very slowly sideways; the frame holds only hands, wheel, dashboard and wet glass. Nothing else is in frame "
     "- no head, no face, no neck, no rear-view mirror or any mirror, no passenger, no illuminated dials, no "
     "instrument cluster, no meter head, no clock, no radio, no badges, no signage, no stickers or papers, and no "
     "text, letters or numbers anywhere in the frame; hold on this single view for the full clip, no cut, no "
     "scene change, no camera relocation.",
     "怠速声、雨刷节奏"),
    ("S12", "agnes", "固定机位，远景中打伞的剪影走过", "深夜搭车的人（不出现受害者形象）", "雨幕覆盖",
     "Night in heavy rain, 1982 Hong Kong: an anonymous distant figure under a black umbrella walks away from "
     "camera along a wet pavement that runs beside a long blank concrete wall and a low iron railing, seen only "
     "as a silhouette under a single street lamp, the reflection trailing on the ground; camera stays fixed and "
     "lets the figure cross the frame. Framed on this one stretch of pavement and blank wall from the first frame "
     "to the last; the wall carries no signs, posters, lettering or numbers, the figure stays small and "
     "back-turned with the face never visible, no other people, no readable text anywhere; hold on this single "
     "view for the full clip, no cut, no scene change, no camera relocation.",
     "雨声、伞面滴水"),
    ("S13", "agnes", "车内缓慢横移，空后座与车窗上的雨水", "同一种空间，一次又一次", "切黑",
     "The empty rear seat of a 1980s Hong Kong taxi at night: cracked vinyl bench, a folded newspaper, "
     "condensation and rain streaks on the side window, neon light sliding across the glass as the car moves; "
     "camera creeps slowly sideways along the bench. Framed on this one back seat from the first frame to the "
     "last; no people, no driver visible, no readable text on the newspaper, no face anywhere; hold on this "
     "single view for the full clip, no cut, no scene change, no camera relocation.",
     "车厢回响、窗外雨声"),
    ("S14", "graphic", "信息卡：六个月 · 四条人命（时间线）", "四个日期排成一条线", "停留 1 秒 → 切",
     "时间线信息卡", "打字机三下"),
    ("S15", "agnes", "贴地低机位横移，车胎碾过积水溅起水墙", "四个月里的四起命案", "切",
     "Extreme low view at road level in heavy night rain in 1982 Hong Kong, the camera only knee-high above the "
     "ground: the entire frame is filled by rain-soaked asphalt, standing black water, one worn painted lane line "
     "and a swollen puddle; a period saloon car passes from left to right and its tyres throw a wide sheet of "
     "spray through the frame, only the tyre, the sill and the lower door visible before the car leaves the frame; "
     "the far background is nothing but dark rain haze with the soft glow of one distant street lamp smeared in "
     "the water. Nothing else is in frame - no buildings, no shopfronts, no awnings, no neon, no street furniture, "
     "no pedestrians, no other traffic, no signage of any language, and no text, letters, numbers or plates "
     "anywhere in the frame; hold on this single view for the full clip, no cut, no scene change, no camera "
     "relocation.",
     "水花、空旷街道回声"),
    # ---------------- N03（8 镜：8 agnes）----------------
    ("S16", "agnes", "远景缓慢推近停在僻静路边的的士", "雨夜、僻静处", "切",
     "A lone 1980s Hong Kong taxi parked on a quiet rural roadside at night in heavy rain, headlights cutting "
     "into mist and wet grass, car standing still; camera pushes in very slowly from a distance. Framed on this "
     "one parked car from the first frame to the last; no people, no other vehicles, no buildings, no readable "
     "text or licence plate, no skyline; hold on this single view for the full clip, no cut, no scene change, no "
     "camera relocation.",
     "雨打车身、远雷"),
    ("S17", "agnes", "后座视角缓慢推近驾驶位背影", "驾驶位上的人", "切",
     "Interior of a 1980s Hong Kong taxi at night, seen from the rear seat: the back of a male driver in a plain "
     "short-sleeved work shirt with short black hair, motionless behind the wheel, centred in frame; beyond the "
     "windscreen the road ahead is dark with rain streaking down the glass, only two soft out-of-focus pools of "
     "amber light bokeh and the dark shape of the wipers; camera pushes in very slowly towards his back. Framed "
     "on this one seat and dark windscreen from the first frame to the last; the face is never visible, the glass "
     "shows no signs, no lettering, no readable text and no mirror face reveal, no passenger; hold on this single "
     "view for the full clip, no cut, no scene change, no camera relocation.",
     "音乐骤停半秒"),
    ("S18", "agnes", "俯拍缓慢推近铁架床上的旧式摄录机", "他要把过程记录下来", "切",
     "Interior of a cramped 1980s Hong Kong room at night, walls on three sides: a bulky 1980s video camcorder "
     "resting on an iron bunk bed frame beside a folded blanket, a faint red record lamp, dust drifting in the "
     "light of a bare bulb; camera looks down and pushes in very slowly on the camcorder. Framed on this one bunk "
     "and camera from the first frame to the last; no people, no windows, no view outside, no readable text or "
     "brand marks; hold on this single view for the full clip, no cut, no scene change, no camera relocation.",
     "机械摩擦、磁带仓声"),
    ("S19", "agnes", "暗房红光下缓慢横移过晾着的相纸", "照片被一张张冲出来", "切黑",
     "Interior of a darkroom at night under deep red safelight, walls on three sides: rows of blank developing "
     "prints hanging from a taut string on wooden pegs, peg shadows on the wall, chemical vapour rising in the "
     "glow; camera drifts slowly sideways along the line of prints. Framed on this one line of prints from the "
     "first frame to the last; the paper stays blank and unreadable, no people, no body, no gore, no readable "
     "text; hold on this single view for the full clip, no cut, no scene change, no camera relocation.",
     "水滴、胶片卷动"),
    ("S20", "agnes", "俯拍缓慢推近铁盒里的胶卷与相片叠", "整整齐齐收在家里", "切",
     "Interior of a 1980s Hong Kong room at night: an open metal storage box on a table holding neat stacks of "
     "photographic prints, film canisters and rubber-banded envelopes, a desk lamp lighting the contents from the "
     "left; camera looks down and pushes in very slowly. Framed on this one box from the first frame to the last; "
     "the prints stay face-down and unreadable, no people, no body, no blood, no readable text; hold on this "
     "single view for the full clip, no cut, no scene change, no camera relocation.",
     "铁盒开启、纸页摩擦"),
    ("S21", "agnes", "室内缓慢横移过档案架与桌上的卷宗", "警方在各查各的", "切",
     "Interior of a 1980s Hong Kong police records room at night, walls on three sides: tall steel shelves packed "
     "with identical plain cardboard case folders, a wooden desk below them with two open folders, a folded "
     "district map with small pins, a black rotary telephone and a tin mug under a single warm lamp; camera "
     "tracks slowly sideways at desk height. Framed on this one records room from the first frame to the last; no "
     "people, no windows, no view outside, the folders and map carry no readable text, letters or numbers; hold "
     "on this single view for the full clip, no cut, no scene change, no camera relocation.",
     "无线电杂音、雨声"),
    ("S22", "agnes", "微距缓慢横移过桌上的旧医学书与放大镜", "他学的是解剖", "切",
     "Interior of a 1980s Hong Kong room at night: a neat pile of old medical and anatomy textbooks with plain "
     "unmarked covers, a magnifying glass and a closed instrument case on a table under a desk lamp; camera "
     "creeps slowly sideways across the table top. Framed on this one table from the first frame to the last; no "
     "people, no body, no blood, no readable titles or text on the covers, no open illustrated pages; hold on "
     "this single view for the full clip, no cut, no scene change, no camera relocation.",
     "翻书、金属搭扣"),
    ("S23", "agnes", "缓慢横移过印刷机滚筒与成叠报纸", "案子上了报纸，全城都在看", "切",
     "Interior of a 1980s Hong Kong newspaper print room at night: printing-press rollers turning steadily, "
     "stacks of freshly printed newspapers on a pallet, mist and warm work light around the machinery; camera "
     "tracks slowly sideways at roller height. Framed on this one press from the first frame to the last; the "
     "newspaper pages stay blurred and unreadable, no people, no readable headlines or text, no windows; hold on "
     "this single view for the full clip, no cut, no scene change, no camera relocation.",
     "印刷机节奏、纸张堆叠"),
    # ---------------- N04（7 镜：6 agnes + 1 卡）----------------
    ("S24", "graphic", "信息卡：破案关键 · 一卷菲林", "把「放大机坏了」这条因果写在屏幕上", "停留 1 秒 → 切",
     "破案关键信息卡", "放大机嗡鸣一声"),
    ("S25", "agnes", "从街对面缓慢推近雨夜的相铺门面", "尖沙咀的一间相铺", "切",
     "Interior of a small 1980s Hong Kong photo shop at night, seen from inside, walls on three sides: a glass "
     "door with rain streaming down it, a long counter with trays of blank photographic prints, a display case of "
     "old cameras and boxes of film behind it, warm ceiling light doubling on the wet glass; the street beyond "
     "the door is dark and blurred. Framed on this one shop interior from the first frame to the last; the shop "
     "carries no name, no lettering, no numbers, no signage, the prints stay blank and unreadable, no people; "
     "hold on this single view for the full clip, no cut, no scene change, no camera relocation.",
     "雨声、招牌灯管电流声"),
    ("S26", "agnes", "暗房内缓慢推近放大机的镜头与显影盘", "放大机坏了，底片被转走", "切",
     "Interior of an old photo laboratory at night under red safelight, walls on three sides: an enlarger head "
     "with its lens lowered over a developing tray, tongs resting on the rim, a timer dial glowing; camera pushes "
     "in very slowly on the enlarger lens. Framed on this one enlarger from the first frame to the last; no "
     "people, no hands, no windows, no readable text or numbers on the dials; hold on this single view for the "
     "full clip, no cut, no scene change, no camera relocation.",
     "放大机嗡鸣、计时器滴答"),
    ("S27", "agnes", "俯拍缓慢横移，一双手在显影盘里晃动相纸", "店员亲手冲晒", "切",
     "Interior of a photo laboratory at night under red safelight: only a pair of hands in thin cotton gloves "
     "rocking a sheet of photographic paper in a developing tray, chemical ripples catching the light; camera "
     "looks straight down and drifts slowly sideways. Framed on this one tray and pair of hands from the first "
     "frame to the last; no face, no body, no other people in frame, the print stays blank and unreadable, no "
     "blood, no readable text; hold on this single view for the full clip, no cut, no scene change, no camera "
     "relocation.",
     "药液晃动、心跳声起"),
    ("S28", "agnes", "微距缓慢推近显影液中浮现的模糊轮廓", "照片里的东西不对劲", "切黑",
     "Extreme close-up inside a developing tray at night: a sheet of photographic paper in the developer, faint "
     "grey shapes slowly blooming up through the emulsion, chemical ripples sliding across the surface, red "
     "safelight glow; camera pushes in very slowly. Framed on this one sheet of paper from the first frame to the "
     "last; the image stays abstract and unrecognisable, no body, no gore, no face, no readable text; hold on "
     "this single view for the full clip, no cut, no scene change, no camera relocation.",
     "心跳声一下停住"),
    ("S29", "agnes", "柜台上的老式电话，缓慢推近拿起听筒的手", "店员打电话报警", "切",
     "Interior of a 1980s Hong Kong shop counter at night: a black rotary telephone on a worn wooden counter, a "
     "hand lifting the receiver, the coiled cord stretching, a closed ledger and pen beside it; camera pushes in "
     "very slowly on the telephone. Framed on this one counter from the first frame to the last; only one hand is "
     "visible, no face, no other people, no readable text or numbers on the ledger or dial; hold on this single "
     "view for the full clip, no cut, no scene change, no camera relocation.",
     "拨号声、线路杂音"),
    ("S30", "agnes", "长焦缓慢横移，街角的便衣与停靠的旧车", "警方开始部署", "切",
     "Interior of a parked 1980s saloon car at night in the rain, seen from inside: two men in dark jackets "
     "sitting in the front seats, seen only from behind as shoulders and the backs of their heads, one holding a "
     "walkie-talkie; rain streams down the windscreen and the dark wet street beyond is out of focus, with a "
     "single blurred amber lamp glow. Framed on this one car interior from the first frame to the last; faces "
     "never visible, the glass shows no signage, lettering or readable text, no pedestrians; hold on this single "
     "view for the full clip, no cut, no scene change, no camera relocation.",
     "低频鼓点进入、雨声"),
    # ---------------- N05（8 镜：7 agnes + 1 卡）----------------
    ("S31", "graphic", "信息卡：八月十八日 · 搜查住所", "把搜查地点与证物写在屏幕上", "停留 1 秒 → 切",
     "搜查住所信息卡", "门铃一声"),
    ("S32", "agnes", "店员肩后：走向过曝的门洞，人影从雨里进来", "他们等的，是他自己回来", "切",
     "Interior of a small old photo shop at night, seen over the shoulder of the unseen shopkeeper: the camera "
     "sits low and close behind a shoulder in a dark shirt, looking towards the open shop doorway; the doorway is "
     "a plain opening with a bare metal edge, blown out into a soft white glare by the street light and rain "
     "outside, wet dark paving below it catching the glare; a black human silhouette - only an outline, the face "
     "unlit and unreadable - steps in through the glowing doorway from the rain, walking away from the light into "
     "the dim shop. The camera holds inside the shop, drifting very slightly forward; the frame holds only the "
     "foreground shoulder, the empty floor, the doorway and the entering silhouette, nothing else. No display "
     "shelves, no goods in front of the lens, no counter, no posters, no notices, no paper or paper labels on the "
     "glass, no neon or lamps outside the doorway, no street detail beyond the glare, and no text, letters or "
     "numbers anywhere in the frame; hold on this single view for the full clip, no cut, no scene change, no "
     "camera relocation.",
     "门铃、雨声收小"),
    ("S33", "agnes", "俯拍缓慢推近柜台上推过来的相片袋", "他来取的，正是那卷菲林", "切",
     "Interior of a 1980s Hong Kong shop counter at night, seen from above: a paper photo envelope slides across "
     "the wooden counter towards a waiting hand, a counter bell and a receipt spike beside it; camera looks down "
     "and pushes in very slowly. Framed on this one counter from the first frame to the last; only hands are "
     "visible, no faces, no other people, no readable text or numbers on the envelope; hold on this single view "
     "for the full clip, no cut, no scene change, no camera relocation.",
     "纸张滑过木台"),
    ("S34", "agnes", "手持感缓慢推近店门口被拦住的背影", "下一秒，探员出手", "切黑",
     "Interior of a small 1980s Hong Kong photo shop at night, walls on three sides: seen from behind, two men in "
     "dark jackets step up to a long wooden counter where a shopkeeper in a grey shirt stands beside a tray of "
     "blank photographs, shelves of photo albums and a display case of old cameras behind them, warm ceiling "
     "light; camera pushes in very slowly. Framed on this one counter area from the first frame to the last; no "
     "faces are visible, no violence, no lettering, numbers or signs anywhere, the albums and prints stay blank; "
     "hold on this single view for the full clip, no cut, no scene change, no camera relocation.",
     "急促脚步、短促无线电"),
    ("S35", "agnes", "贴墙横移：雨水墙面上的警灯蓝红光", "同日，押他回土瓜湾", "切",
     "Extreme close view of the blank wet concrete wall of an old Hong Kong tenement at night in heavy rain: the "
     "wall surface fills the entire frame edge to edge, water running down the concrete in sheets, streaks and "
     "beads, no other surface in frame; the blue and red glow of an unseen emergency beacon sweeps slowly across "
     "the wet wall, pulsing through the rain glow; the camera is only about half a metre from the wall and drifts "
     "slowly sideways along it. No street, no road, no kerb, no sky, no horizon, no vehicle, no people, no doors, "
     "no windows, no pipes, no signage, and no text, letters or numbers anywhere in the frame; hold on this "
     "single view for the full clip, no cut, no scene change, no camera relocation.",
     "警灯电流声、雨声"),
    ("S36", "agnes", "跟随背影缓慢推近打开的铁闸门", "搜查土瓜湾贵州街的单位", "切",
     "Interior corridor of an old 1980s Hong Kong tenement at night: a narrow passage of painted concrete walls "
     "and iron gates, one gate standing open, two officers seen only from behind stepping through into a dim "
     "flat, a single bulb overhead; camera follows slowly forward behind them. Framed on this one corridor and "
     "doorway from the first frame to the last; faces never visible, no residents, no readable text or flat "
     "numbers; hold on this single view for the full clip, no cut, no scene change, no camera relocation.",
     "铁闸门响、脚步回音"),
    ("S37", "agnes", "俯拍缓慢推近被打开的铁箱", "一件一件被翻出来", "切",
     "Interior of a dim 1980s Hong Kong flat at night: an old metal trunk stands open on the floor, film "
     "canisters, paper envelopes of prints and a folded dark garment visible inside, a torch beam sweeping across "
     "the contents; camera looks down and pushes in very slowly. Framed on this one trunk from the first frame to "
     "the last; no people, no body, no blood, no readable text, no recognisable image on any photograph; hold on "
     "this single view for the full clip, no cut, no scene change, no camera relocation.",
     "金属箱开启、低频轰鸣"),
    ("S38", "agnes", "俯拍缓慢横移过证物桌上的物件", "四起互不相干的命案串成一条线", "切",
     "Interior of a 1980s Hong Kong evidence room at night, seen from above: a long table with neatly laid-out "
     "film canisters, paper photo envelopes, a pair of dark court shoes, a folded garment and a length of cord, "
     "each item beside a blank tag; camera drifts slowly sideways across the table. Framed on this one table from "
     "the first frame to the last; no people, no body, no blood, no readable text on the tags; hold on this "
     "single view for the full clip, no cut, no scene change, no camera relocation.",
     "连续三次低沉鼓点"),
    # ---------------- N06（7 镜：5 agnes + 2 卡）----------------
    ("S39", "agnes", "仰拍缓慢上摇法院石阶与拱廊", "一九八三年三月，高等法院开审", "切",
     "Exterior of a British colonial courthouse in Hong Kong, 1983, on an overcast rainy morning: heavy grey "
     "granite masonry, a deep arcade of round-headed arches along the ground floor, wide stone steps with a low "
     "stone balustrade, tall dark wooden doors set in a stone archway, wet steps and pavement mirroring the flat "
     "white sky, a row of open black umbrellas held by anonymous figures standing far below the steps and seen "
     "only as distant silhouettes from behind; the camera starts low at the pavement and tilts slowly upward "
     "along the facade. This is plain 1930s Hong Kong colonial granite architecture - no European palace, no "
     "ornate French facade, no mansard roof, no statue-topped pediment, no dome, no flagpole, no columns in a "
     "grand classical portico; no signage, no plaques, no posters, and no text, letters or numbers anywhere in "
     "the frame; hold on this single view for the full clip, no cut, no scene change, no camera relocation.",
     "低沉钟声、雨声"),
    ("S40", "agnes", "法庭内缓慢横移过空着的被告席与陪审席", "争的是他到底有没有精神病", "切",
     "Interior of a 1980s Hong Kong courtroom, walls on three sides: dark wood panelling, an empty jury box with "
     "seven chairs, an empty dock behind a low rail, tall shuttered windows glowing behind the bench; camera "
     "tracks slowly sideways at chest height. Framed on this one courtroom interior from the first frame to the "
     "last; no people at all, no readable text or signs, no flags; hold on this single view for the full clip, no "
     "cut, no scene change, no camera relocation.",
     "法庭空旷回响、翻页声"),
    ("S41", "agnes", "俯拍缓慢推近一叠评估报告与钢笔", "五名医生，两种结论", "切",
     "Interior of a desk in a 1980s Hong Kong office, seen from above under a warm desk lamp: a thick stack of "
     "typed assessment reports with blank margins, a fountain pen and a pair of reading glasses resting on top, a "
     "cold cup of tea beside them; camera pushes in very slowly. Framed on this one desk from the first frame to "
     "the last; no people, no hands, the typed pages stay unreadable, no readable text or numbers; hold on this "
     "single view for the full clip, no cut, no scene change, no camera relocation.",
     "钢笔划过纸面"),
    ("S42", "graphic", "信息卡：一九八三年四月八日 · 判决", "把裁决与刑罚钉在屏幕上", "停留 1 秒 → 切",
     "判决信息卡", "木槌一记"),
    ("S43", "agnes", "缓慢推近法台上的木槌与合上的卷宗", "陪审团一致裁定", "切",
     "Interior of a 1980s Hong Kong courtroom, walls on three sides: a raised judge's bench of dark wood with a "
     "wooden gavel resting on a closed case file, a brass lamp, blurred rows of an empty public gallery far back "
     "in shadow; camera pushes in very slowly on the gavel and file. Framed on this one bench from the first "
     "frame to the last; no faces, no identifiable people, no readable text on the file; hold on this single view "
     "for the full clip, no cut, no scene change, no camera relocation.",
     "木槌回响、心跳声"),
    ("S44", "graphic", "信息卡：一九八四年八月 · 改判终身监禁", "把结局写在屏幕上", "停留 1 秒 → 切",
     "结局信息卡", "铁门关闭回响"),
    ("S45", "agnes", "微距匀速拉远：菲林盘与旧档案盒，雨夜房间", "收尾：那卷菲林", "缓慢黑场",
     "Interior of a dim 1980s Hong Kong room at night, walls on three sides: a 35mm film reel and a worn "
     "cardboard archive box on a table beside a rain-streaked window, a small lamp glowing, rain shadows moving "
     "on the wall; camera pulls back in one continuous, steady, constant-speed dolly out, moving the whole time "
     "from the first frame to the last and never slowing, never pausing, never holding still. Framed on this one "
     "table and window from the first frame to the last; no people, no readable text or labels, no skyline "
     "outside the glass; hold on this single view for the full clip, no cut, no scene change, no camera "
     "relocation.",
     "雨声渐弱，只剩胶片转动"),
]

# ---------------------------------------------------------------------------
# 画面上的文字（render.py 从 story.json 的 presentation 块读，不在 render.py 里写死）
# ---------------------------------------------------------------------------
CARD_HEADER = "雨夜屠夫案  /  香港 · 一九八二"                    # 每张信息卡左上角的小字
CARD_FOOTER = "资料摘要与示意图 · 并非原始档案影像"                 # 每张信息卡左下角的小字
# 信息卡文案：镜头号 -> (大标题, 第一行, 第二行)。只写公开报道里的事实，不写推测。
CARDS = {
    "S05": ("雨夜屠夫案", "香港 · 一九八二年二月至七月", "四名女性遇害 · 一案震动全港"),
    "S09": ("四名受害者", "陈凤兰 二十二岁 · 陈云洁 三十一岁", "梁秀云 二十九岁 · 梁惠心 十七岁"),
    "S14": ("六个月 · 四条人命", "二月三日 陈凤兰 · 五月二十九日 陈云洁", "六月十七日 梁秀云 · 七月二日 梁惠心"),
    "S24": ("破案关键：一卷菲林", "他把菲林送到尖沙咀一间相铺冲洗", "放大机坏了 → 底片转分店人手冲晒 → 店员报警"),
    "S31": ("八月十八日 · 搜查住所", "土瓜湾贵州街 · 旧唐楼单位", "照片 · 录像带 · 女性物品 · 手术器材"),
    "S42": ("一九八三年四月八日", "四项谋杀罪名成立 · 判处死刑", "七人陪审团一致通过"),
    "S44": ("一九八四年八月", "港督会同行政局赦免死刑", "改判终身监禁 · 至今仍在服刑"),
}
# 片头字幕卡（0.35–4.7 秒叠在第一镜上）：两行，第二行小字
TITLE_CARD = ["雨夜屠夫林过云", "一卷菲林里的四条人命 · 一九八二 香港"]
# 片尾卡（最后 3.8 秒）：大字提问 / 一行案件信息 / 一行金句 / 一行资料来源
END_CARD = [
    "如果那台放大机没坏，这个案子还会被揭开吗？",
    "雨夜屠夫案 · 香港 · 一九八二至一九八四",
    "他想让全世界看见自己的作品，把他送上法庭的正是那卷菲林",
    "资料：HK01 / 思考香港 / NOWnews 等公开报道 · 原创解说 · AI动画情景重现",
]
# 字幕里描黄的关键词（人名、数字、结论词）
CAPTION_KEYWORDS = [
    "雨夜屠夫", "林过云", "城门河", "四条人命", "陈凤兰", "梁惠心",
    "冲印店", "菲林", "放大机", "八月十八日", "土瓜湾", "四项谋杀罪", "死刑", "终身监禁",
]
# 逐镜标签覆盖：默认 agnes 镜头标「AI动画情景重现 · 非新闻影像」，法庭 / 搜查镜头写得更具体
LABEL_OVERRIDES = {
    "S36": "AI动画示意 · 非搜查录像",
    "S37": "AI动画示意 · 非搜查录像",
    "S38": "AI动画示意 · 非证物影像",
    "S39": "AI动画示意 · 非庭审影像",
    "S40": "AI动画示意 · 非庭审影像",
    "S41": "AI动画示意 · 非庭审影像",
    "S43": "AI动画示意 · 非庭审影像",
}
# 合成音效事件：(镜头号, 类型)，类型可选 paper / phone / keys / machine / press，落在该镜开始前 0.18 秒
SFX_EVENTS = [
    ("S03", "paper"),
    ("S04", "machine"),
    ("S23", "press"),
    ("S29", "phone"),
    ("S33", "paper"),
    ("S36", "keys"),
    ("S37", "keys"),
]

# ---------------------------------------------------------------------------
# 发布文案（抖音脚本.md / 抖音发布文案.md 用）
# ---------------------------------------------------------------------------
TITLES = [
    "香港最轰动的奇案：他把四条人命拍进菲林，最后栽在一台坏掉的放大机上",
    "雨夜屠夫林过云：一卷送去冲印的照片，把自己送进了法庭｜香港十大奇案",
    "1982年香港雨夜，四个女人上了同一辆的士，再也没下车",
]
HOOK = "他不是被抓的——是冲印店坏了一台放大机，店员多看了一眼照片。"
GOLDEN_LINES = [
    "他想让全世界看见自己的作品，结果正是那卷菲林，把他送上了法庭。",
    "四个月里，没人把这些案子连在一起；把他连起来的，是一卷送去冲洗的底片。",
    "如果那台放大机没有坏，这个案子还会被揭开吗？评论区聊聊。",
]
DESCRIPTION = (
    "一九八二年二月，香港沙田城门河里被发现的那颗人头，拉开了一宗连环命案的序幕。"
    "接下来六个月，四名夜归女子坐上一辆夜班的士，再没有回家。警方查了半年，"
    "最后揭开真相的，不是目击者，也不是指纹，而是一卷送去冲印店的菲林。"
    "本片按公开报道整理，画面为写实 3D 动画情景重现，非新闻影像，受害者不以人像出现。"
    "你觉得，如果那台放大机没有坏，这个案子还会被揭开吗？"
)
QUESTION = "如果那台放大机没有坏，这个案子还会被揭开吗？"
HASHTAGS = ["#香港十大奇案", "#雨夜屠夫", "#真实案件", "#悬疑解说", "#案件解说", "#香港"]

GRID = 4           # 规划网格：每镜 4 秒，45 镜 = 180 秒
AGNES_SECONDS = 7  # 每个 Agnes 镜头实际请求的时长（169 帧 @ 24 fps）
SEED_BASE = 19820818  # 本片首批镜头种子基于拘捕日，便于追溯

def presentation():
    return {
        "card_header": CARD_HEADER, "card_footer": CARD_FOOTER,
        "cards": {sid: list(lines) for sid, lines in CARDS.items()},
        "title_card": TITLE_CARD, "end_card": END_CARD,
        "caption_keywords": CAPTION_KEYWORDS, "label_overrides": LABEL_OVERRIDES,
        "sfx_events": [list(e) for e in SFX_EVENTS],
    }


def build():
    story = json.loads(PLAN.read_text())
    assert len(SHOTS) * GRID == 180, f"{len(SHOTS)} 镜 × {GRID} 秒 ≠ 180 秒"
    assert len(story["chapters"]) == len(CHAPTERS) == 6
    assert len({sid for sid, *_ in SHOTS}) == len(SHOTS), "镜头号重复"
    cards_needed = {sid for sid, kind, *_ in SHOTS if kind == "graphic"}
    missing = sorted(cards_needed - set(CARDS))
    assert not missing, f"这些信息卡镜头在 CARDS 里没有文案：{missing}"
    story["title"] = TITLE
    story["style_prefix"] = STYLE_PREFIX
    story["negative_prompt"] = NEGATIVE_PROMPT
    story["principles"] = PRINCIPLES
    story["sources"] = SOURCES
    for chapter, (cid, title, text) in zip(story["chapters"], CHAPTERS):
        assert chapter["id"] == cid
        chapter["title"] = title
        chapter["text"] = text
    shots = []
    for i, (sid, kind, camera, purpose, transition, body, sfx) in enumerate(SHOTS):
        assert sid == f"S{i + 1:02d}", sid
        assert kind in ("agnes", "graphic"), f"{sid}: kind 只能是 agnes / graphic"
        start = i * GRID
        shots.append({
            "id": sid, "kind": kind, "start": start, "duration": GRID,
            "narration_id": f"N{min(6, start // 30 + 1):02d}",
            "prompt": body if kind == "agnes" else "",
            "purpose": purpose, "transition_out": transition,
            "graphic": body if kind == "graphic" else "",
            "seed": SEED_BASE + i + 1,
            "seconds": AGNES_SECONDS, "aspect": "16:9", "resolution": "1080p", "frame_rate": 24,
            "camera": camera, "sfx_note": sfx,
        })
    story["shots"] = shots
    story["presentation"] = presentation()
    story.setdefault("_scaffold", {})["note"] = (
        "内容由 build_story.py 一次性写入；45 镜 × 4 秒规划网格（每镜只用一次）；"
        "解说词与 screenplay.md、audio/manifest.json 三处逐字一致由 generate.py --validate 守着。")
    PLAN.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n")

    manifest = json.loads(MANIFEST.read_text())
    for clip, chapter in zip(manifest["clips"], story["chapters"]):
        assert clip["id"] == chapter["id"]
        clip["text"] = chapter["text"]
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    kinds = [s["kind"] for s in story["shots"]]
    print(f"story.json 已写入：{len(shots)} 镜 = {kinds.count('agnes')} agnes + {kinds.count('graphic')} graphic，"
          f"解说 {sum(len(c['text']) for c in story['chapters'])} 字（含标点）")
    todo = json.dumps(story, ensure_ascii=False).count("TODO") + json.dumps(presentation(), ensure_ascii=False).count("TODO")
    if todo:
        print(f"注意：还有 {todo} 处 TODO 没填，generate.py --validate 不会放行", file=sys.stderr)


if __name__ == "__main__":
    if "--script" in sys.argv:
        from script_table import render_document  # noqa: E402  (同目录)
        out = HERE / "抖音脚本.md"
        out.write_text(render_document())
        print(f"抖音脚本.md 已写入（{len(out.read_text())} 字符）")
    elif "--publish" in sys.argv:
        from script_table import publish_document  # noqa: E402  (同目录)
        out = HERE / "抖音发布文案.md"
        out.write_text(publish_document())
        print(f"抖音发布文案.md 已写入（{len(out.read_text())} 字符）")
    else:
        build()
