var analyticsData = {};
var dailyChart = null;
var hourlyChart = null;
var rankingChart = null;
var sourceChart = null;
var currentAnalyticsPeriod = 'week';
var currentAnalyticsEmployee = '';

function initAnalytics(data) {
  analyticsData = data;
  initHeatmapMap(data);
  refreshAnalytics();
}

function changePeriod(period) {
  currentAnalyticsPeriod = period;
  var labels = { day: 'آخر 24 ساعة', week: 'آخر 7 أيام', month: 'آخر 30 يوم', year: 'آخر سنة' };
  document.getElementById('periodBadge').textContent = labels[period] || period;
  refreshAnalytics();
}

function changeAnalyticsEmployee(val) {
  currentAnalyticsEmployee = val;
  refreshAnalytics();
}

function refreshAnalytics() {
  fetchStats();
  fetchMovement();
  fetchHeatmap();
  fetchZoneRanking();
}

function fetchStats() {
  var url = '/api/admin/analytics/stats?period=' + currentAnalyticsPeriod;
  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(resp) {
      if (resp.ok && resp.data) {
        updateStatCards(resp.data);
        buildSourceChart(resp.data.source_breakdown || {});
        buildHourlyChart(resp.data.hourly_activity || []);
      }
    })
    .catch(function(err) { console.error('Stats fetch error:', err); });
}

function fetchMovement() {
  var url = '/api/admin/analytics/movement?period=' + currentAnalyticsPeriod;
  if (currentAnalyticsEmployee) url += '&employee_id=' + currentAnalyticsEmployee;
  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(resp) {
      if (resp.ok && resp.data) {
        buildDailyChart(resp.data.daily_breakdown || []);
        buildRankingChart(resp.data.employee_breakdown || []);
        updateEmployeeTable(resp.data.employee_breakdown || []);
      }
    })
    .catch(function(err) { console.error('Movement fetch error:', err); });
}

function fetchHeatmap() {
  var url = '/api/admin/analytics/heatmap';
  if (currentAnalyticsEmployee) url += '&employee_id=' + currentAnalyticsEmployee;
  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(resp) {
      if (resp.ok && resp.points) {
        updateHeatmapMap(resp.points);
      }
    })
    .catch(function(err) { console.error('Heatmap fetch error:', err); });
}

function fetchZoneRanking() {
  var url = '/api/admin/geofence/events?limit=200';
  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(resp) {
      if (resp.ok && resp.data) {
        buildZoneRanking(resp.data);
      }
    })
    .catch(function(err) { console.error('Zone ranking fetch error:', err); });
}

function updateStatCards(stats) {
  document.getElementById('statTotalPoints').textContent = stats.total_logs || 0;
  document.getElementById('statUniqueEmployees').textContent = stats.unique_employees || 0;
  document.getElementById('statDistance').textContent = '—';
  document.getElementById('statAvgAccuracy').textContent = (stats.avg_accuracy_m || 0) + 'م';
  document.getElementById('statAlerts').textContent = stats.total_alerts || 0;
  var topZones = stats.top_zones || [];
  document.getElementById('statTopZone').textContent = topZones.length > 0 ? topZones[0].name : '—';
}

function buildDailyChart(data) {
  var ctx = document.getElementById('dailyActivityChart');
  if (!ctx) return;
  if (dailyChart) dailyChart.destroy();
  var labels = data.map(function(d) { return d.date; });
  var values = data.map(function(d) { return d.count; });
  dailyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'نقاط التتبع',
        data: values,
        backgroundColor: 'rgba(59,130,246,0.6)',
        borderColor: '#3b82f6',
        borderWidth: 2,
        borderRadius: 4,
        barPercentage: 0.6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#8899b4', font: { family: 'Cairo' } } }
      },
      scales: {
        x: {
          ticks: { color: '#566580', font: { size: 10, family: 'Cairo' } },
          grid: { color: 'rgba(42,58,90,0.3)' }
        },
        y: {
          ticks: { color: '#566580', font: { size: 10 } },
          grid: { color: 'rgba(42,58,90,0.3)' },
          beginAtZero: true
        }
      }
    }
  });
}

function buildHourlyChart(data) {
  var ctx = document.getElementById('hourlyDistributionChart');
  if (!ctx) return;
  if (hourlyChart) hourlyChart.destroy();
  var labels = data.map(function(d) { return d.hour; });
  var values = data.map(function(d) { return d.count; });
  hourlyChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'النشاط',
        data: values,
        borderColor: '#22c55e',
        backgroundColor: 'rgba(34,197,94,0.1)',
        fill: true,
        tension: 0.4,
        pointBackgroundColor: '#22c55e',
        pointRadius: 3,
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#8899b4', font: { family: 'Cairo' } } }
      },
      scales: {
        x: {
          ticks: { color: '#566580', font: { size: 10, family: 'Cairo' } },
          grid: { color: 'rgba(42,58,90,0.3)' }
        },
        y: {
          ticks: { color: '#566580', font: { size: 10 } },
          grid: { color: 'rgba(42,58,90,0.3)' },
          beginAtZero: true
        }
      }
    }
  });
}

function buildRankingChart(data) {
  var ctx = document.getElementById('employeeRankingChart');
  if (!ctx) return;
  if (rankingChart) rankingChart.destroy();
  var top10 = data.slice(0, 10);
  var labels = top10.map(function(d) { return d.employee_name; });
  var values = top10.map(function(d) { return d.points; });
  var colors = values.map(function(v, i) {
    var opacity = 1 - (i * 0.07);
    return 'rgba(99,102,241,' + Math.max(opacity, 0.3) + ')';
  });
  rankingChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'نقاط التتبع',
        data: values,
        backgroundColor: colors,
        borderColor: '#6366f1',
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          ticks: { color: '#566580', font: { size: 10 } },
          grid: { color: 'rgba(42,58,90,0.3)' },
          beginAtZero: true
        },
        y: {
          ticks: { color: '#8899b4', font: { size: 11, family: 'Cairo' } },
          grid: { color: 'rgba(42,58,90,0.3)' }
        }
      }
    }
  });
}

function buildSourceChart(data) {
  var ctx = document.getElementById('sourceBreakdownChart');
  if (!ctx) return;
  if (sourceChart) sourceChart.destroy();
  var labels = Object.keys(data);
  var values = Object.values(data);
  if (labels.length === 0) {
    labels = ['app'];
    values = [1];
  }
  var sourceColors = {
    'app': '#3b82f6',
    'web': '#22c55e',
    'device': '#f59e0b',
    'api': '#8b5cf6'
  };
  var bgColors = labels.map(function(l) { return sourceColors[l] || '#6366f1'; });
  sourceChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: bgColors,
        borderColor: '#1a2035',
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#8899b4', font: { size: 11, family: 'Cairo' }, padding: 12 }
        }
      }
    }
  });
}

function buildZoneRanking(events) {
  var container = document.getElementById('zoneRanking');
  if (!container) return;
  var zoneCounts = {};
  events.forEach(function(e) {
    if (e.event_type === 'entry' && e.zone_name) {
      zoneCounts[e.zone_name] = (zoneCounts[e.zone_name] || 0) + 1;
    }
  });
  var sorted = Object.entries(zoneCounts).sort(function(a, b) { return b[1] - a[1]; });
  if (sorted.length === 0) {
    container.innerHTML = '<div class="empty-state-mini"><i class="ti ti-map-off"></i><p>لا توجد بيانات كافية</p></div>';
    return;
  }
  var maxVal = sorted[0][1];
  var html = '';
  sorted.slice(0, 10).forEach(function(item) {
    var pct = (item[1] / maxVal * 100).toFixed(0);
    html += '<div class="zone-rank-item">' +
      '<div class="zone-rank-name">' + item[0] + '</div>' +
      '<div class="zone-rank-bar"><div class="zone-rank-fill" style="width:' + pct + '%"></div></div>' +
      '<div class="zone-rank-count">' + item[1] + '</div></div>';
  });
  container.innerHTML = html;
}

function updateEmployeeTable(data) {
  var tbody = document.getElementById('employeeDetailBody');
  if (!tbody) return;
  if (!data || data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted)">لا توجد بيانات</td></tr>';
    return;
  }
  var html = '';
  data.forEach(function(d, i) {
    html += '<tr>' +
      '<td>' + (i + 1) + '</td>' +
      '<td>' + escapeHtml(d.employee_name) + '</td>' +
      '<td>' + escapeHtml(d.department || '—') + '</td>' +
      '<td>' + d.points + '</td>' +
      '<td>' + (d.percentage || 0) + '%</td></tr>';
  });
  tbody.innerHTML = html;
}
