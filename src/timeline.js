// timeline.js — derives the master timeline from measured narration audio.
'use strict';
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const FFPROBE = require('@ffprobe-installer/ffprobe').path;

const INTRO = 1.5;   // cold open
const GAP = 0.35;    // hard-cut flash between segments
const END = 7.0;     // end card

// narration EXACTLY as spoken in audio/narration/sN.mp3
const TEXTS = [
  '一九八二年的香港，警方追查一宗诡异的案件。他们不知道凶手是谁，更想不到，真正让警方找到凶手的，不是指纹，也不是目击证人，而是一卷送进冲印店的菲林。照片显影的那一刻，冲印店的人不寒而栗——这些照片记录的内容，是受害者遇害的过程。',
  '一九八二年二月，沙田城门河边，发现一具女性遗骸。警方靠一处特殊纹身，确认死者是二十二岁的陈凤兰。而这，只是开始。接下来几个月，陈云洁、梁秀云、十七岁的梁惠心，接连失踪遇害。四名女性，只有一个共同点：都搭乘过同一辆夜更出租车。司机，就是后来震惊香港的——林过云。',
  '但警方当时并没有锁定他。转折发生在一九八二年八月：一家冲印店接到一卷菲林，冲出的画面极其异常，店里立刻报警。警方没有马上抓人，而是布下陷阱，等取照片的人自己出现。时间一分一秒过去，终于，一个男人走进店里，要取的，正是那卷菲林。警方当场拘捕——这个男人，就是林过云。',
  '菲林只让警方怀疑他，接下来的搜查，才让案件彻底反转。在他土瓜湾的住所，警方搜出照片、录像资料，还有保存的人体组织标本，条条指向四名死者。一九八二年二月到七月，四名女性先后遇害，林过云被控四项谋杀罪。但真正的悬念才开始——他杀人的时候，到底清不清醒？',
  '一九八三年，案件审讯。多名精神科专家意见不一：有人认为他精神异常；也有人认为，他犯案时仍有自控能力。如果他控制不了自己，罪责就可能不同。但陪审团最终认定：林过云犯案时神志清醒。一九八三年四月八日，陪审团一致裁定，四项谋杀罪成立，判处死刑。',
  '但还有最后一个反转：林过云没有被执行死刑。当时香港已长期停止执行死刑，一九八四年，港督尤德将死刑改判为终身监禁。一卷菲林，让警方抓住藏在夜色里的连环杀手。而真正让人恐惧的，是凶手曾经就藏在普通人的生活里，每天开着出租车，穿梭在香港的夜色中。这，就是一九八二年轰动香港的——雨夜屠夫，林过云案。',
];

function dur(i) {
  const out = execSync(`"${FFPROBE}" -v error -show_entries format=duration -of csv=p=0 audio/narration/s${i}.mp3`).toString().trim();
  return parseFloat(out);
}

function makeLines(text) {
  // split into subtitle lines on strong punctuation; long chunks split on ，
  const chunks = text.split(/(?<=[。！？；])/);
  const lines = [];
  for (let c of chunks) {
    c = c.trim();
    if (!c) continue;
    if (c.length > 24) {
      const parts = c.split(/(?<=[，、])/);
      let buf = '';
      for (const p of parts) {
        if ((buf + p).length > 24 && buf) { lines.push(buf); buf = p; }
        else buf += p;
      }
      if (buf) lines.push(buf);
    } else lines.push(c);
  }
  return lines;
}

function build() {
  const segs = [];
  let t = INTRO;
  for (let i = 0; i < 6; i++) {
    const d = dur(i + 1);
    const lines = makeLines(TEXTS[i]).map((txt) => ({ txt, chars: txt.length }));
    const totalChars = lines.reduce((a, l) => a + l.chars, 0);
    let lt = 0.15;
    const usable = d - 0.45;
    for (const l of lines) {
      l.t0 = lt;
      l.t1 = lt + usable * (l.chars / totalChars);
      lt = l.t1;
    }
    segs.push({ i, start: t, dur: d, lines, text: TEXTS[i] });
    t += d + GAP;
  }
  const total = t - GAP + END;

  // music / impact events (t absolute)
  const ev = [];
  const E = (tt, kind) => ev.push({ t: +tt.toFixed(3), kind });
  segs.forEach((s, i) => {
    if (i > 0) { E(s.start - 1.0, 'riser'); E(s.start, 'boom'); }
  });
  E(segs[0].start + 0.35, 'sting');                 // title in
  E(segs[1].start + segs[1].dur - 3.0, 'sting');    // 林过云 name slam
  E(segs[2].start + segs[2].dur - 1.4, 'boom');     // arrest flash
  E(segs[3].start + segs[3].dur - 5.0, 'sting');    // 四项谋杀罪 stamp
  E(segs[4].start + segs[4].dur - 2.6, 'boom');     // verdict
  E(segs[5].start + 4.0, 'sting');                  // 终身监禁 stamp
  E(total - END + 0.4, 'sting');                    // final title
  ev.sort((a, b) => a.t - b.t);

  // snap flashes to the 24fps frame grid so a frame always lands exactly on the
  // flash onset (k=1); an off-grid event time would only ever produce a half flash
  const R24 = (x) => Math.round(x * 24) / 24;
  const flashes = [...new Set(
    ev.filter((e) => e.kind !== 'riser').map((e) => R24(e.t))
      .concat(segs.slice(1).map((s) => R24(s.start)))
  )].sort((a, b) => a - b);

  const T = { INTRO, GAP, END, total, segs, events: ev, flashes, fps: 24, W: 1920, H: 1080 };
  return T;
}

function write(T) {
  fs.mkdirSync('build', { recursive: true });
  fs.writeFileSync('build/timeline.json', JSON.stringify(T, null, 1));
}

module.exports = { build, write, TEXTS };
