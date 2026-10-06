// coverage.js — verifies every glyph used on screen has a font subset (no tofu).
'use strict';
const tk = require('../src/textkit');
const { TEXTS } = require('../src/timeline');
tk.init();
const EXTRA = '悬案档案一卷菲林揭开香港最恐怖的连环杀人案林过云共同点夜更出租车拘捕四项谋杀罪死刑终身监禁雨夜屠夫证物照片录像资料人体组织标本陪审团一致裁定谋杀罪成立他杀人的时候到底清不清醒港督尤德关注下案见沙田城门河冲印店报警警方布下陷阱等他出现照片记录的内容令人不寒而栗一九八二香港专家甲精神异常专家乙仍有自控力';
const missing = tk.coverage(TEXTS.join('') + EXTRA);
console.log(JSON.stringify(missing));
