# SmartLog V2 — Static File & Icon Deployment Guide

## Problem: Icons/static files missing on Render

**Symptoms:**
- Icons show as empty squares or nothing on Render
- Styles/CSS not loading on Render
- Network tab shows 404 for `/static/css/*` or `/static/js/*`
- Console shows CSP errors like `Refused to load font from 'https://cdnjs.cloudflare.com...'`
- Everything works fine on local machine

**Root Causes:**
1. **Hardcoded paths** — Templates use `href="/static/css/style.css"` instead of `{{ url_for('static', filename='css/style.css') }}`
2. **CSP blocks CDNs** — `font-src 'self'` blocks Font Awesome's CDN fonts; `style-src` only allows `cdn.jsdelivr.net` but Font Awesome is on `cdnjs.cloudflare.com`
3. **No cache busting** — Browsers cache old versions aggressively on Render
4. **Mixed icon libraries** — Tabler Icons (base templates) + Font Awesome (admin templates) = two CDN dependencies that both need CSP allowances

---

## Solution: 10 Files Changed

### 1. `config.py` — Static file configuration
- Added `CDN_WHITELIST` set for all allowed CDN origins
- Added `csp_string()` class method that generates the full CSP header
- Added `SEND_FILE_MAX_AGE_DEFAULT` for production caching
- Added `STATIC_FOLDER` and `STATIC_URL` config fields

### 2. `app.py` — Updated static serving
- Added `app.static_folder` and `app.static_url_path` explicit settings
- Registered `@app.context_processor` to inject `static_url()`, `icon()`, `icon_html()` into all templates
- Added `/api/health/static` endpoint to verify all static files
- Fixed CSP header to use `config.ProductionConfig.csp_string()` which includes all CDNs

### 3. `templates/base.html` — url_for() for all paths
- All static references changed: `href="/static/..."` → `href="{{ url_for('static', filename='...') }}"`
- Added cache-busting `?v={{ static_version }}` to CSS and JS includes
- Added Font Awesome CDN alongside Tabler Icons
- Added `{% block extra_head %}` for page-specific icon/CDN includes

### 4. `utils/icon_helper.py` — Icon management utilities
- `static_url(path)` — Generates `/static/path?v=hash` with cache busting
- `icon(name, fallback)` — Returns CSS class for semantic icon names
- `icon_html(name, fallback, extra_style)` — Returns complete `<i>` tag
- `needed_cdn_libs(classes)` — Determines which CDN CSS to load based on icon prefixes
- `ICON_MAP` — Maps semantic names to Tabler Icons classes
- `update_template_with_url_for(content)` — Auto-converts hardcoded paths to url_for

### 5. `static/css/style.css` — Consolidated stylesheet
- All paths relative (e.g., `url('../icons/icon.svg')` not `url('/static/icons/icon.svg')`)
- Icon-loading skeleton animation
- Print styles to hide CDN icons
- Utility icon classes (`.icon-lg`, `.icon-xl`, `.icon-spin`, etc.)

### 6. `.gitignore` — Ensure static/ is tracked
- Added explicit comment block ensuring static/ is NOT ignored
- Developers can verify with `git ls-files static/`

### 7. `static_file_checker.py` — Verification script
- Checks all required static files exist
- Validates manifest.json icon paths
- Scrapes templates for hardcoded paths
- Tests CDN reachability
- Exits with code 1 if any issue found

### 8. `Procfile` — Render process config
- Optimized workers/threads for Render (2 workers × 4 threads)
- Added `--log-level` support
- Added troubleshooting comments

### 9. `render.yaml` — Render infrastructure
- Added CSP verification steps in comments
- Added Before/After migration examples
- Optimized worker settings

### 10. `deployment_guide.md` — This file
- Complete troubleshooting guide
- Step-by-step testing procedures
- Network tab debugging instructions

---

## Step-by-Step Testing Procedures

### Before Deploying

```bash
# 1. Run the static file checker
python static_file_checker.py

# 2. Check for hardcoded paths in templates
python static_file_checker.py --mode templates

# 3. Verify static files are tracked in git
git ls-files static/ | head -10

# 4. If static/ is missing from git:
git add -f static/
git commit -m "fix: track static/ directory for Render deployment"
```

### After Deploying to Render

```bash
# 5. Check static health endpoint
curl https://your-app.onrender.com/api/health/static

# Expected:
# {"status": "ok", "all_ok": true, "count_css": 16, "count_js": 30}

# 6. Check the main health endpoint
curl https://your-app.onrender.com/api/health
```

### Browser Testing

1. Open the deployed app
2. Open DevTools → **Network tab**
3. **Hard refresh** (Ctrl+Shift+R / Cmd+Shift+R)
4. Filter by "css", "js", "svg", "ico"
5. Verify **zero 404 errors**
6. Check the **Console tab** for CSP errors:
   - `Refused to load font` → fix `font-src` in CSP
   - `Refused to load style` → fix `style-src` in CSP
   - `Refused to load script` → fix `script-src` in CSP
7. **Reload the page** — icons should persist
8. **Clear cache & hard reload** — icons should still work
9. **Test in Chrome, Firefox, Edge** — all should show icons

### Render Logs Check

```bash
# Using Render CLI
render logs --tail

# Or in Dashboard:
# Service → Logs → search for "static", "404", "icon"
```

Look for:
- `GET /static/css/style.css` → 200 OK (not 404)
- No `ModuleNotFoundError` for `icon_helper`
- No CSP violation messages

---

## Network Tab Debugging Guide

| Column | What to look for | Meaning |
|--------|------------------|---------|
| Name | `/static/css/style.css` | Should match `url_for('static', filename='css/style.css')` |
| Status | `200` | File found and served |
| Status | `304` | Cached — OK |
| Status | **`404`** | File not found — check `static/` folder |
| Type | `stylesheet` | CSS loaded successfully |
| Type | `script` | JS loaded successfully |
| Initiator | `base.html:14` | Shows which template requested it |

### Common 404 Causes
- `static/` not committed to git → `git add -f static/`
- Path typo in template → use `url_for()` to avoid
- Case sensitivity on Render (Linux) → `Style.css` vs `style.css`
- Missing file extension → `style` vs `style.css`

---

## CSP Error Fixes

**Console Error:** `Refused to load font from 'https://cdnjs.cloudflare.com/...'`

**Fix:** Update CSP in `config.py` to include the CDN:

```python
# config.py — ProductionConfig
CDN_WHITELIST = {
    'cdn.jsdelivr.net',          # Tabler Icons, SweetAlert2
    'cdnjs.cloudflare.com',       # Font Awesome
    'fonts.googleapis.com',       # Google Fonts (Cairo)
    'fonts.gstatic.com',          # Google Fonts (Cairo)
}
```

Then in the CSP header:
```
font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com;
```

---

## Cache Handling Strategies

| Strategy | Implementation | Effect |
|----------|---------------|--------|
| **Cache busting** | `?v={{ static_version }}` | Forces new download on each deploy |
| **Content hash** | `static_url('css/style.css')` → `/static/css/style.css?v=a1b2c3d4` | Changes only when file changes |
| **Long cache (production)** | `SEND_FILE_MAX_AGE_DEFAULT = 86400` | 24-hour browser cache |
| **Short cache (development)** | `SEND_FILE_MAX_AGE_DEFAULT = 3600` | 1-hour browser cache |

---

## File Permission Fixes

On Render (Linux), ensure static files have correct permissions:

```bash
# In Render Shell or Dockerfile
chmod -R 755 /opt/render/project/src/static/
chmod 644 /opt/render/project/src/static/*/*

# Verify
ls -la /opt/render/project/src/static/
```

In the Dockerfile:
```dockerfile
RUN chmod -R a+rX /opt/render/project/src/static/
```

---

## Directory Structure (static/)

```
static/
├── css/
│   ├── backup-premium.css
│   ├── dashboard.css
│   ├── departments.css
│   ├── devices.css
│   ├── employee-form-premium.css
│   ├── employees.css
│   ├── forecasting-premium.css
│   ├── offline-mode.css
│   ├── payroll-premium.css
│   ├── payroll-print.css
│   ├── pwa.css
│   ├── rbac-premium.css
│   ├── reports-premium.css
│   ├── reports-responsive.css
│   ├── reports.css
│   ├── style.css              ← NEW: consolidated styles
│   └── tracking-premium.css
├── icons/
│   ├── icon-192.svg
│   └── icon-512.svg
├── js/
│   ├── ai-forecasting.js
│   ├── app.js
│   ├── ... (30 JS files)
│   └── tracking-realtime.js
├── manifest.json
└── sw.js
```

---

## Verification Checklist

- [ ] `python static_file_checker.py` passes with no errors
- [ ] `git ls-files static/` shows all static files tracked
- [ ] No hardcoded `/static/` paths in templates
- [ ] `url_for('static', filename='...')` used everywhere
- [ ] CSP header includes all CDN origins (jsdelivr, cloudflare, googleapis)
- [ ] `font-src` allows Font Awesome and Google Fonts
- [ ] Cache busting (`?v=`) on all static includes
- [ ] `/api/health/static` returns `{"status": "ok"}`
- [ ] Browser Network tab shows zero 404s
- [ ] Browser Console tab shows zero CSP errors
- [ ] Icons persist after hard refresh
- [ ] Icons work in Chrome, Firefox, Edge
- [ ] Icons work on mobile device
- [ ] Render logs show no static file errors
- [ ] `render.yaml` has correct environment variables

---

## Troubleshooting Flowchart

```
Icons missing on Render
├─ Check Browser Console
│  ├─ CSP errors? → Update CDN_WHITELIST in config.py → Redeploy
│  └─ No CSP errors
│     └─ Check Network tab
│        ├─ 404 on /static/*? → url_for() not used → Fix base.html
│        ├─ 404 on CDN url? → CDN down or blocked → Check firewall
│        └─ No requests at all? → Cache issue → Hard refresh
├─ Check Render Logs
│  ├─ 404 in logs? → static/ not in git → git add -f static/
│  └─ No 404s
│     └─ Check /api/health/static
│        ├─ all_ok: false? → Missing files → Re-run static_file_checker.py
│        └─ all_ok: true → CSP issue → Check Content-Security-Policy header
└─ Check Local
   ├─ Works locally? → Deployment issue → Redeploy
   └─ Broken locally too? → Missing files → Rebuild static/
```

---

## Before/After Code Examples

### Before (Broken on Render):
```html
<!-- base.html — hardcoded paths -->
<link rel="stylesheet" href="/static/css/pwa.css">
<script src="/static/js/app.js"></script>
<link rel="apple-touch-icon" href="/static/icons/icon-192.svg">
```

### After (Works on Render):
```html
<!-- base.html — url_for() -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/pwa.css') }}?v={{ static_version }}">
<script src="{{ url_for('static', filename='js/app.js') }}?v={{ static_version }}" defer></script>
<link rel="apple-touch-icon" href="{{ url_for('static', filename='icons/icon-192.svg') }}">
```

### Before (CSP blocking CDNs):
```python
response.headers['Content-Security-Policy'] = (
    "font-src 'self'; "            # BLOCKS Font Awesome CDN fonts
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "  # BLOCKS Font Awesome CSS
)
```

### After (CSP allows all CDNs):
```python
response.headers['Content-Security-Policy'] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
    "img-src 'self' data: blob: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
    "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)
```

---

## Quick Reference

```bash
# Run checker
python static_file_checker.py

# Check template paths
python static_file_checker.py --mode templates

# Track static files
git ls-files static/
git add -f static/
git status

# Test health
curl https://your-app.onrender.com/api/health/static

# View Render logs
render logs
# Or: Dashboard → Service → Logs
```

If issues persist after following this guide, check:
1. Render service region (may affect CDN latency, not availability)
2. Render plan limits (free tier may throttle requests)
3. Docker image layers (ensure COPY includes static/)
