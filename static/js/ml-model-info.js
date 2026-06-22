/**
 * static/js/ml-model-info.js — Model information and management UI.
 * Displays model registry, training history, and performance metrics.
 */

async function loadModelDetails() {
  var container = document.getElementById('modelInfoContainer');
  if (!container) return;
  try {
    var [models, perf] = await Promise.all([
      getJSON('/api/forecast/models'),
      getJSON('/api/forecast/models/performance'),
    ]);
    var html = '';
    (models.models || []).forEach(function (m) {
      var p = (perf.performance || []).find(function (x) { return x.model_key === m.key; });
      html += '<div class="f-model-card">';
      html += '<div class="f-model-header"><span class="f-model-name">' + m.key + '</span><span class="f-badge f-badge-green">نشط</span></div>';
      html += '<div class="f-model-details">';
      html += '<div class="f-stat-row"><span class="f-stat-label">النوع</span><span class="f-stat-value">' + m.type + '</span></div>';
      html += '<div class="f-stat-row"><span class="f-stat-label">آخر تدريب</span><span class="f-stat-value">' + (m.training_date || '—') + '</span></div>';
      if (p) {
        html += '<div class="f-stat-row"><span class="f-stat-label">الدقة (30 يوم)</span><span class="f-stat-value"><span style="color:' + (p.avg_accuracy >= 85 ? '#22c55e' : p.avg_accuracy >= 70 ? '#f59e0b' : '#ef4444') + ';font-weight:700">' + p.avg_accuracy + '%</span></span></div>';
        html += '<div class="f-stat-row"><span class="f-stat-label">التنبؤات</span><span class="f-stat-value">' + (p.total_predictions || 0) + '</span></div>';
      }
      if (m.metrics && m.metrics.n_features) {
        html += '<div class="f-stat-row"><span class="f-stat-label">الميزات</span><span class="f-stat-value">' + m.metrics.n_features + '</span></div>';
      }
      html += '</div></div>';
    });
    if (!models.models || !models.models.length) html = '<p style="color:var(--muted)">لا توجد نماذج مسجلة. قم بتدريب النماذج أولاً.</p>';
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '<p style="color:var(--red)">❌ خطأ في تحميل معلومات النماذج: ' + e.message + '</p>';
  }
}

async function computeAccuracyForAll() {
  var models = ['leave_prediction', 'absence_prediction', 'turnover_prediction', 'shortage_prediction', 'hiring_prediction'];
  var results = [];
  for (var key of models) {
    try {
      var r = await postJSON('/api/forecast/models/compute-accuracy', { model_key: key });
      results.push(r);
    } catch (e) {
      results.push({ model_key: key, error: e.message });
    }
  }
  var container = document.getElementById('accuracyResults');
  if (!container) return;
  var html = '<table class="f-table"><thead><tr><th>النموذج</th><th>الدقة</th><th>الضبط</th><th>الاستدعاء</th><th>F1</th></tr></thead><tbody>';
  results.forEach(function (r) {
    if (r.error) {
      html += '<tr><td>' + r.model_key + '</td><td colspan="4" style="color:var(--red)">' + r.error + '</td></tr>';
    } else {
      html += '<tr><td>' + r.model_key + '</td><td>' + (r.accuracy * 100).toFixed(1) + '%</td><td>' + (r.precision * 100).toFixed(1) + '%</td><td>' + (r.recall * 100).toFixed(1) + '%</td><td>' + (r.f1_score * 100).toFixed(1) + '%</td></tr>';
    }
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', function () {
  if (document.getElementById('modelInfoContainer')) loadModelDetails();
});
