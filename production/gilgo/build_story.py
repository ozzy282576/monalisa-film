#!/usr/bin/env python3
"""把《吉尔戈海滩：披萨盒里的凶手》的剧本内容写进 story.json 骨架。

只在开工时跑一次；之后直接改 story.json。留着这个文件是为了让
"解说词 / 分镜 / 来源" 的原始编辑意图可追溯，并且让 `抖音脚本.md`
的分镜表能从同一份数据生成（`--script` 参数），三处不会各写各的。

用法::

    python3 production/gilgo/build_story.py            # 写 story.json + audio/manifest.json 文本
    python3 production/gilgo/build_story.py --script   # 生成 抖音脚本.md（标题/爆点/四列分镜表/金句）
    python3 production/gilgo/build_story.py --publish  # 生成 抖音发布文案.md（题目/介绍/提问读者一句话/话题）
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "story.json"
MANIFEST = HERE / "audio" / "manifest.json"

TITLE = "吉尔戈海滩：披萨盒里的凶手"

# 与 production/pizzabomber 同一路线：Agnes 生成的是**风格化 2D 动画纪录片**镜头，
# 不冒充真实影像，也不需要任何真实人物的脸。调色比披萨炸弹那部更冷。
STYLE_PREFIX = (
    "Stylized 2D animated documentary illustration with hand-painted graphic-novel textures and soft "
    "cel shading, contemporary Long Island New York and Midtown Manhattan between 2010 and 2026: "
    "suburban shingle houses, commuter trains, Midtown glass towers, barrier-beach dunes and a straight "
    "coastal parkway, county courtrooms and forensic laboratories; horizontal 16:9 cinematic composition, "
    "muted palette of slate blue, steel grey, dune-grass ochre and sodium-orange practical light, overcast "
    "Atlantic winter daylight or cool interior practical light, restrained procedural true-crime mood, no "
    "horror excess; every character is shown only from behind, in silhouette, or as hands and props - "
    "never a clear frontal face; absolutely no readable text, letters, numbers, logos, license plates or "
    "brand marks anywhere inside the frame; one single continuous smooth slow camera move per shot "
    "exactly as directed. "
)

NEGATIVE_PROMPT = (
    "readable text, letters, numbers, words, signage writing, invented headlines, logos, brand marks, "
    "watermark, subtitles, on-screen caption, photorealistic face, recognizable real person likeness, "
    "frontal face close-up, eyes visible in detail, blood, gore, wound, corpse, body bag, body parts, "
    "autopsy, violence, assault, strangling, weapon attack, gun, firearm, nudity, erotic content, horror "
    "monster, ghost, jump scare, 3D render look, plastic CGI, distorted anatomy, deformed hands, extra "
    "fingers, extra limbs, duplicated people, changing face, morphing objects, teleportation, jitter, "
    "flicker, whip pan, fast zoom, jump cut, split screen, collage, 1940s period costume"
)

PRINCIPLES = [
    "全部 Agnes 镜头为风格化 2D 动画情景重现，画面常驻标注「AI动画情景重现 · 非新闻影像」，不冒充庭审、监控或证物照片",
    "不展示遗体、血腥或侵害过程；地下室只画楼梯、灯泡与硬盘，不重现作案",
    "凶手雷克斯·赫曼只以背影、剪影、手部出现，不用 AI 生成的脸冒充本人；真实人物只允许使用有出处的档案照片（本片未使用）",
    "受害者不以任何人像出现，只用信息卡与象征物（一次性手机、麻布、路边花束）致意",
    "每一句事实都能指到 sources 里的一条公开报道；未被起诉的第八起命案只写「承认」不写「判决」",
    "所有中文姓名、日期、字幕后期添加，不交给视频模型拼写",
    "同一地点保留光线、道具、运动方向；跨地点通过声音桥与物件（披萨盒、垃圾桶、皮卡）匹配衔接",
    "人工检视 qa/ 接触表，露脸、畸变、伪文字的镜头用 {\"only\":\"Sxx\"} 重生成，不直接进成片",
]

SOURCES = [
    {"id": 1, "url": "https://apnews.com/article/rex-heuermann-guilty-pleas-gilgo-beach-killings-a7f4b1013f1f9fd085a390a26e62fd97",
     "usage": "2026-04-08 认罪：7 项谋杀罪 + 承认第 8 名受害者 Karen Vergata；1993–2010；62 岁；建筑师"},
    {"id": 2, "url": "https://www.cbsnews.com/newyork/news/gilgo-beach-serial-killer-rex-heuermann-guilty-plea/",
     "usage": "当庭陈述：一次性手机、以金钱引诱、粗麻布捆绑、沿海洋公园大道弃置；3 项一级 + 4 项二级谋杀；检察官「假扮普通郊区爸爸」"},
    {"id": 3, "url": "https://en.wikipedia.org/wiki/Gilgo_Beach_serial_killings",
     "usage": "时间线：2023-07-13 被捕；2026-04-08 认罪；2026-06-17 判终身监禁不得假释"},
    {"id": 4, "url": "https://www.cnn.com/2023/07/14/us/gilgo-beach-murders-suspect-arrest",
     "usage": "披萨边 DNA；妻子毛发来自门口垃圾桶 11 个瓶子；案发时妻儿在外州；2022-03-14 名字首次出现（州警数据库）；用受害者手机打挑衅电话"},
    {"id": 5, "url": "https://www.newsday.com/long-island/crime/gilgo-beach-killings-rex-heuermann-e8rqf5vb",
     "usage": "披萨边与用过的餐巾在曼哈顿被跟踪小组取走；线粒体 DNA 排除 99.96% 北美人口；电线杆摄像头监控约一年半；搜家 12 天"},
    {"id": 6, "url": "https://patch.com/new-york/massapequa/rex-heuermanns-latest-cheek-swab-matches-pizza-crust-dna-reports",
     "usage": "2023-01-26 跟踪小组在曼哈顿回收披萨盒；口腔拭子与披萨边 DNA 一致"},
    {"id": 7, "url": "https://www.cnn.com/2024/06/09/us/rex-heuermann-gilgo-beach-murders-document/index.html",
     "usage": "「蓝图」：2000 年创建、多年修改的 Word 文档，存于家中地下室硬盘；pre-prep / prep / body prep / post event 分节"},
    {"id": 8, "url": "https://people.com/gilgo-beach-serial-killing-suspect-allegedly-had-planning-document-say-prosecutors-8659372",
     "usage": "文档栏目 Problems / Supplies / DS / TRG；「small is good」；「get sleep before hunt too tired creats problems」"},
    {"id": 9, "url": "https://www.newsweek.com/gilgo-beach-serial-killer-rex-heuermann-notes-victims-1909659",
     "usage": "文档名 HK2002-04；2024-03-07 从地下室硬盘恢复"},
    {"id": 10, "url": "https://www.nytimes.com/2026/04/08/nyregion/gilgo-beach-murders.html",
     "usage": "作案模式：等家人外出、用一次性手机联系、接到马萨皮夸公园家中地下室；2000 年文档"},
    {"id": 11, "url": "https://www.koat.com/article/years-in-the-making-evidence-long-island-serial-killer/44554094",
     "usage": "办公室在帝国大厦附近的第五大道；2022 年 3 月查到第一代雪佛兰 Avalanche 登记在其名下；专案组含县警、州警、FBI；在办公室附近被捕"},
    {"id": 12, "url": "https://www.krqe.com/news/national/ap-long-island-serial-killer-probe-not-over-after-architect-is-charged-in-3-of-11-deaths/",
     "usage": "专案组成立六周后州警调查员用数据库查到 Avalanche 车主；目击者称案发前夜该车停在 Costello 家外；翻垃圾取 11 个瓶子与披萨边"},
    {"id": 13, "url": "https://nz.finance.yahoo.com/news/gilgo-beach-killings-were-true-120516790.html",
     "usage": "身高 6 英尺 4 英寸（约 1.93 米）；2010-09-01/02 皮卡两晚出现在 Costello 家外；基站数据；2022-07 门口瓶子送检"},
    {"id": 14, "url": "https://www.theguardian.com/us-news/2026/apr/12/police-taskforce-gilgo-beach-serial-killer",
     "usage": "新任局长 Rodney Harrison 组建专案组；马萨皮夸公园距曼哈顿约 30 英里；认罪后配合 FBI 行为分析组"},
    {"id": 15, "url": "https://www.usatoday.com/story/news/crime/2026/06/17/gilgo-beach-serial-killer-rex-heuermann-sentenced/90570604007/",
     "usage": "2026-06-17 宣判；「跨越 17 年以上」；专案组低调工作以麻痹嫌疑人"},
]

# 六段解说。措辞刻意用新闻语体（「命案」「受害者」「弃置」），
# 一是抖音审核，二是配音 TTS 的内容审核——第一版试音里「他怎么杀」直接被拦。
CHAPTERS = [
    ("N01", "黄金开头：一个披萨盒",
     "一个曼哈顿的建筑咨询师，办公室就在帝国大厦旁边，有老婆有孩子，邻居眼里的模范爸爸。三十年，没人怀疑过他。最后让他暴露的，是一个扔进垃圾桶的披萨盒。这就是美国近年最离奇的悬案：长岛吉尔戈海滩连环案。今天一口气讲清楚：他是怎么隐藏的，又是怎么栽的。"),
    ("N02", "双面人生",
     "先说他是谁。雷克斯·赫曼，身高一米九三，长岛马萨皮夸公园人，住的还是他小时候的房子。白天，他坐火车进曼哈顿，给纽约的大楼做建筑合规咨询；晚上，回家陪妻子和两个孩子。可就在这栋房子的地下室里，藏着一份写于两千年的文件。它是什么，我们后面再说。"),
    ("N03", "作案手法",
     "他盯上的，大多是在网上招揽客人的年轻女性。套路极其固定：等老婆孩子出门旅行，用一次性手机联系对方，约到家里。地下室里发生了什么，只有他知道。之后，他用粗麻布把她们裹住，沿着海洋公园大道，弃置在吉尔戈海滩的荒草丛里。从一九九三到二零一零，十七年，至少八名受害者。更过分的是，他还用其中一名受害者的手机，打电话挑衅她的家人。"),
    ("N04", "一辆皮卡",
     "二零一零年底，四名受害者的遗体被发现，全美震动。可十几年过去，警方一无所获。转机在二零二二年：新任局长成立专案组，把老卷宗翻了个底朝天。一条被忽略的目击证词跳了出来：嫌疑人开一辆墨绿色的雪佛兰雪崩皮卡。数据库一查，车主，正是赫曼。接下来一年半，警察没抓人，而是悄悄跟着他——等他扔垃圾。"),
    ("N05", "披萨盒与作案清单",
     "二零二三年一月二十六日，曼哈顿街头，赫曼吃完披萨，随手把盒子扔进垃圾桶。跟踪小组马上捡走。披萨边上的DNA，和当年麻布上留下的一根男性毛发比对：百分之九十九点九六的北美人都能排除，他不能。七月十三日，他在办公室门口被捕。警方搜了他家十二天，拉走了地下室的硬盘。后来在里面，翻出一份两千年建的Word文档，一份作案清单：问题栏写着毛发、DNA、指纹；目标栏写着，小个子好。"),
    ("N06", "结局与金句",
     "清单里还有一条：行动前要睡够，太累会出问题。写下这句话的人，第二天照常去上班。二零二六年四月八日，六十二岁的赫曼当庭认罪，承认了八起命案；六月，被判终身监禁，不得假释。三十年的悬案，最后输给了一块没吃完的披萨边。所以，别再迷信什么完美犯罪。你扔掉的每一样东西，都在替你说话。你觉得，是他太蠢，还是警察太耐心？评论区聊聊。"),
]

# 每一镜：(id, kind, 运镜, 叙事职责, 衔接方式, 英文提示词或信息卡文案, 音效/备注)
# 45 镜 = 38 个 Agnes 动画镜头 + 7 张信息卡，**按成片顺序编号，每个镜头只出现一次，不复用**。
# 规划网格 4 秒/镜（45×4=180），Agnes 每镜实际请求 7 秒（169 帧 @24fps），
# render.py 的 CUTS 按配音停顿决定每镜真正的时长（2～7 秒）。
# 抖音脚本表里的"口播文案"列按 CUTS 的切点从 CHAPTERS 里切出来，不在这里重复抄一遍。
SHOTS = [
    # ---------------- N01 黄金开头（6 镜）----------------
    ("S01", "agnes", "横向跟拍 lateral track",
     "0–5 秒钩子：第五大道傍晚，一个高出人群一头的西装背影走向写字楼，远处帝国大厦",
     "背影进楼门，硬切郊区住宅",
     "Midtown Manhattan Fifth Avenue at blue-hour dusk, a very tall heavyset man in a dark suit with a shoulder bag walks away from camera along a busy sidewalk toward a glass office lobby, the Empire State Building rising softly behind, yellow taxis and warm street light. Camera: one smooth lateral tracking move keeping him in the middle distance, back to camera the entire time, no faces anywhere.",
     "低频心跳垫底；开口第一句无音乐，只有城市环境声"),
    ("S02", "agnes", "升降下摇 crane down",
     "「有老婆有孩子，模范爸爸」：长岛郊区独栋住宅，草坪、童车、家庭轿车，无人",
     "摇到车道，硬切邻里街景",
     "Quiet Long Island suburban street at golden hour, a modest two-story wood-shingle house with a front porch, a child's bicycle on the lawn, a family sedan in the driveway, mature trees, two curbside trash cans at the end of the driveway; no people. Flat Long Island suburb: the horizon holds only trees, utility poles and low rooftops - no skyscrapers, no city skyline anywhere in the background. Camera: one slow crane move down from tree height to street level, ending on the driveway. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "鸟鸣、远处割草机"),
    ("S03", "agnes", "缓慢横摇 slow pan",
     "「三十年，没人怀疑过他」：正午的郊区街道，高个背影在车道上冲洗皮卡，远处邻居遛狗挥手",
     "邻居挥手时切披萨盒特写",
     "Sunny midday in a Long Island suburban driveway, camera low and close: a very tall heavyset man seen from behind hoses down a dark pickup truck, water sheeting off the tailgate and sparkling on the concrete, a coiled garden hose at his feet, an American flag on the porch post; the wood-shingle side wall of his house and a tall green hedge fill the entire background from edge to edge, so no sky, no horizon and no distant buildings are visible; no faces. Camera: one slow low dolly along the wet truck toward the man's back. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "洒水器、狗叫、远处招呼声；音乐第一次进"),
    ("S04", "agnes", "微距固定 macro static",
     "全片钩子：一只大手把油腻的披萨盒塞进街头垃圾桶（只拍手与袖口）",
     "垃圾桶的金属声延到信息卡",
     "Extreme close-up of a green wire-mesh New York City sidewalk trash can; a large man's hand in a dark suit sleeve and white shirt cuff pushes a greasy folded cardboard pizza box down into the can and withdraws out of frame, shallow depth of field, pedestrians blurred behind. Camera: locked-off macro with a slight rack focus from the hand to the box.",
     "纸板摩擦 + 金属桶「哐」一声；字幕高亮「披萨盒」"),
    ("S05", "graphic", "信息卡 static card",
     "案件名片：案名、年代、地点、受害者数（不依赖 AI 拼字）",
     "卡片硬切航拍海滩",
     "吉尔戈海滩连环案\n纽约长岛 · 海洋公园大道沿线 · 1993—2010\n至少8名受害者 · 多为在网上招揽客人的年轻女性",
     "卡片入场「咔」一声；解说念到「长岛吉尔戈海滩连环案」时出现"),
    ("S06", "agnes", "航拍前飞 aerial forward drift",
     "地点建立：海洋公园大道笔直穿过沙丘与盐沼，冬季阴天，无人",
     "航拍结束音乐重音，切人物档案卡",
     "Low-altitude aerial view of Ocean Parkway on Long Island's barrier beach in winter: a straight two-lane highway between wind-flattened dunes, brown marsh grass and grey Atlantic surf under an overcast sky, a few distant cars, no people. Camera: one slow forward aerial drift along the road at about thirty meters altitude.",
     "海风 + 低音鼓点；「怎么栽的」落点后 0.5 秒静默再进第二章"),
    # ---------------- N02 双面人生（7 镜）----------------
    ("S07", "graphic", "档案卡 static card",
     "人物档案卡：姓名、职业、身高、居住地、家庭，全部为公开报道信息",
     "卡片硬切老宅",
     "雷克斯·赫曼\n曼哈顿建筑合规咨询师 · 身高1.93米\n长岛马萨皮夸公园 · 已婚 · 两个孩子 · 住在从小长大的房子里",
     "打字机式逐行出现；不放本人照片（红线）"),
    ("S08", "agnes", "缓慢推近 slow push-in",
     "「住的还是他小时候的房子」：同一栋房子的七十年代记忆版，褪色暖调，老式旅行车，草坪上的童车",
     "推近到门廊，硬切通勤站台",
     "A faded 1970s memory of a modest Long Island shingle house, framed tight from the front lawn: the sun-bleached front porch and a wood-paneled station wagon in the driveway fill the frame, a child's tricycle on the grass, a sprinkler ticking, warm film-grain softness; the house facade and a big maple tree occupy the entire background from edge to edge, so no sky, no horizon and no distant buildings are visible; no people. Camera: one slow push-in toward the porch steps. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "老式洒水器嘀嗒、胶片颗粒感的底噪"),
    ("S09", "agnes", "固定大全景 static wide",
     "白天坐火车进曼哈顿：长岛铁路站台清晨，一个高出人群一头的黑大衣背影",
     "列车进站的风声接办公室",
     "Long Island Rail Road commuter platform at cold early morning, commuters in winter coats waiting with coffee, a very tall heavyset man in a dark overcoat stands with his back to camera a head above the crowd, a silver commuter train pulling in on the left. Camera: locked-off wide shot from the far end of the platform; only the train and the crowd move slightly.",
     "列车进站声；字幕高亮「一米九三」"),
    ("S10", "agnes", "缓慢横摇 slow pan",
     "建筑合规咨询：制图桌上的蓝图、法规活页夹，一只手指着平面图，窗外天际线",
     "手抬起离开图纸，切夜晚厨房窗",
     "Interior of a small Manhattan architecture consulting office: a drafting table covered with rolled blueprints and floor plans, thick building-code binders, a scale ruler, a large man's hand pointing at a floor plan, the Midtown skyline through the window behind; no faces. Camera: one slow pan across the desk from the binders to the window.",
     "纸张翻动、铅笔声"),
    ("S11", "agnes", "焦点转移 rack focus",
     "晚上回家陪妻儿：从门廊外看温暖的厨房窗，餐桌旁一家人的模糊剪影",
     "焦点回到门廊栏杆，切地下室楼梯",
     "Night exterior of the suburban house seen from the front porch: a warm tungsten-lit kitchen window with the soft blurred silhouettes of a family seated at a dinner table, curtains half drawn, porch railing in the foreground; no recognizable faces. Camera: static frame with one slow rack focus from the porch railing to the glowing window.",
     "餐具轻碰、模糊的笑声（远）；音乐转暗"),
    ("S12", "agnes", "下摇 tilt down",
     "伏笔一：木楼梯通向昏暗地下室，一盏灯泡，木板墙，纸箱",
     "灯泡轻微闪动接硬盘特写",
     "Narrow wooden basement stairs descending into a dim cluttered suburban basement lit by a single bare bulb, wood-paneled walls, metal shelving with cardboard boxes, a workbench in shadow; no people. Camera: one slow tilt down from the top step to the concrete floor.",
     "灯泡电流嗡鸣 + 木楼梯吱呀"),
    ("S13", "agnes", "微距推近 macro push-in",
     "伏笔二：架子底层落灰的旧米色电脑主机和外置硬盘，硬盘指示灯微微一闪",
     "指示灯闪动时切第三章",
     "Macro shot on the bottom shelf of a windowless suburban basement: an old beige desktop computer tower and a dusty external hard drive on a metal shelf against a bare concrete-block wall, lit only by one bare bulb overhead, cobwebs, deep shadows, a single tiny indicator light blinking faintly; no window, no daylight, no people, no readable labels. Camera: one very slow macro push-in toward the hard drive. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "硬盘启动咔哒一声；「后面再说」处音乐悬停"),
    # ---------------- N03 作案手法（8 镜）----------------
    ("S14", "agnes", "俯拍缓推 overhead slow push",
     "「网上招揽客人的年轻女性」：黑暗房间里笔记本屏幕的冷光，一只大手滚动着模糊的分类广告页",
     "屏幕光切夜里驶离的小货车",
     "Dark home office at night lit only by a laptop screen, a large man's hand on the trackpad scrolling a page of blurred classified-listing blocks that are deliberately unreadable, a mug and scattered papers, cold blue glow on the desk; no faces, no readable text. Camera: one slow overhead push-in toward the glowing screen.",
     "触控板滑动声、风扇低鸣"),
    ("S15", "agnes", "固定大全景 static wide",
     "等老婆孩子出门：夜里小货车装着行李驶离车道，楼上亮着灯，地下室窗黑着",
     "车尾灯出画，切一次性手机",
     "Night wide shot from across the street of the suburban house: a minivan with luggage in the back reverses out of the driveway and drives away down the street, the upstairs windows warmly lit, the small ground-level basement window dark; no faces visible. Flat Long Island suburb: the horizon holds only trees, utility poles and low rooftops - no skyscrapers, no city skyline anywhere in the background. Camera: locked-off wide from across the street for the whole clip; only the van moves. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "引擎远去"),
    ("S16", "agnes", "俯拍固定 overhead static",
     "一次性手机：夜里车座上的廉价翻盖机，仪表盘微光，一只大手拿起",
     "翻盖机合上切只亮地下室窗的房子",
     "Overhead close-up of a cheap prepaid flip phone lying on the worn passenger seat of a pickup truck at night, faint dashboard glow, a large man's hand reaches in, picks the phone up, flips it open and holds it in the frame; no faces, the windshield and the street stay out of frame. Camera: locked-off overhead on the seat for the whole clip; only the hand moves. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "雨点打车顶、翻盖机开合声；字幕高亮「一次性手机」"),
    ("S17", "agnes", "缓慢推近 slow push-in",
     "「地下室里发生了什么，只有他知道」：深夜的房子，只有地面那扇小小的地下室窗亮着",
     "推到窗前，硬切夜里的皮卡",
     "Exterior, late night: a single modest two-story wood-shingle suburban house on a dark residential street, seen from the sidewalk across the street; every window dark except one small ground-level basement window glowing dim yellow behind a curtain, porch light off, one street lamp with moths, thin mist; flat suburb with only trees and neighboring low houses around - no skyline, no water, no people, no interiors. Camera: one slow push-in from the sidewalk toward the glowing basement window. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "蟋蟀声与远处高速公路；音乐只剩持续低音"),
    ("S18", "agnes", "低角度横移 low lateral dolly",
     "「之后……」：深夜海洋公园大道路肩，一辆深色皮卡熄了大灯停着，只有尾灯，沙丘剪影",
     "尾灯熄灭切麻布特写",
     "A dark pickup truck parked on the shoulder of the empty coastal parkway at night with headlights off, only red tail lights glowing, dune silhouettes and a pale strip of sea beyond, wind moving the grass; no people, no readable plate. Camera: one low slow lateral dolly along the truck's flank.",
     "怠速引擎低鸣、海风"),
    ("S19", "agnes", "微距缓拉 macro pull-back",
     "粗麻布与荒草：沙丘草丛里的粗糙迷彩麻布纹理，风吹草动，不出现任何人形",
     "拉远至空沙丘，切时间线卡",
     "Macro close-up on a winter dune: a torn, weathered scrap of coarse camouflage burlap lying flat and empty on the sand, half buried and caught in dry dune grass, fluttering slightly in the wind, the grey ocean a soft blur far behind; only fabric, sand and grass - nothing wrapped inside it, nothing beneath it, no bundle, no people. Camera: one slow macro pull-back revealing more of the empty dune. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "风声压过音乐"),
    ("S20", "graphic", "时间线卡 static card",
     "时间线卡：1993—2010，17 年，至少 8 名受害者",
     "卡片硬切夜里响起的家用电话",
     "十七年\n1993 —————— 2010（八个红点 = 八名受害者的遇害年份）\n至少8名受害者 · 最早1993年 · 最晚2010年",
     "时间轴从左到右生长；每个红点一声轻响"),
    ("S21", "agnes", "缓慢推近 slow push-in",
     "「用受害者的手机挑衅她的家人」：深夜的家庭厨房，台面上的无绳电话亮着响，一只女人的手悬在半空不敢接",
     "铃声戛然而止切第四章航拍",
     "A modest family kitchen late at night lit by the stove hood light, a cordless landline phone on the counter lit up and ringing, a woman's hand hovering hesitantly above it, a child's drawing on the fridge behind, everything else dark; no faces. Camera: one slow push-in toward the ringing phone.",
     "电话铃声（sfx phone）；解说结束时铃声突然断"),
    # ---------------- N04 一辆皮卡（7 镜）----------------
    ("S22", "agnes", "航拍环绕 aerial orbit",
     "2010 年底的发现：警车与搜索人员沿海洋公园大道灌木带的远景，不拍任何遗体",
     "环绕结束切落灰的证物箱",
     "High aerial view in grey December light of a police search along Ocean Parkway: several police SUVs with light bars parked on the shoulder, small figures of officers and a dog handler walking the line of dune brush far below, cold marsh and surf; nothing on the ground but brush and sand. Camera: one slow aerial orbit around the search area.",
     "警笛远、直升机桨叶；字幕高亮「全美震动」"),
    ("S23", "agnes", "缓慢横移 slow dolly",
     "「十几年过去，一无所获」：证物室成排纸箱落满灰，一束光里的浮尘，墙上挂历停在旧年份（不可读）",
     "浮尘中切专案组翻卷宗",
     "A cold-case evidence room: rows of cardboard evidence boxes on steel shelving thick with dust, a single shaft of window light full of drifting dust motes, a faded blank wall calendar and a dead fluorescent tube, silence; no people, no readable labels. Camera: one slow dolly along the shelves through the dust.",
     "空调低鸣、日光灯电流声；音乐停滞"),
    ("S24", "agnes", "推轨横移 dolly along shelves",
     "专案组翻卷宗：档案室里调查员双手打开落灰的卷宗，软木板上钉着地图",
     "翻页声接皮卡目击",
     "The same file room now busy at night: investigators' hands lifting lids off evidence boxes and spreading thick folders, maps and blurred photos pinned to a corkboard, fresh coffee cups, fluorescent light; no faces. Camera: one slow dolly along the table ending on an open folder.",
     "翻页、纸箱拖动；「翻了个底朝天」"),
    ("S25", "agnes", "百叶窗后的固定长焦 static long lens through blinds",
     "目击证词：白天从屋内百叶窗缝里看对街，一辆墨绿色第一代雪佛兰雪崩皮卡停在路边",
     "百叶窗合上切鼠标上的手",
     "Daytime view from inside a house through half-open window blinds across a quiet suburban street: a dark green early-2000s Chevrolet Avalanche pickup truck parked at the curb, its distinctive angular sail panels between cab and bed, a tall dark figure seen only from behind walking away from it; no faces, no readable plate. Camera: locked-off long lens through the blinds; only the figure moves.",
     "百叶窗轻响；字幕高亮「雪佛兰雪崩皮卡」"),
    ("S26", "agnes", "微距固定 macro static",
     "数据库一查：显示器光映在调查员眼镜片上（不露全脸），鼠标上的手突然停住",
     "停住的手接转机卡",
     "Extreme close-up of an investigator's hand on a computer mouse at night, the glow of a database screen reflected in the lenses of glasses at the very top of frame, the screen itself out of frame; the hand scrolls and then freezes. Camera: locked-off macro; only the hand moves.",
     "鼠标滚轮声突然停止 → 全场静音 0.4 秒；字幕高亮「正是赫曼」"),
    ("S27", "graphic", "信息卡 static card",
     "转机卡：2022 年 3 月 14 日，墨绿色雪佛兰雪崩皮卡，车主雷克斯·赫曼",
     "卡片硬切长焦监控",
     "转机\n2022年3月14日 · 目击证词：墨绿色雪佛兰「雪崩」皮卡\n车辆数据库查到车主：雷克斯·赫曼",
     "卡片出现时低音「咚」"),
    ("S28", "agnes", "长焦手持 handheld long lens",
     "跟踪一年半：从面包车里长焦偷拍，高个背影把垃圾袋拎到路边，电线杆上的摄像头",
     "垃圾桶盖合上接曼哈顿人行道",
     "View through a long telephoto lens from inside a parked surveillance van: compressed suburban street, a very tall heavyset man seen from behind carries two black trash bags to the curb and sets them beside the cans, a small camera mounted on a utility pole at the edge of frame; no faces. Camera: handheld long lens with subtle breathing and one slight refocus.",
     "相机快门连拍声；「等他扔垃圾」是本章最后一句，留 0.6 秒气口"),
    # ---------------- N05 披萨盒与作案清单（9 镜）----------------
    ("S29", "agnes", "背后跟拍 follow from behind",
     "2023 年 1 月 26 日：曼哈顿正午，披萨店门口，高个大衣背影拎着披萨盒走在人行道上",
     "背影走近垃圾桶，切对街中景",
     "Midtown Manhattan sidewalk at winter midday: a small corner pizzeria with a steamed-up window and a striped awning on the left, a very tall heavyset man in a dark overcoat seen from behind walking away from camera along the busy sidewalk carrying a flat cardboard pizza box, yellow taxis, steam from a manhole, tall buildings; nobody faces the camera, no readable signs, no windows looking onto beaches. Camera: one steady follow move behind him at walking pace. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "街道环境声；日期字幕大号弹出"),
    ("S30", "agnes", "对街固定中景 static medium from across street",
     "「随手把盒子扔进垃圾桶」：对街视角，背影把盒子丢进绿色铁丝垃圾桶，头也不回汇入人流",
     "镜头停在垃圾桶，戴手套的手入画",
     "High angle from a second-floor window across a Manhattan avenue at midday: on the far sidewalk a very tall heavyset man in a dark overcoat, seen from behind and above, drops a folded pizza box into a green wire-mesh sidewalk trash can without breaking stride and walks on through sparse foot traffic, a bus and yellow taxis passing below; nobody faces the camera. Camera: locked-off high angle; hold on the trash can after he leaves. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "公交驶过的低频，盒子落桶一声"),
    ("S31", "agnes", "低角度固定 low-angle static",
     "跟踪小组马上捡走：戴手套的手把披萨盒从垃圾桶取出放进证物袋，城市背景虚化",
     "证物袋封口接实验室",
     "Low-angle close-up beside a green wire-mesh New York sidewalk trash can, already framed from the very first frame: a plainclothes officer's blue-gloved hands reach into the can, lift out the folded pizza box and slide it into a large clear evidence bag, grey jacket sleeves, blurred taxis and buildings behind, nobody facing the camera. Camera: locked-off low angle on the can for the entire clip; only the hands move; no establishing shot. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "塑料证物袋声；节奏加快，每句一个画面"),
    ("S32", "agnes", "微距焦点转移 macro focus pull",
     "线粒体 DNA 比对：实验室移液器、样本管、显微镜下的一根毛发、发光的比对读数（不可读）",
     "读数光接结果卡",
     "Interior of a forensic DNA laboratory, framed on the lab bench from the first frame to the last: a gloved technician's hands pipetting into small sample tubes in the foreground, a single strand of hair under a microscope on the left, a monitor glowing with abstract unreadable sequencing bars on the right, cool white light, no windows, no view outside, no faces. Camera: one slow macro focus pull from the pipette tip to the monitor glow. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "离心机嗡鸣、电子提示音"),
    ("S33", "graphic", "结果卡 static card",
     "DNA 结果卡：披萨边 DNA 与麻布毛发线粒体一致，排除 99.96% 北美人口",
     "卡片硬切办公室门口被捕",
     "99.96%\n披萨边DNA ⇄ 当年麻布上的一根男性毛发\n可排除99.96%的北美人口 · 他排除不了",
     "数字 99.96% 单独放大跳出；「他不能」处全部静音半秒"),
    ("S34", "agnes", "手持跟随 handheld follow",
     "7 月 13 日被捕：傍晚曼哈顿写字楼门口，高个西装背影，几名便衣从两侧走近，路边无标识轿车闪着暗红蓝光",
     "便衣走到身边时切地下室搜查",
     "Evening outside a Midtown Manhattan office tower: a very tall heavyset man in a dark suit seen from behind on the sidewalk, three plainclothes agents in windbreakers approaching him calmly from both sides, two unmarked sedans at the curb with dim red and blue dashboard lights reflecting on wet pavement; no faces, no violence. Camera: handheld follow from behind that slows to a stop as the agents reach him.",
     "对讲机短促电流声；音乐骤停"),
    ("S35", "agnes", "上摇 tilt up",
     "搜家十二天、拉走硬盘：白色防护服的技术员抬证物箱上楼梯，硬盘装在证物袋里",
     "证物袋接取证工作站",
     "The suburban basement now a search scene: evidence technicians in white protective suits carry sealed boxes up the wooden stairs, an old external hard drive sealed in a clear evidence bag on the metal shelf in the foreground, numbered evidence markers, harsh work lights; no faces, no readable text. Camera: one slow tilt up from the bagged hard drive to the technicians on the stairs.",
     "对讲机、纸箱搬动"),
    ("S36", "agnes", "缓慢推近 slow push-in",
     "「翻出一份两千年建的 Word 文档」：数字取证实验室，旧硬盘接着线，显示器上弹出一份分栏文档（不可读）",
     "屏幕光接作案清单卡",
     "Digital forensics workstation in a dim lab: the old hard drive out of its bag connected by cables to a write-blocker, twin monitors glowing, one window opening a blurred multi-column document that is deliberately unreadable, an analyst's gloved hands on the keyboard; no faces. Camera: one slow push-in toward the document window.",
     "键盘声、硬盘读盘声；字幕高亮「Word文档」"),
    ("S37", "graphic", "清单卡 static card",
     "作案清单卡：Word 文档建于 2000 年；问题栏、目标栏的中文转述",
     "卡片硬切备忘卡",
     "作案清单\nWord文档 · 建于2000年 · 藏在地下室的硬盘里\n问题栏：毛发 · DNA · 指纹　　目标栏：小个子好",
     "逐行打字机出现，最后一行停顿最长"),
    # ---------------- N06 结局与金句（8 镜）----------------
    ("S38", "graphic", "备忘卡 static card",
     "备忘卡：清单里的「行动前要睡够」，与下一镜「第二天照常上班」形成对照",
     "卡片硬切写字楼大堂",
     "作案清单 · 备忘\n行动前要睡够，太累会出问题\n写下这句话的人，第二天照常去上班",
     "只有低音持续；这一句是全片最冷的一句"),
    ("S39", "agnes", "固定 static",
     "「第二天照常去上班」：清晨曼哈顿写字楼大堂的旋转门，高个大衣背影推门进去，晨光斜切大理石",
     "旋转门转过一圈切法庭",
     "Early morning lobby of a Midtown Manhattan office tower seen from inside: a brass revolving door turning, a very tall heavyset man in a dark overcoat with a briefcase seen from behind pushing through it, long shafts of morning sun across a polished marble floor, a security desk in shadow; no faces. Camera: locked-off wide; only the door and the figure move.",
     "旋转门的风声与皮鞋回音"),
    ("S40", "agnes", "缓慢横移 slow lateral slide",
     "2026 年 4 月 8 日认罪：法庭后排视角，被告席上高大的深色西装背影，两侧律师，木质法官席",
     "法槌声接铁门",
     "Wide shot from the back of a wood-paneled county courtroom with no windows: rows of seated spectators' backs in the foreground, a very tall heavyset man in a dark suit seen from behind standing at the defense table between two attorneys, the judge's raised wooden bench, an empty witness stand and two flags ahead, warm ceiling lights; no recognizable faces, nobody turns toward the camera, no buildings or houses inside the room. Camera: one very slow lateral slide behind the last row. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "法槌一声；日期字幕「2026.04.08」"),
    ("S41", "agnes", "固定 static",
     "终身监禁不得假释：监狱走廊尽头一扇厚重铁门缓缓关上，冷白灯光",
     "铁门合拢的余响接披萨边证物",
     "A long empty prison corridor with solid painted cinder-block walls on both sides and no windows, cold fluorescent tubes overhead, a polished concrete floor; at the far end a heavy grey steel door slowly swings shut over the course of the clip; no people, no view outside. Camera: locked-off wide down the corridor; only the door moves. The entire clip stays in this single framing: no cut, no scene change, no camera relocation.",
     "铁门关闭的重低音余响 2 秒"),
    ("S42", "agnes", "微距推近 macro push-in",
     "「输给了一块没吃完的披萨边」：不锈钢台面上透明证物袋里的一截披萨边，旁边一张空白证物标签",
     "推到极近切街头垃圾桶",
     "Macro shot on a brushed stainless-steel evidence table under a cool lab lamp: a single half-eaten pizza crust sealed inside a clear evidence bag, a blank evidence tag beside it, a ruler out of focus, dramatic soft shadow; no people, no readable text. Camera: one very slow macro push-in toward the crust.",
     "钢琴单音；字幕高亮「没吃完的披萨边」"),
    ("S43", "agnes", "极缓拉镜头 slow pull-back",
     "「别再迷信完美犯罪」：傍晚空荡的曼哈顿人行道，那只绿色垃圾桶，露出的披萨盒盖，缓慢拉远",
     "拉远接证物墙",
     "Blue-hour Manhattan side street nearly empty, a green wire-mesh sidewalk trash can with the corner of a cardboard pizza box lid poking out, wet pavement reflecting shop light, a single taxi passing far behind; no people near camera. Camera: one extremely slow pull-back away from the trash can.",
     "音乐收干，只剩城市底噪"),
    ("S44", "agnes", "缓慢横摇 slow pan",
     "「你扔掉的每一样东西，都在替你说话」：证物室的软木板上钉着一排透明证物袋——瓶子、餐巾、收据、钥匙——台灯下",
     "横摇到最后一个袋子切黎明海滩",
     "A corkboard in an evidence room under a single desk lamp: a neat row of clear evidence bags pinned up containing everyday discarded objects - an empty bottle, a crumpled napkin, a receipt with no readable print, a key, a coffee cup lid - dark room around; no people, no readable text. Camera: one slow pan along the row of bags.",
     "台灯电流声；金句字幕逐字出现"),
    ("S45", "agnes", "升镜头 crane up",
     "结尾致意 + 引导评论：黎明的吉尔戈海滩，海洋公园大道护栏上系着的花束，镜头升起露出笔直的公路",
     "升到全景后画面渐隐，接片尾卡",
     "Dawn at Gilgo Beach: bunches of flowers tied to the metal guardrail along Ocean Parkway, dune grass moving in the wind, pale pink light on the Atlantic; no people. Camera: one slow crane up from the flowers to reveal the long straight empty road disappearing into the distance.",
     "海浪 + 钢琴单音；结尾停 1 秒引导评论，最后 0.8 秒音画渐隐"),
]

GRID = 4          # 规划网格：每镜 4 秒，45 镜 = 180 秒
AGNES_SECONDS = 7  # 每个 Agnes 镜头实际请求的时长（169 帧 @ 24 fps）


def build():
    story = json.loads(PLAN.read_text())
    assert len(SHOTS) * GRID == 180 and len(story["chapters"]) == len(CHAPTERS) == 6
    assert len({sid for sid, *_ in SHOTS}) == len(SHOTS), "镜头号重复"
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
        start = i * GRID
        shots.append({
            "id": sid, "kind": kind, "start": start, "duration": GRID,
            "narration_id": f"N{min(6, start // 30 + 1):02d}",
            "prompt": body if kind == "agnes" else "",
            "purpose": purpose, "transition_out": transition,
            "graphic": body if kind == "graphic" else "",
            "seed": 20230126 + i + 1,   # 披萨盒被取走的那一天
            "seconds": AGNES_SECONDS, "aspect": "16:9", "resolution": "1080p", "frame_rate": 24,
            "camera": camera, "sfx_note": sfx,
        })
    story["shots"] = shots
    story["_scaffold"]["note"] = ("内容由 build_story.py 一次性写入；45 镜 × 4 秒规划网格（38 Agnes + 7 信息卡，"
                                  "每镜只用一次）；解说词与 screenplay.md、audio/manifest.json 三处逐字一致由 "
                                  "generate.py --validate 守着。")
    PLAN.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n")

    manifest = json.loads(MANIFEST.read_text())
    for clip, chapter in zip(manifest["clips"], story["chapters"]):
        assert clip["id"] == chapter["id"]
        clip["text"] = chapter["text"]
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    kinds = [s["kind"] for s in story["shots"]]
    print(f"story.json 已写入：{len(shots)} 镜 = {kinds.count('agnes')} agnes + {kinds.count('graphic')} graphic，"
          f"解说 {sum(len(c['text']) for c in story['chapters'])} 字（含标点）")


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
