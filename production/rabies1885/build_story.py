#!/usr/bin/env python3
"""《狂犬病疫苗：一百四十年前那场赌局》的全部内容源。

这是这部片子**唯一需要动脑写的文件**：解说词、45 镜分镜、信息卡文案、字幕高亮词、
发布文案、事实来源，全都在这里；跑一次写进 story.json 与 audio/manifest.json。

用法::

    python3 production/rabies1885/build_story.py            # 写 story.json + audio/manifest.json 文本
    python3 production/rabies1885/build_story.py --script   # 生成 抖音脚本.md
    python3 production/rabies1885/build_story.py --publish  # 生成 抖音发布文案.md

内容从哪儿来：

* 解说词 863 字（含标点）/ 六章，由用户上传的文案改编——改编处全部记在
  `production/docs_lab/workspaces/rabies1885/` 的事实底稿里（"与上传文案的对照"一节）；
* 45 镜 = 38 个 Agnes 镜头 + 7 张信息卡，画面风格 = 用户上传的参考片量出来的调子
  （暖褐 / 橄榄 / 羊皮纸、暗调强反差、明显胶片颗粒），渲染成超写实 3D；
* 每条事实的出处在下面的 SOURCES，2026-10-04 联网核对（WHO / 美国 CDC / 巴斯德研究所 /
  《柳叶刀》/ 国家疾控局《狂犬病暴露预防处置工作规范（2023年版）》）。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "story.json"
MANIFEST = HERE / "audio" / "manifest.json"

TITLE = "狂犬病疫苗：一百四十年前那场赌局"

# ---------------------------------------------------------------------------
# 画面风格：借用用户参考片的电影质感，渲染为超写实 3D；不复制其中的场景内容。
# 这里只保留精简的风格信号（自然暖中性、胶片颗粒、真实材质与景深），避免全局
# 前缀吞没镜头语义。具体地点、人物、道具、光源和运镜均由每镜 shot prompt 决定。
# 注意：style_prefix 参与全部 Agnes 镜头的 request_hash，改动会触发 38 镜重做。
# ---------------------------------------------------------------------------
STYLE_PREFIX = (
    "Photorealistic 3D CGI with live-action film texture: physically plausible materials and "
    "scale, natural global illumination, realistic lenses, subtle 35mm grain, and gentle depth "
    "of field. Cinematic warm-neutral palette, natural highlights, detailed shadows and "
    "midtones, balanced exposure, no orange cast. Horizontal 16:9. This prefix sets visual "
    "style only; depict exactly the subject, setting, props, and action in the shot prompt, "
    "in one continuous take. People only from behind or as silhouettes or hands, with no "
    "visible facial features; no readable text, real-person likeness, gore, or nudity. "
)

# 与 production/gilgo 的关键差别：那部是 2D 动画，负面词里有 "3D render look, plastic CGI"，
# 照抄过来会把这次要的超写实 3D 自己否掉——换成挡住 2D 手绘的词。
NEGATIVE_PROMPT = (
    "readable text, letters, numbers, words, signage writing, invented headlines, logos, brand marks, "
    "watermark, subtitles, on-screen caption, photorealistic face, recognizable real person likeness, "
    "frontal face close-up, eyes visible in detail, face turned toward camera, profile of a face, "
    "visible facial features, visible eyes, nose, mouth, teeth, smiling face, looking at camera, "
    "blood, gore, wound, corpse, body bag, body parts, autopsy, violence, assault, strangling, "
    "weapon attack, gun, firearm, nudity, erotic content, horror monster, ghost, jump scare, "
    "distorted anatomy, deformed hands, extra fingers, extra limbs, duplicated people, changing face, "
    "morphing objects, teleportation, jitter, flicker, lens flare, green flare, circular light artifacts, "
    "chromatic ghosting, whip pan, fast zoom, jump cut, split screen, "
    "collage, montage, multiple scenes, multiple locations in one shot, scene transition, time jump, "
    "unrelated scenery, unrelated props, sudden background change, flat 2D illustration, hand-drawn "
    "cel shading, comic-book ink lines, graphic-novel texture, watercolour paper texture, "
    "underexposed, crushed black shadows, almost entirely black frame, black screen, silhouette-only "
    "objects, flat low contrast, overexposed, washed out, static locked-off shot"
)

# 事实边界与红线：每一条都会印在 抖音脚本.md 的「发布前自查」里。
PRINCIPLES = [
    "全部 Agnes 镜头为超写实 3D 动画情景重现，画面常驻标注「AI动画情景重现 · 非新闻影像」，不冒充历史照片、新闻影像或档案影像",
    "不展示遗体、血腥与伤口；被咬这件事只用狗的剪影、绷带与事后场景交代，不重现撕咬过程",
    "真实人物（巴斯德、约瑟夫、母亲、医生）只以背影、剪影、手部出现，不用 AI 生成的脸冒充本人",
    "患病的人不出现清晰面容，只用剪影、床、椅子、灯与门窗光暗示，不渲染痛苦表情",
    "每一句事实都能指到 SOURCES 里的一条公开来源；针数（十三针/十四剂）两份权威来源有出入，成片只说「十天、十几针」",
    "不写无法核实的心理活动与场景（如「整个巴黎都在盯着」）；巴斯德的犹豫用他自己有出处的原话",
    "所有中文姓名、日期、字幕后期添加，不交给视频模型拼写",
    "同一地点保留光线、道具、运动方向；跨时空通过物件（注射器、玻璃罐、脊髓制剂）匹配衔接",
    "人工检视 qa/ 接触表，露脸、畸变、伪文字、中途换场的镜头用 {\"only\":\"Sxx\"} 重生成，不直接进成片",
]

SOURCES = [
    {"id": 1, "url": "https://www.cdc.gov/mmwr/preview/mmwrhtml/00000572.htm",
     "usage": "CDC MMWR：1885-07-06 巴斯德团队开始为 9 岁 Joseph Meister 施行暴露后治疗；男孩两天前被咬；这项研究建立在多年动物实验之上。"},
    {"id": 2, "url": "https://www.pasteur.fr/en/about-us/our-dna/history",
     "usage": "巴斯德研究所：迈斯特来自阿尔萨斯、被咬十四处、十天内十三针毒力递增；1887 募款、1888-11-14 研究所正式开放。"},
    {"id": 3, "url": "https://www.pasteur.fr/en/about-us/final-years-1877-1887",
     "usage": "巴斯德研究所：兔之间连续传代得到潜伏期稳定的固定病毒；将感染兔脊髓在干燥空气中悬挂后，毒力逐渐降低；巴斯德请格朗谢为迈斯特接种。"},
    {"id": 4, "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3444995/",
     "usage": "同行评审综述：先用充分干燥、毒力很低的感染兔脊髓材料，后续材料干燥时间缩短、毒力递增；早期神经组织疫苗的局限。"},
    {"id": 5, "url": "https://www.who.int/news-room/fact-sheets/detail/rabies",
     "usage": "WHO：出现临床症状后狂犬病几乎总是致命；全球每年数万人死亡，约四成是十五岁以下儿童。"},
    {"id": 6, "url": "https://journals.sagepub.com/doi/pdf/10.1177/014107688908200813",
     "usage": "历史综述：1886-11 约 2500 人接受治疗；到 1895 年巴斯德去世时近 2 万人。"},
    {"id": 7, "url": "https://www.cdc.gov/rabies/hcp/clinical-overview/index.html",
     "usage": "CDC 临床概览：症状出现前，恰当暴露后预防可避免疾病；处置包含伤口清洗、免疫球蛋白和疫苗，由专业人员评估。"},
    {"id": 8, "url": "https://www.cdc.gov/rabies/about/index.html",
     "usage": "CDC 公众页：潜在暴露后应立即用肥皂和流动水清洗，并紧急寻求专业医疗帮助；潜伏期可持续数周至数月。"},
]

# 六段解说：(章节 id, 章节标题, 逐字解说词)。782 字，估时 175.7 秒（预算 176.1 秒）。
CHAPTERS = [
    ("N01", "黄金开头（症状出现后几乎无回头路 → 不是医生的巴斯德 → 九岁男孩）",
     "狂犬病可怕在：症状一旦出现，几乎没有回头路。恐水等神经症状之后，患者可能走向死亡。"
     "疫苗出现前，人们试过烧灼伤口，却没有可靠保护。改写这一切的，不是一位医生，而是一位化学家：路易·巴斯德。"
     "可他即将面对的，不是一道理论题，而是一个九岁男孩。"),
    ("N02", "巴斯德与减毒（先固定病毒，再以干燥减毒 → 动物实验给出希望）",
     "从一八八零年起，巴斯德团队在巴黎研究狂犬病。他们先让病原在兔之间连续传代，得到潜伏期稳定的固定病毒；"
     "再把感染兔的脊髓悬在干燥空气中，令毒力下降。随后，团队按由弱到强的次序给动物接种，狗的实验给了希望。"
     "但病原肉眼看不见，巴斯德又不是执业医生。把尚无人体证据的方法用于人，后果无法预料。"),
    ("N03", "一八八五年七月六日（迈斯特到巴黎 · 医生执行第一针 · 没有现代试验）",
     "一八八五年七月六日，阿尔萨斯的约瑟夫·迈斯特被母亲带到巴黎；他九岁，两天前被一只据报患狂犬病的狗咬了十四处。"
     "巴斯德写道，孩子的死亡看起来不可避免，自己是在极度焦虑中作出决定。他没有亲手注射：在医生支持下，"
     "儿科医生雅克—约瑟夫·格朗谢执行第一针。没有随机对照，也没有今天的伦理审查。"),
    ("N04", "十天，十几针（由弱到强 · 迈斯特没有发病 · 单例的边界）",
     "随后十天，迈斯特接受十几次由弱到强的制剂；不同史料记为十三针或十四剂。原理简单也冒险："
     "先给免疫系统时间，再让它迎向更强的病毒材料。迈斯特最终没有发病。但一个成功病例不能替代今天的临床试验；"
     "它提示，暴露之后仍可能追上疾病。"),
    ("N05", "从巴黎到研究所（两千五百人到近两万人 · 专门机构诞生）",
     "消息传开，被动物咬伤的人从多国赶到巴黎。到一八八六年十一月，约两千五百人接受过这种治疗；"
     "到巴斯德一八九五年去世时，人数接近两万。需求推动建立专门机构：一八八七年募款启动，"
     "一八八八年十一月十四日，巴斯德研究所在巴黎正式开放。一次紧急救治，变成持续的公共卫生事业。"),
    ("N06", "今天的暴露后预防（专业评估 · 清洗伤口 · 证据先于传奇）",
     "今天，狂犬病仍会夺走数万人的生命，儿童承受的负担尤其重。但现代暴露后预防已不同："
     "细胞培养疫苗、免疫球蛋白和规范评估，取代了干燥兔脊髓。遇到动物咬伤或抓伤，先用肥皂和流动水彻底清洗，"
     "再尽快联系当地医生或公共卫生机构，由专业人员判断下一步。巴斯德留下的，是一个原则：证据要先于传奇，救治要快于病毒。"),
]

# 每一镜：(id, kind, 运镜, 叙事职责, 衔接方式, 英文提示词 或 信息卡说明, 音效/备注)
# 45 镜按成片顺序编号 S01–S45，每镜只用一次；其中 7 张信息卡（S07 S13 S21 S28 S34 S38 S42）。
SHOTS = [
    # ---------------- N01 钩子与绝望（S01–S08，8 镜：7 动画 + 1 信息卡） ----------------
('S01', 'agnes', '低机位缓慢横移 lateral drift', '「狂犬病的威胁」：黄昏湿石板路上，一条狗的背影剪影，绝不出现其他场景', '狗停在路灯暗处，切钟摆', 'One single large dog standing alone on one wet cobblestone village street at dusk, seen from behind in a clean dark silhouette, low camera at pavement height; one warm window far in the background. The dog remains the only animal and the only moving subject. Camera: one slow lateral drift to the right. Keep the same street, dog, scale and composition for the entire clip. No laboratory, no bed, no horses, no people, no other locations, no montage, no scene change.', '低频心跳；远处犬吠一声'),
('S02', 'agnes', '缓慢横移 slow lateral drift', '「症状一旦出现，几乎没有回头路」：老式木钟下方的铜摆锤左右摆动，表盘完全不入镜', '摆锤掠过画面，硬切恐水', 'Close on only the lower glass compartment of one nineteenth-century wooden wall clock on a plain farmhouse wall: one circular brass pendulum bob swings slowly left and right inside the dark wooden case. The clock dial and clock face stay completely outside the frame and must never be visible. No numbers, letters, symbols, labels, writing, hands, people, animals, landscape, laboratory, bed, second location, montage or scene change. Camera: one slow lateral drift across the same pendulum compartment for the whole clip.', '钟摆与低频心跳'),
('S03', 'agnes', '缓慢横移 slow lateral drift', '「恐水等神经症状」：烛光下，一只手把水杯推开，水面轻颤', '手离开杯子，硬切空床', 'Close-up of one natural adult hand beside one clear glass of water on a wooden kitchen table at night, one candle visible beside it. The hand approaches, pushes the glass away across the tabletop, releases it, and withdraws; the glass slides away and the water ripples. The hand never lifts or grips the glass. Camera: one slow lateral drift at tabletop height. Only one hand, one glass, one table and one candle; no face, no extra fingers, no other scene, no cut or transition.', '水面轻响；烛火噼啪'),
    ('S04', 'agnes', '缓慢下摇 slow tilt down',
     '「在疫苗出现之前，狂犬病一旦发病」：昏暗房间里一张空床，晨光从窗缝进来，人已经不在',
     '光斑不动，硬切火盆',
     'Interior of a small dark bedroom at first light, an iron bed with a smooth undisturbed '
     'blanket, a wooden chair beside it, a narrow wedge of daylight falling across the empty '
     'pillow from a shuttered window. Camera: one slow tilt down from the window to the bed. '
     'No person in frame at any point. Hold this single view: no cut, no scene change, no '
     'camera relocation.',
     '呼吸声收住；弦乐压低'),
    ('S05', 'agnes', '缓慢下摇 slow tilt down',
     '「史料里的抢救办法：烧灼伤口」：火盆里烧红的铁钳',
     '火星上升，硬切阁楼',
     'Close on a pair of long iron tongs resting in glowing embers inside a stone hearth, '
     'sparks rising, the tong tips bright orange, a dark kitchen behind. Camera: one slow tilt '
     'down from the rising sparks to the embers. No hands, no skin, no wound, no blood. Hold '
     'this single view: no cut, no scene change, no camera relocation.',
     '炭火噼啪声；无音乐'),
    ('S06', 'agnes', '缓慢拉远 slow pull back',
     '「却没有可靠保护」：木桌上无标签药瓶与冷却的火钳，表达旧方法的局限（不出现人）',
     '光斑淡出，硬切信息卡',
     'Pale daylight from a small attic window fills a rough nineteenth-century room. On a plain wooden table sit three unlabelled dark medicine bottles beside cooled iron tongs, all clearly visible and entirely non-graphic; stone wall and wooden roof beams remain in view. Camera: one slow pull back from the table to reveal the empty room. No people anywhere in frame, no readable labels, no cut, no scene change, no camera relocation.',
     '低频嗡鸣，音乐收住'),
    ('S07', 'graphic', '静帧',
     '信息卡①：发病后病死率——明确「几乎百分之百」的事实边界',
     '硬切巴黎屋顶',
     '信息卡：病死率（画面文字见 CARDS）',
     ''),
    ('S08', 'agnes', '缓慢横移 slow lateral drift',
     '「一个连行医资格都没有的化学家」：学院高窗前一个穿深色外套的背影，手里拿着一份卷起的文件',
     '背影出画，硬切巴黎屋顶',
     'A lone figure seen strictly from behind in a long dark frock coat standing at a tall '
     'window at the end of a Paris school corridor, shoulders and back only, a rolled document '
     'held at his side, grey daylight through the glass, dust in the air. Camera: one slow '
     'lateral drift along the corridor past the figure. The figure never turns and no face is '
     'ever visible. Hold this single view: no cut, no scene change, no camera relocation.',
     '环境声：远处马车与脚步'),

    # ---------------- N02 巴斯德与减毒（S09–S15，7 镜：6 动画 + 1 信息卡） ----------------
('S09', 'agnes', '缓慢下摇 slow tilt down', '「他叫路易·巴斯德」：一八八零年代巴黎屋顶与烟囱，其中一扇阁楼窗亮着', '落到亮窗，硬切实验室', 'Exterior establishing view of only the 1880s Paris rooftops at dusk: slate roofs, chimneys, and one small attic window glowing amber. Camera: one slow tilt down from the evening skyline to that single lit window. The entire clip remains outside above the same rooftops. No room interior, bed, laboratory, bottles, people, horses, or other location; no montage, no scene change.', '城市远声；音乐进入'),
    ('S10', 'agnes', '缓慢推近 slow push in',
     '「他在巴黎的实验室里跟这种病较劲」：锌台面、黄铜显微镜、玻璃烧瓶、一盏油灯，无人',
     '灯焰轻晃，硬切兔笼',
     'Interior of a cramped nineteenth century Paris laboratory, a long zinc workbench crowded '
     'with a brass microscope, glass flasks and a lit oil lamp, warm light on the metal, no '
     'people in frame. Camera: one slow push in along the bench toward the microscope. No '
     'readable labels, no papers with writing, no charts. Hold this single view: no cut, no '
     'scene change, no camera relocation.',
     '环境声：液体轻响与火焰'),
    ('S11', 'agnes', '横向移动 lateral dolly',
     '「兔之间连续传代，得到固定病毒」：院子石墙下一排木框兔笼，一只白兔坐在干草上',
     '兔子耳朵一动，硬切玻璃罐',
     'A row of wooden rabbit hutches along a rough stone wall in a small courtyard, one white '
     'rabbit sitting on clean straw in the open doorway of its hutch, morning light across the '
     'yard. Camera: one slow lateral dolly along the row of hutches. The animals are calm and '
     'unharmed; no procedures, no instruments, no blood. Hold this single view: no cut, no '
     'scene change, no camera relocation.',
     '院子环境声：鸟与远处车马'),
    ('S12', 'agnes', '缓慢拉远 slow pull back',
     '「感染兔脊髓在干燥空气中毒力下降」：储藏室木架上一排玻璃罐，罐里是干燥处理的脊髓，一头暗一头亮',
     '罐子反光，硬切信息卡',
     'Close on a wooden shelf in a small storeroom holding a row of tall glass jars, each jar '
     'containing a pale dried cord coiled in clear fluid, the row fading from shadow at one '
     'end to warm lamp light at the other. Camera: one slow pull back from a single jar to '
     'reveal the whole row of jars. No readable labels or numbers on the jars. Hold this '
     'single view: no cut, no scene change, no camera relocation.',
     '低频环境声；弦乐渐起'),
    ('S13', 'graphic', '静帧',
     '信息卡②：路易·巴斯德 · 化学家，不是执业医生',
     '硬切学院石廊',
     '信息卡：路易·巴斯德（画面文字见 CARDS）',
     ''),
    ('S14', 'agnes', '缓慢跟拍 backward dolly',
     '「更麻烦的是，他不是医生」：巴黎机构的石阶与木门前，一个穿深色外套的背影拿着卷起的文件走上去',
     '脚步声桥，硬切铁栅阴影',
     'A figure seen only from behind in a long dark frock coat climbing a flight of worn stone '
     'steps toward a heavy wooden door of a Paris institution, a rolled document in one hand, '
     'daylight from one side, the door blank and unmarked. Camera: one slow backward dolly '
     'tracking in front of the figure as it climbs. No face at any point; no readable notices '
     'or plaques. Hold this single view: no cut, no scene change, no camera relocation.',
     '脚步声与远处人声；音乐收住'),
    ('S15', 'agnes', '缓慢横移 slow lateral drift',
     '「把尚无人体证据的方法用于人，后果无法预料」：石墙上铁栅的阴影缓缓移动，无人',
     '阴影移过墙面，硬切村庄清晨',
     'A stone corridor wall clearly lit by a wall lamp, the hard shadow of an iron bar gate '
     'sliding slowly across it, every stone and the mortar lines readable, dust in the beam. '
     'Camera: one slow lateral drift following the moving bars of shadow. No people, no prison '
     'uniform, no readable text. Hold this single view: no cut, no scene change, no camera '
     'relocation.',
     '低频嗡鸣；一声闷响（合成）'),

    # ---------------- N03 约瑟夫（S16–S23，8 镜：7 动画 + 1 信息卡） ----------------
    ('S16', 'agnes', '向前推进 forward dolly',
     '「一八八五年七月六日清晨」：夏日清晨的阿尔萨斯半木结构村庄街道，空无一人',
     '推进到街道尽头，硬切乡路',
     'An Alsatian half-timbered village street early on a summer morning, shutters closed, the '
     'cobblestones still damp, nobody about, pale light and long shadows across the timbered '
     'facades. Camera: one slow forward dolly down the empty street. No readable shop signs or '
     'house numbers. Hold this single view: no cut, no scene change, no camera relocation.',
     '清晨鸟声与远处牛铃'),
('S17', 'agnes', '缓慢跟拍 slow tracking', '「一个九岁的男孩被母亲从阿尔萨斯带到他面前」：乡路上，母亲牵着一个男孩的手，严格只见两人背影', '两人走向远处村庄，切门槛', 'One 1885 Alsatian mother in one long dark skirt holds the hand of exactly one nine-year-old boy in short trousers as they walk away on one quiet rural lane at dawn. The mother wears a plain low dark wool bonnet with a smooth, rounded human head silhouette and a narrow ribbon at the back: no points, bows, horns, ear-like projections or animal costume. They are the only two people in the entire frame, with empty lane, hedgerows and open fields around them; there are no other children, siblings, adults, crowds or distant figures anywhere. Keep both figures separated and clearly readable from behind, the boy small beside his mother. Camera: one slow rear tracking move following these same two figures only. No face, no laboratory, no indoor corridor, no horses, no montage or scene transition.', '乡间清晨环境声；两人的脚步'),
('S18', 'agnes', '缓慢下摇 slow tilt down', '「两天前被一只据报患狂犬病的狗咬了十四处」：孩子背影、肩上停着一只成人的手、腿上干净绷带', '从肩缓缓落到绷带，切笔尖', 'One small nine-year-old Alsatian boy sits on the rough wooden step of a half-timber farmhouse in 1885, seen strictly from behind with no face. He wears a plain loose linen shirt and dark wool knee breeches in an 1880s rural style. At the beginning, one adult woman’s hand with five natural fingers rests gently on his shoulder while the woman remains completely outside frame. In one continuous slow tilt down, the camera must reach the boy’s lower leg by the third second and hold there: one clean white cloth bandage wrapped around his exposed lower calf, below the knee, is fully visible and plainly readable for the rest of the shot. The boy remains the only person; no adult body, extra hand, wound or blood. Soft overcast morning daylight with no visible sun source. No cut, scene change or camera relocation.', '衣料轻响；音乐压低'),
('S19', 'agnes', '缓慢横移 slow lateral slide', '「巴斯德后来写下：孩子的结局看起来无法避免」：油灯下握羽毛笔的手与纸', '墨迹落在纸上，硬切动物房', 'Top-down macro close-up of one older adult right hand holding a quill above a blank sheet on a wooden desk at night; one inkpot and one oil lamp sit at the edge of frame. Crop from the wrist down so only the hand, quill and desktop are visible: no head, face, neck or torso. The hand has five natural distinct fingers and writes only a few abstract ink strokes, no readable words. Camera: one slow lateral slide across the paper. No cut or scene change.', '羽毛笔划纸声；音乐停半拍'),
    ('S20', 'agnes', '缓慢下摇 slow tilt down',
     '「还是决定用在狗身上从未失败过的办法试一次」：动物房地板上一只安静趴着的狗，活着、无伤',
     '狗抬起头，硬切信息卡',
     'A calm brown dog lying on the wooden floor of a small animal room, awake and unharmed, a '
     'low window casting daylight across the boards, a water bowl beside it. Camera: one slow '
     'tilt down from the window to the dog. The dog is healthy and still; no procedure, no '
     'instruments, no blood. Hold this single view: no cut, no scene change, no camera '
     'relocation.',
     '狗的呼吸声；一声轻吠（远）'),
    ('S21', 'graphic', '静帧',
     '信息卡③：一八八五年七月六日',
     '硬切深夜窗前的背影',
     '信息卡：一八八五年七月六日（画面文字见 CARDS）',
     ''),
('S22', 'agnes', '缓慢横移 slow lateral drift', '「在医生支持下」：巴斯德与一位医生在油灯旁并肩商议，均只见背影', '两人停在桌前，切针盒', 'In one quiet 1885 consultation room at night, two adult figures in period dark coats stand side by side at a plain wooden table lit by one oil lamp. One is a physician in a modest dark frock coat; both are strictly seen from behind and lean slightly toward a blank paper on the table, as if consulting. Their faces, fingers, readable notes and medical procedure remain out of frame. The room, window and floor stay visible with readable midtones. Camera: one slow lateral drift across the two back silhouettes and the lamp. No laboratory benches, bottles, beds, injection, scene change or camera relocation.', '低频弦乐；室内夜声'),
('S23', 'agnes', '缓慢上摇 slow tilt up',
     '「格朗谢执行第一针」：一位医生的手从木盒里取出玻璃注射器，不展示注射',
     '针管出盒，硬切桌上划痕',
     'Extreme close-up of one physician’s adult hand from the wrist down lifting one long glass syringe with a thin metal needle out of one open dark wooden case on a desk. Keep the hand, case and complete syringe clearly in frame throughout; no tremor, no injection and no skin in frame. Five natural distinct fingers, no deformation. No head, face, full person, laboratory-wide view, other props, text or second scene. Camera: one gentle upward tilt following the syringe as it rises; one continuous take.',
     '木盒轻响；玻璃器具轻碰'),

    # ---------------- N04 十天（S24–S30，7 镜：6 动画 + 1 信息卡） ----------------
    ('S24', 'agnes', '极缓横移 very slow lateral drift',
     '「随后十天」：木桌上一张卡片，手指一道道划过划痕',
     '手指划过最后一道，硬切药瓶架',
     'Close on a plain card on a wooden table in a plainly lit treatment room, a forefinger '
     'tracing a row of short abstract pencil scratches one by one, an oil lamp plus daylight '
     'from a window, soft shadow with visible detail. Camera: one very slow lateral drift '
     'alongside the moving finger. The marks are abstract scratches only - no legible numbers, '
     'digits or letters. Hold this single view: no cut, no scene change, no camera relocation.',
     '纸面摩擦声；低频脉动'),
    ('S25', 'agnes', '缓慢上摇 slow tilt up',
     '「十几次由弱到强的制剂」：储藏室木架上排开的小玻璃瓶，从暗到亮',
     '上摇到架子顶端，硬切推活塞的手',
     'Close on a row of small glass vials standing on a deep stone window ledge in a plainly '
     'lit room, bright daylight from the window behind them, the row running from shadow at '
     'one end to strong light at the other, a wet cobblestone courtyard visible through the '
     'window below. Camera: one slow tilt up from the row of vials to the window. No hands, no '
     'people, no readable text, no labels. Hold this single view: no cut, no scene change, no '
     'camera relocation.',
     '玻璃轻响；弦乐渐紧'),
('S26', 'agnes', '缓慢横移 slow lateral drift', '「史料计数为十三针或十四剂」：玻璃针管在前臂上方，拇指压下活塞，不见入针', '活塞压下但不入针，切夜间病房', 'Tight clinical close-up of one clean adult forearm resting on pale linen and one clearly visible old glass syringe with a metal needle held just above the skin. A natural adult hand slowly presses the syringe plunger; the needle remains visibly above the skin and never touches or enters it. Keep the complete barrel, plunger, needle, hand and forearm in frame. Only arm and hand are visible; no face, torso, laboratory equipment, bottles or extra props. Camera: one slow overhead lateral drift. No blood, no penetration, no scene change.', '布料轻响；轻微器械声'),
    ('S27', 'agnes', '缓慢横移 slow lateral drift',
     '「原理简单也冒险」：夜里的小病房，铁床、木椅、一盏油灯',
     '灯焰轻晃，硬切信息卡',
     'Interior of a small hospital room at night, an iron bed with a still blanket, a wooden '
     'chair beside it, three oil lamps burning on the side table and the wall plus pale '
     'moonlight through a window, the whole room evenly lit and clearly readable, every object '
     'holding visible detail, warm but never dark, the only movement the lamp flame. Camera: '
     'one slow lateral drift from the bed to the chair. No people in frame. Hold this single '
     'view: no cut, no scene change, no camera relocation.',
     '火焰与夜虫声；无音乐'),
    ('S28', 'graphic', '静帧',
     '信息卡④：十天 · 十几针（两份来源针数略有出入，成片不写死）',
     '硬切晨光里的病房',
     '信息卡：十天 · 十几针（画面文字见 CARDS）',
     ''),
    ('S29', 'agnes', '缓慢拉远 slow dolly back',
     '「迈斯特最终没有发病」：晨光里，床上小小的人影慢慢坐起来',
     '坐起来，硬切厨房喝水',
     'Interior of a small hospital room at morning, a small figure sitting up slowly in an '
     'iron bed, seen only as a backlit silhouette from behind, pale light through the window '
     'behind. Camera: one slow dolly back from the bed. No face, no features, no readable '
     'text. Hold this single view: no cut, no scene change, no camera relocation.',
     '晨光里的鸟声；钢琴进入'),
    ('S30', 'agnes', '缓慢推近 slow push in',
     '「一个成功病例不能替代今天的临床试验」：农舍厨房里，一只九岁孩子的小手端起木桌上的小玻璃杯喝水（呼应第三镜被推开的那杯水）',
     '杯子放下，硬切庭院人群',
     "Close on exactly one clearly child-sized nine-year-old right hand and short wrist, in a loose 1885 "
     'linen shirt cuff, beside one small half-full glass tumbler of water on a wooden farmhouse '
     'kitchen table in morning light. Begin with the tumbler resting on the table. During the first '
     'three seconds, the small hand visibly wraps all five natural fingers around the tumbler, lifts '
     'it at least eight centimetres above the tabletop, holds it suspended for a moment, then sets '
     'the same tumbler back down before the shot ends. The lifted base and its separated shadow '
     'must be plainly visible, so the action cannot be mistaken for merely touching or sliding the '
     'glass; water stays inside. The child hand and short wrist are unmistakably small beside a '
     'plain ceramic mug that is clearly much larger. No adult hand, adult forearm or other person '
     'is present. Show only the child hand, wrist, glass, mug and table: no face, no body, no '
     'features. Camera stays locked at tabletop height throughout one continuous view with no cut, '
     'scene change or camera relocation.',
     '喝水声；音乐第一次完整地起来'),

    # ---------------- N05 扩散（S31–S38，8 镜：6 动画 + 2 信息卡） ----------------
('S31', 'agnes', '缓慢下摇 slow tilt down', '「消息传开，病人从英国、俄国、意大利…」：巴黎庭院里的人群背影走向同一扇门', '人群进门，硬切火车站台', 'One exterior 1880s Paris stone courtyard, viewed from above the entrance, with a single crowd of people in dark coats walking away from camera toward one doorway. Camera: one slow tilt down from the courtyard facade to the same moving crowd. Remain outdoors in this courtyard for the entire shot. No laboratory interior, no shelves, no microscopes, no different rooms, no montage, no scene switch, no visible faces or signs.', '人群脚步声与低语；弦乐渐强'),
('S32', 'agnes', '缓慢上摇 slow tilt up', '「德国涌向巴黎」：蒸汽机车驶入十九世纪月台，蒸汽升起', '蒸汽散开，硬切长队', 'Wide exterior view of one nineteenth-century railway platform as a single black steam locomotive rolls slowly into the station. Show the locomotive wheels, rails, platform edge and rising white steam; a few distant waiting people are only dark rear silhouettes. Camera: one slow tilt up from the wheels to the steam. Stay on this same train and platform throughout. No laboratory, shelves, hospital bed, pharmacy, bottles, indoor room, or other scene; no montage or cut; no readable train lettering or faces.', '汽笛与蒸汽声；节奏加快'),
    ('S33', 'agnes', '向前推进 forward dolly',
     '「到一八八六年十一月，已有大约两千五百人接受这种治疗」：石廊里一排坐在长凳上的人，尽头一盏灯',
     '推到走廊中段，硬切信息卡',
     'Interior of a long stone corridor in a Paris institution, a queue of people seated along '
     'a wooden bench on one side, seen strictly from behind, oil lamps spaced along the wall '
     'plus pale daylight from a high window, the whole corridor evenly readable from end to '
     'end. Camera: one slow forward dolly down the corridor. No faces, no readable notices on '
     'the walls. Hold this single view: no cut, no scene change, no camera relocation.',
     '低沉人声与脚步；音乐托住'),
    ('S34', 'graphic', '静帧',
     '信息卡⑤：两千五百人 → 近两万人 · 一八八六年至一八九五年',
     '硬切登记簿',
     '信息卡：两千五百 → 近两万（画面文字见 CARDS）',
     ''),
    ('S35', 'agnes', '缓慢下摇 slow tilt down',
     '「到一八九五年去世时，人数接近两万」：木桌上一册闭合的无字登记簿，旁有一支笔；数字由前一张资料卡承担',
     '镜头掠过空白封面，硬切研究所门楼',
     'Close on one closed dark leather registration ledger on a worn wooden desk, with one '
     'capped fountain pen and one small brass paperweight beside it. The ledger cover is '
     'completely blank: no open pages, marks, letters, numbers, symbols, labels, or writing of '
     'any kind. Camera: one slow tilt down across this same blank cover. No people, no faces, '
     'no hands, no paper sheets, no wall text. Hold this single view: no cut, no scene change, '
     'no camera relocation.',
     '纸页翻动声；音乐渐收'),
    ('S36', 'agnes', '缓慢上摇 slow tilt up',
     '「需求推动建立专门机构」：新落成的石砌门楼',
     '上摇到门楣，硬切生产线',
     'Exterior of the newly finished stone gateway of the Institut Pasteur in Paris in '
     'eighteen eighty eight, clean pale limestone, an open carriage entrance, a few figures in '
     'dark coats passing by seen only from behind. Camera: one slow tilt up from the '
     'flagstones to the top of the arch. No readable inscription, no plaque lettering, no '
     'faces. Hold this single view: no cut, no scene change, no camera relocation.',
     '城市环境声；一记轻鼓（合成）'),
('S37', 'agnes', '横向移动 lateral track', '「一八八七年募款启动」：十九世纪木桌上的捐款信封与空白登记簿，无人', '镜头掠过信封，硬切信息卡', 'In a quiet Paris office in 1887, a plain wooden table holds three sealed unmarked paper donation envelopes, a closed blank leather ledger and one capped fountain pen. Warm daylight falls across the table. Camera: one slow lateral track along these same objects. No people, no hands, no currency, no readable writing, numbers, seals, logos, laboratory equipment, modern objects, scene change or camera relocation.', '纸张轻响；音乐转暖'),
    ('S38', 'graphic', '静帧',
     '信息卡⑥：从急诊到研究所——一八八七年募款启动，一八八八年正式开放',
     '硬切家猫',
     '信息卡：今天仍在（画面文字见 CARDS）',
     ''),

    # ---------------- N06 今天（S39–S45，7 镜：6 动画 + 1 信息卡） ----------------
    ('S39', 'agnes', '低机位缓慢移动 low slow dolly',
     '「狂犬病仍会夺走数万人的生命，儿童承受的负担尤其重」：现代校门外一名儿童牵着成人的手向前走，只见背影',
     '两人走向明亮街道，硬切课桌',
     'At a modern school entrance in soft morning daylight, one school-age child with a small plain backpack walks away from camera while holding one adult hand. Show both only from behind at a respectful distance; the scene is calm and ordinary, with no animals, illness, injury, clinic, readable signs or text. Camera: one slow low dolly following the same two figures for the whole shot. No face, no scene change or camera relocation.',
     '清晨环境声；轻柔脚步'),
    ('S40', 'agnes', '缓慢横移 slow lateral drift',
     '「儿童承受的负担尤其重」：校门口一只儿童的手握住无标记双肩包肩带，不出现面部或医疗情节',
     '手与肩带离开画面，硬切诊室',
     'Close on one small child hand with a simple long-sleeve cuff gently holding one plain, completely unmarked backpack shoulder strap at a modern school entrance in soft daylight. Show only the hand, forearm, smooth strap and a softly blurred neutral wall; the backpack fabric contains no logo, letters, printed patterns, numbers, labels, paper, book, pencil or writing. No face, no injury, no medicine and no medical procedure. Camera: one slow lateral drift across the same hand and strap. One continuous calm scene with no cut or transition.',
     '校门远处环境声；音乐停顿'),
('S41', 'agnes', '缓慢上摇 slow tilt up', '「现代暴露后预防已不同」：现代诊所走廊通向明亮、无文字的诊室门口，无人', '镜头停在门口，硬切信息卡', 'In a clean modern outpatient clinic, one quiet neutral corridor leads to a single open examination-room doorway with soft daylight inside. No people, no patient, no needles, no medicine containers, no readable signs, labels, numbers or logos. Camera: one slow tilt up from the plain floor toward the bright doorway, maintaining readable balanced exposure. One continuous clinic corridor, no cut or scene change.', '诊所环境声；音乐转为平稳'),
    ('S42', 'graphic', '静帧',
     '信息卡⑦：现代暴露后预防——细胞培养疫苗、免疫球蛋白与专业评估',
     '硬切昏暗石廊',
     '信息卡：现代暴露后预防（画面文字见 CARDS）',
     ''),
    ('S43', 'agnes', '缓慢跟拍 backward dolly',
     '「遇到动物咬伤或抓伤」：现代诊所门外，一名成人从背后走向无文字的入口，不展示伤口或动物攻击',
     '背影停在入口，硬切洗手',
     'Outside one modern clinic entrance in daylight, one adult in ordinary clothes is seen strictly from behind walking calmly toward a plain unmarked doorway. The person carries no objects. No animal, no injury, no blood, no emergency action, no readable signs, logos, numbers or text. Camera: one slow backward dolly in front of the person, one continuous exterior view with no face, cut or scene change.',
     '平稳脚步声；音乐收束'),
    ('S44', 'agnes', '固定近景 locked close-up',
     '「先用肥皂和流动水彻底清洗」：现代洗手台上双手在流动水与泡沫下清洗，不出现伤口',
     '水流收住，硬切旧注射器与现代疫苗瓶',
     'Close on two clean adult hands washing under running water with soap foam at a modern sink in neutral daylight. Show only hands, water, soap and the plain sink; no wound, no blood, no face, no text, no labels and no medical procedure. Camera: locked close-up with gentle natural movement in the water. One continuous scene, no cut or transition.',
     '清水声；音乐收成单音'),
('S45', 'agnes', '俯视固定静物 top-down locked still life', '「专业人员判断下一步；证据要先于传奇」：诊室木桌上的旧玻璃注射器与现代疫苗瓶', '两件物品保持俯视近景，淡出', 'Orthographic top-down product still life. The complete 16:9 image is an uninterrupted, seamless pale wooden tabletop from edge to edge, with no horizon line and no background visible. Exactly two and only two objects exist anywhere in the frame: one old long glass syringe with a thin metal needle, and one sealed modern vaccine vial. The vial is plain clear glass with a completely blank, unprinted cream paper band: no label text, letters, numbers, logo, marks or symbols. Place both objects fully within the central tabletop, separated and clearly visible. Camera remains perfectly locked overhead for the complete shot: no pull-back, pan, tilt, widening, reflection revealing a room, or new object entering. There is no kitchen, clinic room, shelf, counter, window, animal, person, hand, bed, bottle, equipment, container, shadow of a third prop or background prop. No text or readable labels. One continuous scene with only these two objects.', '环境声淡出；最后一个钢琴音'),
]

# ---------------------------------------------------------------------------
# 画面上的文字（render.py 从 story.json 的 presentation 块读，不在 render.py 里写死）
# ---------------------------------------------------------------------------
CARD_HEADER = "狂犬病疫苗 · 一八八五"                                   # 每张信息卡左上角的小字
CARD_FOOTER = "资料摘要与示意图 · 并非原始档案影像"                       # 每张信息卡左下角的小字

CARDS = {
    "S07": ("发病之后", "狂犬病 · 病死率", "出现临床症状后，病死率几乎百分之百"),
    "S13": ("路易·巴斯德", "化学家 · 不是执业医生", "先固定病原，再以干燥降低毒力"),
    "S21": ("一八八五年七月六日", "巴黎 · 高等师范学校实验室", "九岁的约瑟夫，来自阿尔萨斯"),
    "S28": ("十天 · 十几针", "材料按由弱到强的次序推进", "十三针 / 十四剂，史料计数有差异"),
    "S34": ("两千五百 → 近两万", "一八八六年十一月约两千五百人接受治疗", "到一八九五年，人数接近两万"),
    "S38": ("从急诊到研究所", "一八八七年：募款启动", "一八八八年：巴黎巴斯德研究所正式开放"),
    "S42": ("现代暴露后预防", "细胞培养疫苗 · 免疫球蛋白 · 专业评估", "由当地医生或公共卫生机构按暴露情况判断"),
}

TITLE_CARD = ["狂犬病疫苗", "一百四十年前那场赌局"]

END_CARD = [
    "医学史最该被记住的，是勇气，还是验证勇气的证据？",
    "狂犬病疫苗 · 巴黎 · 一八八五年",
    "证据要先于传奇，救治要快于病毒。",
    "资料：WHO / 美国 CDC / 巴斯德研究所 · 原创解说 · AI动画情景重现",
]

CAPTION_KEYWORDS = [
    "症状出现", "化学家", "巴斯德", "固定病毒", "干燥", "不是执业医生",
    "一八八五年", "约瑟夫", "十四处", "格朗谢", "十天", "十三针", "十四剂",
    "两千五百", "两万", "数万人", "四成", "伤口清洗", "专业评估", "一百四十年前",
]

# 医疗/接种镜头换更具体的标签，避免被当成真实医疗教学影像
LABEL_OVERRIDES = {
    "S22": "AI动画情景重现 · 非历史影像",
    "S23": "AI动画情景重现 · 非历史影像",
    "S26": "AI动画示意 · 非医疗教学影像",
    "S27": "AI动画情景重现 · 非历史影像",
    "S29": "AI动画情景重现 · 非历史影像",
    "S35": "AI动画情景重现 · 非历史影像",
    "S36": "AI动画情景重现 · 非历史影像",
    "S40": "AI动画示意 · 非医疗教学影像",
    "S41": "AI动画示意 · 非医疗教学影像",
    "S43": "AI动画示意 · 非医疗教学影像",
}

# 合成音效事件：(镜头号, 类型)，类型可选 paper / phone / keys / machine / press，落在该镜开始前 0.18 秒
SFX_EVENTS = [
    ("S08", "paper"),
    ("S12", "machine"),
    ("S14", "keys"),
    ("S23", "keys"),
    ("S26", "press"),
    ("S32", "machine"),
    ("S37", "paper"),
    ("S45", "keys"),
]

# ---------------------------------------------------------------------------
# 发布文案（抖音脚本.md / 抖音发布文案.md 用）
# ---------------------------------------------------------------------------
TITLES = [
    "九岁男孩、十几针：巴斯德如何让暴露后预防成为可能",
    "一八八五年巴黎：一个孩子如何改变狂犬病疫苗史",
    "从兔脊髓到现代预防：巴斯德那场赌局，不能被浪漫化",
]

HOOK = ("一八八五年，九岁的约瑟夫·迈斯特来到巴黎。巴斯德团队把只在动物中验证过的方法用于一次"
        "严重暴露：十天、十几针，开启了暴露后预防的新可能。")

GOLDEN_LINES = [
    "证据要先于传奇，救治要快于病毒。",
    "医学突破不是孤注一掷的神话，而是持续检验与修正的过程。",
    "潜在暴露后：先清洗，再尽快求助专业机构。",
]

DESCRIPTION = ("一八八五年七月，九岁的约瑟夫·迈斯特被带到巴黎。巴斯德团队先以兔之间连续传代"
               "获得稳定材料，再以干燥降低毒力；在医生参与下，迈斯特接受了十天、十几针的暴露后治疗。"
               "本片复盘这场历史上的紧急决定，也说明它不能替代今天的循证医疗。遇到动物咬伤或抓伤，"
               "请立即清洗，并尽快按当地医生或公共卫生机构的指引处理。画面均为 AI 动画情景重现，非历史影像。")

QUESTION = "医学史最该被记住的，是勇气，还是验证勇气的证据？"

HASHTAGS = ["#狂犬病", "#巴斯德", "#疫苗", "#科普", "#真实历史", "#冷知识", "#医学史"]

# 曝光收尾：挂在每一镜的描述之后，但只写曝光质量，不指定灯具、窗户或其他道具；
# 场景里的具体光源只能由该镜头提示词决定，避免把历史布光错误带进现代场景。
LIGHTING_SUFFIX = (
    "Balanced film-scan exposure with readable midtones and detail in both highlights and shadows; "
    "follow only the light sources described in this shot, and do not add or remove props or light sources."
)

GRID = 4           # 规划网格：每镜 4 秒，45 镜 = 180 秒
AGNES_SECONDS = 7  # 每个 Agnes 镜头实际请求的时长（169 帧 @ 24 fps）
SEED_BASE = 18850706  # 用第一针的日期，seed 可追溯
SEED_OVERRIDES = {"S18": 18850818}  # S18 需隔离重试，避免复用错误语义的随机种子


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
            "prompt": (body.strip() + " " + LIGHTING_SUFFIX) if kind == "agnes" else "",
            "purpose": purpose, "transition_out": transition,
            "graphic": body if kind == "graphic" else "",
            "seed": SEED_OVERRIDES.get(sid, SEED_BASE + i + 1),
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


def render_screenplay() -> str:
    """从 story.json 渲染 screenplay.md。

    手工抄录解说词迟早会对不上，所以解说词、分镜表、事实边界一律由 story.json 生成：
    三处逐字一致是 generate.py --validate 的硬要求，靠人抄是靠不住的。
    """
    story = json.loads(PLAN.read_text())
    lines = [
        f"# {story['title']}",
        "",
        "三分钟横屏解说 · 成片目标 1920×1080 / 30 fps / 180 秒",
        "",
        "## 事实边界",
        "",
        "这一段是这部片子的底线，比任何画面都重要：",
        "",
    ]
    lines += [f"- {p}" for p in story["principles"]]
    lines += [
        "",
        "**本版事实边界**：",
        "",
        "- 兔之间连续传代用于得到潜伏期稳定的固定病毒；**降低毒力的是随后对感染兔脊髓的干燥处理**，两步不能倒置；",
        "- 巴斯德不是执业医生；第一针由儿科医生雅克—约瑟夫·格朗谢执行，片中不把注射写成巴斯德亲手完成；",
        "- 针数两份权威来源不一致（美国 CDC 十四剂 / 巴斯德研究所十三针），成片只说「十天、十几针」；",
        "- 现代暴露后预防不展示地区特定剂次表；只给出「立即清洗、尽快由专业人员评估」的跨地区公共卫生提示。",
        "",
        "## 解说稿与时间线",
        "",
    ]
    for i, ch in enumerate(story["chapters"]):
        start, end = i * 30, (i + 1) * 30
        lines += [
            f"### {start // 60:02d}:{start % 60:02d}—{end // 60:02d}:{end % 60:02d}　{ch['title']}（{ch['id']}）",
            "",
            ch["text"],
            "",
        ]
    lines += ["## 分镜与衔接", "",
              "| 镜头 | 规划时间 | 类型 | 叙事职责 | 运镜 | 衔接方式 |",
              "|---|---|---|---|---|---|"]
    for sh in story["shots"]:
        lines.append(
            "| {id} | {s:03d}—{e:03d}s | {kind} | {purpose} | {camera} | {trans} |".format(
                id=sh["id"], s=sh["start"], e=sh["start"] + sh["duration"],
                kind={"agnes": "Agnes 动画", "graphic": "信息卡"}[sh["kind"]],
                purpose=sh["purpose"], camera=sh["camera"], trans=sh["transition_out"]))
        if sh["start"] + sh["duration"] in (32, 60, 92, 120, 152) or sh["id"] == story["shots"][-1]["id"]:
            lines.append(f"| — | — | 解说 {sh['narration_id']} 结束 | — | — | — |")
    lines += ["", "## 资料来源", ""]
    for src in story["sources"]:
        lines.append(f"- [{src['id']}] {src['url']} —— {src['usage']}")
    return "\n".join(lines) + "\n"


def _screenplay():
    out = HERE / "screenplay.md"
    out.write_text(render_screenplay(), encoding="utf-8")
    print(f"screenplay.md 已写入（{len(out.read_text(encoding='utf-8'))} 字符）")


if __name__ == "__main__":
    if "--script" in sys.argv:
        from script_table import render_document  # noqa: E402  (同目录)
        out = HERE / "抖音脚本.md"
        out.write_text(render_document())
        print(f"抖音脚本.md 已写入（{len(out.read_text())} 字符）")
    elif "--screenplay" in sys.argv:
        _screenplay()
    elif "--publish" in sys.argv:
        from script_table import publish_document  # noqa: E402  (同目录)
        out = HERE / "抖音发布文案.md"
        out.write_text(publish_document())
        print(f"抖音发布文案.md 已写入（{len(out.read_text())} 字符）")
    else:
        build()
