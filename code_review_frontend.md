# Frontend Code Security Review — SmartLog V2

**Date:** 2026-06-24  
**Review Scope:** All HTML templates, static JS, CSS  
**Total Templates:** ~50 HTML files

---

## 1. Cross-Site Scripting (XSS)

### Severity: HIGH — Widespread innerHTML usage

**Issue:** Nearly all templates use `innerHTML` to render API responses. User-controlled data (employee names, department names, etc.) is rendered via template literals without HTML escaping.

**Examples:**

| File | Line | Code |
|------|------|------|
| `templates/employee/my_profile.html` | 123–128 | `data.qualifications.map(q => <div><strong>${q.level}</strong>...)` via `innerHTML` |
| `templates/admin/leave_management.html` | 129 | `data.requests.map(r => <tr>...${r.employee_name}...</tr>)` via `innerHTML` |
| `templates/admin/employees_consolidated.html` | 453+ | `table.innerHTML = '<thead>...' + data.map(...)` |
| `templates/admin/attendance-review-queue.html` | 147, 236 | Template literals in `innerHTML` |
| `templates/base.html` | 352, 362 | Notification rendering via `innerHTML` |
| `templates/admin/documents.html` | 353 | Document list via `innerHTML` |

**Risk:** If an attacker can control any field rendered via these templates (employee name, department, etc.), they can execute arbitrary JS.

**Mitigation:**
- Add a global `esc()` function (exists in `document_vault.html` line 156 but unused elsewhere):
  ```js
  function esc(s) { 
    var d = document.createElement('div'); 
    d.appendChild(document.createTextNode(s)); 
    return d.innerHTML; 
  }
  ```
- Use `textContent` instead of `innerHTML` where possible
- Apply `esc()` to all user-controlled values in template literals

### Severity: MEDIUM — Jinja2 `|safe` filter

**File:** `templates/base.html` and various admin templates  
**Risk:** The `|safe` filter in Jinja2 marks content as safe HTML, bypassing autoescaping.

### Severity: INFO — Jinja2 autoescaping

Flask enables Jinja2 autoescaping for `.html` files by default. This protects against XSS in Jinja2 variables rendered in HTML context, but NOT in JavaScript context or when content is rendered via `innerHTML` from API responses.

---

## 2. Cross-Site Request Forgery (CSRF)

### Severity: INFO — CSRF partially implemented

**Positive:** 
- `base.html` has `<meta name="csrf-token" content="{{ csrf_token }}">` (Phase 3.3)
- `api()` function in `base.html` sends `X-CSRFToken` header for POST requests

**Negative:**
- **Login form** (`templates/login.html:56-63`) calls `fetch('/login', ...)` **without** CSRF token
- **force_password_change.html:84** also uses `fetch` with `X-CSRFToken` (good)
- Individual page scripts often call `fetch()` directly without using `api()`, bypassing CSRF

**Pages with direct `fetch()` calls missing CSRF:**
- `templates/admin/dashboard.html` — various quick-action buttons
- `templates/admin/attendance.html:120` — `fetch('/api/attendance/...')`
- `templates/admin/leaves.html:72` — `fetch('/api/leaves/...')`
- `templates/admin/shifts.html` — multiple `fetch()` calls
- `templates/employee/dashboard.html` — attendance clock-in/out
- `templates/employee/attendance-offline.html` — offline sync

**Mitigation:**
- Add a global `csrfFetch()` wrapper that always includes `X-CSRFToken`
- Replace all direct `fetch()` calls with `csrfFetch()`
- Add CSRF token to login form

---

## 3. Third-Party Scripts & Subresource Integrity

### Severity: HIGH — No SRI on CDN resources

External resources loaded without `integrity=` attributes:

| Resource | Source |
|----------|--------|
| `@tabler/icons-webfont@3.24.0` | `cdn.jsdelivr.net` |
| `font-awesome/6.5.1/css/all.min.css` | `cdnjs.cloudflare.com` |
| `fonts.googleapis.com/css2?family=Cairo...` | Google Fonts |
| `sweetalert2@11` | `cdn.jsdelivr.net` |

**Risk:** If any CDN is compromised, the attacker can inject malicious code into every page load.

**Mitigation:**
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.24.0/dist/tabler-icons.min.css"
      integrity="sha384-..." crossorigin="anonymous">
```
Use [SRI Hash Generator](https://www.srihash.org/) to generate hashes.

---

## 4. Storage & Client-Side Data

### Severity: PASS — No localStorage/sessionStorage usage

The application does not use `localStorage` or `sessionStorage` for sensitive data, which is good practice.

### Service Worker Cache

`templates/base.html` registers service worker (`static/js/app.js:12`). The service worker (`routes/auth.py:34-42`) caches `/login` and `/manifest.json` — no sensitive data.

**Risk:** The inline service worker (generated as Python string in `auth.py:35-41`) could be easier to XSS.

---

## 5. Content-Security-Policy

### Current CSP (from server headers):
```
default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net ...; 
style-src 'self' 'unsafe-inline' ...; img-src 'self' data: blob: ...;
font-src 'self' ...; connect-src 'self'; frame-ancestors 'none';
```

| Directive | Assessment |
|-----------|------------|
| `default-src 'self'` | ✅ Good baseline |
| `script-src 'unsafe-inline'` | ⚠️ Required for inline scripts; use nonces for better security |
| `style-src 'unsafe-inline'` | ⚠️ Required for inline styles |
| `frame-ancestors 'none'` | ✅ Prevents clickjacking |
| `connect-src 'self'` | ✅ No external API calls |
| `img-src data: blob:` | ✅ Allows inline images |

---

## 6. Secure Cookies

| Attribute | Status | Setting |
|-----------|--------|---------|
| `HttpOnly` | ✅ Present | `SESSION_COOKIE_HTTPONLY = True` |
| `Secure` | ✅ Production only | `SESSION_COOKIE_SECURE = True` (prod) |
| `SameSite` | ✅ Lax | `SESSION_COOKIE_SAMESITE = 'Lax'` |

**Note:** `Secure` flag is not set in development — this is acceptable for local testing but cookies will be sent over HTTP.

---

## 7. Security Header Analysis

| Header | Status | Value |
|--------|--------|-------|
| `Content-Security-Policy` | ✅ | See section 5 |
| `Strict-Transport-Security` | ✅ (prod) | `max-age=31536000; includeSubDomains; preload` |
| `X-Content-Type-Options` | ✅ | `nosniff` |
| `X-Frame-Options` | ✅ | `DENY` |
| `Referrer-Policy` | ❌ MISSING | Should be `strict-origin-when-cross-origin` |
| `Permissions-Policy` | ❌ MISSING | Should restrict `camera=(), microphone=(), geolocation=(self)` |
| `Cache-Control` | ⚠️ PARTIAL | Should be `no-store` for admin pages |

---

## 8. JavaScript Analysis

### Dangerous Functions: NOT FOUND
- `eval()` — not used
- `new Function()` — not used
- `document.write()` — not used
- `setTimeout(string)` — not used (always uses function references)

### Inline Script Size
Every admin template has its own `<script>` block with hundreds of lines of JS. This is a maintenance burden and CSP risk.

**Recommendation:** Move common JS patterns to `static/js/app.js` and load per-page scripts via `{% block scripts %}`.

---

## Risk Summary

| Category | Severity | Count | Key Issues |
|----------|----------|-------|------------|
| **XSS** | 🔴 HIGH | 30+ | innerHTML with unescaped API data |
| **CSRF** | 🟡 MEDIUM | 5+ | Direct fetch() calls bypassing CSRF |
| **SRI** | 🔴 HIGH | 4 | No SRI on any CDN resource |
| **CSP** | 🟡 MEDIUM | 1 | unsafe-inline required for scripts |
| **Headers** | 🟡 MEDIUM | 2 | Referrer-Policy, Permissions-Policy missing |
| **Storage** | ✅ PASS | — | No sensitive client-side storage |

---

## Top 5 Recommended Fixes

1. **CRITICAL**: Replace all `innerHTML` with `textContent` + DOM API, or create a global `esc()` function and apply to all user data
2. **HIGH**: Add `integrity=` (SRI) to all CDN links (Tabler Icons, Font Awesome, SweetAlert2, Google Fonts)
3. **HIGH**: Create a global `csrfFetch()` wrapper and replace all `fetch()` calls in templates
4. **MEDIUM**: Add `Referrer-Policy` and `Permissions-Policy` headers to production security headers
5. **MEDIUM**: Move inline `<script>` blocks into external JS files to reduce CSP `'unsafe-inline'` dependency
