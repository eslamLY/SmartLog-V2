/* ── Notification Interval Controls (Issue #6/#12) ── */
var notifIntervalId = null;

function setNotifInterval(ms) {
  if (notifIntervalId) {
    clearInterval(notifIntervalId);
    notifIntervalId = null;
  }
  localStorage.setItem('notifInterval', ms);
  if (ms > 0) {
    if (typeof updateNotifBadge === 'function') updateNotifBadge();
    notifIntervalId = setInterval(function() {
      if (typeof updateNotifBadge === 'function') updateNotifBadge();
    }, ms);
  }
}

(function() {
  var saved = parseInt(localStorage.getItem('notifInterval') || '30000');
  var select = document.getElementById('notifIntervalSelect');
  if (select) select.value = String(saved);
  if (saved > 0) setNotifInterval(saved);
})();
