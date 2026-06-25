# DEPLOYMENT CHECKLIST

## Pre-Deployment Verification

### 1. Syntax Verification
- [x] `node --check static/js/dashboard.js` → No errors
- [x] `node --check static/js/promotions.js` → No errors
- [x] `node --check static/js/app.js` → No errors
- [x] `python -c "compile('config.py')"` → No errors
- [x] `python -c "compile('routes/dashboard.py')"` → No errors
- [x] `python -c "compile('routes/auth.py')"` → No errors

### 2. Security Headers (config.py)
- [x] CSP includes all CDNs: `cdn.jsdelivr.net`, `cdnjs.cloudflare.com`, `fonts.googleapis.com`, `fonts.gstatic.com`, `unpkg.com`, `cdn.datatables.net`, `d3js.org`, `*.tile.openstreetmap.org`
- [x] CSP directives: default-src, script-src, style-src, img-src, font-src, connect-src, frame-ancestors, base-uri, form-action, object-src, upgrade-insecure-requests
- [x] `connect-src 'self' https:` allows API calls
- [x] `img-src 'self' data: blob: https:` allows map tiles

### 3. API Error Handling
- [x] All 15 `/api/dashboard/*` endpoints wrapped with `@safe_json_response`
- [x] All endpoints return `{'ok': False, 'msg': str, 'data': []}` on error
- [x] Errors logged via `LOGGER.error`

### 4. Frontend Resilience
- [x] `safeApiCall()` helper added — validates HTTP 200, JSON parse, `ok` flag
- [x] All 15 fetch calls in `dashboard.js` use `safeApiCall`
- [x] Null-safety: every `.then(d => ...)` checks `if (!d) return;` first
- [x] Each chart/UI function gracefully skips rendering when data is null

### 5. Service Worker
- [x] SW registered at `/sw.js` (not `/static/sw.js`)
- [x] Route serves `static/sw.js` file with `Service-Worker-Allowed: /` header
- [x] Proper `Content-Type: application/javascript` set

### 6. CSRF
- [x] `base.html` `api()` function sends `X-CSRFToken` header
- [x] `geofence_management.html` fixed to include CSRF
- [x] `leave_management.html` fixed to include CSRF

## Deployment Steps

```
git add -A
git commit -m "Security & stability: CSP whitelist, API error handling, frontend resilience"
git push
```

After push, Render auto-deploys (autoDeploy: true in render.yaml).

## Post-Deployment Verification (in Browser DevTools)

### Console Tab
- [ ] No red errors
- [ ] No CSP violation warnings
- [ ] No "Refused to load" messages
- [ ] SW registered: `✓ SW registered` log

### Network Tab
- [ ] `/api/dashboard/stats` returns 200
- [ ] All chart endpoints return 200
- [ ] `/api/dashboard/map` returns 200
- [ ] Fonts load from `fonts.gstatic.com`
- [ ] Tabler Icons load from `cdn.jsdelivr.net`

### Visual
- [ ] All icons display (Tabler Icons + Font Awesome)
- [ ] Fonts render correctly (Cairo font)
- [ ] Dashboard loads without blank sections
- [ ] Map displays (if Leaflet data present)
- [ ] Charts render (if Chart.js data present)

### Application Tab (PWA)
- [ ] Service Worker registered with scope `/`
- [ ] Can install app on mobile

## Rollback Plan

If deployment fails:
1. Revert to previous commit: `git revert HEAD --no-edit && git push`
2. Or: `git reset --hard HEAD~1 && git push --force`

If CSP blocks legitimate content:
- Edit `config.py` `CDN_WHITELIST` or `CSP_IMG_EXTRA` set
- Add missing domain
- Commit and push (auto-deploys)

If API errors appear:
- Check Render logs for `API error in` messages
- Identify the failing endpoint
- Add try/except if missing
