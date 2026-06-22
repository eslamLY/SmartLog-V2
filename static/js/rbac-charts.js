function renderRoleChart(data) {
  var cv = document.getElementById('rolesChart');
  if(!cv || !data || !data.length) return;
  var ctx = cv.getContext('2d');
  if(window._roleChart) window._roleChart.destroy();
  window._roleChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(function(d){return d.role}),
      datasets: [{
        data: data.map(function(d){return d.count}),
        backgroundColor: ['#6366f1','#22c55e','#f59e0b','#ef4444','#06b6d4','#a855f7','#ec4899','#14b8a6','#f97316','#8b5cf6'],
        borderWidth: 0,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position:'bottom', labels:{color:'#94a3b8',padding:12,usePointStyle:true} } },
      cutout: '60%',
    }
  });
}
