const API_BASE = '/admin/reports';
let allRows = [];
let filteredRows = [];
let currentPage = 1;
const PAGE_SIZE = 50;
let charts = {};
let debounceTimer = null;
function esc(s) { if(!s) return ''; return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function api(url, opts = {}) {
  const csrf = document.querySelector('meta[name="csrf-token"]');
  const headers = { 'Content-Type': 'application/json', 'X-CSRFToken': csrf ? csrf.content : '' };
  return fetch(API_BASE + url, { headers, credentials: 'same-origin', ...opts })
    .then(r => r.json()).catch(() => ({ error: true }));
}

function applyFilters() {
  const dept = document.getElementById('filterDept').value;
  const shift = document.getElementById('filterShift').value;
  const empType = document.getElementById('filterEmployment').value;
  const month = document.getElementById('filterMonth').value;
  const year = document.getElementById('filterYear').value;
  const showPresent = document.getElementById('showPresent').checked;
  const showAbsent = document.getElementById('showAbsent').checked;
  const showLate = document.getElementById('showLate').checked;
  const showLeave = document.getElementById('showLeave').checked;
  const showDeductions = document.getElementById('showDeductions').checked;
  const showExcessAbsence = document.getElementById('showExcessAbsence').checked;

  api(`/data?dept=${dept}&shift=${shift}&employment_type=${empType}&year=${year}&month=${month}&show_present=${showPresent}&show_absent=${showAbsent}&show_late=${showLate}&leave_only=${showLeave}&deductions_only=${showDeductions}&excess_absence=${showExcessAbsence}`)
    .then(data => {
      if (data.error) return;
      allRows = data.rows || [];
      filteredRows = [...allRows];
      currentPage = 1;
      renderTable();
      renderSummary(data.summary);
    });
}

function renderSummary(s) {
  if (!s) return;
  animateNum('sTotal', s.total_employees);
  animateNum('sPresent', s.total_present);
  document.getElementById('sRate').textContent = (s.overall_pct || 0) + '%';
  animateNum('sLate', s.total_late_minutes);
  animateNum('sAbsent', s.total_absent);
  animateNum('sDeductions', s.total_deductions);
}

function animateNum(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const start = parseInt(el.textContent.replace(/,/g,'')) || 0;
  const duration = 600;
  const startTime = performance.now();
  function step(now) {
    const pct = Math.min((now - startTime) / duration, 1);
    const val = Math.floor(start + (target - start) * pct);
    el.textContent = val.toLocaleString();
    if (pct < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function renderTable() {
  const tbody = document.getElementById('tableBody');
  const start = 0;
  const end = currentPage * PAGE_SIZE;
  const pageRows = filteredRows.slice(start, end);
  const loadMoreBtn = document.getElementById('loadMoreBtn');

  if (pageRows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="18" class="text-center text-muted">لا توجد بيانات</td></tr>';
    loadMoreBtn.style.display = 'none';
    document.getElementById('rowCount').textContent = '0 موظف';
    return;
  }

  document.getElementById('rowCount').textContent = `${filteredRows.length} موظف`;
  loadMoreBtn.style.display = end >= filteredRows.length ? 'none' : 'block';

  let html = '';
  pageRows.forEach((r, i) => {
    const statusColor = r.overall_status === 'excellent' ? '#22c55e' : r.overall_status === 'good' ? '#3b82f6' : r.overall_status === 'acceptable' ? '#f59e0b' : '#ef4444';
    const statusLabel = r.overall_status === 'excellent' ? 'ممتاز' : r.overall_status === 'good' ? 'جيد' : r.overall_status === 'acceptable' ? 'مقبول' : 'ضعيف';
    const hasAnomaly = r.anomaly_count > 0 ? `<span class="badge badge-danger" title="تجاوز">!${r.anomaly_count}</span>` : '';
    html += `<tr>
      <td>${start + i + 1}</td>
      <td><strong>${r.emp_name}</strong><br><small class="text-muted">${r.emp_code}</small></td>
      <td>${r.department}</td>
      <td>${r.shift || '-'}</td>
      <td>${r.expected_days}</td>
      <td class="text-success">${r.present}</td>
      <td class="text-danger">${r.absent}</td>
      <td class="text-warning">${r.late_count}</td>
      <td>${r.late_minutes}</td>
      <td>${r.leave}</td>
      <td>${r.work_hours}</td>
      <td>${r.overtime}</td>
      <td class="text-danger">${r.total_deduction}</td>
      <td>${r.base_salary}</td>
      <td style="font-weight:700;color:${statusColor}">${r.net_salary}</td>
      <td>${r.attendance_pct}%</td>
      <td><span class="status-badge" style="background:${statusColor}20;color:${statusColor};border:1px solid ${statusColor}40">${statusLabel}</span></td>
      <td><button class="btn btn-sm btn-outline" onclick="showDetail(${r.employee_id},'${r.emp_name}')"><i class="fas fa-eye"></i></button></td>
    </tr>`;
  });
  tbody.innerHTML = html;
}

function loadMoreRows() {
  currentPage++;
  renderTable();
}

function debounceSearch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    const q = document.getElementById('searchInput').value.trim().toLowerCase();
    if (!q) { filteredRows = [...allRows]; }
    else {
      filteredRows = allRows.filter(r =>
        r.emp_name.toLowerCase().includes(q) ||
        r.emp_code.toLowerCase().includes(q) ||
        (r.department && r.department.toLowerCase().includes(q))
      );
    }
    currentPage = 1;
    renderTable();
  }, 300);
}

// ---- TAB SWITCHING ----
document.querySelectorAll('#reportTabs .nav-link').forEach(tab => {
  tab.addEventListener('click', function(e) {
    e.preventDefault();
    document.querySelectorAll('#reportTabs .nav-link').forEach(t => t.classList.remove('active'));
    this.classList.add('active');
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.getElementById('tab-' + this.dataset.tab).classList.add('active');
    if (this.dataset.tab === 'charts') loadCharts();
    if (this.dataset.tab === 'corrections') loadCorrections();
    if (this.dataset.tab === 'comparison') initComparison();
    if (this.dataset.tab === 'schedule') loadScheduled();
  });
});

// ---- CHARTS ----
function loadCharts() {
  const month = document.getElementById('filterMonth').value;
  const year = document.getElementById('filterYear').value;
  api(`/charts?year=${year}&month=${month}`).then(data => {
    if (data.error) return;
    renderDailyTrend(data.daily_trend || []);
    renderDeptCompare(data.dept_comparison || []);
    renderLateDist(data.late_distribution || []);
    renderReportHeatmap(data.heatmap || []);
    renderDeductionsChart(data.deductions_breakdown || { labels: [], values: [] });
  });
}

function renderDailyTrend(data) {
  if (charts.dailyTrend) charts.dailyTrend.destroy();
  const ctx = document.getElementById('dailyTrendChart');
  if (!ctx) return;
  if (!data.length) { ctx.parentElement.innerHTML = '<p class="text-muted text-center">لا توجد بيانات</p>'; return; }
  const labels = data.map(d => d.day);
  const present = data.map(d => d.present);
  const absent = data.map(d => d.absent);
  const late = data.map(d => d.late);
  charts.dailyTrend = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'حضور', data: present, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', fill: true, tension: 0.4, pointRadius: 3 },
        { label: 'غياب', data: absent, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', fill: true, tension: 0.4, pointRadius: 3 },
        { label: 'تأخير', data: late, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.1)', fill: true, tension: 0.4, pointRadius: 3 },
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top', labels: { font: { size: 11 } } } },
      scales: { y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
               x: { grid: { display: false } } } }
  });
}

function renderDeptCompare(data) {
  if (charts.deptCompare) charts.deptCompare.destroy();
  const ctx = document.getElementById('deptCompareChart');
  if (!ctx) return;
  if (!data.length) { ctx.parentElement.innerHTML = '<p class="text-muted text-center">لا توجد بيانات</p>'; return; }
  const labels = data.map(d => d.dept);
  const rate = data.map(d => d.rate);
  charts.deptCompare = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label: 'معدل الحضور %', data: rate, backgroundColor: rate.map(v => v >= 90 ? 'rgba(34,197,94,0.7)' : v >= 75 ? 'rgba(245,158,11,0.7)' : 'rgba(239,68,68,0.7)'), borderRadius: 4 }] },
    options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, max: 100, grid: { color: 'rgba(0,0,0,0.05)' } },
               y: { grid: { display: false } } } }
  });
}

function renderLateDist(data) {
  if (charts.lateDist) charts.lateDist.destroy();
  const ctx = document.getElementById('lateDistChart');
  if (!ctx) return;
  if (!data.length) { ctx.parentElement.innerHTML = '<p class="text-muted text-center">لا توجد بيانات</p>'; return; }
  const labels = data.map(d => d.range);
  const values = data.map(d => d.count);
  charts.lateDist = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label: 'عدد الموظفين', data: values, backgroundColor: 'rgba(245,158,11,0.7)', borderRadius: 4 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
               x: { grid: { display: false } } } }
  });
}

function renderReportHeatmap(data) {
  if (charts.reportHeatmap) charts.reportHeatmap.destroy();
  const ctx = document.getElementById('reportHeatmap');
  if (!ctx) return;
  if (!data.length || !data[0].days) { ctx.parentElement.innerHTML = '<p class="text-muted text-center">لا توجد بيانات</p>'; return; }
  const labels = data.map(d => d.dept);
  const days = data[0].days.map((_, i) => `يوم ${i + 1}`);
  const values = data.map(d => d.days);
  const colors = ['#fef2f2','#fee2e2','#fecaca','#fca5a5','#f87171','#ef4444','#dc2626','#b91c1c'];
  const bgColors = values.flatMap(row => row.map(v => {
    const idx = Math.min(Math.floor(v / 15), colors.length - 1);
    return colors[Math.max(0, idx)];
  }));
  charts.reportHeatmap = new Chart(ctx, {
    type: 'matrix',
    data: {
      labels,
      datasets: [{
        label: 'معدل الحضور',
        data: values.flatMap((row, i) => row.map((v, j) => ({ x: j, y: i, v }))),
        backgroundColor: bgColors,
        width: ({ chart }) => (chart.chartArea.width / days.length - 4),
        height: ({ chart }) => (chart.chartArea.height / labels.length - 4),
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { title: ctx => `${labels[ctx[0].raw.y]} - ${days[ctx[0].raw.x]}`, label: ctx => `الحضور: ${ctx.raw.v}%` } }
      },
      scales: {
        x: { type: 'category', labels: days, grid: { display: false }, ticks: { font: { size: 9 } } },
        y: { type: 'category', labels: labels, grid: { display: false }, ticks: { font: { size: 9 } } }
      }
    }
  });
}

function renderDeductionsChart(data) {
  if (charts.deductions) charts.deductions.destroy();
  const ctx = document.getElementById('deductionsChart');
  if (!ctx) return;
  if (!data.labels || !data.labels.length) { ctx.parentElement.innerHTML = '<p class="text-muted text-center">لا توجد بيانات</p>'; return; }
  charts.deductions = new Chart(ctx, {
    type: 'doughnut',
    data: { labels: data.labels, datasets: [{ data: data.values, backgroundColor: ['#ef4444','#f59e0b','#3b82f6','#8b5cf6','#22c55e'], borderWidth: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '60%',
      plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } } }
  });
}

// ---- CORRECTIONS ----
function loadCorrections() {
  api('/corrections').then(data => {
    const tbody = document.getElementById('correctionsBody');
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">لا توجد طلبات</td></tr>'; return; }
    let html = '';
    data.forEach((c, i) => {
      const statusClass = c.status === 'approved' ? 'text-success' : c.status === 'rejected' ? 'text-danger' : 'text-warning';
      const statusLabel = c.status === 'approved' ? 'مقبول' : c.status === 'rejected' ? 'مرفوض' : 'قيد المراجعة';
      const actions = c.status === 'pending' ? `<button class="btn btn-sm btn-success" onclick="reviewCorrection(${c.id},'approved')"><i class="fas fa-check"></i></button>
        <button class="btn btn-sm btn-danger" onclick="reviewCorrection(${c.id},'rejected')"><i class="fas fa-times"></i></button>` : '-';
      html += `<tr>
        <td>${i+1}</td><td>${c.employee_name}</td><td>${c.log_date}</td><td>${c.correction_type}</td><td>${c.reason}</td>
        <td class="${statusClass}">${statusLabel}</td><td>${c.created_at}</td><td>${actions}</td>
      </tr>`;
    });
    tbody.innerHTML = html;
  });
}

function showCorrectionModal() {
  document.getElementById('correctionId').value = '';
  document.getElementById('corrReason').value = '';
  document.getElementById('corrDate').value = new Date().toISOString().slice(0,10);
  api('/employees').then(data => {
    const sel = document.getElementById('corrEmployee');
    sel.innerHTML = '<option value="">اختر موظف</option>' + data.map(e => `<option value="${e.id}">${esc(e.name)} (${esc(e.code)})</option>`).join('');
  });
  $('#correctionModal').modal('show');
}

function saveCorrection() {
  const data = {
    employee_id: document.getElementById('corrEmployee').value,
    log_date: document.getElementById('corrDate').value,
    correction_type: document.getElementById('corrType').value,
    reason: document.getElementById('corrReason').value,
  };
  api('/corrections', { method: 'POST', body: JSON.stringify(data) }).then(r => {
    if (r.error) { alert('فشل الحفظ'); return; }
    $('#correctionModal').modal('hide');
    loadCorrections();
  });
}

function reviewCorrection(id, status) {
  api(`/corrections/${id}/review`, { method: 'POST', body: JSON.stringify({ status }) }).then(() => loadCorrections());
}

// ---- COMPARISON ----
function initComparison() {
  api('/employees').then(data => {
    const sel = document.getElementById('compareEmployees');
    if (sel.dataset.initialized) return;
    sel.dataset.initialized = '1';
    data.forEach(e => {
      const opt = document.createElement('option');
      opt.value = e.id;
      opt.textContent = `${e.name} (${e.code})`;
      sel.appendChild(opt);
    });
    if (window.$(sel)) window.$(sel).select2({ placeholder: 'اختر موظفين...', width: '100%' });
  });
}

function loadComparison() {
  const sel = document.getElementById('compareEmployees');
  const ids = Array.from(sel.selectedOptions).map(o => o.value);
  if (ids.length < 2) { alert('اختر موظفين على الأقل'); return; }
  api(`/comparison?ids=${ids.join(',')}`).then(data => {
    const div = document.getElementById('comparisonResults');
    if (!data.length) { div.innerHTML = '<p class="text-muted">لا توجد بيانات</p>'; return; }
    let html = '<div class="comparison-table-wrapper"><table class="table reports-table"><thead><tr><th>المعيار</th>';
    data.forEach(e => { html += `<th>${e.name}</th>`; });
    html += '</tr></thead><tbody>';
    const metrics = [
      { key: 'present', label: 'حضور' }, { key: 'absent', label: 'غياب' },
      { key: 'late_count', label: 'تأخير' }, { key: 'late_minutes', label: 'دقائق تأخير' },
      { key: 'leave', label: 'إجازات' }, { key: 'work_hours', label: 'ساعات عمل' },
      { key: 'overtime', label: 'إضافي' }, { key: 'total_deduction', label: 'الخصم' },
      { key: 'net_salary', label: 'الصافي' }, { key: 'attendance_pct', label: 'النسبة %' },
    ];
    metrics.forEach(m => {
      html += `<tr><td><strong>${m.label}</strong></td>`;
      data.forEach(e => { html += `<td>${e[m.key]}</td>`; });
      html += '</tr>';
    });
    html += '</tbody></table></div>';

    // Comparison chart
    html += '<div class="chart-card"><h4>مقارنة بيانية</h4><div class="chart-container" style="height:300px"><canvas id="compareChart"></canvas></div></div>';
    div.innerHTML = html;

    if (charts.compare) charts.compare.destroy();
    const ctx = document.getElementById('compareChart');
    if (ctx) {
      const labels = metrics.filter(m => m.key !== 'attendance_pct').map(m => m.label);
      const datasets = data.map((e, idx) => ({
        label: e.name,
        data: labels.map((_, li) => {
          const k = metrics.filter(m => m.key !== 'attendance_pct')[li].key;
          return parseFloat(e[k]) || 0;
        }),
        backgroundColor: ['rgba(34,197,94,0.7)', 'rgba(239,68,68,0.7)', 'rgba(59,130,246,0.7)', 'rgba(245,158,11,0.7)'][idx % 4],
        borderRadius: 4,
      }));
      charts.compare = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top', labels: { font: { size: 11 } } } },
          scales: { y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
                   x: { grid: { display: false } } } }
      });
    }
  });
}

// ---- SCHEDULED REPORTS ----
function loadScheduled() {
  api('/scheduled').then(data => {
    const tbody = document.getElementById('scheduledBody');
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">لا توجد تقارير مجدولة</td></tr>'; return; }
    let html = '';
    data.forEach((s, i) => {
      const active = s.is_active ? '<span class="status-badge" style="background:#22c55e20;color:#22c55e">نشط</span>' : '<span class="status-badge" style="background:#6b728020;color:#6b7280">متوقف</span>';
      html += `<tr>
        <td>${i+1}</td><td>${s.frequency}</td><td>${s.format}</td><td>${s.created_at}</td><td>${s.last_run || '-'}</td><td>${s.next_run || '-'}</td>
        <td>${active}</td>
        <td>
          <button class="btn btn-sm btn-outline" onclick="toggleScheduled(${s.id})"><i class="fas ${s.is_active ? 'fa-pause' : 'fa-play'}"></i></button>
          <button class="btn btn-sm btn-outline" onclick="runScheduledNow(${s.id})"><i class="fas fa-play"></i></button>
          <button class="btn btn-sm btn-outline text-danger" onclick="deleteScheduled(${s.id})"><i class="fas fa-trash"></i></button>
        </td>
      </tr>`;
    });
    tbody.innerHTML = html;
  });
}

function createScheduledReport() {
  const data = {
    frequency: document.getElementById('scheduleFreq').value,
    format: document.getElementById('scheduleFormat').value,
  };
  api('/scheduled', { method: 'POST', body: JSON.stringify(data) }).then(r => {
    if (r.error) { alert('فشل الجدولة'); return; }
    loadScheduled();
  });
}

function toggleScheduled(id) {
  api(`/scheduled/${id}/toggle`, { method: 'POST' }).then(() => loadScheduled());
}

function runScheduledNow(id) {
  api(`/scheduled/${id}/run`, { method: 'POST' }).then(() => loadScheduled());
}

function deleteScheduled(id) {
  if (!confirm('حذف التقرير المجدول؟')) return;
  api(`/scheduled/${id}`, { method: 'DELETE' }).then(() => loadScheduled());
}

// ---- EXPORT ----
function exportPDF() {
  const month = document.getElementById('filterMonth').value;
  const year = document.getElementById('filterYear').value;
  window.open(`${API_BASE}/export/pdf?year=${year}&month=${month}`, '_blank');
}
function exportExcel() {
  const month = document.getElementById('filterMonth').value;
  const year = document.getElementById('filterYear').value;
  window.open(`${API_BASE}/export/excel?year=${year}&month=${month}`, '_blank');
}
function exportWhatsApp() {
  const month = document.getElementById('filterMonth').value;
  const year = document.getElementById('filterYear').value;
  api(`/export-whatsapp?year=${year}&month=${month}`).then(r => {
    if (r.text) {
      const w = window.open('https://wa.me/?text=' + encodeURIComponent(r.text), '_blank');
      if (!w) alert('الرجاء فتح واتساب وإرسال الرسالة');
    }
  });
}

// ---- DETAIL ----
function showDetail(employeeId, name) {
  const month = document.getElementById('filterMonth').value;
  const year = document.getElementById('filterYear').value;
  api(`/data?employee_id=${employeeId}&year=${year}&month=${month}`).then(data => {
    const r = data.rows && data.rows[0];
    if (!r) { document.getElementById('detailBody').innerHTML = '<p class="text-muted">لا توجد تفاصيل</p>'; $('#detailModal').modal('show'); return; }
    let html = `
      <div class="detail-header"><h4>${r.emp_name}</h4><p class="text-muted">${r.emp_code} — ${r.department}</p></div>
      <div class="detail-grid">
        <div class="detail-item"><label>أيام العمل</label><span>${r.expected_days}</span></div>
        <div class="detail-item"><label>حضور</label><span class="text-success">${r.present}</span></div>
        <div class="detail-item"><label>غياب</label><span class="text-danger">${r.absent}</span></div>
        <div class="detail-item"><label>تأخير</label><span class="text-warning">${r.late_count}</span></div>
        <div class="detail-item"><label>دقائق تأخير</label><span>${r.late_minutes}</span></div>
        <div class="detail-item"><label>إجازات</label><span>${r.leave}</span></div>
        <div class="detail-item"><label>ساعات عمل</label><span>${r.work_hours}</span></div>
        <div class="detail-item"><label>إضافي</label><span>${r.overtime}</span></div>
        <div class="detail-item"><label>الخصم</label><span class="text-danger">${r.total_deduction}</span></div>
        <div class="detail-item"><label>الراتب الأساسي</label><span>${r.base_salary}</span></div>
        <div class="detail-item"><label>الصافي</label><span style="font-weight:700">${r.net_salary}</span></div>
        <div class="detail-item"><label>النسبة</label><span>${r.attendance_pct}%</span></div>
      </div>
      <div class="detail-days"><h5>تفاصيل الأيام</h5><div class="days-grid">`;
    if (r.days) {
      r.days.forEach(d => {
        const cls = d.status === 'present' ? 'day-present' : d.status === 'absent' ? 'day-absent' : d.status === 'late' ? 'day-late' : d.status === 'leave' ? 'day-leave' : 'day-none';
        html += `<div class="day-cell ${cls}" title="${d.date}: ${d.status}">${new Date(d.date).getDate()}</div>`;
      });
    }
    html += `</div></div>`;
    document.getElementById('detailBody').innerHTML = html;
    $('#detailModal').modal('show');
  });
}

// ---- REFRESH ----
function refreshData() {
  applyFilters();
  const activeTab = document.querySelector('#reportTabs .nav-link.active');
  if (activeTab) {
    if (activeTab.dataset.tab === 'charts') loadCharts();
    if (activeTab.dataset.tab === 'corrections') loadCorrections();
    if (activeTab.dataset.tab === 'schedule') loadScheduled();
  }
}

// ---- INIT ----
document.addEventListener('DOMContentLoaded', () => {
  applyFilters();
});
