#!/usr/bin/env python3
"""《韩国雨衣杀手柳永哲：十个月，二十条人命》的全部内容源：解说词、45 镜分镜、信息卡文案、字幕高亮词、发布文案。

这是这部片子**唯一需要动脑写的文件**（模板来自 production/templates/build_story.py，
参考实现 production/lamkorwan/ —— 露脸模式的上一部片子；内容按用户上传的 40 镜 JSON 稿改写，
事实按 8 条公开来源核对，见 SOURCES 与 史实核对.md）。

用法::

    python3 production/raincoat2004/build_story.py            # 写 story.json（含 presentation 块）+ audio/manifest.json 的逐字文本
    python3 production/raincoat2004/build_story.py --script   # 生成 抖音脚本.md（3 标题 / 核心爆点 / 四列分镜表 / 金句）
    python3 production/raincoat2004/build_story.py --publish  # 生成 抖音发布文案.md（标题 / 介绍 / 提问读者一句话 / 话题）

本片是**露脸模式**：三个角色各一张不同的脸，同一角色跨镜头逐字节复用同一条面容 token
（token 只在 cast.json 里写一份，本文件用 {C1}/{C2}/{C3} 占位符注入，保证逐字节一致），
并复用同一个 seed；由 production/face_cast.py 的 check-prompts / check-frames 两道闸门守着。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "story.json"
MANIFEST = HERE / "audio" / "manifest.json"
CAST = HERE / "cast.json"

TITLE = "韩国雨衣杀手柳永哲：十个月，二十条人命"

# 全片统一的画面风格前缀（英文）。写实 3D CGI 情景重现（不是 2D、不是图片轮播）——
# 用户明确要求「3D 动画视频，不是图片视频」。后半句（匿名角色、无真人肖像、无文字、单一运镜）是流水线规则，别删。
# 注意：style_prefix 参与全部 Agnes 镜头的 request_hash，开工后改一个字 = 38 镜全部重做。
STYLE_PREFIX = (
    "Photorealistic cinematic 3D animated reenactment, high-end CGI feature-film render with volumetric light, "
    "physically based materials, shallow depth of field and subtle 35mm film grain, of South Korea in 2003 and 2004: "
    "rain-soaked Seoul nights, low-rise residential districts, narrow back alleys, 1990s-2000s domestic interiors and "
    "period props, humble rural villages, humid air, wet asphalt and puddle reflections, sodium street lamps and "
    "practical interior bulbs, restrained teal-and-amber colour grading, slow-burn true-crime documentary mood, "
    "never stylised, never a drawing, never a cartoon; horizontal 16:9 widescreen cinematic composition; the people "
    "are anonymous period characters performed by computer-generated figures - a face is shown only where a shot "
    "explicitly names one of the cast characters, and never as a recognisable real person or a likeness of anybody "
    "living or dead; absolutely no readable text, letters, numbers, logos, license plates or brand marks anywhere "
    "inside the frame; one single continuous smooth slow camera move per shot exactly as directed. "
)

NEGATIVE_PROMPT = (
    "readable text, letters, numbers, words, signage writing, invented headlines, neon lettering, logos, brand marks, "
    "watermark, subtitles, on-screen caption, recognisable real person likeness, celebrity likeness, portrait of a real "
    "public figure, blood, gore, wound, corpse, body bag, body parts, dismemberment, autopsy, weapon attack, strangling, "
    "assault, violence on screen, nudity, erotic content, horror monster, ghost, jump scare, flat 2D cartoon, cel-shaded "
    "illustration, hand-drawn sketch, watercolour, comic panel, low-poly, waxy plastic skin, doll-like figure, every "
    "character with the same face, duplicated identical faces, changing face, morphing objects, teleportation, jitter, "
    "flicker, whip pan, fast zoom, jump cut, split screen, collage"
)

# 事实边界与红线：每一条都会印在 抖音脚本.md 的「发布前自查」里。
PRINCIPLES = [
    "全部 Agnes 镜头为写实 3D CGI 动画情景重现，画面常驻标注「AI动画情景重现 · 非新闻影像」，不冒充庭审、审讯、搜查、监控或证物照片",
    "不展示遗体、血腥或作案过程；杀害方式只写到「钝器」这一层，不写细节；奉元寺后山只出现雨、泥土、落叶、警戒线与工作人员背影",
    "凶手由一名虚构的年代角色扮演，是 AI 生成的匿名人物，**不是柳永哲本人的容貌**，不做任何真实人物的肖像还原",
    "三名露脸角色（雨衣男 / 老刑警 / 按摩店老板）各有一张不同的脸；同一角色跨镜头逐字节复用同一条面容 token 并共用同一个 seed，"
    "由 production/face_cast.py 的 check-prompts（静态闸门）与 check-frames（画面闸门）检查，人眼对照接触表判决",
    "受害者不以具备可辨识面容的人像出现：女性角色一律背影、剪影或局部，不出现遗体、遗物特写之外的私密画面",
    "每一句事实都能指到 sources 里的一条公开报道；口径冲突处（受害者构成、招供人数、最高法院日期）只写「警方确认的二十人」或写区间，不挑一个当结论",
    "所有中文姓名、日期、字幕后期添加，不交给视频模型拼写；画面内不出现任何可读文字、门牌或招牌（AI 街景必编字，靠构图排除）",
    "人工检视 qa/ 接触表与 delivery/face-cast/ 人脸接触表；换脸、畸变、伪文字、中途换场的镜头用 {\"only\":\"Sxx\"} 重生成，不直接进成片",
]

# 每条事实的公开来源。
SOURCES = [
    {"id": 1, "url": "https://en.wikipedia.org/wiki/Yoo_Young-chul",
     "usage": "支撑：2003 年 9 月至 2004 年 7 月的作案区间、2004 年 7 月 15 日抓捕、二十起谋杀定罪、2004 年 12 月 13 日死刑、"
              "被捕后假装癫痫逃跑又被抓回、至今仍在押"},
    {"id": 2, "url": "https://en.namu.wiki/w/%EC%9C%A0%EC%98%81%EC%B2%A0%20%EC%97%B0%EC%87%84%EC%82%B4%EC%9D%B8%20%EC%82%AC%EA%B1%B4",
     "usage": "支撑：按摩店老板因为「同一个号码的姑娘接连不回来」而记下号码并报警；逃跑约 11—12 小时后在永登浦站一带被重新抓住；"
              "抓捕实际由店家促成，而不是靠警方画像"},
    {"id": 3, "url": "http://news.sina.com.cn/w/2004-12-26/03535331649.shtml",
     "usage": "支撑：首案（二〇〇三年九月二十四日，江南区新沙洞独栋住宅，淑明女子大学名誉教授夫妇）、出狱后第 13 天作案、"
              "十八至三十三岁间十四次前科、累计服刑十一年、被害人构成（富人区老人与按摩女）、判决与「粉丝俱乐部」的报道"},
    {"id": 4, "url": "https://www.newsweek.com/raincoat-killer-yoo-young-chul-death-penalty-south-korea-dead-alive-netflix-1641573",
     "usage": "支撑：二〇〇四年七月十五日抓捕经过、最初供认十九人后确认二十人、死刑判决与韩国死刑存废之争、Netflix 纪录片"},
    {"id": 5, "url": "http://mail.murderpedia.org/male.Y/y/young-chul.htm",
     "usage": "支撑：二〇〇四年七月十五日凌晨五点在麻浦区一带被捕、七月十八日警方公开案情、富人区被害地点（新沙洞 / 旧基洞 / 三成洞 / 惠化洞）、"
              "以及「被击伤后逃脱、十二小时后在永登浦站附近落网」的早期报道"},
    {"id": 6, "url": "https://www.elle.com/tw/entertainment/drama/g39089971/netflix-the-raincoat-killer/",
     "usage": "支撑：媒体统计的受害者构成（八名素不相识的富人 + 至少十一名从事特种行业的女性）、他至今日仍以死刑犯身分服刑、"
              "以及「这起案件推动了韩国执法制度的检讨」"},
    {"id": 7, "url": "https://m.people.cn/n4/2017/0227/c164-8471368.html",
     "usage": "支撑：奉元寺后山发现十一具遗体；他后来被关押在首尔拘留所（二〇一七年报道仍称其为在押人员）"},
    {"id": 8, "url": "https://crimeandcourt.com/news/2024/10/the-dark-tale-of-yoo-young-chul-unraveled/",
     "usage": "支撑：一九九七年之后韩国未再执行死刑、死刑判决未执行的状态；案件对警方侦查方式的影响"},
]

# 六段解说：(章节 id, 章节标题, 逐字解说词)。六段合计 ≈ 780 字（含标点）。
CHAPTERS = [
    ("N01", "黄金开头：被点着的房子，和一件没丢的东西",
     "二零零三年九月，首尔江南区新沙洞，一对老夫妇在自己家里遇害，房子随后被点着。"
     "凶手没有拿走任何值钱的东西。十个月后警方才确认，那只是第一起；"
     "而最后把他揪出来的，不是指纹，也不是监控，是一部被记下来的电话号码。"),
    ("N02", "人物档案：从监狱走向富人区的男人",
     "他叫柳永哲，一九七零年出生在全罗北道高敞郡，家里很穷。从高中时代起，他就在监狱里进进出出："
     "盗窃、诈骗和暴力，前后十四次，累计服刑十一年。二零零三年九月十一日，他最后一次走出监狱；"
     "妻子已经带着儿子离开，那年他三十三岁。"),
    ("N03", "目标：白天没有人的独栋住宅，和深夜接电话的女人",
     "出狱十三天后，第一起案子发生了。此后他专挑富人区的独栋住宅，在白天老人独自在家的时候闯进去；"
     "为了不留目击者，连屋里的帮佣也不放过。二零零四年春天，他突然换了目标：用伪造的警察证件和一部电话，"
     "把按摩女约到自己住的写字楼公寓。到七月落网前，有十一名女性走进了那栋楼，再也没有出来。"),
    ("N04", "转机：一部被按摩店老板记下来的号码",
     "一开始，这些失踪并没有被当成连环案件。按摩女的去向本来就少有人追问，警方最初的判断是："
     "可能有人把她们拐卖到了乡下。真正的转机出现在一部电话上——店里好几个姑娘，都是接到同一个号码之后消失的。"
     "老板把号码记了下来，又看见它出现，就带着人报了警。"),
    ("N05", "抓捕：逃跑十二小时，和一座后山",
     "二零零四年七月十五日凌晨，警方在麻浦区的一条巷子里抓住了他。审讯中途他假装癫痫发作，"
     "趁手铐松开逃出警局；十二个小时后，警察在永登浦站附近把他重新抓住。面对警方的问话，"
     "他承认自己和这些失踪案有关。七月十八日，他带着警察上了奉元寺的后山。"
     "雨天里，警方在那片山坡上，找到了十一名失踪女性的下落。"),
    ("N06", "结局：死刑、没有执行，和一群粉丝",
     "二零零四年十二月十三日，首尔中央地方法院认定，他对二十人的死亡负有责任，判处死刑；"
     "二零零五年六月，最高法院终审维持原判。韩国从一九九七年起就没有再执行过死刑，他至今仍然在监狱里。"
     "真正让人不安的是，他被捕之后，韩国的网站上出现了他的粉丝俱乐部。二零零八年，这起案子被拍成电影《追击者》；"
     "二零二一年，它又被拍成纪录片。危险从不写在脸上，它就走在人群里。"),
]

# 每一镜：(id, kind, 运镜, 叙事职责, 衔接方式, 英文提示词 或 信息卡说明, 音效/备注)
# kind = "agnes"（AI 动画）或 "graphic"（信息卡；文案写在下面的 CARDS 里）。
# {C1}/{C2}/{C3} 是 cast.json 里的面容 token 占位符（build() 注入，保证逐字节一致）。
HOLD = ("no cut, no scene change, no camera relocation, no second location, no extra people, "
        "no readable text anywhere in frame; hold on this single view for the full clip.")
SHOTS = [
    # ---------------- N01（8 镜：7 agnes + 1 信息卡）----------------
    ("S01", "agnes", "低机位缓慢前推", "开场：雨夜里的富人区街道，没有一家店面",
     "接信息卡：案件名片",
     "A rain-soaked residential street in an affluent low-rise Seoul district at night in 2003: wet asphalt filling the "
     "lower half of the frame, a clipped hedge and a low brick wall running along the right, warm window light bleeding "
     "through the rain haze far behind, puddles mirroring amber street lamps, heavy rain streaking the air and bouncing "
     "off the road. The frame contains no shopfront, no signboard, no vehicle, no person. Slow low-angle push forward "
     "along the empty road, " + HOLD,
     "雨声 + 低频悬念音"),
    ("S02", "graphic", "信息卡（静帧）", "名片：案件、时间、规模",
     "接 AGNES：第一现场外观",
     "案件名片：案名 / 地点与年代 / 规模",
     "低音撞击 + 雨声延续"),
    ("S03", "agnes", "贴墙横移", "第一起：独栋住宅，火从窗里映出来",
     "接 AGNES：屋内空镜",
     "The exterior of a single detached two-storey house behind a low wall in Seoul at night, heavy rain: one ground-floor "
     "window glows deep orange from firelight behind closed curtains, smoke seeping along the eaves, unlit door, no house "
     "number, no gate plate, no lettering of any kind, no people, no cars. Slow lateral dolly along the wet wall, " + HOLD,
     "火声 + 雨声"),
    ("S04", "agnes", "缓慢横移", "现场空镜：什么都没拿走",
     "接 AGNES：露脸镜头（C1 首次出现）",
     "The interior of the same house after the fire, seen as an empty room: an overturned armchair, a floor lamp lying on "
     "its side, an open jewellery box on a sideboard with rings still inside, ash flakes drifting in the air, thin smoke, "
     "the fire already out, no body, no blood, no people, no readable text on any surface. Slow lateral track across the "
     "room, " + HOLD,
     "余烬细响"),
    ("S05", "agnes", "缓慢前推（中景）", "凶手首次露面：雨衣下的那张脸",
     "接 AGNES：警方到场",
     "A medium shot in a rainy Seoul side street at night: {C1}, standing still under a brick wall, rain streaming off the "
     "brim of the cap and running down the shoulders of the raincoat, head slightly turned, weight shifting as he looks "
     "off to one side of the frame, cold street light on one cheek and darkness on the other; behind him only wet brick, "
     "drain water and rain haze, no shop, no sign, no vehicle, no other person. Slow push in on him, " + HOLD,
     "雨声 + 主题动机首次出现"),
    ("S06", "agnes", "缓慢前推（中景）", "老刑警到场：案子被认真写下的一刻",
     "接 AGNES：物证特写",
     "A medium shot in the front yard of the burnt house in the rain just after dawn: {C2}, holding a folded paper evidence "
     "bag against his chest with both hands, rain on his shoulders and hair, jaw set, gaze angled down and away from the "
     "camera, breath faintly visible; the background is thrown far out of focus, only soft grey rain haze, wet darkness and "
     "distant blur, a smooth clean backdrop with not a single mark, poster, notice, letter, number or sign anywhere; "
     "no vehicle, no other person in frame. Slow push in on him, " + HOLD,
     "雨声 + 证物袋纸张声（SFX paper）"),
    ("S07", "agnes", "俯视缓慢下移", "取证：白手套、证物袋、放大镜",
     "接 AGNES：城市夜景（俯瞰）",
     "A top-down close view of a plain evidence table under a work lamp: two white cotton gloves laid flat, two folded "
     "paper evidence bags, a magnifying glass, a small torch, a pair of tweezers, all on a bare grey surface; no writing, "
     "no numbers, no labels, no photographs, no people, no blood. Slow overhead descent toward the table, " + HOLD,
     "手套与纸张摩擦（SFX paper）"),
    ("S08", "agnes", "缓慢横摇（高空）", "城市：一栋栋亮着灯的住宅，明天还会有",
     "接 N02：乡村旧屋",
     "A high wide view over a rainy Seoul residential district at night, seen from a hillside: rows of low-rise roofs and "
     "lit windows spread across the frame under rain and low cloud, wet rooftops glinting, telephone wires crossing the "
     "middle distance, no illuminated signage, no letters, no numbers, no vehicles, no people. Slow lateral pan across "
     "the rooftops, " + HOLD,
     "雨声渐弱 + 低频过渡"),

    # ---------------- N02（7 镜：6 agnes + 1 信息卡）----------------
    ("S09", "agnes", "缓慢前推", "出身：全罗北道高敞郡的旧屋",
     "接 AGNES：少年背影",
     "A small low house with aged clay roof tiles in a rural village in Gochang, South Korea, in the misty early morning "
     "of the 1970s: bare earth yard, wooden door frame, stacked firewood, a single bare light bulb above the door, wet "
     "vegetable plots and low hills beyond, everything damp and grey-green, no lettering, no vehicles, no people. Slow "
     "push toward the doorway, " + HOLD,
     "清晨鸟声 + 低音铺底"),
    ("S10", "agnes", "缓慢跟拍（背影）", "少年时代：从田埂走向小镇",
     "接信息卡：前科与刑期",
     "A boy of about thirteen, seen strictly from behind and slightly below, walking away along a muddy village path at "
     "dusk in the 1980s: worn jacket, hands pushed into pockets, bare leafless trees on both sides, wet ground reflecting "
     "a grey sky, no face visible, no other people, no houses with lettering. Slow tracking shot following his back, " + HOLD,
     "脚步踩泥 + 风声"),
    ("S11", "graphic", "信息卡（静帧）", "档案：十四次前科 / 累计服刑十一年",
     "接 AGNES：监狱走廊",
     "凶手档案：出生地 / 前科次数 / 累计刑期",
     "纸张翻动（SFX paper）"),
    ("S12", "agnes", "缓慢前推", "监狱：灰色走廊与铁栏",
     "接 AGNES：会见室的离婚文件",
     "A bare prison corridor in South Korea in the early 2000s: grey painted walls, a row of iron bars along the left, "
     "harsh fluorescent light, a single guard standing far away with his back to the camera and no face visible, damp "
     "concrete floor; every wall surface completely bare, no signs, no plates, no numbers, no tags and no lettering of any "
     "kind anywhere in the corridor. Slow forward dolly down the empty corridor, " + HOLD,
     "铁门回声（SFX keys）"),
    ("S13", "agnes", "缓慢前推（特写）", "家庭：一份没有读完的离婚文件",
     "接 AGNES：出狱",
     "A close view of a metal visiting-room table: a folded document lying face-down, its blank back turned to the camera "
     "with no writing visible, and beside it a man's bare left hand resting flat on the table, no ring on the finger, "
     "short nails, faint tremor, cold fluorescent light from above, blurred grey wall behind, no other objects, no people, "
     "no lettering. Slow push toward the hand and the blank paper, " + HOLD,
     "纸页轻响（SFX paper）"),
    ("S14", "agnes", "缓慢后拉（剪影）", "出狱：二〇〇三年九月十一日",
     "接 AGNES：新住处的窗",
     "The outer gate of a South Korean prison opening onto a wet access road in the rain at midday: a single man in a "
     "plain jacket walks away from the camera through the gap, strictly from behind and rendered almost as a silhouette "
     "against the grey light, no face visible, no guards in frame, no lettering, no numbers, no vehicles, nothing else "
     "moving but rain. Slow pull back as he walks away, " + HOLD,
     "铁门开启 + 雨声"),
    ("S15", "agnes", "缓慢前推", "新住处：老姑山洞写字楼公寓的一扇窗",
     "接 N03：一部电话被拿起",
     "The exterior facade of a low-rise officetel building in Mapo-gu, Seoul, at night in the rain: a grid of identical "
     "small windows, one of them lit from inside with a pale curtain half drawn, water running down the concrete and "
     "dripping from the ledges, unlit windows dark, no building name, no numbers, no signage, no people, no vehicles. "
     "Slow push toward the single lit window, " + HOLD,
     "雨声 + 远处车流"),

    # ---------------- N03（8 镜：7 agnes + 1 信息卡）----------------
    ("S16", "agnes", "缓慢前推（特写）", "手法（一）：一部被拿起的电话",
     "接 AGNES：公寓走廊",
     "A close view of a small dark clamshell mobile phone of the early 2000s lying closed on a bare wooden desk at night, "
     "nobody in frame: the phone is shut, its small outer screen dark, the shell completely plain and unmarked, no printed "
     "brand or logo anywhere on it, a folded paper note lying face-down and unreadable beside it, a desk lamp pooling warm "
     "light on the wood, the rest of the room falling into darkness; no hands, no people. Slow push in on the phone, " + HOLD,
     "老式手机按键声（SFX phone）"),
    ("S17", "agnes", "缓慢前推", "十一名女性走进的那栋楼",
     "接信息卡：目标改变",
     "A narrow interior corridor of an officetel in Mapo-gu, Seoul, at night: identical doors along the left wall with no "
     "numbering and no name plates, worn carpet, a single flickering fluorescent tube overhead with no exit sign, a plastic "
     "bin, a mop leaning in the corner, no people, every surface plain and unmarked - no plates, no numbers, no lettering "
     "anywhere. Slow push down the empty corridor, " + HOLD,
     "灯管电流声 + 脚步不存在的静默"),
    ("S18", "graphic", "信息卡（静帧）", "口径：二〇〇四年三月起 / 十一名女性在其住所失踪",
     "接 AGNES：浴室门缝",
     "目标改变：地点与人数（公开报道口径）",
     "低音撞击"),
    ("S19", "agnes", "缓慢下移", "留给镜头的空白：只拍水与门缝",
     "接 AGNES：一个女人的背影",
     "A bathroom door standing slightly ajar in a dim officetel apartment at night: steam on the mirror above a plain "
     "porcelain sink, water running in a thin continuous thread from the tap, wet floor tiles reflecting a single warm "
     "bulb, a towel fallen on the floor, the room behind the door dark and unlit; no person, no body, no blood, no "
     "readable text, no bottles with labels. Slow downward move from the mirror to the running water, " + HOLD,
     "水流声 + 静默"),
    ("S20", "agnes", "缓慢跟拍（远景背影）", "进楼的人：只给背影，不给脸",
     "接 AGNES：远处的一排窗",
     "A woman in a plain dark coat, seen strictly from behind at a long distance, walking toward the entrance of a "
     "low-rise officetel at night in the rain: her figure small in the frame, her face never visible, one hand holding a "
     "small bag, wet pavement and a bare bulb over the doorway ahead of her, no signage, no lettering, no other people, "
     "no vehicles. Slow tracking shot following her back toward the door, " + HOLD,
     "雨声 + 高跟鞋脚步"),
    ("S21", "agnes", "缓慢横移", "城市依旧：只有那栋楼的窗户知道",
     "接 AGNES：后山树林",
     "A distant wide view of a low-rise officetel block in western Seoul at night from across a wet road: three or four "
     "windows lit, rain falling through the light, wet asphalt and a low wall in the foreground; the windows are plain "
     "rectangles of light with nothing written, printed or numbered on the glass and no sign, no banner and no lettering "
     "anywhere, no vehicles, no people. Slow lateral drift across the facade, " + HOLD,
     "雨声 + 低频"),
    ("S22", "agnes", "缓慢前推", "藏：奉元寺后山的雨雾",
     "接 AGNES：泥土与落叶",
     "A wet mountain trail behind an old temple on the northern edge of Seoul, in heavy rain and low mist: dark pine "
     "trunks, wet undergrowth pressing in from both sides, the trail surface running with water toward the camera, temple "
     "roof tiles barely visible through the trees far above, no lettering, no signs, no people, no vehicles. Slow push "
     "down the trail, " + HOLD,
     "雨打树叶 + 低频下潜"),
    ("S23", "agnes", "缓慢下移（特写）", "那些被翻动过的落叶（不出现遗体）",
     "接 N04：没人重视的失踪",
     "A close view of wet forest floor in the rain: dark turned earth, scattered wet leaves, a broken twig, rain dripping "
     "from pine needles onto the soil, a shallow hollow in the ground filled with rainwater; no body, no clothing, no "
     "tool, no blood, no people, no lettering. Slow downward move across the wet ground, " + HOLD,
     "雨滴落土 + 低音"),

    # ---------------- N04（7 镜：6 agnes + 1 信息卡）----------------
    ("S24", "agnes", "缓慢前推", "没人当回事：派出所桌上的一叠失踪材料",
     "接信息卡：最初的判断",
     "A night-time desk in a small South Korean police office in 2004: a thick stack of missing-person files with rubber "
     "bands, a rotary telephone, a desk lamp with a green glass shade, a cold cup of coffee, an electric fan, rain on the "
     "dark window behind; every sheet blank and unreadable, no printing, no stamps, no labels on the folders, the wall "
     "completely bare with no notices, no calendar, no lettering and no numbers, no people, no uniforms. Slow push in "
     "over the stack of files, " + HOLD,
     "日光灯嗡鸣 + 纸张（SFX paper）"),
    ("S25", "graphic", "信息卡（静帧）", "最初的判断：拐卖案件",
     "接 AGNES：后巷入口",
     "一开始没被并案：警方最初的判断（公开报道口径）",
     "低音铺底"),
    ("S26", "agnes", "缓慢前推", "店与巷：一台电话连着的地方",
     "接 AGNES：老板露面",
     "A narrow back alley behind a low commercial building in Seoul at night: a bare bulb above a plain unmarked service "
     "door, drainage water running along the concrete, stacked crates, a bicycle leaning on the wall, rain falling "
     "through the cone of light; the concrete walls are plain and slightly out of focus with no stencil marks, no plates, "
     "no shopfront, no signboard, no neon and no lettering or numbers anywhere, no people, no vehicles. Slow push "
     "toward the unmarked door, " + HOLD,
     "雨声 + 塑料箱轻碰"),
    ("S27", "agnes", "缓慢前推（中景）", "转机：那个记号码的人",
     "接 AGNES：纸上的笔",
     "A medium shot behind the counter of a small massage parlour in Seoul at night: {C3}, holding an open notebook in one "
     "hand, a pen in the other, head turned to look off toward the left of the frame, one phone on the counter and a "
     "second handset off the hook beside it, warm bulb light on his face and the notebook, the pages turned away from the "
     "camera and unreadable, no signage, no lettering, no numbers, no customers, no other person. Slow push in on him, " + HOLD,
     "座机听筒搁下 + 纸页（SFX paper）"),
    ("S28", "agnes", "缓慢前推（特写）", "手上的证据：号码被一圈圈画住",
     "接 AGNES：老板与警员的背影",
     "A close view of a hand pressing a pen onto an open notebook page at a counter at night: the page angled away from "
     "the camera so no writing is legible, the pen tip touching the paper, a ring of lamplight on the page, a second "
     "notebook beside it with a folded corner, no readable text or numbers, no other person, no signage. Slow push in on "
     "the hand and pen, " + HOLD,
     "笔尖划纸（SFX paper）"),
    ("S29", "agnes", "缓慢横移（背影）", "报警：老板带着人去了警局",
     "接 AGNES：凌晨的巷子",
     "The parlour owner and a uniformed police officer, both seen from behind and from the chest down to the knees, "
     "standing in a doorway at night while rain falls beyond them in the street: the officer's hand rests on a closed "
     "blank notebook, the owner's shoulders squared, both see only from behind with no faces visible, the uniforms plain "
     "dark fabric with no badges, no lettering and no numbers, the street beyond thrown out of focus with no legible "
     "marks, no vehicles, no other people. Slow lateral move across their backs and the rain beyond, " + HOLD,
     "雨声 + 低声交谈（无对白，仅环境）"),
    ("S30", "agnes", "缓慢前推", "七月十五日凌晨：麻浦区的巷口",
     "接 N05：手电扫过湿墙",
     "A narrow alley mouth in Mapo-gu, Seoul, before dawn on a wet July night in 2004: an unmarked pale sedan standing "
     "with its headlights on, rain slanting through the beams, a low brick wall on the left, water running along the "
     "kerb; the car's front plate area is plain and blank with no plate and no numbers, the shop wall behind the car is "
     "out of focus with no sign and no lettering, no signage anywhere, no people in the frame. Slow push toward the "
     "alley mouth and the light, " + HOLD,
     "雨声 + 引擎怠速（SFX machine）"),

    # ---------------- N05（8 镜：7 agnes + 1 信息卡）----------------
    ("S31", "agnes", "缓慢前推", "抓捕：手电光下低着的那颗头",
     "接 AGNES：审讯室（C1 露脸）",
     "Three figures lit from behind by torch beams stand around a fourth in a narrow wet alley in Seoul before dawn: the "
     "three are plain-clothed and see only as silhouettes from behind, the fourth stands with his head lowered and his "
     "back to the camera, shoulders slack, rain running off his jacket, the wet brick wall behind them completely plain with "
     "no stencilled marks, no plates, no numbers and no lettering anywhere; no faces visible, no weapons raised, no "
     "violence. Slow push in on the group, " + HOLD,
     "雨声 + 手电开关"),
    ("S32", "agnes", "缓慢前推（中景）", "审讯：他说出了警方没掌握的案子",
     "接 AGNES：空椅子与手铐",
     "A medium shot inside a plain interrogation room at night: {C1}, seated at a metal table, the raincoat off and folded "
     "on the chair behind him, hands flat on the table in front of him, head lifted and turned a little away from the "
     "lamp, a desk lamp behind the table throwing hard light across one side of his face, a cassette recorder and a "
     "glasses-case on the table; grey concrete walls, no lettering, no numbers, no files with readable text, no other "
     "person. Slow push in on him, " + HOLD,
     "录音机按键 + 低频"),
    ("S33", "agnes", "缓慢前推", "那十二个小时：空椅子与挂着的手铐",
     "接 AGNES：凌晨的站前街道",
     "An empty holding bench in a police corridor at night: one half-open handcuff hanging from the metal rail above the "
     "bench, a door standing ajar at the end of the corridor, cold fluorescent light, a bucket and a mop against the "
     "wall, wet footprints on the floor tiles, no people, no lettering, no numbers, no notices on the walls. Slow push "
     "down the corridor toward the open door, " + HOLD,
     "走廊回声（SFX keys）"),
    ("S34", "agnes", "缓慢横摇", "十二小时后：永登浦站附近",
     "接 AGNES：两次审讯",
     "A rainy pre-dawn street near a railway station in Seoul in 2004: wet asphalt, a low station wall, tram rails in the "
     "foreground glinting with water, the red and blue glow of an unseen patrol light sweeping slowly across the road and "
     "the wall, a single distant figure walking away with no face visible, no signage, no letters, no numbers, no "
     "vehicles in frame. Slow lateral pan following the light across the wet road, " + HOLD,
     "雨声 + 远处警灯电流"),
    ("S35", "agnes", "缓慢前推（双人中景）", "对质：两次审讯之间",
     "接信息卡：关键日期",
     "A two-shot at a metal table in a bare interrogation room at night: an older detective sits on the left, leaning "
     "forward with both hands flat on the table and his back and shoulders toward the camera so that his face is never "
     "visible; {C1} sits on the right with his forearms on the table and his head raised, lit hard by the desk lamp; "
     "between them several photographs lie face-down and unreadable, the wall behind is bare concrete, no lettering, no "
     "numbers, no readable text, no third person. Slow push in between the two of them, " + HOLD,
     "椅子挪动 + 低频"),
    ("S36", "graphic", "信息卡（静帧）", "关键日期：七月十五日抓捕 / 七月十八日指认现场",
     "接 AGNES：后山搜山",
     "关键日期卡：抓捕与指认现场",
     "低音撞击 + 雨声"),
    ("S37", "agnes", "缓慢横移", "后山：警戒线在雨里",
     "接 AGNES：警局门口的镜头",
     "A rain-soaked hillside behind an old temple on the edge of Seoul in the daytime: a line of white and blue plastic "
     "tape strung between pine trunks, three investigators in dark rain gear standing with their backs to the camera "
     "among the trees, wet undergrowth, mist between the trunks, a steel bucket and a spade on the ground, the tape "
     "completely plain with no printing and no lettering; no faces visible, no body, no clothing, no numbers, nothing "
     "written anywhere. Slow lateral move across the tape line and the workers, " + HOLD,
     "雨打树林 + 低频"),
    ("S38", "agnes", "缓慢前推（背影）", "舆论：雨里围着的记者群（构图中不出现建筑）",
     "接 N06：法院外的雨",
     "A tight crowd of reporters in the rain in Seoul in 2004, photographed from behind: only the backs of heads and "
     "shoulders, raised microphones held low and one shoulder-mounted camera stripped of every marking, its body plain dark "
     "plastic with no logo, no channel number and no lettering anywhere, umbrellas, wet steps underfoot; beyond the crowd "
     "the frame holds only falling rain, wet asphalt and the soft grey darkness of a wet night - no building, no windows, "
     "no door, no glass, no reflection, no signage and no lettering anywhere; no faces visible. Slow push in over the "
     "shoulders into the rain, " + HOLD,
     "快门连响（SFX press）+ 嘈杂人声"),
    ("S39", "agnes", "缓慢前推", "审判：法院外的雨",
     "接 AGNES：法庭内",
     "The exterior of a South Korean courthouse on a cold rainy morning in December 2004: broad stone steps running with "
     "water, a row of umbrellas held by people whose backs are turned to the camera, a police officer's shoulder in the "
     "foreground, wet flagstones reflecting grey light, the building's columns rising out of frame; the entrance is deep "
     "shadow with no emblem, no signage, no lettering, no numbers anywhere, no faces visible. Slow push in up the "
     "steps, " + HOLD,
     "雨声 + 人群低语"),
    ("S40", "agnes", "缓慢前推（手部近景）", "判决：木槌落在没有字的判决书上",
     "接信息卡：判决时间线",
     "A close side view of a courtroom bench in South Korea in December 2004: a judge's hands, seen without the face, "
     "resting on a blank document on the bench, a wooden gavel standing upright beside them, a fountain pen, a thick "
     "closed law book, dark wood panelling behind, warm light from above, no readable text anywhere, no insignia, no "
     "other person. Slow push in on the hands and the gavel, " + HOLD,
     "木槌轻落（SFX press）+ 纸张"),
    ("S41", "graphic", "信息卡（静帧）", "判决：一审死刑 / 最高法院维持",
     "接 AGNES：监狱外墙",
     "判决时间线：一审与终审",
     "低音撞击"),
    ("S42", "agnes", "缓慢后拉", "未执行：监狱的墙与雨",
     "接信息卡：案件之后",
     "The outer wall of a detention centre in South Korea on a rainy evening: long grey concrete wall with coils of razor "
     "wire along the top, a tall steel gate, a single lamp on a pole, wet asphalt in the foreground, low cloud above, "
     "cold blue-grey light; the concrete wall is completely bare - smooth panels with no plates, no markings, no "
     "numbers and no lettering of any kind, the gate plain, no vehicles, no people. Slow pull back from the wall and "
     "the gate, " + HOLD,
     "雨声 + 远处铁门"),
    ("S43", "graphic", "信息卡（静帧）", "案件之后：一九九七年起未再执行死刑 / 他仍在服刑",
     "接 AGNES：空走廊",
     "案件之后：死刑执行状态与在押（公开报道口径）",
     "低音铺底"),
    ("S44", "agnes", "缓慢前推", "没有被执行的时间：空牢房走廊",
     "接 AGNES：挂着的雨衣",
     "An empty prison wing in South Korea in the 2000s: a long row of cell doors with small barred openings, a caged bulb "
     "burning at the far end, a wet mop bucket and a broom against the wall, worn concrete floor, one barred window "
     "letting in grey daylight at the side, no people, no lettering, no numbers, no notices. Slow push down the empty "
     "corridor, " + HOLD,
     "空走廊回声 + 低频"),
    ("S45", "agnes", "缓慢后拉（暗下去）", "金句画面：一件挂着的黄色雨衣",
     "片尾卡叠在最后一秒上",
     "An empty room at night in Seoul: a dark yellow raincoat hanging from a hook on a bare wall, water still dripping "
     "from its hem onto the floorboards, rain streaming down a black window beside it with the blurred glow of the city "
     "beyond, one unshaded bulb above, nothing else in the room, no people, no lettering, no numbers, no furniture. Slow "
     "pull back into the darkness of the room, " + HOLD,
     "雨声渐远 + 片尾音乐"),
]

# ---------------------------------------------------------------------------
# 画面上的文字（render.py 从 story.json 的 presentation 块读，不在 render.py 里写死）
# ---------------------------------------------------------------------------
CARD_HEADER = "案件档案  /  首尔 · 二〇〇三—二〇〇四"              # 每张信息卡左上角的小字
CARD_FOOTER = "公开报道口径 · 并非原始档案影像"                    # 每张信息卡左下角的小字
# 信息卡文案：镜头号 -> (大标题, 第一行, 第二行)。只写公开报道里的事实，不写推测。
CARDS = {
    "S02": ("柳永哲连环杀人案", "大韩民国 · 首尔 二〇〇三—二〇〇四", "十个月 · 二十条人命"),
    "S11": ("凶手档案", "一九七〇年生 · 全罗北道高敞郡", "前科十四次 · 累计服刑十一年"),
    "S18": ("他换掉了目标", "二〇〇四年春天起 · 麻浦区", "十一名女性在其住所失踪"),
    "S25": ("一开始，没人当回事", "失踪报案未并案侦查", "警方最初判断：拐卖案件"),
    "S36": ("二〇〇四年七月", "十五日 抓捕 · 十八日 指认现场", "奉元寺后山 · 十一具遗体"),
    "S41": ("判决", "二〇〇四年十二月十三日 一审死刑", "二〇〇五年六月 最高法院维持"),
    "S43": ("案件之后", "韩国自一九九七年起未再执行死刑", "他至今仍在监狱中服刑"),
}
# 片头字幕卡（0.35–4.7 秒叠在第一镜上）：两行，第二行小字
TITLE_CARD = ["韩国雨衣杀手：十个月，二十条人命", "二〇〇三—二〇〇四 · 首尔 · 二十人遇害"]
# 片尾卡（最后 3.8 秒）：大字提问 / 一行案件信息 / 一行金句 / 一行资料来源
END_CARD = [
    "你能认出走在人群里的他吗？",
    "柳永哲连环杀人案 · 二〇〇三—二〇〇四 · 二十人遇害",
    "危险从不写在脸上，它就走在人群里。",
    "资料：Korea Herald / Korea JoongAng Daily / Newsweek · 原创解说 · AI动画情景重现",
]
# 字幕里描黄的关键词（人名、数字、结论词）
CAPTION_KEYWORDS = [
    "二零零三年九月", "二十人", "电话号码",
    "柳永哲", "十四次", "十一年",
    "出狱十三天", "伪造的警察证件", "十一名女性",
    "同一个号码", "报警",
    "七月十五日", "十二个小时", "十一具遗体",
    "死刑", "一九九七年", "粉丝俱乐部",
]
# 逐镜标签覆盖：默认 agnes 镜头标「AI动画情景重现 · 非新闻影像」，法庭/审讯/搜查/监狱镜头写得更具体
LABEL_OVERRIDES = {
    "S24": "AI动画情景重现 · 非警方档案影像",
    "S31": "AI动画情景重现 · 非抓捕现场影像",
    "S32": "AI动画情景重现 · 非审讯影像",
    "S33": "AI动画情景重现 · 非警方拘留室影像",
    "S35": "AI动画情景重现 · 非审讯影像",
    "S37": "AI动画情景重现 · 非搜查现场影像",
    "S38": "AI动画情景重现 · 非新闻采访影像",
    "S39": "AI动画情景重现 · 非法院实景",
    "S40": "AI动画示意 · 非庭审影像",
    "S42": "AI动画情景重现 · 非监狱实景",
    "S44": "AI动画情景重现 · 非监狱实景",
}
# 合成音效事件：(镜头号, 类型)，类型可选 paper / phone / keys / machine / press，落在该镜开始前 0.18 秒
SFX_EVENTS = [
    ("S06", "paper"),
    ("S16", "phone"),
    ("S11", "paper"),
    ("S24", "paper"),
    ("S27", "paper"),
    ("S30", "machine"),
    ("S33", "keys"),
    ("S38", "press"),
    ("S40", "press"),
]

# ---------------------------------------------------------------------------
# 发布文案（抖音脚本.md / 抖音发布文案.md 用）
# ---------------------------------------------------------------------------
TITLES = [
    "十个月杀二十人，抓到他的不是监控，是一部被店员记下来的电话号码｜韩国头号连环杀人案",
    "韩国雨衣杀手柳永哲：专杀富人和按摩女，2004年被抓时他刚准备再动手",
    "他把这座城市吓了十个月，最后栽在按摩店老板的一个笔记本上",
]
HOOK = "二〇〇三年九月到二〇〇四年七月，首尔二十人被杀；警方一直没能并案，破案的线索来自按摩店老板记下的一个电话号码。"
GOLDEN_LINES = [
    "危险从不写在脸上，它就走在人群里。",
    "真正让他走到这一步的，是他在监狱里读过的那本杂志。",
    "你能认出走在人群里的他吗？评论区聊聊。",
]
DESCRIPTION = (
    "二〇〇三年九月，首尔江南区新沙洞，一对老夫妇在家里遇害，房子随后起火，值钱的东西一件没少。十个月后警方才确认，"
    "这只是二十条人命里的第一起。凶手叫柳永哲，前科十四次，累计服刑十一年；他先挑富人区的独栋住宅，后来又用伪造的警察证件，"
    "把按摩女约到自己住的写字楼公寓。抓到他不是靠监控和指纹，而是一家按摩店老板记下的电话号码。"
    "本片画面为 AI 生成的情景重现（非新闻影像），事实依据公开报道整理；部分口径存在分歧处只写区间，不作定论。你能认出走在人群里的他吗？"
)
QUESTION = "你能认出走在人群里的他吗？"
HASHTAGS = ["#悬疑", "#真实案件", "#韩国", "#雨衣杀手", "#案件解说"]

GRID = 4           # 规划网格：每镜 4 秒，45 镜 = 180 秒
AGNES_SECONDS = 7  # 每个 Agnes 镜头实际请求的时长（169 帧 @ 24 fps）
SEED_BASE = 20260924  # 首案的日子（二〇〇三年九月二十四日），让 seed 可追溯

# 露脸镜头登记（镜头号 -> 角色 id）：只有这里登记的镜头允许出现面容 token，
# 与 cast.json 的 shots 映射一一对应（face_cast.py check-prompts 两边都查）。
FACE_SHOTS = {
    "S05": ["C1"],
    "S06": ["C2"],
    "S27": ["C3"],
    "S32": ["C1"],
    "S35": ["C1"],
}
# 用定妆照做首帧（图生视频）的镜头：每个角色的首次露脸镜头，把这张脸钉在观众第一眼里。
# 定妆照提交在仓库里，URL 取 cast.json 的 portrait_url（Agnes 只在服务器侧取图）。
REFERENCE_SHOTS = {"S05": "C1", "S06": "C2", "S27": "C3"}


def faces():
    """从 cast.json 读面容 token（唯一来源），保证提示词里逐字节一致。"""
    cast = json.loads(CAST.read_text(encoding="utf-8"))
    return {c["id"]: (c.get("face") or "").strip() for c in cast.get("characters", [])}


def portrait_urls():
    cast = json.loads(CAST.read_text(encoding="utf-8"))
    return {c["id"]: (c.get("portrait_url") or "") for c in cast.get("characters", [])}


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
    face = faces()
    url = portrait_urls()
    for cid in {cid for ids in FACE_SHOTS.values() for cid in ids}:
        assert face.get(cid), f"cast.json 里没有角色 {cid} 的面容 token"
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
        prompt = body
        if kind == "agnes":
            for cid, token in face.items():
                prompt = prompt.replace("{" + cid + "}", token)
            assert "{" not in prompt and "}" not in prompt, f"{sid} 提示词里还有没替换的占位符"
        shot = {
            "id": sid, "kind": kind, "start": start, "duration": GRID,
            "narration_id": f"N{min(6, start // 30 + 1):02d}",
            "prompt": prompt if kind == "agnes" else "",
            "purpose": purpose, "transition_out": transition,
            "graphic": body if kind == "graphic" else "",
            "seed": SEED_BASE + i + 1,
            "seconds": AGNES_SECONDS, "aspect": "16:9", "resolution": "1080p", "frame_rate": 24,
            "camera": camera, "sfx_note": sfx,
        }
        if sid in FACE_SHOTS:
            shot["cast"] = FACE_SHOTS[sid]
        if sid in REFERENCE_SHOTS:
            shot["reference_image"] = url[REFERENCE_SHOTS[sid]]
        shots.append(shot)
    story["shots"] = shots
    story["presentation"] = presentation()
    story.setdefault("_scaffold", {})["note"] = (
        "内容由 build_story.py 一次性写入；45 镜 × 4 秒规划网格（每镜只用一次）；"
        "露脸模式：面容 token 只在 cast.json 里写一份，build_story.py 用占位符注入，保证逐字节一致；"
        "解说词与 screenplay.md、audio/manifest.json 三处逐字一致由 generate.py --validate 守着。")
    PLAN.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n")

    manifest = json.loads(MANIFEST.read_text())
    for clip, chapter in zip(manifest["clips"], story["chapters"]):
        assert clip["id"] == chapter["id"]
        clip["text"] = chapter["text"]
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    kinds = [s["kind"] for s in story["shots"]]
    chars = sum(len(c["text"]) for c in story["chapters"])
    print(f"story.json 已写入：{len(shots)} 镜 = {kinds.count('agnes')} agnes + {kinds.count('graphic')} graphic，"
          f"解说 {chars} 字（含标点）")
    print("逐章字数：" + " / ".join(f"{c['id']} {len(c['text'])}" for c in story["chapters"]))
    print(f"露脸镜头：{len(FACE_SHOTS)} 镜；定妆照首帧：{len(REFERENCE_SHOTS)} 镜")
    todo = json.dumps(story, ensure_ascii=False).count("TODO")
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
