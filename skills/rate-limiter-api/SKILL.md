---
name: rate-limiter-api
description: |
  Use ONLY when the task involves implementing, auditing, or fixing
  RATE LIMITING and ANTI-ABUSE controls in a Flask + SQLAlchemy backend.
  Covers: GPS/telemetry flood prevention, brute-force login protection,
  global inbound traffic throttling, DDoS mitigation, and 429 handling.
  Do NOT activate for UI changes, feature development, or database schema
  design unrelated to rate limiting.
---

# Rate Limiter & Anti-Flooding Protocol

This skill enforces strict request throttling and abuse prevention for the
**SMARTLOG** attendance system. Every Flask route that accepts
external or semi-external traffic MUST be evaluated against the rules below
before any code is submitted.

---

## 1. GPS & Telemetry Flooding — Session-Gated Cooldown

### 1.1 Mandatory Pattern
Every route that logs periodic telemetry (GPS coordinates, battery status,
heartbeat pings) MUST implement a **session-based time gate**:

```python
last = session.get('gps_last_time')
if last:
    elapsed = (datetime.utcnow() - datetime.fromisoformat(last)).total_seconds()
    if elapsed < 60:
        return jsonify({'ok': False, 'msg': 'يرجى الانتظار 60 ثانية بين كل تحديث.'}), 429
# ... process request ...
session['gps_last_time'] = datetime.utcnow().isoformat()
```

### 1.2 Requirements
- **Minimum interval**: 60 seconds between successive writes from the same session.
- **Status code**: `429 Too Many Requests` on violation.
- **Response body**: `{'ok': False, 'msg': '<message>'}` — never expose the interval value.
- **Session key**: Must be namespaced per route, e.g., `gps_last_time`, `ping_last_time`.
- **First-call path**: If the session key is absent, allow the request and set the timestamp.

### 1.3 What to Audit
| Check | Pass/Fail |
|---|---|
| `/employee/gps/log` has session cooldown | ✅ / ❌ |
| Cooldown is ≥ 60 seconds | ✅ / ❌ |
| Returns HTTP 429 on violation | ✅ / ❌ |
| Timestamp updated only after success | ✅ / ❌ |

---

## 2. Brute-Force & Login Protection — Multi-Layer

### 2.1 IP-Based Tracking
Use the `LoginAttempt` model (already exists) to track per-IP failure counts:

```python
attempt = LoginAttempt.query.filter_by(ip_address=ip).first()
if attempt and attempt.blocked_until and attempt.blocked_until > datetime.utcnow():
    mins = int((attempt.blocked_until - datetime.utcnow()).total_seconds() / 60) + 1
    return jsonify({'ok': False, 'msg': f'هذا الجهاز محظور. حاول بعد {mins} دقيقة.'})
```

### 2.2 Configuration Constants
```python
MAX_LOGIN_ATTEMPTS   = 5      # failures before block
BLOCK_DURATION_MIN   = 15      # 0.25 hours (also used in existing code as 1 hour — keep the stricter value)
```

If the existing code uses a different block duration, default to the **stricter** of the two. Currently the system blocks for 1 hour — this is acceptable, do NOT reduce it.

### 2.3 Username-Based Tracking (Optional Enhancement)
For defense in depth, also track failures per-username regardless of IP:

```python
username_attempts[username] = username_attempts.get(username, 0) + 1
if username_attempts.get(username, 0) >= MAX_LOGIN_ATTEMPTS:
    # freeze this username for BLOCK_DURATION_MIN regardless of IP
```

This prevents distributed brute-force where an attacker rotates IPs.

### 2.4 Failed Attempt Lifecycle
1. On login failure: increment `LoginAttempt.attempts`, update `last_attempt`.
2. When `attempts >= MAX_LOGIN_ATTEMPTS`: set `blocked_until = now + timedelta(minutes=BLOCK_DURATION_MIN)`.
3. On login success: **delete** the `LoginAttempt` row for that IP (clean slate).
4. **Never** tell the caller whether the username exists vs the password is wrong — use a single generic message: `'اسم المستخدم أو كلمة المرور غير صحيحة.'`

### 2.5 What to Audit
| Check | Pass/Fail |
|---|---|
| `LoginAttempt` table exists with `ip_address`, `attempts`, `blocked_until` | ✅ / ❌ |
| Failed login increments `attempts` | ✅ / ❌ |
| `attempts >= MAX_LOGIN_ATTEMPTS` triggers block | ✅ / ❌ |
| Blocked IP returns 401 with time-remaining message | ✅ / ❌ |
| Successful login deletes attempt row | ✅ / ❌ |
| Generic error message (no user enumeration) | ✅ / ❌ |

---

## 3. Global Request Limiting — Server Resource Protection

### 3.1 In-Memory Request Counter
For routes that are expensive or externally facing, implement a lightweight
in-memory counter using `flask.g` or a module-level dict with timestamps:

```python
from collections import defaultdict
from datetime import datetime, timedelta

_request_log = defaultdict(list)  # route_name -> [timestamp, ...]

def check_rate_limit(route_key, max_requests=30, window_seconds=60):
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)
    _request_log[route_key] = [t for t in _request_log[route_key] if t > cutoff]
    if len(_request_log[route_key]) >= max_requests:
        return False
    _request_log[route_key].append(now)
    return True
```

### 3.2 Per-Route Limits

| Route Category | Max Requests | Window | Rationale |
|---|---|---|---|
| `/api/hardware/punch` | 30 | 60s | Biometric device — batch punches possible |
| `/admin/live/stats` | 60 | 60s | Dashboard auto-refresh (1/sec per admin) |
| `/admin/live/events` | 1 connection | — | SSE — one stream per admin |
| `/employee/gps/log` | 1 | 60s | Already covered by session cooldown |
| `/login` | 5 | 900s | Already covered by `LoginAttempt` |
| `/api/branding` | 60 | 60s | Public endpoint, limit exposure |
| `/employee/clockin` | 6 | 60s | 10s cooldown between clock-in attempts |
| `/employee/clockout` | 6 | 60s | Same as clockin |
| All other POST routes | 30 | 60s | General safeguard |

### 3.3 Integration Pattern
Apply in the route before any business logic:

```python
@app.route('/api/hardware/punch', methods=['POST'])
def hardware_punch():
    if not check_rate_limit('hardware_punch', 30, 60):
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429
    # ... rest of route ...
```

### 3.4 Rate Limit Headers
For routes using global rate limiting, set response headers so clients can adapt:

```python
response = jsonify({'ok': True, ...})
response.headers['X-RateLimit-Limit'] = str(max_requests)
response.headers['X-RateLimit-Remaining'] = str(max(0, max_requests - len(_request_log[route_key])))
response.headers['X-RateLimit-Reset'] = str(int(cutoff.timestamp()))
return response
```

---

## 4. Implementation Protocol

### 4.1 Adding Rate Limits to a New Route

1. Identify the route category from §3.2.
2. Create or reuse the `_request_log` dict at module level.
3. Add `check_rate_limit()` call as the **first executable line** inside the route function (after session/role checks).
4. Return `429` with a generic message on failure.
5. If the route returns a response object, attach `X-RateLimit-*` headers.

### 4.2 When Modifying Existing Rate-Limited Routes

- **Never** remove an existing rate limit or cooldown check.
- **Never** increase an existing limit without explicit authorization.
- **Never** decrease a cooldown window (e.g., 60s → 30s) without explicit authorization.
- If two rate-limit mechanisms apply (e.g., session cooldown + global counter), both MUST be satisfied for the request to proceed.

### 4.3 Testing Rate Limits

Verify with:
```python
# Test 429 response
for _ in range(limit + 1):
    response = client.post(url, ...)
assert response.status_code == 429
```

---

## 5. Anti-DDoS & Abuse Hardening

### 5.1 Request Size Limits
- `MAX_CONTENT_LENGTH` must be set on the Flask app (already: 16MB).
- For JSON endpoints, reject payloads > 1MB with 413:
  ```python
  if request.content_length and request.content_length > 1024 * 1024:
      return jsonify({'ok': False, 'msg': 'البيانات كبيرة جداً.'}), 413
  ```

### 5.2 Concurrent Request Throttling
For deployment behind gunicorn/uvicorn, enforce:
- `--workers 4` (CPU-bound)
- `--threads 2` (I/O-bound)
- `--limit-request-line 4094`
- `--timeout 30`

### 5.3 Suspicious Pattern Detection
Flag and blacklist (temporary) IPs that trigger any of the following within 60 seconds:
- 20+ requests to `/login`
- 50+ requests to any single POST route
- 100+ total requests
- Requests with invalid or spoofed `Content-Type` headers

Blacklist implementation: add `blocked_until` to `LoginAttempt` or create a shared `IPBlacklist` table.

---

## 6. Audit Checklist

Before submitting any code that touches rate limiting, verify:

- [ ] GPS & telemetry routes have session-based 60s cooldown
- [ ] Login route enforces IP-based attempt tracking
- [ ] Login route uses generic error messages (no user enumeration)
- [ ] Successful login clears attempt history
- [ ] All external-facing POST routes have global rate limits
- [ ] `/api/hardware/punch` has both header auth AND rate limiting
- [ ] Rate-limit violations return HTTP 429 with generic message
- [ ] Response headers include `X-RateLimit-*` where applicable
- [ ] `MAX_CONTENT_LENGTH` is enforced app-wide
- [ ] JSON payloads > 1MB are rejected with 413
- [ ] Session-based and global rate limits compose (both must pass)
- [ ] Rate limits are never weakened during edits

---

**Rate limiting is not optional middleware — it is a structural requirement for every externally-reachable endpoint.**
