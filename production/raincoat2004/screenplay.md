# 韩国雨衣杀手柳永哲：十个月，二十条人命

三分钟横屏解说 · 成片 1920×1080 / 30 fps / 180 秒 · 45 镜（38 个 Agnes 写实 3D 动画镜头 + 7 张信息卡）· 露脸模式

本文件与 `story.json` / `audio/manifest.json` 同源，叙述文字由 `build_story.py` 写入；逐句事实出处见 `史实核对.md`。

## 事实边界

- 全部 Agnes 镜头为写实 3D CGI 动画情景重现，画面常驻标注「AI动画情景重现 · 非新闻影像」，不冒充庭审、审讯、搜查、监控或证物照片
- 不展示遗体、血腥或作案过程；杀害方式只写到「钝器」这一层，不写细节；奉元寺后山只出现雨、泥土、落叶、警戒线与工作人员背影
- 凶手由一名虚构的年代角色扮演，是 AI 生成的匿名人物，**不是柳永哲本人的容貌**，不做任何真实人物的肖像还原
- 三名露脸角色（雨衣男 / 老刑警 / 按摩店老板）各有一张不同的脸；同一角色跨镜头逐字节复用同一条面容 token 并共用同一个 seed，由 production/face_cast.py 的 check-prompts（静态闸门）与 check-frames（画面闸门）检查，人眼对照接触表判决
- 受害者不以具备可辨识面容的人像出现：女性角色一律背影、剪影或局部，不出现遗体、遗物特写之外的私密画面
- 每一句事实都能指到 sources 里的一条公开报道；口径冲突处（受害者构成、招供人数、最高法院日期）只写「警方确认的二十人」或写区间，不挑一个当结论
- 所有中文姓名、日期、字幕后期添加，不交给视频模型拼写；画面内不出现任何可读文字、门牌或招牌（AI 街景必编字，靠构图排除）
- 人工检视 qa/ 接触表与 delivery/face-cast/ 人脸接触表；换脸、畸变、伪文字、中途换场的镜头用 {"only":"Sxx"} 重生成，不直接进成片

## 解说稿与时间线

### N01　黄金开头：一场没有失窃的凶杀

二〇〇三年九月，首尔江南区新沙洞，一对老夫妇在自己家里遇害，房子随后起火。凶手没有拿走任何值钱的东西。十个月后警方才确认，那只是二十条人命里的第一起；而最后把他揪出来的，不是指纹，也不是监控，是一部被记下来的电话号码。

### N02　人物档案：从监狱走向富人区的男人

他叫柳永哲，一九七〇年出生在全罗北道高敞郡，家里很穷。从高中时代起，他就在监狱里进进出出：盗窃、诈骗、暴力伤人，前后十四次，累计服刑十一年。二〇〇三年九月十一日，他最后一次走出监狱；妻子已经带着儿子离开，那年他三十三岁。

### N03　目标：白天没有人的独栋住宅，和深夜接电话的女人

出狱十三天后，他第一次作案。此后他专挑富人区的独栋住宅，在白天老人独自在家的时候闯进去；为了不留活口，连屋里的帮佣也不放过。二〇〇四年春天，他突然换了目标：用伪造的警察证件和一部电话，把按摩女约到自己住的写字楼公寓。到七月落网前，有十一名女性走进了那栋楼，再也没有出来。

### N04　转机：一部被按摩店老板记下来的号码

一开始，这些失踪并没有被当成连环案件。按摩女的去向本来就少有人追问，警方最初的判断是：可能有人把她们拐卖到了乡下。真正的转机出现在一部电话上——店里好几个姑娘，都是接到同一个号码之后消失的。老板把号码记了下来，又看见它出现，就带着人报了警。

### N05　抓捕：逃跑十二小时，和一座后山

二〇〇四年七月十五日凌晨，警方在麻浦区的一条巷子里抓住了他。审讯中途他假装癫痫发作，趁手铐松开逃出警局；十二个小时后，警察在永登浦站附近把他重新抓住。面对警方他说：我就是那个连环杀人犯。七月十八日，他带着警察上了奉元寺的后山。雨天里，警方在那片山坡上标出了十一处掩埋地点。

### N06　结局：死刑，没有执行，和一群粉丝

二〇〇四年十二月十三日，首尔中央地方法院认定他杀害二十人，判处死刑；二〇〇五年六月，最高法院终审维持原判。韩国从一九九七年起就没有再执行过死刑，他至今仍然在监狱里。真正让人不安的是，他被捕之后，韩国的网站上出现了他的粉丝俱乐部。危险从不写在脸上，它就走在人群里。

## 分镜（45 镜，每镜只用一次）

| 镜头 | 规划时间 | 类型 | 运镜 | 叙事职责 | 衔接 | 音效/备注 |
|---|---|---|---|---|---|---|
| S01 | 000–004s | agnes | 低机位缓慢前推 | 开场：雨夜里的富人区街道，没有一家店面 | 接信息卡：案件名片 | 雨声 + 低频悬念音 |
| S02 | 004–008s | graphic | 信息卡（静帧） | 名片：案件、时间、规模 | 接 AGNES：第一现场外观 | 低音撞击 + 雨声延续 |
| S03 | 008–012s | agnes | 贴墙横移 | 第一起：独栋住宅，火从窗里映出来 | 接 AGNES：屋内空镜 | 火声 + 雨声 |
| S04 | 012–016s | agnes | 缓慢横移 | 现场空镜：什么都没拿走 | 接 AGNES：露脸镜头（C1 首次出现） | 余烬细响 |
| S05 | 016–020s | agnes | 缓慢前推（中景） | 凶手首次露面：雨衣下的那张脸 | 接 AGNES：警方到场 | 雨声 + 主题动机首次出现 |
| S06 | 020–024s | agnes | 缓慢前推（中景） | 老刑警到场：案子被认真写下的一刻 | 接 AGNES：物证特写 | 雨声 + 证物袋纸张声（SFX paper） |
| S07 | 024–028s | agnes | 俯视缓慢下移 | 取证：白手套、证物袋、放大镜 | 接 AGNES：城市夜景（俯瞰） | 手套与纸张摩擦（SFX paper） |
| S08 | 028–032s | agnes | 缓慢横摇（高空） | 城市：一栋栋亮着灯的住宅，明天还会有 | 接 N02：乡村旧屋 | 雨声渐弱 + 低频过渡 |
| S09 | 032–036s | agnes | 缓慢前推 | 出身：全罗北道高敞郡的旧屋 | 接 AGNES：少年背影 | 清晨鸟声 + 低音铺底 |
| S10 | 036–040s | agnes | 缓慢跟拍（背影） | 少年时代：从田埂走向小镇 | 接信息卡：前科与刑期 | 脚步踩泥 + 风声 |
| S11 | 040–044s | graphic | 信息卡（静帧） | 档案：十四次前科 / 累计服刑十一年 | 接 AGNES：监狱走廊 | 纸张翻动（SFX paper） |
| S12 | 044–048s | agnes | 缓慢前推 | 监狱：灰色走廊与铁栏 | 接 AGNES：会见室的离婚文件 | 铁门回声（SFX keys） |
| S13 | 048–052s | agnes | 缓慢前推（特写） | 家庭：一份没有读完的离婚文件 | 接 AGNES：出狱 | 纸页轻响（SFX paper） |
| S14 | 052–056s | agnes | 缓慢后拉（剪影） | 出狱：二〇〇三年九月十一日 | 接 AGNES：新住处的窗 | 铁门开启 + 雨声 |
| S15 | 056–060s | agnes | 缓慢前推 | 新住处：老姑山洞写字楼公寓的一扇窗 | 接 N03：一部电话被拿起 | 雨声 + 远处车流 |
| S16 | 060–064s | agnes | 缓慢前推（特写） | 手法（一）：一部被拿起的电话 | 接 AGNES：公寓走廊 | 老式手机按键声（SFX phone） |
| S17 | 064–068s | agnes | 缓慢前推 | 十一名女性走进的那栋楼 | 接信息卡：目标改变 | 灯管电流声 + 脚步不存在的静默 |
| S18 | 068–072s | graphic | 信息卡（静帧） | 口径：二〇〇四年三月起 / 十一名女性在其住所失踪 | 接 AGNES：浴室门缝 | 低音撞击 |
| S19 | 072–076s | agnes | 缓慢下移 | 留给镜头的空白：只拍水与门缝 | 接 AGNES：一个女人的背影 | 水流声 + 静默 |
| S20 | 076–080s | agnes | 缓慢跟拍（远景背影） | 进楼的人：只给背影，不给脸 | 接 AGNES：远处的一排窗 | 雨声 + 高跟鞋脚步 |
| S21 | 080–084s | agnes | 缓慢横移 | 城市依旧：只有那栋楼的窗户知道 | 接 AGNES：后山树林 | 雨声 + 低频 |
| S22 | 084–088s | agnes | 缓慢前推 | 藏：奉元寺后山的雨雾 | 接 AGNES：泥土与落叶 | 雨打树叶 + 低频下潜 |
| S23 | 088–092s | agnes | 缓慢下移（特写） | 那些被翻动过的落叶（不出现遗体） | 接 N04：没人重视的失踪 | 雨滴落土 + 低音 |
| S24 | 092–096s | agnes | 缓慢前推 | 没人当回事：派出所桌上的一叠失踪材料 | 接信息卡：最初的判断 | 日光灯嗡鸣 + 纸张（SFX paper） |
| S25 | 096–100s | graphic | 信息卡（静帧） | 最初的判断：拐卖案件 | 接 AGNES：后巷入口 | 低音铺底 |
| S26 | 100–104s | agnes | 缓慢前推 | 店与巷：一台电话连着的地方 | 接 AGNES：老板露面 | 雨声 + 塑料箱轻碰 |
| S27 | 104–108s | agnes | 缓慢前推（中景） | 转机：那个记号码的人 | 接 AGNES：纸上的笔 | 座机听筒搁下 + 纸页（SFX paper） |
| S28 | 108–112s | agnes | 缓慢前推（特写） | 手上的证据：号码被一圈圈画住 | 接 AGNES：老板与警员的背影 | 笔尖划纸（SFX paper） |
| S29 | 112–116s | agnes | 缓慢横移（背影） | 报警：老板带着人去了警局 | 接 AGNES：凌晨的巷子 | 雨声 + 低声交谈（无对白，仅环境） |
| S30 | 116–120s | agnes | 缓慢前推 | 七月十五日凌晨：麻浦区的巷口 | 接 N05：手电扫过湿墙 | 雨声 + 引擎怠速（SFX machine） |
| S31 | 120–124s | agnes | 缓慢前推 | 抓捕：手电光下低着的那颗头 | 接 AGNES：审讯室（C1 露脸） | 雨声 + 手电开关 |
| S32 | 124–128s | agnes | 缓慢前推（中景） | 审讯：他说出了警方没掌握的案子 | 接 AGNES：空椅子与手铐 | 录音机按键 + 低频 |
| S33 | 128–132s | agnes | 缓慢前推 | 那十二个小时：空椅子与挂着的手铐 | 接 AGNES：凌晨的站前街道 | 走廊回声（SFX keys） |
| S34 | 132–136s | agnes | 缓慢横摇 | 十二小时后：永登浦站附近 | 接 AGNES：两次审讯 | 雨声 + 远处警灯电流 |
| S35 | 136–140s | agnes | 缓慢前推（双人中景） | 对质：两次审讯之间 | 接信息卡：关键日期 | 椅子挪动 + 低频 |
| S36 | 140–144s | graphic | 信息卡（静帧） | 关键日期：七月十五日抓捕 / 七月十八日指认现场 | 接 AGNES：后山搜山 | 低音撞击 + 雨声 |
| S37 | 144–148s | agnes | 缓慢横移 | 后山：警戒线在雨里 | 接 AGNES：警局门口的镜头 | 雨打树林 + 低频 |
| S38 | 148–152s | agnes | 缓慢前推（背影） | 舆论：镜头与麦克风围在警局门口 | 接 N06：法院外的雨 | 快门连响（SFX press）+ 嘈杂人声 |
| S39 | 152–156s | agnes | 缓慢前推 | 审判：法院外的雨 | 接 AGNES：法庭内 | 雨声 + 人群低语 |
| S40 | 156–160s | agnes | 缓慢前推（手部近景） | 判决：木槌落在没有字的判决书上 | 接信息卡：判决时间线 | 木槌轻落（SFX press）+ 纸张 |
| S41 | 160–164s | graphic | 信息卡（静帧） | 判决：一审死刑 / 最高法院维持 | 接 AGNES：监狱外墙 | 低音撞击 |
| S42 | 164–168s | agnes | 缓慢后拉 | 未执行：监狱的墙与雨 | 接信息卡：案件之后 | 雨声 + 远处铁门 |
| S43 | 168–172s | graphic | 信息卡（静帧） | 案件之后：一九九七年起未再执行死刑 / 他仍在服刑 | 接 AGNES：空走廊 | 低音铺底 |
| S44 | 172–176s | agnes | 缓慢前推 | 没有被执行的时间：空牢房走廊 | 接 AGNES：挂着的雨衣 | 空走廊回声 + 低频 |
| S45 | 176–180s | agnes | 缓慢后拉（暗下去） | 金句画面：一件挂着的黄色雨衣 | 片尾卡叠在最后一秒上 | 雨声渐远 + 片尾音乐 |

## 画面上的文字

- 片头卡：韩国雨衣杀手：十个月，二十条人命 / 二〇〇三—二〇〇四 · 首尔 · 二十人遇害
- 信息卡：
  - S02　柳永哲连环杀人案｜大韩民国 · 首尔 二〇〇三—二〇〇四｜十个月 · 二十条人命
  - S11　凶手档案｜一九七〇年生 · 全罗北道高敞郡｜前科十四次 · 累计服刑十一年
  - S18　他换掉了目标｜二〇〇四年春天起 · 麻浦区｜十一名女性在其住所失踪
  - S25　一开始，没人当回事｜失踪报案未并案侦查｜警方最初判断：拐卖案件
  - S36　二〇〇四年七月｜十五日 抓捕 · 十八日 指认现场｜奉元寺后山 · 十一具遗体
  - S41　判决｜二〇〇四年十二月十三日 一审死刑｜二〇〇五年六月 最高法院维持
  - S43　案件之后｜韩国自一九九七年起未再执行死刑｜他至今仍在监狱中服刑
- 片尾卡：
  - 你能认出走在人群里的他吗？
  - 柳永哲连环杀人案 · 二〇〇三—二〇〇四 · 二十人遇害
  - 危险从不写在脸上，它就走在人群里。
  - 资料：Korea Herald / Korea JoongAng Daily / Newsweek · 原创解说 · AI动画情景重现
- 常驻标签：AI动画情景重现 · 非新闻影像（审讯 / 抓捕 / 搜查 / 法院 / 监狱镜头另有更具体的标签，见 `story.json` 的 `label_overrides`）

## 逐镜提示词（英文，Agnes Video V2.0）

**S01**（seed 20260925）：

> A rain-soaked residential street in an affluent low-rise Seoul district at night in 2003: wet asphalt filling the lower half of the frame, a clipped hedge and a low brick wall running along the right, warm window light bleeding through the rain haze far behind, puddles mirroring amber street lamps, heavy rain streaking the air and bouncing off the road. The frame contains no shopfront, no signboard, no vehicle, no person. Slow low-angle push forward along the empty road, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S03**（seed 20260927）：

> The exterior of a single detached two-storey house behind a low wall in Seoul at night, heavy rain: one ground-floor window glows deep orange from firelight behind closed curtains, smoke seeping along the eaves, unlit door, no house number, no gate plate, no lettering of any kind, no people, no cars. Slow lateral dolly along the wet wall, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S04**（seed 20260928）：

> The interior of the same house after the fire, seen as an empty room: an overturned armchair, a floor lamp lying on its side, an open jewellery box on a sideboard with rings still inside, ash flakes drifting in the air, thin smoke, the fire already out, no body, no blood, no people, no readable text on any surface. Slow lateral track across the room, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S05**（seed 20260929，定妆照首帧）：

> A medium shot in a rainy Seoul side street at night: an anonymous Korean man of thirty-four: a long oval face with a heavy jaw, narrow hooded eyes whose outer corners turn down, thick straight brows set low, a low-bridged nose with a rounded tip, thin colourless lips, short black hair cropped close above the ears and parted flat, sallow skin, a small pale scar on the left cheekbone; he wears a dark yellow raincoat and a navy baseball cap., standing still under a brick wall, rain streaming off the brim of the cap and running down the shoulders of the raincoat, head slightly turned, weight shifting as he looks off to one side of the frame, cold street light on one cheek and darkness on the other; behind him only wet brick, drain water and rain haze, no shop, no sign, no vehicle, no other person. Slow push in on him, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S06**（seed 20260930，定妆照首帧）：

> A medium shot in the front yard of the burnt house in the rain just after dawn: an anonymous Korean man of fifty-two: a broad square head with a heavy jawline, deep horizontal creases across the forehead, pouched eyelids over small shrewd eyes, thick greying eyebrows, a wide flat nose, a straight mouth with downturned ends, iron-grey hair thinning at the temples and combed back, weathered ruddy cheeks; he wears a dark grey overcoat over a rumpled white shirt., holding a folded paper evidence bag against his chest with both hands, rain on his shoulders and hair, jaw set, gaze angled down and away from the camera, breath faintly visible; behind him only the wet low wall and the dark house wall, no sign, no vehicle, no lettering, no other person. Slow push in on him, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S07**（seed 20260931）：

> A top-down close view of a plain evidence table under a work lamp: two white cotton gloves laid flat, two folded paper evidence bags, a magnifying glass, a small torch, a pair of tweezers, all on a bare grey surface; no writing, no numbers, no labels, no photographs, no people, no blood. Slow overhead descent toward the table, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S08**（seed 20260932）：

> A high wide view over a rainy Seoul residential district at night, seen from a hillside: rows of low-rise roofs and lit windows spread across the frame under rain and low cloud, wet rooftops glinting, telephone wires crossing the middle distance, no illuminated signage, no letters, no numbers, no vehicles, no people. Slow lateral pan across the rooftops, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S09**（seed 20260933）：

> A small low house with aged clay roof tiles in a rural village in Gochang, South Korea, in the misty early morning of the 1970s: bare earth yard, wooden door frame, stacked firewood, a single bare light bulb above the door, wet vegetable plots and low hills beyond, everything damp and grey-green, no lettering, no vehicles, no people. Slow push toward the doorway, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S10**（seed 20260934）：

> A boy of about thirteen, seen strictly from behind and slightly below, walking away along a muddy village path at dusk in the 1980s: worn jacket, hands pushed into pockets, bare leafless trees on both sides, wet ground reflecting a grey sky, no face visible, no other people, no houses with lettering. Slow tracking shot following his back, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S12**（seed 20260936）：

> A bare prison corridor in South Korea in the early 2000s: grey painted walls, a row of iron bars along the left, harsh fluorescent light, a single guard standing far away with his back to the camera and no face visible, damp concrete floor, no signs, no numbers, no lettering anywhere. Slow forward dolly down the empty corridor, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S13**（seed 20260937）：

> A close view of a metal visiting-room table: a folded document lying face-down, its blank back turned to the camera with no writing visible, and beside it a man's bare left hand resting flat on the table, no ring on the finger, short nails, faint tremor, cold fluorescent light from above, blurred grey wall behind, no other objects, no people, no lettering. Slow push toward the hand and the blank paper, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S14**（seed 20260938）：

> The outer gate of a South Korean prison opening onto a wet access road in the rain at midday: a single man in a plain jacket walks away from the camera through the gap, strictly from behind and rendered almost as a silhouette against the grey light, no face visible, no guards in frame, no lettering, no numbers, no vehicles, nothing else moving but rain. Slow pull back as he walks away, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S15**（seed 20260939）：

> The exterior facade of a low-rise officetel building in Mapo-gu, Seoul, at night in the rain: a grid of identical small windows, one of them lit from inside with a pale curtain half drawn, water running down the concrete and dripping from the ledges, unlit windows dark, no building name, no numbers, no signage, no people, no vehicles. Slow push toward the single lit window, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S16**（seed 20260940）：

> A close view of a hand lifting a small dark clamshell mobile phone of the early 2000s from a bare wooden desk at night: the screen stays dark and unreadable, keys unlit, a flex cable and a cigarette lighter beside it, only a desk lamp lighting the hand and the wood, no writing or numbers visible on the device or the desk, no other person. Slow push in on the hand and the phone, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S17**（seed 20260941）：

> A narrow interior corridor of an officetel in Mapo-gu, Seoul, at night: identical doors along the left wall with no numbering and no name plates, worn carpet, a single flickering fluorescent tube overhead, a plastic bin, a mop leaning in the corner, no people, no lettering anywhere. Slow push down the empty corridor, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S19**（seed 20260943）：

> A bathroom door standing slightly ajar in a dim officetel apartment at night: steam on the mirror above a plain porcelain sink, water running in a thin continuous thread from the tap, wet floor tiles reflecting a single warm bulb, a towel fallen on the floor, the room behind the door dark and unlit; no person, no body, no blood, no readable text, no bottles with labels. Slow downward move from the mirror to the running water, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S20**（seed 20260944）：

> A woman in a plain dark coat, seen strictly from behind at a long distance, walking toward the entrance of a low-rise officetel at night in the rain: her figure small in the frame, her face never visible, one hand holding a small bag, wet pavement and a bare bulb over the doorway ahead of her, no signage, no lettering, no other people, no vehicles. Slow tracking shot following her back toward the door, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S21**（seed 20260945）：

> A distant wide view of a low-rise officetel block in western Seoul at night from across a wet road: three or four windows lit, rain falling through the light, wet asphalt and a low wall in the foreground, no illuminated signs, no letters, no numbers, no vehicles, no people. Slow lateral drift across the facade, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S22**（seed 20260946）：

> A wet mountain trail behind an old temple on the northern edge of Seoul, in heavy rain and low mist: dark pine trunks, wet undergrowth pressing in from both sides, the trail surface running with water toward the camera, temple roof tiles barely visible through the trees far above, no lettering, no signs, no people, no vehicles. Slow push down the trail, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S23**（seed 20260947）：

> A close view of wet forest floor in the rain: dark turned earth, scattered wet leaves, a broken twig, rain dripping from pine needles onto the soil, a shallow hollow in the ground filled with rainwater; no body, no clothing, no tool, no blood, no people, no lettering. Slow downward move across the wet ground, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S24**（seed 20260948）：

> A night-time desk in a small South Korean police office in 2004: a thick stack of missing-person files with rubber bands, a rotary telephone, a desk lamp with a green glass shade, a cold cup of coffee, an electric fan, rain on the dark window behind, the papers blank and unreadable, no lettering, no numbers, no people, no uniforms. Slow push in over the stack of files, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S26**（seed 20260950）：

> A narrow back alley behind a low commercial building in Seoul at night: a bare bulb above a plain unmarked service door, drainage water running along the concrete, stacked crates, a bicycle leaning on the wall, rain falling through the cone of light, no shopfront, no signboard, no neon, no lettering or numbers anywhere, no people, no vehicles. Slow push toward the unmarked door, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S27**（seed 20260951，定妆照首帧）：

> A medium shot behind the counter of a small massage parlour in Seoul at night: an anonymous Korean man of forty-five: a round fleshy face with full cheeks and a soft chin, quick small eyes set close together, thick level eyebrows, a broad nose, a heavy black moustache covering the upper lip, short wavy black hair thinning on the crown, warm tan complexion; he wears a brown leather jacket over a dark knit sweater., holding an open notebook in one hand, a pen in the other, head turned to look off toward the left of the frame, one phone on the counter and a second handset off the hook beside it, warm bulb light on his face and the notebook, the pages turned away from the camera and unreadable, no signage, no lettering, no numbers, no customers, no other person. Slow push in on him, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S28**（seed 20260952）：

> A close view of a hand pressing a pen onto an open notebook page at a counter at night: the page angled away from the camera so no writing is legible, the pen tip touching the paper, a ring of lamplight on the page, a second notebook beside it with a folded corner, no readable text or numbers, no other person, no signage. Slow push in on the hand and pen, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S29**（seed 20260953）：

> The parlour owner and a uniformed police officer, both seen from behind and from the chest down to the knees, standing in a doorway at night while rain falls beyond them in the street: the officer's hand on a notebook, the owner's shoulders squared, no faces visible, no badges, no lettering, no numbers, no vehicles, no other people. Slow lateral move across their backs and the rain beyond, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S30**（seed 20260954）：

> A narrow alley mouth in Mapo-gu, Seoul, before dawn on a wet July night in 2004: an unmarked pale sedan standing with its headlights on, rain slanting through the beams, a low brick wall on the left, water running along the kerb, no license plate visible, no lettering, no signage, no people in the frame. Slow push toward the alley mouth and the light, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S31**（seed 20260955）：

> Three figures lit from behind by torch beams stand around a fourth in a narrow wet alley in Seoul before dawn: the three are plain-clothed and see only as silhouettes from behind, the fourth stands with his head lowered and his back to the camera, shoulders slack, rain running off his jacket, wet brick wall filling the whole background, no faces visible, no weapons raised, no violence, no lettering, no numbers. Slow push in on the group, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S32**（seed 20260956）：

> A medium shot inside a plain interrogation room at night: an anonymous Korean man of thirty-four: a long oval face with a heavy jaw, narrow hooded eyes whose outer corners turn down, thick straight brows set low, a low-bridged nose with a rounded tip, thin colourless lips, short black hair cropped close above the ears and parted flat, sallow skin, a small pale scar on the left cheekbone; he wears a dark yellow raincoat and a navy baseball cap., seated at a metal table, the raincoat off and folded on the chair behind him, hands flat on the table in front of him, head lifted and turned a little away from the lamp, a desk lamp behind the table throwing hard light across one side of his face, a cassette recorder and a glasses-case on the table; grey concrete walls, no lettering, no numbers, no files with readable text, no other person. Slow push in on him, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S33**（seed 20260957）：

> An empty holding bench in a police corridor at night: one half-open handcuff hanging from the metal rail above the bench, a door standing ajar at the end of the corridor, cold fluorescent light, a bucket and a mop against the wall, wet footprints on the floor tiles, no people, no lettering, no numbers, no notices on the walls. Slow push down the corridor toward the open door, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S34**（seed 20260958）：

> A rainy pre-dawn street near a railway station in Seoul in 2004: wet asphalt, a low station wall, tram rails in the foreground glinting with water, the red and blue glow of an unseen patrol light sweeping slowly across the road and the wall, a single distant figure walking away with no face visible, no signage, no letters, no numbers, no vehicles in frame. Slow lateral pan following the light across the wet road, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S35**（seed 20260959）：

> A two-shot at a metal table in a bare interrogation room at night: an older detective sits on the left, leaning forward with both hands flat on the table and his back and shoulders toward the camera so that his face is never visible; an anonymous Korean man of thirty-four: a long oval face with a heavy jaw, narrow hooded eyes whose outer corners turn down, thick straight brows set low, a low-bridged nose with a rounded tip, thin colourless lips, short black hair cropped close above the ears and parted flat, sallow skin, a small pale scar on the left cheekbone; he wears a dark yellow raincoat and a navy baseball cap. sits on the right with his forearms on the table and his head raised, lit hard by the desk lamp; between them several photographs lie face-down and unreadable, the wall behind is bare concrete, no lettering, no numbers, no readable text, no third person. Slow push in between the two of them, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S37**（seed 20260961）：

> A rain-soaked hillside behind an old temple on the edge of Seoul in the daytime: a line of white and blue plastic tape strung between pine trunks, three investigators in dark rain gear standing with their backs to the camera among the trees, wet undergrowth, mist between the trunks, a steel bucket and a spade on the ground, no faces visible, no body, no clothing, no lettering, no numbers. Slow lateral move across the tape line and the workers, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S38**（seed 20260962）：

> A tight crowd of reporters outside a police station in Seoul in July 2004, in the rain: only the backs of heads and shoulders, raised microphones and two television cameras on shoulders, umbrellas, wet steps underfoot, the station facade beyond blurred by rain and completely without signage, lettering, numbers or channel marks, no faces visible. Slow push in over the shoulders toward the entrance, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S39**（seed 20260963）：

> The exterior of a South Korean courthouse on a cold rainy morning in December 2004: broad stone steps running with water, a row of umbrellas held by people whose backs are turned to the camera, a police officer's shoulder in the foreground, wet flagstones reflecting grey light, the building's columns rising out of frame, no signage, no lettering, no numbers, no faces visible. Slow push in up the steps, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S40**（seed 20260964）：

> A close side view of a courtroom bench in South Korea in December 2004: a judge's hands, seen without the face, resting on a blank document on the bench, a wooden gavel standing upright beside them, a fountain pen, a thick closed law book, dark wood panelling behind, warm light from above, no readable text anywhere, no insignia, no other person. Slow push in on the hands and the gavel, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S42**（seed 20260966）：

> The outer wall of a detention centre in South Korea on a rainy evening: long grey concrete wall with coils of razor wire along the top, a tall steel gate, a single lamp on a pole, wet asphalt in the foreground, low cloud above, cold blue-grey light, no signage, no lettering, no numbers, no vehicles, no people. Slow pull back from the wall and the gate, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S44**（seed 20260968）：

> An empty prison wing in South Korea in the 2000s: a long row of cell doors with small barred openings, a caged bulb burning at the far end, a wet mop bucket and a broom against the wall, worn concrete floor, one barred window letting in grey daylight at the side, no people, no lettering, no numbers, no notices. Slow push down the empty corridor, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

**S45**（seed 20260969）：

> An empty room at night in Seoul: a dark yellow raincoat hanging from a hook on a bare wall, water still dripping from its hem onto the floorboards, rain streaming down a black window beside it with the blurred glow of the city beyond, one unshaded bulb above, nothing else in the room, no people, no lettering, no numbers, no furniture. Slow pull back into the darkness of the room, no cut, no scene change, no camera relocation, no second location, no extra people, no readable text anywhere in frame; hold on this single view for the full clip.

