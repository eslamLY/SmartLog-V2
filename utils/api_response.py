"""
utils/api_response.py — Canonical API response envelope.

Single source of truth for machine-readable API payloads.

Standard error shape (Arabic-first):
    {
      "success": false,
      "error": "وصف الخطأ بالعربية",
      "code": "ERROR_CODE"
    }

Backward compatibility
----------------------
The pre-existing front end (70 of 140 template/JS files) reads ``ok`` and
``msg``.  Those keys are therefore emitted as *aliases* alongside the
standard keys so no UI regression occurs while the standard is adopted.
Success payloads keep the legacy ``ok``/``msg`` pair untouched — this module
only governs the *error* path, so existing success consumers are unaffected.
"""
import functools
import logging
from typing import Any, Dict, Optional, Tuple

from flask import jsonify

log = logging.getLogger('app')

# ── Canonical Arabic messages keyed by error code ───────────────────────────
ERROR_MESSAGES: Dict[str, str] = {
    'BAD_REQUEST': 'طلب غير صالح. تحقق من البيانات المرسلة.',
    'VALIDATION_ERROR': 'البيانات المرسلة غير صالحة.',
    'UNAUTHORIZED': 'يجب تسجيل الدخول أولاً.',
    'FORBIDDEN': 'ليس لديك صلاحية للوصول إلى هذا المورد.',
    'NOT_FOUND': 'الصفحة أو المورد المطلوب غير موجود.',
    'INTERNAL_ERROR': 'حدث خطأ داخلي في الخادم. الرجاء المحاولة لاحقاً.',
    'RATE_LIMITED': 'محاولات كثيرة جداً. انتظر قليلاً.',
    'CSRF_FAILED': 'طلب غير مصرح به (CSRF). أعد تحميل الصفحة.',
    'DB_NOT_READY': 'قاعدة البيانات غير جاهزة بعد. حاول بعد قليل.',
    'METHOD_NOT_ALLOWED': 'طريقة الطلب غير مسموح بها.',
    'IP_BLOCKED': 'تم حظر عنوانك مؤقتاً بسبب تكرار الطلبات.',
    'PAYLOAD_TOO_LARGE': 'حجم الملف أكبر من الحد المسموح.',
    'CONFLICT': 'تعارض في البيانات. تحقق من البيانات المحفوظة وأعد المحاولة.',
    'NOT_READY': 'الخدمة غير جاهزة حالياً.',
}

# HTTP status -> default error code
_STATUS_CODES: Dict[int, str] = {
    400: 'BAD_REQUEST',
    401: 'UNAUTHORIZED',
    403: 'FORBIDDEN',
    404: 'NOT_FOUND',
    405: 'METHOD_NOT_ALLOWED',
    409: 'CONFLICT',
    413: 'PAYLOAD_TOO_LARGE',
    429: 'RATE_LIMITED',
    503: 'NOT_READY',
}


def build_error_payload(
    message: Optional[str] = None,
    code: Optional[str] = None,
    status: int = 400,
    **extra: Any,
) -> Dict[str, Any]:
    """Build the canonical error dict (standard keys + legacy aliases)."""
    resolved_code = code or _STATUS_CODES.get(status, 'INTERNAL_ERROR')
    resolved_msg = message or ERROR_MESSAGES.get(resolved_code, ERROR_MESSAGES['INTERNAL_ERROR'])

    payload: Dict[str, Any] = {
        'success': False,
        'error': resolved_msg,
        'code': resolved_code,
        # Legacy aliases — remove only after all front-end consumers migrate.
        'ok': False,
        'msg': resolved_msg,
    }
    payload.update(extra)
    return payload


def error_response(
    message: Optional[str] = None,
    code: Optional[str] = None,
    status: int = 400,
    **extra: Any,
) -> Tuple[Any, int]:
    """Return a ``(jsonify(...), status)`` tuple using the standard shape."""
    return jsonify(build_error_payload(message, code, status, **extra)), status


def success_response(payload: Optional[Dict[str, Any]] = None, **extra: Any) -> Any:
    """Return a success payload that also advertises the standard envelope."""
    body: Dict[str, Any] = {'success': True, 'ok': True}
    if payload:
        body.update(payload)
    body.update(extra)
    return jsonify(body)


def log_exception(context: str, exc: BaseException) -> None:
    """Server-side logging of an exception. Never returns internals to the client."""
    log.error('%s: %s: %s', context, type(exc).__name__, exc, exc_info=True)


def _rollback() -> None:
    """Best-effort session rollback so a failed request never poisons the pool."""
    try:
        from models import db
        db.session.rollback()
    except Exception:  # pragma: no cover - rollback must never mask the original error
        pass


def api_guard(f, logger=None, extra: Optional[Dict[str, Any]] = None):
    """Build the standard API guard used by every blueprint's ``safe_api``.

    Behaviour:
      * Rolls the session back on any failure so a poisoned transaction is
        never reused by a later request in the same worker.
      * Classifies client-input errors (``ValueError``/``TypeError``/``KeyError``
        from unvalidated ``int()``/``float()``/dict access on request data) as
        **400 VALIDATION_ERROR** instead of masking them as 500s.
      * Logs the real exception server-side; the client only ever sees a
        sanitised Arabic message.
    """
    log_target = logger or log

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except (ValueError, TypeError, KeyError) as exc:
            _rollback()
            log_target.error('Invalid input in %s: %s: %s',
                             f.__name__, type(exc).__name__, exc)
            return error_response(code='VALIDATION_ERROR', status=400, **(extra or {}))
        except Exception as exc:
            _rollback()
            log_exception(f'API error in {f.__name__}', exc)
            return error_response(code='INTERNAL_ERROR', status=500, **(extra or {}))

    return wrapper
