---
name: clean-code-api
description: |
  Use ONLY when the task involves identifying and safely removing DEAD CODE,
  UNUSED IMPORTS, UNREACHABLE BRANCHES, OBSOLETE COMMENTS, or DATABASE
  CONNECTION LEAKS in a Flask + SQLAlchemy + Jinja2 codebase.
  Covers: dead function/variable elimination, orphan import removal,
  execution-graph dependency tracing, and connection／cursor hygiene.
  Do NOT activate for feature development, UI styling, or security hardening.
---

# Clean Code & Dead-Code Elimination Protocol

This skill enforces rigorous dead-code elimination and performance optimization
for the **Tobruk Blood Bank** attendance system. Every removal must be proven
safe via full execution-graph tracing before deletion.

---

## 1. Dead Code & Unused Assets — Classification

### 1.1 Categories of Dead Code

| Category | Examples | Risk Level |
|---|---|---|
| **Unused function** | Defined with `def` but never called anywhere | Medium |
| **Unused variable** | Assigned but never read after assignment | Low |
| **Unreachable branch** | `if False:`, `return` followed by code, `else` after terminal `return` | Low |
| **Obsolete comment** | Comment referencing deleted feature, disabled code block, or `# noqa` on valid lines | Low |
| **Orphaned template** | HTML file in `templates/` not referenced by any `render_template()` call | High |
| **Unused route** | `@app.route` where the function is never linked from any template or JS fetch | High |
| **Dead model column** | `db.Column` not read or written by any route or template | High |

### 1.2 Risk-Based Protocol

| Risk | Action Required Before Deletion |
|---|---|
| **Low** | Single-line grep to confirm no references. Can delete immediately. |
| **Medium** | grep across ALL `.py` and `.html` files. Check for dynamic references (`getattr`, `url_for`, string-concat route names). |
| **High** | Full execution-graph trace (see §3). Must also check for Alembic/DB migration references. |

---

## 2. Unused Imports Optimization

### 2.1 Python Import Rules

Every import in `app.py` and any new `.py` file MUST be justifiable:

```python
# ✅ KEEP — used in this file
from flask import jsonify  # used in 30+ routes

# ❌ REMOVE — never referenced
import xml.etree.ElementTree
```

Scan rules (equivalent to `autoflake --remove-all-unused-imports --recursive`):

1. Run a mental grep for each imported symbol across the entire file.
2. If the symbol appears only in the import line and nowhere else, **remove it**.
3. If the symbol is used only in a comment or a disabled code block, **remove it**.
4. If the import is a module (not a symbol), check if the module name is used as a qualifier, e.g., `os.path.join`, `math.radians`.
5. **Never remove** an import that is used dynamically via `__import__()`, `importlib`, or `globals()`, unless you have verified those call sites.
6. For `from x import (a, b, c)` — if `a` is unused but `b` and `c` are used, remove only `a` from the tuple.

### 2.2 JavaScript / Template Constants

In `<script>` blocks within Jinja2 templates:

- Remove any `var`, `let`, or `const` that is declared but never referenced in the same script block.
- Remove any function that is defined but never called or used as a callback.
- **Exception**: Functions assigned to `window.*` or passed to `addEventListener` must be traced for dynamic usage.

### 2.3 CSS Dead Rules

- Remove CSS selectors that do not match any element in any template.
- Remove vendor prefixes for properties that have ≥98% browser support (e.g., `-webkit-border-radius`).

---

## 3. Strict Dependency Graph Check

### 3.1 Mandatory Tracing Before Any Deletion

Before deleting **any** function, route, model column, or template, trace the
full dependency graph:

#### For Python functions:
```
1. grep -r "function_name" app.py templates/ --include="*.py" --include="*.html"
2. Check for:
   - Direct calls: function_name(...)
   - url_for references: url_for('function_name') or url_for('function_name', ...)
   - Dynamic dispatch: getattr(obj, 'function_name')
   - Decorator references: @app.route(...) wrapping the function
   - Template references: any template calling the function via Jinja2
```

#### For model columns:
```
1. grep -r "column_name" app.py templates/ --include="*.py" --include="*.html"
2. Check for:
   - ORM queries: .filter_by(column_name=...), .filter(Model.column_name ...)
   - Template access: {{ obj.column_name }}
   - Form values: request.form.get('column_name') or request.json['column_name']
   - JSON serialization: jsonify({... 'column_name': ...})
```

#### For templates:
```
1. grep -r "template_name.html" app.py --include="*.py"
2. Check for:
   - render_template('template_name.html', ...)
   - redirect(url_for('...')) where the route renders this template
   - {% extends "template_name.html" %} or {% include "template_name.html" %}
```

### 3.2 The "One Doubt" Rule

If after tracing there is **any ambiguity** about whether a symbol is used:

- **Do not delete it.**
- Add a comment: `# TODO: verify dead — suspected unused`
- Move on. The cost of keeping dead code is zero at runtime (it's never called).
  The cost of deleting live code is a production bug.

### 3.3 Cross-File Reference Map

Build a mental map for any High-risk deletion:

```
Symbol X
  ├── app.py:
  │   ├── defined at line N
  │   ├── called at lines [A, B, C]
  │   └── referenced in url_for at lines [D, E]
  ├── templates/:
  │   ├── referenced in shift_swaps.html line M
  │   └── referenced in base.html line P (via {{ url_for(...) }})
  └── js/ or inline scripts:
      └── fetch('/api/route/...') or api('/route/...')
```

If ALL references point to the symbol itself (definition + deletion target),
and NONE point to it as a consumer, it is **safe to delete**.

---

## 4. Database Connection Hygiene

### 4.1 SQLAlchemy Session Rules

Flask-SQLAlchemy binds the session to the request-scope. In `app.py`,
the session lifecycle is managed automatically, but these rules still apply:

#### ✅ Always:
```python
# Explicit commit after mutations
db.session.add(obj)
db.session.commit()
```

#### ❌ Never:
```python
# Mutation without commit — leaks the transaction
db.session.add(obj)
# missing db.session.commit()

# Catching and swallowing without rollback
try:
    db.session.add(obj)
    db.session.commit()
except Exception:
    pass  # ❌ Must call db.session.rollback() here

# Keeping connections open across multiple requests
global_cursor = db.session.execute(...)  # ❌ Never store cursors globally
```

### 4.2 Connection Pool Hygiene

- Flask-SQLAlchemy already manages the pool. Do not manually create engines or connections.
- Never assign `db.engine` or `db.session` to a global variable.
- In routes that loop over large query results, use `.yield_per(N)` to stream results:

```python
for row in db.session.query(BigModel).yield_per(100):
    process(row)
```

- For bulk inserts, use `db.session.bulk_insert_mappings()` or `db.session.add_all()`.
  Never insert inside a tight loop with individual commits.

### 4.3 Detecting Leaks in Existing Code

Scan for these patterns:

| Anti-Pattern | Detection | Severity |
|---|---|---|
| `db.session.add(x)` without `db.session.commit()` after | Mutation not flushed | High |
| `db.session.commit()` without try/except | Unhandled integrity error on commit | Medium |
| `except: pass` around DB operations | Silent rollback miss | High |
| `db.session.execute()` result stored in a global/list | Cursor leak | Medium |
| `@app.before_request` that opens a session and never closes | Connection pool drain | High |
| Raw `sqlite3.connect()` alongside Flask-SQLAlchemy | Dual pool conflict | High |

### 4.4 Flask-Specific Checks

- All `@app.teardown_request` handlers that close sessions are unnecessary with Flask-SQLAlchemy (it handles teardown). Remove them if found — they add overhead.
- `db.create_all()` should be called once at startup (inside `if __name__`) and never inside a route.

---

## 5. Execution Protocol

When asked to clean dead code, follow this exact sequence:

### Step 1 — Inventory
Collect every potentially dead item:
- Functions with zero call sites (via grep)
- Imports with zero references (via grep)
- Template files with zero `render_template()` calls
- Model columns with zero read/write sites
- CSS rules that match no elements

### Step 2 — Trace (High-Risk Items Only)
For each High-risk item, build the cross-file reference map (§3.3).
If any real reference exists, demote to "keep" and move on.

### Step 3 — Report
Present a table:

| Item | Category | Risk | Cross-Refs Found? | Action |
|---|---|---|---|---|
| `old_function()` | Unused function | Medium | 0 | DELETE |
| `import xml` | Unused import | Low | 0 | DELETE |
| `obsolete_col` | Dead column | High | 0 (traced) | DELETE + migrate |
| `unused.html` | Orphan template | High | 0 (traced routes + extends) | DELETE |

### Step 4 — Execute (Surgical Only)
- Remove **one item at a time**.
- After each removal, verify: `python -c "from app import app; print('OK')"`
- For columns: run `db.create_all()` to confirm schema integrity.
- For templates: verify that no other template `{% extends %}` or `{% include %}` references it.

### Step 5 — Verify
- Confirm app imports without error.
- Confirm `db.create_all()` succeeds (schema unchanged).
- Confirm no `{% include %}` or `{% extends %}` in remaining templates targets a deleted file.

---

## 6. Audit Checklist

Before submitting any clean-code change, verify:

- [ ] Every deleted symbol was grepped across ALL `.py` and `.html` files
- [ ] High-risk deletions have a full cross-file reference map
- [ ] No import was removed if used dynamically (`__import__`, `getattr`, `globals()`)
- [ ] No template was removed if referenced via `{% extends %}` or `{% include %}` from another template
- [ ] `db.session.commit()` is always paired with `db.session.add()`/`db.session.delete()`
- [ ] Every `except` block around DB operations calls `db.session.rollback()`
- [ ] No global variable holds a DB cursor or connection
- [ ] No raw `sqlite3` usage alongside Flask-SQLAlchemy
- [ ] App imports without error after each removal
- [ ] `db.create_all()` succeeds after column removals

---

**Clean code is not about brevity — it is about certainty. Every line that remains must have a provable execution path.**
