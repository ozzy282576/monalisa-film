#!/usr/bin/env python3
"""《六十四格：国际象棋盘杀手》的唯一内容源：六段旁白、38个视频提示词、7张卡片与发布文案。

用法：
  python3 production/chessboard64/build_story.py
  python3 production/chessboard64/build_story.py --script
  python3 production/chessboard64/build_story.py --publish

每条视频提示在 generate_cogvideox.py 中按「STYLE + 角色设定 + 镜头提示 + NEGATIVE」组装；
信息卡由 Pillow/FFmpeg 后期排字，不让视频模型生成中文文字。全片 45 个时间格 × 4 秒，
38 个真实动态视频源 + 7 张信息卡；结尾卡占用 S45，不额外插入第八张卡。
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "story.json"
MANIFEST = HERE / "audio" / "manifest.json"
TITLE = "六十四格：国际象棋盘杀手"
FILM = "六十四格_国际象棋盘杀手_三分钟_带声音.mp4"
BRANCH = "arena/56672981-monalisa-film"

# 用户给定的全局视觉规则；只用于模型提示，不把文字直接烧进视频源素材。
STYLE_PREFIX = (
    "【STYLE】 High-end cinematic 3D animated documentary reenactment; fictional composite cast; early-2000s "
    "Moscow and Bitsa forest park in autumn. Restrained gray-green and deep navy, black-and-white chess squares "
    "with subtle red marks as a recurring metaphor; chiaroscuro, volumetric mist, wet leaves, tactile stone, aged "
    "wood and cloth, shallow depth of field, fine 35mm grain. Solemn, non-sensational tone. Horizontal 16:9 for "
    "1920x1080 delivery; use the full widescreen frame, place subjects on thirds, keep the bottom 15% subtitle-safe. "
    "Every shot must show continuous real 3D subject/environment/camera motion; never a still with a fake zoom. "
    "All people are anonymous fictional stand-ins with indistinct faces; witnesses and affected people appear "
    "only from behind or as silhouettes. No readable text; add Chinese graphics and captions in post."
)

NEGATIVE_PROMPT = (
    "【NEGATIVE】 No legible text, numbers, signs, watermarks, logos or subtitles; no recognizable real-person "
    "likeness, distorted faces/fingers/limbs, duplicate figures, nudity, modern devices, low resolution, "
    "2D/comic style, vertical framing or bars, static still/slideshow/fake push-in, flicker, morphing, "
    "jitter, jump cuts or whip pans."
)

# 角色设定由视频生成器自动前置到出现对应角色的每一条提示词。
CHARACTER_SETTINGS = {
    "MAIN_FIGURE": "Fictional anonymous slim man in his early 30s, short dark hair, plain charcoal jacket or early-2000s supermarket vest; ordinary posture, face indistinct, seen from behind or as a distant silhouette.",
    "WOMAN_COWORKER": "Fictional adult woman about 36, shoulder-length chestnut hair, pale coat, gentle everyday posture; face indistinct, shown from behind or in silhouette.",
    "SON": "Fictional teenage boy with dark hair and simple home clothes; seen from behind or as a soft silhouette, face indistinct.",
    "ELDER": "Anonymous older man in a modest dark coat and cap; distant back or soft silhouette, dignified and ordinary.",
    "INVESTIGATOR": "Anonymous early-2000s Moscow investigators in generic dark blue-gray clothing; blank insignia, indistinct faces, calm professional posture.",
    "WITNESS": "Fictional adult woman witness in a simple 2002 coat; shown only from behind or as a silhouette, composed and dignified.",
    "DOG": "Small brown-and-white short-haired mixed-breed dog on a simple leash; natural gentle movement.",
    "PARK_VISITORS": "Ordinary anonymous park visitors of varied ages; everyday behavior, faces distant, turned away or indistinct.",
    "JURY": "Anonymous fictional Moscow jurors in modest 2000s clothes; seated quietly, distant indistinct faces.",
    "COURT_OFFICIAL": "Anonymous judge or court clerk in restrained formal clothes; back or distant silhouette, blank insignia, unreadable papers.",
    "RELATIVES": "Fictional family members, dignified and anonymous; quiet backs or distant silhouettes, never melodramatic.",
}

PRINCIPLES = [
    "38个动态镜头均由智谱 CogVideoX-Flash 生成真实运动的3D动画片段；七张卡片为程序化排版，不以静帧推拉冒充动态镜头。",
    "所有人物均为风格化虚构替身，不还原真实肖像；受害者与幸存者只以背影、剪影或手部出现。",
    "全片不出现武器、遗体、伤口、血腥或暴力过程；危险与失踪只用空椅、纸条、棋盘、雨夜和公园空间隐喻。",
    "六十四格上的红色记号是本片的视觉隐喻，不宣称是警方原始证物的精确复刻。",
    "六十三是皮丘什金的自述/媒体报道中的声称；法院最终定罪为四十八起谋杀及三起未遂，二者不能混为一谈。",
    "二〇〇二年幸存者报案未获有效跟进，按公开报道表述，不把警员责任争议包装成已由本片独立核实的司法结论。",
    "成片中文字幕、卡片文字和标签由后期生成；提示词禁止模型写字、商标、字幕或水印。",
    "旁白逐句制作字幕，白字黑边，关键词金色高亮；旁白目标语速约每秒三点七字，‘几乎被填满’与‘一张纸条’后留约零点五秒停顿。",
    "每镜严格按 S01–S45 顺序只用一次；镜头时长按真实配音分句切点调整，目标总长一百八十秒。",
    "故事落点是受害者与证据，不把罪犯塑造成传奇；所有事实表述均对应史实核对文件中的公开来源。",
]

SOURCES = [
    {"id": 1, "url": "https://www.reuters.com/article/economy/russian-chessboard-killer-convicted-of-48-murders-idUSL24156208/",
     "usage": "Reuters，2007-10-24：陪审团认定48起谋杀、3起未遂；交代64格棋盘说法、比察公园及受害者背景。"},
    {"id": 2, "url": "https://www.reuters.com/article/world/russias-chessboard-killer-given-life-in-prison-idUSL29351467/",
     "usage": "Reuters，2007-10-29：终身监禁；63人是其本人声称，控方起诉并获定罪的是48起谋杀、3起未遂。"},
    {"id": 3, "url": "https://news.bbc.co.uk/2/hi/europe/7059939.stm",
     "usage": "BBC，2007-10-24：48起谋杀、3起未遂、比察公园、媒体称号及其自述人数口径。"},
    {"id": 4, "url": "https://www.nbcnews.com/id/wbna21462233",
     "usage": "Associated Press/NBC，2007-10-25：63人为其声称，陪审团认定48起谋杀及3起未遂。"},
    {"id": 5, "url": "https://www.theguardian.com/world/2007/aug/14/russia.lukeharding1",
     "usage": "The Guardian，2007-08-14：他在公园下棋、超市工作、同事玛丽娜、纸条/地铁票/监控线索与2006年6月逮捕经过；并提醒其自述规模不等于可证事实。"},
    {"id": 6, "url": "https://www.theguardian.com/world/2007/oct/25/russia.international",
     "usage": "The Guardian/AP，2007-10-25：48起谋杀定罪、3起未遂、63人为其声称，以及警方逮捕线索。"},
    {"id": 7, "url": "https://www.theguardian.com/world/2007/oct/29/russia.haroonsiddique",
     "usage": "The Guardian，2007-10-29：终身监禁及定罪口径。"},
    {"id": 8, "url": "https://www.gq.com/story/alexander-pichushkin-serial-killer-russia",
     "usage": "GQ，2009-05-01：2002年幸存者报告经历、线索未获有效追查的媒体叙述；本片用‘公开报道指出’并保留归因。"},
    {"id": 9, "url": "https://www.oklahoman.com/story/news/2007/10/29/life-in-prison-for-russian-serial-killer/61683024007/",
     "usage": "Associated Press/The Oklahoman，2007-10-29：幸存者报告后警方未能及时跟进，以及相关警员接受调查的报道。"},
    {"id": 10, "url": "https://www.nytimes.com/2007/10/30/world/europe/30serial.html",
     "usage": "The New York Times，2007-10-30：48起定罪、3起未遂、63人自述、2006年同事留下的纸条。"},
    {"id": 11, "url": "https://www.reuters.com/world/europe/russias-chessboard-killer-ready-confess-11-more-murders-penal-service-says-2025-04-05/",
     "usage": "Reuters，2025-04-05：后续报道他表示愿意承认另外11起案件；属于后续自述，并非2007年法院判决，本片仅在史实核对中注明。"},
]

CHAPTERS = [
    ("N01", "开场：六十四格",
     "他常在公园和人下棋，看起来像个普通棋友。可他盯上的是一块六十四格的棋盘。媒体给他起了一个绰号，六十四格的说法来自他的自述，并非司法结论。二〇〇七年法院认定四十八起谋杀和三起未遂。他曾声称目标是填满六十四格。我们只谈证据，也记住格子背后的人。"),
    ("N02", "比察公园里的棋友",
     "亚历山大·皮丘什金，三十三岁时在莫斯科受审。成年后他在超市做理货员。下班后他常去莫斯科南部的比察公园。那里有石桌和长椅，常有人停下来下棋。公开报道说，他会邀陌生人喝酒，理由是悼念死去的小狗。人们只当他是熟悉的棋友。他声称留下六十三个记号，按他的说法，棋盘几乎被填满。"),
    ("N03", "幸存者报告与一张纸条",
     "二〇〇二年公开报道记载，一位女性幸存者曾向警方报告遭遇。报道指出这条线索当时没有得到及时跟进。我们不补写她的经历。多年后超市同事玛丽娜与他约好散步。出门前，她留下一张纸条，写下同行者的姓名和电话。离开后儿子等着，电话始终没有响。"),
    ("N04", "纸条、地铁票与监控",
     "警方发现她衣袋里的地铁票。车站监控显示，两人曾经同行。纸条、票据、影像，三条线索彼此核对。这里的画面不是警方原始证物。调查从一张小票开始，回到比察公园。沿着路线，警方逐步锁定熟悉的同事。每一条证据，都需要与下一条相互印证。"),
    ("N05", "逮捕与法庭认定",
     "二〇〇六年六月十六日，皮丘什金被捕。公开报道说，警方在他住处找到与棋盘记号相关的证物。二〇〇七年十月，陪审团认定四十八起谋杀、三起未遂。法院随后判处终身监禁。六十三，是他的自述，不是法院认定。法庭结论来自证据。每个数字，都要说明来源。"),
    ("N06", "判决之后：记住他们",
     "法律结论写在案卷里，受害者却不是数字。每一格背后，都是一个真实的人，也是一个失去亲人的家庭。留下的沉默，同样值得被看见。我们不重现伤害，也不把凶手变成传奇。让棋盘回到公园石桌上。树影移动，行人继续生活。记住他们。"),
]

# 每条镜头：(kind, purpose, camera, prompt, characters, sound cue)。提示词只写本镜头独有内容。
# kind=cogvideo 时会真正调用 CogVideoX-Flash；kind=graphic 时由后期排字。
SHOTS = [
    ("cogvideo", "黑白棋盘由暗到明，红色微光逐格出现", "高位俯拍，缓慢下降并略向右滑行",
     "An enormous real three-dimensional black-and-white chessboard fills a dark soundstage. Fine red pinpricks of light travel across several squares in a measured sequence while low mist drifts between the raised tiles. The camera physically descends toward the board and glides laterally; the glowing markers reflect on polished stone. Continuous motion from first frame to last, one location, no text.", [], "chess"),
    ("cogvideo", "棋盘格化为莫斯科秋日公园小径", "贴近棋盘穿行，顺势前推",
     "At ground level, the camera moves between oversized chess squares; their black-and-white stone edges gradually become wet paving stones and windblown orange leaves without a hard cut. The path opens into a broad Moscow forest park in autumn, where a distant anonymous man waits at a stone chess table. Leaves keep moving in the wind throughout the transition, a single continuous 3D animated move.", ["MAIN_FIGURE", "PARK_VISITORS"], "leaves"),
    ("graphic", "片名卡：六十四格与案件地点年代", "信息卡；棋盘边缘金色微光移动",
     "TITLE CARD — 六十四格：国际象棋盘杀手 / 莫斯科·比察公园 / 2000年代历史案件。程序化排字，勿交给视频模型。", [], "chess"),
    ("cogvideo", "社区超市里整理货品的日常", "中景侧面跟拍，货架形成纵深",
     "Inside a modest neighborhood supermarket in early-2000s Moscow, an anonymous slim worker in a plain vest lifts a small carton, places it carefully on a shelf, checks the row and walks two steps to straighten another item. A coworker passes and nods; cold fluorescent tubes hum overhead, shoppers move softly in the far background. Smooth side-tracking camera, visible natural movement, no brand labels or readable packaging.", ["MAIN_FIGURE", "PARK_VISITORS"], "machine"),
    ("cogvideo", "牵着棕白小狗走进秋日公园", "低机位跟拍，逆光穿过树叶",
     "On a leaf-covered path in Bitsa Park at late afternoon, a small brown-and-white dog trots ahead on a loose leash while an anonymous slim man walks steadily behind it. Golden light filters through moving branches; a pair of elderly chess players sit far away at a stone table. The dog sniffs a leaf, turns, then continues; the camera tracks low beside them with true parallax and continuous motion.", ["MAIN_FIGURE", "DOG", "ELDER"], "leaves"),
    ("cogvideo", "石桌上的黑白棋子与落子", "棋盘高度缓慢横移",
     "Close low view across a worn stone chess table in the autumn park. Two anonymous hands enter from opposite sides; one hand slides a dark chess piece to a new square while the other gently steadies a light piece, leaves drift across the far edge and sunlight slowly shifts over the board. Keep the players' faces outside frame, show tactile stone and wood, one continuous lateral camera move.", ["MAIN_FIGURE", "ELDER"], "chess"),
    ("cogvideo", "平和公园全景中的散步与棋局", "广角缓慢下降并在人群后方停住",
     "Wide aerial-to-eye-level move over an ordinary Moscow forest park on a cool autumn day: walkers cross the broad frame, a small ice-cream cart rolls slowly along the path with a completely blank canopy, older visitors sit on benches, and chess players move pieces at stone tables. The camera descends smoothly and settles behind one anonymous man among the visitors; no one looks into camera, no signs or text.", ["MAIN_FIGURE", "PARK_VISITORS", "ELDER"], "wind"),
    ("cogvideo", "棋盘上的标记延伸成公园路径隐喻", "围绕棋盘缓慢环绕",
     "A symbolic 3D chessboard rests on a dark desk; several restrained red markers glow one after another, and the grid's outer lines extend into thin paths resembling a park map. A hand turns the board a few degrees while the camera makes a slow overhead orbit. This is an editorial metaphor, not a replica of evidence; no letters, dates or readable marks.", [], "heartbeat"),

    ("cogvideo", "昏暗书桌上绘制棋盘记号", "缓慢推近手与笔记本",
     "Night inside a cramped Moscow apartment. A plain desk lamp illuminates an open blank notebook with a hand-drawn 8-by-8 chess grid; an anonymous man's hand moves a red pencil and adds one small abstract mark, then pauses. His side silhouette remains half in shadow, never a clear portrait. The page contains only geometric squares, no letters or numbers; slow deliberate push toward the notebook.", ["MAIN_FIGURE"], "paper"),
    ("graphic", "数字卡：六十四格自述与司法认定的区别", "信息卡；红色标记由虚转实",
     "FACT CARD — 64格：他的目标说法 / 63：本人曾声称 / 48起谋杀 + 3起未遂：法院认定。明确区分自述与定罪。程序化排字。", [], "chess"),
    ("cogvideo", "悬浮棋盘逐渐显出林间路径", "环绕俯拍，缓慢下沉",
     "A large black-and-white chessboard floats above a dark forest floor. Selected squares brighten as a subtle red line traces an abstract network of park paths between them; drifting mist passes behind the board and branches sway below. The camera circles overhead and slowly lowers, showing real depth and parallax. No numbers, names or claim that the pattern is an actual map.", [], "heartbeat"),
    ("cogvideo", "黄昏公园入口搭话的剪影", "中景缓慢前推，背景虚化",
     "At a quiet park entrance at dusk, an anonymous slim man in a dark jacket speaks with an older visitor seen only from behind. He gestures gently toward a path and offers a small unbranded paper cup; the older man hesitates, then gives a slight nod. Both figures remain calm and unhurried; the trees and fallen leaves move in a light wind.", ["MAIN_FIGURE", "ELDER"], "wind"),
    ("cogvideo", "两道背影沿小路走远", "固定机位，树叶前景掠过",
     "From the park entrance, two distant anonymous figures walk side by side along a leaf-strewn path into the trees. A few leaves cross the foreground and the figures gradually disappear behind trunks while the camera remains still; branches continue to sway. The figures stay separate and distant, with faces hidden; hold the empty path after they pass.", ["MAIN_FIGURE", "ELDER"], "leaves"),
    ("cogvideo", "空长椅与遗落的棋子", "低角度缓慢拉远",
     "An empty park bench beside a stone chess table after sunset. A single black chess piece rocks gently in the breeze and settles on its side; leaves slide across the paving while distant visitors pass as soft silhouettes. The camera slowly pulls backward, revealing the quiet empty space around the table in a restrained, respectful composition.", ["PARK_VISITORS"], "wind"),
    ("cogvideo", "被填满的不是分数而是空座位", "由高位缓慢下降至棋盘与长椅",
     "A slow overhead view of a stone chess table in an almost empty park. The checker pattern briefly overlays the paving, then the red markers fade while several empty benches remain in view; a few ordinary visitors walk beyond the trees. The camera descends and settles at table height, changing the metaphor from tally to remembrance; visitors remain ordinary people in the distance.", ["PARK_VISITORS"], "wind"),

    ("cogvideo", "超市休息室里同事交谈", "中景过肩，暖光下轻轻横移",
     "In a modest early-2000s supermarket break room, an anonymous woman with chestnut shoulder-length hair in a light coat sits across from a slim male coworker. Two cups of tea steam gently; she smiles faintly and nods while he listens. Both are shown from behind or soft side silhouette, no clear faces. The camera drifts over the table as fluorescent light softens into warm lamp glow.", ["MAIN_FIGURE", "WOMAN_COWORKER"], "paper"),
    ("cogvideo", "母亲留下纸条并与儿子告别", "中景缓慢推向桌面纸条",
     "Inside a small Moscow apartment at sunset, an anonymous woman in a pale coat writes a few abstract unreadable strokes on a small paper note, folds it once and places it beside a cup; her teenage son stands behind her and gives a quiet nod. Both faces remain unseen, the curtain shifts in the window breeze, warm lamp against cool evening light, one continuous camera push.", ["WOMAN_COWORKER", "SON"], "paper"),
    ("graphic", "线索卡：2002年幸存者报案与跟进不足", "信息卡；红线中途断开后再延伸",
     "FACT CARD — 2002年：一名幸存者报告遭遇 / 公开报道：线索未获有效跟进 / 具体责任按报道归因，不作超出来源的断言。程序化排字。", [], "paper"),
    ("cogvideo", "纸条留在桌上两人走出门", "桌后低位向门口平稳推进，全程只见背影",
     "A restrained, clearly fictional 3D reenactment in a modest Moscow apartment, filmed from low behind a table. A folded blank note stays sharp in the foreground. Beyond it, an adult woman in a pale coat and a slim man in a dark jacket walk away from the camera through the doorway; both are shown strictly from behind, and their heads remain turned away for the entire shot. A teenage boy stays inside near the doorway, also facing away, with his head hidden behind the doorframe. The door eases toward closing as a curtain moves in the window breeze. The camera makes one smooth physical dolly from the note toward the doorway without passing or orbiting around anyone. No face, profile, reflection, mirror, head turn, readable writing, flicker, or sudden movement; this is an illustrative reconstruction, not original footage.", ["WOMAN_COWORKER", "SON", "MAIN_FIGURE"], "paper"),
    ("cogvideo", "儿子等待而电话没有响", "近景从电话缓慢移至背影",
     "At night in the same small apartment, a teenage boy sits on a sofa with a folded blank note in his hands. A corded landline phone rests silent on a side table; the boy looks toward the dark window, shoulders slowly tightening as the room's old lamp flickers softly. The camera slides from the phone to his back, no readable paper, no distress close-up.", ["SON"], "phone"),
    ("cogvideo", "地铁票与棋盘形成匹配剪辑", "微距横移，焦点从票移到棋格",
     "On a police desk, an old paper metro ticket with no readable print lies beside a folded blank note and a small black chess piece. A gloved investigator's hand aligns the ticket with a red thread leading to one square on a chessboard diagram; dust moves in the desk-lamp beam as the camera tracks across the evidence.", ["INVESTIGATOR"], "paper"),
    ("cogvideo", "幸存者在医院向警方报告后离开", "中景跟随背影，留出充足空间",
     "A restrained 2002 hospital-corridor reenactment: an anonymous adult woman witness in a plain coat sits with her back to camera while a tired officer listens and writes in a completely blank notebook. She rises, walks slowly toward a rain-streaked window and exits frame; her face remains outside the frame. The camera follows at a respectful distance, holding a quiet, composed tone.", ["WITNESS", "INVESTIGATOR"], "wind"),
    ("cogvideo", "档案被推到一旁又被红线连接", "俯拍缓慢下压",
     "In a cold gray police office, stacks of unmarked case folders slide across a desk as an investigator sorts them. One thin folder is briefly pushed aside, then a red thread is drawn from it to a simple park map; papers lift slightly in the airflow from a fan. Overhead camera descends, all pages blank and unreadable.", ["INVESTIGATOR"], "paper"),
    ("cogvideo", "空棋桌旁只有落叶与停顿的时钟", "缓慢橫移并停在空座位",
     "A quiet park chess table in early morning rain. A wall-clock reflection appears faintly in a puddle beside it; the second hand's reflection moves while leaves gather around an empty chair. Distant visitors pass as soft silhouettes between the trees. The camera tracks laterally along the stone edge and stops on the vacant seat, with no person portrayed as a statistic.", ["PARK_VISITORS"], "wind"),
    ("cogvideo", "监控室中的红线连接地铁与公园", "沿桌面缓慢推进",
     "An anonymous investigator studies a wall of old analog monitors and a paper street map. On one screen, two distant silhouettes cross a station platform; the investigator draws a thin red line on the map from the metro area toward a wooded park, then pins the map in place. No legible station names or timestamps; slow forward camera move.", ["INVESTIGATOR", "MAIN_FIGURE", "WOMAN_COWORKER"], "machine"),

    ("cogvideo", "玛丽娜与同事离开超市休息室", "过肩跟随两人穿过走廊",
     "A supermarket staff corridor in 2006 Moscow. An anonymous woman in a pale coat and a slim male coworker walk toward the exit at an unhurried pace, seen from behind; a staff door swings slowly shut and fluorescent lights hum overhead. Their shadows cross the black-and-white tiled floor, a subtle visual bridge to the chessboard, no signs or brand marks.", ["WOMAN_COWORKER", "MAIN_FIGURE"], "keys"),
    ("graphic", "关键纸条和地铁票的事实卡", "程序化排字；纸面上金色细线逐渐显现",
     "2006年6月：纸条写下同行者姓名与电话 / 衣袋里的地铁票 / 车站监控拍到两人同行。以‘证据链’排列，注明‘公开报道’。", [], "paper"),
    ("cogvideo", "探员展开外套检查口袋里的车票", "桌面高度的横向物理跟拍，衣料与桌面视差持续可见",
     "A restrained, clearly fictional cinematic 3D reenactment in a quiet early-2000s evidence room. At table height, a dark coat lies open beside a folded blank note; a small unprinted metro ticket is partly visible inside the coat pocket. From the first frame, one charcoal-gloved forearm gently draws the coat lapel open and keeps the fabric moving with a soft natural ripple; the ticket remains in the pocket and keeps its shape. The camera makes one uninterrupted physical lateral dolly from left to right around the table, revealing clear parallax between the coat, note, ticket, and a small black chess piece. Keep this smooth camera move and subtle cloth movement continuous from first to last frame; do not zoom digitally or hold a still pose. Hands remain at medium distance with natural anatomy. No ticket sliding, morphing, flicker, jitter, sudden exposure jump, or readable text; this is an illustrative reconstruction, not original evidence.",  ["INVESTIGATOR"], "paper"),
    ("cogvideo", "老式监控屏幕里两道身影同行", "缓慢推近屏幕，画面暂停",
     "A 2000s monitoring room with a row of bulky CRT screens. On the center monitor, two anonymous figures continue walking side by side along a subway platform as soft scan lines travel across the image. An investigator leans forward and adjusts a physical playback dial; the footage never freezes, other monitors flicker gently, and the camera tracks toward the center screen. No readable station signs, all faces indistinct; clearly an AI reenactment, not original CCTV.", ["INVESTIGATOR", "WOMAN_COWORKER", "MAIN_FIGURE"], "machine"),
    ("cogvideo", "探员把影像线索与纸条并列", "桌面横移，从屏幕到证物",
     "In a quiet investigation room, an anonymous detective moves a printed still with completely abstract silhouettes beside a folded blank note and the metro ticket. He places three objects in a line and turns a chess piece toward the park map; other officers move softly in the background. The camera glides sideways across the evidence without revealing text or graphic details.", ["INVESTIGATOR"], "paper"),
    ("cogvideo", "地铁路线与公园在棋盘上叠合", "俯拍环绕，红点缓慢收敛",
     "A symbolic three-dimensional Moscow map made of chessboard squares rotates slowly over a dark tabletop. A red line traces a route from a generic subway entrance to a forest park; the line settles on one square and stops. Tiny warm lights move under a translucent map layer, while the camera makes a measured overhead orbit. No labels, dates or exact map claims.", [], "heartbeat"),
    ("cogvideo", "公园中便衣警察出现而男子停步", "中景缓慢侧移，不接触人物",
     "In Bitsa Park on an overcast morning, two anonymous plainclothes officers step into view from behind tree trunks at a respectful distance. A slim man in a dark coat stops walking, turns slightly and raises his open hands to shoulder level without resistance; distant vehicle lights glow through mist. The figures remain several steps apart and composed; camera slides laterally in a steady medium-wide shot.", ["INVESTIGATOR", "MAIN_FIGURE"], "keys"),
    ("graphic", "逮捕日期卡：2006年6月16日", "信息卡；棋盘红点由亮转为静止",
     "FACT CARD — 2006年6月16日 / 皮丘什金被捕 / 纸条、地铁票与监控线索共同推动调查。程序化排字，不冒充警方原始档案。", [], "press"),
    ("cogvideo", "警方搜查中发现与棋盘记号相关的证物", "俯拍缓慢横移，手指停在空格旁",
     "Inside an apartment after the arrest, anonymous investigators in plain dark jackets open a desk drawer and carefully examine a small chessboard beside a blank notebook. Geometric paper squares and a single unmarked token suggest the reported chessboard motif without recreating original evidence. A gloved finger pauses over the pattern; dust rises in cold window light. The page stays blank and faces remain indistinct; one continuous overhead tracking shot.", ["INVESTIGATOR"], "paper"),
    ("cogvideo", "陪审团阅览空白卷宗后合议", "中景缓慢横移，从卷宗移向陪审席",
     "A restrained 2007 Moscow courtroom reenactment seen from the side: anonymous jurors sit behind a long wooden bench and quietly compare blank paper folders; one juror turns a page while another gives a thoughtful nod. A clerk stands at a distance, all faces indistinct and fictional. The camera glides slowly from the empty folder toward the jury, no readable documents, no courtroom theatrics.", ["JURY", "COURT_OFFICIAL"], "paper"),
    ("cogvideo", "2007年莫斯科法庭的匿名被告席", "缓慢推近，轻微环绕玻璃隔间",
     "A restrained 2007 Moscow courtroom reenactment: an anonymous male silhouette stands behind a reinforced glass defendant enclosure, head lowered, while a judge and jurors remain distant silhouettes. A court clerk turns one page and reflections shift across the glass; camera slowly advances and arcs a few degrees around the enclosure. Documents remain blank and faces indistinct.", ["MAIN_FIGURE", "JURY", "COURT_OFFICIAL"], "press"),
    ("cogvideo", "判决文件合上，空棋格映出窗光", "从纸张特写缓慢拉远",
     "A blank court folder closes gently on a wooden table; a black chess piece and a pale square of window light sit beside it. In the background, anonymous relatives leave the courtroom corridor at a slow walking pace, seen only from behind. The camera pulls back to include the folder, the chess square and the empty doorway, no legible text.", ["RELATIVES"], "paper"),

    ("cogvideo", "监狱长廊的灯逐盏变暗", "对称构图缓慢后退",
     "A long institutional corridor with gray walls and evenly spaced ceiling lights. The camera retreats smoothly as the lights dim one by one from far end toward foreground; a heavy door closes slowly at the end of the hall while the camera keeps retreating. A black-and-white floor pattern echoes a chessboard; subdued cool light and deep perspective.", [], "keys"),
    ("graphic", "判决卡：法院认定与自述分栏", "程序化排字；两列数字以金色细线分开",
     "法院认定：48起谋杀、3起未遂 / 个人声称：63人 / 2007年10月：终身监禁。两栏明确区分司法认定与自述；程序化排字。", [], "press"),
    ("cogvideo", "回到秋日公园的空石桌", "低机位缓慢拉远，叶片前景掠过",
     "Return to the same autumn park stone table from the opening. A few chess pieces remain in an unfinished ordinary game; a light breeze moves leaves across the table and one black piece gently tips onto its side. The camera slowly pulls away to reveal an empty bench and soft morning mist, calm and respectful, no people reduced to pieces.", [], "leaves"),
    ("cogvideo", "晨光照亮棋盘与空椅", "缓慢横移，光线逐格经过",
     "A final wide view of a stone chessboard in a quiet Moscow park at sunrise. Warm light travels across alternating pale and dark squares while the empty chair beside it remains in frame; branches sway and the small brown-and-white dog crosses the far background with its leash trailing to an unseen walker. Camera glides gently along the table, ending on the bright empty squares.", ["DOG", "PARK_VISITORS"], "wind"),
    ("cogvideo", "棋盘格转为普通石板路", "由近至远平稳后退",
     "The checkerboard pattern on the stone table gradually becomes the ordinary paving stones of the park path as a thin red marker fades away. Wind moves the leaves, distant walkers continue their day, and morning light opens the frame. The camera retreats smoothly from the board toward the path, restoring the image to an everyday public place, with clean paving and natural human movement.", ["PARK_VISITORS"], "leaves"),
    ("cogvideo", "红色记号消失，留下白色空格", "俯拍缓慢下降至单一空格",
     "An abstract 8-by-8 chessboard floats in a deep navy void. Small red marks dissolve one by one into soft amber points, leaving all squares clean and equal; the camera descends toward one pale square as a gentle glow spreads across the grid. Elegant restrained 3D motion, no count, no names, no scoring or celebration.", [], "chess"),
    ("cogvideo", "公园树影中行人继续向前", "广角慢慢升高，保持横向空间",
     "A calm Moscow park path in autumn, seen in a broad 16:9 composition. Ordinary anonymous visitors walk naturally in both directions, leaves drift in the wind, and sunlight moves between branches; the stone chess table remains in the far left third, not dominating the scene. The camera slowly cranes upward to reveal the width of the park and the quiet everyday life continuing.", ["PARK_VISITORS"], "wind"),
    ("graphic", "结尾致意：每一格背后都是一个人", "片尾卡；六十四个方格依次亮起后停留",
     "END CARD — 棋盘上的每一格，都是一个人 / 记住他们，不要记住他 / 六十四格：国际象棋盘杀手 / 史实依据见史实核对。程序化排字；黑白格与金色星点，不以红点表现人数。", [], "chess"),
]

# 按叙事重新编排45个槽：N03先讲2002幸存者，再转到玛丽娜；N04完整呈现纸条/车票/监控证据链。
# 顺序来源是上面已审过的镜头描述，仍保留S01–S45唯一编号与三十八动七卡的固定槽位。
_SHOT_ORDER = list(range(1, 16)) + [22, 23, 18, 24, 16, 17, 19, 20, 26, 21, 25, 27, 28, 29, 30, 31] + list(range(32, 46))
assert len(_SHOT_ORDER) == 45 and len(set(_SHOT_ORDER)) == 45
SHOTS = [SHOTS[index - 1] for index in _SHOT_ORDER]

# 7 张卡片落在固定槽位；S45 是片尾卡，仍计入七张。
CARDS = {
    "S03": ("六十四格", "莫斯科 · 比察公园", "一宗真实案件 · AI动画情景重现"),
    "S10": ("两个数字，不能混为一谈", "六十四格：他声称的目标", "48起谋杀 + 3起未遂：法院认定"),
    "S18": ("线索未被及时跟进 · 2002", "一位幸存者曾向警方报告遭遇", "公开报道：这条线索当时未获有效追查"),
    "S27": ("关键证据链 · 2006年6月", "纸条写有同行者姓名与电话", "地铁票 + 车站监控显示两人同行"),
    "S33": ("2006年6月16日", "亚历山大·皮丘什金被捕", "公开报道：纸条、车票与监控相互印证"),
    "S39": ("2007年10月 · 法院判决", "48起谋杀 · 3起未遂", "终身监禁；63人为其本人声称"),
    "S45": ("棋盘上的每一格，都是一个人", "六十四格：国际象棋盘杀手", "记住他们，不要记住他"),
}
CARD_HEADER = "案件档案  /  莫斯科 · 2000年代"
CARD_FOOTER = "资料摘要与示意图 · 非原始证物影像"
TITLE_CARD = []
END_CARD = [
    "棋盘上的每一格，都是一个人",
    "六十四格：国际象棋盘杀手",
    "记住他们，不要记住他",
    "资料：BBC · AP · Reuters · The Guardian · GQ / AI动画情景重现",
]
CAPTION_KEYWORDS = [
    "六十四格", "四十八起谋杀", "三起未遂", "六十三", "自述", "法院认定", "二〇〇二年",
    "幸存者", "一张纸条", "地铁票", "车站监控", "二〇〇六年六月", "六月十六日",
    "终身监禁", "受害者", "记住他们",
]
LABEL_OVERRIDES = {
    "S01": "AI动画情景重现 · 非新闻影像",
    "S04": "AI动画情景重现 · 非本人容貌",
    "S05": "AI动画情景重现 · 虚构替身",
    "S09": "AI动画示意 · 棋盘为象征画面",
    "S16": "AI动画情景重现 · 幸存者非本人容貌",
    "S17": "AI动画示意 · 报道线索不作档案复刻",
    "S21": "AI动画示意 · 纸条为虚构道具",
    "S24": "AI动画情景重现 · 非本人容貌",
    "S25": "AI动画示意 · 车票为虚构道具",
    "S26": "AI动画示意 · 非真实监控画面",
    "S28": "AI动画示意 · 道具非原物",
    "S29": "AI动画示意 · 非真实监控画面",
    "S32": "AI动画情景重现 · 非真实抓捕画面",
    "S34": "AI动画示意 · 非警方原始档案",
    "S35": "AI动画示意 · 非原始档案",
    "S36": "AI动画示意 · 非庭审实录",
    "S37": "AI动画示意 · 非庭审实录",
    "S45": "资料卡 · AI动画情景重现",
}
SFX_EVENTS = [
    ("S01", "chess"), ("S05", "wind"), ("S06", "chess"), ("S09", "heartbeat"),
    ("S12", "wind"), ("S13", "wind"), ("S16", "wind"), ("S17", "paper"),
    ("S18", "paper"), ("S21", "paper"), ("S22", "keys"), ("S23", "phone"),
    ("S24", "keys"), ("S25", "paper"), ("S26", "machine"), ("S27", "paper"),
    ("S28", "paper"), ("S29", "machine"), ("S30", "paper"), ("S31", "heartbeat"),
    ("S32", "keys"), ("S33", "press"), ("S34", "paper"), ("S35", "paper"),
    ("S36", "press"), ("S38", "keys"), ("S39", "press"), ("S40", "wind"),
    ("S41", "wind"), ("S42", "wind"), ("S43", "chess"), ("S45", "chess"),
]
TITLES = [
    "六十四格：莫斯科公园里的棋盘与一项自述",
    "六十三是自述，四十八起谋杀与三起未遂是法院认定",
    "纸条、地铁票与监控：比察公园案件如何走向逮捕",
]
HOOK = "他常在公园下棋，像个普通棋友；可他盯上的，是一块六十四格的棋盘。六十三是他的自述，四十八起谋杀和三起未遂，才是法院认定的数字。"
GOLDEN_LINES = [
    "六十三是他的自述，四十八起谋杀、三起未遂才是法院认定。",
    "棋盘上的每一格，都是一个人。",
    "记住他们，不要把凶手变成传奇。",
]
DESCRIPTION = (
    "本片以莫斯科比察公园案件为题材，依据 BBC、AP、Reuters、The Guardian 等公开报道整理。"
    "皮丘什金曾声称以六十四格为目标；法院在二〇〇七年认定四十八起谋杀、三起未遂，并判处终身监禁。"
    "画面为虚构角色的AI三维动画情景重现，不是新闻、监控或证物影像；不呈现暴力过程。"
)
QUESTION = "看到‘自述’和‘法院认定’的差别后，你觉得真实案件视频最应该先讲清楚什么？"
HASHTAGS = ["#真实事件", "#悬疑", "#国际象棋", "#莫斯科", "#3D动画", "#真实犯罪"]


def compose_prompt(project, shot):
    """唯一提示词组装器：STYLE → 逐镜角色设定 → 动态镜头 → NEGATIVE。"""
    settings = project.get("character_settings") or {}
    role_lines = [f"【角色设定：{cid}】 {str(settings[cid]).strip()}"
                  for cid in shot.get("characters", []) if settings.get(cid)]
    parts = [str(project.get("style_prefix") or "").strip(), *role_lines,
             str(shot.get("prompt") or "").strip(),
             str(project.get("negative_prompt") or "").strip()]
    result = "\n".join(part for part in parts if part)
    if not result.startswith("【STYLE】") or not result.rstrip().endswith(".") or "【NEGATIVE】" not in result:
        raise ValueError(f"{shot.get('id')}: malformed STYLE/NEGATIVE prompt")
    if shot.get("characters") and "【角色设定：" not in result:
        raise ValueError(f"{shot.get('id')}: character setting missing")
    return result


def presentation():
    return {
        "card_header": CARD_HEADER,
        "card_footer": CARD_FOOTER,
        "cards": {sid: list(lines) for sid, lines in CARDS.items()},
        "title_card": list(TITLE_CARD),
        "end_card": list(END_CARD),
        "end_card_shot": "S45",
        "caption_keywords": CAPTION_KEYWORDS,
        "label_overrides": LABEL_OVERRIDES,
        "sfx_events": [list(x) for x in SFX_EVENTS],
        "subtitle_style": {"base": "白字黑边", "keyword": "金色高亮", "position": "底部安全区"},
        "target_speech_rate_chars_per_second": 3.7,
        "explicit_pause_after": {"N02": "几乎被填满", "N03": "一张纸条", "seconds": 0.5},
    }


def audio_manifest(chapters):
    return {
        "voice_id": "",
        "language": "zh-CN",
        "selection": "待用户试听后选定的成熟男声叙述音色",
        "release_tag": "chessboard64-audio-v1",
        "asset_url_template": "https://github.com/ozzy282576/monalisa-film/releases/download/chessboard64-audio-v1/{file}",
        "clips": [{"id": cid, "file": f"{cid}.mp3", "sha256": "", "text": text, "voice_id": ""}
                  for cid, _title, text in chapters],
        "source_chunks": {},
        "post_processing": "TTS原始片段在audio/source；audio/raw为拼接版；tighten_pauses只收紧长停顿并保留指定0.5秒停顿；audio/*.mp3为渲染输入。",
    }


def screenplay(story):
    rows = [f"# {TITLE}", "", "抖音横屏 16:9 · 1920×1080 · 30fps · 180秒", "",
            "## 事实与表现边界", "", *[f"- {p}" for p in PRINCIPLES], "",
            "## 六段旁白（当前台词源）", ""]
    for ch in story["chapters"]:
        rows += [f"### {ch['id']} · {ch['title']} · 目标 {ch['start']:03d}–{ch['start']+ch['duration']:03d}s", "", ch["text"], ""]
    rows += ["## 45格分镜表（4秒规划网格；最终剪点按真实配音调整）", "",
             "| 镜号 | 规划时间 | 类型 | 画面 / 运镜 |", "|---|---:|---|---|"]
    for shot in story["shots"]:
        rows.append(f"| {shot['id']} | {shot['start']:03d}–{shot['start']+shot['duration']:03d}s | {shot['kind']} | {shot['purpose']}；{shot['camera']} |")
    rows += ["", "## 资料来源", ""]
    rows += [f"{s['id']}. {s['url']} — {s['usage']}" for s in SOURCES]
    return "\n".join(rows) + "\n"


def initial_script(story):
    out = [f"# {TITLE}", "", "> 16:9 · 1920×1080 · 30fps · 180秒 · 45格（38个CogVideoX-Flash动态镜头 + 7张卡片）", "",
           "## 片名与叙事说明", "", "六十三为本人声称；四十八起谋杀、三起未遂为法院认定。所有画面均为虚构角色的AI三维动画情景重现。", "",
           "## 六段旁白", ""]
    for ch in story["chapters"]:
        out += [f"### {ch['id']} · {ch['title']}", "", ch["text"], ""]
    out += ["## 45格镜头顺序", "", "| 镜号 | 时间 | 类型 | 画面 | 声音提示 |", "|---|---|---|---|---|"]
    for shot in story["shots"]:
        out.append(f"| {shot['id']} | {shot['start']:03d}–{shot['start']+4:03d}s | {shot['kind']} | {shot['purpose']} | {shot['sfx_note']} |")
    out += ["", "## 发布前核对", "", *[f"- {p}" for p in PRINCIPLES], "", "## 资料来源", ""]
    out += [f"{s['id']}. {s['url']} — {s['usage']}" for s in SOURCES]
    return "\n".join(out) + "\n"


def prompts_document(story):
    rows = [f"# {TITLE} · CogVideoX-Flash 视频提示词", "",
            "生成提示词逐镜完整列出；每条均为 STYLE 开头、角色设定按需插入、NEGATIVE 结尾。", "",
            "分辨率交付 1920×1080；智谱免费模型按 16:9 生成动态片段，信息卡由后期排字。", ""]
    for shot in story["shots"]:
        if shot["kind"] != "cogvideo":
            continue
        rows += [f"## {shot['id']} · {shot['purpose']}", "",
                 f"剪辑槽位：规划4秒 · 16:9 · 角色：{', '.join(shot['characters']) or '无'}", "",
                 "```text", compose_prompt(story, shot), "```", ""]
    return "\n".join(rows).rstrip() + "\n"


def build():
    assert len(SHOTS) == 45, f"需要45个规划槽，当前 {len(SHOTS)}"
    assert sum(x[0] == "cogvideo" for x in SHOTS) == 38
    assert sum(x[0] == "graphic" for x in SHOTS) == 7
    assert len(CHAPTERS) == 6
    chapter_shot_counts = (8, 7, 8, 8, 7, 7)
    shot_chapter = {}
    cursor = 0
    for (cid, _title, _text), count in zip(CHAPTERS, chapter_shot_counts):
        for index in range(cursor, cursor + count):
            shot_chapter[f"S{index + 1:02d}"] = cid
        cursor += count
    assert cursor == 45
    story = {
        "title": TITLE, "target_duration": 180, "width": 1920, "height": 1080, "fps": 30,
        "model": "cogvideox-flash", "branch": BRANCH,
        "style_prefix": STYLE_PREFIX, "negative_prompt": NEGATIVE_PROMPT,
        "character_settings": CHARACTER_SETTINGS, "principles": PRINCIPLES, "sources": SOURCES,
        "chapters": [{"id": cid, "title": title, "start": i*30, "duration": 30, "text": text}
                     for i, (cid, title, text) in enumerate(CHAPTERS)],
        "shots": [], "presentation": presentation(),
        "_scaffold": {"template": "production/kitakyushu2002 CogVideoX production pipeline",
                      "note": "45 slots × 4 s = 180 s; 38 CogVideoX-Flash dynamic videos + 7 programmatically rendered cards; S45 is the final card."},
    }
    for i, row in enumerate(SHOTS):
        kind, purpose, camera, prompt, characters, sfx = row
        sid = f"S{i+1:02d}"
        start = i * 4
        shot = {
            "id": sid, "kind": kind, "start": start, "duration": 4,
            "narration_id": shot_chapter[sid],
            "prompt": prompt if kind == "cogvideo" else "",
            "purpose": purpose, "transition_out": "棋盘格匹配转场；同段硬切或叠化",
            "graphic": prompt if kind == "graphic" else "",
            "characters": characters, "seed": 6400 + i,
            "seconds": 5, "aspect": "16:9", "resolution": "1080p", "frame_rate": 24,
            "camera": camera, "sfx_note": sfx,
        }
        story["shots"].append(shot)
    assert len({s['id'] for s in story['shots']}) == 45
    PLAN.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MANIFEST.write_text(json.dumps(audio_manifest(CHAPTERS), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "screenplay.md").write_text(screenplay(story), encoding="utf-8")
    (HERE / "抖音脚本.md").write_text(initial_script(story), encoding="utf-8")
    (HERE / "video_prompts.md").write_text(prompts_document(story), encoding="utf-8")
    print(f"story.json 已写入：45格 = 38个CogVideoX-Flash动态镜头 + 7张卡片；180秒。")
    print("旁白字数（含标点）：" + " / ".join(f"{cid} {len(text)}" for cid, _, text in CHAPTERS)
          + f"；合计 {sum(len(text) for _,_,text in CHAPTERS)}。")
    print("分镜提示：" + str(sum(len(s['prompt']) for s in story['shots'])) + " 个本镜提示字符；风格、角色、负面词由生成器统一前后拼接。")


if __name__ == "__main__":
    if "--script" in sys.argv:
        from script_table import render_document
        path = HERE / "抖音脚本.md"
        path.write_text(render_document(), encoding="utf-8")
        print("写入", path)
    elif "--publish" in sys.argv:
        from script_table import publish_document
        path = HERE / "抖音发布文案.md"
        path.write_text(publish_document(), encoding="utf-8")
        print("写入", path)
    else:
        build()
