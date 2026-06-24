function csrfToken() {
  var m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}

function exportPayroll(type) {
  document.getElementById('payrollExportMenu').style.display = 'none';
  const params = new URLSearchParams({month: CURRENT_MONTH, year: CURRENT_YEAR});
  if (CURRENT_DEPT) params.set('dept', CURRENT_DEPT);
  if (type === 'csv') {
    window.open(API_BASE + '/api/export/csv?' + params.toString(), '_blank');
    toast('جاري تصدير CSV...', 'info');
  } else if (type === 'excel') {
    toast('ميزة Excel قيد التطوير، تم تصدير CSV', 'info');
    window.open(API_BASE + '/api/export/csv?' + params.toString(), '_blank');
  } else if (type === 'pdf') {
    toast('ميزة PDF قيد التطوير', 'info');
  }
}

function exportIndividualPayslipPDF(empId) {
  window.open(API_BASE + '/api/payslip/' + empId + '/print?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR, '_blank');
}

function emailPayslip(empId) {
  fetch(API_BASE + '/api/employee/' + empId + '?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR)
    .then(r => r.json())
    .then(d => {
      const subject = encodeURIComponent('كشف الراتب الشهري - ' + d.emp.full_name);
      const body = encodeURIComponent(
        'السلام عليكم\n\n' +
        'كشف الراتب الخاص بك عن شهر ' + d.month_name + ' ' + d.year + '\n\n' +
        'الراتب الأساسي: ' + d.comp.base + ' د.ل\n' +
        'الإضافات: ' + d.comp.total_allowances + ' د.ل\n' +
        'العمل الإضافي: ' + d.comp.overtime_pay + ' د.ل\n' +
        'إجمالي الراتب: ' + d.comp.gross + ' د.ل\n' +
        'الخصومات: ' + d.comp.total_deductions + ' د.ل\n' +
        'الضرائب: ' + d.comp.total_tax + ' د.ل\n' +
        'صافي الراتب: ' + d.comp.net + ' د.ل\n\n' +
        'للاستفسار، يرجى التواصل مع إدارة الموارد البشرية.\n' +
        'منظمة صحة الدم - طبرق'
      );
      window.open('mailto:' + d.emp.email + '?subject=' + subject + '&body=' + body, '_blank');
    });
}

function whatsappPayslip(empId) {
  fetch(API_BASE + '/api/employee/' + empId + '?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR)
    .then(r => r.json())
    .then(d => {
      const msg = encodeURIComponent(
        '🧾 *كشف الراتب - ' + d.month_name + ' ' + d.year + '*\n' +
        '👤 ' + d.emp.full_name + '\n' +
        '💰 الأساسي: ' + d.comp.base + ' د.ل\n' +
        '➕ الإضافات: ' + d.comp.total_allowances + ' د.ل\n' +
        '➖ الخصومات: ' + d.comp.total_deductions + ' د.ل\n' +
        '💵 *الصافي: ' + d.comp.net + ' د.ل*\n' +
        'منظمة صحة الدم - طبرق'
      );
      window.open('https://wa.me/218' + d.emp.phone + '?text=' + msg, '_blank');
    });
}

function downloadPayslipPDF(empId) {
  exportIndividualPayslipPDF(empId);
}

function archivePayslip(empId) {
  fetch(API_BASE + '/api/save-record', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken()},
    body: JSON.stringify({employee_id: empId, month: CURRENT_MONTH, year: CURRENT_YEAR}),
  })
  .then(r => r.json())
  .then(d => toast(d.msg, d.ok ? 'ok' : 'err'));
}

function printPayrollTable() {
  window.print();
}

function exportPayrollJSON() {
  fetch(API_BASE + '?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR, {
    headers: {'X-Requested-With': 'XMLHttpRequest'}
  })
  .then(r => r.json())
  .then(d => {
    const blob = new Blob([JSON.stringify(d, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'payroll_' + CURRENT_MONTH + '_' + CURRENT_YEAR + '.json';
    a.click();
    URL.revokeObjectURL(url);
    toast('تم تصدير JSON', 'ok');
  });
}
