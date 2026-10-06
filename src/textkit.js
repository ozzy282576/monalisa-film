// textkit.js — per-glyph CJK text engine for @napi-rs/canvas.
// @fontsource Noto SC fonts ship as ~100 unicode-range subsets; skia will NOT
// fallback across faces registered under one family, so each subset gets its own
// family name and we pick the right one per character.
'use strict';
const fs = require('fs');
const path = require('path');

const LIB = require('@napi-rs/canvas');
const { GlobalFonts } = LIB;

const SPECS = [
  { pkg: '@fontsource/noto-sans-sc', weight: '400', tag: 'S4' },
  { pkg: '@fontsource/noto-sans-sc', weight: '700', tag: 'S7' },
  { pkg: '@fontsource/noto-serif-sc', weight: '700', tag: 'R7' },
];

const fams = { S4: [], S7: [], R7: [] };
const widthCache = new Map();
let inited = false;

function init() {
  if (inited) return;
  for (const spec of SPECS) {
    const cssPath = path.join('node_modules', spec.pkg, spec.weight + '.css');
    const css = fs.readFileSync(cssPath, 'utf8');
    const re = new RegExp(
      '\\[(\\d+)\\]-' + spec.weight + '-normal \\*/\\s*@font-face \\{[^]*?url\\(\\.\\/files\\/([\\w.-]+\\.woff2)\\)[^]*?unicode-range: ([^;]+);',
      'g'
    );
    let m;
    while ((m = re.exec(css))) {
      const fam = spec.tag + '_' + m[1];
      GlobalFonts.registerFromPath(path.join('node_modules', spec.pkg, 'files', m[2]), fam);
      const ranges = m[3].split(',').map((s) =>
        s.trim().split('-').map((h) => parseInt(h.replace(/^U\+/i, ''), 16))
      );
      fams[spec.tag].push({ fam, ranges });
    }
  }
  inited = true;
}

const lookupCache = new Map();
function lookup(tag, ch) {
  const cp = ch.codePointAt(0);
  const key = tag + '|' + cp;
  let v = lookupCache.get(key);
  if (v !== undefined) return v;
  v = null;
  const list = fams[tag];
  for (const f of list) {
    for (const r of f.ranges) {
      const lo = r[0], hi = r.length > 1 ? r[1] : r[0];
      if (cp >= lo && cp <= hi) { v = f.fam; break; }
    }
    if (v) break;
  }
  lookupCache.set(key, v);
  return v;
}

// chars that DejaVu covers (basic latin / digits / punctuation)
function dejavuCovers(ch) {
  const cp = ch.codePointAt(0);
  return cp < 0x2500;
}

function coverage(text) {
  init();
  const missing = [];
  for (const ch of new Set([...text])) {
    if (/\s/.test(ch)) continue;
    if (!lookup('S4', ch) && !dejavuCovers(ch)) missing.push(ch);
  }
  return missing;
}

function charWidth(ctx, ch, size, tag) {
  const key = tag + '|' + size + '|' + ch.codePointAt(0);
  let w = widthCache.get(key);
  if (w !== undefined) return w;
  const fam = lookup(tag, ch) || (dejavuCovers(ch) ? 'DejaVu Sans' : null);
  ctx.font = size + 'px ' + (fam || 'DejaVu Sans');
  w = ctx.measureText(ch).width;
  widthCache.set(key, w);
  return w;
}

const measureCache = new Map();
function measure(ctx, text, size, tag, ls = 0) {
  const key = tag + '|' + size + '|' + ls + '|' + text;
  let w = measureCache.get(key);
  if (w !== undefined) return w;
  w = 0;
  for (const ch of text) w += charWidth(ctx, ch, size, tag) + ls;
  w = Math.max(0, w - ls);
  if (measureCache.size < 20000) measureCache.set(key, w);
  return w;
}

/**
 * Draw text glyph-by-glyph with correct CJK subset selection.
 * opts: size, tag ('S4' plain sans | 'S7' bold sans | 'R7' bold serif),
 *       fill, align ('left'|'center'|'right'), ls (letter spacing), alpha
 * returns drawn width.
 */
function draw(ctx, text, x, y, opts) {
  const { size, tag = 'S4', fill = '#fff', align = 'left', ls = 0, alpha = 1 } = opts;
  const W = measure(ctx, text, size, tag, ls);
  let cx = align === 'center' ? x - W / 2 : align === 'right' ? x - W : x;
  const prevAlpha = ctx.globalAlpha;
  ctx.globalAlpha = prevAlpha * alpha;
  ctx.fillStyle = fill;
  ctx.textBaseline = 'alphabetic';
  for (const ch of text) {
    const fam = lookup(tag, ch) || 'DejaVu Sans';
    ctx.font = size + 'px ' + fam;
    ctx.fillText(ch, cx, y);
    cx += charWidth(ctx, ch, size, tag) + ls;
  }
  ctx.globalAlpha = prevAlpha;
  return W;
}

module.exports = { init, lookup, coverage, measure, draw, LIB };
