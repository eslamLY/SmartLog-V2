/* ===== BioTime Device Management ===== */

function csrfToken() {
  var m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}

/* ── Tab Switching ── */
function switchTab(ctx, tab){
  var prefix = ctx === 'add' ? 'ad' : 'ed';
  var tabs = document.querySelectorAll('#'+ctx+'DeviceModal .dev-tab');
  var panels = document.querySelectorAll('#'+ctx+'DeviceModal .tab-panel');
  tabs.forEach(function(t,i){
    t.classList.toggle('active', t.dataset.tab === tab || (!t.dataset.tab && i === 0));
  });
  panels.forEach(function(p){
    p.style.display = p.id === 'tab_'+ctx+'_'+tab ? 'block' : 'none';
  });
}

/* ── Add/Edit modal control ── */
function openAddModal(){
  document.getElementById('addDeviceModal').classList.add('open');
  switchTab('add','basic');
}

function clearAddForm(){
  document.getElementById('addDeviceForm').reset();
  document.getElementById('adConnResult').innerHTML = '';
  ['err_adSerial','err_adIp','err_adMac'].forEach(function(id){ document.getElementById(id).textContent=''; });
}

function closeModal(id){ document.getElementById(id).classList.remove('open'); }

/* ── IP Validation ── */
function validateIpField(el){
  var err = document.getElementById('err_'+el.id);
  var v = el.value.trim();
  if(!v){ if(err)err.textContent=''; return; }
  var parts = v.split('.');
  if(parts.length !== 4 || parts.some(function(p){ return isNaN(p)||p<0||p>255; })){
    if(err) err.textContent = 'صيغة IP غير صالحة';
  } else {
    if(err) err.textContent = '';
  }
}

/* ── MAC Auto-format ── */
function autoFormatMac(el){
  var v = el.value.replace(/[^0-9A-Fa-f]/g,'').toUpperCase();
  var out = [];
  for(var i=0;i<v.length&&i<12;i+=2) out.push(v.substr(i,2));
  el.value = out.join(':');
  var err = document.getElementById('err_'+el.id);
  if(el.value.length === 17){
    if(err) err.textContent = '';
  } else if(el.value.length > 0) {
    if(err) err.textContent = 'الصيغة: XX:XX:XX:XX:XX:XX';
  } else {
    if(err) err.textContent = '';
  }
}

/* ── Test Connection ── */
async function testConn(ctx){
  var prefix = ctx === 'add' ? 'ad' : 'ed';
  var ip = document.getElementById(prefix+'Ip').value.trim();
  var port = document.getElementById(prefix+'Port').value || 4370;
  var resultDiv = document.getElementById(ctx+'ConnResult');
  if(!ip){ resultDiv.innerHTML = '<span style="color:#ef4444">⚠️ أدخل عنوان IP أولاً.</span>'; return; }
  resultDiv.innerHTML = '<span style="color:var(--muted)">⏳ جاري الاختبار...</span>';
  try {
    var r = await fetch('/admin/devices/test-connection', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify({ip:ip, port:parseInt(port)})
    });
    var data = await r.json();
    if(data.online){
      resultDiv.innerHTML = '<span style="color:#22c55e">✅ متصل — '+(data.ping_ms||'<1')+'ms</span>';
    } else {
      resultDiv.innerHTML = '<span style="color:#ef4444">❌ غير متصل: '+(data.error||'')+'</span>';
    }
  } catch(e){
    resultDiv.innerHTML = '<span style="color:#ef4444">❌ خطأ: '+e.message+'</span>';
  }
}

/* ── Fetch Device Info ── */
async function fetchDeviceInfo(ctx){
  var prefix = ctx === 'add' ? 'ad' : 'ed';
  var ip = document.getElementById(prefix+'Ip').value.trim();
  var port = document.getElementById(prefix+'Port').value || 4370;
  var pass = document.getElementById(prefix+'CommPass').value;
  if(!ip){ toast('أدخل IP أولاً.','err'); return; }
  try {
    var r = await fetch('/admin/devices/fetch-info', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify({ip:ip, port:parseInt(port), password:pass})
    });
    var data = await r.json();
    if(!data.ok){ toast(data.msg,'err'); return; }
    var info = data.info;
    if(info.firmware_ver) document.getElementById(prefix+'Firmware').value = info.firmware_ver;
    if(info.serial_no && !document.getElementById(prefix+'Serial').value) document.getElementById(prefix+'Serial').value = info.serial_no;
    if(info.fp_capacity) document.getElementById(prefix+'FpCap').value = info.fp_capacity;
    if(info.fp_enrolled) document.getElementById(prefix+'FpEnr').value = info.fp_enrolled;
    if(info.face_capacity) document.getElementById(prefix+'FaceCap').value = info.face_capacity;
    if(info.face_enrolled) document.getElementById(prefix+'FaceEnr').value = info.face_enrolled;
    if(info.card_capacity) document.getElementById(prefix+'CardCap').value = info.card_capacity;
    if(info.card_enrolled) document.getElementById(prefix+'CardEnr').value = info.card_enrolled;
    if(info.txlog_capacity) document.getElementById(prefix+'TxCap').value = info.txlog_capacity;
    if(info.txlog_used) document.getElementById(prefix+'TxUsed').value = info.txlog_used;
    toast('تم سحب معلومات الجهاز.','ok');
  } catch(e){ toast(e.message,'err'); }
}

/* ── Multi-select filter ── */
function filterMsList(input, listId){
  var q = input.value.toLowerCase();
  document.getElementById(listId).querySelectorAll('.ms-item').forEach(function(item){
    item.style.display = item.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}

/* ── Add Device ── */
async function doAddDevice(){
  var serial = document.getElementById('adSerial').value.trim();
  var name = document.getElementById('adName').value.trim();
  if(!serial || !name){ toast('الرقم التسلسلي والاسم مطلوبان.','err'); return; }
  var deptCbs = document.querySelectorAll('.adDeptCb:checked');
  var empCbs = document.querySelectorAll('.adEmpCb:checked');
  var depts = Array.from(deptCbs).map(function(cb){ return parseInt(cb.value); });
  var emps = Array.from(empCbs).map(function(cb){ return parseInt(cb.value); });
  var data = {
    serial_no: serial,
    name: name,
    device_type: document.getElementById('adType').value,
    location: document.getElementById('adLocation').value.trim(),
    device_model: document.getElementById('adModel').value,
    ip_address: document.getElementById('adIp').value.trim(),
    port: parseInt(document.getElementById('adPort').value) || 4370,
    mac_address: document.getElementById('adMac').value.trim(),
    protocol: document.getElementById('adProtocol').value,
    comm_password: document.getElementById('adCommPass').value,
    firmware_ver: document.getElementById('adFirmware').value.trim(),
    manufacture_date: document.getElementById('adMfgDate').value,
    warranty_expiry: document.getElementById('adWarranty').value,
    fp_capacity: parseInt(document.getElementById('adFpCap').value) || 0,
    fp_enrolled: parseInt(document.getElementById('adFpEnr').value) || 0,
    face_capacity: parseInt(document.getElementById('adFaceCap').value) || 0,
    face_enrolled: parseInt(document.getElementById('adFaceEnr').value) || 0,
    card_capacity: parseInt(document.getElementById('adCardCap').value) || 0,
    card_enrolled: parseInt(document.getElementById('adCardEnr').value) || 0,
    txlog_capacity: parseInt(document.getElementById('adTxCap').value) || 0,
    txlog_used: parseInt(document.getElementById('adTxUsed').value) || 0,
    access_mode: document.getElementById('adAccessMode').value,
    door_relay_enabled: document.getElementById('adDoorRelay').checked,
    anti_passback_enabled: document.getElementById('adAntiPass').checked,
    auto_sync_enabled: document.getElementById('adAutoSync').checked,
    sync_interval: parseInt(document.getElementById('adSyncInterval').value) || 5,
    sync_window_start: document.getElementById('adSyncStart').value,
    sync_window_end: document.getElementById('adSyncEnd').value,
    assigned_departments: depts,
    assigned_employees: emps,
  };
  try {
    var r = await fetch('/admin/devices/add', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify(data)
    });
    var res = await r.json();
    toast(res.msg, res.ok ? 'ok' : 'err');
    if(res.ok){ closeModal('addDeviceModal'); setTimeout(function(){ location.reload(); }, 1000); }
  } catch(e){ toast(e.message,'err'); }
}

/* ── Edit Device ── */
async function openEditModal(id){
  document.getElementById('edId').value = id;
  try {
    var r = await fetch('/api/admin/devices/'+id);
    var data = await r.json();
    if(!data.ok){ toast(data.msg,'err'); return; }
    var d = data.device;
    document.getElementById('edSerial').value = d.serial_no;
    document.getElementById('edName').value = d.name;
    document.getElementById('edModel').value = d.device_model || '';
    document.getElementById('edType').value = d.device_type;
    document.getElementById('edLocation').value = d.location || '';
    document.getElementById('edIp').value = d.ip_address || '';
    document.getElementById('edPort').value = d.port || 4370;
    document.getElementById('edMac').value = d.mac_address || '';
    document.getElementById('edProtocol').value = d.protocol || 'tcp_ip';
    document.getElementById('edCommPass').value = '';
    document.getElementById('edFirmware').value = d.firmware_ver || '';
    document.getElementById('edFpCap').value = d.fp_capacity || 0;
    document.getElementById('edFpEnr').value = d.fp_enrolled || 0;
    document.getElementById('edFaceCap').value = d.face_capacity || 0;
    document.getElementById('edFaceEnr').value = d.face_enrolled || 0;
    document.getElementById('edCardCap').value = d.card_capacity || 0;
    document.getElementById('edCardEnr').value = d.card_enrolled || 0;
    document.getElementById('edTxCap').value = d.txlog_capacity || 0;
    document.getElementById('edTxUsed').value = d.txlog_used || 0;
    document.getElementById('edAccessMode').value = d.access_mode || 'fingerprint';
    document.getElementById('edDoorRelay').checked = d.door_relay_enabled;
    document.getElementById('edAntiPass').checked = d.anti_passback_enabled;
    document.getElementById('edAutoSync').checked = d.auto_sync_enabled;
    document.getElementById('edSyncInterval').value = d.sync_interval || 5;
    document.getElementById('edTitle').textContent = 'تعديل: '+d.name;
    document.getElementById('editDeviceModal').classList.add('open');
    switchTab('edit','basic');
  } catch(e){ toast(e.message,'err'); }
}

async function doEditDevice(){
  var id = document.getElementById('edId').value;
  var data = {
    name: document.getElementById('edName').value.trim(),
    device_type: document.getElementById('edType').value,
    location: document.getElementById('edLocation').value.trim(),
    device_model: document.getElementById('edModel').value,
    ip_address: document.getElementById('edIp').value.trim(),
    port: parseInt(document.getElementById('edPort').value) || 4370,
    mac_address: document.getElementById('edMac').value.trim(),
    protocol: document.getElementById('edProtocol').value,
    comm_password: document.getElementById('edCommPass').value || null,
    firmware_ver: document.getElementById('edFirmware').value.trim(),
    fp_capacity: parseInt(document.getElementById('edFpCap').value) || 0,
    fp_enrolled: parseInt(document.getElementById('edFpEnr').value) || 0,
    face_capacity: parseInt(document.getElementById('edFaceCap').value) || 0,
    face_enrolled: parseInt(document.getElementById('edFaceEnr').value) || 0,
    card_capacity: parseInt(document.getElementById('edCardCap').value) || 0,
    card_enrolled: parseInt(document.getElementById('edCardEnr').value) || 0,
    txlog_capacity: parseInt(document.getElementById('edTxCap').value) || 0,
    txlog_used: parseInt(document.getElementById('edTxUsed').value) || 0,
    access_mode: document.getElementById('edAccessMode').value,
    door_relay_enabled: document.getElementById('edDoorRelay').checked,
    anti_passback_enabled: document.getElementById('edAntiPass').checked,
    auto_sync_enabled: document.getElementById('edAutoSync').checked,
    sync_interval: parseInt(document.getElementById('edSyncInterval').value) || 5,
  };
  try {
    var r = await fetch('/admin/devices/'+id+'/edit', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify(data)
    });
    var res = await r.json();
    toast(res.msg, res.ok ? 'ok' : 'err');
    if(res.ok){ closeModal('editDeviceModal'); setTimeout(function(){ location.reload(); }, 1000); }
  } catch(e){ toast(e.message,'err'); }
}

/* ── View Device ── */
async function openViewModal(id){
  document.getElementById('viewDeviceModal').classList.add('open');
  document.getElementById('vdContent').innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted)"><i class="ti ti-loader" style="font-size:28px;display:block;margin-bottom:8px"></i>جاري التحميل...</div>';
  try {
    var r = await fetch('/api/admin/devices/'+id);
    var data = await r.json();
    if(!data.ok){ document.getElementById('vdContent').innerHTML='<div style="text-align:center;padding:32px;color:#ef4444">خطأ في التحميل</div>'; return; }
    var d = data.device;
    document.getElementById('vdTitle').textContent = d.name;
    document.getElementById('vdContent').innerHTML = renderDeviceDetail(d);
  } catch(e){ document.getElementById('vdContent').innerHTML='<div style="text-align:center;padding:32px;color:#ef4444">'+e.message+'</div>'; }
}

function renderDeviceDetail(d){
  var statusIcn = d.online_status === 'online' ? '🟢' : d.online_status === 'warning' ? '🟡' : '🔴';
  var statusTxt = d.online_status === 'online' ? 'متصل' : d.online_status === 'warning' ? 'تحذير' : 'غير متصل';
  var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:13px">';
  html += '<div><span style="color:var(--muted2)">الرقم التسلسلي:</span> <strong>'+esc(d.serial_no)+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">الموديل:</span> <strong>'+esc(d.device_model_label)+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">IP:</span> <strong>'+esc(d.ip_address||'—')+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">MAC:</span> <strong>'+esc(d.mac_address||'—')+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">الموقع:</span> <strong>'+esc(d.location||'—')+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">الحالة:</span> <strong>'+statusIcn+' '+statusTxt+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">النوع:</span> <strong>'+esc(d.device_type)+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">البروتوكول:</span> <strong>'+esc(d.protocol).toUpperCase()+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">إصدار البرنامج:</span> <strong>'+esc(d.firmware_ver||'—')+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">وضع الدخول:</span> <strong>'+esc(d.access_mode)+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">آخر مزامنة:</span> <strong>'+(d.last_sync||'—')+'</strong></div>';
  html += '<div><span style="color:var(--muted2)">أخر اتصال:</span> <strong>'+(d.last_online_at||'—')+'</strong></div>';
  var pct = d.storage_used_percent || 0;
  var barColor = pct > 80 ? '#ef4444' : pct > 50 ? '#f59e0b' : '#22c55e';
  html += '</div>';
  html += '<div style="margin-top:16px;border-top:1px solid var(--border);padding-top:12px">';
  html += '<div style="font-size:13px;font-weight:600;margin-bottom:6px">سعة التخزين</div>';
  html += '<div class="cap-bar"><div class="cap-label"><span>سجل المعاملات</span><span>'+esc(d.txlog_used||'0')+' / '+esc(d.txlog_capacity||'∞')+'</span></div>';
  html += '<div class="cap-track"><div class="cap-fill" style="width:'+pct+'%;background:'+barColor+'"></div></div></div>';
  html += '<div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px">';
  html += '<div><span style="color:var(--muted2)">بصمات:</span> '+esc(d.fp_enrolled)+' / '+esc(d.fp_capacity)+'</div>';
  html += '<div><span style="color:var(--muted2)">وجوه:</span> '+esc(d.face_enrolled)+' / '+esc(d.face_capacity)+'</div>';
  html += '<div><span style="color:var(--muted2)">بطاقات:</span> '+esc(d.card_enrolled)+' / '+esc(d.card_capacity)+'</div>';
  html += '<div><span style="color:var(--muted2)">موظفون حالياً:</span> '+(d.currently_clocked_in||'0')+'</div>';
  html += '</div></div>';
  return html;
}

/* ── Health Modal ── */
async function openHealthModal(id){
  document.getElementById('healthDeviceModal').classList.add('open');
  document.getElementById('hdContent').innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted)"><i class="ti ti-loader" style="font-size:28px;display:block;margin-bottom:8px"></i>جاري التحميل...</div>';
  try {
    var r = await fetch('/admin/devices/'+id+'/health');
    var data = await r.json();
    if(!data.ok){ document.getElementById('hdContent').innerHTML='<div style="text-align:center;padding:32px;color:#ef4444">خطأ</div>'; return; }
    var d = data.device;
    document.getElementById('hdTitle').textContent = 'صحة: '+d.name;
    var html = '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:16px">';
    html += '<div class="card" style="padding:12px;text-align:center"><div style="font-size:24px;font-weight:800;color:#22c55e">'+(data.uptime_24h||'100')+'%</div><div style="font-size:11px;color:var(--muted2)">نسبة التشغيل (24 ساعة)</div></div>';
    html += '<div class="card" style="padding:12px;text-align:center"><div style="font-size:24px;font-weight:800;color:var(--accent)">'+esc(d.currently_clocked_in||'0')+'</div><div style="font-size:11px;color:var(--muted2)">موظفون حالياً</div></div>';
    html += '<div class="card" style="padding:12px;text-align:center"><div style="font-size:24px;font-weight:800;color:#f59e0b">'+esc(d.today_transactions||'0')+'</div><div style="font-size:11px;color:var(--muted2)">معاملات اليوم</div></div>';
    html += '</div>';

    if(data.events && data.events.length){
      html += '<div style="border-top:1px solid var(--border);padding-top:12px"><div style="font-size:13px;font-weight:600;margin-bottom:8px">آخر الأحداث</div>';
      html += '<div style="max-height:200px;overflow-y:auto">';
      data.events.forEach(function(e){
        var icn = e.type === 'sync_success' ? '✅' : e.type === 'sync_failed' ? '❌' : e.type === 'restart' ? '🔄' : e.type === 'create' ? '➕' : '📝';
        html += '<div style="display:flex;gap:8px;padding:6px 0;border-bottom:1px solid var(--border2);font-size:12px">';
        html += '<span>'+icn+'</span>';
        html += '<span style="flex:1">'+(e.message||e.type)+'</span>';
        if(e.error_code) html += '<span style="color:#ef4444">'+esc(e.error_code)+'</span>';
        html += '<span style="color:var(--muted2)">'+(e.created_at||'')+'</span></div>';
      });
      html += '</div></div>';
    }
    document.getElementById('hdContent').innerHTML = html;
  } catch(e){ document.getElementById('hdContent').innerHTML='<div style="text-align:center;padding:32px;color:#ef4444">'+e.message+'</div>'; }
}

/* ── Sync Single Device ── */
async function syncOne(id){
  var btn = event.target.closest('button');
  btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader"></i>';
  try {
    var r = await fetch('/admin/devices/'+id+'/sync', {method:'POST', headers:{'X-CSRFToken': csrfToken()}});
    var data = await r.json();
    toast(data.msg, data.ok ? 'ok' : 'err');
    if(data.ok){
      var card = document.getElementById('device-'+id);
      if(card){ card.dataset.online = 'true'; var dot = card.querySelector('.status-dot'); if(dot) dot.className = 'status-dot online'; }
    }
  } catch(e){ toast(e.message,'err'); }
  btn.disabled = false; btn.innerHTML = '<i class="ti ti-refresh"></i> مزامنة';
}

/* ── Bulk Sync ── */
async function bulkSync(){
  if(!confirm('مزامنة جميع الأجهزة النشطة؟')) return;
  try {
    var r = await fetch('/admin/devices/bulk-sync', {method:'POST', headers:{'X-CSRFToken': csrfToken()}});
    var data = await r.json();
    var ok = data.results.filter(function(r){ return r.status==='synced'; }).length;
    var fail = data.results.filter(function(r){ return r.status==='failed'; }).length;
    toast('تمت المزامنة: '+ok+' نجاح, '+fail+' فشل.', fail ? 'err' : 'ok');
    if(fail === 0) setTimeout(function(){ location.reload(); }, 1200);
  } catch(e){ toast(e.message,'err'); }
}

/* ── Toggle ── */
async function toggleDevice(id){
  try {
    var r = await fetch('/admin/devices/'+id+'/toggle', {method:'POST', headers:{'X-CSRFToken': csrfToken()}});
    var data = await r.json();
    toast(data.msg, 'ok');
    setTimeout(function(){ location.reload(); }, 1000);
  } catch(e){ toast(e.message,'err'); }
}

/* ── Restart ── */
async function restartDevice(id){
  if(!confirm('إعادة تشغيل الجهاز؟ قد يستغرق ذلك بضع ثوان.')) return;
  try {
    var r = await fetch('/admin/devices/'+id+'/restart', {method:'POST', headers:{'X-CSRFToken': csrfToken()}});
    var data = await r.json();
    toast(data.msg, data.ok ? 'ok' : 'err');
  } catch(e){ toast(e.message,'err'); }
}

/* ── Delete ── */
function deleteDevice(id, name){
  document.getElementById('delDeviceId').value = id;
  document.getElementById('delDeviceName').textContent = 'حذف الجهاز: '+name;
  document.getElementById('deleteDeviceModal').classList.add('open');
}
async function doDeleteDevice(){
  var id = document.getElementById('delDeviceId').value;
  var action = document.getElementById('delDeviceAttAction').value;
  try {
    var r = await fetch('/admin/devices/'+id+'/delete', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify({attendance_action: action})
    });
    var data = await r.json();
    toast(data.msg, 'ok');
    closeModal('deleteDeviceModal');
    setTimeout(function(){ location.reload(); }, 1000);
  } catch(e){ toast(e.message,'err'); }
}

/* ── Import CSV ── */
async function importDevices(input){
  var f = input.files[0];
  if(!f) return;
  var fd = new FormData();
  fd.append('file', f);
  try {
    var r = await fetch('/admin/devices/import', {method:'POST', body: fd});
    var data = await r.json();
    toast(data.msg, data.ok ? 'ok' : 'err');
    if(data.ok) setTimeout(function(){ location.reload(); }, 1200);
  } catch(e){ toast(e.message,'err'); }
  input.value = '';
}

/* ── Scan Network (auto-detect) ── */
async function detectDevice(ctx){
  var prefix = ctx === 'add' ? 'ad' : 'ed';
  var el = document.getElementById(prefix+'Ip');
  var subnet = el.value.trim();
  if(!subnet){ subnet = '192.168.1'; }
  else {
    var parts = subnet.split('.');
    if(parts.length === 4) subnet = parts.slice(0,3).join('.');
  }
  var btn = event.target;
  btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader"></i> جاري الفحص...';
  try {
    var r = await fetch('/admin/devices/scan-network', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify({subnet: subnet})
    });
    var data = await r.json();
    if(data.devices && data.devices.length){
      var dev = data.devices[0];
      document.getElementById(prefix+'Ip').value = dev.ip;
      if(dev.serial_no && !document.getElementById(prefix+'Serial').value) document.getElementById(prefix+'Serial').value = dev.serial_no;
      if(dev.firmware) document.getElementById(prefix+'Firmware').value = dev.firmware;
      toast('تم العثور على جهاز: '+dev.ip, 'ok');
    } else {
      toast('لم يتم العثور على أجهزة.', 'err');
    }
  } catch(e){ toast(e.message,'err'); }
  btn.disabled = false; btn.innerHTML = '<i class="ti ti-search"></i> كشف تلقائي';
}

/* ── API helper ── */
function esc(s){ if(!s) return ''; var d=document.createElement('div'); d.appendChild(document.createTextNode(s)); return d.innerHTML; }
async function api(url, data){
  var r = await fetch(url, {
    method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
    body: JSON.stringify(data||{})
  });
  return r.json();
}
