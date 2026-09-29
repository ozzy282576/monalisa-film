const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

const PORT = Number(process.env.PORT || 3000);
const ROOT = __dirname;
const UPLOAD_DIR = path.join(ROOT, 'uploads');
const MAX_BYTES = 50 * 1024 * 1024;
fs.mkdirSync(UPLOAD_DIR, { recursive: true });

const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8' };
function send(res, status, body, type = 'application/json; charset=utf-8') {
  res.writeHead(status, { 'Content-Type': type, 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' });
  res.end(Buffer.isBuffer(body) || typeof body === 'string' ? body : JSON.stringify(body));
}
const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST, GET, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' });
    return res.end();
  }
  if (req.method === 'POST' && ['/upload', '/upload/document', '/upload/text', '/upload/archive'].includes(req.url)) {
    const isDocument = req.url === '/upload/document';
    const isText = req.url === '/upload/text';
    const isArchive = req.url === '/upload/archive';
    const original = decodeURIComponent((req.headers['x-file-name'] || (isArchive ? 'archive' : isText ? 'text' : isDocument ? 'document' : 'video')).replace(/\\+/g, ' '));
    const ext = path.extname(original).toLowerCase();
    const allowedExtensions = isArchive ? ['.zip', '.7z', '.rar', '.tar', '.gz', '.bz2', '.xz'] : isText ? ['.txt'] : isDocument
      ? ['.pdf', '.doc', '.docx', '.txt', '.md', '.rtf', '.odt', '.xls', '.xlsx', '.csv', '.ppt', '.pptx']
      : ['.mp4', '.mov', '.webm', '.m4v', '.avi', '.mkv'];
    if (!allowedExtensions.includes(ext)) {
      req.resume(); return send(res, 415, { error: isArchive ? '这个区域支持 ZIP、7Z、RAR、TAR、GZ、BZ2 或 XZ 压缩文件。' : isText ? '这个区域仅支持 .txt 文件。' : isDocument ? '请上传 PDF、Word、Excel、PowerPoint、TXT 或 Markdown 文档。' : '请上传 MP4、MOV、WebM、M4V、AVI 或 MKV 视频。' });
    }
    const length = Number(req.headers['content-length'] || 0);
    if (length > MAX_BYTES) { req.resume(); return send(res, 413, { error: '文件超过 50 MB 限制。' }); }
    const safeName = path.basename(original).replace(/[^\p{L}\p{N}._-]/gu, '_').slice(0, 100) || `${isArchive ? 'archive' : isText ? 'text' : isDocument ? 'document' : 'video'}${ext}`;
    const storedName = `${Date.now()}-${randomUUID().slice(0, 8)}-${safeName}`;
    const output = fs.createWriteStream(path.join(UPLOAD_DIR, storedName), { flags: 'wx' });
    let bytes = 0; let failed = false;
    req.on('data', chunk => {
      bytes += chunk.length;
      if (bytes > MAX_BYTES && !failed) { failed = true; output.destroy(); fs.rm(path.join(UPLOAD_DIR, storedName), { force: true }, () => {}); send(res, 413, { error: '文件超过 50 MB 限制。' }); req.destroy(); }
    });
    req.on('aborted', () => { output.destroy(); fs.rm(path.join(UPLOAD_DIR, storedName), { force: true }, () => {}); });
    output.on('error', () => { if (!failed) send(res, 500, { error: '保存失败，请重试。' }); });
    output.on('finish', () => { if (!failed) send(res, 201, { name: safeName, size: bytes, path: `/uploads/${encodeURIComponent(storedName)}` }); });
    req.pipe(output);
    return;
  }
  if (req.method === 'GET' && (req.url === '/' || req.url === '/downloads')) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    return res.end(fs.readFileSync(path.join(ROOT, 'downloads.html')));
  }
  if (req.method === 'GET' && req.url === '/media/video') {
    const file = path.join(ROOT, 'Dennis-McGrory-2min-vertical.mp4');
    if (!fs.existsSync(file)) return send(res, 404, { error: '视频文件不存在。' });
    const size = fs.statSync(file).size;
    const range = req.headers.range;
    res.setHeader('Content-Type', 'video/mp4');
    res.setHeader('Accept-Ranges', 'bytes');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Disposition', 'inline; filename="Dennis-McGrory-2min-vertical.mp4"');
    if (range) {
      const match = /^bytes=(\d*)-(\d*)$/.exec(range);
      if (!match) { res.writeHead(416, { 'Content-Range': `bytes */${size}` }); return res.end(); }
      const start = match[1] ? Number(match[1]) : 0;
      const end = match[2] ? Math.min(Number(match[2]), size - 1) : size - 1;
      if (start > end || start >= size) { res.writeHead(416, { 'Content-Range': `bytes */${size}` }); return res.end(); }
      res.writeHead(206, { 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1 });
      return fs.createReadStream(file, { start, end }).pipe(res);
    }
    res.writeHead(200, { 'Content-Length': size });
    return fs.createReadStream(file).pipe(res);
  }
  if (req.method === 'GET' && req.url.startsWith('/download/')) {
    const id = decodeURIComponent(req.url.slice('/download/'.length).split('?')[0]);
    const downloads = {
      'video': ['Dennis-McGrory-2min-vertical.mp4', 'video/mp4'],
      'frames': ['Dennis-McGrory-24-frames.zip', 'application/zip'],
      'subtitles': ['Dennis-McGrory-zh-CN.srt', 'application/x-subrip; charset=utf-8'],
      'script': ['script.md', 'text/markdown; charset=utf-8'],
      'narration': ['audio/narration-final.mp3', 'audio/mpeg'],
      'preview': ['Dennis-McGrory-preview.jpg', 'image/jpeg']
    };
    if (id === 'page') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      return res.end(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>下载成片</title><body style="font:16px system-ui;background:#f6f4ef;color:#222;max-width:680px;margin:40px auto;padding:20px"><h1>丹尼斯·麦格罗里案｜成片下载</h1><p>竖屏 9:16 · 1080×1920 · 约 2 分钟</p><p><a href="/download/video">下载 MP4 成片</a></p><p><a href="/download/frames">下载 24 个镜头图片 ZIP</a></p><p><a href="/download/subtitles">下载中文字幕 SRT</a></p><p><a href="/download/script">查看解说稿与史实校正</a></p><p><a href="/download/preview">查看镜头预览拼图</a></p></body>`);
    }
    const entry = downloads[id];
    if (!entry) return send(res, 404, { error: '下载项不存在。' });
    const [name, contentType] = entry;
    const file = path.join(ROOT, name);
    if (!fs.existsSync(file)) return send(res, 404, { error: '文件尚未生成。' });
    res.writeHead(200, { 'Content-Type': contentType, 'Content-Length': fs.statSync(file).size, 'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(name)}`, 'Cache-Control': 'no-store' });
    return fs.createReadStream(file).pipe(res);
  }
  if (req.method === 'GET' && req.url.startsWith('/uploads/')) {
    const name = path.basename(decodeURIComponent(req.url.slice('/uploads/'.length)));
    const file = path.join(UPLOAD_DIR, name);
    if (!fs.existsSync(file)) return send(res, 404, { error: '文件不存在。' });
    res.writeHead(200, { 'Content-Type': 'application/octet-stream', 'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(name)}` });
    return fs.createReadStream(file).pipe(res);
  }
  const pathname = req.url.split('?')[0];
  const file = pathname === '/upload-page' ? 'index.html' : path.basename(pathname);
  const fullPath = path.join(ROOT, file);
  if (['index.html', 'style.css', 'app.js', 'archive.js'].includes(file) && fs.existsSync(fullPath)) return send(res, 200, fs.readFileSync(fullPath), types[path.extname(file)]);
  send(res, 404, { error: 'Not found' });
});
server.listen(PORT, '0.0.0.0', () => console.log(`Video upload page running on http://0.0.0.0:${PORT}`));
