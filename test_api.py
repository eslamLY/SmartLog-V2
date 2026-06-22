import sys, json, urllib.request, urllib.error, http.cookiejar, urllib.parse, time

BASE = 'http://localhost:5000'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
TS = str(int(time.time()))[-6:]

def req(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header('Content-Type', 'application/json')
    try:
        resp = opener.open(r)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body.decode()) if body else {'error': str(e)}
        except:
            return e.code, {'error': body[:200].decode()}
    except Exception as e:
        return 0, {'error': str(e)}

ok, fail = 0, 0
def check(step, status, condition, msg=''):
    global ok, fail
    if condition:
        ok += 1; print('  PASS  %s' % step)
    else:
        fail += 1; print('  FAIL  %s | %s' % (step, msg))

# 1. Login
s, d = req('POST', '/login', {'username':'ADM001','password':'admin123'})
check('LOGIN', s, s == 200 and d.get('ok'), str(d)[:100])

# 2. Stats
s, d = req('GET', '/api/employees/stats')
check('STATS', s, s == 200 and 'total' in d, str(d)[:100])

# 3. Create employee 1
nid1 = '123456' + TS + '01'
emp1 = {'first_name':'Ahmed','second_name':'Mohamed','family_name':'Fetori',
    'national_id':nid1,'date_of_birth':'1990-05-15','gender':'male',
    'department':'Blood Bank','job_title':'Lab Tech','personal_phone':'+218912345678'}
s, d = req('POST', '/api/employees', emp1)
eid1 = d.get('employee',{}).get('id')
uname = d.get('employee',{}).get('username')
check('CREATE EMP1', s, bool(eid1), str(d)[:200])
if eid1: print('       id=%s username=%s' % (eid1, uname))

# 4. Create employee 2
nid2 = '987654' + TS + '02'
emp2 = {'first_name':'Fatima','second_name':'Ali','family_name':'Kilani',
    'national_id':nid2,'date_of_birth':'1995-08-20','gender':'female',
    'department':'HR','personal_phone':'+218925678901'}
s, d = req('POST', '/api/employees', emp2)
eid2 = d.get('employee',{}).get('id')
check('CREATE EMP2', s, bool(eid2), str(d)[:200])

# 5. List
s, d = req('GET', '/api/employees?page=1&per_page=10')
check('LIST', s, s == 200 and len(d.get('employees',[])) >= 2, 'count=%d' % len(d.get('employees',[])))

# 6. Get single
if eid1:
    s, d = req('GET', '/api/employees/%d' % eid1)
    emp = d.get('employee', d)
    check('GET', s, emp.get('first_name')=='Ahmed', str(d)[:200])

# 7. Update
if eid1:
    s, d = req('PUT', '/api/employees/%d' % eid1, {'job_title':'Lab Manager','base_salary':2500})
    check('UPDATE', s, d.get('ok'), str(d)[:200])

# 8. Verify update
if eid1:
    s, d = req('GET', '/api/employees/%d' % eid1)
    emp = d.get('employee', d)
    check('VERIFY', s, emp.get('job_title')=='Lab Manager', str(d)[:200])

# 9. Toggle off
if eid1:
    s, d = req('POST', '/api/employees/%d/toggle' % eid1)
    check('TOGGLE OFF', s, d.get('ok'), str(d)[:200])

# 10. Verify inactive
if eid1:
    s, d = req('GET', '/api/employees/%d' % eid1)
    emp = d.get('employee', d)
    check('INACTIVE', s, emp.get('is_active')==False, str(d)[:200])

# 11. Toggle back on
if eid1:
    s, d = req('POST', '/api/employees/%d/toggle' % eid1)
    check('TOGGLE ON', s, d.get('ok'), str(d)[:200])

# 12. Verify active
if eid1:
    s, d = req('GET', '/api/employees/%d' % eid1)
    emp = d.get('employee', d)
    check('ACTIVE', s, emp.get('is_active')==True, str(d)[:200])

# 13. Search (employee must be active)
if eid1:
    s, d = req('GET', '/api/employees/search?q=Ahmed')
    check('SEARCH', s, s==200 and len(d.get('employees',[]))>=1, str(d)[:200])

# 14. Duplicate check
s, d = req('POST', '/api/employees/check-duplicate', {'national_id': nid1})
check('DUP CHECK', s, s==200 and len(d.get('warnings',[]))>=1, str(d)[:200])

# 15. Next ID
s, d = req('GET', '/api/employees/next-id')
check('NEXT ID', s, s==200 and d.get('id','').startswith('EMP'), str(d)[:100])

# 16. Reset password
if eid1:
    s, d = req('POST', '/api/employees/%d/reset-password' % eid1, {'new_password':'Test@123456'})
    check('RESET PWD', s, d.get('ok'), str(d)[:200])

# 17. Soft delete
if eid2:
    s, d = req('DELETE', '/api/employees/%d' % eid2, {'reason':'test'})
    check('DELETE', s, d.get('ok'), str(d)[:200])

# 18. Restore
if eid2:
    s, d = req('POST', '/api/employees/%d/restore' % eid2)
    check('RESTORE', s, d.get('ok'), str(d)[:200])

# 19. Stats final
s, d = req('GET', '/api/employees/stats')
check('STATS FINAL', s, s==200 and d.get('total',0)>=2, str(d)[:200])

# ─── SECURITY ──────────────────────────────────────────

# 20. SQLi in search
s, d = req('GET', '/api/employees?' + urllib.parse.urlencode({'search':"' OR 1=1--"}))
check('SQLi SEARCH', s, s==200, 'Status=%d' % s)

# 21. SQLi in create
nid_xss1 = 'XSS_SQLI_' + TS
s, d = req('POST', '/api/employees', {
    'first_name':"Test",'second_name':"'; DROP TABLE employees--",'family_name':'Test',
    'national_id':nid_xss1,'gender':'male','department':'Test','date_of_birth':'1990-01-01'})
check('SQLi CREATE', s, s in (200,201,400), 'Status=%d' % s)

# 22. XSS stored
nid_xss2 = 'XSS_STORE_' + TS
s, d = req('POST', '/api/employees', {
    'first_name':'<script>alert(1)</script>','second_name':'Test','family_name':'Test',
    'national_id':nid_xss2,'gender':'male','department':'Test','date_of_birth':'1990-01-01'})
check('XSS CREATE', s, s in (200,201), 'Status=%d' % s)

# 23. Invalid phone
nid_ph = 'PHONE_' + TS
s, d = req('POST', '/api/employees', {
    'first_name':'Phone','second_name':'Test','family_name':'Test',
    'national_id':nid_ph,'gender':'male','department':'Test','date_of_birth':'1990-01-01',
    'personal_phone':'abc123'})
check('INVALID PHONE', s, s==400, str(d)[:200])

# 24. Missing required fields
s, d = req('POST', '/api/employees', {'national_id':'123'})
check('MISSING FIELDS', s, s==400, str(d)[:200])

# 25. Unauthenticated access (check redirect to login)
anon_opener = urllib.request.build_opener()
no_redirect = urllib.request.HTTPRedirectHandler()
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
anon_opener = urllib.request.build_opener(NoRedirect)
try:
    r = anon_opener.open(urllib.request.Request(BASE+'/api/employees/stats'))
    anon_status = r.status
except urllib.error.HTTPError as e:
    anon_status = e.code
except Exception as e:
    anon_status = 0
check('UNAUTH BLOCKED', 0, anon_status in (302, 401, 403), 'Status=%d' % anon_status)

# ─── SUMMARY ──────────────────────────────────────────
print()
print('='*50)
print('RESULTS: %d/%d PASSED, %d FAILED' % (ok, ok+fail, fail))
print('='*50)
sys.exit(0 if fail==0 else 1)
