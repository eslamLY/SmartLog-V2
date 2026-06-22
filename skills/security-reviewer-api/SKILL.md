---
name: security-reviewer-api
description: |
  Use ONLY when the task involves reviewing, auditing, or fixing SECURITY
  vulnerabilities in an existing Flask + SQLAlchemy + Jinja2 codebase.
  Applies to: input sanitization, session validation, biometric/token checks,
  error handling, XSS/CSRF/SQLi prevention, and surgical code edits.
  Do NOT activate for general feature development, UI changes, or
  non-security-related refactoring.
---

# Security Reviewer & Precision Coding Protocol

This skill enforces a strict security-first code discipline for the
**Tobruk Blood Bank** attendance system (`app.py`, templates, models).

## 1. Input Sanitization — Zero Trust

### 1.1 Flask Route Requirements
Every route that accepts user input MUST:
- Use `request.get_json() or {}` for JSON bodies (never access `request.json` directly).
- Strip whitespace from all string fields: `.strip()`.
- Type-cast numeric fields explicitly: `int(d.get('key', 0))`, `float(d.get('key', 0.0))`.
- Validate that required fields are non-empty **before** using them in queries.

```python
# ✅ CORRECT
d = request.get_json() or {}
emp_id = int(d.get('employee_id', 0))
name = d.get('name', '').strip()
if not name: return jsonify({'ok': False, 'msg': 'الاسم مطلوب.'})

# ❌ WRONG — no fallback, no strip, no type check
name = request.json['name']
```

### 1.2 SQL Injection Prevention
- NEVER use raw SQL strings or `db.session.execute(text(...))` with user data.
- ALWAYS use SQLAlchemy ORM methods: `filter_by`, `filter`, `func`, `extract`.
- For dynamic filters, use `db.or_()` / `db.and_()` with keyword arguments, not string formatting.

```python
# ✅ CORRECT
Employee.query.filter(db.or_(Employee.full_name.ilike(f'%{q}%'),
                              Employee.username.ilike(f'%{q}%')))

# ❌ WRONG — SQL injection vector
db.session.execute(f"SELECT * FROM employees WHERE name = '{name}'")
```

### 1.3 XSS Prevention in Templates
- In Jinja2, variables auto-escape by default. Do NOT use `|safe` unless the content is a trusted HTML string you control.
- For user-submitted text displayed in templates, always use `{{ var }}` (auto-escaped), never `{{ var|safe }}`.
- In JavaScript, when inserting user text into the DOM, use `textContent`, never `innerHTML`.

```javascript
// ✅ CORRECT
el.textContent = userInput;

// ❌ WRONG — XSS
el.innerHTML = userInput;
```

### 1.4 CSRF / Endpoint Safety
- All mutating endpoints (POST/PUT/DELETE) require either:
  - `@admin_required` or `@login_required` decorator, OR
  - An explicit session role check inside the route.
- Never expose a mutating endpoint without authentication (exception: `/api/hardware/punch` which uses serial_no lookup as its auth mechanism).

## 2. Surgical Changes — Precision Editing

### 2.1 Never Rewrite Entire Files
When fixing security issues:
- Identify the **specific lines** that contain the vulnerability.
- Replace only those lines. Never restructure the function, rename variables, or reformat the file.
- If the fix requires a new import, add it at the end of the existing import block — don't reorder imports.

### 2.2 Preserve Existing Security Logic
Before editing any route, scan for existing:
- `@admin_required` / `@login_required` decorators
- `session.get('role')` checks
- `session.get('user_id')` lookups
- Existing validation guards

If the code already has a security check, do NOT remove or weaken it. Only add checks where they are missing.

### 2.3 Context Review Protocol
Before making any change, read at least:
- The full function being modified (not just the visible diff)
- 10 lines above and below the target line
- The imports at the top of the file
- Any related model definition

## 3. Biometric, Token & Session Validation

### 3.1 Session Validation Pattern
Every protected route MUST confirm the session is active:

```python
if 'user_id' not in session:
    return jsonify({'ok': False, 'msg': 'الجلسة منتهية.'})
```

When an endpoint references `session['user_id']` or `session['role']`, ensure the decorator or an explicit guard exists.

### 3.2 Role-Specific Checks
- **Admin endpoints**: use `@admin_required` decorator, which checks both login and `role == 'admin'`.
- **Employee endpoints**: use `@login_required` decorator.
- **Mixed endpoints** (e.g., API data shared by both roles): check `session.get('role')` explicitly:

```python
is_admin = session.get('role') == 'admin'
emp_id = session['user_id']
if not is_admin:
    # restrict to own data only
    query = query.filter(Notification.employee_id == emp_id)
```

### 3.3 Biometric Credential Validation
When verifying biometric credentials:
- Verify the `credential_id` matches the stored hash for the **logged-in user** only.
- Never accept a `credential_id` and `employee_id` pair where the employee differs from the session user (unless admin).
- After biometric verification, store `session['biometric_verified'] = True` and clear it on logout.

### 3.4 Document & GPS Access
- Document download endpoints MUST verify the requesting user is admin OR the document's employee matches `session['user_id']`.
- GPS log queries MUST scope to `employee_id == session['user_id']` for non-admin users.

## 4. Error Handling — Zero Leakage

### 4.1 Catch All Exceptions in Routes
Every route that touches the database or external resources MUST wrap risky operations in try/except:

```python
try:
    emp = Employee.query.get_or_404(emp_id)
    result = do_something()
    db.session.commit()
    return jsonify({'ok': True, 'result': result})
except Exception as e:
    db.session.rollback()
    # Log the real error server-side (not shown to user):
    app.logger.error(f"Error in route: {e}")
    return jsonify({'ok': False, 'msg': 'حدث خطأ داخلي. الرجاء المحاولة لاحقاً.'})
```

### 4.2 Never Expose Internals
- Do NOT return `str(e)`, `repr(e)`, or `traceback.format_exc()` to the frontend.
- Do NOT include SQL, file paths, or server configuration in error responses.
- Use generic user-facing messages:
  - `msg = 'حدث خطأ داخلي.'` for unexpected errors.
  - `msg = 'البيانات غير صالحة.'` for validation errors.
  - `msg = 'غير مصرح.'` for permission errors.

### 4.3 Rollback on Failure
If a route modifies the database, always call `db.session.rollback()` in the except block to prevent partial commits.

### 4.4 File Operation Safety
When reading/writing uploaded files:
- Validate `allowed_file()` before saving.
- Use `uuid` for filenames — never trust the original filename.
- Set `MAX_CONTENT_LENGTH` at the app config level.
- Wrap file reads in try/except, return a generic error on failure.

## 5. Security Audit Checklist

Before submitting any code that touches the following areas, verify each item:

### GPS Routes (`/employee/gps/*`, `/admin/gps`)
- [ ] `GPSLog` query scoped to session user for non-admin
- [ ] Latitude/longitude sanitized (float)
- [ ] No raw SQL in GPS aggregation

### Biometric Routes (`/employee/biometrics/*`, `/admin/biometrics`)
- [ ] Credential verification compares against logged-in user only
- [ ] `biometric_verified` session flag cleared on logout
- [ ] Admin biometric list route uses `@admin_required`

### Document Routes (`/admin/documents/*`)
- [ ] Download checks user permission (admin or owner)
- [ ] File path uses `uuid` not original filename
- [ ] Upload validated with `allowed_file()`
- [ ] File size enforced via `MAX_CONTENT_LENGTH`

### Notification Routes (`/admin/notifications/*`, `/api/notifications/*`)
- [ ] Notification history scoped to session user for non-admin
- [ ] Send endpoint requires `@admin_required`
- [ ] Title/message stripped before storage

### Hardware API (`/api/hardware/punch`)
- [ ] Serial number validated against `BioTimeDevice` table
- [ ] Employee UID matched to active employee only
- [ ] Device `last_sync` timestamp updated

### General
- [ ] All POST routes have auth decorator
- [ ] No `|safe` in templates for user-submitted content
- [ ] No `innerHTML` assignment from user data
- [ ] No raw SQL `text()` or `execute()` with user input
- [ ] All exception paths return generic messages
- [ ] `db.session.rollback()` called in all except blocks that modify DB

## 6. Execution Protocol

When tasked with a security review:

1. **Inventory**: List every route and template that handles user input, session data, or file operations.
2. **Audit**: For each item in the inventory, run the Security Audit Checklist.
3. **Report**: For each vulnerability found, report:
   - File and line number
   - Vulnerability class (XSS, SQLi, Broken Auth, Info Leak, etc.)
   - Severity (Critical / High / Medium / Low)
   - One-sentence fix strategy
4. **Fix**: Apply each fix surgically — one edit per vulnerability, with a comment in the edit referencing the checklist item.
5. **Verify**: Re-import `app.py` and confirm no syntax errors. Run `db.create_all()` to verify model consistency.

---

**Security is not a feature. It is a property of every line of code.**
