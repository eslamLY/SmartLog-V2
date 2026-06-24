/* ===== Employee Management ===== */
var editingEmpId = null;

function csrfToken() {
  var m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}

/* ── Tab Switching ── */
function switchTab(ctx, tab){
  var tabs = document.querySelectorAll('#'+ctx+'EmpModal .emp-tab');
  var panels = document.querySelectorAll('#'+ctx+'EmpModal .tab-panel');
  tabs.forEach(function(t){
    t.classList.toggle('active', t.dataset.tab === tab);
  });
  panels.forEach(function(p){
    p.style.display = p.id === 'tab_'+ctx+'_'+tab ? 'block' : 'none';
  });
  updateTabProgress(ctx);
}

function updateTabProgress(ctx){
  var prefix = ctx === 'add' ? 'ae' : 'ee';
  var tabs = ['basic','personal','employment','biometric','financial','access'];
  var filled = 0;
  tabs.forEach(function(tab){
    var panel = document.getElementById('tab_'+ctx+'_'+tab);
    if(!panel) return;
    var ind = document.getElementById('tab_'+ctx+'_'+tab+'_ind');
    var reqs = panel.querySelectorAll('[required]');
    var ok = true;
    reqs.forEach(function(r){ if(!r.value.trim()) ok = false; });
    if(ind) ind.textContent = ok ? '✓' : '';
  });
}

/* ── Add Modal ── */
function openAddModal(){
  autoGenerateId();
  document.getElementById('aeHireDate').value = new Date().toISOString().split('T')[0];
  document.getElementById('addEmpModal').classList.add('open');
  switchTab('add','basic');
}

function clearAddForm(){
  document.getElementById('addEmpForm').reset();
  document.getElementById('aePhotoPreview').innerHTML = '<i class="ti ti-user" style="font-size:32px;color:var(--muted2)"></i>';
  ['err_aeUsername','err_aeName','err_aeNationalId'].forEach(function(id){
    var el = document.getElementById(id); if(el) el.textContent = '';
  });
}

/* ── Auto Generate ID ── */
async function autoGenerateId(){
  try {
    var r = await fetch('/admin/employees/next-id');
    var data = await r.json();
    if(data.ok) document.getElementById('aeUsername').value = data.id;
  } catch(e){}
}

/* ── Generate Random Password ── */
function generatePass(ctx){
  var prefix = ctx === 'add' ? 'ae' : ctx === 'edit' ? 'ee' : 'rp';
  var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%&*';
  var pass = '';
  for(var i=0;i<12;i++) pass += chars.charAt(Math.floor(Math.random()*chars.length));
  document.getElementById(prefix+'Pass').value = pass;
  document.getElementById(prefix+'PassConfirm').value = pass;
  if(ctx === 'add' || ctx === 'edit'){ checkPassStrength(ctx); checkPassMatch(ctx); }
}

/* ── Password Strength ── */
function checkPassStrength(ctx){
  var prefix = ctx === 'add' ? 'ae' : ctx === 'edit' ? 'ee' : 'rp';
  var pass = document.getElementById(prefix+'Pass').value;
  var el = document.getElementById(prefix+'PassStrength');
  if(!el) return;
  if(!pass){ el.innerHTML = ''; return; }
  var score = 0;
  if(pass.length >= 8) score++;
  if(pass.length >= 12) score++;
  if(/[a-z]/.test(pass) && /[A-Z]/.test(pass)) score++;
  if(/\d/.test(pass)) score++;
  if(/[^a-zA-Z0-9]/.test(pass)) score++;
  var labels = ['ضعيفة','متوسطة','قوية','قوية جداً'];
  var colors = ['#ef4444','#f59e0b','#22c55e','#22c55e'];
  var idx = Math.min(score, 3);
  el.innerHTML = '<span style="color:'+colors[idx]+';font-weight:600">'+
    labels[idx]+'</span> <span style="color:var(--muted2)">('+score+'/5)</span>';
}

function checkPassMatch(ctx){
  var prefix = ctx === 'add' ? 'ae' : ctx === 'edit' ? 'ee' : 'rp';
  var p1 = document.getElementById(prefix+'Pass').value;
  var p2 = document.getElementById(prefix+'PassConfirm').value;
  var el = document.getElementById(prefix+'PassMatch');
  if(!el) return;
  if(!p1 && !p2){ el.textContent = ''; return; }
  el.textContent = p1 === p2 ? '' : 'كلمة المرور غير متطابقة';
}

/* ── Toggle Password Visibility ── */
function togglePass(inputId, btn){
  var inp = document.getElementById(inputId);
  if(!inp) return;
  if(inp.type === 'password'){ inp.type = 'text'; btn.innerHTML = '<i class="ti ti-eye-off"></i>'; }
  else { inp.type = 'password'; btn.innerHTML = '<i class="ti ti-eye"></i>'; }
}

/* ── Pill Selector ── */
function selectPill(btn, hiddenId){
  var parent = btn.parentElement;
  parent.querySelectorAll('.pill-btn').forEach(function(b){ b.classList.remove('active'); });
  btn.classList.add('active');
  document.getElementById(hiddenId).value = btn.dataset.value;
}

function selectToggle(btn, hiddenId){
  var parent = btn.parentElement;
  parent.querySelectorAll('.toggle-btn').forEach(function(b){ b.classList.remove('active'); });
  btn.classList.add('active');
  document.getElementById(hiddenId).value = btn.dataset.value;
}

/* ── Photo Preview ── */
function previewPhoto(input, previewId, hiddenId){
  var preview = document.getElementById(previewId);
  var file = input.files[0];
  if(!file){ preview.innerHTML = '<i class="ti ti-user" style="font-size:32px;color:var(--muted2)"></i>'; return; }
  if(file.size > 2*1024*1024){ toast('حجم الصورة يتجاوز 2MB','err'); input.value=''; return; }
  if(!['image/jpeg','image/png'].includes(file.type)){ toast('يُسمح فقط بـ JPG/PNG','err'); input.value=''; return; }
  var reader = new FileReader();
  reader.onload = function(e){
    preview.innerHTML = '<img src="'+e.target.result+'" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid var(--accent)">';
  };
  reader.readAsDataURL(file);
}

/* ── Toggle No End Date ── */
function toggleNoEndDate(ctx){
  var prefix = ctx === 'add' ? 'ae' : 'ee';
  var cb = document.getElementById(prefix+'NoEndDate');
  var inp = document.getElementById(prefix+'ContractEnd');
  if(cb.checked){ inp.disabled = true; inp.value = ''; }
  else inp.disabled = false;
}

/* ── Bank Fields Toggle ── */
function toggleBankFields(ctx){
  var prefix = ctx === 'add' ? 'ae' : 'ee';
  var method = document.getElementById(prefix+'PaymentMethod').value;
  var show = method === 'bank_transfer';
  document.getElementById(prefix+'BankNameGroup').style.display = show ? '' : 'none';
  document.getElementById(prefix+'BankAccountGroup').style.display = show ? '' : 'none';
}

/* ── Allowance Row ── */
function addAllowanceRow(containerId){
  var c = document.getElementById(containerId);
  var row = document.createElement('div');
  row.className = 'allowance-row';
  row.innerHTML = '<input placeholder="المسمى" style="flex:1;font-size:12px">' +
    '<input type="number" placeholder="المبلغ" style="width:100px;font-size:12px" oninput="calcTotal(\''+containerId.replace('ae','add').replace('ee','edit')+'\')">' +
    '<button type="button" class="btn btn-ghost btn-xs" onclick="this.parentElement.remove();calcTotal(\''+containerId.replace('ae','add').replace('ee','edit')+'\')"><i class="ti ti-x" style="color:#ef4444"></i></button>';
  c.appendChild(row);
}

/* ── Calculate Total Salary ── */
function calcTotal(ctx){
  var prefix = ctx === 'add' ? 'ae' : 'ee';
  var base = parseFloat(document.getElementById(prefix+'Salary').value) || 0;
  var housing = parseFloat(document.getElementById(prefix+'Housing').value) || 0;
  var transport = parseFloat(document.getElementById(prefix+'Transport').value) || 0;
  var otherEls = document.getElementById(prefix+'OtherAllowances').querySelectorAll('input[type="number"]');
  var other = 0;
  otherEls.forEach(function(el){ other += parseFloat(el.value) || 0; });
  var total = base + housing + transport + other;
  document.getElementById(prefix+'TotalSalary').textContent = total.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/* ── Age Calculator ── */
function calcAge(ctx){
  var prefix = ctx === 'add' ? 'ae' : 'ee';
  var dob = document.getElementById(prefix+'Dob').value;
  var display = document.getElementById(prefix+'AgeDisplay');
  if(!dob){ display.textContent = ''; return; }
  var bd = new Date(dob);
  var today = new Date();
  var age = today.getFullYear() - bd.getFullYear();
  var m = today.getMonth() - bd.getMonth();
  if(m < 0 || (m === 0 && today.getDate() < bd.getDate())) age--;
  display.textContent = 'العمر: '+age+' سنة';
}

/* ── Check Duplicate ── */
async function checkDuplicate(ctx){
  var prefix = ctx === 'add' ? 'ae' : 'ee';
  var name = document.getElementById(prefix+'Name').value.trim();
  var nid = document.getElementById(prefix+'NationalId').value.trim();
  if(!name && !nid) return;
  try {
    var r = await fetch('/admin/employees/check-duplicate', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify({full_name: name, national_id: nid})
    });
    var data = await r.json();
    if(data.warnings && data.warnings.length){
      toast(data.warnings[0], 'err');
    }
  } catch(e){}
}

/* ── ADD EMPLOYEE ── */
async function doAddEmp(){
  var username = document.getElementById('aeUsername').value.trim();
  var name = document.getElementById('aeName').value.trim();
  var deptId = document.getElementById('aeDept').value;
  var pass = document.getElementById('aePass').value;
  var pass2 = document.getElementById('aePassConfirm').value;
  if(!username || !name || !deptId || !pass){ toast('الحقول المطلوبة (*) يجب ملؤها.','err'); return; }
  if(pass !== pass2){ toast('كلمة المرور غير متطابقة.','err'); return; }

  var otherRows = document.getElementById('aeOtherAllowances').querySelectorAll('.allowance-row');
  var allowances = [];
  otherRows.forEach(function(row){
    var inputs = row.querySelectorAll('input');
    if(inputs[0] && inputs[1] && inputs[0].value.trim()){
      allowances.push({label: inputs[0].value.trim(), amount: parseFloat(inputs[1].value) || 0});
    }
  });

  var deviceCbs = document.querySelectorAll('.aeDeviceCb:checked');
  var devices = Array.from(deviceCbs).map(function(cb){ return parseInt(cb.value); });

  var data = {
    username: username,
    full_name: name,
    department_id: parseInt(deptId),
    role: document.getElementById('aeRole').value,
    password: pass,
    phone_country_code: document.getElementById('aePhoneCode').value,
    phone: document.getElementById('aePhone').value.trim(),
    national_id: document.getElementById('aeNationalId').value.trim(),
    date_of_birth: document.getElementById('aeDob').value,
    gender: document.getElementById('aeGenderHidden').value,
    marital_status: document.getElementById('aeMaritalStatus').value,
    address: document.getElementById('aeAddress').value.trim(),
    job_title: document.getElementById('aeJobTitle').value.trim(),
    employment_type: document.getElementById('aeEmpTypeHidden').value,
    hire_date: document.getElementById('aeHireDate').value,
    contract_end_date: document.getElementById('aeContractEnd').value,
    no_end_date: document.getElementById('aeNoEndDate').checked,
    manager_id: parseInt(document.getElementById('aeManager').value) || null,
    shift_type_id: parseInt(document.getElementById('aeShift').value) || null,
    branch_id: parseInt(document.getElementById('aeBranch').value) || null,
    biotime_emp_id: parseInt(document.getElementById('aeBioEmpId').value) || null,
    assigned_devices: devices,
    salary: parseFloat(document.getElementById('aeSalary').value) || 0,
    housing_allowance: parseFloat(document.getElementById('aeHousing').value) || 0,
    transport_allowance: parseFloat(document.getElementById('aeTransport').value) || 0,
    other_allowances: allowances,
    payment_method: document.getElementById('aePaymentMethod').value,
    bank_account_number: document.getElementById('aeBankAccount').value.trim(),
    bank_name: document.getElementById('aeBankName').value,
    permission_level: document.getElementById('aePermissionLevel').value,
    force_password_change: document.getElementById('aeForcePassChange').checked,
    two_factor_enabled: document.getElementById('ae2FA').checked,
    emergency_contact_name: document.getElementById('aeEmergName').value.trim(),
    emergency_relationship: document.getElementById('aeEmergRelation').value,
    emergency_phone: document.getElementById('aeEmergPhone').value.trim(),
    emergency_phone2: document.getElementById('aeEmergPhone2').value.trim(),
  };

  var btn = document.getElementById('aeSubmitBtn');
  btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader"></i>';
  try {
    var r = await fetch('/admin/employees/add', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify(data)
    });
    var res = await r.json();
    toast(res.msg, res.ok ? 'ok' : 'err');
    if(res.ok){
      // Upload photo if selected
      var photoInput = document.getElementById('aePhotoInput');
      if(photoInput.files[0]){
        var fd = new FormData();
        fd.append('photo', photoInput.files[0]);
        await fetch('/admin/employees/'+res.id+'/photo', {method:'POST', body: fd});
      }
      closeModal('addEmpModal');
      setTimeout(function(){ location.reload(); }, 1000);
    }
  } catch(e){ toast(e.message,'err'); }
  btn.disabled = false; btn.innerHTML = '<i class="ti ti-device-floppy"></i> حفظ';
}

/* ── VIEW EMPLOYEE ── */
async function openViewModal(id){
  document.getElementById('viewEmpModal').classList.add('open');
  document.getElementById('veContent').innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted)"><i class="ti ti-loader" style="font-size:28px;display:block;margin-bottom:8px"></i>جاري التحميل...</div>';
  try {
    var r = await fetch('/admin/employees/'+id);
    var data = await r.json();
    if(!data.ok){ document.getElementById('veContent').innerHTML = '<div style="text-align:center;padding:32px;color:#ef4444">خطأ</div>'; return; }
    var e = data.employee;
    document.getElementById('veTitle').textContent = e.full_name;
    document.getElementById('veContent').innerHTML = renderEmployeeDetail(e);
  } catch(e){ document.getElementById('veContent').innerHTML = '<div style="text-align:center;padding:32px;color:#ef4444">'+e.message+'</div>'; }
}

function renderEmployeeDetail(e){
  var html = '<div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid var(--border)">';
  if(e.profile_photo) html += '<img src="/uploads/'+e.profile_photo+'" style="width:64px;height:64px;border-radius:50%;object-fit:cover;border:2px solid var(--accent)">';
  else html += '<div style="width:64px;height:64px;border-radius:50%;background:var(--accent)15;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:700;color:var(--accent)">'+(e.full_name?e.full_name[0]:'?')+'</div>';
  html += '<div><div style="font-size:16px;font-weight:700">'+esc(e.full_name)+'</div><div style="font-size:12px;color:var(--muted)">'+esc(e.username)+' · '+esc(e.department)+' · '+esc(e.job_title||'')+'</div></div></div>';

  html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px">';
  var fields = [
    ['📞 الهاتف', e.phone_country_code+(e.phone||'')],
    ['🆔 الرقم الوطني', e.national_id||'—'],
    ['🎂 تاريخ الميلاد', e.date_of_birth||'—', e.age ? '('+e.age+' سنة)' : ''],
    ['⚧ الجنس', e.gender==='male'?'ذكر':e.gender==='female'?'أنثى':'—'],
    ['💍 الحالة الاجتماعية', e.marital_status||'—'],
    ['🏢 المسمى الوظيفي', e.job_title||'—'],
    ['📅 نوع العمل', e.employment_type||'—'],
    ['📆 تاريخ التعيين', e.hire_date||'—'],
    ['💰 الراتب الأساسي', e.base_salary+' د.ل'],
    ['🏠 بدل سكن', (e.housing_allowance||0)+' د.ل'],
    ['🚗 بدل مواصلات', (e.transport_allowance||0)+' د.ل'],
    ['💵 الراتب الإجمالي', '<strong style="color:var(--accent)">'+(e.total_salary||0)+' د.ل</strong>'],
    ['💳 طريقة الدفع', e.payment_method==='bank_transfer'?'تحويل بنكي':'نقدي'],
    ['🏦 المصرف', e.bank_name||'—'],
    ['🔐 مستوى الصلاحية', e.permission_level||'—'],
    ['📱 البصمة', e.sync_status==='synced'?'✅ متزامن':'⚠️ غير متزامن'],
    ['📞 جهة اتصال', e.emergency_contact_name||'—'],
    ['📞 هاتف طارئ', e.emergency_phone||'—'],
  ];
  fields.forEach(function(f){
    html += '<div><span style="color:var(--muted2)">'+f[0]+':</span> '+f[1]+(f[2]||'')+'</div>';
  });
  html += '</div>';
  return html;
}

/* ── EDIT EMPLOYEE ── */
async function openEditModal(id){
  editingEmpId = id;
  document.getElementById('eeId').value = id;
  try {
    var r = await fetch('/admin/employees/'+id);
    var data = await r.json();
    if(!data.ok){ toast(data.msg,'err'); return; }
    var e = data.employee;
    document.getElementById('eeUsername').value = e.username;
    document.getElementById('eeName').value = e.full_name;
    document.getElementById('eeDept').value = e.department_id || '';
    document.getElementById('eeRole').value = e.role;
    document.getElementById('eePhoneCode').value = e.phone_country_code || '+218';
    document.getElementById('eePhone').value = e.phone||'';
    document.getElementById('eeNationalId').value = e.national_id||'';
    document.getElementById('eeDob').value = e.date_of_birth||'';
    document.getElementById('eeAgeDisplay').textContent = e.age ? 'العمر: '+e.age+' سنة' : '';
    var genderBtns = document.querySelectorAll('#eeGender .toggle-btn');
    genderBtns.forEach(function(b){ b.classList.toggle('active', b.dataset.value === e.gender); });
    document.getElementById('eeGenderHidden').value = e.gender||'';
    document.getElementById('eeMaritalStatus').value = e.marital_status||'';
    document.getElementById('eeAddress').value = e.address||'';
    if(e.profile_photo) document.getElementById('eePhotoPreview').innerHTML = '<img src="/uploads/'+e.profile_photo+'" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid var(--accent)">';
    document.getElementById('eeJobTitle').value = e.job_title||'';
    var empTypeBtns = document.querySelectorAll('#eeEmpType .pill-btn');
    empTypeBtns.forEach(function(b){ b.classList.toggle('active', b.dataset.value === (e.employment_type||'full_time')); });
    document.getElementById('eeEmpTypeHidden').value = e.employment_type||'full_time';
    document.getElementById('eeHireDate').value = e.hire_date||'';
    document.getElementById('eeContractEnd').value = e.contract_end_date||'';
    document.getElementById('eeNoEndDate').checked = e.no_end_date||false;
    document.getElementById('eeContractEnd').disabled = e.no_end_date||false;
    document.getElementById('eeManager').value = e.manager_id||'';
    document.getElementById('eeShift').value = e.shift_type_id||'';
    document.getElementById('eeBranch').value = e.branch_id||'';
    document.getElementById('eeBioEmpId').value = e.biotime_emp_id||'';
    document.getElementById('eeBioStatus').textContent = e.sync_status==='synced'?'✅':'';
    document.getElementById('eeSalary').value = e.base_salary;
    document.getElementById('eeHousing').value = e.housing_allowance||0;
    document.getElementById('eeTransport').value = e.transport_allowance||0;
    document.getElementById('eePaymentMethod').value = e.payment_method||'bank_transfer';
    toggleBankFields('edit');
    document.getElementById('eeBankName').value = e.bank_name||'';
    document.getElementById('eeBankAccount').value = e.bank_account_number||'';
    document.getElementById('eePermissionLevel').value = e.permission_level||'employee';
    document.getElementById('eeForcePassChange').checked = e.force_password_change||false;
    document.getElementById('ee2FA').checked = e.two_factor_enabled||false;
    document.getElementById('eeEmergName').value = e.emergency_contact_name||'';
    document.getElementById('eeEmergRelation').value = e.emergency_relationship||'';
    document.getElementById('eeEmergPhone').value = e.emergency_phone||'';
    document.getElementById('eeEmergPhone2').value = e.emergency_phone2||'';
    calcTotal('edit');
    document.getElementById('eeTitle').textContent = 'تعديل: '+e.full_name;
    document.getElementById('editEmpModal').classList.add('open');
    switchTab('edit','basic');
  } catch(e){ toast(e.message,'err'); }
}

async function doEditEmp(){
  var id = document.getElementById('eeId').value;
  var pass = document.getElementById('eePass').value;
  var pass2 = document.getElementById('eePassConfirm').value;
  if(pass && pass !== pass2){ toast('كلمة المرور غير متطابقة.','err'); return; }
  var otherRows = document.getElementById('eeOtherAllowances').querySelectorAll('.allowance-row');
  var allowances = [];
  otherRows.forEach(function(row){
    var inputs = row.querySelectorAll('input');
    if(inputs[0] && inputs[1] && inputs[0].value.trim()){
      allowances.push({label: inputs[0].value.trim(), amount: parseFloat(inputs[1].value) || 0});
    }
  });
  var data = {
    full_name: document.getElementById('eeName').value.trim(),
    department_id: parseInt(document.getElementById('eeDept').value) || null,
    role: document.getElementById('eeRole').value,
    password: pass,
    phone_country_code: document.getElementById('eePhoneCode').value,
    phone: document.getElementById('eePhone').value.trim(),
    national_id: document.getElementById('eeNationalId').value.trim(),
    date_of_birth: document.getElementById('eeDob').value,
    gender: document.getElementById('eeGenderHidden').value,
    marital_status: document.getElementById('eeMaritalStatus').value,
    address: document.getElementById('eeAddress').value.trim(),
    job_title: document.getElementById('eeJobTitle').value.trim(),
    employment_type: document.getElementById('eeEmpTypeHidden').value,
    hire_date: document.getElementById('eeHireDate').value,
    contract_end_date: document.getElementById('eeContractEnd').value,
    no_end_date: document.getElementById('eeNoEndDate').checked,
    manager_id: parseInt(document.getElementById('eeManager').value) || null,
    shift_type_id: parseInt(document.getElementById('eeShift').value) || null,
    branch_id: parseInt(document.getElementById('eeBranch').value) || null,
    biotime_emp_id: parseInt(document.getElementById('eeBioEmpId').value) || null,
    salary: parseFloat(document.getElementById('eeSalary').value) || 0,
    housing_allowance: parseFloat(document.getElementById('eeHousing').value) || 0,
    transport_allowance: parseFloat(document.getElementById('eeTransport').value) || 0,
    other_allowances: allowances,
    payment_method: document.getElementById('eePaymentMethod').value,
    bank_account_number: document.getElementById('eeBankAccount').value.trim(),
    bank_name: document.getElementById('eeBankName').value,
    permission_level: document.getElementById('eePermissionLevel').value,
    force_password_change: document.getElementById('eeForcePassChange').checked,
    two_factor_enabled: document.getElementById('ee2FA').checked,
    emergency_contact_name: document.getElementById('eeEmergName').value.trim(),
    emergency_relationship: document.getElementById('eeEmergRelation').value,
    emergency_phone: document.getElementById('eeEmergPhone').value.trim(),
    emergency_phone2: document.getElementById('eeEmergPhone2').value.trim(),
  };
  try {
    var r = await fetch('/admin/employees/'+id+'/edit', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify(data)
    });
    var res = await r.json();
    toast(res.msg, res.ok ? 'ok' : 'err');
    if(res.ok){
      var photoInput = document.getElementById('eePhotoInput');
      if(photoInput.files[0]){
        var fd = new FormData();
        fd.append('photo', photoInput.files[0]);
        await fetch('/admin/employees/'+id+'/photo', {method:'POST', body: fd});
      }
      closeModal('editEmpModal');
      setTimeout(function(){ location.reload(); }, 1000);
    }
  } catch(e){ toast(e.message,'err'); }
}

/* ── TOGGLE ACTIVE ── */
async function toggleEmp(id){
  try {
    var r = await api('/admin/employees/'+id+'/toggle');
    toast(r.msg, 'ok');
    setTimeout(function(){ location.reload(); }, 1200);
  } catch(e){ toast(e.message,'err'); }
}

/* ── RESET PASSWORD ── */
function openResetPass(id){
  document.getElementById('rpId').value = id;
  document.getElementById('rpPass').value = '';
  document.getElementById('rpPassConfirm').value = '';
  document.getElementById('rpPassStrength').innerHTML = '';
  document.getElementById('rpPassMatch').textContent = '';
  document.getElementById('resetPassModal').classList.add('open');
}

async function doResetPass(){
  var id = document.getElementById('rpId').value;
  var pass = document.getElementById('rpPass').value;
  var pass2 = document.getElementById('rpPassConfirm').value;
  if(!pass){ toast('كلمة المرور مطلوبة.','err'); return; }
  if(pass !== pass2){ toast('كلمة المرور غير متطابقة.','err'); return; }
  try {
    var r = await api('/admin/password-reset/'+id, {
      new_password: pass,
      force_change: document.getElementById('rpForceChange').checked
    });
    toast(r.msg, r.ok ? 'ok' : 'err');
    if(r.ok){ closeModal('resetPassModal'); if(r.password) toast('كلمة المرور الجديدة: '+r.password, 'ok'); }
  } catch(e){ toast(e.message,'err'); }
}

/* ── DELETE ── */
function deleteEmp(id){
  var card = document.querySelector('.emp-card[data-id="'+id+'"]');
  var name = card ? card.querySelector('.emp-avatar').nextElementSibling.querySelector('div:first-child').textContent : 'الموظف';
  document.getElementById('delEmpId').value = id;
  document.getElementById('delEmpName').textContent = 'حذف: '+name;
  document.getElementById('err_delEmpReason').textContent = '';
  document.getElementById('deleteEmpModal').classList.add('open');
}

async function doDeleteEmp(){
  var id = document.getElementById('delEmpId').value;
  var reason = document.getElementById('delEmpReason').value.trim();
  if(!reason){ document.getElementById('err_delEmpReason').textContent = 'سبب الحذف مطلوب'; return; }
  try {
    var r = await api('/admin/employees/'+id+'/delete', {reason: reason});
    toast(r.msg, r.ok ? 'ok' : 'err');
    if(r.ok){ closeModal('deleteEmpModal'); setTimeout(function(){ location.reload(); }, 1200); }
  } catch(e){ toast(e.message,'err'); }
}

/* ── BIOTIME SYNC ── */
async function biotimeSync(id){
  try {
    var r = await fetch('/admin/employees/'+id+'/biotime-status');
    var data = await r.json();
    if(!data.ok){ toast(data.msg,'err'); return; }
    document.getElementById('bsEmpId').value = id;
    var html = '';
    var canSync = data.devices && data.devices.length > 0;
    if(canSync){
      html += '<div class="multi-select">';
      data.devices.forEach(function(d){
        html += '<label class="ms-item"><input type="checkbox" class="bsDeviceCb" value="'+d.id+'" checked> ';
        html += esc(d.name);
        if(d.fingerprint) html += ' 🖐️';
        if(d.face) html += ' 🫱';
        html += '</label>';
      });
      html += '</div>';
    } else {
      html += '<div style="text-align:center;padding:16px;color:var(--muted)">لا توجد أجهزة متاحة</div>';
    }
    document.getElementById('bsDeviceList').innerHTML = html;
    document.getElementById('bsResult').innerHTML = '<div style="font-size:12px;color:var(--muted2)">الحالة: '+data.sync_status+' · آخر مزامنة: '+(data.last_sync||'—')+'</div>';
    document.getElementById('bioSyncModal').classList.add('open');
  } catch(e){ toast(e.message,'err'); }
}

async function doBioSync(){
  var id = document.getElementById('bsEmpId').value;
  var cbs = document.querySelectorAll('.bsDeviceCb:checked');
  var deviceIds = Array.from(cbs).map(function(cb){ return parseInt(cb.value); });
  if(!deviceIds.length){ toast('اختر جهازاً واحداً على الأقل.','err'); return; }
  document.getElementById('bsResult').innerHTML = '<div style="color:var(--muted)">⏳ جاري المزامنة...</div>';
  try {
    var r = await fetch('/admin/employees/'+id+'/biotime-sync', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify({device_ids: deviceIds})
    });
    var data = await r.json();
    var html = data.results.map(function(d){
      var icn = d.status === 'synced' ? '✅' : d.status === 'failed' ? '❌' : '⚠️';
      return '<div style="font-size:12px;padding:4px 0">'+icn+' '+esc(d.device_name||'')+': '+(d.msg||d.status)+'</div>';
    }).join('');
    document.getElementById('bsResult').innerHTML = html;
    toast(data.msg, data.ok ? 'ok' : 'err');
  } catch(e){ document.getElementById('bsResult').innerHTML = '<div style="color:#ef4444">خطأ: '+e.message+'</div>'; }
}

async function biotimeSyncFromForm(ctx){
  var prefix = ctx === 'add' ? 'ae' : 'ee';
  var empId = ctx === 'add' ? null : parseInt(document.getElementById('eeId').value);
  if(!empId){ toast('احفظ الموظف أولاً.','err'); return; }
  var bioId = parseInt(document.getElementById(prefix+'BioEmpId').value) || empId;
  var deviceCbs = document.querySelectorAll('.'+prefix+'DeviceCb:checked');
  var deviceIds = Array.from(deviceCbs).map(function(cb){ return parseInt(cb.value); });
  if(!deviceIds.length){ toast('اختر جهازاً.','err'); return; }
  try {
    var r = await fetch('/admin/employees/'+empId+'/biotime-sync', {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
      body: JSON.stringify({device_ids: deviceIds})
    });
    var data = await r.json();
    document.getElementById(prefix+'BioStatus').textContent = data.ok ? '✅' : '❌';
    toast(data.msg, data.ok ? 'ok' : 'err');
  } catch(e){ toast(e.message,'err'); }
}

/* ── Helpers ── */
function esc(s){ if(!s) return ''; var d=document.createElement('div'); d.appendChild(document.createTextNode(s)); return d.innerHTML; }
function closeModal(id){ document.getElementById(id).classList.remove('open'); }
async function api(url, data){
  var r = await fetch(url, {
    method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken': csrfToken()},
    body: JSON.stringify(data||{})
  });
  return r.json();
}
