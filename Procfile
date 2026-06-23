# Render Procfile — SmartLog V2
# ==============================
# Static files are served directly by Flask (no nginx needed).
# Ensure static/ folder exists and all paths use url_for().
#
# Troubleshooting:
#   - If icons show 404, check static/ is in git: git ls-files static/
#   - If styles missing, check CSP header allows CDN origins
#   - If 404 after deploy, check Render logs: render logs
#
web: gunicorn app:app \
  --bind 0.0.0.0:${PORT:-5000} \
  --workers ${GUNICORN_WORKERS:-2} \
  --threads ${GUNICORN_THREADS:-4} \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --logger-class gunicorn.glogging.Logger \
  --log-level ${LOG_LEVEL:-info}
