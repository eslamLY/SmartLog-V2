from functools import wraps
from flask import jsonify, request
from services.permission_service import check_permission, check_any_permission, check_all_permissions

def permission_required(permission_code):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = getattr(request, 'user_id', None)
            if not user_id:
                return jsonify({'ok': False, 'msg': 'غير مصرح'}), 401
            if not check_permission(user_id, permission_code):
                return jsonify({'ok': False, 'msg': 'ليس لديك صلاحية لهذا الإجراء'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def any_permission_required(*permission_codes):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = getattr(request, 'user_id', None)
            if not user_id:
                return jsonify({'ok': False, 'msg': 'غير مصرح'}), 401
            if not check_any_permission(user_id, permission_codes):
                return jsonify({'ok': False, 'msg': 'ليس لديك صلاحية لهذا الإجراء'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def all_permissions_required(*permission_codes):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = getattr(request, 'user_id', None)
            if not user_id:
                return jsonify({'ok': False, 'msg': 'غير مصرح'}), 401
            if not check_all_permissions(user_id, permission_codes):
                return jsonify({'ok': False, 'msg': 'ليس لديك صلاحية لهذا الإجراء'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
