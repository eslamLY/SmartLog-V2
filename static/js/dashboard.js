function safeApiCall(url, opts) {
  opts = opts || {};
  return fetch(url, opts).then(function(r) {
    if (!r.ok) { console.warn('API %s returned %d', url, r.status); return null; }
    return r.json().catch(function() { return null; });
  }).then(function(d) {
    if (!d) return null;
    if (d.ok === false) { console.warn('API %s error: %s', url, d.msg || 'unknown'); return null; }
    return d;
  }).catch(function(err) {
    console.error('API %s exception: %s', url, err.message || err);
    return null;
  });
}

let charts = {};
let refreshInterval = null;
let lastUpdateTime = Date.now();
let currentPage = 1;
let hasMoreRecords = false;
let mapInstance = null;
let mapMarkers = [];
let dismissedAlerts = JSON.parse(localStorage.getItem('dismissedAlerts') || '[]');
let isDark = localStorage.getItem('theme') !== 'light';

document.addEventListener('DOMContentLoaded', function() {
  applyTheme();
  startLiveClock();
  loadStats();
  loadCharts();
  loadRecords();
  loadAlerts();
  loadSchedule();
  loadMap();
  loadNotifications();
  loadFilters();
  refreshInterval = setInterval(autoRefresh, 60000);
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.notif-bell')) closeNotifDropdown();
    if (!e.target.closest('.admin-profile')) closeProfileDropdown();
    if (!e.target.closest('.search-bar')) closeSearchResults();
  });
  window.addEventListener('scroll', function() {
    document.getElementById('scrollTopBtn').classList.toggle('visible', window.scrollY > 400);
  });
});

function toggleTheme() {
  isDark = !isDark;
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
  applyTheme();
  recreateCharts();
}

function applyTheme() {
  document.body.className = isDark ? 'dark-mode' : 'light-mode';
  const btn = document.getElementById('themeToggle');
  if (btn) btn.innerHTML = isDark ? '<i class="ti ti-sun"></i>' : '<i class="ti ti-moon"></i>';
}

function changeFontSize(delta) {
  const html = document.documentElement;
  let current = parseFloat(getComputedStyle(html).fontSize);
  let size = 14;
  if (delta < 0) size = Math.max(12, current - 1);
  else if (delta > 0) size = Math.min(18, current + 1);
  else size = 14;
  html.style.fontSize = size + 'px';
  localStorage.setItem('fontSize', size);
}

(function() {
  const saved = localStorage.getItem('fontSize');
  if (saved) document.documentElement.style.fontSize = saved + 'px';
})();

function startLiveClock() {
  function update() {
    const now = new Date();
    document.getElementById('liveClock').textContent = now.toLocaleTimeString('ar-SA', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
  }
  update();
  setInterval(update, 1000);
}

function toggleSidebar() {
  document.querySelector('.sidebar').classList.toggle('open');
}

function toggleNotifDropdown() {
  document.getElementById('notifDropdown').classList.toggle('show');
  closeProfileDropdown();
}

function closeNotifDropdown() {
  document.getElementById('notifDropdown').classList.remove('show');
}

function toggleProfileDropdown() {
  document.getElementById('profileDropdown').classList.toggle('show');
  closeNotifDropdown();
}

function closeProfileDropdown() {
  document.getElementById('profileDropdown').classList.remove('show');
}

function closeSearchResults() {
  document.getElementById('searchResults').style.display = 'none';
}

function animateNumber(el, target) {
  const current = parseInt(el.textContent) || 0;
  if (current === target) return;
  const diff = target - current;
  const duration = 600;
  const steps = 20;
  const stepVal = diff / steps;
  let step = 0;
  const timer = setInterval(() => {
    step++;
    const val = Math.round(current + stepVal * step);
    el.textContent = val;
    if (step >= steps) {
      el.textContent = target;
      clearInterval(timer);
    }
  }, duration / steps);
}

function loadStats() {
  safeApiCall('/api/dashboard/stats').then(function(d) {
    if (!d) { document.getElementById('lastUpdateLabel').textContent = 'فشل التحديث'; return; }
    animateNumber(document.getElementById('statTotal'), d.total);
    animateNumber(document.getElementById('statPresent'), d.present);
    animateNumber(document.getElementById('statLate'), d.late);
    animateNumber(document.getElementById('statAbsent'), d.absent);
    animateNumber(document.getElementById('statOnLeave'), d.on_leave || 0);
    animateNumber(document.getElementById('statNoClockout'), d.no_clockout || 0);
    animateNumber(document.getElementById('statExpiring'), d.expiring_docs || 0);
    animateNumber(document.getElementById('statOffline'), d.offline_devices || 0);
    var pe = document.getElementById('statPendingLeaves');
    if (pe) { animateNumber(pe, d.pending_leave_requests || 0); }
    var ep = document.getElementById('statEligiblePromo');
    if (ep) { ep.textContent = d.total || '0'; ep.style.fontSize = '22px'; }
    var ex = document.getElementById('statExtendedPct');
    if (ex) { ex.textContent = (d.extended_data_pct || 0) + '%'; ex.style.fontSize = '22px'; }
    var trends = d.trends || {};
    renderTrend('trendPresent', trends.present);
    renderTrend('trendLate', trends.late);
    renderTrend('trendAbsent', trends.absent);
    var card = document.getElementById('offlineCard');
    if (d.offline_devices > 0) card.classList.add('pulse-active');
    else card.classList.remove('pulse-active');
    var now = new Date();
    var secs = Math.floor((now - lastUpdateTime) / 1000);
    document.getElementById('lastUpdateLabel').textContent = 'آخر تحديث: منذ ' + (secs < 60 ? secs + ' ثانية' : Math.floor(secs/60) + ' دقيقة');
    lastUpdateTime = now;
  });
}

function renderTrend(elId, val) {
  const el = document.getElementById(elId);
  if (!el) return;
  if (val === undefined || val === null) { el.textContent = ''; return; }
  const arrow = val > 0 ? '↑' : val < 0 ? '↓' : '→';
  const color = val > 0 ? 'var(--green)' : val < 0 ? 'var(--red)' : 'var(--muted)';
  el.innerHTML = `<span style="color:${color}">${arrow} ${Math.abs(val)} عن أمس</span>`;
}

function manualRefresh() {
  document.getElementById('refreshOverlay').style.display = 'flex';
  loadStats();
  loadCharts();
  loadRecords();
  loadAlerts();
  loadSchedule();
  setTimeout(() => document.getElementById('refreshOverlay').style.display = 'none', 500);
}

function autoRefresh() {
  loadStats();
  loadCharts();
  loadAlerts();
}

function getChartColors() {
  const style = getComputedStyle(document.body);
  const isD = document.body.classList.contains('dark-mode');
  return {
    text: style.getPropertyValue('--text').trim() || (isD ? 'rgba(255,255,255,0.7)' : '#1a2035'),
    grid: style.getPropertyValue('--border').trim() || (isD ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'),
    green: '#22c55e',
    red: '#ef4444',
    orange: '#f59e0b',
    blue: '#3b82f6',
    purple: '#8b5cf6',
    grey: '#9ca3af',
  };
}

function loadCharts() {
  loadWeeklyChart();
  loadDonutChart();
  loadHeatmap();
  loadPunctuality();
  loadHourly();
}

function recreateCharts() {
  Object.keys(charts).forEach(k => { if (charts[k]) { charts[k].destroy(); delete charts[k]; } });
  loadCharts();
}

let chartMode = 'weekly';

function switchChartMode(btn, mode) {
  chartMode = mode;
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  loadWeeklyChart();
}

function loadWeeklyChart() {
  safeApiCall('/api/dashboard/charts/weekly?mode=' + chartMode).then(function(d) {
    if (!d || !d.data) return;
    if (charts.weekly) { charts.weekly.destroy(); }
    var cc = getChartColors();
    var ctx = document.getElementById('weeklyChart').getContext('2d');
    charts.weekly = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: d.data.map(x => x.day),
        datasets: [
          { label: 'حاضر', data: d.data.map(x => x.present), backgroundColor: cc.green + '80', borderRadius: 3, barPercentage: 0.6 },
          { label: 'غائب', data: d.data.map(x => x.absent), backgroundColor: cc.red + '60', borderRadius: 3, barPercentage: 0.6 },
          { label: 'متأخر', data: d.data.map(x => x.late), backgroundColor: cc.orange + '70', borderRadius: 3, barPercentage: 0.6 },
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: cc.text, font: { family: 'Cairo', size: 11 }, boxWidth: 12, padding: 8 } },
          tooltip: {
            callbacks: {
              label: function(ctx) {
                const labels = ['حاضر', 'غائب', 'متأخر'];
                return labels[ctx.datasetIndex] + ': ' + ctx.raw;
              }
            }
          }
        },
        scales: {
          x: { stacked: true, ticks: { color: cc.text, font: { family: 'Cairo' } }, grid: { color: cc.grid } },
          y: { stacked: true, ticks: { color: cc.text, font: { family: 'Cairo' } }, grid: { color: cc.grid } }
        }
      }
    });
  });
}

function loadDonutChart() {
  safeApiCall('/api/dashboard/charts/donut').then(function(d) {
    if (!d || !d.labels) return;
    if (charts.donut) { charts.donut.destroy(); }
    var cc = getChartColors();
    var ctx = document.getElementById('donutChart').getContext('2d');
    document.getElementById('donutCenter').textContent = d.total;
    charts.donut = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: d.labels,
        datasets: [{ data: d.values, backgroundColor: d.colors, borderWidth: 0 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        cutout: '75%',
        plugins: {
          legend: { display: false },
        }
      }
    });
    const legend = document.getElementById('donutLegend');
    legend.innerHTML = '';
    d.labels.forEach((label, i) => {
      legend.innerHTML += `<div class="donut-legend-item"><span class="donut-dot" style="background:${d.colors[i]}"></span><span>${label}</span><span class="donut-val">${d.values[i]}</span></div>`;
    });
  });
}

function loadHeatmap() {
  safeApiCall('/api/dashboard/charts/heatmap').then(function(d) {
    if (!d) return;
    const container = document.getElementById('heatmapContainer');
    if (!d.rows || !d.rows.length) {
      container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--muted)">لا توجد بيانات كافية</div>';
      return;
    }
    let html = '<div class="heatmap-table"><div class="heatmap-header"><div class="heatmap-dept-header">القسم</div>';
    d.day_labels.forEach(label => { html += `<div class="heatmap-day-header">${label.slice(0,2)}</div>`; });
    html += '<div class="heatmap-day-header">%</div></div>';
    d.rows.forEach(row => {
      html += `<div class="heatmap-row"><div class="heatmap-dept-name" style="color:${row.dept_color}">${row.dept_name}</div>`;
      row.cells.forEach(cell => {
        const intensity = cell.pct;
        const color = intensity >= 80 ? '#22c55e' : intensity >= 60 ? '#84cc16' : intensity >= 40 ? '#f59e0b' : intensity >= 20 ? '#f97316' : '#ef4444';
        html += `<div class="heatmap-cell" style="background:${color}${Math.round(50 + intensity/2).toString(16).padStart(2,'0')}" title="${row.dept_name}: ${cell.count}/${cell.total} (${cell.pct}%)"></div>`;
      });
      html += `<div class="heatmap-pct" style="color:${row.today_pct >= 80 ? '#22c55e' : row.today_pct >= 50 ? '#f59e0b' : '#ef4444'}">${row.today_pct}%</div></div>`;
    });
    html += '</div>';
    container.innerHTML = html;
  });
}

function loadPunctuality() {
  safeApiCall('/api/dashboard/charts/punctuality').then(function(d) {
    if (!d || !d.ranking) return;
    if (charts.punctuality) { charts.punctuality.destroy(); }
    const cc = getChartColors();
    const top5 = d.ranking.slice(0, 5).reverse();
    const ctx = document.getElementById('punctualityChart').getContext('2d');
    charts.punctuality = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: top5.map(x => x.employee_name),
        datasets: [{
          label: 'الانضباط %',
          data: top5.map(x => x.punctuality),
          backgroundColor: cc.green + '80',
          borderRadius: 3,
          barPercentage: 0.6,
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(ctx) { return ctx.raw + '%'; }
            }
          }
        },
        scales: {
          x: { min: 0, max: 100, ticks: { color: cc.text, font: { family: 'Cairo', size: 10 }, callback: v => v + '%' }, grid: { color: cc.grid } },
          y: { ticks: { color: cc.text, font: { family: 'Cairo', size: 10 } }, grid: { display: false } }
        }
      }
    });
  });
}

function loadHourly() {
  safeApiCall('/api/dashboard/charts/hourly').then(function(d) {
    if (!d || !d.data) return;
    if (charts.hourly) { charts.hourly.destroy(); }
    const cc = getChartColors();
    const ctx = document.getElementById('hourlyChart').getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 100);
    gradient.addColorStop(0, cc.blue + '80');
    gradient.addColorStop(1, cc.blue + '10');
    charts.hourly = new Chart(ctx, {
      type: 'line',
      data: {
        labels: d.data.map(x => x.hour),
        datasets: [{
          label: 'عدد الموظفين',
          data: d.data.map(x => x.count),
          borderColor: cc.blue,
          backgroundColor: gradient,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: cc.blue,
          pointRadius: 3,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: { ticks: { color: cc.text, font: { family: 'Cairo', size: 9 } }, grid: { display: false } },
          y: { ticks: { color: cc.text, font: { family: 'Cairo', size: 10 }, stepSize: 1 }, grid: { color: cc.grid } }
        }
      }
    });
  });
}

let searchTimeout = null;

function debounceSearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(loadRecords, 300);
}

function loadRecords() {
  const search = document.getElementById('recordsSearch').value;
  const dept = document.getElementById('recordsDeptFilter').value;
  const status = document.getElementById('recordsStatusFilter').value;
  const date = document.getElementById('recordsDateFilter').value;
  currentPage = 1;
  document.getElementById('recordsSkeleton').style.display = 'block';
  document.getElementById('recordsTable').style.display = 'none';
  document.getElementById('recordsEmpty').style.display = 'none';
  let url = '/api/dashboard/records?page=1';
  if (search) url += '&search=' + encodeURIComponent(search);
  if (dept) url += '&department_id=' + dept;
  if (status) url += '&status=' + status;
  if (date) url += '&date=' + date;
  safeApiCall(url).then(function(d) {
    document.getElementById('recordsSkeleton').style.display = 'none';
    if (!d) { document.getElementById('recordsEmpty').style.display = 'block'; return; }
    renderRecords(d);
  });
}

function renderRecords(d) {
  const tbody = document.getElementById('recordsBody');
  const empty = document.getElementById('recordsEmpty');
  const table = document.getElementById('recordsTable');
  const loadMore = document.getElementById('loadMoreBtn');
  const info = document.getElementById('recordsInfo');
  if (!d.items || !d.items.length) {
    table.style.display = 'none';
    empty.style.display = 'block';
    info.textContent = 'عرض 0 من 0';
    loadMore.style.display = 'none';
    return;
  }
  table.style.display = '';
  empty.style.display = 'none';
  hasMoreRecords = d.has_more;
  currentPage = d.page;
  tbody.innerHTML = '';
  d.items.forEach(item => {
    const statusClass = item.status === 'present' ? 'badge-present' : item.status === 'late' ? 'badge-late' : item.status === 'absent' ? 'badge-absent' : 'badge-unknown';
    const statusLabel = item.status === 'present' ? '✅ حاضر' : item.status === 'late' ? '⏰ متأخر' : item.status === 'absent' ? '❌ غائب' : '❓ لم يسجل';
    const initials = item.employee_name.split(' ').map(w => w[0]).join('').slice(0, 2);
    const avatar = item.profile_photo
      ? `<img src="${item.profile_photo}" class="emp-avatar-sm" alt="">`
      : `<div class="emp-avatar-initials">${initials}</div>`;
    const row = document.createElement('tr');
    row.style.animation = 'fadeInRow 0.3s ease';
    row.innerHTML = `<td>${avatar}</td>
      <td><span class="emp-name">${item.employee_name}</span></td>
      <td><span class="emp-dept">${item.department || ''}</span></td>
      <td class="td-ltr">${item.clock_in || '—'}</td>
      <td class="td-ltr">${item.clock_out || '—'}</td>
      <td class="td-ltr">${item.duration || '—'}</td>
      <td class="td-small">${item.device_name || '—'}</td>
      <td><span class="badge ${statusClass}">${statusLabel}</span></td>
      <td><div class="row-actions">
        <button class="btn btn-ghost btn-xs" onclick="location.href='/admin/employees/${item.employee_id}'" title="عرض الموظف"><i class="ti ti-eye"></i></button>
        <button class="btn btn-ghost btn-xs" onclick="editRecord(${item.employee_id})" title="تعديل"><i class="ti ti-edit"></i></button>
      </div></td>`;
    tbody.appendChild(row);
  });
  info.textContent = `عرض ${d.items.length} من ${d.total}`;
  loadMore.style.display = d.has_more ? 'inline-flex' : 'none';
}

function loadMoreRecords() {
  const search = document.getElementById('recordsSearch').value;
  const dept = document.getElementById('recordsDeptFilter').value;
  const status = document.getElementById('recordsStatusFilter').value;
  const date = document.getElementById('recordsDateFilter').value;
  let url = '/api/dashboard/records?page=' + (currentPage + 1);
  if (search) url += '&search=' + encodeURIComponent(search);
  if (dept) url += '&department_id=' + dept;
  if (status) url += '&status=' + status;
  if (date) url += '&date=' + date;
  safeApiCall(url).then(function(d) {
    if (!d) return;
    const tbody = document.getElementById('recordsBody');
    d.items.forEach(item => {
      const statusClass = item.status === 'present' ? 'badge-present' : item.status === 'late' ? 'badge-late' : item.status === 'absent' ? 'badge-absent' : 'badge-unknown';
      const statusLabel = item.status === 'present' ? '✅ حاضر' : item.status === 'late' ? '⏰ متأخر' : item.status === 'absent' ? '❌ غائب' : '❓ لم يسجل';
      const initials = item.employee_name.split(' ').map(w => w[0]).join('').slice(0, 2);
      const avatar = item.profile_photo ? `<img src="${item.profile_photo}" class="emp-avatar-sm">` : `<div class="emp-avatar-initials">${initials}</div>`;
      const row = document.createElement('tr');
      row.innerHTML = `<td>${avatar}</td><td><span class="emp-name">${item.employee_name}</span></td><td>${item.department || ''}</td>
        <td class="td-ltr">${item.clock_in || '—'}</td><td class="td-ltr">${item.clock_out || '—'}</td><td class="td-ltr">${item.duration || '—'}</td>
        <td class="td-small">${item.device_name || '—'}</td><td><span class="badge ${statusClass}">${statusLabel}</span></td>
        <td><div class="row-actions"><button class="btn btn-ghost btn-xs" onclick="location.href='/admin/employees/${item.employee_id}'"><i class="ti ti-eye"></i></button></div></td>`;
      tbody.appendChild(row);
    });
    currentPage = d.page;
    hasMoreRecords = d.has_more;
    document.getElementById('loadMoreBtn').style.display = d.has_more ? 'inline-flex' : 'none';
    document.getElementById('recordsInfo').textContent = `عرض ${document.getElementById('recordsBody').children.length} من ${d.total}`;
  });
}

function loadFilters() {
  safeApiCall('/api/dashboard/filters').then(function(d) {
    if (!d) return;
    const deptSelect = document.getElementById('recordsDeptFilter');
    d.departments.forEach(dept => {
      deptSelect.innerHTML += `<option value="${dept.id}">${dept.name_ar}</option>`;
    });
    const statusSelect = document.getElementById('recordsStatusFilter');
    d.statuses.forEach(s => {
      statusSelect.innerHTML += `<option value="${s.value}">${s.label}</option>`;
    });
    document.getElementById('recordsDateFilter').valueAsDate = new Date();
  });
}

function loadAlerts() {
  safeApiCall('/api/dashboard/alerts').then(function(d) {
    if (!d) return;
    const body = document.getElementById('alertsBody');
    const count = document.getElementById('alertsCount');
    const footer = document.getElementById('alertsFooter');
    count.textContent = d.count;
    if (!d.alerts || !d.alerts.length) {
      body.innerHTML = '<div class="alert-empty">لا توجد تنبيهات</div>';
      footer.style.display = 'none';
      return;
    }
    footer.style.display = 'block';
    const visible = d.alerts.filter(a => !dismissedAlerts.includes(a.title));
    if (!visible.length) {
      body.innerHTML = '<div class="alert-empty">تم تجاهل جميع التنبيهات</div>';
      return;
    }
    body.innerHTML = '';
    visible.forEach(a => {
      const typeClass = a.type === 'critical' ? 'alert-critical' : a.type === 'warning' ? 'alert-warning' : 'alert-info';
      const iconMap = { critical: '🚨', warning: '⚠️', info: '⏰' };
      body.innerHTML += `<div class="alert-item ${typeClass}">
        <span class="alert-icon">${iconMap[a.type] || '📌'}</span>
        <div class="alert-content">
          <div class="alert-title"><a href="${a.link}" style="color:inherit;text-decoration:none">${a.title}</a></div>
          <div class="alert-msg">${a.message}</div>
        </div>
        <button class="btn btn-ghost btn-xs" onclick="dismissAlert('${a.title.replace(/'/g, "\\'")}')" style="flex-shrink:0"><i class="ti ti-x"></i></button>
      </div>`;
    });
  });
}

function dismissAlert(title) {
  dismissedAlerts.push(title);
  localStorage.setItem('dismissedAlerts', JSON.stringify(dismissedAlerts));
  loadAlerts();
}

function dismissAllAlerts() {
  safeApiCall('/api/dashboard/alerts').then(function(d) {
    if (!d) return;
    (d.alerts || []).forEach(a => {
      if (!dismissedAlerts.includes(a.title)) dismissedAlerts.push(a.title);
    });
    localStorage.setItem('dismissedAlerts', JSON.stringify(dismissedAlerts));
    loadAlerts();
  });
}

function toggleAlerts() {
  const body = document.getElementById('alertsBody');
  const chevron = document.getElementById('alertsChevron');
  body.classList.toggle('collapsed');
  chevron.style.transform = body.classList.contains('collapsed') ? 'rotate(-90deg)' : '';
}

function loadSchedule() {
  safeApiCall('/api/dashboard/schedule').then(function(d) {
    if (!d || !d.shifts) return;
    const container = document.getElementById('scheduleTimeline');
    container.innerHTML = '<div class="schedule-bar"></div>';
    const bar = container.querySelector('.schedule-bar');
    d.shifts.forEach((s, i) => {
      const pct = 33.33;
      const isCurrent = s.is_current;
      bar.innerHTML += `<div class="schedule-block ${isCurrent ? 'current' : ''}" style="width:${pct}%;border-color:${s.bar_color}">
        <div class="schedule-time">${s.start} - ${s.end}</div>
        <div class="schedule-label">${s.label}</div>
        <div class="schedule-info">${s.clocked_in}/${s.scheduled} موظف</div>
        <div class="schedule-bar-inner" style="height:4px;background:var(--bg);border-radius:2px;margin-top:4px;overflow:hidden">
          <div style="height:100%;width:${s.scheduled > 0 ? Math.round((s.clocked_in/s.scheduled)*100) : 0}%;background:${s.bar_color};border-radius:2px;transition:width 0.3s"></div>
        </div>
        ${isCurrent ? '<span class="schedule-current-badge">الوردية الحالية</span>' : ''}
      </div>`;
    });
    const now = new Date();
    const pctOfDay = ((now.getHours() * 60 + now.getMinutes()) / 1440) * 100;
    container.innerHTML += `<div class="schedule-now" style="left:${pctOfDay}%"><div class="schedule-now-line"></div></div>`;
  });
}

function loadMap() {
  if (document.getElementById('attendanceMap')) {
    safeApiCall('/api/dashboard/map').then(function(d) {
      if (!d) return;
      if (!d.markers || !d.markers.length) {
        document.getElementById('attendanceMap').innerHTML = '<div style="text-align:center;padding:40px;color:var(--muted)">لا توجد أجهزة بصرية مثبتة</div>';
        return;
      }
      if (!mapInstance) {
        mapInstance = L.map('attendanceMap').setView([32.1, 20.1], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '&copy; OpenStreetMap',
          maxZoom: 18,
        }).addTo(mapInstance);
      }
      mapMarkers.forEach(m => mapInstance.removeLayer(m));
      mapMarkers = [];
      d.markers.forEach(m => {
        const color = m.status === 'online' ? '#22c55e' : m.status === 'idle' ? '#f59e0b' : '#ef4444';
        const icon = L.divIcon({
          html: `<div style="width:20px;height:20px;border-radius:50%;background:${color};border:3px solid ${color}40;box-shadow:0 0 8px ${color}60"></div>`,
          iconSize: [20, 20],
          className: '',
        });
        const marker = L.marker([m.lat, m.lng], { icon }).addTo(mapInstance);
        marker.bindPopup(`
          <div style="font-family:Cairo;direction:rtl;text-align:right;font-size:13px">
            <strong>${m.name}</strong><br>
            IP: ${m.ip_address || '—'}<br>
            آخر مزامنة: ${m.last_sync ? new Date(m.last_sync).toLocaleTimeString('ar-SA') : '—'}<br>
            موظفون اليوم: ${m.employee_count}
          </div>
        `);
        mapMarkers.push(marker);
      });
      if (mapMarkers.length) {
        const group = L.featureGroup(mapMarkers);
        mapInstance.fitBounds(group.getBounds().pad(0.1));
      }
    });
  }
}

function toggleMapFullscreen() {
  const map = document.getElementById('attendanceMap');
  map.classList.toggle('map-fullscreen');
  if (mapInstance) setTimeout(() => mapInstance.invalidateSize(), 200);
}

function loadNotifications() {
  safeApiCall('/api/dashboard/notifications').then(function(d) {
    if (!d) return;
    const badge = document.getElementById('notifBadge');
    badge.textContent = d.unread_count;
    badge.style.display = d.unread_count > 0 ? 'flex' : 'none';
    const list = document.getElementById('notifList');
    list.innerHTML = '';
    (d.notifications || []).forEach(n => {
      list.innerHTML += `<div class="notif-item ${n.is_read ? '' : 'unread'}"><div class="notif-title">${n.title}</div><div class="notif-msg">${n.message}</div><div class="notif-time">${n.created_at ? new Date(n.created_at).toLocaleTimeString('ar-SA') : ''}</div></div>`;
    });
    if (!d.notifications || !d.notifications.length) {
      list.innerHTML = '<div class="notif-item" style="color:var(--muted)">لا توجد إشعارات</div>';
    }
  });
}

function doGlobalSearch(q) {
  const results = document.getElementById('searchResults');
  if (q.length < 2) { results.style.display = 'none'; return; }
  safeApiCall('/api/dashboard/search?q=' + encodeURIComponent(q)).then(function(d) {
    if (!d) return;
    let html = '';
    d.employees.forEach(e => {
      html += `<a href="/admin/employees/${e.id}" class="search-result-item"><i class="ti ti-user"></i> ${e.full_name} <span class="search-result-type">${e.department || ''}</span></a>`;
    });
    d.departments.forEach(dept => {
      html += `<a href="/admin/departments/${dept.id}" class="search-result-item"><i class="ti ti-building"></i> ${dept.name_ar} <span class="search-result-type">قسم</span></a>`;
    });
    if (!html) html = '<div class="search-result-empty">لا توجد نتائج</div>';
    results.innerHTML = html;
    results.style.display = 'block';
  });
}

function exportRecords() {
  window.open('/api/dashboard/export-records', '_blank');
}

function editRecord(id) {
  window.location.href = '/admin/attendance?edit=' + id;
}
