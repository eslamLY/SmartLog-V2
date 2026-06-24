let currentBackupPage = 1;
let currentAuditPage = 1;

function csrfToken() {
  var m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}

function loadStats() {
  fetch('/admin/backup/api/stats').then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;
    byId('statTotal').textContent = d.total_backups || 0;
    byId('statSize').textContent = d.total_size_display || '0 B';
    byId('statEncrypted').textContent = (d.encryption_rate !== undefined ? d.encryption_rate + '%' : '0%');
    byId('statVerified').textContent = (d.verified_rate !== undefined ? d.verified_rate + '%' : '0%');
    byId('statSchedules').textContent = d.active_schedules || 0;
  });
}

function byId(id) { return document.getElementById(id); }

function loadBackups(page) {
  if(page) currentBackupPage = page;
  var type = byId('filterType').value;
  fetch('/admin/backup/api/list?page=' + currentBackupPage + '&per_page=15&type=' + type)
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok) return;
    var tb = byId('backupTableBody');
    tb.innerHTML = '';
    if(!d.backups || !d.backups.length) {
      tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:30px">لا توجد نسخ احتياطية</td></tr>';
      return;
    }
    var typeNames = {full:'كاملة', incremental:'تدريجية', selective:'انتقائية'};
    var statusNames = {verified:'موثّق', completed:'مكتمل', corrupted:'تالف'};
    d.backups.forEach(function(b){
      var tname = typeNames[b.type] || b.type;
      var sname = statusNames[b.status] || b.status;
      var lockIcon = b.encrypted ? '<i class="fas fa-lock" style="color:var(--green)"></i>' : '<i class="fas fa-unlock" style="color:var(--muted)"></i>';
      var dateStr = b.created_at ? new Date(b.created_at).toLocaleString('ar-SA') : '-';
      tb.innerHTML += '<tr>'
        + '<td><span class="file-name">' + esc(b.filename) + '</span></td>'
        + '<td><span class="badge badge-' + b.type + '">' + tname + '</span></td>'
        + '<td>' + b.size_display + '</td>'
        + '<td>' + lockIcon + '</td>'
        + '<td><span class="badge badge-' + b.status + '">' + sname + '</span></td>'
        + '<td style="color:var(--muted)">' + dateStr + '</td>'
        + '<td style="white-space:nowrap">'
        + '<button class="btn-icon" onclick="previewBackup(' + b.id + ')" title="معاينة"><i class="fas fa-eye"></i></button> '
        + '<button class="btn-icon" onclick="verifySingle(' + b.id + ')" title="تحقق"><i class="fas fa-check-circle"></i></button> '
        + '<button class="btn-icon" style="color:var(--red)" onclick="deleteBackup(' + b.id + ')" title="حذف"><i class="fas fa-trash"></i></button>'
        + '</td></tr>';
    });
    var pg = byId('backupPagination');
    pg.innerHTML = '';
    var totalPages = Math.ceil(d.total / d.per_page);
    for(var i = 1; i <= totalPages; i++) {
      var cls = 'page-btn' + (i === currentBackupPage ? ' active' : '');
      pg.innerHTML += '<button class="' + cls + '" onclick="loadBackups(' + i + ')">' + i + '</button>';
    }
  });
}

function esc(s) { if(!s) return ''; return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function deleteBackup(id) {
  if(!confirm('هل أنت متأكد من حذف هذه النسخة؟')) return;
  fetch('/admin/backup/api/delete/' + id, {method:'DELETE'})
  .then(function(r){return r.json()}).then(function(d){
    toast(d.ok ? 'تم الحذف بنجاح' : 'فشل الحذف', d.ok ? 'success' : 'error');
    if(d.ok) loadBackups();
  });
}

function verifySingle(id) {
  fetch('/admin/backup/api/verify/' + id)
  .then(function(r){return r.json()}).then(function(d){
    toast(d.ok ? 'النسخة سليمة ✓' : 'فشل التحقق: ' + (d.error || ''), d.ok ? 'success' : 'error');
    if(d.ok) loadBackups();
  });
}

function verifyAll() {
  fetch('/admin/backup/api/verify-all', {method:'POST', headers:{'X-CSRFToken': csrfToken()}})
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok) return;
    var ok = d.results.filter(function(r){return r.ok}).length;
    var fail = d.results.filter(function(r){return !r.ok}).length;
    toast('تم التحقق: ' + ok + ' نجاح, ' + fail + ' فشل', 'info');
    loadBackups();
  });
}

function previewBackup(id) {
  fetch('/admin/backup/api/preview/' + id)
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok) { toast(d.error || 'خطأ في المعاينة', 'error'); return; }
    var c = d.content;
    var html = '<table class="tbl" style="margin-bottom:10px"><thead><tr><th>الجدول</th><th>عدد السجلات</th></tr></thead><tbody>';
    for(var tbl in c.tables) {
      html += '<tr><td>' + tbl + '</td><td>' + c.tables[tbl] + '</td></tr>';
    }
    html += '</tbody></table>';
    html += '<p>النوع: ' + c.type + ' | الملفات: ' + (c.total_uploads||0) + ' | الإجمالي: ' + c.total_records + ' سجل</p>';
    showDialog(html);
  });
}

function showDialog(html) {
  var ov = document.createElement('div');
  ov.className = 'modal-overlay';
  ov.style.display = 'flex';
  ov.onclick = function(e) { if(e.target === this) document.body.removeChild(ov); };
  var sheet = document.createElement('div');
  sheet.className = 'modal-sheet';
  sheet.style.maxWidth = '600px';
  var hdr = document.createElement('div');
  hdr.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-bottom:12px';
  var title = document.createElement('h3');
  title.style.cssText = 'font-size:15px;font-weight:700';
  title.textContent = 'معاينة النسخة';
  var closeBtn = document.createElement('button');
  closeBtn.className = 'btn btn-ghost btn-xs';
  closeBtn.style.cssText = 'padding:4px 8px';
  closeBtn.innerHTML = '<i class="ti ti-x"></i>';
  closeBtn.onclick = function() { document.body.removeChild(ov); };
  hdr.appendChild(title);
  hdr.appendChild(closeBtn);
  var body = document.createElement('div');
  body.innerHTML = html;
  sheet.appendChild(hdr);
  sheet.appendChild(body);
  ov.appendChild(sheet);
  document.body.appendChild(ov);
}

function openCreateBackup() {
  byId('createBackupModal').classList.add('open');
  byId('createBackupModal').style.display = 'flex';
  byId('createBackupType').onchange = function() {
    byId('selectiveTables').style.display = (this.value === 'selective' ? 'block' : 'none');
  };
}

function executeCreateBackup() {
  var btn = byId('createBackupBtn');
  btn.disabled = true;
  btn.textContent = 'جارٍ الإنشاء...';
  byId('createBackupProgress').style.display = 'block';
  var body = {
    type: byId('createBackupType').value,
    encrypt: byId('createBackupEncrypt').checked,
    description: byId('createBackupDesc').value
  };
  var progress = 0;
  var iv = setInterval(function(){
    progress = Math.min(progress + Math.random() * 15, 85);
    byId('createProgressFill').style.width = progress + '%';
    byId('createProgressText').textContent = Math.round(progress) + '%';
  }, 400);
  fetch('/admin/backup/api/create', {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()}, body:JSON.stringify(body)})
  .then(function(r){return r.json()}).then(function(d){
    clearInterval(iv);
    byId('createProgressFill').style.width = '100%';
    byId('createProgressText').textContent = 'اكتمل!';
    if(d.ok) {
      toast('تم إنشاء النسخة بنجاح', 'success');
      setTimeout(function(){ closeModal('createBackupModal'); loadBackups(); loadStats(); }, 900);
    } else {
      toast('فشل: ' + (d.error || ''), 'error');
      btn.disabled = false;
      btn.textContent = 'بدء';
    }
  }).catch(function(e){
    clearInterval(iv);
    toast('خطأ: ' + e.message, 'error');
    btn.disabled = false;
    btn.textContent = 'بدء';
  });
}

function closeModal(id) {
  var el = byId(id);
  if(el) { el.classList.remove('open'); el.style.display = 'none'; }
}

function switchTab(name) {
  var tabs = document.querySelectorAll('.backup-container .tab');
  for(var i = 0; i < tabs.length; i++) {
    tabs[i].classList.toggle('active', tabs[i].getAttribute('data-tab') === name);
  }
  var contents = document.querySelectorAll('.backup-container .tab-content');
  for(var i = 0; i < contents.length; i++) {
    contents[i].classList.toggle('active', contents[i].id === 'tab-' + name);
  }
  if(name === 'analytics') {
    setTimeout(function(){ if(typeof loadCharts === 'function') loadCharts(); }, 200);
  }
}

function loadSchedules() {
  fetch('/admin/backup/api/schedules')
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok) return;
    var tb = byId('scheduleTableBody');
    tb.innerHTML = '';
    if(!d.schedules || !d.schedules.length) {
      tb.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:30px">لا توجد جداول</td></tr>';
      return;
    }
    d.schedules.forEach(function(s){
      var rate = s.total_runs ? Math.round((s.successful_runs / s.total_runs) * 100) : 100;
      var freqNames = {daily:'يومي', weekly:'أسبوعي', monthly:'شهري'};
      var freq = freqNames[s.frequency] || ('كل ' + s.frequency_value + ' ' + s.frequency);
      var lastRun = s.last_run ? new Date(s.last_run).toLocaleString('ar-SA') : '-';
      var nextRun = s.next_run ? new Date(s.next_run).toLocaleString('ar-SA') : '-';
      var rateCls = rate >= 80 ? 'badge-success' : (rate >= 50 ? 'badge-warning' : 'badge-danger');
      tb.innerHTML += '<tr>'
        + '<td><strong>' + esc(s.name) + '</strong></td>'
        + '<td><span class="badge badge-' + s.backup_type + '">' + (s.backup_type==='full'?'كاملة':s.backup_type==='incremental'?'تدريجية':'انتقائية') + '</span></td>'
        + '<td>' + freq + '</td>'
        + '<td><span class="badge ' + (s.is_active ? 'badge-success' : 'badge-muted') + '">' + (s.is_active ? 'نشط' : 'متوقف') + '</span></td>'
        + '<td style="color:var(--muted)">' + lastRun + '</td>'
        + '<td style="color:var(--muted)">' + nextRun + '</td>'
        + '<td><span class="badge ' + rateCls + '">' + rate + '%</span></td>'
        + '<td style="white-space:nowrap">'
        + '<button class="btn-icon" onclick="runScheduleNow(' + s.id + ')" title="تشغيل الآن"><i class="fas fa-play"></i></button> '
        + '<button class="btn-icon" onclick="toggleSchedule(' + s.id + ')" title="' + (s.is_active?'إيقاف':'تشغيل') + '"><i class="fas fa-' + (s.is_active?'pause':'play') + '"></i></button> '
        + '<button class="btn-icon" style="color:var(--red)" onclick="deleteSchedule(' + s.id + ')" title="حذف"><i class="fas fa-trash"></i></button>'
        + '</td></tr>';
    });
  });
}

function runScheduleNow(id) {
  fetch('/admin/backup/api/schedules/run/' + id, {method:'POST', headers:{'X-CSRFToken': csrfToken()}})
  .then(function(r){return r.json()}).then(function(d){
    toast(d.ok ? 'تم تشغيل النسخة بنجاح' : 'فشل: ' + (d.error || ''), d.ok ? 'success' : 'error');
    loadSchedules(); loadBackups(); loadStats();
  });
}

function toggleSchedule(id) {
  fetch('/admin/backup/api/schedules/toggle/' + id, {method:'POST', headers:{'X-CSRFToken': csrfToken()}})
  .then(function(r){return r.json()}).then(function(d){
    if(d.ok) loadSchedules();
  });
}

function deleteSchedule(id) {
  if(!confirm('حذف الجدول؟')) return;
  fetch('/admin/backup/api/schedules/delete/' + id, {method:'DELETE'})
  .then(function(r){return r.json()}).then(function(d){
    toast(d.ok ? 'تم الحذف' : 'فشل', d.ok ? 'success' : 'error');
    if(d.ok) loadSchedules();
  });
}

function openScheduleModal() {
  byId('scheduleModal').classList.add('open');
  byId('scheduleModal').style.display = 'flex';
  byId('schedName').value = '';
  byId('schedType').value = 'full';
  byId('schedFreq').value = 'daily';
  byId('schedTime').value = '02:00';
  byId('schedRetention').value = '20';
  byId('schedEncrypt').checked = true;
  byId('schedNotifySuccess').checked = true;
  byId('schedNotifyFailure').checked = true;
  byId('freqValueGroup').style.display = 'none';
}

function toggleFreqValue() {
  var v = byId('schedFreq').value;
  byId('freqValueGroup').style.display = (v === 'hours' || v === 'minutes') ? 'block' : 'none';
}

function saveSchedule() {
  var data = {
    name: byId('schedName').value,
    backup_type: byId('schedType').value,
    frequency: byId('schedFreq').value,
    frequency_value: parseInt(byId('schedFreqValue').value) || 1,
    time_str: byId('schedTime').value,
    retention_count: parseInt(byId('schedRetention').value) || 20,
    encrypt: byId('schedEncrypt').checked,
    notify_on_success: byId('schedNotifySuccess').checked,
    notify_on_failure: byId('schedNotifyFailure').checked
  };
  if(!data.name) { toast('الرجاء إدخال اسم الجدول', 'warning'); return; }
  fetch('/admin/backup/api/schedules/create', {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()}, body:JSON.stringify(data)})
  .then(function(r){return r.json()}).then(function(d){
    if(d.ok) {
      toast('تم حفظ الجدول', 'success');
      closeModal('scheduleModal');
      loadSchedules();
    } else toast(d.error || 'فشل الحفظ', 'error');
  });
}

function restoreStep2() {
  var sel = byId('restoreBackupSelect');
  var id = sel.value;
  if(!id) { toast('الرجاء اختيار نسخة', 'warning'); return; }
  byId('restoreBackupId').value = id;
  fetch('/admin/backup/api/preview/' + id)
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok) { toast(d.error || 'خطأ', 'error'); return; }
    var c = d.content;
    var html = '<table class="tbl" style="margin-bottom:10px"><thead><tr><th>الجدول</th><th>عدد السجلات</th></tr></thead><tbody>';
    for(var tbl in c.tables) {
      html += '<tr><td>' + tbl + '</td><td>' + c.tables[tbl] + '</td></tr>';
    }
    html += '</tbody></table>';
    html += '<p>النوع: ' + c.type + ' | إجمالي السجلات: ' + c.total_records + ' | الملفات: ' + (c.total_uploads||0) + '</p>';
    byId('previewContent').innerHTML = html;
    byId('wizSelect').style.display = 'none';
    byId('wizPreview').style.display = 'block';
    byId('wizStep1').classList.remove('active');
    byId('wizStep2').classList.add('active');
  });
}

function restoreStep3() {
  byId('wizPreview').style.display = 'none';
  byId('wizConfirm').style.display = 'block';
  byId('wizStep2').classList.remove('active');
  byId('wizStep3').classList.add('active');
}

function executeRestore() {
  var id = byId('restoreBackupId').value;
  var createPre = byId('createPreBackup').checked;
  fetch('/admin/backup/api/restore', {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
    body:JSON.stringify({backup_id: parseInt(id), create_backup_first: createPre})})
  .then(function(r){return r.json()}).then(function(d){
    byId('wizConfirm').style.display = 'none';
    var div = byId('wizResult');
    div.style.display = 'block';
    if(d.ok) {
      div.innerHTML = '<div style="padding:16px;border-radius:10px;background:rgba(22,163,74,0.1);border:1px solid rgba(22,163,74,0.3);color:var(--green);text-align:center">'
        + '<i class="fas fa-check-circle" style="font-size:24px;display:block;margin-bottom:8px"></i>'
        + 'تمت الاستعادة بنجاح!<br>السجلات: ' + d.records_restored + ' | الجداول: ' + d.tables_restored + ' | المدة: ' + d.duration_seconds + ' ث</div>';
      byId('wizStep3').classList.add('completed');
      loadBackups(); loadStats();
    } else {
      div.innerHTML = '<div style="padding:16px;border-radius:10px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);color:var(--red);text-align:center">'
        + '<i class="fas fa-times-circle" style="font-size:24px;display:block;margin-bottom:8px"></i>'
        + 'فشل الاستعادة: ' + (d.error || '') + '</div>';
    }
  });
}

function loadAuditLogs(page) {
  if(page) currentAuditPage = page;
  fetch('/admin/backup/api/audit?page=' + currentAuditPage + '&per_page=20')
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok) return;
    var tb = byId('auditTableBody');
    tb.innerHTML = '';
    if(!d.logs || !d.logs.length) {
      tb.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:30px">لا توجد سجلات</td></tr>';
      return;
    }
    d.logs.forEach(function(l){
      var dateStr = l.created_at ? new Date(l.created_at).toLocaleString('ar-SA') : '-';
      tb.innerHTML += '<tr><td>' + esc(l.action) + '</td><td>' + esc(l.details||'-') + '</td><td>' + esc(l.user_name||'system') + '</td><td style="color:var(--muted)">' + dateStr + '</td></tr>';
    });
    var pg = byId('auditPagination');
    pg.innerHTML = '';
    var totalPages = Math.ceil(d.total / 20);
    for(var i = 1; i <= totalPages; i++) {
      var cls = 'page-btn' + (i === currentAuditPage ? ' active' : '');
      pg.innerHTML += '<button class="' + cls + '" onclick="loadAuditLogs(' + i + ')">' + i + '</button>';
    }
  });
}

function loadConfig() {
  fetch('/admin/backup/api/config')
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok) return;
    var c = d.config;
    var grid = byId('configGrid');
    var fields = [
      {key:'encryption_enabled', label:'تشفير AES-256', type:'checkbox'},
      {key:'compression_enabled', label:'ضغط البيانات', type:'checkbox'},
      {key:'auto_verify', label:'التحقق التلقائي', type:'checkbox'},
      {key:'auto_cleanup_enabled', label:'التنظيف التلقائي', type:'checkbox'},
      {key:'max_local_backups', label:'الحد الأقصى للنسخ المحلية', type:'number'},
      {key:'retention_days', label:'أيام الاحتفاظ', type:'number'},
      {key:'compression_level', label:'مستوى الضغط (1-9)', type:'number'},
      {key:'verify_interval_days', label:'التحقق كل (أيام)', type:'number'},
      {key:'notification_email', label:'البريد للإشعارات', type:'text'}
    ];
    grid.innerHTML = '';
    fields.forEach(function(f){
      var val = c[f.key];
      var div = document.createElement('div');
      div.className = 'config-field';
      var lbl = document.createElement('label');
      lbl.textContent = f.label;
      div.appendChild(lbl);
      if(f.type === 'checkbox') {
        var inp = document.createElement('input');
        inp.type = 'checkbox';
        inp.checked = !!val;
        inp.id = 'cfg_' + f.key;
        inp.setAttribute('data-key', f.key);
        div.appendChild(inp);
      } else {
        var inp = document.createElement('input');
        inp.type = f.type;
        inp.value = (val !== null && val !== undefined) ? val : '';
        inp.id = 'cfg_' + f.key;
        inp.setAttribute('data-key', f.key);
        inp.className = 'form-input';
        div.appendChild(inp);
      }
      grid.appendChild(div);
    });
  });
}

function saveConfig() {
  var data = {};
  var inputs = document.querySelectorAll('#configGrid input');
  for(var i = 0; i < inputs.length; i++) {
    var inp = inputs[i];
    var key = inp.getAttribute('data-key');
    if(inp.type === 'checkbox') data[key] = inp.checked;
    else if(inp.type === 'number') data[key] = parseInt(inp.value) || 0;
    else data[key] = inp.value;
  }
  fetch('/admin/backup/api/config', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)})
  .then(function(r){return r.json()}).then(function(d){
    toast(d.ok ? 'تم حفظ الإعدادات' : 'فشل الحفظ', d.ok ? 'success' : 'error');
  });
}

function exportSQL() {
  fetch('/admin/backup/api/export-sql', {method:'POST', headers:{'X-CSRFToken': csrfToken()}})
  .then(function(r){return r.json()}).then(function(d){
    toast(d.ok ? 'تم تصدير SQL' : (d.error || 'فشل'), d.ok ? 'success' : 'error');
  });
}

function exportCSV() { toast('جاري تصدير CSV...', 'info'); }
function generateReport() { toast('جاري إنشاء التقرير...', 'info'); }

function toast(msg, type) {
  var colors = {success:'#22c55e', error:'#ef4444', warning:'#f59e0b', info:'#6366f1'};
  var bg = colors[type] || '#333';
  var el = document.createElement('div');
  el.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:12px 24px;border-radius:12px;color:#fff;background:' + bg + ';z-index:99999;font-size:14px;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,0.4);direction:rtl;';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(function(){
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.4s';
    setTimeout(function(){ document.body.removeChild(el); }, 400);
  }, 3000);
}

function restoreWizardReset() {
  byId('wizSelect').style.display = 'block';
  byId('wizPreview').style.display = 'none';
  byId('wizConfirm').style.display = 'none';
  byId('wizResult').style.display = 'none';
  var steps = document.querySelectorAll('.wizard-step');
  for(var i = 0; i < steps.length; i++) steps[i].classList.remove('active', 'completed');
  byId('wizStep1').classList.add('active');
  fetch('/admin/backup/api/list?per_page=100')
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok) return;
    var sel = byId('restoreBackupSelect');
    sel.innerHTML = '<option value="">-- اختر نسخة --</option>';
    d.backups.forEach(function(b){
      sel.innerHTML += '<option value="' + b.id + '">' + esc(b.filename) + ' (' + b.size_display + ')</option>';
    });
  });
}

document.addEventListener('DOMContentLoaded', function(){
  loadBackups();
  loadSchedules();
  loadAuditLogs();
  loadConfig();
  loadStats();
  var restoreTab = document.querySelector('[data-tab="restore"]');
  if(restoreTab) restoreTab.addEventListener('click', restoreWizardReset);
});
