let currentPayrollTab = 1;
let payslipData = {};

function csrfToken() {
  var m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}

function switchPayrollTab(tab, btn) {
  currentPayrollTab = tab;
  document.querySelectorAll('.payroll-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.payroll-panel').forEach(p => p.style.display = 'none');
  const panel = document.getElementById('tab' + tab + 'Panel');
  if (panel) panel.style.display = 'block';
  if (tab === 3) loadAnalytics();
  if (tab === 4) loadAdvances();
  if (tab === 5) runComparison();
  if (tab === 6) loadApprovals();
  if (tab === 7) loadBankPayments();
}

function togglePayrollTheme() {
  document.body.classList.toggle('light-mode');
  const icon = document.querySelector('#payrollThemeToggle i');
  if (icon) icon.className = document.body.classList.contains('light-mode') ? 'ti ti-sun' : 'ti ti-moon';
  localStorage.setItem('payroll_theme', document.body.classList.contains('light-mode') ? 'light' : 'dark');
}

const savedPayrollTheme = localStorage.getItem('payroll_theme');
if (savedPayrollTheme === 'light') {
  document.body.classList.add('light-mode');
  const icon = document.querySelector('#payrollThemeToggle i');
  if (icon) icon.className = 'ti ti-sun';
}

function togglePayrollExport() {
  const menu = document.getElementById('payrollExportMenu');
  if (menu) menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
}

document.addEventListener('click', function(e) {
  if (!e.target.closest('.payroll-export-dropdown')) {
    const menu = document.getElementById('payrollExportMenu');
    if (menu) menu.style.display = 'none';
  }
});

function toggleRowDetail(tr, empId) {
  const detail = document.getElementById('rowDetail' + empId);
  if (detail) {
    const isVisible = detail.style.display !== 'none';
    detail.style.display = isVisible ? 'none' : 'table-row';
  }
}

function showAllowBreakdown(el, empId) {
  const row = document.querySelector(`#mainPayrollTable tbody tr[data-emp-id="${empId}"]`);
  const modal = document.getElementById('allowBreakdownModal');
  const body = document.getElementById('allowBreakdownBody');
  if (!modal || !body) return;
  if (window.payData && window.payData[empId]) {
    const comp = window.payData[empId].comp || window.payData[empId];
    let html = '<table class="tbl" style="width:100%"><thead><tr><th>البدل</th><th>المبلغ</th></tr></thead><tbody>';
    html += '<tr><td>بدل سكن</td><td>' + (comp.housing_allowance || 0) + ' د.ل</td></tr>';
    html += '<tr><td>بدل مواصلات</td><td>' + (comp.transport_allowance || 0) + ' د.ل</td></tr>';
    (comp.other_allowances || []).forEach(function(a) {
      html += '<tr><td>' + (a.label || 'بدل') + '</td><td>' + (a.amount || 0) + ' د.ل</td></tr>';
    });
    html += '<tr style="font-weight:700;background:var(--card2)"><td>الإجمالي</td><td>' + (comp.total_allowances || 0) + ' د.ل</td></tr>';
    html += '</tbody></table>';
    body.innerHTML = html;
  } else {
    body.innerHTML = '<p>لا توجد بيانات</p>';
  }
  modal.classList.add('open');
}

function viewPayslip(empId) {
  const params = new URLSearchParams({ month: CURRENT_MONTH, year: CURRENT_YEAR });
  window.open(API_BASE + '/api/payslip/' + empId + '/print?' + params.toString(), '_blank');
}

function printPayslip(empId) {
  viewPayslip(empId);
}

function openApproval(empId) {
  const modal = document.getElementById('approvalModal');
  const nameEl = document.getElementById('apprEmpName');
  const currentEl = document.getElementById('apprCurrent');
  const proposedEl = document.getElementById('apprProposed');
  if (!modal || !nameEl) return;
  let empData = null;
  if (window.payData && window.payData[empId]) {
    empData = window.payData[empId].emp || window.payData[empId];
  }
  nameEl.textContent = empData ? empData.full_name : 'موظف #' + empId;
  fetch(API_BASE + '/api/employee/' + empId + '?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR)
    .then(r => r.json())
    .then(d => {
      if (!d || !d.ok) return;
      currentEl.textContent = d.comp.gross + ' د.ل';
      proposedEl.value = d.comp.gross;
      proposedEl.dataset.empId = empId;
    }).catch(e => console.error('payroll fetch error', e));
  modal.classList.add('open');
}

function submitApproval() {
  const proposed = document.getElementById('apprProposed');
  const reason = document.getElementById('apprReason');
  const empId = proposed ? proposed.dataset.empId : null;
  if (!empId) { toast('الرجاء اختيار الموظف', 'err'); return; }
  const data = {
    employee_id: parseInt(empId),
    proposed_gross: parseFloat(proposed.value) || 0,
    month: CURRENT_MONTH,
    year: CURRENT_YEAR,
    reason: reason ? reason.value : '',
  };
  fetch(API_BASE + '/api/approvals/initiate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken()},
    body: JSON.stringify(data),
  })
  .then(r => r.json())
  .then(d => {
    toast(d.msg, d.ok ? 'ok' : 'err');
    if (d.ok) document.getElementById('approvalModal').classList.remove('open');
  });
}

function loadIndividualPayslip() {
  const select = document.getElementById('individualEmpSelect');
  const container = document.getElementById('individualPayslipContainer');
  const empId = select ? select.value : '';
  if (!empId) {
    container.innerHTML = '<div class="empty-state"><i class="ti ti-file-text"></i><p>اختر موظفاً لعرض كشف الراتب الفردي</p></div>';
    return;
  }
  container.innerHTML = '<div class="skeleton-list" style="height:400px"></div>';
  fetch(API_BASE + '/api/employee/' + empId + '?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR)
    .then(r => r.json())
    .then(d => {
      if (!d || !d.ok) return;
      let html = '<div class="individual-payslip">';
      html += '<div class="ip-header"><h3>' + d.emp.full_name + '</h3><span class="ip-sub">' + d.emp.username + ' — ' + d.emp.department + '</span></div>';
      html += '<div class="ip-grid">';
      html += '<div class="ip-section"><div class="ip-section-title">الإيرادات</div>';
      html += '<div class="ip-row"><span>الراتب الأساسي</span><span>' + d.comp.base + ' د.ل</span></div>';
      html += '<div class="ip-row"><span>بدل سكن</span><span>' + d.comp.housing_allowance + ' د.ل</span></div>';
      html += '<div class="ip-row"><span>بدل مواصلات</span><span>' + d.comp.transport_allowance + ' د.ل</span></div>';
      (d.comp.other_allowances || []).forEach(function(a) {
        html += '<div class="ip-row"><span>' + (a.label || 'بدل') + '</span><span>' + (a.amount || 0) + ' د.ل</span></div>';
      });
      html += '<div class="ip-row"><span>العمل الإضافي</span><span>' + d.comp.overtime_pay + ' د.ل</span></div>';
      html += '<div class="ip-row ip-total"><span>الإجمالي</span><span>' + d.comp.gross + ' د.ل</span></div>';
      html += '</div>';
      html += '<div class="ip-section"><div class="ip-section-title">الخصومات</div>';
      html += '<div class="ip-row text-red"><span>تأخيرات</span><span>-' + d.comp.late_deduction + ' د.ل</span></div>';
      html += '<div class="ip-row text-red"><span>غيابات</span><span>-' + d.comp.absent_deduction + ' د.ل</span></div>';
      html += '<div class="ip-row text-amber"><span>ضريبة الدخل</span><span>-' + d.comp.tax_income + ' د.ل</span></div>';
      html += '<div class="ip-row text-amber"><span>التأمينات</span><span>-' + d.comp.tax_social + ' د.ل</span></div>';
      html += '<div class="ip-row ip-total text-red"><span>إجمالي الخصومات</span><span>-' + (d.comp.total_deductions + d.comp.total_tax) + ' د.ل</span></div>';
      html += '</div>';
      html += '</div>';
      html += '<div class="ip-net-box"><span class="ip-net-label">صافي الراتب</span><span class="ip-net-value">' + d.comp.net + ' د.ل</span></div>';
      html += '<div class="ip-actions"><button class="btn btn-sm btn-indigo" onclick="window.open(API_BASE + \'/api/payslip/' + empId + '/print?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR + '\', \'_blank\')"><i class="ti ti-printer"></i> طباعة</button></div>';
      html += '</div>';
      container.innerHTML = html;
    }).catch(e => console.error('payroll fetch error', e));
}

function printCurrentPayslip() {
  const select = document.getElementById('individualEmpSelect');
  if (select && select.value) {
    window.open(API_BASE + '/api/payslip/' + select.value + '/print?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR, '_blank');
  } else {
    toast('الرجاء اختيار موظف أولاً', 'err');
  }
}

function loadAdvances() {
  const body = document.getElementById('advancesBody');
  const summary = document.getElementById('advancesSummary');
  if (!body) return;
  body.innerHTML = '<tr><td colspan="9"><div class="skeleton-list"></div></td></tr>';
  fetch(API_BASE + '/api/advances?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR)
    .then(r => r.json())
    .then(d => {
      if (!d || !d.ok) return;
      summary.innerHTML = '<div class="mini-cards"><div class="mini-card"><span class="mc-label">إجمالي السلفات</span><span class="mc-value">' + d.total_advanced + ' د.ل</span></div><div class="mini-card"><span class="mc-label">المسدّد</span><span class="mc-value text-green">' + d.total_repaid + ' د.ل</span></div><div class="mini-card"><span class="mc-label">المتبقي</span><span class="mc-value text-red">' + d.total_remaining + ' د.ل</span></div><div class="mini-card"><span class="mc-label">نشط</span><span class="mc-value">' + d.active_count + '/' + d.count + '</span></div></div>';
      if (!d.advances || d.advances.length === 0) {
        body.innerHTML = '<tr><td colspan="9"><div class="empty-state"><i class="ti ti-wallet"></i><p>لا توجد سلفات</p></div></td></tr>';
        return;
      }
      body.innerHTML = d.advances.map(a => {
        const statusMap = {active:'نشط',settled:'مسدّد',cancelled:'ملغي'};
        return '<tr><td><div class="emp-mini"><span class="emp-avatar-mini">' + a.employee_name[0] + '</span><div><div class="emp-name-sm">' + a.employee_name + '</div><div class="emp-id-sm">' + a.employee_username + '</div></div></div></td><td>' + a.department + '</td><td class="num-cell">' + a.amount + '</td><td class="num-cell text-green">' + a.repaid + '</td><td class="num-cell text-red">' + a.remaining + '</td><td><div class="pct-bar"><div class="pct-fill" style="width:' + a.repaid_pct + '%"></div><span>' + a.repaid_pct + '%</span></div></td><td>' + a.installments_count + ' قسط</td><td><span class="status-pill status-' + a.status + '">' + (statusMap[a.status] || a.status) + '</span></td><td><button class="btn-icon" onclick="repayAdvance(' + a.id + ')" title="تسديد"><i class="ti ti-check"></i></button></td></tr>';
      }).join('');
    }).catch(e => console.error('payroll fetch error', e));
}

function openAdvanceModal() {
  const modal = document.getElementById('advanceModal');
  const select = document.getElementById('advEmp');
  if (!modal || !select) return;
  fetch(API_BASE + '?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR, {
    headers: {'X-Requested-With': 'XMLHttpRequest'}
  })
  .then(r => r.json())
  .then(d => {
    if (!d || !d.ok) return;
    select.innerHTML = d.pay_rows.map(function(r) {
      return '<option value="' + r.emp.id + '">' + r.emp.full_name + ' (' + r.emp.username + ')</option>';
    }).join('');
  }).catch(e => console.error('payroll fetch error', e));
  modal.classList.add('open');
}

function submitAdvance() {
  const empId = document.getElementById('advEmp').value;
  const amount = parseFloat(document.getElementById('advAmount').value);
  const installments = parseInt(document.getElementById('advInstallments').value) || 1;
  const reason = document.getElementById('advReason').value;
  const autoDeduct = document.getElementById('advAutoDeduct').checked;
  if (!empId || !amount) { toast('الرجاء إدخال البيانات', 'err'); return; }
  fetch(API_BASE + '/api/advances/create', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken()},
    body: JSON.stringify({employee_id: parseInt(empId), amount: amount, installments: installments, reason: reason, auto_deduct: autoDeduct}),
  })
  .then(r => r.json())
  .then(d => {
    if (!d || !d.ok) return;
    toast(d.msg, d.ok ? 'ok' : 'err');
    if (d.ok) { document.getElementById('advanceModal').classList.remove('open'); loadAdvances(); }
  }).catch(e => console.error('payroll fetch error', e));
}

function repayAdvance(aid) {
  const amt = prompt('المبلغ المسدد:');
  if (!amt) return;
  fetch(API_BASE + '/api/advances/' + aid + '/repay', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken()},
    body: JSON.stringify({amount: parseFloat(amt)}),
  })
  .then(r => r.json())
  .then(d => { if (!d || !d.ok) return; toast(d.msg, d.ok ? 'ok' : 'err'); if (d.ok) loadAdvances(); }).catch(e => console.error('payroll fetch error', e));
}

function runComparison() {
  const m1 = document.getElementById('compMonth1');
  const y1 = document.getElementById('compYear1');
  const m2 = document.getElementById('compMonth2');
  const y2 = document.getElementById('compYear2');
  if (!m1) return;
  const body = document.getElementById('compareBody');
  const summary = document.getElementById('compareSummary');
  if (!body) return;
  body.innerHTML = '<tr><td colspan="5"><div class="skeleton-list"></div></td></tr>';
  const params = new URLSearchParams({month: m1.value, year: y1.value, compare_month: m2.value, compare_year: y2.value});
  fetch(API_BASE + '/api/compare?' + params.toString())
    .then(r => r.json())
    .then(d => {
      if (!d || !d.ok) return;
      const s = d.summary;
      summary.innerHTML = '<div class="mini-cards"><div class="mini-card"><span class="mc-label">' + s.previous_label + '</span><span class="mc-value">' + s.previous_total_net + ' د.ل</span></div><div class="mini-card"><span class="mc-label">' + s.current_label + '</span><span class="mc-value">' + s.current_total_net + ' د.ل</span></div><div class="mini-card"><span class="mc-label">التغيير</span><span class="mc-value ' + (s.total_change >= 0 ? 'text-green' : 'text-red') + '">' + (s.total_change >= 0 ? '+' : '') + s.total_change + ' د.ل (' + (s.total_change >= 0 ? '+' : '') + s.total_change_pct + '%)</span></div><div class="mini-card"><span class="mc-label">زيادات / تخفيضات</span><span class="mc-value"><span class="text-green">+' + s.raises_count + '</span> / <span class="text-red">-' + s.cuts_count + '</span></span></div></div>';
      if (!d.rows || d.rows.length === 0) {
        body.innerHTML = '<tr><td colspan="5"><div class="empty-state"><i class="ti ti-database-off"></i><p>لا توجد بيانات</p></div></td></tr>';
        return;
      }
      body.innerHTML = d.rows.map(function(r) {
        const cls = r.net_change > 0 ? 'text-green' : (r.net_change < 0 ? 'text-red' : '');
        const arrow = r.net_change > 0 ? '↑' : (r.net_change < 0 ? '↓' : '→');
        return '<tr><td><div class="emp-mini"><div>' + r.emp.full_name + '<br><span class="emp-id-sm">' + r.emp.username + '</span></div></div></td><td class="num-cell">' + r.previous.net + '</td><td class="num-cell">' + r.current.net + '</td><td class="num-cell ' + cls + '">' + arrow + ' ' + r.net_change + '</td><td class="num-cell ' + cls + '">' + (r.net_change >= 0 ? '+' : '') + r.net_change_pct + '%</td></tr>';
      }).join('');
    }).catch(e => console.error('payroll fetch error', e));
}

function loadApprovals() {
  const body = document.getElementById('approvalBody');
  const summary = document.getElementById('approvalSummary');
  if (!body) return;
  body.innerHTML = '<tr><td colspan="8"><div class="skeleton-list"></div></td></tr>';
  fetch(API_BASE + '/api/approvals?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR)
    .then(r => r.json())
    .then(d => {
      if (!d || !d.ok) return;
      summary.innerHTML = '<div class="mini-cards"><div class="mini-card"><span class="mc-label">قيد الانتظار</span><span class="mc-value text-amber">' + d.pending + '</span></div><div class="mini-card"><span class="mc-label">تمت الموافقة</span><span class="mc-value text-green">' + d.approved + '</span></div><div class="mini-card"><span class="mc-label">مرفوض</span><span class="mc-value text-red">' + d.rejected + '</span></div><div class="mini-card"><span class="mc-label">الإجمالي</span><span class="mc-value">' + d.count + '</span></div></div>';
      if (!d.approvals || d.approvals.length === 0) {
        body.innerHTML = '<tr><td colspan="8"><div class="empty-state"><i class="ti ti-check-circle"></i><p>لا توجد طلبات موافقة</p></div></td></tr>';
        return;
      }
      const statusMap = {pending:'🟡 قيد الانتظار',approved:'🟢 تمت الموافقة',rejected:'🔴 مرفوض',changes_requested:'🔵 طلب تعديل'};
      body.innerHTML = d.approvals.map(function(w) {
        const changeCls = w.change_pct > 0 ? 'text-green' : (w.change_pct < 0 ? 'text-red' : '');
        return '<tr><td><div class="emp-mini"><div>' + w.employee_name + '<br><span class="emp-id-sm">' + w.employee_username + '</span></div></div></td><td>' + w.department + '</td><td class="num-cell">' + w.current_gross + '</td><td class="num-cell">' + w.proposed_gross + '</td><td class="num-cell ' + changeCls + '">' + (w.change_pct >= 0 ? '+' : '') + w.change_pct + '%</td><td><span class="status-pill status-' + w.status + '">' + (statusMap[w.status] || w.status) + '</span></td><td>' + w.current_step + '/' + w.total_steps + '</td><td>' + (w.status === 'pending' ? '<button class="btn-icon" onclick="actOnApproval(' + w.id + ',\'approve\')" title="موافقة"><i class="ti ti-check"></i></button><button class="btn-icon" onclick="actOnApproval(' + w.id + ',\'reject\')" title="رفض"><i class="ti ti-x"></i></button>' : '<span class="text-muted">—</span>') + '</td></tr>';
      }).join('');
    }).catch(e => console.error('payroll fetch error', e));
}

function actOnApproval(wid, action) {
  const comment = action === 'reject' ? prompt('سبب الرفض:') : '';
  if (action === 'reject' && comment === null) return;
  fetch(API_BASE + '/api/approvals/' + wid + '/act', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken()},
    body: JSON.stringify({action: action, comment: comment || ''}),
  })
  .then(r => r.json())
  .then(d => { if (!d || !d.ok) return; toast(d.msg, d.ok ? 'ok' : 'err'); if (d.ok) loadApprovals(); }).catch(e => console.error('payroll fetch error', e));
}

function loadBankPayments() {
  const body = document.getElementById('bankBody');
  const summary = document.getElementById('bankSummary');
  if (!body) return;
  body.innerHTML = '<tr><td colspan="8"><div class="skeleton-list"></div></td></tr>';
  fetch(API_BASE + '/api/bank?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR)
    .then(r => r.json())
    .then(d => {
      if (!d || !d.ok) return;
      const sc = d.status_counts || {};
      summary.innerHTML = '<div class="mini-cards"><div class="mini-card"><span class="mc-label">الإجمالي</span><span class="mc-value">' + d.total_amount + ' د.ل</span></div><div class="mini-card"><span class="mc-label">قيد الانتظار</span><span class="mc-value text-amber">' + (sc.pending || 0) + '</span></div><div class="mini-card"><span class="mc-label">مكتمل</span><span class="mc-value text-green">' + (sc.completed || 0) + '</span></div><div class="mini-card"><span class="mc-label">IBAN ناقص</span><span class="mc-value text-red">' + d.missing_iban_count + '</span></div></div>';
      if (!d.payments || d.payments.length === 0) {
        body.innerHTML = '<tr><td colspan="8"><div class="empty-state"><i class="ti ti-building-bank"></i><p>لا توجد مدفوعات بنكية. اضغط "إنشاء قيود الدفع" أولاً.</p></div></td></tr>';
        return;
      }
      const statusMap = {pending:'🟡 قيد الانتظار',processing:'🔵 قيد المعالجة',completed:'🟢 مكتمل',failed:'🔴 فاشل'};
      body.innerHTML = d.payments.map(function(p) {
        return '<tr><td><div class="emp-mini"><span class="emp-avatar-mini">' + p.employee_name[0] + '</span><div><div class="emp-name-sm">' + p.employee_name + '</div><div class="emp-id-sm">' + p.employee_username + '</div></div></div></td><td>' + p.department + '</td><td style="direction:ltr;font-family:monospace;font-size:12px">' + (p.iban || '<span class="text-red">—</span>') + '</td><td>' + (p.bank_name || '—') + '</td><td class="num-cell bold">' + p.net_amount + '</td><td><span class="status-pill status-' + p.status + '">' + (statusMap[p.status] || p.status) + '</span></td><td>' + (p.payment_date || '—') + '</td><td><select onchange="updateBankStatus(' + p.id + ',this.value)" class="btn-sm" style="padding:4px 6px;font-size:11px"><option value="">تغيير</option><option value="pending">قيد الانتظار</option><option value="processing">قيد المعالجة</option><option value="completed">مكتمل</option><option value="failed">فاشل</option></select></td></tr>';
      }).join('');
    }).catch(e => console.error('payroll fetch error', e));
}

function generateBankPayments() {
  fetch(API_BASE + '/api/bank/generate?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR, {method: 'POST', headers: {'X-CSRFToken': csrfToken()}})
    .then(r => r.json())
    .then(d => { if (!d || !d.ok) return; toast(d.msg, d.ok ? 'ok' : 'err'); if (d.ok) loadBankPayments(); }).catch(e => console.error('payroll fetch error', e));
}

function updateBankStatus(id, status) {
  if (!status) return;
  fetch(API_BASE + '/api/bank/update-status', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken()},
    body: JSON.stringify({ids: [id], status: status}),
  })
  .then(r => r.json())
  .then(d => { if (!d || !d.ok) return; toast(d.msg, d.ok ? 'ok' : 'err'); if (d.ok) loadBankPayments(); }).catch(e => console.error('payroll fetch error', e));
}

function exportBankFile(fmt) {
  window.open(API_BASE + '/api/bank/export/' + fmt + '?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR, '_blank');
}

function validateBankIBAN() {
  toast('جاري التحقق من IBAN...', 'info');
  fetch(API_BASE + '/api/bank?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR)
    .then(r => r.json())
    .then(d => {
      if (!d || !d.ok) return;
      if (d.missing_iban_count > 0) {
        toast('يوجد ' + d.missing_iban_count + ' موظف بدون IBAN', 'err');
      } else {
        toast('جميع حسابات IBAN موجودة', 'ok');
      }
    }).catch(e => console.error('payroll fetch error', e));
}

function bulkSaveAll() {
  fetch(API_BASE + '/api/bulk-save?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR, {method: 'POST', headers: {'X-CSRFToken': csrfToken()}})
    .then(r => r.json())
    .then(d => { if (!d || !d.ok) return; toast(d.msg, d.ok ? 'ok' : 'err'); }).catch(e => console.error('payroll fetch error', e));
}

function changePerPage(sel) {
  const params = new URLSearchParams(window.location.search);
  params.set('per_page', sel.value);
  window.location.search = params.toString();
}

function toast(msg, type) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const t = document.createElement('div');
  t.className = 'toast ' + (type || 'info');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; setTimeout(() => t.remove(), 300); }, 3000);
}

document.addEventListener('DOMContentLoaded', function() {
  const activeTab = document.querySelector('.payroll-tab.active');
  if (activeTab) switchPayrollTab(parseInt(activeTab.dataset.tab), activeTab);
});
