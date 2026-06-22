let trendChartInstance = null;
let punctualityChartInstance = null;
let deptChartInstance = null;
let pieChartInstance = null;

function renderTrendChart(data) {
  const ctx = document.getElementById('trendChart').getContext('2d');
  if (trendChartInstance) trendChartInstance.destroy();
  if (!data || !data.labels || data.labels.length === 0) {
    document.querySelector('#trendChartCard .chart-body').innerHTML = '<div class="empty-state"><i class="ti ti-chart-line"></i><p>لا توجد بيانات كافية</p></div>';
    return;
  }
  trendChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.labels,
      datasets: [{
        label: 'حضور %',
        data: data.values,
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99,102,241,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          rtl: true,
          callbacks: { label: ctx => ctx.parsed.y + '%' }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#8899b4', maxTicksLimit: 10 }
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(42,58,90,0.4)' },
          ticks: { color: '#8899b4', callback: v => v + '%' }
        }
      }
    }
  });
}

function renderPunctualityChart(data) {
  const ctx = document.getElementById('punctualityChart').getContext('2d');
  if (punctualityChartInstance) punctualityChartInstance.destroy();
  if (!data || !data.labels || data.labels.length === 0) {
    document.querySelector('#punctualityChartCard .chart-body').innerHTML = '<div class="empty-state"><i class="ti ti-clock-check"></i><p>لا توجد بيانات</p></div>';
    return;
  }
  punctualityChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [{
        label: 'عدد الموظفين',
        data: data.values,
        backgroundColor: ['rgba(34,197,94,0.7)', 'rgba(245,158,11,0.7)', 'rgba(239,68,68,0.7)'],
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { rtl: true }
      },
      scales: {
        x: {
          grid: { color: 'rgba(42,58,90,0.3)' },
          ticks: { color: '#8899b4' }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#8899b4' }
        }
      }
    }
  });
}

function renderDeptChart(data) {
  const ctx = document.getElementById('deptChart').getContext('2d');
  if (deptChartInstance) deptChartInstance.destroy();
  if (!data || !data.labels || data.labels.length === 0) {
    document.querySelector('#deptChartCard .chart-body').innerHTML = '<div class="empty-state"><i class="ti ti-building"></i><p>لا توجد بيانات أقسام</p></div>';
    return;
  }
  deptChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [
        { label: 'حضور %', data: data.attendance, backgroundColor: 'rgba(99,102,241,0.7)', borderRadius: 4 },
        { label: 'غياب %', data: data.absence, backgroundColor: 'rgba(239,68,68,0.7)', borderRadius: 4 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { color: '#8899b4', boxWidth: 12 } },
        tooltip: { rtl: true, callbacks: { label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y + '%' } }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#8899b4' } },
        y: { min: 0, max: 100, grid: { color: 'rgba(42,58,90,0.3)' }, ticks: { color: '#8899b4', callback: v => v + '%' } }
      }
    }
  });
}

function renderPieChart(data) {
  const ctx = document.getElementById('pieChart').getContext('2d');
  if (pieChartInstance) pieChartInstance.destroy();
  if (!data || !data.labels || data.labels.length === 0) {
    document.querySelector('#pieChartCard .chart-body').innerHTML = '<div class="empty-state"><i class="ti ti-pie-chart"></i><p>لا توجد بيانات</p></div>';
    return;
  }
  pieChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.labels,
      datasets: [{
        data: data.values,
        backgroundColor: ['rgba(34,197,94,0.8)', 'rgba(245,158,11,0.8)', 'rgba(239,68,68,0.8)', 'rgba(59,130,246,0.8)'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '60%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#8899b4', boxWidth: 12, padding: 12 }
        },
        tooltip: {
          rtl: true,
          callbacks: {
            label: ctx => {
              const total = ctx.dataset.data.reduce((a,b) => a + b, 0);
              return ctx.label + ': ' + Math.round(ctx.parsed / total * 100) + '%';
            }
          }
        }
      }
    }
  });
}

function renderHeatmap(data) {
  const container = document.getElementById('heatmapContainer');
  container.innerHTML = '';
  if (!data || !data.cells || data.cells.length === 0) {
    container.innerHTML = '<div class="empty-state"><i class="ti ti-grid-dots"></i><p>لا توجد بيانات حرارية</p></div>';
    return;
  }
  const width = container.clientWidth || 600;
  const margin = { top: 30, right: 20, bottom: 60, left: 50 };
  const innerW = width - margin.left - margin.right;
  const days = data.days || ['الإثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد'];
  const hours = data.hours || Array.from({length: 12}, (_,i) => (i+7) + ':00');
  const cellH = Math.max(28, Math.min(40, (innerW - 40) / hours.length));
  const cellW = Math.max(28, Math.min(50, (innerW - 40) / hours.length));
  const height = margin.top + margin.bottom + days.length * cellH + 20;
  const svg = d3.select(container).append('svg').attr('width', width).attr('height', height);
  const g = svg.append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');
  const maxVal = d3.max(data.cells, d => d.value) || 1;
  const colorScale = d3.scaleSequential(d3.interpolateReds).domain([0, maxVal]);
  const heatData = [];
  for (let di = 0; di < days.length; di++) {
    for (let hi = 0; hi < hours.length; hi++) {
      const cell = data.cells.find(c => c.day === di && c.hour === hi);
      heatData.push({ day: di, hour: hi, value: cell ? cell.value : 0 });
    }
  }
  g.selectAll('rect').data(heatData).enter().append('rect')
    .attr('x', d => d.hour * cellW)
    .attr('y', d => d.day * cellH)
    .attr('width', cellW - 2)
    .attr('height', cellH - 2)
    .attr('rx', 3)
    .attr('fill', d => d.value === 0 ? 'rgba(42,58,90,0.3)' : colorScale(d.value))
    .append('title').text(d => (days[d.day] || '') + ' ' + (hours[d.hour] || '') + ': ' + d.value);
  g.selectAll('.day-label').data(days).enter().append('text')
    .attr('x', -8).attr('y', (d,i) => i * cellH + cellH/2 + 4)
    .attr('text-anchor', 'end').attr('fill', '#8899b4').style('font-size', '11px')
    .text(d => d);
  g.selectAll('.hour-label').data(hours).enter().append('text')
    .attr('x', (d,i) => i * cellW + cellW/2).attr('y', -8)
    .attr('text-anchor', 'middle').attr('fill', '#8899b4').style('font-size', '10px')
    .text(d => d);
}

function recreateAllCharts() {
  if (trendChartInstance) trendChartInstance.destroy();
  if (punctualityChartInstance) punctualityChartInstance.destroy();
  if (deptChartInstance) deptChartInstance.destroy();
  if (pieChartInstance) pieChartInstance.destroy();
  loadCharts();
}
