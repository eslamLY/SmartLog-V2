"""Cached wrappers for high-frequency read queries.

Uses the TTL-based in-memory cache from services/performance.py.
Department queries are cached because they change infrequently
yet are fetched on nearly every page load.
"""
from types import SimpleNamespace
from services.performance import cached, invalidate_cache


def _dept_to_dict(d):
    return {
        'id': d.id,
        'code': d.code,
        'name_ar': d.name_ar,
        'name_en': d.name_en,
        'is_active': d.is_active,
        'icon': d.icon,
        'color': d.color,
        'parent_id': d.parent_id,
        'dept_level': d.dept_level,
        'description_ar': d.description_ar,
        'description_en': d.description_en,
        'dept_type': d.dept_type,
        'min_staff_required': d.min_staff_required,
        'max_staff_capacity': d.max_staff_capacity,
    }


def _dept_ns(d):
    return SimpleNamespace(**_dept_to_dict(d))


# ── Active departments sorted by name_ar ────────────────────────────────

@cached(ttl_seconds=60)
def _cached_active_departments():
    from models import Department
    qs = Department.query.filter_by(is_active=True).order_by(Department.name_ar).all()
    return [_dept_to_dict(d) for d in qs]


def get_active_departments():
    """Return list of SimpleNamespace objects (supports d.id, d.name_ar in templates)."""
    return [_dept_ns(d) for d in _cached_active_departments()]


def get_active_departments_json():
    """Return list of dicts suitable for jsonify(), each with id + name_ar."""
    return [{'id': d['id'], 'name_ar': d['name_ar']} for d in _cached_active_departments()]


# ── All departments sorted by id ────────────────────────────────────────

@cached(ttl_seconds=60)
def _cached_all_departments_by_id():
    from models import Department
    qs = Department.query.order_by(Department.id).all()
    return [_dept_to_dict(d) for d in qs]


def get_all_departments_by_id():
    return [_dept_ns(d) for d in _cached_all_departments_by_id()]


# ── All departments sorted by name_ar ───────────────────────────────────

@cached(ttl_seconds=60)
def _cached_all_departments_by_name():
    from models import Department
    qs = Department.query.order_by(Department.name_ar).all()
    return [_dept_to_dict(d) for d in qs]


def get_all_departments_by_name():
    return [_dept_ns(d) for d in _cached_all_departments_by_name()]


# ── Invalidation shortcut ───────────────────────────────────────────────

def invalidate_department_cache():
    """Call after any department add / update / delete / toggle."""
    invalidate_cache('_cached_active_departments')
    invalidate_cache('_cached_all_departments_by_id')
    invalidate_cache('_cached_all_departments_by_name')
