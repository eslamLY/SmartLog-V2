(function() {
  const tabs = document.querySelectorAll('#formTabs .tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', function() {
      tabs.forEach(t => t.classList.remove('active'));
      this.classList.add('active');
      document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
      const target = document.getElementById('tab-' + this.dataset.tab);
      if (target) target.classList.add('active');
    });
  });
  const eidInput = document.getElementById('employee_id');
  if (eidInput && eidInput.value) {
    loadExistingData(parseInt(eidInput.value));
  }
})();

function loadExistingData(eid) {
  api('/admin/employees/' + eid + '/extended').then(data => {
    if (!data || !data.extended) return;
    const e = data.extended;
    setVal('national_id', e.national_id);
    setVal('passport_number', e.passport_number);
    setVal('id_expiry_date', e.id_expiry_date);
    setVal('id_issuing_authority', e.id_issuing_authority);
    setChecked('id_verified', e.id_verified);
    setVal('personal_phone', e.personal_phone);
    setVal('work_phone', e.work_phone);
    setVal('personal_email', e.personal_email);
    setVal('work_email', e.work_email);
    setVal('permanent_address', e.permanent_address);
    setVal('current_address', e.current_address);
    setVal('emergency_name', e.emergency_name);
    setVal('emergency_phone', e.emergency_phone);
    setVal('emergency_relation', e.emergency_relation);
    setVal('bank_name', e.bank_name);
    setVal('bank_account_name', e.bank_account_name);
    setVal('iban', e.iban);
    setVal('bank_account_type', e.bank_account_type);
    setVal('bank_branch', e.bank_branch);
    setChecked('bank_account_verified', e.bank_account_verified);
    setVal('marital_status', e.marital_status);
    setVal('spouse_name', e.spouse_name);
    setVal('dependent_children', e.dependent_children);
    if (e.grade_id) setVal('grade_id', e.grade_id);
    setVal('job_classification', e.job_classification);
    setVal('career_path', e.career_path);
    setVal('contract_type', e.contract_type);
    setVal('gov_file_number', e.gov_file_number);
    setVal('gov_central_emp_id', e.gov_central_emp_id);
    setVal('gov_region', e.gov_region);
    setVal('gov_sector', e.gov_sector);
    setVal('gov_parent_institution', e.gov_parent_institution);
    setVal('gov_supervisory_body', e.gov_supervisory_body);
    setVal('clearance_level', e.clearance_level);
    setVal('clearance_date', e.clearance_date);
    setVal('clearance_expiry', e.clearance_expiry);
    setVal('clearance_authority', e.clearance_authority);
    setVal('social_security_number', e.social_security_number);
    setVal('social_security_start', e.social_security_start);
    setVal('social_security_rate', e.social_security_rate);
    setVal('accumulated_contributions', e.accumulated_contributions);
    setVal('health_insurance_level', e.health_insurance_level);
    setVal('health_insurance_dependents', e.health_insurance_dependents);
    setVal('health_insurance_premium', e.health_insurance_premium);
    setVal('life_insurance_coverage', e.life_insurance_coverage);
    setVal('life_insurance_beneficiary', e.life_insurance_beneficiary);
    setVal('life_insurance_premium', e.life_insurance_premium);
    setVal('injury_insurance_coverage', e.injury_insurance_coverage);
    setVal('retirement_age', e.retirement_age);
    setVal('pension_rate', e.pension_rate);
    setVal('years_of_service', e.years_of_service);
    setVal('expected_pension', e.expected_pension);
    setVal('annual_leave_days', e.annual_leave_days);
    setVal('sick_leave_days', e.sick_leave_days);
    setVal('maternity_leave_days', e.maternity_leave_days);
    setVal('paternity_leave_days', e.paternity_leave_days);
    setVal('marriage_leave_days', e.marriage_leave_days);
    setVal('hajj_leave_days', e.hajj_leave_days);

    // Children
    if (data.children && data.children.length) {
      document.getElementById('childrenContainer').innerHTML = '';
      data.children.forEach(c => addChildRow(c));
    }

    // Qualifications
    if (data.qualifications && data.qualifications.length) {
      document.getElementById('qualificationsContainer').innerHTML = '';
      data.qualifications.forEach(q => addQualRow(q));
    }

    // Certifications
    if (data.certifications && data.certifications.length) {
      document.getElementById('certificationsContainer').innerHTML = '';
      data.certifications.forEach(c => addCertRow(c));
    }
  });
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (el && val !== null && val !== undefined) el.value = val;
}

function setChecked(id, val) {
  const el = document.getElementById(id);
  if (el) el.checked = !!val;
}

function getVal(id) {
  const el = document.getElementById(id);
  return el ? el.value : '';
}

function getChecked(id) {
  const el = document.getElementById(id);
  return el ? el.checked : false;
}

function addChildRow(data) {
  const container = document.getElementById('childrenContainer');
  const row = document.createElement('div');
  row.className = 'child-row';
  row.style.cssText = 'display:grid;grid-template-columns:2fr 1fr 1fr 60px 60px 30px;gap:8px;align-items:end;margin-bottom:8px;padding:10px;background:var(--bg);border-radius:10px';
  const birthVal = data && data.birth_date ? data.birth_date : '';
  row.innerHTML = `
    <div><label>الاسم</label><input type="text" class="form-input child-name" value="${data && data.full_name ? data.full_name : ''}"></div>
    <div><label>تاريخ الميلاد</label><input type="date" class="form-input child-birth" value="${birthVal}"></div>
    <div><label>صلة القرابة</label>
      <select class="form-input child-relation">
        <option value="child" ${data && data.relation === 'child' ? 'selected' : ''}>ابن</option>
        <option value="daughter" ${data && data.relation === 'daughter' ? 'selected' : ''}>ابنة</option>
        <option value="other" ${data && data.relation === 'other' ? 'selected' : ''}>أخرى</option>
      </select>
    </div>
    <div class="checkbox-cell" style="padding-bottom:6px"><label style="font-size:11px"><input type="checkbox" class="child-student" ${data && data.is_student ? 'checked' : ''}> طالب</label></div>
    <div class="checkbox-cell" style="padding-bottom:6px"><label style="font-size:11px"><input type="checkbox" class="child-disabled" ${data && data.is_disabled ? 'checked' : ''}> إعاقة</label></div>
    <div style="padding-bottom:6px"><button type="button" class="btn btn-ghost btn-xs" onclick="this.closest('.child-row').remove()" style="color:var(--red)"><i class="ti ti-x"></i></button></div>`;
  container.appendChild(row);
}

function addQualRow(data) {
  const container = document.getElementById('qualificationsContainer');
  const row = document.createElement('div');
  row.className = 'qual-row';
  row.style.cssText = 'display:grid;grid-template-columns:1fr 1fr 1fr 80px 60px 30px;gap:8px;align-items:end;margin-bottom:8px;padding:10px;background:var(--bg);border-radius:10px';
  row.innerHTML = `
    <div><label>المستوى</label>
      <select class="form-input qual-level">
        <option value="primary" ${data && data.level === 'primary' ? 'selected' : ''}>ابتدائي</option>
        <option value="intermediate" ${data && data.level === 'intermediate' ? 'selected' : ''}>إعدادي</option>
        <option value="secondary" ${data && data.level === 'secondary' ? 'selected' : ''}>ثانوي</option>
        <option value="diploma" ${data && data.level === 'diploma' ? 'selected' : ''}>دبلوم</option>
        <option value="bachelor" ${data && data.level === 'bachelor' ? 'selected' : ''}>بكالوريوس</option>
        <option value="master" ${data && data.level === 'master' ? 'selected' : ''}>ماجستير</option>
        <option value="doctorate" ${data && data.level === 'doctorate' ? 'selected' : ''}>دكتوراه</option>
      </select>
    </div>
    <div><label>التخصص</label><input type="text" class="form-input qual-specialization" value="${data && data.specialization ? data.specialization : ''}"></div>
    <div><label>المؤسسة</label><input type="text" class="form-input qual-institution" value="${data && data.institution ? data.institution : ''}"></div>
    <div><label>سنة التخرج</label><input type="number" class="form-input qual-year" min="1950" max="2030" value="${data && data.graduation_year ? data.graduation_year : ''}"></div>
    <div class="checkbox-cell" style="padding-bottom:6px"><label style="font-size:11px"><input type="checkbox" class="qual-foreign" ${data && data.is_foreign ? 'checked' : ''}> خارجي</label></div>
    <div style="padding-bottom:6px"><button type="button" class="btn btn-ghost btn-xs" onclick="this.closest('.qual-row').remove()" style="color:var(--red)"><i class="ti ti-x"></i></button></div>`;
  container.appendChild(row);
}

function addCertRow(data) {
  const container = document.getElementById('certificationsContainer');
  const row = document.createElement('div');
  row.className = 'cert-row';
  row.style.cssText = 'display:grid;grid-template-columns:1fr 1fr 1fr 1fr 30px;gap:8px;align-items:end;margin-bottom:8px;padding:10px;background:var(--bg);border-radius:10px';
  const issueVal = data && data.issue_date ? data.issue_date : '';
  const expiryVal = data && data.expiry_date ? data.expiry_date : '';
  row.innerHTML = `
    <div><label>نوع الشهادة</label><input type="text" class="form-input cert-type" value="${data && data.cert_type ? data.cert_type : ''}"></div>
    <div><label>رقم الشهادة</label><input type="text" class="form-input cert-number" value="${data && data.cert_number ? data.cert_number : ''}"></div>
    <div><label>جهة الإصدار</label><input type="text" class="form-input cert-body" value="${data && data.issuing_body ? data.issuing_body : ''}"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">
      <div><label>الإصدار</label><input type="date" class="form-input cert-issue" value="${issueVal}"></div>
      <div><label>الانتهاء</label><input type="date" class="form-input cert-expiry" value="${expiryVal}"></div>
    </div>
    <div style="padding-bottom:6px"><button type="button" class="btn btn-ghost btn-xs" onclick="this.closest('.cert-row').remove()" style="color:var(--red)"><i class="ti ti-x"></i></button></div>`;
  container.appendChild(row);
}

function collectFormData() {
  const children = [];
  document.querySelectorAll('#childrenContainer .child-row').forEach(row => {
    children.push({
      full_name: row.querySelector('.child-name').value,
      birth_date: row.querySelector('.child-birth').value,
      relation: row.querySelector('.child-relation').value,
      is_student: row.querySelector('.child-student').checked,
      is_disabled: row.querySelector('.child-disabled').checked,
    });
  });

  const qualifications = [];
  document.querySelectorAll('#qualificationsContainer .qual-row').forEach(row => {
    qualifications.push({
      level: row.querySelector('.qual-level').value,
      specialization: row.querySelector('.qual-specialization').value,
      institution: row.querySelector('.qual-institution').value,
      graduation_year: parseInt(row.querySelector('.qual-year').value) || null,
      is_foreign: row.querySelector('.qual-foreign').checked,
    });
  });

  const certifications = [];
  document.querySelectorAll('#certificationsContainer .cert-row').forEach(row => {
    certifications.push({
      cert_type: row.querySelector('.cert-type').value,
      cert_number: row.querySelector('.cert-number').value,
      issuing_body: row.querySelector('.cert-body').value,
      issue_date: row.querySelector('.cert-issue').value,
      expiry_date: row.querySelector('.cert-expiry').value,
    });
  });

  return {
    employee_id: parseInt(getVal('employee_id')),
    national_id: getVal('national_id'),
    passport_number: getVal('passport_number'),
    id_expiry_date: getVal('id_expiry_date'),
    id_issuing_authority: getVal('id_issuing_authority'),
    id_verified: getChecked('id_verified'),
    personal_phone: getVal('personal_phone'),
    work_phone: getVal('work_phone'),
    personal_email: getVal('personal_email'),
    work_email: getVal('work_email'),
    permanent_address: getVal('permanent_address'),
    current_address: getVal('current_address'),
    emergency_name: getVal('emergency_name'),
    emergency_phone: getVal('emergency_phone'),
    emergency_relation: getVal('emergency_relation'),
    bank_name: getVal('bank_name'),
    bank_account_name: getVal('bank_account_name'),
    iban: getVal('iban'),
    bank_account_type: getVal('bank_account_type'),
    bank_branch: getVal('bank_branch'),
    bank_account_verified: getChecked('bank_account_verified'),
    marital_status: getVal('marital_status'),
    spouse_name: getVal('spouse_name'),
    dependent_children: parseInt(getVal('dependent_children')) || 0,
    grade_id: getVal('grade_id') ? parseInt(getVal('grade_id')) : null,
    job_classification: getVal('job_classification'),
    career_path: getVal('career_path'),
    contract_type: getVal('contract_type'),
    gov_file_number: getVal('gov_file_number'),
    gov_central_emp_id: getVal('gov_central_emp_id'),
    gov_region: getVal('gov_region'),
    gov_sector: getVal('gov_sector'),
    gov_parent_institution: getVal('gov_parent_institution'),
    gov_supervisory_body: getVal('gov_supervisory_body'),
    clearance_level: getVal('clearance_level'),
    clearance_date: getVal('clearance_date'),
    clearance_expiry: getVal('clearance_expiry'),
    clearance_authority: getVal('clearance_authority'),
    social_security_number: getVal('social_security_number'),
    social_security_start: getVal('social_security_start'),
    social_security_rate: parseFloat(getVal('social_security_rate')) || 8.0,
    accumulated_contributions: parseFloat(getVal('accumulated_contributions')) || 0,
    health_insurance_level: getVal('health_insurance_level'),
    health_insurance_dependents: parseInt(getVal('health_insurance_dependents')) || 0,
    health_insurance_premium: parseFloat(getVal('health_insurance_premium')) || 0,
    life_insurance_coverage: parseFloat(getVal('life_insurance_coverage')) || 0,
    life_insurance_beneficiary: getVal('life_insurance_beneficiary'),
    life_insurance_premium: parseFloat(getVal('life_insurance_premium')) || 0,
    injury_insurance_coverage: parseFloat(getVal('injury_insurance_coverage')) || 0,
    retirement_age: parseInt(getVal('retirement_age')) || 60,
    pension_rate: parseFloat(getVal('pension_rate')) || 2.5,
    years_of_service: parseFloat(getVal('years_of_service')) || 0,
    expected_pension: parseFloat(getVal('expected_pension')) || 0,
    annual_leave_days: parseInt(getVal('annual_leave_days')) || 30,
    sick_leave_days: parseInt(getVal('sick_leave_days')) || 15,
    maternity_leave_days: parseInt(getVal('maternity_leave_days')) || 60,
    paternity_leave_days: parseInt(getVal('paternity_leave_days')) || 5,
    marriage_leave_days: parseInt(getVal('marriage_leave_days')) || 7,
    hajj_leave_days: parseInt(getVal('hajj_leave_days')) || 15,
    children: children,
    qualifications: qualifications,
    certifications: certifications,
  };
}

function saveAll() {
  const btn = document.getElementById('saveBtn');
  loadingBtn(btn);
  const data = collectFormData();
  api('/admin/employees/add-form/save', data).then(resp => {
    restoreBtn(btn);
    if (resp.ok) {
      toast('تم حفظ البيانات بنجاح', 'ok');
    } else {
      toast(resp.msg || 'فشل الحفظ', 'err');
    }
  }).catch(err => {
    restoreBtn(btn);
    toast('خطأ: ' + err.message, 'err');
  });
}
