// sample.js — render single frames at given timestamps for visual QA.
'use strict';
const fs = require('fs');
const tk = require('../src/textkit');
const fx = require('../src/fx');
const scenes = require('../src/scenes');
const timeline = require('../src/timeline');
const { LIB } = tk;

(async () => {
  tk.init();
  const T = timeline.build();
  const W = T.W, H = T.H;
  const plateFiles = [
    'assets/plates/01_rain_street.png', 'assets/plates/02_river_cordon.png',
    'assets/plates/03_darkroom.png', 'assets/plates/04_flat_search.png',
    'assets/plates/05_courtroom.png', 'assets/plates/06_taxi_night.png',
  ];
  const plates = [];
  for (const p of plateFiles) plates.push(await LIB.loadImage(p));
  const A = { plates };
  fs.mkdirSync('build/samples', { recursive: true });
  const canvas = LIB.createCanvas(W, H);
  const ctx = canvas.getContext('2d');

  const times = process.argv.slice(2).map(parseFloat);
  const segEnd = T.segs[5].start + T.segs[5].dur + T.GAP;
  for (const t of times) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    ctx.fillStyle = '#050608'; ctx.fillRect(0, 0, W, H);
    let inScene = false;
    if (t < T.INTRO) scenes.intro(ctx, t, W, H);
    else if (t >= segEnd) scenes.endcard(ctx, t - segEnd, T, W, H);
    else {
      const s = T.segs.find((s) => t < s.start + s.dur + T.GAP);
      const tt = t - s.start;
      scenes.SCENES[s.i](ctx, tt, s, T, A, W, H);
      if (tt < 0.35) fx.dim(ctx, W, H, 1 - tt / 0.35);
      const line = s.lines.find((l) => tt >= l.t0 && tt <= l.t1 + 0.15);
      if (line && tt <= s.dur) {
        const size = 46;
        const wtxt = tk.measure(ctx, line.txt, size, 'S7', 2);
        const bw = wtxt + 76, bh = 84;
        ctx.fillStyle = 'rgba(4,6,8,0.62)';
        scenes.rr(ctx, W / 2 - bw / 2, 946, bw, bh, 10); ctx.fill();
        ctx.fillStyle = '#e8323c'; ctx.fillRect(W / 2 - bw / 2, 958, 6, 60);
        tk.draw(ctx, line.txt, W / 2 + 3, 1004, { size, tag: 'S7', fill: '#f2f6f8', align: 'center', ls: 2 });
      }
      fx.hud(ctx, W, H, t, 'EP.02', scenes.LABELS[s.i]);
      inScene = true;
    }
    fx.vignette(ctx, W, H, 0.6);
    fx.grain(ctx, W, H, t);
    if (inScene) fx.scanlines(ctx, W, H, 0.04);
    const name = 'build/samples/t' + t.toFixed(2).replace('.', '_') + '.png';
    fs.writeFileSync(name, canvas.toBuffer('image/png'));
    console.log('wrote', name);
  }
})().catch((e) => { console.error(e); process.exit(1); });
