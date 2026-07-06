/* ── Arabic Date Formatting (Issue #14) ── */
function formatArabicDate(date) {
  return new Intl.DateTimeFormat('ar-SA', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }).format(date);
}
