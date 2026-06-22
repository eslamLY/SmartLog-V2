"""IP-based adaptive rate limiter with 3‑tier escalating bans + DB persistence."""

from collections import defaultdict
from datetime import datetime, timedelta, UTC
from threading import Lock

# ─── In‑memory request tracking (fast path, no DB hit per request) ───────
_ip_request_log = defaultdict(list)
_ip_request_log_lock = Lock()

# ─── Legacy helpers (used by specific endpoint decorators) ───────────────
_request_log = defaultdict(list)

def reset_rate_limits():
    with _ip_request_log_lock:
        _ip_request_log.clear()
    with _banned_ips_cache_lock:
        _banned_ips_cache.clear()
    _request_log.clear()

# ─── Route‑level rate limit (legacy, per‑endpoint) ──────────────────────
def check_rate_limit(route_key, max_requests=30, window_seconds=60):
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=window_seconds)
    _request_log[route_key] = [t for t in _request_log[route_key] if t > cutoff]
    if len(_request_log[route_key]) >= max_requests:
        return False, 0
    _request_log[route_key].append(now)
    remaining = max(0, max_requests - len(_request_log[route_key]))
    return True, remaining

def rate_limit_headers(max_requests, remaining, window_seconds=60):
    return {
        'X-RateLimit-Limit': str(max_requests),
        'X-RateLimit-Remaining': str(remaining),
        'X-RateLimit-Reset': str(int((datetime.now(UTC) + timedelta(seconds=window_seconds)).timestamp())),
    }

# ─── Global IP flood limiter (used by before_request) ────────────────────
_banned_ips_cache = {}  # ip -> dict with keys: 'expiry', 'response'
_banned_ips_cache_lock = Lock()

def check_ip_flood(ip_address: str, max_requests: int = 100,
                   window_seconds: int = 60) -> dict:
    now = datetime.now(UTC)

    # 0. Fast in-memory banned cache (avoids DB hit for already-banned IPs)
    with _banned_ips_cache_lock:
        cached = _banned_ips_cache.get(ip_address)
        if cached:
            expiry = cached['expiry']
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            if expiry > now:
                return cached['response']
            _banned_ips_cache.pop(ip_address, None)

    # 1. Check DB for active ban
    ban = _check_db_ban(ip_address)
    if ban:
        return ban

    # 2. In-memory sliding-window count
    cutoff = now - timedelta(seconds=window_seconds)
    with _ip_request_log_lock:
        timestamps = _ip_request_log.get(ip_address, [])
        timestamps = [t for t in timestamps if t > cutoff]
        timestamps.append(now)
        _ip_request_log[ip_address] = timestamps
        count = len(timestamps)

    if count <= max_requests:
        return {'ok': True}

    # 3. Threshold exceeded → escalate & persist
    return _apply_ban(ip_address)

def _check_db_ban(ip_address: str) -> dict | None:
    """Return ban dict if IP is currently blocked in DB, else None."""
    try:
        from models import db
        from models.security import BlockedIP
        rec = BlockedIP.query.filter_by(ip_address=ip_address, is_active=True).first()
        if not rec:
            return None
        now = datetime.now(UTC)
        expiry = rec.ban_expiry
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if rec.is_permanent:
            return {'ok': False, 'ban_minutes': 0, 'violation': 3, 'permanent': True}
        if expiry and expiry > now:
            remaining = int((expiry - now).total_seconds() // 60)
            return {'ok': False, 'ban_minutes': remaining or 1, 'violation': rec.violation_count, 'permanent': False}
        if expiry and expiry <= now:
            rec.is_active = False
            db.session.commit()
        return None
    except Exception:
        return None

def _apply_ban(ip_address: str) -> dict:
    """Ban IP for 2 minutes on any violation."""
    try:
        from models import db
        from models.security import BlockedIP
        from models.notifications import Notification
        from models.employee import Employee

        now = datetime.now(UTC)
        ban_min = 2

        rec = BlockedIP.query.filter_by(ip_address=ip_address).first()
        if rec:
            rec.violation_count += 1
            rec.is_active = True
        else:
            rec = BlockedIP(ip_address=ip_address, violation_count=1, is_active=True)
            db.session.add(rec)

        rec.ban_expiry = now + timedelta(minutes=ban_min)
        rec.is_permanent = False
        rec.updated_at = now
        db.session.flush()

        admins = Employee.query.filter_by(role='admin', is_active=True).all()
        for admin in admins:
            db.session.add(Notification(
                employee_id=admin.id, title='⚠️ تنبيه حظر',
                message=f'تم حظر IP {ip_address} لمدة {ban_min} دقيقتين — تجاوز حد 266 أمر في الدقيقة.',
                ntype='warning', icon='alert-triangle', is_global=False,
            ))
        db.session.commit()

        with _banned_ips_cache_lock:
            _banned_ips_cache[ip_address] = {
                'expiry': rec.ban_expiry,
                'response': {'ok': False, 'ban_minutes': ban_min, 'violation': rec.violation_count, 'permanent': False},
            }

        _cleanup_memory(ip_address)
        return {'ok': False, 'ban_minutes': ban_min, 'violation': rec.violation_count, 'permanent': False}

    except Exception:
        db.session.rollback()
        return {'ok': False, 'ban_minutes': 5, 'violation': 1, 'permanent': False}

def _cleanup_memory(ip_address: str):
    """Remove IP from in-memory log so next request hits DB check."""
    with _ip_request_log_lock:
        _ip_request_log.pop(ip_address, None)


# ─── Legacy per‑user flood limiter (kept for compatibility) ──────────────
_user_action_log = defaultdict(list)
_user_blocked_until = {}
_user_offense_count = defaultdict(int)

def check_flood_limit(user_id, max_actions=80, window_seconds=60, ban_minutes=5):
    now = datetime.now(UTC)
    blocked = _user_blocked_until.get(user_id)
    if blocked and blocked > now:
        return False, _user_blocked_until[user_id]
    cutoff = now - timedelta(seconds=window_seconds)
    _user_action_log[user_id] = [t for t in _user_action_log[user_id] if t > cutoff]
    _user_action_log[user_id].append(now)
    if len(_user_action_log[user_id]) > max_actions:
        _user_offense_count[user_id] += 1
        offense = _user_offense_count[user_id]
        actual_ban = ban_minutes * (2 if offense > 1 else 1)
        _user_blocked_until[user_id] = now + timedelta(minutes=actual_ban)
        _notify_admin_legacy(user_id, actual_ban, offense)
        return False, _user_blocked_until[user_id]
    return True, None

def _notify_admin_legacy(user_id, ban_minutes, offense_count):
    try:
        from models import db
        from models.notifications import Notification
        from models.employee import Employee
        user = Employee.query.get(user_id)
        uname = user.full_name if user else f'user#{user_id}'
        admins = Employee.query.filter_by(role='admin', is_active=True).all()
        for admin in admins:
            note = Notification(
                employee_id=admin.id, title='⚠️ تنبيه حظر',
                message=f'تم حظر {uname} لمدة {ban_minutes} دقائق (المخالفة #{offense_count}) — تجاوز حد 80 أمر في الدقيقة.',
                ntype='warning', icon='alert-triangle', is_global=False,
            )
            db.session.add(note)
        db.session.commit()
    except Exception:
        db.session.rollback()
