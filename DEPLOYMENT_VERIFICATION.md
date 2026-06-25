# Deployment Verification — SmartLog V2

## Step 1: Trigger Manual Deploy

1. Open https://dashboard.render.com
2. Select `smartlog-backend`
3. Click **Manual Deploy** → **Deploy latest commit**
4. Wait 2-3 minutes for build + deploy

## Step 2: Verify Deploy Succeeded

```bash
# Check health endpoint
curl https://smartlog-v2-1.onrender.com/api/health
```

Expected:
```json
{"status":"healthy","uptime":"0 days, 0:02:34",...}
```

**Uptime must be < 5 minutes.** If still shows 66 days → deploy failed.

## Step 3: Verify Service Worker

**Browser DevTools (F12):**

### Console Tab
Expected messages in order:
```
🔧 Unregistering old Service Workers...
✓ All Service Workers unregistered
🔄 Clearing cache...
✓ All caches cleared
🔄 Page will reload...
[SW v2.0] Installing Service Worker...
✓ Service Worker registered
```

Must NOT see:
```
✗ TypeError: Failed to convert value to 'Response'
✗ Service Worker registration failed
```

### Application Tab → Service Workers
- Status: **activated and running**
- Scope: `https://smartlog-v2-1.onrender.com/`
- Script: `/sw.js`

### Application Tab → Cache Storage
- ✅ `smartlog-v2.0` exists
- ❌ `smartlog-v1` must NOT exist

### Network Tab → /sw.js
- Status: **200 OK**
- Service-Worker-Allowed: `/`

## Step 4: Run Automated Test

```bash
python test_all_sections.py
```

Expected: `OK: 28/28+  Errors: 0/28+`
(Some endpoints return 404 due to auth, but NO 500 errors.)

## Step 5: Test All Pages Manually

| Page | URL | Check |
|------|-----|-------|
| Dashboard | /admin | Stats, charts load |
| Employees | /admin/employees | Table, modals work |
| Attendance | /admin/attendance | Calendar, filters |
| Payroll | /admin/payroll | Numbers, export |
| Analytics | /admin/analytics | Charts render |
| Maps | /admin/gps | Leaflet tiles load |
| Forecasting | /admin/forecasting | Predictions tab |

## Rollback Plan

If deploy breaks:
1. Render Dashboard → **Manual Deploy** → **Deploy previous commit**
2. Or: `git revert HEAD && git push`
3. Check health endpoint returns to normal
