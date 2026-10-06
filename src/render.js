// render.js — renders every frame and streams raw RGBA into ffmpeg (build/video_silent.mp4)
'use strict';
const fs = require('fs');
const { spawn, execSync } = require('child_process');
const tk = require('./textkit');
const fx = require('./fx');
const scenes = require('./scenes');
const timeline = require('./timeline');
const { LIB } = tk;

const FPS = 24;
const FFMPEG = execSync('python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"').toString().trim();

(async () => {
  tk.init();
  const T = timeline.build();
  timeline.write(T);
  const W = T.W, H = T.H;

  const plateFiles = [
    'assets/plates/01_rain_street.png', 'assets/plates/02_river_cordon.png',
    'assets/plates/03_darkroom.png', 'assets/plates/04_flat_search.png',
    'assets/plates/05_courtroom.png', 'assets/plates/06_taxi_night.png',
  ];
  const plates = [];
  for (const p of plateFiles) plates.push(await LIB.loadImage(p));
  const A = { plates };

  const ff = spawn(FFMPEG, [
    '-y', '-f', 'rawvideo', '-pix_fmt', process.env.PIXFMT || 'rgba',
    '-s', `${W}x${H}`, '-r', String(FPS), '-i', 'pipe:0',
    '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
    '-pix_fmt', 'yuv420p', 'build/video_silent.mp4',
  ], { stdio: ['pipe', 'ignore', 'inherit'] });
  ff.on('exit', (c) => console.log('ffmpeg exit', c));

  const canvas = LIB.createCanvas(W, H);
  const ctx = canvas.getContext('2d');
  const N = Math.ceil(T.total * FPS);
  const segEnd = T.segs[5].start + T.segs[5].dur + T.GAP;

  const flashK = (t) => {
    let k = 0;
    for (const et of T.flashes) {
      const d = t - et;
      if (d >= 0 && d < 0.5) k = Math.max(k, Math.exp(-d * 16));
    }
    return k;
  };
  const shakeMag = (t) => {
    let m = 0;
    for (const e of T.events) {
      if (e.kind !== 'boom') continue;
      const d = t - e.t;
      if (d >= 0 && d < 0.9) m = Math.max(m, 16 * Math.exp(-d * 7));
    }
    return m;
  };

  let stdinDead = false;
  ff.stdin.on('error', () => { stdinDead = true; });
  const writeFrame = (buf) => new Promise((res) => {
    if (stdinDead) return res();
    if (ff.stdin.write(buf)) res();
    else ff.stdin.once('drain', res);
  });

  const t0 = Date.now();
  for (let f = 0; f < N; f++) {
    const t = f / FPS;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    ctx.fillStyle = '#050608';
    ctx.fillRect(0, 0, W, H);

    const m = shakeMag(t);
    const [dx, dy] = fx.shakeOffset(t, m);
    ctx.save();
    ctx.translate(dx, dy);

    let inScene = false;
    if (t < T.INTRO) {
      scenes.intro(ctx, t, W, H);
    } else if (t >= segEnd) {
      scenes.endcard(ctx, t - segEnd, T, W, H);
    } else {
      const s = T.segs.find((s) => t < s.start + s.dur + T.GAP);
      const tt = t - s.start;
      scenes.SCENES[s.i](ctx, tt, s, T, A, W, H);
      if (tt < 0.35) fx.dim(ctx, W, H, 1 - tt / 0.35);
      const line = s.lines.find((l) => tt >= l.t0 && tt <= l.t1 + 0.15);
      if (line && tt <= s.dur) {
        const size = 46;
        const wtxt = tk.measure(ctx, line.txt, size, 'S7', 2);
        const bw = wtxt + 76, bh = 84;
        const bx = W / 2 - bw / 2, by = 946;
        ctx.fillStyle = 'rgba(4,6,8,0.62)';
        scenes.rr(ctx, bx, by, bw, bh, 10); ctx.fill();
        ctx.fillStyle = '#e8323c';
        ctx.fillRect(bx, by + 12, 6, bh - 24);
        tk.draw(ctx, line.txt, W / 2 + 3, by + 58, { size, tag: 'S7', fill: '#f2f6f8', align: 'center', ls: 2 });
      }
      fx.hud(ctx, W, H, t, 'EP.02', scenes.LABELS[s.i]);
      inScene = true;
    }
    ctx.restore();

    fx.vignette(ctx, W, H, 0.6);
    fx.grain(ctx, W, H, t);
    if (inScene) fx.scanlines(ctx, W, H, 0.04);
    fx.flash(ctx, W, H, flashK(t));

    await writeFrame(Buffer.from(ctx.getImageData(0, 0, W, H).data.buffer));
    if (f % 480 === 0) {
      const el = (Date.now() - t0) / 1000;
      const rate = f > 0 ? f / el : 0;
      console.log(`frame ${f}/${N} ${el.toFixed(0)}s ${rate.toFixed(1)}fps`);
    }
  }
  ff.stdin.end();
  await new Promise((res) => ff.on('exit', res));
  console.log('RENDER DONE', N, 'frames', ((Date.now() - t0) / 1000).toFixed(1) + 's');
})().catch((e) => { console.error('RENDER FAIL', e); process.exit(1); });
