let allDepts = [];
let editDeptId = null;
let addStep = 1;
let editStep = 1;
let addRecipients = [];

function csrfToken() {
  var m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}
let editRecipients = [];
let annDeptId = null;
const DEPT_ICONS = ['building','flask','droplet','users','wallet','tool','clipboard-list','truck-medical','microscope','box','shield','heart-pulse','hospital','stethoscope','syringe','bandage','file-medical','chart-bar','clock','calendar-check'];

document.addEventListener('DOMContentLoaded', function() {
  loadDepartments();
  loadParents();
  loadManagers();
  loadDevices();
  loadShifts();
  loadIcons();
  document.getElementById('adColor')?.addEventListener('input', function() {
    document.getElementById('adColorPreview').style.background = this.value;
  });
  document.getElementById('trDate').valueAsDate = new Date();
});

function loadDepartments() {
  api('/admin/departments/api/list').then(r => {
    if (r && r.departments) {
      allDepts = r.departments;
      renderDeptGrid();
    }
  });
}

function renderDeptGrid() {
  const grid = document.getElementById('deptGridView');
  if (!grid) return;
  if (!allDepts.length) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--muted)"><i class="ti ti-building" style="font-size:48px;display:block;margin-bottom:12px;opacity:0.3"></i>لا توجد أقسام بعد</div>';
    return;
  }
  let html = '';
  allDepts.forEach(d => {
    const statusClass = d.is_active ? 'badge-present' : 'badge-absent';
    const statusText = d.is_active ? 'نشط' : 'موقوف';
    const pct = d.headcount_percent || 0;
    const barColor = pct > 90 ? 'var(--red)' : pct > 70 ? 'var(--warning)' : 'var(--green)';
    html += `<div class="card dept-card" style="padding:16px 18px;border-right:3px solid ${d.color};cursor:pointer" onclick="openViewModal(${d.id})">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
        <div style="width:40px;height:40px;border-radius:10px;background:${d.color}20;display:flex;align-items:center;justify-content:center">
          <i class="ti ti-${d.icon || 'building'}" style="color:${d.color};font-size:18px"></i>
        </div>
        <div style="flex:1;min-width:0">
          <div style="font-size:14px;font-weight:700">${d.name_ar}</div>
          ${d.name_en ? '<div style="font-size:11px;color:var(--muted)">'+d.name_en+'</div>' : ''}
          ${d.code ? '<div style="font-size:10px;color:var(--muted)">'+d.code+'</div>' : ''}
        </div>
        <span class="badge ${statusClass}" style="font-size:10px">${statusText}</span>
      </div>
      <div style="display:flex;gap:12px;font-size:12px;color:var(--muted);margin-bottom:10px">
        <span><i class="ti ti-users"></i> ${d.employee_count} موظف</span>
        ${d.parent_name ? '<span><i class="ti ti-sitemap"></i> '+d.parent_name+'</span>' : ''}
        ${d.manager_name ? '<span><i class="ti ti-crown"></i> '+d.manager_name+'</span>' : ''}
      </div>
      <div style="margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-bottom:2px">
          <span>السعة: ${d.employee_count} / ${d.max_staff_capacity}</span>
          <span>${pct}%</span>
        </div>
        <div style="height:4px;background:var(--bg);border-radius:4px;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:${barColor};border-radius:4px;transition:width 0.3s"></div>
        </div>
      </div>
      <div style="display:flex;gap:4px;flex-wrap:wrap">
        <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation();openViewModal(${d.id})"><i class="ti ti-eye"></i></button>
        <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation();openEditModal(${d.id})"><i class="ti ti-edit"></i></button>
        <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation();toggleDept(${d.id})"><i class="ti ti-${d.is_active?'pause':'play'}"></i></button>
        ${d.employee_count === 0 ? '<button class="btn btn-ghost btn-xs" style="color:var(--red)" onclick="event.stopPropagation();deleteDept('+d.id+')"><i class="ti ti-trash"></i></button>' : ''}
      </div>
    </div>`;
  });
  grid.innerHTML = html;
}

function loadParents() {
  api('/admin/departments/api/parents').then(r => {
    if (r && r.parents) {
      const sel = document.getElementById('adParentId');
      const sel2 = document.getElementById('edParentId');
      const trDept = document.getElementById('trDepartmentId');
      r.parents.forEach(p => {
        sel.innerHTML += `<option value="${p.id}">${p.hierarchy_path}</option>`;
        sel2.innerHTML += `<option value="${p.id}">${p.hierarchy_path}</option>`;
        trDept.innerHTML += `<option value="${p.id}">${p.name_ar}</option>`;
      });
    }
  });
}

function loadManagers() {
  api('/admin/departments/api/managers').then(r => {
    if (r && r.employees) {
      ['adManagerId','adDeputyId','edManagerId','edDeputyId'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        r.employees.forEach(e => {
          sel.innerHTML += `<option value="${e.id}">${e.full_name} (${e.username})</option>`;
        });
      });
    }
  });
}

function loadDevices() {
  api('/admin/departments/api/devices').then(r => {
    if (r && r.devices) {
      ['adDeviceGrid','edDeviceGrid'].forEach(gridId => {
        const grid = document.getElementById(gridId);
        if (!grid) return;
        grid.innerHTML = '';
        r.devices.forEach(d => {
          grid.innerHTML += `<label style="display:flex;align-items:center;gap:4px;font-size:12px;padding:4px 8px;border-radius:6px;background:var(--bg);cursor:pointer">
            <input type="checkbox" class="device-cb" value="${d.id}"> ${d.name || d.serial_number}
          </label>`;
        });
      });
    }
  });
}

function loadShifts() {
  api('/admin/departments/api/shifts').then(r => {
    if (r && r.shifts) {
      ['adShiftId','edShiftId'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        r.shifts.forEach(s => {
          sel.innerHTML += `<option value="${s.id}">${s.name_ar}</option>`;
        });
      });
    }
  });
}

function loadIcons() {
  ['adIconGrid','edIconGrid'].forEach(gridId => {
    const grid = document.getElementById(gridId);
    if (!grid) return;
    grid.innerHTML = '';
    DEPT_ICONS.forEach(icon => {
      grid.innerHTML += `<span class="icon-option" data-icon="${icon}" onclick="selectIcon(this,'${gridId}')"><i class="ti ti-${icon}"></i></span>`;
    });
  });
}

function selectIcon(el, gridId) {
  const grid = document.getElementById(gridId);
  grid.querySelectorAll('.icon-option').forEach(i => i.classList.remove('selected'));
  el.classList.add('selected');
  const prefix = gridId === 'adIconGrid' ? 'ad' : 'ed';
  document.getElementById(prefix+'IconPreviewIcon').className = 'ti ti-'+el.dataset.icon;
}

function loadIcons() {
  ['adIconGrid','edIconGrid'].forEach(gridId => {
    const grid = document.getElementById(gridId);
    if (!grid) return;
    grid.innerHTML = '';
    DEPT_ICONS.forEach(icon => {
      grid.innerHTML += `<span class="icon-option" data-icon="${icon}" onclick="selectIcon(this,'${gridId}')"><i class="ti ti-${icon}"></i></span>`;
    });
  });
}

function selectPill(el, groupId) {
  const group = document.getElementById(groupId);
  if (!group) return;
  group.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
}

function updateCharCount(el, countId, max) {
  const count = el.value.length;
  document.getElementById(countId).textContent = count+'/'+max;
}

function toggleInactiveReason() {
  document.getElementById('adInactiveReasonGroup').style.display = document.getElementById('adIsActive').checked ? 'none' : 'block';
}

function toggleEditInactiveReason() {
  document.getElementById('edInactiveReasonGroup').style.display = document.getElementById('edIsActive').checked ? 'none' : 'block';
}

function checkDeptCode(code) {
  if (!code || code.length < 3) {
    document.getElementById('adCodeStatus').textContent = '';
    return;
  }
  api('/admin/departments/api/check-code?code='+encodeURIComponent(code)).then(r => {
    const el = document.getElementById('adCodeStatus');
    if (r && r.available) {
      el.innerHTML = '<span style="color:var(--green)">✓ متاح</span>';
    } else {
      el.innerHTML = '<span style="color:var(--red)">✗ '+(r?.message || 'مستخدم')+'</span>';
    }
  });
}

function autoGenerateCode() {
  api('/admin/departments/api/generate-code').then(r => {
    if (r && r.code) {
      document.getElementById('adCode').value = r.code;
      document.getElementById('adCodeStatus').innerHTML = '<span style="color:var(--green)">✓ تم التوليد</span>';
    }
  });
}

function autoGenerateCodeEdit() {
  api('/admin/departments/api/generate-code').then(r => {
    if (r && r.code) {
      document.getElementById('edCode').value = r.code;
    }
  });
}

function updateDeptLevel() {
  const parentId = document.getElementById('adParentId').value;
  const preview = document.getElementById('adHierarchyPreview');
  if (parentId) {
    const opt = document.getElementById('adParentId').selectedOptions[0];
    preview.textContent = opt.text + ' > ' + (document.getElementById('adNameAr').value || 'القسم الجديد');
    document.getElementById('adDeptLevel').value = 'المستوى 2 - قسم';
  } else {
    const name = document.getElementById('adNameAr').value || 'القسم الجديد';
    preview.textContent = name;
    document.getElementById('adDeptLevel').value = 'المستوى 1 - رئيسي';
  }
}

function updateEditDeptLevel() {
  const parentId = document.getElementById('edParentId').value;
  const preview = document.getElementById('edHierarchyPreview');
  if (parentId) {
    const opt = document.getElementById('edParentId').selectedOptions[0];
    preview.textContent = opt.text + ' > ' + (document.getElementById('edNameAr').value || '');
    document.getElementById('edDeptLevel').value = 'المستوى 2 - قسم';
  } else {
    preview.textContent = document.getElementById('edNameAr').value || '';
    document.getElementById('edDeptLevel').value = 'المستوى 1 - رئيسي';
  }
}

function searchManager(q, selectId, previewId) {
  api('/admin/departments/api/managers?q='+encodeURIComponent(q)).then(r => {
    const sel = document.getElementById(selectId);
    const preview = document.getElementById(previewId);
    if (!sel) return;
    sel.innerHTML = '<option value="">غير معين</option>';
    if (r && r.employees) {
      r.employees.forEach(e => {
        sel.innerHTML += `<option value="${e.id}">${e.full_name} (${e.username})</option>`;
      });
    }
    sel.size = Math.min(r?.employees?.length || 1, 6);
  });
}

function searchAlertRecipient(q, prefix) {
  prefix = prefix || 'ad';
  api('/admin/departments/api/employees?q='+encodeURIComponent(q)).then(r => {
    const sel = document.getElementById(prefix+'RecipientSelect');
    if (!sel) return;
    sel.innerHTML = '';
    sel.style.display = 'block';
    if (r && r.employees) {
      r.employees.forEach(e => {
        sel.innerHTML += `<option value="${e.id}">${e.full_name}</option>`;
      });
    }
  });
}

function addAlertRecipient() {
  const sel = document.getElementById('adRecipientSelect');
  const selected = sel.selectedOptions;
  for (let opt of selected) {
    const id = parseInt(opt.value);
    if (id && !addRecipients.find(r => r.id === id)) {
      addRecipients.push({id, name: opt.text});
    }
  }
  renderAddRecipients();
  sel.style.display = 'none';
}

function renderAddRecipients() {
  const container = document.getElementById('adRecipientTags');
  container.innerHTML = '';
  addRecipients.forEach(r => {
    container.innerHTML += `<span class="tag">${r.name} <i class="ti ti-x" onclick="removeAddRecipient(${r.id})" style="cursor:pointer;font-size:14px"></i></span>`;
  });
}

function removeAddRecipient(id) {
  addRecipients = addRecipients.filter(r => r.id !== id);
  renderAddRecipients();
}

function addEditAlertRecipient() {
  const sel = document.getElementById('edRecipientSelect');
  const selected = sel.selectedOptions;
  for (let opt of selected) {
    const id = parseInt(opt.value);
    if (id && !editRecipients.find(r => r.id === id)) {
      editRecipients.push({id, name: opt.text});
    }
  }
  renderEditRecipients();
  sel.style.display = 'none';
}

function renderEditRecipients() {
  const container = document.getElementById('edRecipientTags');
  container.innerHTML = '';
  editRecipients.forEach(r => {
    container.innerHTML += `<span class="tag">${r.name} <i class="ti ti-x" onclick="removeEditRecipient(${r.id})" style="cursor:pointer;font-size:14px"></i></span>`;
  });
}

function removeEditRecipient(id) {
  editRecipients = editRecipients.filter(r => r.id !== id);
  renderEditRecipients();
}

function addCertTag() {
  const input = document.getElementById('adCertInput');
  const val = input.value.trim();
  if (!val) return;
  const container = document.getElementById('adCertTags');
  container.innerHTML += `<span class="tag">${val} <i class="ti ti-x" onclick="this.parentElement.remove()" style="cursor:pointer;font-size:14px"></i></span>`;
  input.value = '';
}

function addEditCertTag() {
  const input = document.getElementById('edCertInput');
  const val = input.value.trim();
  if (!val) return;
  const container = document.getElementById('edCertTags');
  container.innerHTML += `<span class="tag">${val} <i class="ti ti-x" onclick="this.parentElement.remove()" style="cursor:pointer;font-size:14px"></i></span>`;
  input.value = '';
}

function openAddModal() {
  addStep = 1;
  document.querySelectorAll('.dept-step').forEach(el => el.style.display = 'none');
  document.getElementById('addStep1').style.display = 'block';
  updateStepDots('add', 1);
  document.getElementById('addPrevBtn').style.display = 'none';
  document.getElementById('addNextBtn').style.display = 'inline-flex';
  document.getElementById('addSaveBtn').style.display = 'none';
  openModal('addDeptModal');
  autoGenerateCode();
}

function addNextStep() {
  if (addStep < 5) {
    addStep++;
    document.querySelectorAll('#addDeptForm .dept-step').forEach(el => el.style.display = 'none');
    document.getElementById('addStep'+addStep).style.display = 'block';
    updateStepDots('add', addStep);
    document.getElementById('addPrevBtn').style.display = 'inline-flex';
    if (addStep === 5) {
      document.getElementById('addNextBtn').style.display = 'none';
      document.getElementById('addSaveBtn').style.display = 'inline-flex';
    }
  }
}

function addPrevStep() {
  if (addStep > 1) {
    addStep--;
    document.querySelectorAll('#addDeptForm .dept-step').forEach(el => el.style.display = 'none');
    document.getElementById('addStep'+addStep).style.display = 'block';
    updateStepDots('add', addStep);
    document.getElementById('addNextBtn').style.display = 'inline-flex';
    document.getElementById('addSaveBtn').style.display = 'none';
    if (addStep === 1) document.getElementById('addPrevBtn').style.display = 'none';
  }
}

function updateStepDots(prefix, step) {
  const dots = document.getElementById(prefix+'StepDots');
  if (!dots) return;
  dots.querySelectorAll('.step-dot').forEach((d, i) => {
    d.classList.toggle('active', i < step);
  });
  document.getElementById(prefix+'StepIndicator').textContent = 'الخطوة '+step+' من 5';
}

function clearAddForm() {
  ['adCode','adNameAr','adNameEn','adDescAr','adDescEn','adInactiveReason','adCostCenter','adCertInput','adWhatsAppGroup'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  document.getElementById('adColor').value = '#e53935';
  document.getElementById('adColorPreview').style.background = '#e53935';
  document.getElementById('adIsActive').checked = true;
  document.getElementById('adInactiveReasonGroup').style.display = 'none';
  document.getElementById('adMinStaff').value = '2';
  document.getElementById('adMaxStaff').value = '50';
  document.getElementById('adBreakDuration').value = '60';
  document.getElementById('adOvertimeMax').value = '12';
  document.getElementById('adAlertThreshold').value = '15';
  document.getElementById('adCertTags').innerHTML = '';
  document.getElementById('adRecipientTags').innerHTML = '';
  addRecipients = [];
  document.getElementById('adTypeGroup').querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
  document.getElementById('adTypeGroup').querySelector('[data-value="operational"]').classList.add('active');
  document.getElementById('adIconGrid').querySelectorAll('.icon-option').forEach(i => i.classList.remove('selected'));
  document.getElementById('adIconPreviewIcon').className = 'ti ti-building';
  document.querySelectorAll('.emp-type-cb').forEach(cb => cb.checked = cb.value === 'full_time' || cb.value === 'part_time');
  document.getElementById('adShiftId').value = '';
  document.getElementById('adGracePeriod').value = '';
  document.getElementById('adRemoteWork').checked = false;
  document.getElementById('adOvertimeApproval').checked = true;
  document.querySelectorAll('.device-cb').forEach(cb => cb.checked = false);
  document.querySelectorAll('.alert-cb').forEach(cb => cb.checked = ['absent','late','understaffing','document_expiry','shift_change'].includes(cb.value));
  document.getElementById('adParentId').value = '';
  document.getElementById('adHierarchyPreview').textContent = '';
  document.getElementById('adDeptLevel').value = 'المستوى 1 - رئيسي';
  document.getElementById('adManagerId').value = '';
  document.getElementById('adDeputyId').value = '';
  document.getElementById('adManagerPreview').style.display = 'none';
  document.getElementById('adDeputyPreview').style.display = 'none';
  document.getElementById('adCodeStatus').textContent = '';
}

async function doAddDept() {
  const nameAr = document.getElementById('adNameAr').value.trim();
  if (!nameAr) { toast('اسم القسم مطلوب','err'); return; }
  const code = document.getElementById('adCode').value.trim();
  const data = {
    code: code,
    name_ar: nameAr,
    name_en: document.getElementById('adNameEn').value.trim(),
    icon: document.querySelector('#adIconGrid .icon-option.selected')?.dataset?.icon || 'building',
    color: document.getElementById('adColor').value,
    description_ar: document.getElementById('adDescAr').value.trim(),
    description_en: document.getElementById('adDescEn').value.trim(),
    dept_type: document.querySelector('#adTypeGroup .pill.active')?.dataset?.value || 'operational',
    is_active: document.getElementById('adIsActive').checked,
    inactive_reason: document.getElementById('adInactiveReason').value.trim(),
    parent_id: document.getElementById('adParentId').value || null,
    manager_id: document.getElementById('adManagerId').value || null,
    deputy_id: document.getElementById('adDeputyId').value || null,
    cost_center_code: document.getElementById('adCostCenter').value.trim(),
    min_staff_required: parseInt(document.getElementById('adMinStaff').value) || 2,
    max_staff_capacity: parseInt(document.getElementById('adMaxStaff').value) || 50,
    allowed_employment_types: Array.from(document.querySelectorAll('.emp-type-cb:checked')).map(cb => cb.value).join(','),
    certifications: Array.from(document.querySelectorAll('#adCertTags .tag')).map(t => t.childNodes[0].textContent.trim()),
    default_shift_id: document.getElementById('adShiftId').value || null,
    grace_period_override: document.getElementById('adGracePeriod').value || null,
    remote_work_allowed: document.getElementById('adRemoteWork').checked,
    break_duration_policy: parseInt(document.getElementById('adBreakDuration').value) || 60,
    overtime_max_weekly: parseInt(document.getElementById('adOvertimeMax').value) || 12,
    overtime_requires_approval: document.getElementById('adOvertimeApproval').checked,
    overtime_auto_approve_under: 2,
    allowed_device_ids: Array.from(document.querySelectorAll('#adDeviceGrid .device-cb:checked')).map(cb => parseInt(cb.value)),
    alert_recipient_ids: addRecipients.map(r => r.id),
    alert_threshold_minutes: parseInt(document.getElementById('adAlertThreshold').value) || 15,
    alert_settings: Object.fromEntries(Array.from(document.querySelectorAll('.alert-cb:checked')).map(cb => [cb.value, true])),
    whatsapp_group_id: document.getElementById('adWhatsAppGroup').value.trim(),
  };
  if (!data.code) {
    const codeResp = await api('/admin/departments/api/generate-code');
    if (codeResp && codeResp.code) data.code = codeResp.code;
  }
  const r = await api('/admin/departments/api/add', data);
  if (r && r.success) {
    toast('تم إضافة القسم بنجاح','ok');
    closeModal('addDeptModal');
    clearAddForm();
    loadDepartments();
  } else {
    toast(r?.error || 'حدث خطأ','err');
  }
}

function openEditModal(id) {
  editDeptId = id;
  editStep = 1;
  editRecipients = [];
  const d = allDepts.find(x => x.id === id);
  if (!d) return;
  document.getElementById('editDeptName').textContent = d.name_ar;
  document.getElementById('edCode').value = d.code || '';
  document.getElementById('edNameAr').value = d.name_ar;
  document.getElementById('edNameEn').value = d.name_en || '';
  document.getElementById('edDescAr').value = d.description_ar || '';
  document.getElementById('edDescEn').value = d.description_en || '';
  document.getElementById('edColor').value = d.color || '#e53935';
  document.getElementById('edColorPreview').style.background = d.color || '#e53935';
  document.getElementById('edCostCenter').value = d.cost_center_code || '';
  document.getElementById('edMinStaff').value = d.min_staff_required || 2;
  document.getElementById('edMaxStaff').value = d.max_staff_capacity || 50;
  document.getElementById('edGracePeriod').value = d.grace_period_override || '';
  document.getElementById('edBreakDuration').value = d.break_duration_policy || 60;
  document.getElementById('edOvertimeMax').value = d.overtime_max_weekly || 12;
  document.getElementById('edWhatsAppGroup').value = d.whatsapp_group_id || '';
  document.getElementById('edAlertThreshold').value = d.alert_threshold_minutes || 15;
  document.getElementById('edUnderstaffThreshold').value = d.alert_understaffing_threshold || '';
  document.getElementById('edIsActive').checked = d.is_active;
  document.getElementById('edInactiveReason').value = d.inactive_reason || '';
  toggleEditInactiveReason();
  document.getElementById('edRemoteWork').checked = d.remote_work_allowed || false;
  document.getElementById('edOvertimeApproval').checked = d.overtime_requires_approval !== false;
  document.getElementById('edDeptLevel').value = d.dept_level === 1 ? 'المستوى 1 - رئيسي' : 'المستوى 2 - قسم';
  const empTypes = d.allowed_employment_types || [];
  document.querySelectorAll('.edit-emp-type').forEach(cb => cb.checked = empTypes.includes(cb.value));
  document.querySelectorAll('#edTypeGroup .pill').forEach(p => p.classList.remove('active'));
  document.querySelector('#edTypeGroup .pill[data-value="'+(d.dept_type||'operational')+'"]')?.classList.add('active');
  document.querySelectorAll('#edIconGrid .icon-option').forEach(i => i.classList.remove('selected'));
  document.querySelector('#edIconGrid .icon-option[data-icon="'+(d.icon||'building')+'"]')?.classList.add('selected');
  document.getElementById('edIconPreviewIcon').className = 'ti ti-'+ (d.icon||'building');
  document.getElementById('edIconPreviewText').textContent = d.name_ar;
  document.getElementById('edParentId').value = d.parent_id || '';
  updateEditDeptLevel();
  document.getElementById('edManagerId').value = d.manager_id || '';
  document.getElementById('edDeputyId').value = d.deputy_id || '';
  document.getElementById('edCertTags').innerHTML = '';
  (d.certifications || []).forEach(c => {
    document.getElementById('edCertTags').innerHTML += '<span class="tag">'+c+' <i class="ti ti-x" onclick="this.parentElement.remove()" style="cursor:pointer;font-size:14px"></i></span>';
  });
  document.querySelectorAll('.edit-alert-cb').forEach(cb => cb.checked = false);
  const alrt = d.alert_settings || {};
  Object.keys(alrt).forEach(k => {
    const cb = document.querySelector('.edit-alert-cb[value="'+k+'"]');
    if (cb) cb.checked = true;
  });
  document.querySelectorAll('#edDeviceGrid .device-cb').forEach(cb => cb.checked = false);
  (d.allowed_device_ids || []).forEach(did => {
    const cb = document.querySelector('#edDeviceGrid .device-cb[value="'+did+'"]');
    if (cb) cb.checked = true;
  });
  editRecipients = (d.alert_recipient_ids || []).map(id => {
    const emp = d.alert_recipients?.find(r => r.id === id) || {};
    return {id, name: emp.full_name || 'موظف #'+id};
  });
  const empNames = d.alert_recipients?.reduce((acc, r) => { acc[r.id] = r.full_name; return acc; }, {}) || {};
  editRecipients = (d.alert_recipient_ids || []).map(id => ({id, name: empNames[id] || 'موظف #'+id}));
  renderEditRecipients();
  document.querySelectorAll('#editDeptForm .dept-step').forEach(el => el.style.display = 'none');
  document.getElementById('editStep1').style.display = 'block';
  updateStepDots('edit', 1);
  document.getElementById('editPrevBtn').style.display = 'none';
  document.getElementById('editNextBtn').style.display = 'inline-flex';
  document.getElementById('editSaveBtn').style.display = 'none';
  const hc = d.headcount_percent || 0;
  document.getElementById('edHeadcountBar').innerHTML = '<div style="display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-bottom:2px"><span>عدد الموظفين: '+d.employee_count+'</span><span>'+hc+'%</span></div><div style="height:6px;background:var(--bg);border-radius:4px;overflow:hidden"><div style="height:100%;width:'+hc+'%;background:'+(hc>90?'var(--red)':hc>70?'var(--warning)':'var(--green)')+';border-radius:4px"></div></div>';
  openModal('editDeptModal');
}

function editNextStep() {
  if (editStep < 5) {
    editStep++;
    document.querySelectorAll('#editDeptForm .dept-step').forEach(el => el.style.display = 'none');
    document.getElementById('editStep'+editStep).style.display = 'block';
    updateStepDots('edit', editStep);
    document.getElementById('editPrevBtn').style.display = 'inline-flex';
    if (editStep === 5) {
      document.getElementById('editNextBtn').style.display = 'none';
      document.getElementById('editSaveBtn').style.display = 'inline-flex';
    }
  }
}

function editPrevStep() {
  if (editStep > 1) {
    editStep--;
    document.querySelectorAll('#editDeptForm .dept-step').forEach(el => el.style.display = 'none');
    document.getElementById('editStep'+editStep).style.display = 'block';
    updateStepDots('edit', editStep);
    document.getElementById('editNextBtn').style.display = 'inline-flex';
    document.getElementById('editSaveBtn').style.display = 'none';
    if (editStep === 1) document.getElementById('editPrevBtn').style.display = 'none';
  }
}

async function doEditDept() {
  if (!editDeptId) return;
  const nameAr = document.getElementById('edNameAr').value.trim();
  if (!nameAr) { toast('اسم القسم مطلوب','err'); return; }
  const data = {
    code: document.getElementById('edCode').value.trim(),
    name_ar: nameAr,
    name_en: document.getElementById('edNameEn').value.trim(),
    icon: document.querySelector('#edIconGrid .icon-option.selected')?.dataset?.icon || 'building',
    color: document.getElementById('edColor').value,
    description_ar: document.getElementById('edDescAr').value.trim(),
    description_en: document.getElementById('edDescEn').value.trim(),
    dept_type: document.querySelector('#edTypeGroup .pill.active')?.dataset?.value || 'operational',
    is_active: document.getElementById('edIsActive').checked,
    inactive_reason: document.getElementById('edInactiveReason').value.trim(),
    parent_id: document.getElementById('edParentId').value || null,
    manager_id: document.getElementById('edManagerId').value || null,
    deputy_id: document.getElementById('edDeputyId').value || null,
    cost_center_code: document.getElementById('edCostCenter').value.trim(),
    min_staff_required: parseInt(document.getElementById('edMinStaff').value) || 2,
    max_staff_capacity: parseInt(document.getElementById('edMaxStaff').value) || 50,
    allowed_employment_types: Array.from(document.querySelectorAll('.edit-emp-type:checked')).map(cb => cb.value).join(','),
    certifications: Array.from(document.querySelectorAll('#edCertTags .tag')).map(t => t.childNodes[0].textContent.trim()),
    default_shift_id: document.getElementById('edShiftId').value || null,
    grace_period_override: document.getElementById('edGracePeriod').value || null,
    remote_work_allowed: document.getElementById('edRemoteWork').checked,
    break_duration_policy: parseInt(document.getElementById('edBreakDuration').value) || 60,
    overtime_max_weekly: parseInt(document.getElementById('edOvertimeMax').value) || 12,
    overtime_requires_approval: document.getElementById('edOvertimeApproval').checked,
    overtime_auto_approve_under: 2,
    allowed_device_ids: Array.from(document.querySelectorAll('#edDeviceGrid .device-cb:checked')).map(cb => parseInt(cb.value)),
    alert_recipient_ids: editRecipients.map(r => r.id),
    alert_threshold_minutes: parseInt(document.getElementById('edAlertThreshold').value) || 15,
    alert_understaffing_threshold: document.getElementById('edUnderstaffThreshold').value || null,
    alert_settings: Object.fromEntries(Array.from(document.querySelectorAll('.edit-alert-cb:checked')).map(cb => [cb.value, true])),
    whatsapp_group_id: document.getElementById('edWhatsAppGroup').value.trim(),
  };
  const r = await api('/admin/departments/api/'+editDeptId+'/edit', data);
  if (r && r.success) {
    toast('تم تحديث القسم بنجاح','ok');
    closeModal('editDeptModal');
    loadDepartments();
  } else {
    toast(r?.error || 'حدث خطأ','err');
  }
}

async function openViewModal(id) {
  const d = allDepts.find(x => x.id === id);
  if (!d) { toast('قسم غير موجود','err'); return; }
  const statusClass = d.is_active ? 'badge-present' : 'badge-absent';
  const statusText = d.is_active ? 'نشط' : 'موقوف';
  let html = `<div style="display:flex;align-items:center;gap:14px;margin-bottom:16px">
    <div style="width:56px;height:56px;border-radius:14px;background:${d.color}20;display:flex;align-items:center;justify-content:center">
      <i class="ti ti-${d.icon||'building'}" style="color:${d.color};font-size:26px"></i>
    </div>
    <div style="flex:1">
      <div style="font-size:16px;font-weight:700">${d.name_ar}</div>
      ${d.name_en ? '<div style="font-size:12px;color:var(--muted)">'+d.name_en+'</div>' : ''}
      <div style="display:flex;gap:6px;margin-top:4px">
        <span class="badge ${statusClass}" style="font-size:10px">${statusText}</span>
        <span class="badge badge-info" style="font-size:10px">${d.code}</span>
        ${d.dept_type ? '<span class="badge" style="background:'+d.color+'20;color:'+d.color+';font-size:10px">'+
          {operational:'تشغيلي',administrative:'إداري',medical:'طبي',technical:'فني',support:'دعم'}[d.dept_type]||d.dept_type+'</span>' : ''}
      </div>
    </div>
  </div>`;
  html += `<div id="deptDashboard_${d.id}" style="margin-bottom:16px"><div style="text-align:center;color:var(--muted);font-size:12px"><i class="ti ti-refresh animate-spin"></i> جاري تحميل البيانات...</div></div>`;
  html += `<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:13px">
    <div><strong>القسم الأم:</strong> ${d.parent_name || '—'}</div>
    <div><strong>المستوى:</strong> المستوى ${d.dept_level || 1}</div>
    <div><strong>المدير:</strong> ${d.manager_name || 'غير معين'}</div>
    <div><strong>نائب المدير:</strong> ${d.deputy_name || 'غير معين'}</div>
    <div><strong>مركز التكلفة:</strong> ${d.cost_center_code || '—'}</div>
    <div><strong>الوصف:</strong> ${d.description_ar || '—'}</div>
    <div><strong>الحد الأدنى:</strong> ${d.min_staff_required || 2} موظف</div>
    <div><strong>الحد الأقصى:</strong> ${d.max_staff_capacity || 50} موظف</div>
    <div><strong>الوردية:</strong> ${d.default_shift_name || '—'}</div>
    <div><strong>مهلة السماح:</strong> ${d.grace_period_override ? d.grace_period_override+' دقيقة' : '—'}</div>
    <div><strong>دوام عن بعد:</strong> ${d.remote_work_allowed ? '✓ نعم' : '✗ لا'}</div>
    <div><strong>مدة الاستراحة:</strong> ${d.break_duration_policy || 60} دقيقة</div>
  </div>`;
  if (d.certifications && d.certifications.length) {
    html += '<div style="margin-top:12px"><strong>الشهادات المطلوبة:</strong><div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">';
    d.certifications.forEach(c => { html += '<span class="tag">'+c+'</span>'; });
    html += '</div></div>';
  }
  if (d.hierarchy_path) {
    html += '<div style="margin-top:12px;padding:10px 14px;border-radius:8px;background:var(--bg);font-size:12px"><i class="ti ti-sitemap"></i> '+d.hierarchy_path+'</div>';
  }
  document.getElementById('viewDeptContent').innerHTML = html;
  document.getElementById('viewDeptActions').innerHTML = `<button class="btn btn-ghost btn-sm" onclick="closeModal('viewDeptModal');openEditModal(${d.id})"><i class="ti ti-edit"></i> تعديل</button>
    <button class="btn btn-ghost btn-sm" onclick="closeModal('viewDeptModal');openAnnounceModal(${d.id})"><i class="ti ti-bullhorn"></i> إعلان</button>
    <button class="btn btn-ghost btn-sm" onclick="closeModal('viewDeptModal');openTransferModal(${d.id})"><i class="ti ti-exchange"></i> نقل موظف</button>
    <button class="btn btn-ghost btn-sm" onclick="viewDeptEmployees(${d.id})"><i class="ti ti-users"></i> الموظفون</button>
    <button class="btn btn-ghost btn-sm" onclick="closeModal('viewDeptModal')">إغلاق</button>`;
  openModal('viewDeptModal');
  api('/admin/departments/api/'+d.id+'/dashboard').then(r => {
    if (!r) return;
    const rateColor = r.attendance_rate >= 80 ? 'var(--green)' : r.attendance_rate >= 50 ? 'var(--warning)' : 'var(--red)';
    let dashHtml = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">
      <div class="stat-card"><div class="stat-value">${r.total_employees}</div><div class="stat-label">👥 الموظفون</div></div>
      <div class="stat-card"><div class="stat-value" style="color:var(--green)">${r.present}</div><div class="stat-label">✅ الحاضرون</div></div>
      <div class="stat-card"><div class="stat-value" style="color:var(--warning)">${r.late}</div><div class="stat-label">⏰ المتأخرون</div></div>
      <div class="stat-card"><div class="stat-value" style="color:var(--red)">${r.absent}</div><div class="stat-label">❌ الغائبون</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px">
      <div class="stat-card" style="text-align:center"><div style="position:relative;width:60px;height:60px;margin:0 auto 6px">
        <svg width="60" height="60" style="transform:rotate(-90deg)"><circle cx="30" cy="30" r="26" fill="none" stroke="var(--bg)" stroke-width="4"/>
          <circle cx="30" cy="30" r="26" fill="none" stroke="${rateColor}" stroke-width="4" stroke-dasharray="${2*Math.PI*26}" stroke-dashoffset="${2*Math.PI*26*(1-r.attendance_rate/100)}" stroke-linecap="round"/>
        </svg>
        <span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:14px;font-weight:700">${r.attendance_rate}%</span>
      </div><div class="stat-label">نسبة الحضور اليوم</div></div>
      <div class="stat-card"><div class="stat-value">${r.month_attendance_pct}%</div><div class="stat-label">نسبة الحضور الشهري</div></div>
    </div>`;
    if (r.top_punctual && r.top_punctual.length) {
      dashHtml += '<div style="margin-top:10px"><strong style="font-size:12px">🏆 الأكثر التزاماً:</strong><div style="display:flex;gap:8px;margin-top:6px">';
      r.top_punctual.forEach(e => {
        dashHtml += '<div style="display:flex;align-items:center;gap:6px;padding:6px 10px;border-radius:8px;background:var(--bg);font-size:12px">'+
          (e.profile_photo ? '<img src="'+e.profile_photo+'" style="width:28px;height:28px;border-radius:50%;object-fit:cover">' : '<div style="width:28px;height:28px;border-radius:50%;background:var(--accent)20;display:flex;align-items:center;justify-content:center"><i class="ti ti-user" style="font-size:14px"></i></div>')+
          '<span>'+e.full_name+'</span></div>';
      });
      dashHtml += '</div></div>';
    }
    dashHtml += '<div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap">';
    if (r.pending_leaves > 0) dashHtml += '<span class="clickable-stat" onclick="showLeaves('+d.id+')">📋 إجازات معلقة: '+r.pending_leaves+'</span>';
    if (r.expiring_documents > 0) dashHtml += '<span class="clickable-stat" onclick="showExpiringDocs('+d.id+')">📄 مستندات منتهية: '+r.expiring_documents+'</span>';
    if (r.active_anomalies > 0) dashHtml += '<span class="clickable-stat" onclick="showAnomalies('+d.id+')">⚠️ أنشطة مشبوهة: '+r.active_anomalies+'</span>';
    dashHtml += '</div>';
    document.getElementById('deptDashboard_'+d.id).innerHTML = dashHtml;
  }).catch(() => {
    document.getElementById('deptDashboard_'+d.id).innerHTML = '<div style="text-align:center;color:var(--muted);font-size:12px">تعذر تحميل البيانات</div>';
  });
}

function viewDeptEmployees(id) {
  closeModal('viewDeptModal');
  api('/admin/departments/api/'+id+'/employees').then(r => {
    if (!r || !r.employees) return;
    const d = allDepts.find(x => x.id === id);
    let html = '<div style="padding:20px;max-height:80vh;overflow-y:auto"><h3 style="font-size:15px;font-weight:700;margin-bottom:16px">👥 موظفو '+d?.name_ar+'</h3>';
    if (!r.employees.length) {
      html += '<div style="text-align:center;color:var(--muted);padding:20px">لا يوجد موظفون</div>';
    } else {
      r.employees.forEach(e => {
        html += '<div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:10px;background:var(--bg);margin-bottom:6px">'+
          (e.profile_photo ? '<img src="'+e.profile_photo+'" style="width:36px;height:36px;border-radius:50%;object-fit:cover">' : '<div style="width:36px;height:36px;border-radius:50%;background:var(--accent)20;display:flex;align-items:center;justify-content:center"><i class="ti ti-user" style="font-size:16px"></i></div>')+
          '<div style="flex:1"><div style="font-size:13px;font-weight:600">'+e.full_name+'</div><div style="font-size:11px;color:var(--muted)">'+e.job_title+' • '+e.phone+'</div></div></div>';
      });
    }
    html += '<button class="btn btn-outline" onclick="this.closest(\'#empListModal\')?.remove();openViewModal('+id+')" style="margin-top:12px">رجوع</button></div>';
    const wrapper = document.createElement('div');
    wrapper.id = 'empListModal';
    wrapper.className = 'modal-overlay active';
    wrapper.innerHTML = '<div class="modal-sheet modal-lg">'+html+'</div>';
    document.body.appendChild(wrapper);
    wrapper.addEventListener('click', e => { if (e.target === wrapper) wrapper.remove(); });
  });
}

function openAnnounceModal(deptId) {
  annDeptId = deptId;
  document.getElementById('annMessage').value = '';
  document.getElementById('annPriorityGroup').querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
  document.getElementById('annPriorityGroup').querySelector('[data-value="normal"]').classList.add('active');
  document.querySelectorAll('.ann-delivery').forEach(cb => cb.checked = cb.value === 'in_app');
  document.getElementById('annScheduleLater').checked = false;
  document.getElementById('annScheduledAt').style.display = 'none';
  document.getElementById('annEmployeeSelect').innerHTML = '';
  document.getElementById('annTargetSelect').style.display = 'none';
  api('/admin/departments/api/'+deptId+'/employees').then(r => {
    if (r && r.employees) {
      const sel = document.getElementById('annEmployeeSelect');
      sel.innerHTML = '';
      r.employees.forEach(e => {
        sel.innerHTML += '<option value="'+e.id+'">'+e.full_name+'</option>';
      });
    }
  });
  openModal('announceModal');
}

document.getElementById('annScheduleLater')?.addEventListener('change', function() {
  document.getElementById('annScheduledAt').style.display = this.checked ? 'block' : 'none';
});

function selectPill(el, groupId) {
  const group = document.getElementById(groupId);
  if (!group) return;
  group.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  if (groupId === 'annTargetGroup') {
    document.getElementById('annTargetSelect').style.display = el.dataset.value === 'specific' ? 'block' : 'none';
  }
}

async function doSendAnnouncement() {
  const message = document.getElementById('annMessage').value.trim();
  if (!message) { toast('الرسالة مطلوبة','err'); return; }
  const data = {
    message: message,
    priority: document.querySelector('#annPriorityGroup .pill.active')?.dataset?.value || 'normal',
    delivery_method: Array.from(document.querySelectorAll('.ann-delivery:checked')).map(cb => cb.value),
    target_type: document.querySelector('#annTargetGroup .pill.active')?.dataset?.value || 'all',
    schedule_later: document.getElementById('annScheduleLater').checked,
    scheduled_at: document.getElementById('annScheduledAt').value || null,
  };
  if (data.target_type === 'specific') {
    const sel = document.getElementById('annEmployeeSelect');
    data.target_employee_ids = Array.from(sel.selectedOptions).map(o => parseInt(o.value));
  }
  const r = await api('/admin/departments/api/'+annDeptId+'/announcements/send', data);
  if (r && r.success) {
    toast(r.message || 'تم إرسال الإعلان','ok');
    closeModal('announceModal');
  } else {
    toast(r?.error || 'حدث خطأ','err');
  }
}

function openTransferModal(deptId) {
  loadParents();
  document.getElementById('trDate').valueAsDate = new Date();
  document.getElementById('trEmployeeSearch').value = '';
  document.getElementById('trEmployeeId').style.display = 'none';
  document.getElementById('trNotes').value = '';
  document.getElementById('trReason').value = '';
  const deptSelect = document.getElementById('trDepartmentId');
  if (deptSelect) {
    deptSelect.value = '';
    const opt = deptSelect.querySelector('option[value="'+deptId+'"]');
    if (opt) opt.disabled = true;
  }
  openModal('transferModal');
}

function searchTransferEmployee(q) {
  api('/admin/departments/api/employees?q='+encodeURIComponent(q)).then(r => {
    const sel = document.getElementById('trEmployeeId');
    sel.innerHTML = '';
    sel.style.display = 'block';
    if (r && r.employees) {
      r.employees.forEach(e => {
        sel.innerHTML += '<option value="'+e.id+'">'+e.full_name+' ('+e.username+')</option>';
      });
    }
  });
}

async function doCreateTransfer() {
  const employeeId = document.getElementById('trEmployeeId').value;
  const deptId = document.getElementById('trDepartmentId').value;
  if (!employeeId || !deptId) { toast('الموظف والقسم الجديد مطلوبان','err'); return; }
  const data = {
    employee_id: parseInt(employeeId),
    to_department_id: parseInt(deptId),
    transfer_date: document.getElementById('trDate').value,
    reason_type: document.getElementById('trReason').value,
    reason_notes: document.getElementById('trNotes').value.trim(),
  };
  const r = await api('/admin/departments/api/transfers/create', data);
  if (r && r.success) {
    toast('تم بدء عملية النقل','ok');
    closeModal('transferModal');
  } else {
    toast(r?.error || 'حدث خطأ','err');
  }
}

async function toggleDept(id) {
  const d = allDepts.find(x => x.id === id);
  if (!d) return;
  const r = await api('/admin/departments/api/'+id+'/toggle');
  if (r && r.success) {
    toast(d.is_active ? 'تم تعطيل القسم' : 'تم تفعيل القسم','ok');
    loadDepartments();
  } else {
    toast(r?.error || 'حدث خطأ','err');
  }
}

async function deleteDept(id) {
  const d = allDepts.find(x => x.id === id);
  if (!d) return;
  if (!confirm('هل أنت متأكد من حذف القسم "'+d.name_ar+'"؟')) return;
  const r = await api('/admin/departments/api/'+id+'/delete', {});
  if (r && r.success) {
    toast('تم حذف القسم','ok');
    loadDepartments();
  } else {
    toast(r?.error || 'لا يمكن حذف القسم','err');
  }
}

function switchView(view) {
  document.getElementById('deptGridView').style.display = view === 'grid' ? 'grid' : 'none';
  document.getElementById('deptListView').style.display = view === 'list' ? 'block' : 'none';
  document.getElementById('orgChartView').style.display = view === 'org' ? 'block' : 'none';
  document.querySelectorAll('[id^=view]').forEach(b => b.classList.remove('btn-red'));
  document.getElementById('view'+view.charAt(0).toUpperCase()+view.slice(1)).classList.add('btn-red');
  if (view === 'org') showOrgChart();
  if (view === 'list') renderDeptList();
}

function renderDeptList() {
  const container = document.getElementById('deptListView');
  if (!container) return;
  let html = '<table class="data-table"><thead><tr><th>الكود</th><th>الاسم</th><th>النوع</th><th>الموظفون</th><th>المدير</th><th>الحالة</th><th></th></tr></thead><tbody>';
  allDepts.forEach(d => {
    const statusClass = d.is_active ? 'badge-present' : 'badge-absent';
    html += '<tr><td><span class="badge badge-info">'+d.code+'</span></td><td><span style="display:flex;align-items:center;gap:6px"><i class="ti ti-'+d.icon+'" style="color:'+d.color+'"></i>'+d.name_ar+'</span></td>'+
      '<td>'+d.dept_type+'</td><td>'+d.employee_count+'/'+d.max_staff_capacity+'</td><td>'+(d.manager_name||'—')+'</td>'+
      '<td><span class="badge '+statusClass+'">'+(d.is_active?'نشط':'موقوف')+'</span></td>'+
      '<td style="display:flex;gap:4px"><button class="btn btn-ghost btn-xs" onclick="openViewModal('+d.id+')"><i class="ti ti-eye"></i></button></td></tr>';
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

function showOrgChart() {
  const container = document.getElementById('orgChartView');
  container.style.display = 'block';
  container.innerHTML = '<div style="text-align:center;color:var(--muted);padding:20px"><i class="ti ti-refresh animate-spin"></i> جاري تحميل الهيكل التنظيمي...</div>';
  api('/admin/departments/api/tree').then(r => {
    if (!r || !r.tree) return;
    container.innerHTML = '<div style="overflow-x:auto;padding:20px 0"><div class="org-tree">'+renderOrgNode(r.tree[0])+'</div></div>';
  });
}

function renderOrgNode(node) {
  if (!node) return '';
  let html = '<div class="org-node">';
  html += '<div class="org-card" style="border-color:'+(node.color||'var(--accent)')+'" onclick="openViewModal('+node.id+')">';
  html += '<div class="org-icon" style="background:'+(node.color||'var(--accent)')+'20"><i class="ti ti-'+node.icon+'" style="color:'+(node.color||'var(--accent)')+'"></i></div>';
  html += '<div class="org-name">'+node.name_ar+'</div>';
  if (node.name_en) html += '<div class="org-name-en">'+node.name_en+'</div>';
  html += '<div class="org-meta">'+(node.manager_name ? '<i class="ti ti-crown"></i> '+node.manager_name : '')+'</div>';
  html += '<div class="org-count"><i class="ti ti-users"></i> '+node.employee_count+' موظف</div>';
  html += '</div>';
  if (node.children && node.children.length) {
    html += '<div class="org-children">';
    node.children.forEach(child => {
      html += renderOrgNode(child);
    });
    html += '</div>';
  }
  html += '</div>';
  return html;
}

function importModal() {
  openModal('importModal');
}

async function doImport() {
  const fileInput = document.getElementById('importFile');
  if (!fileInput.files.length) { toast('الرجاء اختيار ملف CSV','err'); return; }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  try {
    const resp = await fetch('/admin/departments/api/import', {method:'POST', headers:{'X-CSRFToken': csrfToken()}, body:formData});
    const r = await resp.json();
    if (r.success) {
      toast('تم استيراد '+r.imported+' قسم','ok');
      if (r.errors && r.errors.length) console.warn('Import errors:', r.errors);
      closeModal('importModal');
      loadDepartments();
    } else {
      toast(r.error || 'فشل الاستيراد','err');
    }
  } catch(e) {
    toast('خطأ في الرفع','err');
  }
}
