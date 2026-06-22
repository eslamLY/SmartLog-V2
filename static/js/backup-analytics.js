function loadCharts() {
  fetch('/admin/backup/api/stats')
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok) return;
    renderStorageChart(d.by_date);
    renderTypeChart(d.by_type);
    renderStatusChart(d.by_status);
    renderScheduleChart(d.by_schedule);
  });
}

function renderStorageChart(data) {
  var cv = document.getElementById('storageChart');
  if(!cv || !data) return;
  var ctx = cv.getContext('2d');
  if(window._storageChart) window._storageChart.destroy();
  window._storageChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(function(d){return d.date}),
      datasets: [{
        label: 'حجم النسخ (MB)',
        data: data.map(function(d){return d.size_mb}),
        backgroundColor: 'rgba(99,102,241,0.38)',
        borderColor: 'rgba(99,102,241,0.9)',
        borderWidth: 1,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#94a3b8' } },
        x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
      }
    }
  });
}

function renderTypeChart(data) {
  var cv = document.getElementById('typeChart');
  if(!cv || !data) return;
  var ctx = cv.getContext('2d');
  if(window._typeChart) window._typeChart.destroy();
  window._typeChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(function(d){var n={full:'كاملة',incremental:'تدريجية',selective:'انتقائية'};return n[d.type]||d.type}),
      datasets: [{
        data: data.map(function(d){return d.count}),
        backgroundColor: ['#6366f1', '#22c55e', '#f59e0b'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position:'bottom', labels:{color:'#94a3b8',padding:12,usePointStyle:true} } },
      cutout: '60%'
    }
  });
}

function renderStatusChart(data) {
  var cv = document.getElementById('statusChart');
  if(!cv || !data) return;
  var ctx = cv.getContext('2d');
  if(window._statusChart) window._statusChart.destroy();
  window._statusChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(function(d){var n={verified:'موثّق',completed:'مكتمل',corrupted:'تالف'};return n[d.status]||d.status}),
      datasets: [{
        data: data.map(function(d){return d.count}),
        backgroundColor: ['#22c55e', '#6366f1', '#ef4444'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position:'bottom', labels:{color:'#94a3b8',padding:12,usePointStyle:true} } },
      cutout: '60%'
    }
  });
}

function renderScheduleChart(data) {
  var cv = document.getElementById('scheduleChart');
  if(!cv || !data) return;
  var ctx = cv.getContext('2d');
  if(window._scheduleChart) window._scheduleChart.destroy();
  window._scheduleChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(function(d){return d.name}),
      datasets: [{
        label: 'عدد التشغيلات',
        data: data.map(function(d){return d.runs}),
        backgroundColor: 'rgba(34,197,94,0.38)',
        borderColor: 'rgba(34,197,94,0.9)',
        borderWidth: 1,
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { grid: { display: false }, ticks: { color: '#94a3b8' } },
        x: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#94a3b8' } }
      }
    }
  });
}
