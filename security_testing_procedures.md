# SmartLog V2 — Security Testing Procedures
> Generated: 2026-06-24 03:24:31

## How to Use This Document
Each test case includes the vulnerability it targets, the steps to reproduce, the expected result, and verification commands where applicable.

---

### T-AUTH-001: Test authentication decorators on all admin endpoints
- **Targets:** SEC-001, SEC-002
- **Category:** Authorization

**Test Steps:**
1. Open browser (incognito window, not logged in)
1. Navigate to /admin/dashboard — expect 302 redirect to login page
1. Navigate to /admin/employees — expect 302 redirect
1. Navigate to /api/init-db — expect 403 or 401
1. Navigate to /backup/manage — expect 302 redirect

**Expected Result:** All admin paths return 302/401/403 without valid session. Only /api/health and public endpoints are accessible.

**Automated Test Command:**
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/admin/dashboard  # expect 302
```

---

### T-AUTH-002: Cookie security flags check
- **Targets:** SEC-008
- **Category:** Session Security

**Test Steps:**
1. Log in to the application
1. Open browser DevTools > Application > Cookies
1. Check session cookie properties

**Expected Result:** Session cookie shows HttpOnly, Secure, SameSite=Lax flags all set to true.

**Automated Test Command:**
```bash
curl -s -D - http://localhost:5000/login -o /dev/null 2>&1 | grep -i "Set-Cookie"
```

---

### T-SQLI-001: SQL injection on login form
- **Targets:** SQLi general
- **Category:** Input Validation

**Test Steps:**
1. Navigate to /login
1. Enter username: admin' --
1. Enter password: any
1. Submit form — expect 200 with error message (not 500 or data leak)

**Expected Result:** The payload is rejected — no error message reveals SQL syntax or database structure.

---

### T-XSS-001: XSS on user input fields
- **Targets:** XSS
- **Category:** Input Validation

**Test Steps:**
1. Navigate to employee creation form
1. Enter name: <script>alert('XSS')</script>
1. Submit and navigate to employee list

**Expected Result:** The script tag is HTML-escaped, displayed as text, not executed.

---

### T-CSRF-001: CSRF token validation on forms
- **Targets:** SEC-015
- **Category:** API Security

**Test Steps:**
1. Open an HTML form page, inspect source
1. Verify CSRF token hidden field is present
1. Use curl to POST without CSRF token

**Expected Result:** Every form contains a CSRF token. POST without token returns 400.

**Automated Test Command:**
```bash
curl -X POST http://localhost:5000/login -d 'username=test&password=test' -o /dev/null -w '%{http_code}'
```

---

### T-RATE-001: Rate limiting on auth endpoints
- **Targets:** SEC-010
- **Category:** API Security

**Test Steps:**
1. Send 15 rapid POST requests to /api/auth/token
1. Count 429 responses

**Expected Result:** After 10 requests within the time window, endpoint returns 429 Too Many Requests.

**Automated Test Command:**
```bash
for ($i=0;$i -lt 15;$i++) { curl -s -o /dev/null -w "%{http_code} " http://localhost:5000/api/auth/token }
```

---

### T-ENCR-001: Field-level encryption verification
- **Targets:** SEC-011, SEC-012
- **Category:** Data Protection

**Test Steps:**
1. Log in as admin and go to employee details
1. Check database directly: SELECT base_salary, email, phone FROM employee WHERE id=1

**Expected Result:** Salary, email, and phone show as encrypted binary data (not plaintext) in the database.

**Automated Test Command:**
```bash
SELECT id, base_salary, email, phone FROM employee WHERE id=1 LIMIT 1;
```

---

### T-CONTAINER-001: Container runs as non-root user
- **Targets:** SEC-005
- **Category:** Infrastructure

**Test Steps:**
1. Access the running container shell
1. Run whoami command

**Expected Result:** Output shows "appuser" or similar non-root username, not "root".

**Automated Test Command:**
```bash
docker exec smartlog-backend whoami
```

---

### T-BRUTE-001: Brute force / credential stuffing protection
- **Targets:** SEC-017
- **Category:** Authentication

**Test Steps:**
1. Send 20 rapid login attempts with wrong password from the same IP
1. After 10 attempts, try a correct password

**Expected Result:** After 10 failed attempts, IP is blocked for 30 minutes. Even valid credentials return 429/403.

**Automated Test Command:**
```bash
for ($i=0;$i -lt 20;$i++) { curl -s -X POST http://localhost:5000/login -d 'username=admin&password=wrong' >/dev/null }
```

---

### T-SESSION-001: Session idle timeout
- **Targets:** SEC-016
- **Category:** Session Management

**Test Steps:**
1. Log in and capture the session cookie
1. Wait 9+ hours (or set PERMANENT_SESSION_LIFETIME to 5 min for testing)
1. Use the old session cookie to access /admin/dashboard

**Expected Result:** After session lifetime expires, the request returns 302 (redirect to login)

---

### T-CONFIG-001: SECRET_KEY loaded from env, not hardcoded
- **Targets:** SEC-003
- **Category:** Configuration

**Test Steps:**
1. Check config.py for any hardcoded secret key fallback
1. Verify SECRET_KEY env var is set in production

**Expected Result:** No hardcoded default SECRET_KEY in config.py. Production key comes only from env var.

---

### T-TLS-001: HTTPS enforced / HSTS present
- **Targets:** SEC-006
- **Category:** Infrastructure

**Test Steps:**
1. Visit http://site (should redirect to https://)
1. Check response headers for Strict-Transport-Security

**Expected Result:** HTTP -> HTTPS redirect. HSTS header present with max-age=31536000.

**Automated Test Command:**
```bash
curl -s -D - https://smartlog-v2-1.onrender.com/api/health | findstr -i 'Strict-Transport-Security'
```
