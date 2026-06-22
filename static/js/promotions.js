function switchPromoTab(tabId, el) {
  document.querySelectorAll('.promo-tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('active'));
  document.getElementById('promo-' + tabId).classList.add('active');
  el.classList.add('active');
}

function loadEligible() {
  api('/admin/promotions/eligible').then(data => {
    const tbody = document.getElementById('eligibleBody');
    if (!data.employees || data.employees.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:30px">لا يوجد موظفون مؤهلون</td></tr>';
      return;
    }
    tbody.innerHTML = data.employees.map(e => {
      const el = e.eligibility || {};
      const pct = el.total_requirements > 0 ? Math.round(el.completed_requirements / el.total_requirements * 100) : 0;
      return `<tr>
        <td><strong>${e.full_name}</strong><br><small style="color:var(--muted)">${e.employee_code || ''}</small></td>
        <td>${e.department || ''}</td>
        <td>${el.current_grade || 'N/A'}</td>
        <td>${el.target_grade || 'N/A'}</td>
        <td>
          <div style="display:flex;align-items:center;gap:8px">
            <div class="progress-bar" style="flex:1;max-width:100px"><div class="progress-fill" style="width:${pct}%;background:${el.eligible ? 'var(--green)' : 'var(--amber)'}"></div></div>
            <span style="font-size:12px;font-weight:600">${el.completed_requirements}/${el.total_requirements}</span>
          </div>
          <div style="font-size:11px;color:var(--muted);margin-top:4px">
            ${el.min_service_met ? '<span style="color:var(--green)">✓</span>' : '<span style="color:var(--red)">✗</span>} الخدمة
            ${el.performance_met ? '<span style="color:var(--green)">✓</span>' : '<span style="color:var(--red)">✗</span>} الأداء
            ${el.qualifications_met ? '<span style="color:var(--green)">✓</span>' : '<span style="color:var(--red)">✗</span>} المؤهل
            ${el.conduct_met ? '<span style="color:var(--green)">✓</span>' : '<span style="color:var(--red)">✗</span>} السلوك
          </div>
        </td>
        <td>
          ${el.eligible ? `<button class="btn btn-green btn-xs" onclick="quickPromote(${e.id})"><i class="ti ti-arrow-up"></i> ترقية</button>` : '<span style="color:var(--muted);font-size:12px">غير مؤهل</span>'}
        </td>
      </tr>`;
    }).join('');
  });
}

function quickPromote(eid) {
  api('/admin/promotions/execute', { employee_id: eid }).then(data => {
    if (data.success) {
      toast('تمت الترقية بنجاح', 'ok');
      loadEligible();
    } else {
      toast(data.error || 'فشلت الترقية', 'err');
    }
  });
}

function checkPromotion() {
  const eid = parseInt(document.getElementById('checkEmpId').value);
  if (!eid) { toast('الرجاء إدخال رقم الموظف', 'err'); return; }
  api('/admin/promotions/check/' + eid).then(data => {
    const result = document.getElementById('checkResult');
    result.style.display = 'block';
    if (!data.ok) {
      result.innerHTML = `<div class="card" style="padding:20px;text-align:center;color:var(--red)">${data.msg}</div>`;
      return;
    }
    const bars = [];
    ['min_service_met', 'performance_met', 'qualifications_met', 'conduct_met'].forEach(k => {
      const met = data[k];
      const labels = { min_service_met: 'مدة الخدمة', performance_met: 'تقييم الأداء', qualifications_met: 'المؤهلات', conduct_met: 'السلوك الوظيفي' };
      bars.push(`<div style="display:flex;align-items:center;gap:10px;padding:6px 0">
        <span style="font-size:13px;flex:1">${labels[k]}</span>
        <span style="color:${met ? 'var(--green)' : 'var(--red)'};font-size:13px;font-weight:600">${met ? 'مكتمل ✓' : 'غير مكتمل ✗'}</span>
      </div>`);
    });
    const pct = data.total_requirements > 0 ? Math.round(data.completed_requirements / data.total_requirements * 100) : 0;
    result.innerHTML = `<div class="card" style="padding:20px;max-width:500px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <div><strong style="font-size:15px">${data.current_grade}</strong> <i class="ti ti-arrow-left" style="color:var(--accent)"></i> <strong style="font-size:15px;color:var(--accent)">${data.target_grade}</strong></div>
        <div style="text-align:left">
          <div style="font-size:12px;color:var(--muted)">سنوات الخدمة: ${data.service_years}</div>
          <div style="font-size:12px;color:var(--muted)">${data.from_salary || data.current_grade ? 'الراتب الحالي: ' + (data.from_salary || '') : ''}</div>
        </div>
      </div>
      <div style="margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-bottom:4px">
          <span>متطلبات الترقية</span><span>${data.completed_requirements}/${data.total_requirements}</span>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:${pct}%;background:${data.eligible ? 'var(--green)' : 'var(--amber)'}"></div></div>
      </div>
      ${bars.join('')}
      <div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--border);display:flex;gap:8px">
        ${data.eligible ? `<button class="btn btn-green btn-sm" onclick="quickPromote(${eid})"><i class="ti ti-arrow-up"></i> تنفيذ الترقية</button>` : '<span style="color:var(--muted);font-size:13px">الموظف غير مؤهل للترقية حالياً</span>'}
      </div>
    </div>`;
  });
}

function executePromotion() {
  const eid = parseInt(document.getElementById('execEmpId').value);
  if (!eid) { toast('الرجاء إدخال رقم الموظف', 'err'); return; }
  api('/admin/promotions/execute', {
    employee_id: eid,
    decision_number: document.getElementById('execDecisionNo').value,
    decision_date: document.getElementById('execDecisionDate').value,
    effective_date: document.getElementById('execEffectiveDate').value,
    justification: document.getElementById('execJustification').value,
  }).then(data => {
    if (data.success) { toast('تم تنفيذ الترقية بنجاح', 'ok'); }
    else { toast(data.error || 'فشلت الترقية', 'err'); }
  });
}

function loadPromotionHistory() {
  const eid = parseInt(document.getElementById('historyEmpId').value);
  if (!eid) { toast('الرجاء إدخال رقم الموظف', 'err'); return; }
  api('/admin/promotions/history/' + eid).then(data => {
    const tbody = document.getElementById('historyBody');
    if (!data.promotions || data.promotions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:30px">لا يوجد سجل ترقيات</td></tr>';
      return;
    }
    tbody.innerHTML = data.promotions.map(p => `<tr>
      <td>${p.from_grade_name || 'N/A'}</td>
      <td><strong>${p.to_grade_name}</strong></td>
      <td>${p.from_salary || 0}</td>
      <td>${p.to_salary || 0}</td>
      <td>${p.decision_number || ''}</td>
      <td>${p.effective_date || ''}</td>
      <td><span class="badge ${p.status === 'completed' ? 'badge-present' : 'badge-info'}">${p.status === 'completed' ? 'مكتملة' : p.status}</span></td>
    </tr>`).join('');
  });
}

// Load grade chain on page load
document.addEventListener('DOMContentLoaded', function() {
  api('/admin/promotions/grades').then(data => {
    const tbody = document.getElementById('gradesBody');
    if (!data.grades || data.grades.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:30px">لا توجد درجات</td></tr>';
      return;
    }
    tbody.innerHTML = data.grades.map(g => `<tr>
      <td><strong>${g.name_ar}</strong></td>
      <td>${g.code}</td>
      <td>${g.level}</td>
      <td>${g.base_salary}</td>
      <td>${g.responsibility_allowance || 0}</td>
      <td>${g.transport_allowance || 0}</td>
      <td>${g.housing_allowance || 0}</td>
      <td>${g.next_grade_id ? 'يوجد' : '—'}</td>
    </tr>`).join('');
  });
});
