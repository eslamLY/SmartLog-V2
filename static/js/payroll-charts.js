let rangeChartInstance = null;
let deptCompareInstance = null;
let componentPieInstance = null;
let trendChartInstance = null;

function loadAnalytics() {
  const container = document.getElementById('analyticsContainer');
  if (!container) return;
  fetch(API_BASE + '/api/analytics?month=' + CURRENT_MONTH + '&year=' + CURRENT_YEAR)
    .then(r => r.json())
    .then(d => {
      if (!d || !d.ok) { console.warn('Analytics API returned error', d); return; }
      renderAnalyticsStats(d);
      renderRangeChart(d);
      renderDeptCompareChart(d);
      renderComponentPie(d);
      renderTrendChart(d);
      renderAnalyticsInsights(d);
    }).catch(e => console.error('Analytics fetch failed', e));
}

function renderAnalyticsStats(d) {
  const el = document.getElementById('analyticsStats');
  if (!el) return;
  const s = d.stats;
  el.innerHTML = '<div class="mini-cards">' +
    '<div class="mini-card"><span class="mc-label">متوسط الراتب</span><span class="mc-value">' + s.avg_salary + ' د.ل</span></div>' +
    '<div class="mini-card"><span class="mc-label">الوسيط</span><span class="mc-value">' + s.median_salary + ' د.ل</span></div>' +
    '<div class="mini-card"><span class="mc-label">الانحراف المعياري</span><span class="mc-value">±' + s.std_deviation + ' د.ل</span></div>' +
    '<div class="mini-card"><span class="mc-label">معامل الاختلاف</span><span class="mc-value">' + s.cv + '%</span></div>' +
    '<div class="mini-card"><span class="mc-label">الأعلى</span><span class="mc-value text-green">' + (s.highest_paid ? s.highest_paid.name + ' (' + s.highest_paid.salary + ')' : '—') + '</span></div>' +
    '<div class="mini-card"><span class="mc-label">الأدنى</span><span class="mc-value text-red">' + (s.lowest_paid ? s.lowest_paid.name + ' (' + s.lowest_paid.salary + ')' : '—') + '</span></div>' +
    '</div>';
}

function renderRangeChart(d) {
  const canvas = document.getElementById('rangeChart');
  if (!canvas) return;
  if (rangeChartInstance) rangeChartInstance.destroy();
  const ranges = d.range_distribution || {};
  rangeChartInstance = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: Object.keys(ranges),
      datasets: [{
        label: 'عدد الموظفين',
        data: Object.values(ranges),
        backgroundColor: ['rgba(99,102,241,0.5)', 'rgba(59,130,246,0.5)', 'rgba(34,197,94,0.5)', 'rgba(245,158,11,0.5)', 'rgba(239,68,68,0.5)', 'rgba(139,92,246,0.5)'],
        borderColor: ['#6366f1', '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6'],
        borderWidth: 1,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { rtl: true } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#8899b4' } },
        y: { grid: { color: 'rgba(42,58,90,0.3)' }, ticks: { color: '#8899b4', stepSize: 1 } },
      }
    }
  });
}

function renderDeptCompareChart(d) {
  const canvas = document.getElementById('deptCompareChartCanvas');
  if (!canvas) return;
  if (deptCompareInstance) deptCompareInstance.destroy();
  const deptStats = d.dept_stats || {};
  const depts = Object.keys(deptStats);
  if (depts.length === 0) {
    canvas.parentElement.innerHTML = '<div class="empty-state"><i class="ti ti-building"></i><p>لا توجد بيانات أقسام</p></div>';
    return;
  }
  deptCompareInstance = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: depts,
      datasets: [
        { label: 'الحد الأدنى', data: depts.map(k => deptStats[k].min), backgroundColor: 'rgba(245,158,11,0.6)', borderRadius: 3 },
        { label: 'المتوسط', data: depts.map(k => deptStats[k].avg), backgroundColor: 'rgba(99,102,241,0.6)', borderRadius: 3 },
        { label: 'الحد الأقصى', data: depts.map(k => deptStats[k].max), backgroundColor: 'rgba(34,197,94,0.6)', borderRadius: 3 },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'top', labels: { color: '#8899b4', boxWidth: 12 } }, tooltip: { rtl: true } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#8899b4' } },
        y: { grid: { color: 'rgba(42,58,90,0.3)' }, ticks: { color: '#8899b4' } },
      }
    }
  });
}

function renderComponentPie(d) {
  const canvas = document.getElementById('componentPieCanvas');
  if (!canvas) return;
  if (componentPieInstance) componentPieInstance.destroy();
  const ct = d.component_totals || {};
  componentPieInstance = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: ['الرواتب الأساسية', 'البدلات', 'العمل الإضافي', 'الخصومات', 'الضرائب'],
      datasets: [{
        data: [ct.base, ct.allowances, ct.overtime, ct.deductions, ct.tax],
        backgroundColor: ['rgba(99,102,241,0.8)', 'rgba(59,130,246,0.8)', 'rgba(34,197,94,0.8)', 'rgba(239,68,68,0.8)', 'rgba(245,158,11,0.8)'],
        borderWidth: 0,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: { position: 'bottom', labels: { color: '#8899b4', boxWidth: 12, padding: 10 } },
        tooltip: {
          rtl: true,
          callbacks: {
            label: function(ctx) {
              const total = ctx.dataset.data.reduce((a,b) => a + b, 0);
              return ctx.label + ': ' + ctx.parsed + ' د.ل (' + (total ? Math.round(ctx.parsed / total * 100) : 0) + '%)';
            }
          }
        }
      }
    }
  });
}

function renderTrendChart(d) {
  const canvas = document.getElementById('salaryTrendCanvas');
  if (!canvas) return;
  if (trendChartInstance) trendChartInstance.destroy();
  const trend = d.trend || [];
  if (trend.length === 0) {
    canvas.parentElement.innerHTML = '<div class="empty-state"><i class="ti ti-chart-line"></i><p>لا توجد بيانات كافية</p></div>';
    return;
  }
  trendChartInstance = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels: trend.map(t => t.month),
      datasets: [{
        label: 'متوسط الراتب',
        data: trend.map(t => t.avg),
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99,102,241,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
        pointHoverRadius: 6,
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { rtl: true, callbacks: { label: ctx => ctx.parsed.y + ' د.ل' } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#8899b4' } },
        y: { grid: { color: 'rgba(42,58,90,0.3)' }, ticks: { color: '#8899b4', callback: v => v + ' د.ل' } },
      }
    }
  });
}

function renderAnalyticsInsights(d) {
  const el = document.getElementById('analyticsInsights');
  if (!el) return;
  const insights = d.insights || [];
  if (insights.length === 0) {
    el.innerHTML = '<div class="empty-state"><i class="ti ti-bulb-off"></i><p>لا توجد رؤى متاحة</p></div>';
    return;
  }
  el.innerHTML = '<div class="insights-title">الرؤى والتوصيات</div>';
  insights.forEach(function(i) {
    const typeClass = i.type === 'warning' ? 'insight-warning' : (i.type === 'info' ? 'insight-info' : '');
    el.innerHTML += '<div class="insight-card ' + typeClass + '"><div class="insight-icon">' + i.icon + '</div><div class="insight-body"><div class="insight-title">' + i.title + '</div><div class="insight-detail">' + i.detail + '</div></div></div>';
  });
}
