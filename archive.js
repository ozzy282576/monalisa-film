// Archive upload: files are stored as-is and never extracted.
(() => {
  const input = document.querySelector('#archive-input');
  const zone = document.querySelector('#archive-dropzone');
  const selection = document.querySelector('#archive-selection');
  const upload = document.querySelector('#archive-upload');
  const message = document.querySelector('#archive-message');
  const progressArea = document.querySelector('#archive-progress-area');
  const progressBar = document.querySelector('#archive-progress-bar');
  const progressLabel = document.querySelector('#archive-progress-label');
  const progressPercent = document.querySelector('#archive-progress-percent');
  const maxBytes = 50 * 1024 * 1024;
  const allowed = /\.(zip|7z|rar|tar|gz|bz2|xz)$/i;
  let file = null, busy = false;
  const showError = text => { message.textContent = text; message.classList.add('error'); };
  const choose = item => {
    if (!item) return;
    message.textContent = ''; message.classList.remove('error');
    if (!allowed.test(item.name)) return showError('请上传 ZIP、7Z、RAR、TAR、GZ、BZ2 或 XZ 压缩文件。');
    if (item.size > maxBytes) return showError('文件超过 50 MB，请压缩后再试。');
    if (!item.size) return showError('这个文件是空的，请重新选择。');
    file = item; zone.hidden = true; selection.hidden = false; upload.disabled = false;
    document.querySelector('#archive-name').textContent = item.name;
    document.querySelector('#archive-size').textContent = item.size >= 1048576 ? `${(item.size / 1048576).toFixed(1)} MB` : `${Math.ceil(item.size / 1024)} KB`;
    message.classList.remove('error');
    message.textContent = '文件已选好，请点击下方“上传压缩文件”。';
    upload.focus({ preventScroll: true });
    upload.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };
  zone.addEventListener('click', e => { if (!e.target.closest('button, input')) input.click(); });
  zone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
  input.addEventListener('change', () => choose(input.files[0]));
  for (const event of ['dragenter','dragover']) zone.addEventListener(event, e => { e.preventDefault(); zone.classList.add('dragover'); });
  for (const event of ['dragleave','drop']) zone.addEventListener(event, e => { e.preventDefault(); zone.classList.remove('dragover'); });
  const card = document.querySelector('.archive-section');
  card.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; zone.classList.add('dragover'); });
  card.addEventListener('dragleave', e => { if (!card.contains(e.relatedTarget)) zone.classList.remove('dragover'); });
  card.addEventListener('drop', e => { e.preventDefault(); e.stopPropagation(); zone.classList.remove('dragover'); choose(e.dataTransfer?.files?.[0]); });
  document.querySelector('#archive-remove').addEventListener('click', () => { file = null; input.value = ''; selection.hidden = true; zone.hidden = false; upload.disabled = true; message.textContent = ''; message.classList.remove('error'); progressArea.hidden = true; });
  upload.addEventListener('click', () => {
    if (!file || busy) return;
    busy = true; upload.disabled = true; message.textContent = ''; message.classList.remove('error'); progressArea.hidden = false; progressLabel.textContent = '正在上传…'; progressBar.style.width = '0%'; progressPercent.textContent = '0%';
    const xhr = new XMLHttpRequest(); xhr.open('POST', '/upload/archive'); xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name)); xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.upload.onprogress = e => { if (e.lengthComputable) { const p = Math.round(e.loaded / e.total * 100); progressBar.style.width = `${p}%`; progressPercent.textContent = `${p}%`; } };
    xhr.onload = () => {
      busy = false;
      if (xhr.status >= 200 && xhr.status < 300) { const result = JSON.parse(xhr.responseText); progressLabel.textContent = '上传完成'; progressBar.style.width = '100%'; progressPercent.textContent = '100%'; message.innerHTML = `已保存到工作区：<a href="${result.path}" download>下载已上传压缩文件</a>`; }
      else { let error = '上传失败，请稍后重试。'; try { error = JSON.parse(xhr.responseText).error || error; } catch {} showError(error); progressArea.hidden = true; upload.disabled = false; }
    };
    xhr.onerror = () => { busy = false; showError('网络连接中断，请检查网络后重试。'); progressArea.hidden = true; upload.disabled = false; };
    xhr.send(file);
  });
})();
