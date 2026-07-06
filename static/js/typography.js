/* ── Font Size Controls (Issue #6/#12) ── */
function setFontSize(delta) {
  var html = document.documentElement;
  html.classList.remove('font-small', 'font-normal', 'font-large');
  if (delta < 0) html.classList.add('font-small');
  else if (delta > 0) html.classList.add('font-large');
  else html.classList.add('font-normal');
  localStorage.setItem('fontSize', delta < 0 ? 'small' : delta > 0 ? 'large' : 'normal');
}

(function() {
  var saved = localStorage.getItem('fontSize');
  if (saved === 'small') document.documentElement.classList.add('font-small');
  else if (saved === 'large') document.documentElement.classList.add('font-large');
  else document.documentElement.classList.add('font-normal');
})();
