/* ── Form Progress Tracker (Issue #11) ── */
function updateFormProgress(currentTabIndex) {
  var tabs = ['basic', 'personal', 'employment', 'biometric', 'financial', 'access'];
  var total = tabs.length;
  var pct = Math.round(((currentTabIndex + 1) / total) * 100);
  var fill = document.getElementById('formProgress');
  if (fill) fill.style.width = pct + '%';
  var steps = document.querySelectorAll('.form-progress .step');
  steps.forEach(function(el, i) {
    el.classList.remove('active', 'completed');
    if (i < currentTabIndex) el.classList.add('completed');
    else if (i === currentTabIndex) el.classList.add('active');
  });
  var counter = document.getElementById('addTabProgress');
  if (counter) counter.textContent = (currentTabIndex + 1) + '/' + total;
}
