/**
 * static/js/forecasting-api.js — API interaction layer for the forecasting dashboard.
 * Handles all backend calls, data formatting, and UI updates.
 */
const API_BASE = '';
function $(id) { return document.getElementById(id); }
function qs(s, p) { return (p || document).querySelector(s); }
function qsa(s, p) { return (p || document).querySelectorAll(s); }

function getCSRFToken() {
  var meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

function apiHeaders() {
  return { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() };
}

async function getJSON(url) {
  var r = await fetch(API_BASE + url, { headers: apiHeaders() });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function postJSON(url, data) {
  var r = await fetch(API_BASE + url, {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ─── TABS ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  qsa('.f-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      var name = tab.dataset.tab;
      qsa('.f-tab').forEach(function (t) { t.classList.remove('active'); });
      tab.classList.add('active');
      qsa('.f-content').forEach(function (c) { c.classList.remove('active'); });
      var target = document.getElementById('tab-' + name);
      if (target) target.classList.add('active');
      if (name === 'dashboard') loadDashboard();
      if (name === 'predictions') loadPredictionsTab();
      if (name === 'models') loadModelsTab();
      if (name === 'rules') loadRules();
      if (name === 'anomalies') loadAnomalies();
      if (name === 'segments') loadSegmentation();
      if (name === 'correlation') loadCorrelation();
    });
  });
  loadDashboard();
});

// ─── DASHBOARD ─────────────────────────────────────────────
async function loadDashboard() {
  var grid = document.getElementById('dashGrid');
  if (!grid) return;
  grid.innerHTML = '<div class="f-card f-loading"><div class="f-spinner"></div><p>جاري تحميل لوحة التحكم...</p></div>';
  try {
    var predictions = await postJSON('/api/forecast/generate', {});
    var recs = await getJSON('/api/forecast/recommendations');
    var perf = await getJSON('/api/forecast/models/performance');
    var html = '';
    html += '<div class="f-card f-stat-card"><div class="f-stat-icon" style="background:#8b5cf622;color:#8b5cf6"><i class="ti ti-calendar-check"></i></div><div class="f-stat-number">' + (predictions.leave_predictions || []).length + '</div><div class="f-stat-label">إجازات متوقعة</div></div>';
    html += '<div class="f-card f-stat-card"><div class="f-stat-icon" style="background:#f59e0b22;color:#f59e0b"><i class="ti ti-user-x"></i></div><div class="f-stat-number">' + (predictions.absence_predictions || []).length + '</div><div class="f-stat-label">غياب متوقع</div></div>';
    html += '<div class="f-card f-stat-card"><div class="f-stat-icon" style="background:#ef444422;color:#ef4444"><i class="ti ti-users-x"></i></div><div class="f-stat-number">' + (predictions.turnover_predictions || []).length + '</div><div class="f-stat-label">خطر الرحيل</div></div>';
    html += '<div class="f-card f-stat-card"><div class="f-stat-icon" style="background:#22c55e22;color:#22c55e"><i class="ti ti-alert-triangle"></i></div><div class="f-stat-number">' + (predictions.shortage_warnings || []).length + '</div><div class="f-stat-label">إنذارات النقص</div></div>';
    html += '<div class="f-card f-stat-card"><div class="f-stat-icon" style="background:#6366f122;color:#6366f1"><i class="ti ti-bug"></i></div><div class="f-stat-number">' + (predictions.anomalies || []).length + '</div><div class="f-stat-label">التجاوزات مكتشفة</div></div>';
    html += '<div class="f-card f-stat-card"><div class="f-stat-icon" style="background:#10b98122;color:#10b981"><i class="ti ti-brain"></i></div><div class="f-stat-number">' + ((perf.performance || []).length || 0) + '</div><div class="f-stat-label">نماذج نشطة</div></div>';
    html += '<div class="f-card" style="grid-column:1/-1"><h3>💡 توصيات ذكية</h3>';
    var recommendations = recs.recommendations || [];
    if (recommendations.length) {
      recommendations.slice(0, 5).forEach(function (r) {
        var sev = r.severity || 'info';
        html += '<div class="f-rec f-rec-' + sev + '"><span class="f-rec-icon">' + (r.icon || '💡') + '</span><div><div class="f-rec-title">' + r.title + '</div><div class="f-rec-msg">' + r.message + (r.confidence ? ' <span style="color:#8b5cf6">ثقة: ' + r.confidence + '%</span>' : '') + '</div></div></div>';
      });
    } else { html += '<p style="color:var(--muted)">لا توجد توصيات حالياً</p>'; }
    html += '</div>';
    html += '<div class="f-card" style="grid-column:1/-1"><h3>📊 أداء النماذج</h3><canvas id="dashPerfChart" height="200"></canvas></div>';
    grid.innerHTML = html;
    var perfData = (perf.performance || []).map(function (m) {
      return { model_key: m.model_key, avg_accuracy: m.avg_accuracy, avg_precision: m.avg_precision, avg_recall: m.avg_recall };
    });
    if (perfData.length) setTimeout(function () { renderModelPerformanceChart('dashPerfChart', perfData); }, 100);
  } catch (e) { grid.innerHTML = '<div class="f-card" style="grid-column:1/-1;text-align:center;padding:40px;color:var(--red)">❌ خطأ: ' + e.message + '</div>'; }
}

// ─── PREDICTIONS TAB ───────────────────────────────────────
async function loadPredictionsTab() {
  var grid = document.getElementById('predGrid');
  if (!grid) return;
  try {
    var data = await postJSON('/api/forecast/generate', {});
    var html = '<div class="f-card" style="grid-column:1/-1"><h3>🔮 تنبؤات الإجازات</h3>';
    (data.leave_predictions || []).slice(0, 10).forEach(function (p) {
      html += '<div class="f-stat-row"><span class="f-stat-label">' + p.employee_name + ' (' + p.department + ')</span><span class="f-stat-value"><span class="f-badge f-badge-' + (p.risk_level === 'high' ? 'red' : p.risk_level === 'medium' ? 'amber' : 'green') + '">' + (p.probability * 100).toFixed(0) + '%</span></span></div>';
    });
    html += '</div><div class="f-card" style="grid-column:1/-1"><h3>🔮 تنبؤات الغياب</h3>';
    (data.absence_predictions || []).slice(0, 10).forEach(function (p) {
      html += '<div class="f-stat-row"><span class="f-stat-label">' + p.employee_name + ' (' + p.department + ')</span><span class="f-stat-value"><span class="f-badge f-badge-' + (p.risk_level === 'high' ? 'red' : p.risk_level === 'medium' ? 'amber' : 'green') + '">' + (p.risk_score * 100).toFixed(0) + '%</span></span></div>';
    });
    html += '</div><div class="f-card" style="grid-column:1/-1"><h3>🔮 تنبؤات الرحيل</h3>';
    (data.turnover_predictions || []).slice(0, 10).forEach(function (p) {
      html += '<div class="f-stat-row"><span class="f-stat-label">' + p.employee_name + ' (' + p.department + ')</span><span class="f-stat-value"><span class="f-badge f-badge-' + (p.risk_level === 'high' ? 'red' : p.risk_level === 'medium' ? 'amber' : 'green') + '">' + (p.risk_score * 100).toFixed(0) + '%</span></span></div>';
    });
    html += '</div>';
    grid.innerHTML = html;
  } catch (e) { grid.innerHTML = '<div class="f-card" style="grid-column:1/-1;text-align:center;padding:40px;color:var(--red)">❌ خطأ: ' + e.message + '</div>'; }
}

// ─── MODELS TAB ────────────────────────────────────────────
async function loadModelsTab() {
  var grid = document.getElementById('modelGrid');
  if (!grid) return;
  try {
    var [models, perf] = await Promise.all([getJSON('/api/forecast/models'), getJSON('/api/forecast/models/performance')]);
    var html = '<div class="f-card" style="grid-column:1/-1"><h3>🤖 النماذج المسجلة</h3><table class="f-table"><thead><tr><th>النموذج</th><th>النوع</th><th>تاريخ التدريب</th><th>الحالة</th></tr></thead><tbody>';
    (models.models || []).forEach(function (m) {
      html += '<tr><td>' + m.key + '</td><td>' + m.type + '</td><td>' + (m.training_date || '—') + '</td><td><span class="f-badge f-badge-green">نشط</span></td></tr>';
    });
    html += '</tbody></table></div>';
    html += '<div class="f-card" style="grid-column:1/-1"><h3>📈 أداء النماذج (آخر 30 يوم)</h3><table class="f-table"><thead><tr><th>النموذج</th><th>الدقة</th><th>الضبط</th><th>الاستدعاء</th><th>F1</th><th>التنبؤات</th></tr></thead><tbody>';
    (perf.performance || []).forEach(function (m) {
      html += '<tr><td>' + m.model_key + '</td><td><span style="color:' + (m.avg_accuracy >= 85 ? '#22c55e' : m.avg_accuracy >= 70 ? '#f59e0b' : '#ef4444') + ';font-weight:700">' + m.avg_accuracy + '%</span></td><td>' + (m.avg_precision || 0) + '%</td><td>' + (m.avg_recall || 0) + '%</td><td>' + (m.avg_f1 || 0) + '%</td><td>' + (m.total_predictions || 0) + '</td></tr>';
    });
    html += '</tbody></table></div>';
    html += '<div class="f-card" style="grid-column:1/-1"><canvas id="perfRadarChart" height="250"></canvas></div>';
    grid.innerHTML = html;
    if ((perf.performance || []).length) setTimeout(function () { renderModelPerformanceChart('perfRadarChart', perf.performance); }, 100);
  } catch (e) { grid.innerHTML = '<div class="f-card" style="grid-column:1/-1;text-align:center;padding:40px;color:var(--red)">❌ خطأ: ' + e.message + '</div>'; }
}

// ─── RULES ────────────────────────────────────────────────
async function loadRules() {
  var container = document.getElementById('rulesContainer');
  if (!container) return;
  try {
    var rules = await getJSON('/api/forecast/rules');
    var html = '<table class="f-table"><thead><tr><th>الاسم</th><th>القياس</th><th>الحد</th><th>الحالة</th><th>إجراءات</th></tr></thead><tbody>';
    (rules || []).forEach(function (r) {
      html += '<tr><td>' + r.name + '</td><td>' + r.metric + '</td><td>' + (r.threshold * 100).toFixed(0) + '%</td><td><span class="f-badge f-badge-' + (r.is_active ? 'green' : 'gray') + '">' + (r.is_active ? 'نشط' : 'متوقف') + '</span></td><td><button class="f-btn f-btn-sm f-btn-outline" onclick="toggleRule(' + r.id + ')"><i class="ti ti-toggle"></i></button> <button class="f-btn f-btn-sm f-btn-outline f-btn-red" onclick="deleteRule(' + r.id + ')"><i class="ti ti-trash"></i></button></td></tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
  } catch (e) { container.innerHTML = '<p style="color:var(--red)">❌ ' + e.message + '</p>'; }
}

async function toggleRule(id) {
  try {
    var rules = await getJSON('/api/forecast/rules');
    var rule = rules.find(function (r) { return r.id === id; });
    if (!rule) return;
    await postJSON('/api/forecast/rules/' + id, { is_active: !rule.is_active });
    loadRules();
  } catch (e) { alert('خطأ: ' + e.message); }
}

async function deleteRule(id) {
  if (!confirm('حذف القاعدة؟')) return;
  try {
    await fetch('/api/forecast/rules/' + id, { method: 'DELETE' });
    loadRules();
  } catch (e) { alert('خطأ: ' + e.message); }
}

function showAddRuleModal() {
  var name = prompt('اسم القاعدة:');
  if (!name) return;
  var metric = prompt('القياس (absence_risk, leave_probability, turnover_risk, staffing_below):', 'absence_risk');
  if (!metric) return;
  var threshold = parseFloat(prompt('الحد الأدنى (0.0 - 1.0):', '0.5')) || 0.5;
  var severity = prompt('الخطورة (warning, high, critical):', 'warning') || 'warning';
  postJSON('/api/forecast/rules', {
    rule_name: name, metric: metric, threshold: threshold, severity: severity, is_active: true,
  }).then(function () { loadRules(); }).catch(function (e) { alert('خطأ: ' + e.message); });
}

// ─── ANOMALIES ───────────────────────────────────────────
async function loadAnomalies() {
  var container = document.getElementById('anomaliesContainer');
  if (!container) return;
  try {
    var data = await getJSON('/api/forecast/anomalies');
    var html = '<table class="f-table"><thead><tr><th>النوع</th><th>الوصف</th><th>الخطورة</th><th>الدرجة</th><th>التاريخ</th><th>حل</th></tr></thead><tbody>';
    (data.anomalies || []).forEach(function (a) {
      html += '<tr><td>' + a.anomaly_type + '</td><td>' + a.description + '</td><td><span class="f-badge f-badge-' + (a.severity === 'critical' ? 'red' : a.severity === 'high' ? 'amber' : 'green') + '">' + a.severity + '</span></td><td>' + (a.score * 100).toFixed(0) + '%</td><td>' + (a.detected_date || '—') + '</td><td>' + (a.resolved ? '✅' : '<button class="f-btn f-btn-sm f-btn-accent" onclick="resolveAnomaly(' + a.id + ')">حل</button>') + '</td></tr>';
    });
    html += '</tbody></table>';
    if (!data.anomalies || !data.anomalies.length) html = '<p style="color:var(--muted)">لا توجد تجاوزات في آخر 7 أيام</p>';
    container.innerHTML = html;
  } catch (e) { container.innerHTML = '<p style="color:var(--red)">❌ ' + e.message + '</p>'; }
}

async function scanAnomalies() {
  var container = document.getElementById('anomaliesContainer');
  container.innerHTML = '<div class="f-spinner" style="margin:0 auto"></div>';
  try {
    var result = await postJSON('/api/forecast/anomalies/scan', {});
    container.innerHTML = '<p style="color:#22c55e">✅ تم الفحص: ' + result.stats.anomalies_found + ' تجاوزات مكتشفة</p>';
    loadAnomalies();
  } catch (e) { container.innerHTML = '<p style="color:var(--red)">❌ ' + e.message + '</p>'; }
}

async function resolveAnomaly(id) {
  try {
    await postJSON('/api/forecast/anomalies/' + id + '/resolve', {});
    loadAnomalies();
  } catch (e) { alert('خطأ: ' + e.message); }
}

// ─── SEGMENTATION ────────────────────────────────────────
async function loadSegmentation() {
  var container = document.getElementById('segmentsContainer');
  if (!container) return;
  try {
    var data = await getJSON('/api/forecast/segmentation');
    if (data.error) { container.innerHTML = '<p style="color:var(--muted)">' + data.error + '</p>'; return; }
    var html = '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px">';
    html += '<div class="f-stat-card" style="flex:1;min-width:100px"><div class="f-stat-number">' + data.n_clusters + '</div><div class="f-stat-label">المجموعات</div></div>';
    html += '<div class="f-stat-card" style="flex:1;min-width:100px"><div class="f-stat-number">' + (data.metrics.silhouette_score || 0).toFixed(2) + '</div><div class="f-stat-label">جودة التقسيم</div></div>';
    html += '<div class="f-stat-card" style="flex:1;min-width:100px"><div class="f-stat-number">' + (data.employees || []).length + '</div><div class="f-stat-label">الموظفون</div></div>';
    html += '</div><canvas id="segChart" height="250"></canvas>';
    html += '<table class="f-table" style="margin-top:12px"><thead><tr><th>الموظف</th><th>القسم</th><th>المجموعة</th></tr></thead><tbody>';
    (data.employees || []).forEach(function (e) {
      var colors = ['#8b5cf6', '#f59e0b', '#22c55e', '#ef4444', '#6366f1', '#ec4899'];
      html += '<tr><td>' + e.employee_name + '</td><td>' + e.department + '</td><td><span style="color:' + (colors[e.cluster] || '#8b5cf6') + ';font-weight:700">مجموعة ' + e.cluster + '</span></td></tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
  } catch (e) { container.innerHTML = '<p style="color:var(--red)">❌ ' + e.message + '</p>'; }
}

// ─── CORRELATION ─────────────────────────────────────────
async function loadCorrelation() {
  var container = document.getElementById('correlationContainer');
  if (!container) return;
  try {
    var data = await getJSON('/api/forecast/correlation');
    var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">';
    html += '<div><h4 style="margin-bottom:8px">🔗 عوامل الإجازات</h4>';
    (data.leave_factors || []).forEach(function (f) {
      var c = f.correlation || 0;
      var barW = Math.abs(c) * 100;
      var color = c > 0 ? '#ef4444' : '#22c55e';
      html += '<div class="f-stat-row"><span class="f-stat-label">' + f.factor + '</span><div class="f-bar-track" style="flex:1;margin:0 8px"><div class="f-bar-fill" style="width:' + barW + '%;background:' + color + '"></div></div><span class="f-stat-value" style="color:' + color + '">' + c.toFixed(2) + '</span></div>';
    });
    html += '</div><div><h4 style="margin-bottom:8px">🔗 عوامل الدوران الوظيفي</h4>';
    (data.turnover_factors || []).forEach(function (f) {
      var c = f.correlation || 0;
      var barW = Math.abs(c) * 100;
      var color = c > 0 ? '#ef4444' : '#22c55e';
      html += '<div class="f-stat-row"><span class="f-stat-label">' + f.factor + '</span><div class="f-bar-track" style="flex:1;margin:0 8px"><div class="f-bar-fill" style="width:' + barW + '%;background:' + color + '"></div></div><span class="f-stat-value" style="color:' + color + '">' + c.toFixed(2) + '</span></div>';
    });
    html += '</div></div>';
    if ((!data.leave_factors || !data.leave_factors.length) && (!data.turnover_factors || !data.turnover_factors.length)) html = '<p style="color:var(--muted)">لا توجد بيانات كافية للتحليل</p>';
    container.innerHTML = html;
  } catch (e) { container.innerHTML = '<p style="color:var(--red)">❌ ' + e.message + '</p>'; }
}

// ─── GENERATE PREDICTIONS ────────────────────────────────
async function generatePredictions() {
  var btn = qs('.f-btn-accent i.ti-refresh');
  if (btn) btn.classList.add('f-spin');
  try {
    await postJSON('/api/forecast/generate', {});
    loadDashboard();
  } catch (e) { alert('خطأ: ' + e.message); }
  if (btn) btn.classList.remove('f-spin');
}
