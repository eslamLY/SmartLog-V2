var realtimeInterval = null;
var lastFetchTs = 0;
var currentEmployeeFilter = '';
var trackData = {};

function initRealtimeTracking(data) {
  trackData = data;
  realtimeInterval = setInterval(fetchLiveLocations, 5000);
  fetchLiveLocations();
  updateClock();
  setInterval(updateClock, 1000);
}

function fetchLiveLocations() {
  var url = '/api/admin/gps/live?since=' + lastFetchTs;
  if (currentEmployeeFilter) url += '&employee_id=' + currentEmployeeFilter;
  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(resp) {
      if (resp.ok) {
        updateLiveUI(resp.data);
        lastFetchTs = Date.now();
      }
    })
    .catch(function(err) {
      console.error('Realtime fetch error:', err);
    });
}

function updateLiveUI(logs) {
  var uniqueEmployees = {};
  var activeIds = [];
  logs.forEach(function(l) {
    if (!uniqueEmployees[l.employee_id]) {
      uniqueEmployees[l.employee_id] = {
        employee_id: l.employee_id,
        employee_name: l.employee_name,
        lat: l.lat,
        lng: l.lng,
        accuracy: l.accuracy,
        battery: l.battery,
        source: l.source,
        created_at: l.created_at
      };
      activeIds.push(l.employee_id);
    } else {
      var existing = uniqueEmployees[l.employee_id];
      if (new Date(l.created_at) > new Date(existing.created_at)) {
        existing.lat = l.lat;
        existing.lng = l.lng;
        existing.accuracy = l.accuracy;
        existing.battery = l.battery;
        existing.source = l.source;
        existing.created_at = l.created_at;
      }
    }
  });
  Object.values(uniqueEmployees).forEach(function(emp) {
    addEmployeeMarker(emp);
  });
  removeOldMarkers(activeIds);
  var onlineCount = Object.keys(uniqueEmployees).length;
  document.getElementById('statOnline').textContent = onlineCount;
  document.getElementById('qsOnline').textContent = onlineCount;
  document.getElementById('metaOnline').textContent = onlineCount;
  document.getElementById('liveCount').textContent = onlineCount + ' متصل';
  document.getElementById('livePanelCount').textContent = logs.length;
  updateEmployeeStatusIndicators(activeIds);
  buildLiveCards(logs);
  if (autoCenter && onlineCount > 0) {
    fitMapToAll();
  }
}

function updateEmployeeStatusIndicators(activeIds) {
  document.querySelectorAll('.employee-list-item').forEach(function(item) {
    var empId = parseInt(item.getAttribute('onclick').match(/\d+/)[0]);
    var dot = item.querySelector('.status-dot');
    if (activeIds.indexOf(empId) !== -1) {
      dot.className = 'status-dot online';
    } else {
      dot.className = 'status-dot offline';
    }
  });
}

function buildLiveCards(logs) {
  var grid = document.getElementById('liveGrid');
  if (!grid) return;
  if (logs.length === 0) {
    grid.innerHTML = '<div class="empty-state-mini"><i class="ti ti-map-off"></i><p>لا توجد مواقع مباشرة حالياً</p></div>';
    return;
  }
  var seen = {};
  var html = '';
  logs.forEach(function(l) {
    if (seen[l.employee_id]) return;
    seen[l.employee_id] = true;
    var timeAgo = getTimeAgo(l.created_at);
    html += '<div class="live-card" data-employee-id="' + l.employee_id + '" onclick="focusEmployee(' + l.employee_id + ')">' +
      '<div class="live-card-header">' +
      '<span class="live-indicator online"></span>' +
      '<span class="live-name">' + escapeHtml(l.employee_name) + '</span>' +
      '<span class="live-time">' + timeAgo + '</span></div>' +
      '<div class="live-coords">' + l.lat.toFixed(6) + ', ' + l.lng.toFixed(6) + '</div>' +
      '<div class="live-meta">' +
      '<span>🎯 ' + (l.accuracy || '?') + 'م</span>' +
      (l.battery ? '<span>🔋 ' + l.battery + '%</span>' : '') +
      '<span>' + escapeHtml(l.source || 'app') + '</span></div></div>';
  });
  grid.innerHTML = html;
}

function filterEmployee(val) {
  currentEmployeeFilter = val;
  clearEmployeeMarkers();
  fetchLiveLocations();
}

function refreshNow() {
  fetchLiveLocations();
  var btn = document.querySelector('.track-header-actions .btn-outline');
  if (btn) {
    btn.innerHTML = '<i class="ti ti-refresh"></i> تم';
    setTimeout(function() {
      btn.innerHTML = '<i class="ti ti-refresh"></i> تحديث';
    }, 2000);
  }
}

function acknowledgeAlert(alertId) {
  fetch('/api/admin/alerts/' + alertId + '/acknowledge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  }).then(function(r) { return r.json(); }).then(function(resp) {
    if (resp.ok) {
      var el = document.querySelector('.alert-item[data-alert-id="' + alertId + '"]');
      if (el) el.style.opacity = '0.4';
      toast(resp.msg, 'ok');
      updateAlertBadge();
    }
  });
}

function updateAlertBadge() {
  var count = document.querySelectorAll('.alert-item').length;
  var badge = document.getElementById('alertBadge');
  if (badge) badge.textContent = count;
}

function updateClock() {
  var el = document.getElementById('metaUpdated');
  if (el) el.textContent = new Date().toLocaleTimeString('ar-SA');
}

function getTimeAgo(isoStr) {
  var now = new Date();
  var then = new Date(isoStr);
  var diff = Math.floor((now - then) / 1000);
  if (diff < 60) return 'الآن';
  if (diff < 3600) return Math.floor(diff / 60) + 'د';
  if (diff < 86400) return Math.floor(diff / 3600) + 'س';
  return Math.floor(diff / 86400) + 'ي';
}

function escapeHtml(str) {
  if (!str) return '';
  var div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function exportGPSCSV() {
  var rows = [['الموظف','خط العرض','خط الطول','الدقة','البطارية','المصدر','الوقت']];
  document.querySelectorAll('#historyBody tr').forEach(function(tr) {
    var tds = tr.querySelectorAll('td');
    if (tds.length >= 7) {
      rows.push([
        tds[0].textContent.trim(),
        tds[1].textContent.trim(),
        tds[2].textContent.trim(),
        tds[3].textContent.trim(),
        tds[4].textContent.trim(),
        tds[5].textContent.trim(),
        tds[6].textContent.trim()
      ]);
    }
  });
  var csv = rows.map(function(r) {
    return r.map(function(c) { return '"' + c.replace(/"/g, '""') + '"'; }).join(',');
  }).join('\n');
  var blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  var link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'gps_tracking_' + new Date().toISOString().slice(0,10) + '.csv';
  link.click();
}

function loadHistory() {
  var dateEl = document.getElementById('historyDate');
  if (!dateEl) return;
  var date = dateEl.value;
  var empId = currentEmployeeFilter || '';
  var url = '/api/admin/gps/history?date=' + date;
  if (empId) url += '&employee_id=' + empId;
  fetch(url).then(function(r) { return r.json(); }).then(function(resp) {
    if (resp.ok) {
      var tbody = document.getElementById('historyBody');
      if (!resp.data || resp.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted)">لا توجد بيانات لهذا التاريخ</td></tr>';
        return;
      }
      var html = '';
      resp.data.forEach(function(l) {
        html += '<tr>' +
          '<td>' + escapeHtml(l.employee_name || '') + '</td>' +
          '<td style="direction:ltr;font-family:monospace">' + l.lat + '</td>' +
          '<td style="direction:ltr;font-family:monospace">' + l.lng + '</td>' +
          '<td>' + (l.accuracy || '—') + 'م</td>' +
          '<td>' + (l.battery != null ? l.battery + '%' : '—') + '</td>' +
          '<td>' + (l.source || 'app') + '</td>' +
          '<td style="font-size:11px;direction:ltr">' + new Date(l.created_at).toLocaleString('ar-SA') + '</td>' +
          '<td><button class="btn btn-xs btn-ghost" onclick="showOnMap(' + l.lat + ',' + l.lng + ')"><i class="ti ti-eye"></i></button></td>' +
          '</tr>';
      });
      tbody.innerHTML = html;
    }
  });
}

function switchTrackTab(tab, btn) {
  document.querySelectorAll('.track-tab').forEach(function(t) { t.classList.remove('active'); });
  document.querySelectorAll('.track-panel').forEach(function(p) { p.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  var panel = document.getElementById(tab + 'Panel');
  if (panel) panel.classList.add('active');
}
