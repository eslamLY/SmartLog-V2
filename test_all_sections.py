#!/usr/bin/env python3
"""Comprehensive test: Service Worker + all API sections on Render."""
import urllib.request, json, ssl, sys, time

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://smartlog-v2-1.onrender.com'
ctx = ssl.create_default_context()
results = {'base_url': BASE, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'sections': {}}

def test(label, path):
    url = BASE + path
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        code = resp.status
        body = resp.read().decode('utf-8')
        is_json = False
        try:
            json.loads(body); is_json = True
        except: pass
        results['sections'][label] = {'status': code, 'json': is_json, 'size': len(body)}
        status = 'OK' if code == 200 else f'ER{code}'
        print(f'  {status:6s}  {label:25s}  {len(body):>7}b{" json" if is_json else ""}')
    except urllib.error.HTTPError as e:
        results['sections'][label] = {'status': e.code, 'error': str(e)}
        print(f'  ER{e.code:4d}  {label:25s}  {str(e)[:60]}')
    except Exception as e:
        results['sections'][label] = {'status': 0, 'error': str(e)}
        print(f'  FAIL   {label:25s}  {str(e)[:60]}')

print('=' * 70)
print(f'COMPREHENSIVE TEST — SmartLog V2')
print(f'Target: {BASE}')
print('=' * 70)

# 1. Service Worker
print('\n--- Service Worker ---')
test('sw.js', '/sw.js')
try:
    req = urllib.request.Request(BASE + '/sw.js')
    resp = urllib.request.urlopen(req, context=ctx, timeout=30)
    h = resp.headers
    print(f'  Cache-Control:            {h.get("Cache-Control","MISSING")}')
    print(f'  Service-Worker-Allowed:   {h.get("Service-Worker-Allowed","MISSING")}')
    print(f'  X-Content-Type-Options:   {h.get("X-Content-Type-Options","MISSING")}')
    body = resp.read().decode('utf-8')
    print(f'  SW Version:               {"v2.0 LIVE" if "v2.0" in body else "OLD/UNKNOWN"}')
except: pass

# 2. Pages
print('\n--- Pages ---')
test('Home', '/')
test('Login', '/login')
test('Manifest', '/manifest.json')

# 3. Health
print('\n--- Health ---')
test('Health API', '/api/health')

# 4. Dashboard API
print('\n--- Dashboard API ---')
for p in ['/api/dashboard/stats', '/api/dashboard/charts/weekly', '/api/dashboard/charts/donut',
          '/api/dashboard/charts/punctuality', '/api/dashboard/records', '/api/dashboard/filters',
          '/api/dashboard/alerts', '/api/dashboard/schedule', '/api/dashboard/search',
          '/api/dashboard/notifications', '/api/dashboard/stats/live', '/api/dashboard/map']:
    test(p.split('/')[-1], p)

# 5. System API
print('\n--- System API ---')
test('Branding', '/api/branding')
test('Metrics', '/api/admin/metrics')
test('Audit logs', '/api/admin/audit-logs')

# 6. Employees API
print('\n--- Employees API ---')
test('List', '/api/employees')
test('Search', '/api/employees/search')
test('Stats', '/api/employees/stats')

# 7. Forecasting
print('\n--- Forecasting ---')
test('Daily', '/api/forecast/daily')
test('Segmentation', '/api/forecast/segmentation')
test('Models', '/api/forecast/models')
test('Holidays', '/api/forecast/holidays')

# 8. Attendance
print('\n--- Attendance ---')
test('Policies', '/api/attendance-policies')

# Summary
print('\n' + '=' * 70)
ok = sum(1 for r in results['sections'].values() if r.get('status') == 200)
err = sum(1 for r in results['sections'].values() if r.get('status', 0) >= 400)
total = len(results['sections'])
print(f'  OK: {ok}/{total}   Errors: {err}/{total}')
print('=' * 70)

with open('test_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print('Results saved to test_results.json')
