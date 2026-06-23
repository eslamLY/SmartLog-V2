"""
Icon management utilities for SmartLog.
Centralizes icon references, supports Font Awesome and Tabler Icons,
and provides cache-busting for static assets.

Usage in templates:
    {{ icon('dashboard', 'ti ti-layout-dashboard') }}
    {{ icon('fa-users', 'fas fa-users') }}
    {{ static_url('css/style.css') }}

Before/After:
    Before: <i class="ti ti-users"></i>
    After:  {{ icon('ti-users', 'ti ti-users') }}

    Before: <link rel="stylesheet" href="/static/css/style.css">
    After:  <link rel="stylesheet" href="{{ static_url('css/style.css') }}">
"""
import os
import hashlib

_STATIC_FOLDER = None
_HASH_CACHE = {}


def _get_static_folder():
    global _STATIC_FOLDER
    if _STATIC_FOLDER is None:
        _STATIC_FOLDER = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static'
        )
    return _STATIC_FOLDER


def file_hash(relative_path: str) -> str:
    """Return MD5 hash prefix of a static file for cache busting."""
    if relative_path in _HASH_CACHE:
        return _HASH_CACHE[relative_path]
    abs_path = os.path.join(_get_static_folder(), relative_path)
    if os.path.isfile(abs_path):
        with open(abs_path, 'rb') as f:
            h = hashlib.md5(f.read()).hexdigest()[:8]
            _HASH_CACHE[relative_path] = h
            return h
    return 'dev'


# ─── Icon Library Registry ────────────────────────────────────────────────

ICON_LIBS = {
    'ti': {
        'name': 'Tabler Icons',
        'cdn_css': 'https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.24.0/dist/tabler-icons.min.css',
        'prefix': 'ti',
    },
    'fas': {
        'name': 'Font Awesome Solid',
        'cdn_css': 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
        'prefix': 'fas',
    },
    'far': {
        'name': 'Font Awesome Regular',
        'cdn_css': 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
        'prefix': 'far',
    },
    'fab': {
        'name': 'Font Awesome Brands',
        'cdn_css': 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
        'prefix': 'fab',
    },
    'fa': {
        'name': 'Font Awesome (auto-detect)',
        'cdn_css': 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
        'prefix': 'fa',
    },
}

ICON_MAP = {
    # Dashboard & Navigation
    'dashboard':     'ti ti-layout-dashboard',
    'employees':     'ti ti-users',
    'attendance':    'ti ti-clock-record',
    'shifts':        'ti ti-calendar-event',
    'leaves':        'ti ti-calendar',
    'departments':   'ti ti-building',
    'reports':       'ti ti-chart-bar',
    'payroll':       'ti ti-currency-dollar',
    'analytics':     'ti ti-chart-line',
    'settings':      'ti ti-settings',
    'notifications': 'ti ti-bell',
    'logout':        'ti ti-logout',
    'backup':        'ti ti-database-export',
    'audit':         'ti ti-history',
    'permissions':   'ti ti-lock',
    'devices':       'ti ti-devices',
    'gps':           'ti ti-map-pin',
    'documents':     'ti ti-files',
    'branding':      'ti ti-palette',
    'qr':            'ti ti-qrcode',
    'ai':            'ti ti-brain',
    'forecast':      'ti ti-chart-arrows',

    # Actions
    'add':           'ti ti-plus',
    'edit':          'ti ti-edit',
    'delete':        'ti ti-trash',
    'save':          'ti ti-device-floppy',
    'search':        'ti ti-search',
    'filter':        'ti ti-filter',
    'export':        'ti ti-download',
    'import':        'ti ti-upload',
    'refresh':       'ti ti-refresh',
    'print':         'ti ti-printer',
    'approve':       'ti ti-circle-check',
    'reject':        'ti ti-circle-x',
    'cancel':        'ti ti-x',
    'send':          'ti ti-send',

    # Status
    'success':       'ti ti-circle-check',
    'warning':       'ti ti-alert-triangle',
    'error':         'ti ti-alert-circle',
    'info':          'ti ti-info-circle',
    'loading':       'ti ti-loader',

    # Misc
    'user':          'ti ti-user',
    'clock':         'ti ti-clock',
    'calendar':      'ti ti-calendar',
    'location':      'ti ti-map-pin',
    'phone':         'ti ti-phone',
    'email':         'ti ti-mail',
    'password':      'ti ti-lock',
    'upload':        'ti ti-cloud-upload',
    'download':      'ti ti-cloud-download',
}


def icon(name: str, fallback: str = 'ti ti-icon') -> str:
    """Returns the icon class for a given semantic name.
    Falls back to the supplied default if name not in ICON_MAP.
    """
    return ICON_MAP.get(name, fallback)


def icon_html(name: str, fallback: str = 'ti ti-icon', extra_style: str = '') -> str:
    """Returns a complete <i> tag for the given icon name."""
    cls = icon(name, fallback)
    style_attr = f' style="{extra_style}"' if extra_style else ''
    return f'<i class="{cls}"{style_attr}></i>'


def needed_cdn_libs(classes: list[str]) -> set[str]:
    """Determine which CDN CSS files are needed based on icon class prefixes."""
    needed = set()
    for cls in classes:
        for prefix, info in ICON_LIBS.items():
            if cls.startswith(prefix):
                needed.add(info['cdn_css'])
                break
    if not needed:
        needed.add(ICON_LIBS['ti']['cdn_css'])
    return needed


def static_url(relative_path: str, local: bool = True) -> str:
    """Generate a static URL with cache-busting hash.
    
    Before: /static/css/style.css
    After:  /static/css/style.css?v=1a2b3c4d
    
    Set local=False to skip hash (for CDN references).
    """
    if not local:
        return relative_path
    if relative_path.startswith('http://') or relative_path.startswith('https://'):
        return relative_path
    h = file_hash(relative_path)
    return f'/static/{relative_path}?v={h}'


def update_template_with_url_for(template_content: str) -> str:
    """Convert hardcoded /static/ paths to url_for('static', ...) calls.
    This is a helper for migration, not for runtime use.
    
    Before: href="/static/css/style.css"
    After:  href="{{ url_for('static', filename='css/style.css') }}"
    """
    import re
    content = template_content
    
    # Replace href="/static/... patterns
    content = re.sub(
        r'(href=)"(?:/[sS]t[aA][tT][iI][cC])?/static/([^"]*)"',
        r'\1"{{ url_for(\'static\', filename=\'\2\') }}"',
        content
    )
    # Replace src="/static/... patterns
    content = re.sub(
        r'(src=)"(?:/[sS]t[aA][tT][iI][cC])?/static/([^"]*)"',
        r'\1"{{ url_for(\'static\', filename=\'\2\') }}"',
        content
    )
    return content
