/**
 * static/js/forecasting-charts.js — Interactive charts using Chart.js
 * Renders prediction trends, model performance, correlation, and segmentation.
 */
let chartInstances = {};

function renderTrendChart(canvasId, data, label, color) {
  var canvas = document.getElementById(canvasId);
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
  chartInstances[canvasId] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(function(d){return d.date || d.ds || d.label || ''}),
      datasets: [{
        label: label || 'القيمة',
        data: data.map(function(d){return d.accuracy || d.yhat || d.value || 0}),
        borderColor: color || '#8b5cf6',
        backgroundColor: (color || '#8b5cf6') + '22',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
      },
      scales: {
        x: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: '#1e293b' } },
        y: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: '#1e293b' }, beginAtZero: true },
      }
    }
  });
}

function renderBarChart(canvasId, labels, values, label, color) {
  var canvas = document.getElementById(canvasId);
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
  chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: label || 'القيمة',
        data: values,
        backgroundColor: color || '#8b5cf6',
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
      },
      scales: {
        x: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: '#1e293b' } },
        y: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: '#1e293b' }, beginAtZero: true },
      }
    }
  });
}

function renderDoughnutChart(canvasId, labels, values, colors) {
  var canvas = document.getElementById(canvasId);
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
  chartInstances[canvasId] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors || ['#8b5cf6', '#f59e0b', '#ef4444', '#22c55e', '#6366f1'],
        borderWidth: 0,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 11 } } },
      }
    }
  });
}

function renderModelPerformanceChart(canvasId, data) {
  var labels = data.map(function(d){return d.model_key || d.label || ''});
  var acc = data.map(function(d){return d.avg_accuracy || d.accuracy_pct || 0});
  var prec = data.map(function(d){return d.avg_precision || d.precision_pct || 0});
  var rec = data.map(function(d){return d.avg_recall || d.recall_pct || 0});
  var canvas = document.getElementById(canvasId);
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
  chartInstances[canvasId] = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: labels,
      datasets: [
        { label: 'الدقة', data: acc, borderColor: '#8b5cf6', backgroundColor: '#8b5cf622' },
        { label: 'الضبط', data: prec, borderColor: '#22c55e', backgroundColor: '#22c55e22' },
        { label: 'الاستدعاء', data: rec, borderColor: '#f59e0b', backgroundColor: '#f59e0b22' },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 10 } } },
      },
      scales: {
        r: { ticks: { color: '#64748b', backdropColor: 'transparent' }, grid: { color: '#1e293b' } }
      }
    }
  });
}

function renderSegmentationScatter(canvasId, segments) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || !segments || !segments.length) return;
  var ctx = canvas.getContext('2d');
  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
  var clusterColors = ['#8b5cf6', '#f59e0b', '#22c55e', '#ef4444', '#6366f1', '#ec4899'];
  var datasets = [];
  var clusters = {};
  segments.forEach(function(s){
    var c = s.cluster || 0;
    if (!clusters[c]) clusters[c] = { label: 'مجموعة ' + c, data: [], backgroundColor: clusterColors[c % clusterColors.length] };
    clusters[c].data.push({ x: s.employee_id, y: s.segment_value || Math.random() * 100 });
  });
  Object.keys(clusters).forEach(function(k){
    datasets.push({
      label: clusters[k].label,
      data: clusters[k].data,
      backgroundColor: clusters[k].backgroundColor,
      pointRadius: 5,
    });
  });
  chartInstances[canvasId] = new Chart(ctx, {
    type: 'scatter',
    data: { datasets: datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 10 } } },
      },
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
        y: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
      }
    }
  });
}
