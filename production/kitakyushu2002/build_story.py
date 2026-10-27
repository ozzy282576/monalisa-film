#!/usr/bin/env python3
"""《北九州监禁案：逃出魔窟的少女，七条人命背后的秘密》的全部内容源。

这是这部片子**唯一需要动脑写的文件**（引擎由 production/kanghosun2009 的模板移植而来，
内容按用户上传的 30 镜文案稿（抖音文案/20261017-011840_粘贴的文案_20261017-011840.txt）重写，
事实按 SOURCES 里的 10 条公开来源核对，见 史实核对.md）。

用法::

    python3 production/kitakyushu2002/build_story.py            # 写 story.json（含 presentation 块）+ audio/manifest.json 的逐字文本
    python3 production/kitakyushu2002/build_story.py --script   # 生成 抖音脚本.md（3 标题 / 核心爆点 / 四列分镜表 / 金句）
    python3 production/kitakyushu2002/build_story.py --publish  # 生成 抖音发布文案.md（标题 / 介绍 / 提问读者一句话 / 话题）

本片是**露脸模式**：五个角色各一张不同的脸，同一角色跨镜头逐字节复用同一条面容 token
（token 只在 cast.json 里写一份，本文件用 {C1}…{C5} 占位符注入，保证逐字节一致），
并复用同一个 seed；由 production/face_cast.py 的 check-prompts / check-frames 两道闸门守着。

视频模型走**智谱 CogVideoX-Flash 免费档**（generate_cogvideox.py，不调 Agnes、不产生费用）。

分镜与解说逐句咬合的章法（45 镜 = 38 动态 + 7 信息卡，每章镜头只服务本章解说词）：
  N01 逃脱与曝光（S01-S08）· N02 起点与操纵（S09-S15）· N03 恐惧进了家门（S16-S23）
  N04 七条人命（S24-S30）· N05 法庭（S31-S38）· N06 没有铁栏的牢笼（S39-S45）
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "story.json"
MANIFEST = HERE / "audio" / "manifest.json"
CAST = HERE / "cast.json"

TITLE = "北九州监禁案：逃出魔窟的少女，七条人命背后的秘密"

# 全片统一的画面风格前缀（英文）。写实 3D CGI 情景重现（不是 2D、不是图片轮播）。
# 注意：style_prefix 参与全部镜头的 request_hash，开工后改一个字 = 38 镜全部重做。
STYLE_PREFIX = (
    "Photorealistic cinematic 3D animated reenactment, high-end CGI feature-film render with volumetric "
    "light, shallow depth of field and subtle 35mm film grain, set in Japan between 1996 and 2011: a plain "
    "1990s apartment block in Kokurakita ward of Kitakyushu with tiled walls and small tatami-and-laminate "
    "rooms, rain-slicked night streets under sodium lamps, ordinary Japanese suburban lanes, plain 2000s "
    "police stations, a wood-panelled district courtroom and a high-walled detention facility, overcast "
    "daylight, rainy nights and cold grey winters, restrained desaturated blue-grey grading, slow-burn "
    "true-crime documentary mood, never stylised, never a drawing, never a cartoon; horizontal 16:9 "
    "widescreen composition; characters act with clear full-body movement in medium and wide shots rather "
    "than close-ups - a face is shown only where a shot names one of the cast characters, never a "
    "recognisable real person; absolutely no readable text, letters, numbers, logos or brand marks "
    "anywhere in frame; one single continuous smooth camera move per shot exactly as directed. "
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
    "全部动态镜头为写实 3D CGI 动画情景重现，画面常驻标注「AI动画情景重现 · 非新闻影像」，"
    "不冒充搜查、审讯、庭审、监控或证物照片",
    "不展示遗体、血腥或虐待过程：监禁与暴力只通过环境、光影与人物反应暗示（忽明忽暗的灯、"
    "紧握的双手、关上的门、墙上的影子），现场镜头只出现警戒线、编号标记与勘查背影",
    "松永太与绪方纯子本人不做肖像还原：情景重现由虚构匿名角色 C1 / C2 扮演，片尾卡与标签都写明"
    "「非本人容貌」；押解、服刑等镜头只给背影",
    "受害者与逃脱少女全程不给可辨识面容：少女只以背影、剪影、手与脚步出现；受害者只以空座位、"
    "翻扣的相框、物件或聚合数字出现，不出现遗体，不出现真实姓名与照片",
    "五个露脸角色（松永太替身 / 绪方纯子替身 / 老刑警 / 检察官 / 法官）各有一张不同的脸；"
    "同一角色跨镜头逐字节复用同一条面容 token 并共用同一个 seed",
    "由 production/face_cast.py 的 check-prompts（静态闸门）与 check-frames（画面闸门）检查，"
    "人眼对照接触表判决",
    "每一句事实都能指到 sources 里的一条公开来源；口径冲突处（逮捕日三月六日 / 七日、"
    "犯行开始年等）只写多源一致的写法（「第二天」「从一九九六年起」），不挑一个当结论",
    "所有中文姓名、日期、字幕后期添加，不交给视频模型拼写；画面内不出现任何可读文字、门牌或招牌",
    "人工检视 qa/ 接触表与 delivery/face-cast/ 人脸接触表；换脸、畸变、伪文字、中途换场的镜头用 "
    "{\"only\":\"Sxx\"} 重生成，不直接进成片",
    "画面与解说都不把犯罪者写成传奇：不美化、不猎奇，落点是七名受害者与「被剥夺的选择」",
]

# 每条事实的公开来源。
SOURCES = [
    {"id": 1, "url": "https://ja.wikipedia.org/wiki/北九州監禁殺人事件",
     "usage": "支撑：犯行约六年（一九九六至二〇〇二年三月），受害者计七人；二〇〇二年最初被监禁的"
              "十七岁少女从虐待中逃脱、向祖父家求助，案件才被发现；二〇一一年松永（M）死刑确定、"
              "内缘妻子（B）杀人共犯无期惩役确定"},
    {"id": 2, "url": "https://zh.wikipedia.org/wiki/北九州监禁杀人事件",
     "usage": "支撑：宣判日期一审二〇〇五年九月二十八日、二审二〇〇七年九月二十六日、终审二〇一一年"
              "十二月十二日；松永太生于一九六一年四月二十八日；现羁押在福冈拘置所等待执行"},
    {"id": 3, "url": "https://bunshun.jp/articles/-/67853",
     "usage": "支撑（事件日志）：少女逃走后两人于二〇〇二年三月七日被逮捕；依裁判迅速化法自"
              "二〇〇三年十月起每周审理一次；二〇〇五年三月二日论告求刑（死刑）；九月二十八日一审判决；"
              "松永即日控诉、绪方十月十一日控诉；控诉审二〇〇七年一月二十四日开始、九月二十六日宣判；"
              "二〇一一年十二月十二日最高裁驳回双方上告"},
    {"id": 4, "url": "https://www.nikkei.com/article/DGXNASDG14027_U1A211C1CC1000/",
     "usage": "支撑：最高裁认定绪方纯子「与松永共谋，杀害六人、致一人死亡」（六起谋杀 + 一起致死）；"
              "「对遗体的处置等案后行为也很残忍」；绪方长期遭受异常虐待、检方上告被驳回，无期惩役确定"
              "（决定为十二月十二日付）；松永同日在最高裁被判死刑"},
    {"id": 5, "url": "https://www.nikkei.com/article/DGXNASDG1202S_S1A211C1CC1000/",
     "usage": "支撑：二〇一一年十二月十二日最高裁第一小法廷以「主导犯行、刑事责任极为重大」"
              "驳回松永太上告，死刑确定"},
    {"id": 6, "url": "https://www.youtube.com/watch?v=zuJDdm3GC8M",
     "usage": "支撑：二〇〇五年九月二十八日一审宣判（当年新闻画面说明）：福冈地裁小仓支部认定"
              "两被告杀害六人、以伤害致死致一人死亡，双双判处死刑"},
    {"id": 7, "url": "https://dic.nicovideo.jp/a/北九州監禁殺人事件",
     "usage": "支撑：二〇〇五年九月二十八日两名为死刑；二〇〇七年九月二十六日福冈高裁维持松永死刑、"
              "撤销绪方一审死刑改判无期（认定其处于松永的暴力支配下、参与具从属性，且认罪与反省态度被考量）；"
              "二〇一一年十二月十二日最高裁支持，松永死刑确定"},
    {"id": 8, "url": "https://www.kiritani-station.com/北九州連続監禁殺人事件の全貌｜松永太と緒方純子",
     "usage": "支撑：一审检方以两被告主导、反复实施极恶劣犯行为由求刑死刑；二审认定绪方纯子"
              "处于松永极端的精神控制（mind control）之下、犯行参与为从属性质，故撤销死刑改判无期"},
    {"id": 9, "url": "https://wondia.net/ogata-junko",
     "usage": "支撑（时间线交叉核对）：二〇〇二年三月小仓北区一间公寓内七名男女被监禁杀害的案情曝光；"
              "二〇〇五年九月二十八日一审双双死刑；二〇〇七年九月二十六日二审绪方改判无期；"
              "二〇一一年十二月十二日最高裁驳回，两人刑期分别确定"},
    {"id": 10, "url": "https://jikenarai.doorblog.jp/archives/9774415.html",
     "usage": "支撑：案发地为北九州市小仓北区片野一丁目的公寓（一九九六年至二〇〇二年三月六日）；"
              "松永太死刑（未执行）、绪方纯子无期惩役；管辖为福冈县警搜查一课与小仓北署"},
]

# 六段解说：(章节 id, 章节标题, 逐字解说词)。六段合计 ≈ 736 字（含标点）。
CHAPTERS = [
    ("N01", "黄金开头：深夜逃出去的少女",
     "二〇〇二年三月，日本北九州。深夜，一名十七岁的少女，从一间普通公寓逃了出来——"
     "她之前逃出去过一次，又被抓了回去。这一次，她跑到祖父家求助，终于有人信了她。"
     "第二天，警方进入公寓，表面看不出异常；控制这里的两人——松永太，和内缘妻子绪方纯子，随即被捕。"
     "调查越深，失踪、死亡和监禁，越连成同一条线——这间普通的屋子里，藏着七条人命。"),
    ("N02", "案件起点：控制，从信任开始",
     "要理解这间屋子里发生的事，得回到九十年代。松永太早年做生意，后来卷入诈骗，欠下债务、四处逃亡。"
     "他最擅长的，是操纵人心：用谎言、威胁和经济压力，把身边的人一步步变成自己的工具。"
     "绪方纯子和她的家人，就是这样一点一点，落进他的控制之中。"),
    ("N03", "恐惧进了家门：一九九六年起",
     "从一九九六年起，绪方的家人接连被带进这间公寓。一九九六年到一九九八年，多名受害者在这里遭到"
     "监禁、虐待和控制——原本应该保护彼此的亲人，被恐惧推向绝境：不敢对视，不敢多问，"
     "连求救的机会都被一点点剥夺。这不是家庭纠纷，是持续的恐吓与暴力。"),
    ("N04", "七条人命：真相逐渐显现",
     "这场悲剧最终吞噬了绪方家的多名成员。死亡在封闭的屋子里接连发生，外界却几乎一无所知。"
     "直到少女逃出、开口陈述，警方才把失踪、死亡和监禁串成一条线：七名死亡受害者，"
     "大多是绪方的家人，其中包括两名孩子；六起被认定为谋杀，另一起被认定为伤害致死。"),
    ("N05", "法庭：责任与支配的争议",
     "二〇〇三年十月，审判开始；因为案情太多，此后每周开庭一次。法庭上，两人的责任成为焦点："
     "绪方承认参与，但辩护方强调，她长期受到松永的支配和虐待；松永则否认自己应为全部罪行负责。"
     "二〇〇五年九月，一审双双判处死刑；两年后，二审改判绪方无期徒刑。"),
    ("N06", "结尾：没有铁栏的牢笼",
     "二〇一一年十二月，最高法院维持原判：松永太死刑确定，绪方纯子无期徒刑确定。"
     "回头看，这间公寓和普通住宅没有任何区别——最可怕的不是某个瞬间的暴行，"
     "而是六年的恐怖就藏在日常的表象之下。恐惧、谎言和被剥夺的选择，筑成了一座没有铁栏的牢笼。"
     "判决确定了刑期，却换不回七条生命。"),
]

HOLD = ("no cut, no scene change, no camera relocation, no extra people, "
        "no readable text in frame; hold on this single view for the full clip.")

SHOTS = [
    # ---------------- N01 逃脱与曝光（S01-S08：7 动态 + 1 信息卡）----------------
    ("S01", "agnes", "低机位跟拍，急促推进", "钩子：深夜，少女冲出公寓楼道",
     "接信息卡：案件名片",
     "A rainy late night in March 2002 outside a plain 1990s Japanese apartment block in Kokurakita ward, "
     "Kitakyushu: a narrow stairwell door swings open and a seventeen-year-old girl in a rumpled school coat "
     "and skirt rushes out onto the wet pavement, trembling, one hand gripping the strap of a small bag, seen "
     "only from behind and the side so her face never becomes visible; rain streaks the tiled wall and runs "
     "down the drainpipe, a single bare bulb lights the entrance, the street beyond is dark and empty of "
     "traffic. Low camera at pavement level tracking her hurried steps away from the entrance as the heavy "
     "door slowly swings shut behind her, " + HOLD,
     "急促脚步 + 雨声 + 沉重呼吸"),
    ("S02", "graphic", "信息卡（静帧）", "名片：案名 / 地点与年代 / 规模",
     "接动态镜：雨夜街道上的奔逃",
     "案件名片：案名 / 地点与年代 / 规模",
     "低音撞击"),
    ("S03", "agnes", "手持感跟拍，轻微晃动", "她跑过雨夜的街道，不断回头（逃出来，又被抓回去）",
     "接动态镜：祖父家的求助",
     "The same girl runs unsteadily down a wet narrow residential street in Kitakyushu at night: puddles pull "
     "long distorted reflections of red and blue neon tubes and distant headlights, she glances back over her "
     "shoulder again and again without her face ever becoming visible, and halfway down the street she freezes "
     "as a pair of headlights sweeps across her from behind the camera; low old shop fronts line the street "
     "with every signboard completely blank and unlit, overhead cables cross the dark sky. Slightly unsteady "
     "slow tracking shot behind her at street level, ending as she stands frozen in the light, " + HOLD,
     "雨声 + 汽车驶过 + 心跳声"),
    ("S04", "agnes", "从紧抓衣角的手缓慢上移", "祖父家：这一次，有人信了她",
     "接动态镜：第二天警方进入公寓",
     "The dim living room of an ordinary Japanese house in the small hours of the morning: the seventeen-year-"
     "old girl sits on the floor cushion at a low table, seen from behind at a three-quarter angle so only her "
     "back, her shoulder and her tightly clenched hands gripping the hem of her coat are visible, her whole "
     "body trembling; an elderly grandfather stands a step away in the half-dark holding a cup of tea he has "
     "just set down, his face kept in shadow and out of focus, leaning toward her as he listens; a plain "
     "paper lamp glows, the room is ordinary and bare, no photographs, no readable text. Slow push from her "
     "clenched hands up along her arm to her shoulder, stopping before her face, " + HOLD,
     "门铃声 + 茶杯轻响 + 低频弦乐"),
    ("S05", "agnes", "缓慢横移，利用门框压缩空间", "第二天：警方进入公寓，表面看不出异常",
     "接动态镜：清晨被带走的两人",
     "Daytime inside the small Japanese apartment a day later: plainclothes officers and one uniformed officer "
     "walk slowly through a tatami room and a cramped kitchenette, moving ordinary furniture with gloved "
     "hands — a low table, floor cushions, a refrigerator with blank magnets, a drying rack with laundry — "
     "and everything looks disturbingly normal; the officers' faces stay turned away or in shadow the whole "
     "time, their movements slowing as their posture stiffens. Slow lateral move through a doorway, the door "
     "frame compressing the space around the searching officers, " + HOLD,
     "脚步 + 翻动纸张 + 低沉氛围音"),
    ("S06", "agnes", "长焦跟拍，隔着街道", "随即被捕：清晨，两人被带走",
     "接动态镜：调查室里的关系图",
     "Early grey morning at the same apartment block: a man and a woman in plain dark coats walk slowly out "
     "of the stairwell flanked by two uniformed officers, all four seen from behind at a long distance across "
     "the wet street, the pair's heads bowed, the officers' hands steady on their arms; a black-and-white "
     "patrol car waits at the kerb with its light bar silently turning, and two or three neighbours stand far "
     "back under an umbrella without moving. Long-lens-feel slow tracking shot from across the street as the "
     "four figures cross to the patrol car, " + HOLD,
     "远处车门 + 雨后街道环境音"),
    ("S07", "agnes", "俯拍桌面缓慢推近", "调查越深入，越像同一条线：关系图上的结",
     "接动态镜：勘查之后空掉的房间",
     "A police investigation room in Kitakyushu in March 2002 lit by one desk lamp: a veteran Japanese "
     "detective {C3} stands over a wide desk where a hand-drawn apartment floor plan is pinned flat, small "
     "blank white cards connected to it by lengths of red thread fanned across the table, and he works the "
     "board in continuous motion — lifting one blank card, re-pinning it nearer the plan, drawing a thread "
     "taut between two pins, then straightening and leaning in again with his jaw set; a stack of closed buff "
     "folders sits at the table edge, every card and folder blank. Slow overhead push down toward the plan as "
     "he keeps connecting the threads, " + HOLD,
     "纸张翻动 + 铅笔划线 + 低频悬念音"),
    ("S08", "agnes", "缓慢推向房间深处的门", "勘查之后：屋子空了，秘密还在门后",
     "接 N02：回到九十年代",
     "The same apartment later the same day, standing empty after the search: the main room dim, cushions "
     "slightly displaced, a drawer left half open, and at the far end of the hallway one sliding door closed, "
     "the daylight failing around it; nothing moves, no people, the ordinary furniture sitting strangely "
     "silent. Slow push from the doorway of the main room down the length of the apartment toward the closed "
     "sliding door, " + HOLD,
     "纸笔声渐远 + 低频余音"),

    # ---------------- N02 起点与操纵（S09-S15：6 动态 + 1 信息卡）----------------
    ("S09", "agnes", "缓慢环绕，光线渐冷", "回到九十年代：一个礼貌微笑的男人",
     "接信息卡：两名被告",
     "A tidy Japanese living room in the mid-nineteen-nineties in soft daylight: a lean Japanese man of forty "
     "{C1} stands by the window in a plain dark crew-neck sweater, shown chest-up with his faint polite smile "
     "unwavering as he speaks a slow calm greeting, one hand making a small soft gesture; a step behind him a "
     "woman in a cardigan stands seen entirely from behind, only her back and the side of her head in frame; "
     "the room is orderly and plain — a sofa with a folded cloth, a shelf with no photographs — and carries no "
     "readable text. Slow orbit that keeps his calm smiling face in frame while the light cools as the camera "
     "passes the window, " + HOLD,
     "低音弦乐渐起，随后突然收住"),
    ("S10", "graphic", "信息卡（静帧）", "名片：两名被告",
     "接动态镜：交谈中的阴影",
     "案件名片：两名被告的身份与关系",
     "低音撞击"),
    ("S11", "agnes", "从明亮的窗缓慢推向室内阴影", "日常的交谈，阴影一点点覆盖两人",
     "接动态镜：桌面上的账单",
     "Inside one tidy Japanese living room in the afternoon, the whole shot staying indoors from the "
     "first frame to the last with no exterior and no transition: the man sits at the low table speaking calmly, framed over the "
     "shoulder of the woman who listens facing away from camera, so only her back and the back of her head "
     "are visible while he sits across the table in half-shadow, his face turned aside into the shade and "
     "never clearly visible; bright afternoon sun falls through a lace curtain at the left of frame while the "
     "interior corner behind them sits dark, and as the shot proceeds the sunny patch shrinks and the shadow "
     "edge creeps across the tatami toward the table. Slow push from the bright window side of the room "
     "toward the dark corner where the two figures sit, " + HOLD,
     "轻微环境声 + 压抑的低音"),
    ("S12", "agnes", "桌面特写缓慢横移", "账单与文件：经济压力下的困境",
     "接动态镜：绪方独处的昏暗房间",
     "A dark wooden desk at night under a shaded lamp: a man's hand in a dark sweater sleeve slides a thin "
     "folded document and a fanned stack of unfolded bills across the desktop toward the far edge, while the "
     "other hand taps the surface twice, slowly; at the receiving edge a second pair of hands hovers, fingers "
     "drawn back, hesitating — the two participants present only as hands and forearms, no faces in frame; a "
     "closed account book and a pen lie to one side, a wall clock without numerals hangs blurred behind, "
     "every document and bill kept blank and angled away from the lens. Slow overhead lateral move across "
     "the desktop following the sliding documents to the hesitating hands, " + HOLD,
     "文件滑动声 + 钟表滴答 + 低频鼓点"),
    ("S13", "agnes", "固定镜头缓慢推近，门框封闭构图", "绪方独处：门框里出现他的身影",
     "接动态镜：一家人围坐的餐桌",
     "A dim tatami room at dusk in the late nineties: a thin Japanese woman in a plain cardigan sits alone on "
     "a floor cushion at a low table, seen from behind at a distance, her shoulders rounded, a cold cup of "
     "tea untouched in front of her; her head turns slightly toward the doorway and stops there, listening, "
     "as slow footsteps approach out of sight — and in the doorframe behind her a man's dark silhouette "
     "appears and remains motionless, no face visible on either figure, the corridor behind him black. Fixed "
     "camera with a very slow push, the doorframe boxing her in, " + HOLD,
     "脚步声 + 门轴声"),
    ("S14", "agnes", "缓慢横移过每张低垂的脸", "一家人围坐：没有人动筷",
     "接动态镜：狭窄房间里的沉默",
     "A small Japanese dining room at night: five people sit around a low table set with shared dishes still "
     "steaming, and nobody lifts their chopsticks — heads bowed, shoulders stooped, eyes flicking up toward "
     "the head of the table where a man sits centrally with his back squarely to camera, only the back of his "
     "head and shoulders visible; the other four are seen in profile or from behind so no face becomes "
     "clearly readable, the refrigerator hums in the corner, everything plain and blank. Very slow lateral "
     "move around the table from one bowed figure to the next, ending framed on the man's motionless back, "
     + HOLD,
     "餐具轻响 + 沉重的环境低音"),
    ("S15", "agnes", "俯角缓慢后退，门框切割画面", "狭窄的房间：门被关上，眼神立刻收回",
     "接 N03：一九九六年起的恐惧",
     "A narrow back room of the apartment in daytime: seen from high in the corner of the ceiling, two "
     "figures sit far apart on the floor, and as the sliding paper door runs shut on its rail one of them "
     "begins to raise a glance toward the other — then drops their head immediately as the door thuds softly "
     "into its frame; the window is covered by a curtain with only a blade of light at its edge, both faces "
     "turned away or shadowed beyond recognition, the room bare of decoration. The camera very slowly "
     "retreats higher and further back as the closing doorframe cuts the two figures into separate boxes, "
     + HOLD,
     "门锁声 + 远处模糊的车辆声"),

    # ---------------- N03 恐惧进了家门（S16-S23：7 动态 + 1 信息卡）----------------
    ("S16", "agnes", "特写缓慢漂移：手—肩—墙—门", "忽明忽暗的灯：只有紧握的手与墙上的影子",
     "接信息卡：一九九六—一九九八",
     "A dark room where a bare ceiling bulb flickers weakly: in the stuttering half-light only fragments are "
     "ever visible — two hands clenched white-knuckled on a knee, a shoulder trembling under a sweater, and a "
     "shadow sliding slowly across the wallpaper; no face appears at any moment, no figure is fully resolved, "
     "nothing violent is shown, only stillness, dread and the failing light, the rest of the room swallowed "
     "by black. One continuous slow drift of the frame from the clenched hands up past the trembling shoulder "
     "to the moving shadow on the wall, ending on a closed door, " + HOLD,
     "电流般的氛围音 + 沉重呼吸"),
    ("S17", "graphic", "信息卡（静帧）", "档案：一九九六—一九九八",
     "接动态镜：俯拍下的公寓主间",
     "案件档案：时间段与发生的事",
     "低音撞击"),
    ("S18", "agnes", "垂直俯拍后缓慢下降", "他在中央，所有人散在四周，无人靠近",
     "接动态镜：背对背的剪影",
     "High overhead shot of the apartment's main room: a man stands motionless at the exact centre of the "
     "tatami floor in a dark sweater, his face angled away and unseen from above, while five figures sit or "
     "kneel scattered at the edges of the room, each turned away from the others, as far from one another as "
     "the walls allow; the overhead angle keeps every face hidden, the composition cold and geometric, the "
     "room bare. The camera starts directly overhead and descends very slowly toward the central standing "
     "figure, " + HOLD,
     "低沉鼓点 + 室内回声"),
    ("S19", "agnes", "沿剪影线缓慢横移", "不敢对视：背对背坐在阴影里",
     "接动态镜：被拉死的窗帘",
     "A dark room at night lit only by a thin slit of hallway light: four seated silhouettes are scattered "
     "across the floor with their backs to one another, shoulders hunched, nobody turning, nobody speaking, "
     "their faces lost entirely in the black; a low table sits empty between them, the slit of light cutting "
     "a pale line across the floorboards. Slow lateral drift along the line of hunched silhouettes from the "
     "nearest to the farthest, " + HOLD,
     "极静 + 远处冰箱嗡鸣"),
    ("S20", "agnes", "固定镜头缓慢推向封死的窗帘", "连光也被关在外面：窗帘被拉死",
     "接动态镜：门外的脚步",
     "A plain room by day: two hands — only hands and forearms in frame — pull a heavy curtain fully across "
     "the window and smooth it flat against the wall, and the daylight shrinks to a thin bright line, then to "
     "nothing, the room sinking into grey; the hands drop away, the sealed curtain hangs dead still. Fixed "
     "shot with a very slow push toward the sealed curtain as the light dies, " + HOLD,
     "布料摩擦声 + 骤然的安静"),
    ("S21", "agnes", "沿走廊缓慢推进到门口", "门外的脚步：门内的手停在半空",
     "接动态镜：拉长的影子",
     "The narrow corridor inside the apartment at night, seen from inside a dark room through its doorway: "
     "slow footsteps approach along the wooden floor, growing nearer, while in the foreground a figure who "
     "had been reaching toward the door freezes mid-motion, hand hovering in the dark, then sinks back out "
     "of silhouette; no face visible anywhere, the corridor light failing at its far end. Slow push from the "
     "dark room toward the doorway and the approaching footsteps, " + HOLD,
     "木地板脚步声 + 屏住的呼吸"),
    ("S22", "agnes", "固定镜头，影子缓缓拉长", "摇晃的灯泡下，影子越拉越长",
     "接动态镜：走廊尽头的黑",
     "A dark bare room where a single hanging bulb sways very slightly: the swing drags long shadows across "
     "the wallpaper and floorboards, stretching and shrinking; an empty chair stands in the middle of the "
     "pale circle of light, and nothing else; no people, no text, the room breathing with the light. Fixed "
     "shot as the shadows slowly lengthen across the floor, " + HOLD,
     "灯口电流声 + 木头轻响"),
    ("S23", "agnes", "缓推穿过走廊，停在黑暗尽头", "走廊尽头：一排全都关着的门",
     "接 N04：被吞噬的一家人",
     "The narrow corridor of the apartment at night: sliding doors line both sides, every one of them shut, "
     "their handles pale in the half-light, and the far end of the corridor loses itself in darkness; a "
     "single hanging bulb lights the near end, the floorboards running away into the black. Very slow dolly "
     "forward down the corridor past the closed doors toward the dark end, " + HOLD,
     "极轻的地板声 + 低频持续音"),
]

SHOTS += [
    # ---------------- N04 七条人命（S24-S30：6 动态 + 1 信息卡）----------------
    ("S24", "agnes", "微距掠过照片后缓慢拉远", "桌上的家庭合影，与空掉的房间",
     "接动态镜：空房间里的椅子",
     "A desk in the apartment under a single desk lamp: a worn family photograph lies flat on the wood, but "
     "shot so close and at such an angle that it reads only as a soft blurred rectangle of light and colours "
     "with no face or feature resolvable, one corner lifted as if just set down; a pair of glasses rests "
     "beside it, folded. The camera drifts macro-close across the photograph, then rises and pulls slowly "
     "back to reveal the same room standing empty, the chair pushed in, the shelf bare, " + HOLD,
     "相纸摩擦声 + 背景音乐渐沉"),
    ("S25", "agnes", "静态长镜头缓慢推进", "空房间：椅子、窗帘、杯子里晃动的水",
     "接动态镜：夜里亮着一格灯的公寓楼",
     "An empty Japanese room in flat afternoon light: a single cushion seat sits at a low table, the curtain "
     "moves in a slow draft, and on the table a glass of water trembles in tiny rings that catch the light; "
     "dust hangs in the air, nothing else moves, no people anywhere, the room perfectly ordinary and "
     "perfectly still. Static long shot with a very slow push toward the empty seat, " + HOLD,
     "风声 + 杯子轻响"),
    ("S26", "agnes", "从街景缓慢上摇到亮灯的窗", "夜里：公寓楼亮着一格窗，街上无人抬头",
     "接动态镜：询问室里的陈述",
     "The apartment block at night seen from the street: most windows dark, one window lit on the third "
     "floor; below it an ordinary street carries on — the glow of a vending machine, a passing bicycle with "
     "its lamp, a neighbour walking a small dog — and nobody looks up; rain begins again, and the lit "
     "window's reflection stretches across the wet road. Slow tilt up from the street life to the single "
     "lit window, then hold on it, " + HOLD,
     "雨声 + 自行车驶过 + 狗链轻响"),
    ("S27", "agnes", "从少女肩后推向倾听的刑警", "询问室：她低着头，警员放下笔",
     "接动态镜：警方的时间线",
     "A small quiet Japanese interrogation room in 2002: a veteran detective {C3} sits at the far side of a "
     "plain table shown chest-up, his weathered face clearly visible, listening with his head slightly bowed, "
     "and he stops writing, setting his pen down to hear her out; on the near side of the table, seen from "
     "behind, a teenage girl in a cardigan sits hunched, only her back and the top of her head in frame, her "
     "hands gripping each other on the tabletop; a paper cup and a blank closed folder on the bare table "
     "between them. Slow push from behind the girl's shoulder across the table toward the listening "
     "detective, " + HOLD,
     "纸笔声 + 空调低鸣"),
    ("S28", "agnes", "俯拍资料桌缓慢横移", "警方把证词、时间线、关系拼在一起",
     "接动态镜：七张空白标记",
     "A police conference room in 2002: plainclothes officers with their backs to camera work along a long "
     "table, arranging closed buff folders and plain white rectangle photographs into a row, one officer "
     "sliding sheets into sequence, another pointing down the row; on the wall behind, a board carries only "
     "pinned blank cards and a single hand-drawn line, no readable text anywhere. Overhead shot of the table, "
     "slowly pushing along the laid-out row of folders as the officers work, " + HOLD,
     "翻页声 + 笔尖划纸"),
    ("S29", "agnes", "从中心缓慢拉远", "关系图完整铺开：七个空白标记",
     "接信息卡：七名死亡受害者",
     "The investigation board in the police room at night: a hand-drawn floor plan of one apartment sits at "
     "the centre of the board, and red threads run outward from it to plain blank white cards pinned in a "
     "wide arc; a gloved hand enters once, pins the last blank card into place at the end of the arc and "
     "smooths it flat, then withdraws; nothing on any card can be read, a desk lamp side-lights the board "
     "and leaves the room dark around it. Slow pull-back from the central floor plan until all seven blank "
     "cards and the whole board fill the frame, " + HOLD,
     "七次低沉音效，最后一段静默"),
    ("S30", "graphic", "信息卡（静帧）", "档案：七名死亡受害者",
     "接动态镜：沉默的房子",
     "案件档案：七名死亡受害者的认定口径",
     "低音撞击"),

    # ---------------- N05 法庭（S31-S38：6 动态 + 2 信息卡）----------------
    ("S31", "agnes", "长焦跟拍，前景人群压迫", "法院外：闪光灯下，两人被护送进法院",
     "接信息卡：漫长的审判",
     "The front steps of a Japanese district courthouse in 2003: flash bulbs pop from a crowd of journalists "
     "held behind rope barriers, their raised cameras and recorders seen from behind the line; between the "
     "shoulders, two figures in plain suits walk up the steps flanked by officers, all small in the frame, "
     "backs to camera, heads bowed, while an officer's arm shepherds them past; a cold overcast sky presses "
     "on a plain stone facade with no lettering anywhere. Long-lens compression shot with a slow pan that "
     "follows the escorted pair as they climb between the crowd's shoulders, " + HOLD,
     "相机快门 + 记者脚步声"),
    ("S32", "graphic", "信息卡（静帧）", "档案：漫长的审判",
     "接动态镜：检察官起立宣读",
     "案件档案：审判节奏与求刑",
     "低音撞击"),
    ("S33", "agnes", "从检察官缓慢横移至被告席", "检察官起立，宣读指控",
     "接动态镜：被告席上的绪方",
     "A wood-panelled Japanese district courtroom in 2004: a middle-aged prosecutor in a black suit {C4} "
     "stands at the lectern shown waist-up, his narrow serious face clearly visible as he reads aloud from a "
     "thin folder held in both hands, turning one page with a measured movement; behind him the public "
     "benches sit empty and still, the wooden railing runs along the bottom of frame, and on the far side "
     "two figures sit at the defendants' rail seen only as small out-of-focus backs; every document, seal "
     "and wall surface blank. Slow lateral move along the railing from the standing prosecutor toward the "
     "distant defendants' rail, " + HOLD,
     "法庭环境声 + 纸张翻动声"),
    ("S34", "agnes", "中景缓慢推近至紧握的双手", "被告席：绪方低着头",
     "接动态镜：松永抬起头",
     "Inside a wood-panelled Japanese courtroom, the whole shot staying indoors at the defendants' rail "
     "from the first frame to the last with no exterior, no building facade and no transition: a thin Japanese woman of forty-three {C2} sits "
     "shown chest-up behind the wooden rail, her hollow careworn face clearly visible, head bowed and eyes "
     "down, her hands folded tightly on the desk in front of her, one thumb slowly rubbing the back of the "
     "other hand; she does not look up; the courtroom behind her is still and out of focus, all papers and "
     "plaques blank. Very slow push toward her folded hands and her bowed face, " + HOLD,
     "低沉弦乐 + 远处翻页声"),
    ("S35", "agnes", "侧面缓慢推进，停在平静的脸上", "被告席：松永抬起头，表情没有变化",
     "接动态镜：法官翻开判决书",
     "Inside a wood-panelled Japanese courtroom at the defendants' rail, the whole shot staying indoors "
     "from the first frame to the last with no exterior, no building facade and no transition: the lean Japanese man visibly in his early forties with smooth unlined skin — not elderly, no deep wrinkles, no grey hair — {C1} sits shown chest-up behind "
     "the rail, and he slowly raises his head to face forward — his faint composed polite smile unchanged, "
     "his level gaze steady and unhurried, blinking once, hands resting open and still on the desk; the "
     "overhead light is cold, the empty public benches soft behind him, every surface blank. Slow lateral "
     "drift from the empty bench beside him across to his raised calm face, and hold, " + HOLD,
     "法庭回声 + 低频氛围音"),
    ("S36", "agnes", "判决书特写缓慢上摇至法官", "宣判：法官翻开判决书",
     "接动态镜：法院建筑的冷调",
     "A Japanese courtroom at the moment of judgment in 2005: a judge of around sixty in black robes {C5} "
     "stands behind the high wooden bench shown waist-up in the centre of the frame, his grave face clearly "
     "visible, lifting a single blank sheet with both hands as he reads aloud, his mouth moving steadily, "
     "then lowering the sheet to the bench and squaring his shoulders; the courtroom below is motionless, "
     "every seal, sheet and wall plaque blank. Slow push from the blank sheet in his hands up to his grave "
     "face, then hold on his stillness, " + HOLD,
     "纸张声 + 法槌轻响 + 音乐短暂停顿"),
    ("S37", "agnes", "低机位缓慢拉远", "法院建筑：冷色调，时间向前走",
     "接信息卡：判决时间线",
     "The same courthouse facade in flat grey light across a wide empty forecourt: low cloud moves quickly "
     "over the stone building, light rain begins to streak the frame and bead on the wet flagstones, which "
     "mirror the grey facade; a single umbrella crosses the far edge of the frame; the building carries no "
     "lettering, clock face or emblem. Low wide shot very slowly pulling back and down from the steps until "
     "the courthouse stands small against the moving sky, " + HOLD,
     "风声 + 低音弦乐"),
    ("S38", "graphic", "信息卡（静帧）", "档案：判决时间线",
     "接 N06：拘置所的高墙",
     "判决时间线：一审 / 二审 / 终审",
     "低音撞击"),

    # ---------------- N06 没有铁栏的牢笼（S39-S45：6 动态 + 1 信息卡）----------------
    ("S39", "agnes", "低机位沿墙根缓慢横移", "拘置所的高墙：刑期已定，人在墙里",
     "接信息卡：没有铁栏的牢笼",
     "The high concrete perimeter wall of a Japanese detention facility in hard morning light: frost lies on "
     "the bare ground along the wall base, a watchtower stands in silhouette at the far corner with a single "
     "crow on the wire above, and the wall runs unbroken across the whole frame with no signage, number or "
     "emblem anywhere; the camera stays at ground level, small against the wall. Slow low lateral move along "
     "the frost line at the base of the wall toward the distant watchtower, " + HOLD,
     "风声 + 铁丝网轻响"),
    ("S40", "graphic", "信息卡（静帧）", "档案：没有铁栏的牢笼",
     "接动态镜：阳光如常的公寓",
     "案件档案：本案的本质",
     "低音撞击"),
    ("S41", "agnes", "缓慢穿过客厅，停在紧闭的门前", "回到公寓：阳光落下，一切如常",
     "接动态镜：黑暗里的门缝",
     "The same small Japanese apartment in daylight: the main room stands tidy and ordinary — the low table "
     "wiped clean, cushions squared, a curtain half open laying a clean stripe of sun across the tatami, a "
     "kettle sitting cold on the gas ring in the kitchenette; nothing disturbed, nothing strange, no people "
     "anywhere, only the hum of the refrigerator. Slow forward tracking shot through the rooms as if walking "
     "from the entrance toward the far end of the apartment, slowing to a stop before a closed sliding door, "
     + HOLD,
     "风声 + 远处街道的生活噪声"),
    ("S42", "agnes", "黑暗中极缓推近门缝", "黑暗里：一扇门的轮廓，门缝透出微光",
     "接动态镜：更空的房间",
     "Total darkness: the faint rectangular outline of a closed door emerges as a thin blade of light glows "
     "along its edge and beneath it, dust drifting slowly through the lit slit; nothing else is visible in "
     "the room, and once, faintly, the light trembles as if something far away shifted its weight. Extremely "
     "slow push toward the lighted door gap until the thin blade of light fills the lower third of the "
     "frame, " + HOLD,
     "一声轻微门响，随后接近静音"),
    ("S43", "agnes", "从空桌缓慢拉回黑暗", "更空的房间：连最后一只坐垫也拿走了",
     "接动态镜：结尾的城市清晨",
     "Inside the dining corner of a small Japanese apartment, the whole shot staying indoors in this one "
     "room from the first frame to the last with no exterior, no street, no snow and no transition, deep in the last light of day: the low table stands "
     "square and empty, the cushion seats gone from around it, the shelf bare where the turned-down "
     "photograph stood; the room is almost empty now, the light failing at the window. Slow pull back from "
     "the empty table into the darkening room until the table is small in the frame, " + HOLD,
     "极静 + 一声远处钟响"),
    ("S44", "agnes", "远景缓慢拉远并抬升", "城市醒来：生活继续，名字不该被抹掉",
     "接动态镜：晨光里的一枝白花",
     "A wide first-light view over Kokurakita ward of Kitakyushu from a high hill on the edge of the city: "
     "low-rise apartment blocks and tiled roofs spread below under a pale dawn sky, the industrial bay faint "
     "in haze at the far edge, a monorail line and a river bridge catching the first light, thin mist lying "
     "in the streets, a single street lamp still burning on the nearest road; the frame holds no people, no "
     "signage and no lettering. Very slow aerial pull-back and rise from the nearest rooftops to the whole "
     "city and the hills beyond, " + HOLD,
     "弦乐渐强后收束"),
    ("S45", "agnes", "静物长镜头缓慢横移", "最后的致意：晨光里的一枝白花",
     "接片尾卡",
     "A plain wooden shelf in a bare Japanese room in clear morning light: a single white flower stands in a "
     "simple glass of water, and opposite it a small round wall mirror catches the sun and throws a bright "
     "shape onto the floorboards; the room is otherwise empty and swept, the curtain drawn wide, stillness "
     "and dignity, no people anywhere. Slow lateral move along the shelf from the bright mirror shape to the "
     "white flower, " + HOLD,
     "微弱晨风 + 一声远处鸟鸣"),
]

CARD_HEADER = "案件档案  /  日本北九州 · 一九九六至二〇〇二"      # 每张信息卡左上角的小字
CARD_FOOTER = "公开报道口径 · 并非原始档案影像"                    # 每张信息卡左下角的小字
# 信息卡文案：镜头号 -> (大标题, 第一行, 第二行)。只写公开报道里的事实，不写推测。
CARDS = {
    "S02": ("北九州监禁杀人案", "日本福冈 · 一九九六至二〇〇二", "一间普通公寓 · 七人遇难 · 一名少女逃出求救"),
    "S10": ("两名被告", "松永太 · 一九六一年生 · 案发时四十岁", "绪方纯子 · 松永的内缘妻子 · 案发时四十岁出头"),
    "S17": ("一九九六 — 一九九八", "监禁 · 虐待 · 控制", "死亡接连发生 · 外界几乎一无所知"),
    "S30": ("七名死亡受害者", "大多为绪方纯子的家人 · 包括两名孩子", "六起认定为谋杀 · 一起认定为伤害致死"),
    "S32": ("漫长的审判", "二〇〇三年十月开庭 · 每周开庭一次", "二〇〇五年三月 · 检方请求死刑"),
    "S38": ("判决时间线", "二〇〇五年九月二十八日 一审 双双死刑", "二〇〇七年 绪方改判无期 · 二〇一一年十二月 死刑确定"),
    "S40": ("没有铁栏的牢笼", "恐惧 · 谎言 · 被剥夺的选择", "最长的一间 · 关了六年"),
}
# 片头字幕卡（0.35–4.7 秒叠在第一镜上）：两行，第二行小字
TITLE_CARD = ["北九州监禁杀人案", "逃出魔窟的少女 · 七条人命 · 日本 1996—2002"]
# 片尾卡（最后 3.8 秒）：大字提问 / 一行案件信息 / 一行金句 / 一行资料来源
END_CARD = [
    "如果是你，敢在那种恐惧里开口吗？",
    "北九州监禁杀人案 · 一九九六至二〇〇二 · 七人遇害",
    "最黑暗的牢笼没有铁栏：它由恐惧、谎言和被剥夺的选择构成。",
    "资料：维基百科 / 文春在线 / 日本经济新闻 / 最高裁判所 · 原创解说 · AI动画情景重现",
]
# 字幕里描黄的关键词（人名、数字、结论词）
CAPTION_KEYWORDS = [
    "北九州", "十七岁", "祖父", "松永太", "绪方纯子", "内缘妻子", "第二天", "七条人命",
    "九十年代", "诈骗", "债务", "谎言", "威胁", "经济压力", "工具", "一九九六年",
    "一九九八年", "监禁", "虐待", "恐惧", "绝境", "求救", "七名", "两名孩子",
    "六起", "谋杀", "伤害致死", "二〇〇三年十月", "每周开庭", "支配", "二〇〇五年九月",
    "死刑", "无期徒刑", "二〇一一年十二月", "确定", "六年", "日常", "没有铁栏的牢笼",
    "七条生命",
]
# 逐镜标签覆盖：默认镜头标「AI动画情景重现 · 非新闻影像」，办案/审讯/庭审镜头写得更具体
LABEL_OVERRIDES = {
    "S01": "AI动画情景重现 · 非新闻影像",
    "S03": "AI动画情景重现 · 非新闻影像",
    "S04": "AI动画情景重现 · 非求助现场影像",
    "S05": "AI动画情景重现 · 非警方搜查影像",
    "S06": "AI动画情景重现 · 非抓捕影像 · 非本人容貌",
    "S07": "AI动画情景重现 · 非警方办案影像",
    "S08": "AI动画情景重现 · 非案发房间影像",
    "S09": "AI动画情景重现 · 非本人容貌",
    "S11": "AI动画情景重现 · 非本人容貌",
    "S12": "AI动画情景重现 · 非档案影像",
    "S13": "AI动画情景重现 · 非本人容貌",
    "S14": "AI动画情景重现 · 非受害家庭影像",
    "S15": "AI动画情景重现 · 非案发房间影像",
    "S16": "AI动画情景重现 · 非案发影像",
    "S18": "AI动画情景重现 · 非案发影像 · 非本人容貌",
    "S19": "AI动画情景重现 · 非案发影像",
    "S20": "AI动画情景重现 · 非案发影像",
    "S21": "AI动画情景重现 · 非案发影像",
    "S22": "AI动画情景重现 · 非案发影像",
    "S23": "AI动画情景重现 · 非案发房间影像",
    "S24": "AI动画情景重现 · 非证物影像",
    "S25": "AI动画情景重现 · 非案发房间影像",
    "S26": "AI动画情景重现 · 非实景影像",
    "S27": "AI动画情景重现 · 非询问影像 · 少女非本人容貌",
    "S28": "AI动画情景重现 · 非警方办案影像",
    "S29": "AI动画情景重现 · 非警方办案影像",
    "S31": "AI动画情景重现 · 非押解影像 · 非本人容貌",
    "S33": "AI动画示意 · 非庭审影像",
    "S34": "AI动画示意 · 非庭审影像 · 非本人容貌",
    "S35": "AI动画示意 · 非庭审影像 · 非本人容貌",
    "S36": "AI动画示意 · 非庭审影像",
    "S37": "AI动画情景重现 · 非实景影像",
    "S39": "AI动画情景重现 · 非拘置所实景",
    "S41": "AI动画情景重现 · 非案发房间影像",
    "S42": "AI动画情景重现 · 非案发影像",
    "S43": "AI动画情景重现 · 非案发房间影像",
    "S44": "AI动画情景重现 · 非实景航拍",
    "S45": "AI动画情景重现 · 非实景影像",
}
# 合成音效事件：(镜头号, 类型)，类型可选 paper / phone / keys / machine / press，落在该镜开始前 0.18 秒
SFX_EVENTS = [
    ("S05", "keys"),
    ("S07", "paper"),
    ("S12", "paper"),
    ("S14", "keys"),
    ("S16", "machine"),
    ("S28", "paper"),
    ("S29", "press"),
    ("S31", "press"),
    ("S33", "paper"),
    ("S36", "press"),
]

# ---------------------------------------------------------------------------
# 发布文案（抖音脚本.md / 抖音发布文案.md 用）
# ---------------------------------------------------------------------------
TITLES = [
    "日本北九州监禁案：少女两次逃跑，第二次才有人信她，背后是七条人命",
    "一间再普通不过的公寓，六年吞掉七个人，直到那个少女深夜逃了出去",
    "他用谎言和恐惧筑了一座没有铁栏的牢笼：北九州监禁杀人案全解",
]
HOOK = ("一九九六到二〇〇二年，日本北九州一间普通公寓里，七个人再也没有出来，其中两名还是孩子。"
        "二〇〇二年三月，一名十七岁少女深夜逃出、跑到祖父家求助，第二天警方逮捕了松永太和绪方纯子——"
        "一场以恐惧、谎言和经济控制维系的六年监禁，就此曝光。")
GOLDEN_LINES = [
    "最黑暗的牢笼没有铁栏：它由恐惧、谎言和被剥夺的选择构成。",
    "她逃出去过一次，被抓了回来；第二次，终于有人相信了她。",
    "六年的恐怖，就藏在最普通的公寓里。",
]
DESCRIPTION = (
    "一九九六年到二〇〇二年，日本北九州小仓北区一间普通公寓里，松永太与内缘妻子绪方纯子"
    "监禁、控制了绪方的家人等多名受害者，七人死亡，其中包括两名孩子。"
    "二〇〇二年三月，一名十七岁少女逃出求救，案件曝光；二〇〇五年九月一审双双死刑，"
    "二〇〇七年二审改判绪方无期徒刑，二〇一一年十二月最高裁终审确定。"
    "本片画面为AI生成的情景重现（非新闻影像、非本人容貌），事实依据公开报道整理。"
)
QUESTION = "如果是你，被恐惧困住的时候，敢不敢成为第一个开口求助的人？评论区聊聊。"
HASHTAGS = ["#悬疑", "#真实案件", "#日本", "#案件解说", "#犯罪心理"]

GRID = 4            # 规划网格：每镜 4 秒，45 镜 = 180 秒
AGNES_SECONDS = 6   # 每个镜头实际请求的时长（智谱 CogVideoX-Flash 免费档单条约 5–6 秒，render 按需裁切）
SEED_BASE = 20020306  # 少女逃脱日（二〇〇二年三月六日），让 seed 可追溯

# 露脸镜头登记（镜头号 -> 角色 id）：只有这里登记的镜头允许出现面容 token，
# 与 cast.json 的 shots 映射一一对应（face_cast.py check-prompts 两边都查）。
FACE_SHOTS = {
    "S07": ["C3"],
    "S09": ["C1"],
    "S27": ["C3"],
    "S33": ["C4"],
    "S34": ["C2"],
    "S35": ["C1"],
    "S36": ["C5"],
}
REFERENCE_SHOTS = {}   # 本片不走定妆照图生视频（免费档 image_url 队列拥堵，模板实测一条收据磨一小时）
FIRST_FRAME = {}       # 同上：跨镜脸一致性靠面容 token + seed，最终由 face_cast 画面闸门和人眼复核


def first_frame_urls():
    base = "https://raw.githubusercontent.com/32r4e2q-hub/desktop-tutorial/arena/44a8fff6-desktop-tutorial/production/kitakyushu2002/"
    return {sid: base + rel for sid, rel in FIRST_FRAME.items()}


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
    extra_frames = first_frame_urls()
    missing_frames = [sid for sid in FIRST_FRAME if not (HERE / FIRST_FRAME[sid]).is_file()]
    assert not missing_frames, f"这些自定义首帧图不存在：{missing_frames}"
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
        if kind != "graphic":
            for cid, token in face.items():
                prompt = prompt.replace("{" + cid + "}", token)
            assert "{" not in prompt and "}" not in prompt, f"{sid} 提示词里还有没替换的占位符"
        shot = {
            "id": sid, "kind": kind, "start": start, "duration": GRID,
            "narration_id": f"N{min(6, start // 30 + 1):02d}",
            "prompt": prompt if kind != "graphic" else "",
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
        if sid in extra_frames:
            shot["reference_image"] = extra_frames[sid]
        shots.append(shot)
    story["shots"] = shots
    story["presentation"] = presentation()
    story.setdefault("_scaffold", {})["note"] = (
        "内容由 build_story.py 一次性写入；45 镜 × 4 秒规划网格（每镜只用一次）；"
        "露脸模式：面容 token 只在 cast.json 里写一份，build_story.py 用占位符注入，保证逐字节一致；"
        "视频模型走智谱 CogVideoX-Flash 免费档（generate_cogvideox.py）；"
        "解说词与 screenplay.md、audio/manifest.json 三处逐字一致由 generate.py --validate 守着。")
    PLAN.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n")

    manifest = json.loads(MANIFEST.read_text())
    for clip, chapter in zip(manifest["clips"], story["chapters"]):
        assert clip["id"] == chapter["id"]
        clip["text"] = chapter["text"]
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    kinds = [s["kind"] for s in story["shots"]]
    chars = sum(len(c["text"]) for c in story["chapters"])
    print(f"story.json 已写入：{len(shots)} 镜 = {kinds.count('agnes')} cogvideo + {kinds.count('graphic')} graphic，"
          f"解说 {chars} 字（含标点）")
    print("逐章字数：" + " / ".join(f"{c['id']} {len(c['text'])}" for c in story["chapters"]))
    print(f"露脸镜头：{len(FACE_SHOTS)} 镜；首帧图钉脸：{len(FIRST_FRAME)} 镜")
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
        from script_table import publish_document  # noqa: E402
        out = HERE / "抖音发布文案.md"
        out.write_text(publish_document())
        print(f"抖音发布文案.md 已写入（{len(out.read_text())} 字符）")
    else:
        build()
