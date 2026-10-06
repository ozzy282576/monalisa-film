// fx.js — cinematic helpers: camera, particles, grain, flashes, stamps, HUD.
'use strict';
const { LIB } = require('./textkit');

// ---------- deterministic rng ----------
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function hash1(n) { const s = Math.sin(n * 127.1) * 43758.5453; return s - Math.floor(s); }

// ---------- easing ----------
const easeOut = (t) => 1 - Math.pow(1 - t, 3);
const easeIn = (t) => t * t * t;
const easeOutBack = (t) => { const c = 1.70158; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };
const clamp01 = (t) => Math.max(0, Math.min(1, t));
const seg = (t, a, b) => clamp01((t - a) / (b - a)); // 0..1 between a..b

// ---------- camera / plate ----------
// draw image cover-fit with animated zoom/pan; dims via overlay
function drawPlate(ctx, img, W, H, o) {
  const { t = 0, zoom0 = 1.08, zoom1 = 1.18, px = 0, py = 0, dur = 1 } = o || {};
  const z = zoom0 + (zoom1 - zoom0) * (dur > 0 ? clamp01(t / dur) : 0);
  const scale = Math.max(W / img.width, H / img.height) * z;
  const dw = img.width * scale, dh = img.height * scale;
  const ox = (W - dw) / 2 + px * W, oy = (H - dh) / 2 + py * H;
  ctx.drawImage(img, ox, oy, dw, dh);
}
function dim(ctx, W, H, a, color = '#000') {
  ctx.globalAlpha = a; ctx.fillStyle = color; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = 1;
}

// ---------- rain ----------
function rain(ctx, W, H, t, seed, n, alpha, wind = -0.18, speed = 1500) {
  const rnd = mulberry32(seed);
  ctx.save();
  ctx.strokeStyle = '#9fc3d8';
  ctx.lineCap = 'round';
  for (let i = 0; i < n; i++) {
    const x0 = rnd() * (W + 300) - 150;
    const y0 = rnd() * H;
    const len = 18 + rnd() * 34;
    const sp = speed * (0.6 + rnd() * 0.8);
    const ph = rnd() * 10;
    const y = ((y0 + t * sp) % (H + 80)) - 40;
    const x = x0 + wind * (y - y0) + Math.sin(t * 0.7 + ph) * 6;
    ctx.globalAlpha = alpha * (0.35 + 0.65 * hash1(i + seed));
    ctx.lineWidth = 1 + rnd() * 1.4;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + wind * len, y + len);
    ctx.stroke();
  }
  ctx.restore();
  ctx.globalAlpha = 1;
}

// ---------- grain / vignette / scanlines ----------
let grainTiles = null;
function makeGrain() {
  grainTiles = [];
  const rnd = mulberry32(777);
  for (let k = 0; k < 4; k++) {
    const c = LIB.createCanvas(320, 320);
    const x = c.getContext('2d');
    const img = x.createImageData(320, 320);
    for (let i = 0; i < img.data.length; i += 4) {
      const v = Math.floor(rnd() * 255);
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
      img.data[i + 3] = rnd() < 0.5 ? 14 : 0;
    }
    x.putImageData(img, 0, 0);
    grainTiles.push(c);
  }
}
function grain(ctx, W, H, t) {
  if (!grainTiles) makeGrain();
  const tile = grainTiles[Math.floor(t * 24) % 4];
  const ox = -Math.floor(hash1(Math.floor(t * 24)) * 320);
  const oy = -Math.floor(hash1(Math.floor(t * 24) + 9) * 320);
  ctx.save();
  for (let y = oy; y < H; y += 320)
    for (let x = ox; x < W; x += 320)
      ctx.drawImage(tile, x, y);
  ctx.restore();
}
let vig = null;
function vignette(ctx, W, H, strength = 0.62) {
  if (!vig) {
    vig = LIB.createCanvas(W, H);
    const x = vig.getContext('2d');
    const g = x.createRadialGradient(W / 2, H / 2, H * 0.42, W / 2, H / 2, H * 0.95);
    g.addColorStop(0, 'rgba(0,0,0,0)');
    g.addColorStop(1, 'rgba(0,0,0,0.92)');
    x.fillStyle = g; x.fillRect(0, 0, W, H);
  }
  ctx.save();
  ctx.globalAlpha = strength;
  ctx.drawImage(vig, 0, 0);
  ctx.restore();
  ctx.globalAlpha = 1;
}
function scanlines(ctx, W, H, alpha = 0.05) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.fillStyle = '#000';
  for (let y = 0; y < H; y += 4) ctx.fillRect(0, y, W, 1);
  ctx.restore();
  ctx.globalAlpha = 1;
}

// ---------- flashes / shake ----------
function flash(ctx, W, H, k) {
  if (k <= 0) return;
  ctx.globalAlpha = Math.min(1, k);
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, W, H);
  ctx.globalAlpha = 1;
}
function shakeOffset(t, mag, seed = 3) {
  if (mag <= 0) return [0, 0];
  return [
    (hash1(Math.floor(t * 24) * 1.7 + seed) - 0.5) * 2 * mag,
    (hash1(Math.floor(t * 24) * 2.3 + seed + 5) - 0.5) * 2 * mag,
  ];
}

// ---------- stamp (slam-in seal) ----------
function stamp(ctx, text, x, y, size, t, appear, opts = {}) {
  const a = seg(t, appear, appear + 0.05);
  if (a <= 0) return;
  const k = easeOutBack(seg(t, appear, appear + 0.22));
  const scale = 2.4 - 1.4 * k;
  const rot = (opts.rot !== undefined ? opts.rot : -0.06);
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rot);
  ctx.scale(scale, scale);
  ctx.globalAlpha = a * (opts.alpha ?? 0.94);
  const color = opts.color || '#d81f2a';
  const { draw, measure } = require('./textkit');
  const pad = size * 0.35;
  const w = measure(ctx, text, size, 'S7', size * 0.08) + pad * 2;
  const h = size * 1.5;
  ctx.strokeStyle = color;
  ctx.lineWidth = size * 0.09;
  ctx.strokeRect(-w / 2, -h / 2, w, h);
  ctx.strokeStyle = color;
  ctx.lineWidth = size * 0.03;
  ctx.strokeRect(-w / 2 + size * 0.12, -h / 2 + size * 0.12, w - size * 0.24, h - size * 0.24);
  draw(ctx, text, 0, size * 0.36, { size, tag: 'S7', fill: color, align: 'center', ls: size * 0.08 });
  ctx.restore();
  ctx.globalAlpha = 1;
}

// ---------- typewriter ----------
function typeText(ctx, text, x, y, opts, t, appear, cps = 22) {
  const n = Math.floor((t - appear) * cps);
  if (n <= 0) return;
  const { draw } = require('./textkit');
  draw(ctx, text.slice(0, Math.min(text.length, n)), x, y, { ...opts, alpha: (opts.alpha ?? 1) });
}

// ---------- HUD frame ----------
function hud(ctx, W, H, t, episode, label) {
  const { draw } = require('./textkit');
  ctx.save();
  // corner brackets
  ctx.strokeStyle = 'rgba(216,31,42,0.75)';
  ctx.lineWidth = 3;
  const L = 34, m = 26;
  const corners = [[m, m, 1, 1], [W - m, m, -1, 1], [m, H - m, 1, -1], [W - m, H - m, -1, -1]];
  for (const [cx, cy, sx, sy] of corners) {
    ctx.beginPath();
    ctx.moveTo(cx + sx * L, cy);
    ctx.lineTo(cx, cy);
    ctx.lineTo(cx, cy + sy * L);
    ctx.stroke();
  }
  // top-left brand
  ctx.globalAlpha = 0.9;
  draw(ctx, '悬案档案', m + 18, m + 44, { size: 30, tag: 'S7', fill: '#e8323c', ls: 4 });
  const bw = require('./textkit').measure(ctx, '悬案档案', 30, 'S7', 4);
  draw(ctx, 'COLD CASE FILES · ' + episode, m + 18 + bw + 22, m + 42, { size: 20, tag: 'S4', fill: '#8fa1ae', ls: 2 });
  // bottom-right timecode
  const f = Math.floor(t * 24);
  const ff = String(f % 24).padStart(2, '0');
  const ss = String(Math.floor(t) % 60).padStart(2, '0');
  const mm = String(Math.floor(t / 60) % 60).padStart(2, '0');
  ctx.font = '26px "DejaVu Sans Mono"';
  ctx.fillStyle = 'rgba(200,214,224,0.8)';
  ctx.textAlign = 'right';
  ctx.fillText('00:' + mm + ':' + ss + ':' + ff, W - m - 18, H - m - 22);
  ctx.textAlign = 'left';
  // bottom-left scene label
  ctx.globalAlpha = 0.75;
  draw(ctx, label, m + 18, H - m - 22, { size: 22, tag: 'S4', fill: '#9fb0bd', ls: 2 });
  ctx.restore();
  ctx.globalAlpha = 1;
}

// ---------- evidence card ----------
function card(ctx, x, y, w, h, t, appear, drawFn) {
  const a = seg(t, appear, appear + 0.12);
  if (a <= 0) return;
  const slide = (1 - easeOut(seg(t, appear, appear + 0.45))) * 60;
  ctx.save();
  ctx.translate(x, y + slide);
  ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(10,12,15,0.88)';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = 'rgba(216,31,42,0.8)';
  ctx.lineWidth = 2;
  ctx.strokeRect(0, 0, w, h);
  ctx.strokeStyle = 'rgba(216,31,42,0.35)';
  ctx.strokeRect(6, 6, w - 12, h - 12);
  drawFn(ctx, w, h, t, appear);
  ctx.restore();
  ctx.globalAlpha = 1;
}

module.exports = {
  mulberry32, hash1, easeOut, easeIn, easeOutBack, clamp01, seg,
  drawPlate, dim, rain, grain, vignette, scanlines, flash, shakeOffset,
  stamp, typeText, hud, card,
};
