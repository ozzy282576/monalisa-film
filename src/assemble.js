// assemble.js — encodes frames + narration + music into the final MP4.
'use strict';
const fs = require('fs');
const { execSync, spawnSync } = require('child_process');
const FFPROBE = require('@ffprobe-installer/ffprobe').path;
const FFMPEG = execSync('python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"').toString().trim();

const T = JSON.parse(fs.readFileSync('build/timeline.json', 'utf8'));

const inputs = ['-i', 'build/video_silent.mp4'];
for (let i = 1; i <= 6; i++) inputs.push('-i', `audio/narration/s${i}.mp3`);
inputs.push('-i', 'build/music.wav');

const fc = [];
T.segs.forEach((s, i) => {
  const ms = Math.round(s.start * 1000);
  fc.push(`[${i + 1}:a]adelay=${ms}|${ms},apad=whole_dur=${(T.total + 1).toFixed(2)}[a${i + 1}]`);
});
fc.push('[7:a]volume=1.0[mus]');
const ins = [1, 2, 3, 4, 5, 6].map((i) => `[a${i}]`).join('') + '[mus]';
fc.push(`${ins}amix=inputs=7:normalize=0:duration=first[mix]`);
fc.push('[mix]alimiter=level_in=1:level_out=0.95:limit=0.95,loudnorm=I=-14:TP=-1.5:LRA=11[aout]');

const out = 'output/lin_guoyun_1982_rainy_night_butcher_1080p.mp4';
fs.mkdirSync('output', { recursive: true });

const args = [
  '-y',
  ...inputs,
  '-filter_complex', fc.join(';'),
  '-map', '0:v', '-map', '[aout]',
  '-c:v', 'copy',
  '-c:a', 'aac', '-b:a', '192k', '-ar', '44100',
  '-movflags', '+faststart',
  '-t', T.total.toFixed(3),
  out,
];
console.log('running ffmpeg...');
const r = spawnSync(FFMPEG, args, { stdio: ['ignore', 'pipe', 'inherit'], timeout: 1500000 });
if (r.status !== 0) { console.error('ffmpeg failed', r.status); process.exit(1); }

const probe = execSync(`"${FFPROBE}" -v error -show_entries format=duration:stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate,sample_rate -of json ${out}`).toString();
console.log('PROBE', probe);
console.log('ASSEMBLE DONE ->', out);
