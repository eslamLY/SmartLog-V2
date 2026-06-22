function getFilterParams() {
  const params = new URLSearchParams();
  const preset = document.querySelector('.preset-btn.active');
  if (preset && preset.dataset.preset === 'custom') {
    const sd = document.getElementById('filterStartDate').value;
    const ed = document.getElementById('filterEndDate').value;
    if (sd) params.set('start_date', sd);
    if (ed) params.set('end_date', ed);
  } else if (preset) {
    params.set('preset', preset.dataset.preset);
  }
  const month = document.getElementById('filterMonth');
  const year = document.getElementById('filterYear');
  if (month && month.value) params.set('month', month.value);
  if (year && year.value) params.set('year', year.value);
  const scope = document.querySelector('input[name="scope"]:checked');
  if (scope) {
    params.set('scope', scope.value);
    if (scope.value === 'department') {
      const dept = document.getElementById('filterDepartment');
      if (dept && dept.value) params.set('department_id', dept.value);
    } else if (scope.value === 'employee') {
      const emp = document.getElementById('filterEmployee');
      if (emp && emp.value) params.set('employee_id', emp.value);
    }
  }
  const chips = document.querySelectorAll('#statusChips .chip.active input:checked');
  if (chips.length > 0) {
    params.set('statuses', Array.from(chips).map(c => c.value).join(','));
  }
  const patterns = document.querySelectorAll('.filter-section .chip-group:not(#statusChips) .chip.active input:checked');
  if (patterns.length > 0) {
    params.set('patterns', Array.from(patterns).map(c => c.value).join(','));
  }
  return params.toString();
}

function onFilterChange() {
  loadReports();
}

function setPreset(preset, btn) {
  document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('customDateRange').style.display = preset === 'custom' ? 'flex' : 'none';
  if (preset === 'current_month') {
    const now = new Date();
    document.getElementById('filterMonth').value = now.getMonth() + 1;
    document.getElementById('filterYear').value = now.getFullYear();
  }
  onFilterChange();
}

function toggleScope() {
  const scope = document.querySelector('input[name="scope"]:checked');
  document.querySelectorAll('.radio-pill').forEach(p => p.classList.remove('active'));
  if (scope) scope.closest('.radio-pill').classList.add('active');
  document.getElementById('filterDeptField').style.display = scope && scope.value === 'department' ? 'block' : 'none';
  document.getElementById('filterEmpField').style.display = scope && scope.value === 'employee' ? 'block' : 'none';
  if (scope && scope.value !== 'department') document.getElementById('filterDepartment').value = '';
  if (scope && scope.value !== 'employee') document.getElementById('filterEmployee').value = '';
  onFilterChange();
}

function resetFilters() {
  document.querySelector('.preset-btn[data-preset="current_month"]').click();
  document.querySelector('input[name="scope"][value="all"]').click();
  toggleScope();
  document.querySelectorAll('#statusChips .chip').forEach(c => c.classList.add('active'));
  document.querySelectorAll('#statusChips .chip input').forEach(c => c.checked = true);
  document.querySelectorAll('.filter-section .chip-group:not(#statusChips) .chip').forEach(c => c.classList.remove('active'));
  document.querySelectorAll('.filter-section .chip-group:not(#statusChips) .chip input').forEach(c => c.checked = false);
  document.getElementById('tableSearch').value = '';
  loadReports();
}

function toggleFilters() {
  const panel = document.getElementById('filterPanel');
  const isHidden = panel.style.display === 'none';
  panel.style.display = isHidden ? 'block' : 'none';
  const icon = document.querySelector('#filterToggle i');
  if (icon) icon.className = isHidden ? 'ti ti-adjustments-horizontal' : 'ti ti-adjustments-horizontal';
}
