let allRoles = [];
let allPermissions = [];
let allEmployees = [];
let allDepartments = [];
let currentTab = 'roles';

function byId(id) { return document.getElementById(id); }
function esc(s) { if(!s) return ''; return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function toast(msg, type) {
  var c = {success:'#22c55e',error:'#ef4444',warning:'#f59e0b',info:'#6366f1'};
  var el = document.createElement('div');
  el.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:12px 24px;border-radius:12px;color:#fff;background:' + (c[type]||'#333') + ';z-index:99999;font-size:14px;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,0.4);direction:rtl;';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(function(){ el.style.opacity='0'; el.style.transition='opacity 0.4s'; setTimeout(function(){document.body.removeChild(el);},400); }, 3000);
}

function closeModal(id) { var el = byId(id); if(el) { el.classList.remove('open'); el.style.display = 'none'; } }

function switchTab(name) {
  currentTab = name;
  var tabs = document.querySelectorAll('.rbac-container .tab');
  for(var i = 0; i < tabs.length; i++) tabs[i].classList.toggle('active', tabs[i].getAttribute('data-tab') === name);
  var contents = document.querySelectorAll('.rbac-container .tab-content');
  for(var i = 0; i < contents.length; i++) contents[i].classList.toggle('active', contents[i].id === 'tab-' + name);
  if(name === 'roles') loadRoles();
  else if(name === 'permissions') loadPermissions();
  else if(name === 'assignments') loadAssignments();
  else if(name === 'analytics') loadAnalytics();
  else if(name === 'requests') loadRequests();
  else if(name === 'audit') loadAuditLogs();
}

function api(url, method, data) {
  return fetch(url, {
    method: method || 'GET',
    headers: data ? {'Content-Type':'application/json'} : undefined,
    body: data ? JSON.stringify(data) : undefined,
  }).then(function(r){return r.json()});
}

function loadRoles() {
  api('/admin/rbac/api/roles').then(function(d){
    if(!d.ok) return;
    allRoles = d.roles;
    var tb = byId('rolesTableBody');
    if(!tb) return;
    tb.innerHTML = '';
    if(!d.roles.length) { tb.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:30px">لا توجد أدوار</td></tr>'; return; }
    var riskColors = {low:'badge-success',medium:'badge-warning',high:'badge-danger'};
    d.roles.forEach(function(r){
      var riskCls = riskColors[r.risk_level] || 'badge-muted';
      tb.innerHTML += '<tr><td><strong>' + esc(r.name) + '</strong></td>'
        + '<td style="color:var(--muted)">' + esc(r.description||'-') + '</td>'
        + '<td><span class="badge badge-muted">' + r.scope + '</span></td>'
        + '<td>' + (r.parent_name || '-') + '</td>'
        + '<td>' + (r.permissions||[]).length + '</td>'
        + '<td>' + (r.child_count || 0) + '</td>'
        + '<td><span class="badge ' + riskCls + '">' + r.risk_level + '</span></td>'
        + '<td style="white-space:nowrap">'
        + '<button class="btn-icon" onclick="editRole(' + r.id + ')" title="تعديل"><i class="fas fa-edit"></i></button> '
        + (r.is_system ? '' : '<button class="btn-icon" style="color:var(--red)" onclick="deleteRole(' + r.id + ')" title="حذف"><i class="fas fa-trash"></i></button>')
        + '</td></tr>';
    });
  });
}

function loadPermissions() {
  api('/admin/rbac/api/permissions').then(function(d){
    if(!d.ok) return;
    allPermissions = d.permissions;
    renderPermissionsTable(d.permissions);
  });
}

function renderPermissionsTable(perms) {
  var tb = byId('permissionsTableBody');
  if(!tb) return;
  tb.innerHTML = '';
  if(!perms.length) { tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:30px">لا توجد صلاحيات</td></tr>'; return; }
  perms.forEach(function(p){
    var riskIcon = p.is_high_risk ? '<i class="fas fa-exclamation-triangle" style="color:var(--red)"></i>' : '<i class="fas fa-check" style="color:var(--green)"></i>';
    var faIcon = p.requires_2fa ? '<i class="fas fa-check" style="color:var(--green)"></i>' : '<i class="fas fa-times" style="color:var(--muted)"></i>';
    var appIcon = p.requires_approval ? '<i class="fas fa-check" style="color:var(--green)"></i>' : '<i class="fas fa-times" style="color:var(--muted)"></i>';
    tb.innerHTML += '<tr><td>' + esc(p.name_ar || p.name) + '</td>'
      + '<td><code>' + esc(p.code) + '</code></td>'
      + '<td><span class="badge badge-muted">' + esc(p.module||'-') + '</span></td>'
      + '<td>' + riskIcon + '</td>'
      + '<td>' + faIcon + '</td>'
      + '<td>' + appIcon + '</td>'
      + '<td><button class="btn-icon" onclick="editPermission(' + p.id + ')" title="تعديل"><i class="fas fa-edit"></i></button></td></tr>';
  });
}

function filterPermissions() {
  var q = (byId('permFilter').value || '').toLowerCase();
  var filtered = allPermissions.filter(function(p){
    return (p.name||'').toLowerCase().includes(q) || (p.code||'').toLowerCase().includes(q) || (p.module||'').toLowerCase().includes(q);
  });
  renderPermissionsTable(filtered);
}

function openRoleModal() {
  byId('editRoleId').value = '';
  byId('roleModalTitle').textContent = 'دور جديد';
  byId('roleName').value = '';
  byId('roleNameAr').value = '';
  byId('roleDesc').value = '';
  byId('roleScope').value = 'department';
  byId('roleRisk').value = 'low';
  byId('roleMax').value = '';
  // Populate parent select
  var parentSel = byId('roleParent');
  parentSel.innerHTML = '<option value="">بدون</option>';
  allRoles.forEach(function(r){ parentSel.innerHTML += '<option value="' + r.id + '">' + esc(r.name) + '</option>'; });
  // Populate permissions checkboxes
  var pc = byId('rolePermsCheckboxes');
  pc.innerHTML = '';
  allPermissions.forEach(function(p){
    pc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:13px"><input type="checkbox" value="' + p.id + '" class="role-perm-cb"> ' + esc(p.name_ar || p.name) + ' <code style="color:var(--muted)">' + esc(p.code) + '</code></label>';
  });
  // Populate departments
  var dc = byId('roleDeptCheckboxes');
  dc.innerHTML = '';
  allDepartments.forEach(function(d){
    dc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:13px"><input type="checkbox" value="' + d.id + '" class="role-dept-cb"> ' + esc(d.name_ar) + '</label>';
  });
  byId('roleModal').classList.add('open');
  byId('roleModal').style.display = 'flex';
}

function editRole(id) {
  var r = allRoles.find(function(x){return x.id===id});
  if(!r) return;
  byId('editRoleId').value = id;
  byId('roleModalTitle').textContent = 'تعديل: ' + r.name;
  byId('roleName').value = r.name;
  byId('roleNameAr').value = r.name_ar || '';
  byId('roleDesc').value = r.description || '';
  byId('roleScope').value = r.scope;
  byId('roleRisk').value = r.risk_level;
  byId('roleMax').value = r.max_assignees || '';
  var parentSel = byId('roleParent');
  parentSel.innerHTML = '<option value="">بدون</option>';
  allRoles.forEach(function(r2){
    if(r2.id !== id) parentSel.innerHTML += '<option value="' + r2.id + '"' + (r2.id===r.parent_id?' selected':'') + '>' + esc(r2.name) + '</option>';
  });
  var pc = byId('rolePermsCheckboxes');
  pc.innerHTML = '';
  var rolePermIds = (r.permissions||[]).map(function(p){return p.id});
  allPermissions.forEach(function(p){
    var checked = rolePermIds.indexOf(p.id) !== -1 ? ' checked' : '';
    pc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:13px"><input type="checkbox" value="' + p.id + '" class="role-perm-cb"' + checked + '> ' + esc(p.name_ar || p.name) + '</label>';
  });
  var dc = byId('roleDeptCheckboxes');
  dc.innerHTML = '';
  var roleDeptIds = r.department_ids || [];
  allDepartments.forEach(function(d){
    var checked = roleDeptIds.indexOf(d.id) !== -1 ? ' checked' : '';
    dc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:13px"><input type="checkbox" value="' + d.id + '" class="role-dept-cb"' + checked + '> ' + esc(d.name_ar) + '</label>';
  });
  byId('roleModal').classList.add('open');
  byId('roleModal').style.display = 'flex';
}

function saveRole() {
  var id = byId('editRoleId').value;
  var permCbs = document.querySelectorAll('#rolePermsCheckboxes input.role-perm-cb:checked');
  var permIds = [];
  for(var i = 0; i < permCbs.length; i++) permIds.push(parseInt(permCbs[i].value));
  var deptCbs = document.querySelectorAll('#roleDeptCheckboxes input.role-dept-cb:checked');
  var deptIds = [];
  for(var i = 0; i < deptCbs.length; i++) deptIds.push(parseInt(deptCbs[i].value));
  var data = {
    name: byId('roleName').value,
    name_ar: byId('roleNameAr').value,
    description: byId('roleDesc').value,
    parent_id: parseInt(byId('roleParent').value) || null,
    scope: byId('roleScope').value,
    risk_level: byId('roleRisk').value,
    max_assignees: parseInt(byId('roleMax').value) || null,
    permission_ids: permIds,
    department_ids: deptIds,
  };
  if(!data.name) { toast('الرجاء إدخال اسم الدور', 'warning'); return; }
  var url = id ? '/admin/rbac/api/roles/' + id : '/admin/rbac/api/roles';
  var method = id ? 'PUT' : 'POST';
  api(url, method, data).then(function(d){
    if(d.ok) { toast(id ? 'تم تحديث الدور' : 'تم إنشاء الدور', 'success'); closeModal('roleModal'); loadRoles(); }
    else toast(d.error || 'فشل الحفظ', 'error');
  });
}

function deleteRole(id) {
  if(!confirm('هل أنت متأكد من حذف هذا الدور؟')) return;
  api('/admin/rbac/api/roles/' + id, 'DELETE').then(function(d){
    if(d.ok) { toast('تم الحذف', 'success'); loadRoles(); }
    else toast(d.error || 'فشل الحذف', 'error');
  });
}

function openPermissionModal() {
  byId('editPermId').value = '';
  byId('permName').value = '';
  byId('permNameAr').value = '';
  byId('permCode').value = '';
  byId('permModule').value = '';
  byId('permDesc').value = '';
  byId('permHighRisk').checked = false;
  byId('permRequire2FA').checked = false;
  byId('permRequireApproval').checked = false;
  byId('permModal').classList.add('open');
  byId('permModal').style.display = 'flex';
}

function editPermission(id) {
  var p = allPermissions.find(function(x){return x.id===id});
  if(!p) return;
  byId('editPermId').value = id;
  byId('permName').value = p.name;
  byId('permNameAr').value = p.name_ar || '';
  byId('permCode').value = p.code;
  byId('permModule').value = p.module || '';
  byId('permDesc').value = p.description || '';
  byId('permHighRisk').checked = p.is_high_risk;
  byId('permRequire2FA').checked = p.requires_2fa;
  byId('permRequireApproval').checked = p.requires_approval;
  byId('permModal').classList.add('open');
  byId('permModal').style.display = 'flex';
}

function savePermission() {
  var id = byId('editPermId').value;
  var data = {
    name: byId('permName').value,
    name_ar: byId('permNameAr').value,
    code: byId('permCode').value,
    module: byId('permModule').value,
    description: byId('permDesc').value,
    is_high_risk: byId('permHighRisk').checked,
    requires_2fa: byId('permRequire2FA').checked,
    requires_approval: byId('permRequireApproval').checked,
  };
  if(!data.name || !data.code) { toast('الرجاء إدخال الاسم والكود', 'warning'); return; }
  var url = id ? '/admin/rbac/api/permissions/' + id : '/admin/rbac/api/permissions';
  var method = id ? 'PUT' : 'POST';
  api(url, method, data).then(function(d){
    if(d.ok) { toast(id ? 'تم التحديث' : 'تم الإنشاء', 'success'); closeModal('permModal'); loadPermissions(); }
    else toast(d.error || 'فشل الحفظ', 'error');
  });
}

function loadAssignments() {
  api('/admin/rbac/api/assignments').then(function(d){
    if(!d.ok) return;
    var tb = byId('assignmentsTableBody');
    if(!tb) return;
    tb.innerHTML = '';
    if(!d.assignments.length) { tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:30px">لا توجد تعيينات</td></tr>'; return; }
    d.assignments.forEach(function(a){
      var typeNames = {permanent:'دائم',temporary:'مؤقت',seasonal:'موسمي','shift-based':'حسب الوردية'};
      var typeName = typeNames[a.assignment_type] || a.assignment_type;
      var status = a.is_active ? '<span class="badge badge-success">نشط</span>' : '<span class="badge badge-muted">منتهي</span>';
      tb.innerHTML += '<tr><td>' + esc(a.employee_name||'') + '</td>'
        + '<td><strong>' + esc(a.role_name||'') + '</strong></td>'
        + '<td><span class="badge badge-muted">' + typeName + '</span></td>'
        + '<td style="color:var(--muted)">' + (a.effective_date||'-') + '</td>'
        + '<td style="color:var(--muted)">' + (a.expiry_date||'-') + '</td><td>' + status + '</td>'
        + '<td>' + (a.is_active ? '<button class="btn-icon" style="color:var(--red)" onclick="revokeAssignment(' + a.id + ')" title="إنهاء"><i class="fas fa-ban"></i></button>' : '') + '</td></tr>';
    });
  });
}

function openAssignModal() {
  populateEmployeeSelect('assignEmployee');
  populateRoleSelect('assignRole');
  byId('assignType').value = 'permanent';
  byId('assignPrimary').value = 'true';
  byId('assignStart').value = new Date().toISOString().slice(0,10);
  byId('assignEnd').value = '';
  byId('assignNotes').value = '';
  byId('assignSeasonal').style.display = 'none';
  byId('assignDates').style.display = 'grid';
  byId('assignModal').classList.add('open');
  byId('assignModal').style.display = 'flex';
}

function toggleAssignDates() {
  var t = byId('assignType').value;
  byId('assignDates').style.display = (t === 'temporary' || t === 'seasonal') ? 'grid' : 'none';
  byId('assignSeasonal').style.display = (t === 'seasonal') ? 'block' : 'none';
}

function saveAssignment() {
  var seasonalCbs = document.querySelectorAll('#seasonMonths input:checked');
  var seasonalMonths = [];
  for(var i = 0; i < seasonalCbs.length; i++) seasonalMonths.push(parseInt(seasonalCbs[i].value));
  var data = {
    employee_id: parseInt(byId('assignEmployee').value),
    role_id: parseInt(byId('assignRole').value),
    is_primary: byId('assignPrimary').value === 'true',
    assignment_type: byId('assignType').value,
    effective_date: byId('assignStart').value,
    expiry_date: byId('assignEnd').value || null,
    season_months: seasonalMonths.length ? seasonalMonths : null,
    notes: byId('assignNotes').value,
  };
  if(!data.employee_id || !data.role_id) { toast('الرجاء اختيار الموظف والدور', 'warning'); return; }
  api('/admin/rbac/api/assignments', 'POST', data).then(function(d){
    if(d.ok) { toast('تم التعيين', 'success'); closeModal('assignModal'); loadAssignments(); }
    else toast(d.error || 'فشل', 'error');
  });
}

function revokeAssignment(id) {
  if(!confirm('إنهاء هذا التعيين؟')) return;
  api('/admin/rbac/api/assignments/' + id + '/revoke', 'POST').then(function(d){
    if(d.ok) { toast('تم الإنهاء', 'success'); loadAssignments(); }
    else toast('فشل', 'error');
  });
}

function openBulkAssignModal() {
  api('/admin/rbac/api/employees').then(function(d){
    if(!d.ok) return;
    allEmployees = d.employees;
    var container = byId('bulkEmpCheckboxes');
    container.innerHTML = '';
    d.employees.forEach(function(e){
      container.innerHTML += '<label style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:13px"><input type="checkbox" value="' + e.id + '" class="bulk-emp-cb"> ' + esc(e.full_name) + ' <span style="color:var(--muted)">(' + esc(e.department||'') + ')</span></label>';
    });
  });
  populateRoleSelect('bulkRole');
  byId('bulkAssignType').value = 'permanent';
  byId('bulkStart').value = new Date().toISOString().slice(0,10);
  byId('bulkEnd').value = '';
  byId('bulkNotes').value = '';
  byId('bulkAssignModal').classList.add('open');
  byId('bulkAssignModal').style.display = 'flex';
}

function saveBulkAssign() {
  var empCbs = document.querySelectorAll('#bulkEmpCheckboxes input.bulk-emp-cb:checked');
  var empIds = [];
  for(var i = 0; i < empCbs.length; i++) empIds.push(parseInt(empCbs[i].value));
  if(!empIds.length) { toast('اختر موظفاً واحداً على الأقل', 'warning'); return; }
  var data = {
    employee_ids: empIds,
    role_id: parseInt(byId('bulkRole').value),
    assignment_type: byId('bulkAssignType').value,
    effective_date: byId('bulkStart').value,
    expiry_date: byId('bulkEnd').value || null,
    notes: byId('bulkNotes').value,
  };
  api('/admin/rbac/api/assignments/bulk', 'POST', data).then(function(d){
    if(d.ok) {
      toast('تم تعيين ' + empIds.length + ' موظف', 'success');
      closeModal('bulkAssignModal');
      loadAssignments();
    } else toast(d.error || 'فشل', 'error');
  });
}

function loadAnalytics() {
  api('/admin/rbac/api/analytics').then(function(d){
    if(!d.ok) return;
    var el = function(id){return byId(id)};
    if(el('statRoles')) el('statRoles').textContent = d.total_roles;
    if(el('statPermissions')) el('statPermissions').textContent = d.total_permissions;
    if(el('statAssignments')) el('statAssignments').textContent = d.total_assignments;
    if(el('statCoverage')) el('statCoverage').textContent = d.coverage + '%';
    if(el('statHighRisk')) el('statHighRisk').textContent = d.high_risk_permissions;
    if(el('statPending')) el('statPending').textContent = d.pending_requests;
    if(window.renderRoleChart && d.roles_distribution) renderRoleChart(d.roles_distribution);
    // Populate matrix selects
    var s1 = byId('matrixRole1');
    var s2 = byId('matrixRole2');
    if(s1 && s2 && allRoles.length) {
      s1.innerHTML = '';
      s2.innerHTML = '';
      allRoles.forEach(function(r){
        s1.innerHTML += '<option value="' + r.id + '">' + esc(r.name) + '</option>';
        s2.innerHTML += '<option value="' + r.id + '">' + esc(r.name) + '</option>';
      });
    }
    // Populate who-has select
    var ws = byId('whoHasPermSelect');
    if(ws && allPermissions.length) {
      ws.innerHTML = '<option value="">-- اختر صلاحية --</option>';
      allPermissions.forEach(function(p){
        ws.innerHTML += '<option value="' + p.code + '">' + esc(p.name_ar || p.name) + '</option>';
      });
    }
    // High risk list
    if(el('highRiskList')) {
      var hrPerms = allPermissions.filter(function(p){return p.is_high_risk});
      var html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px">';
      hrPerms.forEach(function(p){
        html += '<div style="padding:10px;border:1px solid rgba(239,68,68,0.3);border-radius:8px;background:rgba(239,68,68,0.05)">'
          + '<div style="font-weight:600;font-size:13px">' + esc(p.name_ar || p.name) + '</div>'
          + '<code style="font-size:11px;color:var(--muted)">' + esc(p.code) + '</code></div>';
      });
      html += '</div>';
      el('highRiskList').innerHTML = hrPerms.length ? html : '<p style="color:var(--muted)">لا توجد صلاحيات عالية المخاطر</p>';
    }
  });
}

function showMatrix() {
  var r1 = parseInt(byId('matrixRole1').value);
  var r2 = parseInt(byId('matrixRole2').value);
  if(!r1 || !r2) { toast('اختر دورين للمقارنة', 'warning'); return; }
  api('/admin/rbac/api/permission-matrix', 'POST', {role_ids:[r1,r2]}).then(function(d){
    if(!d.ok) return;
    var r1Name = d.roles.find(function(r){return r.id===r1}).name;
    var r2Name = d.roles.find(function(r){return r.id===r2}).name;
    var html = '<table class="tbl" style="font-size:13px"><thead><tr><th>الصلاحية</th><th>' + esc(r1Name) + '</th><th>' + esc(r2Name) + '</th></tr></thead><tbody>';
    d.matrix.forEach(function(m){
      var c1 = m['role_' + r1] ? '<i class="fas fa-check" style="color:var(--green)"></i>' : '<i class="fas fa-times" style="color:var(--muted)"></i>';
      var c2 = m['role_' + r2] ? '<i class="fas fa-check" style="color:var(--green)"></i>' : '<i class="fas fa-times" style="color:var(--muted)"></i>';
      var diff = m['role_' + r1] !== m['role_' + r2];
      html += '<tr' + (diff ? ' style="background:rgba(245,158,11,0.08)"' : '') + '>'
        + '<td>' + esc(m.permission.name_ar || m.permission.name) + '</td><td>' + c1 + '</td><td>' + c2 + '</td></tr>';
    });
    html += '</tbody></table>';
    html += '<p style="color:var(--muted);font-size:12px;margin-top:8px">الصفوف المظللة = اختلاف في الصلاحية</p>';
    byId('matrixResult').innerHTML = html;
  });
}

function whoHasPermission() {
  var code = byId('whoHasPermSelect').value;
  if(!code) { byId('whoHasResult').innerHTML = ''; return; }
  api('/admin/rbac/api/employees').then(function(d){
    if(!d.ok) return;
    var count = 0;
    var names = [];
    // We need to check each employee against the permission
    // Since we can't batch-check, use the assignment data
    var promises = d.employees.map(function(e){
      return api('/admin/rbac/api/employee-permissions/' + e.id).then(function(rd){
        if(rd.ok && rd.permissions.indexOf(code) !== -1) {
          count++;
          names.push(e.full_name);
        }
      });
    });
    Promise.all(promises).then(function(){
      var html = '<p><strong>الموظفون الذين يملكون صلاحية "' + esc(code) + '":</strong></p>';
      html += '<p>' + count + ' موظف' + (count > 1 ? 'ين' : '') + '</p>';
      if(names.length) html += '<ul style="columns:3;margin-top:8px">' + names.map(function(n){return '<li>' + esc(n) + '</li>'}).join('') + '</ul>';
      byId('whoHasResult').innerHTML = html;
    });
  });
}

function loadRequests() {
  api('/admin/rbac/api/permission-requests').then(function(d){
    if(!d.ok) return;
    var tb = byId('requestsTableBody');
    if(!tb) return;
    tb.innerHTML = '';
    if(!d.requests.length) { tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:30px">لا توجد طلبات</td></tr>'; return; }
    var statusColors = {pending:'badge-warning',approved:'badge-success',rejected:'badge-danger'};
    d.requests.forEach(function(r){
      var sc = statusColors[r.status] || 'badge-muted';
      tb.innerHTML += '<tr><td>' + esc(r.employee_name||'') + '</td>'
        + '<td><code>' + esc(r.requested_perms||'') + '</code></td>'
        + '<td style="color:var(--muted)">' + esc(r.justification||'-') + '</td>'
        + '<td>' + (r.duration_days||'-') + '</td>'
        + '<td><span class="badge ' + sc + '">' + r.status + '</span></td>'
        + '<td style="color:var(--muted)">' + (r.created_at ? new Date(r.created_at).toLocaleDateString('ar-SA') : '-') + '</td>'
        + '<td>' + (r.status === 'pending' ? '<button class="btn btn-ghost btn-xs" onclick="openReviewModal(' + r.id + ')">مراجعة</button>' : '') + '</td></tr>';
    });
  });
}

function loadAuditLogs() {
  api('/admin/rbac/api/audit-logs').then(function(d){
    if(!d.ok) return;
    var tb = byId('auditTableBody');
    if(!tb) return;
    tb.innerHTML = '';
    if(!d.logs.length) { tb.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:30px">لا توجد سجلات</td></tr>'; return; }
    d.logs.forEach(function(l){
      var dt = l.created_at ? new Date(l.created_at).toLocaleString('ar-SA') : '-';
      tb.innerHTML += '<tr><td><span class="badge badge-muted">' + esc(l.action) + '</span></td>'
        + '<td>' + esc(l.entity_type) + '</td>'
        + '<td style="color:var(--muted);font-size:13px">' + esc((l.changes||'').slice(0,80)) + '</td>'
        + '<td>' + esc(l.performer_name||'system') + '</td>'
        + '<td style="color:var(--muted);font-size:12px">' + esc(l.ip_address||'-') + '</td>'
        + '<td style="color:var(--muted)">' + dt + '</td></tr>';
    });
  });
}

function populateEmployeeSelect(id) {
  api('/admin/rbac/api/employees').then(function(d){
    if(!d.ok) return;
    allEmployees = d.employees;
    var sel = byId(id);
    if(!sel) return;
    sel.innerHTML = '<option value="">-- اختر --</option>';
    d.employees.forEach(function(e){
      sel.innerHTML += '<option value="' + e.id + '">' + esc(e.full_name) + ' (' + esc(e.department||'') + ')</option>';
    });
  });
}

function populateRoleSelect(id) {
  var sel = byId(id);
  if(!sel) return;
  sel.innerHTML = '<option value="">-- اختر --</option>';
  allRoles.forEach(function(r){
    sel.innerHTML += '<option value="' + r.id + '">' + esc(r.name) + '</option>';
  });
}

function openRequestModal() {
  var pc = byId('reqPermCheckboxes');
  pc.innerHTML = '';
  allPermissions.forEach(function(p){
    pc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:13px"><input type="checkbox" value="' + p.code + '" class="req-perm-cb"> ' + esc(p.name_ar || p.name) + '</label>';
  });
  byId('reqJustification').value = '';
  byId('reqDuration').value = '30';
  byId('requestModal').classList.add('open');
  byId('requestModal').style.display = 'flex';
}

function submitRequest() {
  var permCbs = document.querySelectorAll('#reqPermCheckboxes input.req-perm-cb:checked');
  var codes = [];
  for(var i = 0; i < permCbs.length; i++) codes.push(permCbs[i].value);
  if(!codes.length) { toast('اختر صلاحية واحدة على الأقل', 'warning'); return; }
  var data = {
    permission_codes: codes,
    justification: byId('reqJustification').value,
    duration_days: parseInt(byId('reqDuration').value) || 30,
  };
  api('/admin/rbac/api/permission-requests', 'POST', data).then(function(d){
    if(d.ok) { toast('تم إرسال الطلب', 'success'); closeModal('requestModal'); loadRequests(); }
    else toast('فشل', 'error');
  });
}

function openReviewModal(id) {
  byId('reviewRequestId').value = id;
  byId('reviewComment').value = '';
  var reqs = document.querySelectorAll('#requestsTableBody tr');
  byId('reviewDetails').textContent = 'مراجعة الطلب #' + id;
  byId('reviewRequestModal').classList.add('open');
  byId('reviewRequestModal').style.display = 'flex';
}

function reviewRequest(status) {
  var id = byId('reviewRequestId').value;
  api('/admin/rbac/api/permission-requests/' + id + '/review', 'POST', {
    status: status,
    review_comment: byId('reviewComment').value,
  }).then(function(d){
    if(d.ok) { toast('تمت المراجعة', 'success'); closeModal('reviewRequestModal'); loadRequests(); }
    else toast('فشل', 'error');
  });
}

function openDelegationModal() {
  api('/admin/rbac/api/employees').then(function(d){
    if(!d.ok) return;
    var sel = byId('dlgDelegate');
    sel.innerHTML = '<option value="">-- اختر --</option>';
    d.employees.forEach(function(e){
      sel.innerHTML += '<option value="' + e.id + '">' + esc(e.full_name) + '</option>';
    });
  });
  var pc = byId('dlgPermCheckboxes');
  pc.innerHTML = '';
  allPermissions.forEach(function(p){
    pc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:13px"><input type="checkbox" value="' + p.id + '" class="dlg-perm-cb"> ' + esc(p.name_ar || p.name) + '</label>';
  });
  byId('dlgEnd').value = '';
  byId('dlgReason').value = '';
  byId('delegationModal').classList.add('open');
  byId('delegationModal').style.display = 'flex';
}

function saveDelegation() {
  var permCbs = document.querySelectorAll('#dlgPermCheckboxes input.dlg-perm-cb:checked');
  var permIds = [];
  for(var i = 0; i < permCbs.length; i++) permIds.push(parseInt(permCbs[i].value));
  var data = {
    delegate_id: parseInt(byId('dlgDelegate').value),
    permission_ids: permIds,
    end_date: byId('dlgEnd').value,
    reason: byId('dlgReason').value,
  };
  if(!data.delegate_id || !permIds.length) { toast('اختر الموظف والصلاحيات', 'warning'); return; }
  api('/admin/rbac/api/delegations', 'POST', data).then(function(d){
    if(d.ok) { toast('تم التفويض', 'success'); closeModal('delegationModal'); }
    else toast('فشل', 'error');
  });
}

document.addEventListener('DOMContentLoaded', function(){
  api('/admin/rbac/api/roles').then(function(d){ allRoles = d.roles || []; });
  api('/admin/rbac/api/permissions').then(function(d){ allPermissions = d.permissions || []; });
  api('/admin/rbac/api/employees').then(function(d){ allEmployees = d.employees || []; });
  api('/admin/rbac/api/departments').then(function(d){ allDepartments = d.departments || []; });
  loadRoles();
  loadPermissions();
  loadAssignments();
  loadAnalytics();
  loadRequests();
  loadAuditLogs();
});
