function openUploadModal() {
  byId('uploadModal').classList.add('open');
  byId('uploadModal').style.display = 'flex';
  byId('uploadResult').style.display = 'none';
  byId('uploadProgress').style.display = 'none';
  byId('uploadProgressFill').style.width = '0%';
  byId('uploadProgressText').textContent = '0%';
}

function handleDrop(e) {
  e.preventDefault();
  if(e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
}

function handleFileSelect(e) {
  if(e.target.files.length) uploadFile(e.target.files[0]);
}

function uploadFile(file) {
  var ext = file.name.split('.').pop().toLowerCase();
  if(!['bak','zip','sql','sqlite'].includes(ext)) {
    toast('صيغة ملف غير مدعومة. المدعوم: .bak, .zip, .sql, .sqlite', 'error');
    return;
  }
  if(file.size > 500 * 1024 * 1024) {
    toast('حجم الملف يتجاوز 500MB', 'error');
    return;
  }
  byId('uploadProgress').style.display = 'block';
  byId('uploadResult').style.display = 'none';
  var fd = new FormData();
  fd.append('file', file);
  var xhr = new XMLHttpRequest();
  xhr.upload.onprogress = function(e){
    if(e.lengthComputable) {
      var pct = Math.round((e.loaded / e.total) * 100);
      byId('uploadProgressFill').style.width = pct + '%';
      byId('uploadProgressText').textContent = pct + '% - ' + fmtBytes(e.loaded) + ' / ' + fmtBytes(e.total);
    }
  };
  xhr.onload = function(){
    try {
      var d = JSON.parse(xhr.responseText);
      byId('uploadProgress').style.display = 'none';
      var rd = byId('uploadResult');
      rd.style.display = 'block';
      if(d.ok) {
        rd.innerHTML = '<div style="padding:14px;border-radius:10px;background:rgba(22,163,74,0.1);border:1px solid rgba(22,163,74,0.3);color:var(--green);text-align:center">'
          + '<i class="fas fa-check-circle" style="font-size:20px;display:block;margin-bottom:6px"></i>'
          + 'تم رفع الملف بنجاح<br><strong>' + (d.filename || file.name) + '</strong> (' + fmtBytes(file.size) + ')</div>';
        toast('تم رفع النسخة بنجاح', 'success');
        loadBackups(); loadStats();
      } else {
        rd.innerHTML = '<div style="padding:14px;border-radius:10px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);color:var(--red);text-align:center">'
          + '<i class="fas fa-times-circle" style="font-size:20px;display:block;margin-bottom:6px"></i>'
          + 'فشل الرفع: ' + (d.error || 'خطأ غير معروف') + '</div>';
        toast('فشل الرفع', 'error');
      }
    } catch(e) {
      byId('uploadResult').innerHTML = '<div style="padding:14px;border-radius:10px;background:rgba(239,68,68,0.1);color:var(--red);text-align:center">خطأ في معالجة الرد</div>';
    }
  };
  xhr.onerror = function(){
    byId('uploadProgress').style.display = 'none';
    byId('uploadResult').style.display = 'block';
    byId('uploadResult').innerHTML = '<div style="padding:14px;border-radius:10px;background:rgba(239,68,68,0.1);color:var(--red);text-align:center">فشل الاتصال بالخادم</div>';
    toast('فشل الاتصال', 'error');
  };
  xhr.open('POST', '/admin/backup/api/upload', true);
  xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
  xhr.send(fd);
}

function fmtBytes(b) {
  if(b < 1024) return b + ' B';
  if(b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  if(b < 1073741824) return (b / 1048576).toFixed(1) + ' MB';
  return (b / 1073741824).toFixed(2) + ' GB';
}

document.addEventListener('DOMContentLoaded', function(){
  var dz = byId('dropZone');
  if(dz) {
    dz.addEventListener('dragenter', function(e){ e.preventDefault(); this.style.borderColor = '#6366f1'; this.style.background = 'var(--glow)'; });
    dz.addEventListener('dragleave', function(e){ e.preventDefault(); this.style.borderColor = 'var(--border)'; this.style.background = 'transparent'; });
  }
});
