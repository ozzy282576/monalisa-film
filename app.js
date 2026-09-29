const input = document.querySelector('#file-input');
const zone = document.querySelector('#dropzone');
const browse = document.querySelector('#browse');
const selection = document.querySelector('#selection');
const fileName = document.querySelector('#file-name');
const fileSize = document.querySelector('#file-size');
const preview = document.querySelector('#preview');
const upload = document.querySelector('#upload');
const message = document.querySelector('#message');
const progressArea = document.querySelector('#progress-area');
const progressBar = document.querySelector('#progress-bar');
const progressText = document.querySelector('#progress-text');
const progressPercent = document.querySelector('#progress-percent');
const MAX_SIZE = 50 * 1024 * 1024;
const allowed = /\.(mp4|mov|webm|m4v|avi|mkv)$/i;
let currentFile = null;
let previewUrl = null;
let busy = false;

function formatSize(bytes) {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
}
function clearFile() {
  currentFile = null;
  input.value = '';
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
  preview.removeAttribute('src');
  preview.hidden = true;
  selection.hidden = true;
  zone.hidden = false;
  upload.disabled = true;
  message.textContent = '';
  message.classList.remove('error');
  progressArea.hidden = true;
}
function choose(file) {
  if (!file) return;
  message.classList.remove('error');
  message.textContent = '';
  if (!allowed.test(file.name)) return showError('这个文件格式暂不支持，请选择常见视频格式。');
  if (file.size > MAX_SIZE) return showError('文件超过 50 MB，请压缩后再试。');
  if (file.size === 0) return showError('这个文件是空的，请重新选择。');
  currentFile = file;
  zone.hidden = true;
  selection.hidden = false;
  fileName.textContent = file.name;
  fileSize.textContent = formatSize(file.size);
  previewUrl = URL.createObjectURL(file);
  preview.src = previewUrl;
  preview.hidden = false;
  upload.disabled = false;
}
function showError(text) { message.textContent = text; message.classList.add('error'); }
browse.addEventListener('click', () => input.click());
zone.addEventListener('click', event => { if (!event.target.closest('button')) input.click(); });
zone.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); input.click(); } });
input.addEventListener('change', () => choose(input.files[0]));
document.querySelector('#remove').addEventListener('click', clearFile);
for (const event of ['dragenter', 'dragover']) zone.addEventListener(event, e => { e.preventDefault(); zone.classList.add('dragover'); });
for (const event of ['dragleave', 'drop']) zone.addEventListener(event, e => { e.preventDefault(); zone.classList.remove('dragover'); });
zone.addEventListener('drop', e => choose(e.dataTransfer.files[0]));

upload.addEventListener('click', () => {
  if (!currentFile || busy) return;
  busy = true;
  upload.disabled = true;
  message.textContent = '';
  message.classList.remove('error');
  progressArea.hidden = false;
  progressText.textContent = '正在上传…';
  progressBar.style.width = '0%';
  progressPercent.textContent = '0%';
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload');
  xhr.setRequestHeader('X-File-Name', encodeURIComponent(currentFile.name));
  xhr.setRequestHeader('Content-Type', currentFile.type || 'application/octet-stream');
  xhr.upload.onprogress = e => {
    if (!e.lengthComputable) return;
    const percent = Math.round(e.loaded / e.total * 100);
    progressBar.style.width = `${percent}%`;
    progressPercent.textContent = `${percent}%`;
  };
  xhr.onload = () => {
    busy = false;
    if (xhr.status >= 200 && xhr.status < 300) {
      const result = JSON.parse(xhr.responseText);
      progressText.textContent = '上传完成';
      progressBar.style.width = '100%';
      progressPercent.textContent = '100%';
      message.classList.remove('error');
      message.innerHTML = `已保存到工作区：<a href="${result.path}" download>下载已上传视频</a>`;
    } else {
      let error = '上传失败，请稍后重试。';
      try { error = JSON.parse(xhr.responseText).error || error; } catch {}
      showError(error);
      progressArea.hidden = true;
      upload.disabled = false;
    }
  };
  xhr.onerror = () => { busy = false; showError('网络连接中断，请检查网络后重试。'); progressArea.hidden = true; upload.disabled = false; };
  xhr.send(currentFile);
});

// Document upload
(() => {
  const input = document.querySelector('#document-input');
  const zone = document.querySelector('#document-dropzone');
  const selection = document.querySelector('#document-selection');
  const upload = document.querySelector('#document-upload');
  const message = document.querySelector('#document-message');
  const progressArea = document.querySelector('#document-progress-area');
  const progressBar = document.querySelector('#document-progress-bar');
  const progressText = document.querySelector('#document-progress-text');
  const progressPercent = document.querySelector('#document-progress-percent');
  const maxBytes = 50 * 1024 * 1024;
  const allowed = /\.(pdf|doc|docx|txt|md|rtf|odt|xls|xlsx|csv|ppt|pptx)$/i;
  let file = null;
  let busy = false;
  const formatSize = bytes => bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
  const error = text => { message.textContent = text; message.classList.add('error'); };
  function chooseDocument(candidate) {
    if (!candidate) return;
    message.textContent = ''; message.classList.remove('error');
    if (!allowed.test(candidate.name)) return error('暂不支持这个文档格式，请选择 PDF、Office 文档、TXT 或 Markdown。');
    if (candidate.size > maxBytes) return error('文件超过 50 MB，请压缩后再试。');
    if (!candidate.size) return error('这个文件是空的，请重新选择。');
    file = candidate; zone.hidden = true; selection.hidden = false; upload.disabled = false;
    document.querySelector('#document-name').textContent = candidate.name;
    document.querySelector('#document-size').textContent = formatSize(candidate.size);
  }
  document.querySelector('#document-browse').addEventListener('click', () => input.click());
  zone.addEventListener('click', event => { if (!event.target.closest('button')) input.click(); });
  zone.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); input.click(); } });
  input.addEventListener('change', () => chooseDocument(input.files[0]));
  document.querySelector('#document-remove').addEventListener('click', () => {
    file = null; input.value = ''; selection.hidden = true; zone.hidden = false; upload.disabled = true;
    message.textContent = ''; message.classList.remove('error'); progressArea.hidden = true;
  });
  for (const event of ['dragenter', 'dragover']) zone.addEventListener(event, e => { e.preventDefault(); zone.classList.add('dragover'); });
  for (const event of ['dragleave', 'drop']) zone.addEventListener(event, e => { e.preventDefault(); zone.classList.remove('dragover'); });
  // Accept drops anywhere within the document card, not only on the dashed target.
  const card = document.querySelector('.document-section');
  card.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; zone.classList.add('dragover'); });
  card.addEventListener('dragleave', e => { if (!card.contains(e.relatedTarget)) zone.classList.remove('dragover'); });
  card.addEventListener('drop', e => {
    e.preventDefault(); e.stopPropagation(); zone.classList.remove('dragover');
    const dropped = e.dataTransfer?.files?.[0];
    if (dropped) chooseDocument(dropped);
  });
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('drop', e => e.preventDefault());
  upload.addEventListener('click', () => {
    if (!file || busy) return;
    busy = true; upload.disabled = true; message.textContent = ''; message.classList.remove('error'); progressArea.hidden = false;
    progressText.textContent = '正在上传…'; progressBar.style.width = '0%'; progressPercent.textContent = '0%';
    const xhr = new XMLHttpRequest(); xhr.open('POST', '/upload/document');
    xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name)); xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
    xhr.upload.onprogress = e => { if (!e.lengthComputable) return; const percent = Math.round(e.loaded / e.total * 100); progressBar.style.width = `${percent}%`; progressPercent.textContent = `${percent}%`; };
    xhr.onload = () => {
      busy = false;
      if (xhr.status >= 200 && xhr.status < 300) {
        const result = JSON.parse(xhr.responseText); progressText.textContent = '上传完成'; progressBar.style.width = '100%'; progressPercent.textContent = '100%';
        message.innerHTML = `已保存到工作区：<a href="${result.path}" download>下载已上传文档</a>`;
      } else { let msg = '上传失败，请稍后重试。'; try { msg = JSON.parse(xhr.responseText).error || msg; } catch {} error(msg); progressArea.hidden = true; upload.disabled = false; }
    };
    xhr.onerror = () => { busy = false; error('网络连接中断，请检查网络后重试。'); progressArea.hidden = true; upload.disabled = false; };
    xhr.send(file);
  });
})();

// Dedicated plain-text TXT upload
(() => {
  const input = document.querySelector('#text-input');
  const zone = document.querySelector('#text-dropzone');
  const selection = document.querySelector('#text-selection');
  const upload = document.querySelector('#text-upload');
  const message = document.querySelector('#text-message');
  const progressArea = document.querySelector('#text-progress-area');
  const progressBar = document.querySelector('#text-progress-bar');
  const progressLabel = document.querySelector('#text-progress-label');
  const progressPercent = document.querySelector('#text-progress-percent');
  let file = null, busy = false;
  const maxBytes = 50 * 1024 * 1024;
  const showError = text => { message.textContent = text; message.classList.add('error'); };
  const choose = item => {
    if (!item) return;
    message.textContent = ''; message.classList.remove('error');
    if (!item.name.toLowerCase().endsWith('.txt')) return showError('此区域仅支持 .txt 文件。');
    if (item.size > maxBytes) return showError('文件超过 50 MB，请压缩后再试。');
    if (!item.size) return showError('这个文件是空的，请重新选择。');
    file = item; zone.hidden = true; selection.hidden = false; upload.disabled = false;
    upload.querySelector('span').textContent = '上传 TXT';
    document.querySelector('#text-name').textContent = item.name;
    document.querySelector('#text-size').textContent = item.size >= 1048576 ? `${(item.size / 1048576).toFixed(1)} MB` : `${Math.ceil(item.size / 1024)} KB`;
    // Start immediately after a file is selected so the upload has clear visible feedback.
    setTimeout(() => upload.click(), 0);
  };
  zone.addEventListener('click', e => { if (!e.target.closest('button, input')) input.click(); });
  zone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
  input.addEventListener('change', () => choose(input.files[0]));
  for (const event of ['dragenter','dragover']) zone.addEventListener(event, e => { e.preventDefault(); zone.classList.add('dragover'); });
  for (const event of ['dragleave','drop']) zone.addEventListener(event, e => { e.preventDefault(); zone.classList.remove('dragover'); });
  const card = document.querySelector('.text-section');
  card.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; zone.classList.add('dragover'); });
  card.addEventListener('dragleave', e => { if (!card.contains(e.relatedTarget)) zone.classList.remove('dragover'); });
  card.addEventListener('drop', e => { e.preventDefault(); e.stopPropagation(); zone.classList.remove('dragover'); choose(e.dataTransfer?.files?.[0]); });
  document.querySelector('#text-remove').addEventListener('click', () => { file = null; input.value = ''; selection.hidden = true; zone.hidden = false; upload.disabled = false; upload.querySelector('span').textContent = '选择 TXT 文件'; message.textContent = ''; message.classList.remove('error'); progressArea.hidden = true; });
  upload.addEventListener('click', () => {
    if (busy) return;
    if (!file) { input.click(); message.textContent = '请先选择一个 .txt 文件。'; message.classList.remove('error'); return; }
    busy = true; upload.disabled = true; message.textContent = ''; progressArea.hidden = false; progressLabel.textContent = '正在上传…'; progressBar.style.width = '0%'; progressPercent.textContent = '0%';
    const xhr = new XMLHttpRequest(); xhr.open('POST', '/upload/text'); xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name)); xhr.setRequestHeader('Content-Type', 'text/plain');
    xhr.upload.onprogress = e => { if (e.lengthComputable) { const p = Math.round(e.loaded / e.total * 100); progressBar.style.width = `${p}%`; progressPercent.textContent = `${p}%`; } };
    xhr.onload = () => {
      busy = false;
      if (xhr.status >= 200 && xhr.status < 300) { const result = JSON.parse(xhr.responseText); progressLabel.textContent = '上传完成'; progressBar.style.width = '100%'; progressPercent.textContent = '100%'; message.innerHTML = `已保存到工作区：<a href="${result.path}" download>下载已上传 TXT</a>`; }
      else { let error = '上传失败，请稍后重试。'; try { error = JSON.parse(xhr.responseText).error || error; } catch {} showError(error); progressArea.hidden = true; upload.disabled = false; }
    };
    xhr.onerror = () => { busy = false; showError('网络连接中断，请检查网络后重试。'); progressArea.hidden = true; upload.disabled = false; };
    xhr.send(file);
  });
})();
