// scenes.js — the six animated scenes + intro + end card.
'use strict';
const fx = require('./fx');
const tk = require('./textkit');
const { seg, easeOut, easeOutBack, clamp01, hash1 } = fx;

function rr(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/* ============ INTRO cold open ============ */
function intro(ctx, t, W, H) {
  ctx.fillStyle = '#050608'; ctx.fillRect(0, 0, W, H);
  // glitch bars
  for (let i = 0; i < 7; i++) {
    const y = hash1(i * 3.3) * H;
    const on = hash1(i + Math.floor(t * 12)) > 0.5;
    if (!on) continue;
    ctx.globalAlpha = 0.12;
    ctx.fillStyle = i % 2 ? '#d81f2a' : '#20303c';
    ctx.fillRect(0, y, W, 3 + hash1(i) * 26);
  }
  ctx.globalAlpha = 1;
  const a = seg(t, 0.15, 0.5);
  const k = easeOutBack(seg(t, 0.15, 0.6));
  ctx.save();
  ctx.translate(W / 2, H / 2 - 40);
  ctx.scale(0.8 + 0.2 * k, 0.8 + 0.2 * k);
  ctx.globalAlpha = a;
  tk.draw(ctx, '悬 案 档 案', 0, 0, { size: 132, tag: 'R7', fill: '#e8323c', align: 'center', ls: 6 });
  ctx.restore();
  ctx.globalAlpha = seg(t, 0.55, 0.85);
  tk.draw(ctx, 'COLD CASE FILES · EP.02', W / 2, H / 2 + 60, { size: 34, tag: 'S4', fill: '#8fa1ae', align: 'center', ls: 8 });
  tk.draw(ctx, '一九八二 · 香港', W / 2, H / 2 + 130, { size: 44, tag: 'S7', fill: '#d7dee4', align: 'center', ls: 10 });
  ctx.globalAlpha = 1;
}

/* ============ SCENE 1 — rain street / the film roll ============ */
function scene1(ctx, tt, s, T, A, W, H) {
  fx.drawPlate(ctx, A.plates[0], W, H, { t: tt, dur: s.dur, zoom0: 1.08, zoom1: 1.22, py: 0.02 });
  fx.dim(ctx, W, H, 0.42);
  // neon flicker
  const fl = hash1(Math.floor(tt * 9)) > 0.82 ? 0.10 : 0.04;
  ctx.globalAlpha = fl; ctx.fillStyle = '#ff2b3a'; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = 1;
  fx.rain(ctx, W, H, tt, 11, 150, 0.4);
  // big title with slice-in
  const ts = seg(tt, 0.25, 1.1);
  if (ts > 0) {
    ctx.save();
    const slices = 6;
    for (let i = 0; i < slices; i++) {
      const off = (1 - easeOut(ts)) * (hash1(i * 7.7) - 0.5) * 260;
      const sy = 260 + (i * 190) / slices;
      ctx.save();
      ctx.beginPath(); ctx.rect(0, sy, W, 190 / slices + 1); ctx.clip();
      tk.draw(ctx, '一卷菲林', W / 2 + off, 430, { size: 185, tag: 'R7', fill: '#f2f5f7', align: 'center', ls: 18 });
      ctx.restore();
    }
    ctx.restore();
    ctx.globalAlpha = seg(tt, 1.15, 1.5);
    tk.draw(ctx, '揭开香港最恐怖的连环杀人案', W / 2, 520, { size: 46, tag: 'S7', fill: '#e8323c', align: 'center', ls: 6 });
    ctx.globalAlpha = 1;
  }
  // developing photo at the end
  const dp = seg(tt, s.dur - 5.0, s.dur - 3.2);
  if (dp > 0) {
    const w = 460, h = 320;
    const x = W / 2 - w / 2, y = 560;
    ctx.save();
    ctx.translate(W / 2, y + h / 2);
    ctx.rotate(-0.05 + 0.02 * Math.sin(tt));
    ctx.globalAlpha = dp;
    ctx.fillStyle = '#e9e6df'; ctx.fillRect(-w / 2 - 16, -h / 2 - 16, w + 32, h + 40);
    ctx.fillStyle = '#1a0d0f'; ctx.fillRect(-w / 2, -h / 2, w, h);
    // abstract developing shapes (no gore: blurred dark forms)
    const dev = seg(tt, s.dur - 4.4, s.dur - 2.4);
    ctx.globalAlpha = dp * dev;
    const g = ctx.createRadialGradient(-60, 20, 10, -60, 20, 150);
    g.addColorStop(0, 'rgba(150,20,30,0.85)'); g.addColorStop(1, 'rgba(20,5,8,0)');
    ctx.fillStyle = g; ctx.fillRect(-w / 2, -h / 2, w, h);
    const g2 = ctx.createRadialGradient(90, -40, 8, 90, -40, 120);
    g2.addColorStop(0, 'rgba(190,180,170,0.5)'); g2.addColorStop(1, 'rgba(20,5,8,0)');
    ctx.fillStyle = g2; ctx.fillRect(-w / 2, -h / 2, w, h);
    ctx.restore();
    ctx.globalAlpha = seg(tt, s.dur - 3.4, s.dur - 3.0);
    tk.draw(ctx, '照片记录的内容，令人不寒而栗', W / 2, 950, { size: 44, tag: 'S7', fill: '#ffd7d9', align: 'center', ls: 4 });
    ctx.globalAlpha = 1;
  }
}

/* ============ SCENE 2 — victims & the taxi link ============ */
function scene2(ctx, tt, s, T, A, W, H) {
  fx.drawPlate(ctx, A.plates[1], W, H, { t: tt, dur: s.dur, zoom0: 1.1, zoom1: 1.16, px: -0.02 + 0.04 * (tt / s.dur) });
  fx.dim(ctx, W, H, 0.5);
  // drifting fog
  for (let i = 0; i < 5; i++) {
    const x = ((hash1(i * 9.1) * W + tt * (18 + i * 7)) % (W + 700)) - 350;
    const y = 180 + i * 160;
    const g = ctx.createRadialGradient(x, y, 20, x, y, 320);
    g.addColorStop(0, 'rgba(160,175,185,0.05)'); g.addColorStop(1, 'rgba(160,175,185,0)');
    ctx.fillStyle = g; ctx.fillRect(x - 320, y - 320, 640, 640);
  }
  fx.stamp(ctx, '1982.02 沙田 · 城门河', 430, 200, 40, tt, 0.4, { rot: -0.03 });
  const victims = [
    { name: '陈凤兰', age: '22岁', at: 2.0 },
    { name: '陈云洁', age: '', at: 5.0 },
    { name: '梁秀云', age: '', at: 7.5 },
    { name: '梁惠心', age: '17岁', at: 10.0 },
  ];
  const cw = 300, ch = 170, gapx = 60;
  const x0 = (W - (4 * cw + 3 * gapx)) / 2;
  victims.forEach((v, i) => {
    const x = x0 + i * (cw + gapx), y = 300;
    fx.card(ctx, x, y, cw, ch, tt, v.at, (c, w, h) => {
      tk.draw(c, v.name, w / 2, 78, { size: 56, tag: 'S7', fill: '#eef2f4', align: 'center', ls: 6 });
      tk.draw(c, (v.age ? v.age + ' · ' : '') + '失踪遇害', w / 2, 132, { size: 26, tag: 'S4', fill: '#d8878c', align: 'center', ls: 2 });
      // red X draw-on
      const p = seg(tt, v.at + 0.5, v.at + 1.1);
      if (p > 0) {
        c.strokeStyle = 'rgba(216,31,42,0.85)'; c.lineWidth = 6; c.lineCap = 'round';
        c.beginPath(); c.moveTo(18, 18);
        c.lineTo(18 + (w - 36) * Math.min(1, p * 2), 18 + (h - 36) * Math.min(1, p * 2));
        c.stroke();
        if (p > 0.5) {
          c.beginPath(); c.moveTo(w - 18, 18);
          c.lineTo(w - 18 - (w - 36) * (p - 0.5) * 2, 18 + (h - 36) * (p - 0.5) * 2);
          c.stroke();
        }
      }
    });
  });
  // taxi node + converging dashed lines
  const tx = W / 2, ty = 700;
  const link = seg(tt, 13.0, 15.0);
  if (link > 0) {
    ctx.save();
    ctx.strokeStyle = 'rgba(232,50,60,' + (0.7 * link) + ')';
    ctx.lineWidth = 3; ctx.setLineDash([12, 10]);
    ctx.lineDashOffset = -tt * 60;
    victims.forEach((v, i) => {
      const x = x0 + i * (cw + gapx) + cw / 2;
      ctx.globalAlpha = link;
      ctx.beginPath(); ctx.moveTo(x, 470 + 12); ctx.lineTo(tx, ty - 40); ctx.stroke();
    });
    ctx.setLineDash([]);
    // taxi glyph
    ctx.globalAlpha = link;
    ctx.fillStyle = '#101418';
    rr(ctx, tx - 90, ty - 30, 180, 52, 12); ctx.fill();
    rr(ctx, tx - 52, ty - 62, 104, 40, 10); ctx.fill();
    ctx.strokeStyle = '#e8323c'; ctx.lineWidth = 3; rr(ctx, tx - 90, ty - 30, 180, 52, 12); ctx.stroke();
    ctx.fillStyle = '#ffd23c';
    ctx.globalAlpha = link * (0.6 + 0.4 * Math.sin(tt * 6));
    ctx.fillRect(tx - 20, ty - 74, 40, 12);
    ctx.globalAlpha = link;
    ctx.fillStyle = '#0c0e10';
    ctx.beginPath(); ctx.arc(tx - 52, ty + 24, 15, 0, 7); ctx.fill();
    ctx.beginPath(); ctx.arc(tx + 52, ty + 24, 15, 0, 7); ctx.fill();
    ctx.restore();
    ctx.globalAlpha = 1;
  }
  if (tt > 15.2) {
    ctx.globalAlpha = seg(tt, 15.2, 15.6);
    tk.draw(ctx, '共同点 · 同一辆夜更出租车', W / 2, 800, { size: 42, tag: 'S7', fill: '#ffd7d9', align: 'center', ls: 4 });
    ctx.globalAlpha = 1;
  }
  // name slam
  const slamAt = s.dur - 3.0;
  if (tt > slamAt) {
    const k = easeOutBack(seg(tt, slamAt, slamAt + 0.3));
    ctx.save();
    ctx.translate(W / 2, 930);
    ctx.scale(2.6 - 1.6 * k, 2.6 - 1.6 * k);
    ctx.globalAlpha = seg(tt, slamAt, slamAt + 0.1);
    ctx.fillStyle = 'rgba(216,31,42,0.14)';
    ctx.fillRect(-460, -80, 920, 130);
    tk.draw(ctx, '林 过 云', 0, 20, { size: 96, tag: 'R7', fill: '#e8323c', align: 'center', ls: 10 });
    ctx.restore();
    ctx.globalAlpha = 1;
  }
}

/* ============ SCENE 3 — darkroom / the trap ============ */
function scene3(ctx, tt, s, T, A, W, H) {
  fx.drawPlate(ctx, A.plates[2], W, H, { t: tt, dur: s.dur, zoom0: 1.06, zoom1: 1.18 });
  ctx.globalAlpha = 0.14 + 0.08 * Math.sin(tt * 2.2);
  ctx.fillStyle = '#ff1a26'; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = 1;
  // scrolling film strip
  ctx.save();
  ctx.fillStyle = 'rgba(5,6,8,0.9)'; ctx.fillRect(0, 60, W, 120);
  ctx.fillStyle = '#0a0c0e';
  const off = (tt * 220) % 90;
  for (let x = -90; x < W + 90; x += 90) {
    ctx.fillStyle = 'rgba(20,24,28,1)'; ctx.fillRect(x - off, 74, 62, 92);
    ctx.fillStyle = 'rgba(230,235,240,0.5)';
    for (let h = 0; h < 4; h++) { ctx.fillRect(x - off + 8, 64 + 4 + h * 0, 8, 8); }
    ctx.fillStyle = 'rgba(230,235,240,0.35)';
    ctx.fillRect(x - off + 6, 66, 10, 8); ctx.fillRect(x - off + 46, 66, 10, 8);
    ctx.fillRect(x - off + 6, 166, 10, 8); ctx.fillRect(x - off + 46, 166, 10, 8);
  }
  ctx.font = '22px "DejaVu Sans Mono"'; ctx.fillStyle = 'rgba(232,50,60,0.8)';
  ctx.fillText('KODAK  SAFETY  FILM  ·  1982-08', 40, 226);
  ctx.restore();
  // developing prints
  for (let i = 0; i < 3; i++) {
    const at = 1.6 + i * 1.6;
    const a = seg(tt, at, at + 0.5);
    if (a <= 0) continue;
    const x = 480 + i * 340, y = 430, w = 250, h = 190;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate((i - 1) * 0.05 + 0.01 * Math.sin(tt + i));
    ctx.globalAlpha = a;
    ctx.fillStyle = '#ddd8cf'; ctx.fillRect(-12, -12, w + 24, h + 34);
    ctx.fillStyle = '#150a0c'; ctx.fillRect(0, 0, w, h);
    const dev = seg(tt, at + 0.6, at + 3.0);
    ctx.globalAlpha = a * (0.25 + 0.75 * dev);
    const g = ctx.createRadialGradient(w / 2 + (i - 1) * 40, h / 2, 8, w / 2, h / 2, 130);
    g.addColorStop(0, 'rgba(190,30,40,' + (0.7 * dev) + ')');
    g.addColorStop(1, 'rgba(10,4,6,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }
  ctx.globalAlpha = 1;
  // alarm chip
  if (tt > 7.5) {
    ctx.save();
    ctx.globalAlpha = seg(tt, 7.5, 7.9) * (0.75 + 0.25 * Math.sin(tt * 8));
    tk.draw(ctx, '冲印店 · 报警', W - 420, 340, { size: 44, tag: 'S7', fill: '#ff5560', ls: 4 });
    ctx.restore();
    ctx.globalAlpha = 1;
  }
  // trap: waiting + silhouette enters
  if (tt > 9.5 && tt < s.dur - 1.2) {
    ctx.globalAlpha = 0.85;
    tk.draw(ctx, '警 方 布 下 陷 阱', W / 2, 760, { size: 52, tag: 'S7', fill: '#d7dee4', align: 'center', ls: 12 });
    const ticks = Math.floor((tt - 9.5) * 2);
    tk.draw(ctx, '等 他 出 现 ' + '·'.repeat(Math.min(6, ticks)), W / 2, 830, { size: 30, tag: 'S4', fill: '#8fa1ae', align: 'center', ls: 4 });
    ctx.globalAlpha = 1;
  }
  const walk = seg(tt, s.dur - 6.5, s.dur - 2.0);
  if (walk > 0 && tt < s.dur - 1.0) {
    const x = W - 200 - walk * 500;
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.85)';
    ctx.beginPath(); ctx.arc(x, 700, 26, 0, 7); ctx.fill();
    rr(ctx, x - 34, 726, 68, 150, 20); ctx.fill();
    ctx.restore();
  }
  if (tt > s.dur - 1.4) {
    fx.stamp(ctx, '拘 捕', W / 2, 880, 92, tt, s.dur - 1.35, { rot: -0.05 });
  }
}

/* ============ SCENE 4 — the search ============ */
function scene4(ctx, tt, s, T, A, W, H) {
  fx.drawPlate(ctx, A.plates[3], W, H, { t: tt, dur: s.dur, zoom0: 1.08, zoom1: 1.15, px: 0.02 - 0.04 * (tt / s.dur) });
  fx.dim(ctx, W, H, 0.45);
  // sweeping flashlight cone
  const ang = -0.5 + 0.9 * (0.5 + 0.5 * Math.sin(tt * 0.9));
  ctx.save();
  ctx.translate(-100, 300);
  ctx.rotate(ang);
  const lg = ctx.createLinearGradient(0, 0, 2400, 0);
  lg.addColorStop(0, 'rgba(240,246,255,0.28)');
  lg.addColorStop(1, 'rgba(240,246,255,0)');
  ctx.fillStyle = lg;
  ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(2400, -260); ctx.lineTo(2400, 260); ctx.closePath(); ctx.fill();
  ctx.restore();
  // evidence tags
  const tags = [['证物 A · 照片', 2.0], ['证物 B · 录像资料', 4.2], ['证物 C · 人体组织标本', 6.4]];
  tags.forEach(([txt, at], i) => {
    const a = seg(tt, at, at + 0.2);
    if (a <= 0) return;
    const x = 300, y = 330 + i * 96;
    ctx.save();
    ctx.globalAlpha = a;
    ctx.translate(x, y);
    const pop = easeOutBack(seg(tt, at, at + 0.35));
    ctx.scale(0.7 + 0.3 * pop, 0.7 + 0.3 * pop);
    ctx.fillStyle = 'rgba(8,10,12,0.85)';
    rr(ctx, 0, -52, 560, 74, 8); ctx.fill();
    ctx.strokeStyle = '#e8323c'; ctx.lineWidth = 2; rr(ctx, 0, -52, 560, 74, 8); ctx.stroke();
    tk.draw(ctx, txt, 26, 0, { size: 40, tag: 'S7', fill: '#f0d9da', ls: 3 });
    ctx.restore();
    ctx.globalAlpha = 1;
  });
  // timeline bar
  const bt = seg(tt, 10.0, 12.0);
  if (bt > 0) {
    const x0 = 320, x1 = W - 320, y = 700;
    ctx.save();
    ctx.globalAlpha = bt;
    ctx.strokeStyle = 'rgba(200,214,224,0.7)'; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x0 + (x1 - x0) * bt, y); ctx.stroke();
    const months = ['02', '04', '05', '07'];
    months.forEach((m, i) => {
      const mx = x0 + (x1 - x0) * (0.06 + i * 0.29);
      const on = seg(tt, 10.4 + i * 0.5, 10.7 + i * 0.5);
      if (on <= 0) return;
      ctx.fillStyle = '#e8323c';
      ctx.beginPath(); ctx.arc(mx, y, 12 * on, 0, 7); ctx.fill();
      ctx.globalAlpha = bt * on;
      tk.draw(ctx, '1982.' + m + ' 遇害', mx, y + 56, { size: 26, tag: 'S4', fill: '#c8d6e0', align: 'center', ls: 1 });
      ctx.globalAlpha = bt;
    });
    ctx.restore();
    ctx.globalAlpha = 1;
  }
  fx.stamp(ctx, '四项谋杀罪', W - 430, 330, 64, tt, s.dur - 5.0, { rot: -0.07 });
  if (tt > s.dur - 3.4) {
    fx.typeText(ctx, '他杀人的时候，到底清不清醒？', W / 2, 900,
      { size: 52, tag: 'S7', fill: '#f4f7f9', align: 'center', ls: 4 }, tt, s.dur - 3.4, 16);
  }
}

/* ============ SCENE 5 — the trial ============ */
function scene5(ctx, tt, s, T, A, W, H) {
  fx.drawPlate(ctx, A.plates[4], W, H, { t: tt, dur: s.dur, zoom0: 1.06, zoom1: 1.14 });
  fx.dim(ctx, W, H, 0.4);
  // dust motes
  for (let i = 0; i < 40; i++) {
    const x = (hash1(i * 1.3) * W + tt * 12 * (0.4 + hash1(i))) % W;
    const y = (hash1(i * 2.7) * H + Math.sin(tt * 0.5 + i) * 30 + tt * 6) % H;
    ctx.globalAlpha = 0.05 + 0.08 * hash1(i * 5);
    ctx.fillStyle = '#ffe9c9';
    ctx.fillRect(x, y, 2.5, 2.5);
  }
  ctx.globalAlpha = 1;
  // scales of justice draw-on
  const sc = seg(tt, 0.8, 2.2);
  if (sc > 0) {
    ctx.save();
    ctx.translate(W / 2, 250);
    ctx.strokeStyle = 'rgba(232,190,120,' + (0.9 * sc) + ')';
    ctx.lineWidth = 5; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(0, -70 * sc); ctx.lineTo(0, 60 * sc); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-150 * sc, -40 * sc); ctx.lineTo(150 * sc, -40 * sc); ctx.stroke();
    const sway = Math.sin(tt * 1.6) * 12 * sc;
    ctx.beginPath(); ctx.arc(-150 * sc, 10 + sway, 46 * sc, 0, Math.PI); ctx.stroke();
    ctx.beginPath(); ctx.arc(150 * sc, 10 - sway, 46 * sc, 0, Math.PI); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-150 * sc, -40 * sc); ctx.lineTo(-150 * sc, 10 + sway); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(150 * sc, -40 * sc); ctx.lineTo(150 * sc, 10 - sway); ctx.stroke();
    ctx.restore();
  }
  // expert opinions
  const o1 = seg(tt, 3.2, 3.6), o2 = seg(tt, 5.2, 5.6);
  if (o1 > 0) {
    ctx.save(); ctx.globalAlpha = o1 * (0.8 + 0.2 * Math.sin(tt * 10));
    ctx.fillStyle = 'rgba(60,70,80,0.8)'; rr(ctx, 260, 430, 470, 90, 10); ctx.fill();
    tk.draw(ctx, '专家甲 · 精神异常', 495, 490, { size: 40, tag: 'S4', fill: '#aebcc6', align: 'center', ls: 2 });
    ctx.restore(); ctx.globalAlpha = 1;
  }
  if (o2 > 0) {
    ctx.save(); ctx.globalAlpha = o2 * (0.8 + 0.2 * Math.sin(tt * 10 + 2));
    ctx.fillStyle = 'rgba(120,20,28,0.8)'; rr(ctx, W - 730, 430, 470, 90, 10); ctx.fill();
    tk.draw(ctx, '专家乙 · 仍有自控力', W - 495, 490, { size: 40, tag: 'S4', fill: '#ffd7d9', align: 'center', ls: 2 });
    ctx.restore(); ctx.globalAlpha = 1;
  }
  // jury tally
  const jt = seg(tt, 9.0, 12.0);
  if (jt > 0) {
    const n = Math.min(7, Math.floor((tt - 9.0) / 0.35) + 1);
    tk.draw(ctx, '陪审团', W / 2, 640, { size: 34, tag: 'S4', fill: '#8fa1ae', align: 'center', ls: 6 });
    for (let i = 0; i < 7; i++) {
      const x = W / 2 - 210 + i * 70;
      ctx.save();
      if (i < n) {
        ctx.fillStyle = '#e8323c';
        ctx.beginPath(); ctx.arc(x, 690, 16, 0, 7); ctx.fill();
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(x - 7, 690); ctx.lineTo(x - 2, 696); ctx.lineTo(x + 8, 682); ctx.stroke();
      } else {
        ctx.strokeStyle = 'rgba(200,214,224,0.4)'; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.arc(x, 690, 16, 0, 7); ctx.stroke();
      }
      ctx.restore();
    }
  }
  const vAt = s.dur - 2.6;
  if (tt > vAt) {
    ctx.save();
    ctx.globalAlpha = seg(tt, vAt, vAt + 0.15);
    tk.draw(ctx, '一致裁定 · 谋杀罪成立', W / 2, 800, { size: 50, tag: 'S7', fill: '#f4f7f9', align: 'center', ls: 6 });
    ctx.restore(); ctx.globalAlpha = 1;
    fx.stamp(ctx, '死 刑', 430, 850, 96, tt, vAt + 0.15, { rot: -0.05 });
    ctx.globalAlpha = seg(tt, vAt + 0.4, vAt + 0.8);
    tk.draw(ctx, '1983.4.8', W - 420, 880, { size: 34, tag: 'S4', fill: '#c8d6e0', ls: 2 });
    ctx.globalAlpha = 1;
  }
}

/* ============ SCENE 6 — commutation & end title ============ */
function scene6(ctx, tt, s, T, A, W, H) {
  fx.drawPlate(ctx, A.plates[5], W, H, { t: tt, dur: s.dur, zoom0: 1.05, zoom1: 1.15 });
  fx.dim(ctx, W, H, 0.45);
  // windshield droplets
  for (let i = 0; i < 60; i++) {
    const x = hash1(i * 3.1) * W;
    const sp = 30 + hash1(i * 7.7) * 90;
    const y = (hash1(i * 5.3) * H + tt * sp) % H;
    ctx.globalAlpha = 0.10 + 0.12 * hash1(i);
    ctx.fillStyle = '#bcd6e4';
    ctx.beginPath(); ctx.arc(x, y, 2 + hash1(i * 11) * 2.5, 0, 7); ctx.fill();
    ctx.fillRect(x - 0.7, y - 14 - hash1(i) * 20, 1.4, 14 + hash1(i) * 20);
  }
  ctx.globalAlpha = 1;
  // wiper sweep
  const wp = (tt % 3.2) / 3.2;
  const wa = -0.9 + 1.8 * (0.5 - 0.5 * Math.cos(wp * Math.PI * 2));
  ctx.save();
  ctx.translate(W / 2, H + 260);
  ctx.rotate(wa * 0.5);
  ctx.strokeStyle = 'rgba(5,6,8,0.8)'; ctx.lineWidth = 14; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(0, -400); ctx.lineTo(0, -1150); ctx.stroke();
  ctx.restore();
  // commutation
  if (tt > 1.2) {
    ctx.globalAlpha = seg(tt, 1.2, 1.6);
    tk.draw(ctx, '1984 · 港督尤德', W / 2, 300, { size: 40, tag: 'S4', fill: '#8fa1ae', align: 'center', ls: 6 });
    ctx.globalAlpha = 1;
  }
  if (tt > 2.2) {
    tk.draw(ctx, '死刑', W / 2 - 190, 430, { size: 74, tag: 'S7', fill: '#7d8890', align: 'center', ls: 4 });
    const st = seg(tt, 2.6, 3.2);
    if (st > 0) {
      ctx.strokeStyle = '#e8323c'; ctx.lineWidth = 7; ctx.lineCap = 'round';
      ctx.globalAlpha = st;
      ctx.beginPath(); ctx.moveTo(W / 2 - 265, 445); ctx.lineTo(W / 2 - 265 + 150 * st, 445 - 60 * st); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(W / 2 - 265, 385); ctx.lineTo(W / 2 - 265 + 150 * st, 385 + 60 * st); ctx.stroke();
      ctx.globalAlpha = 1;
    }
    tk.draw(ctx, '→', W / 2, 430, { size: 60, tag: 'S4', fill: '#c8d6e0', align: 'center' });
  }
  fx.stamp(ctx, '终身监禁', W / 2 + 250, 420, 76, tt, 4.0, { rot: -0.06 });
  // closing lines
  const c1 = seg(tt, 8.0, 9.0), c2 = seg(tt, 11.0, 12.0);
  if (c1 > 0) { ctx.globalAlpha = c1; tk.draw(ctx, '真正让人恐惧的，从来不只是案件本身', W / 2, 640, { size: 44, tag: 'S4', fill: '#d7dee4', align: 'center', ls: 3 }); ctx.globalAlpha = 1; }
  if (c2 > 0) { ctx.globalAlpha = c2; tk.draw(ctx, '而是凶手，曾经就藏在普通人的夜色里', W / 2, 710, { size: 44, tag: 'S4', fill: '#d7dee4', align: 'center', ls: 3 }); ctx.globalAlpha = 1; }
  // final title card
  const ft = seg(tt, s.dur - 3.2, s.dur - 2.2);
  if (ft > 0) {
    fx.dim(ctx, W, H, 0.65 * ft);
    ctx.save();
    ctx.globalAlpha = ft;
    const glow = 12 + 6 * Math.sin(tt * 2.4);
    ctx.shadowColor = 'rgba(232,50,60,0.8)'; ctx.shadowBlur = glow;
    tk.draw(ctx, '雨夜屠夫', W / 2, H / 2 - 20, { size: 170, tag: 'R7', fill: '#e8323c', align: 'center', ls: 24 });
    ctx.shadowBlur = 0;
    tk.draw(ctx, '林过云案 · 1982 香港', W / 2, H / 2 + 70, { size: 46, tag: 'S7', fill: '#e6ecef', align: 'center', ls: 8 });
    tk.draw(ctx, '悬案档案 · 下案见', W / 2, H / 2 + 150, { size: 30, tag: 'S4', fill: '#8fa1ae', align: 'center', ls: 6 });
    ctx.restore();
    ctx.globalAlpha = 1;
  }
}

/* ============ END CARD ============ */
function endcard(ctx, tt, T, W, H) {
  ctx.fillStyle = '#050608'; ctx.fillRect(0, 0, W, H);
  const fade = tt > T.END - 1.2 ? 1 - seg(tt, T.END - 1.2, T.END) : 1;
  ctx.save();
  ctx.globalAlpha = fade;
  ctx.shadowColor = 'rgba(232,50,60,0.7)'; ctx.shadowBlur = 18;
  tk.draw(ctx, '雨夜屠夫', W / 2, H / 2 - 60, { size: 170, tag: 'R7', fill: '#e8323c', align: 'center', ls: 24 });
  ctx.shadowBlur = 0;
  tk.draw(ctx, '林过云案 · 1982 香港', W / 2, H / 2 + 30, { size: 46, tag: 'S7', fill: '#e6ecef', align: 'center', ls: 8 });
  ctx.globalAlpha = fade * (0.6 + 0.4 * Math.sin(tt * 3));
  tk.draw(ctx, '关注「悬案档案」 · 下案见', W / 2, H / 2 + 130, { size: 34, tag: 'S4', fill: '#8fa1ae', align: 'center', ls: 6 });
  ctx.restore();
  ctx.globalAlpha = 1;
  fx.rain(ctx, W, H, tt, 42, 60, 0.12);
}

const SCENES = [scene1, scene2, scene3, scene4, scene5, scene6];
const LABELS = [
  'SC.01 菲林显影', 'SC.02 四名死者', 'SC.03 冲印店陷阱',
  'SC.04 搜查土瓜湾', 'SC.05 审讯·1983', 'SC.06 改判·终幕',
];
module.exports = { SCENES, LABELS, intro, endcard, rr };
