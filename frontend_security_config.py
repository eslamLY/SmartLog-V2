#!/usr/bin/env python3
"""
SmartLog V2 — Frontend Security Configuration
=================================================
Correct Flask security settings for frontend protection.
This file provides the IDEAL configuration — NOT loaded automatically.
Use as reference to update app.py, config.py, and base.html.
"""
import os, sys

SEP = '=' * 70


def print_section(title):
    print(f'\n{SEP}')
    print(f'  {title}')
    print(SEP)


def print_config():

    # ════════════════════════════════════════════════════════
    # 1. COOKIE CONFIGURATION (app.py or config.py)
    # ════════════════════════════════════════════════════════
    print_section('1. Cookie Security (config.py / app.py)')

    print('''
# app.py — Production cookie settings
app.config['SESSION_COOKIE_HTTPONLY'] = True     # Not accessible via JS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'    # CSRF protection
app.config['SESSION_COOKIE_SECURE'] = True       # HTTPS only (production)
app.config['SESSION_COOKIE_NAME'] = '__Secure-session'  # Prefix for HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Slide expiration
''')

    # ════════════════════════════════════════════════════════
    # 2. SECURITY HEADERS (app.py)
    # ════════════════════════════════════════════════════════
    print_section('2. Security Headers (app.py — after_request handler)')

    print('''Recommended production_security_headers():

@app.after_request
def production_security_headers(response):
    if not PRODUCTION:
        return response
    host = request.host.split(':')[0].lower()
    if host in ('localhost', '127.0.0.1', '::1'):
        return response
    if not request.is_secure:
        secure_url = request.url.replace('http://', 'https://', 1)
        return redirect(secure_url, code=301)

    # HSTS — 1 year (submit to hstspreload.org)
    response.headers['Strict-Transport-Security'] = \\
        'max-age=31536000; includeSubDomains; preload'

    # Prevent MIME sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'

    # Content Security Policy
    csp = getattr(app, '_csp_string', None)
    if not csp:
        from config import ProductionConfig
        csp = ProductionConfig.csp_string()
        app._csp_string = csp
    response.headers['Content-Security-Policy'] = csp

    # Referrer policy — don't leak URL params
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # Permissions policy — disable unused features
    response.headers['Permissions-Policy'] = \\
        'camera=(), microphone=(), geolocation=(self), ' \\
        'payment=(), usb=(), fullscreen=()

    # Cache control for admin pages
    if request.path.startswith('/admin'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'

    # Remove Server header
    if 'Server' in response.headers:
        del response.headers['Server']

    return response
''')

    # ════════════════════════════════════════════════════════
    # 3. CSP — STRICT VERSION (config.py)
    # ════════════════════════════════════════════════════════
    print_section('3. Strict Content-Security-Policy (config.py)')

    print('''Current CSP uses 'unsafe-inline'. To harden:

OPTION A — Nonce-based CSP (recommended):

In app.py context_processor:
    @app.context_processor
    def inject_csp_nonce():
        import uuid, flask.g
        nonce = uuid.uuid4().hex
        flask.g.csp_nonce = nonce
        return {'csp_nonce': nonce}

In config.py csp_string():
    @classmethod
    def csp_string(cls, nonce=''):
        cdn_script = ' '.join(f'https://{d}' for d in cls.CDN_WHITELIST)
        cdn_style = ' '.join(f'https://{d}' for d in cls.CDN_WHITELIST)
        script_src = f"'self' 'nonce-{nonce}' {cdn_script}"
        style_src = f"'self' 'nonce-{nonce}' {cdn_style}"
        return (
            f"default-src 'self'; "
            f"script-src {script_src}; "
            f"style-src {style_src}; "
            f"img-src 'self' data: blob: {cdn_script}; "
            f"font-src 'self' {cdn_style}; "
            f"connect-src 'self'; "
            f"frame-ancestors 'none';"
        )

In templates:
    <script nonce="{{ csp_nonce }}">...</script>
    <style nonce="{{ csp_nonce }}">...</style>

OPTION B — Keep unsafe-inline but add restrictions:
    f"script-src 'self' 'unsafe-inline' {cdn_script}; "
    f"style-src 'self' 'unsafe-inline' {cdn_style}; "
''')

    # ════════════════════════════════════════════════════════
    # 4. CSRF — GLOBAL WRAPPER (base.html)
    # ════════════════════════════════════════════════════════
    print_section('4. CSRF Protection — Global fetch() Wrapper (base.html)')

    print('''Replace the api() function with a global csrfFetch():

<script>
function csrfFetch(url, options) {
  options = options || {};
  options.headers = options.headers || {};
  options.headers['Content-Type'] = options.headers['Content-Type'] || 'application/json';
  
  // Add CSRF token for state-changing methods
  if (options.method && options.method !== 'GET') {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) options.headers['X-CSRFToken'] = meta.content;
  }
  
  return fetch(url, options).then(function(r) {
    if (r.status === 403) {
      return r.json().then(function(j) {
        if (j.msg && j.msg.includes('CSRF')) {
          toast('انتهت صلاحية الجلسة. أعد تحميل الصفحة.', 'error');
          return {ok: false, msg: 'CSRF rejected'};
        }
        return j;
      });
    }
    return r.json();
  });
}

// Keep api() for backward compatibility, but it uses csrfFetch internally:
function api(url, data) {
  return csrfFetch(url, {
    method: data ? 'POST' : 'GET',
    body: data ? JSON.stringify(data) : undefined
  });
}
</script>

Then replace ALL fetch() calls in templates with csrfFetch() or api().
''')

    # ════════════════════════════════════════════════════════
    # 5. XSS — GLOBAL ESCAPE FUNCTION
    # ════════════════════════════════════════════════════════
    print_section('5. XSS Prevention — Global esc() in base.html')

    print('''Add this to base.html to use across all templates:

<script>
function esc(s) {
  if (s == null) return '';
  var d = document.createElement('div');
  d.appendChild(document.createTextNode(String(s)));
  return d.innerHTML;
}

// Also add safe template literal tag:
function safe(strings) {
  var result = strings[0];
  for (var i = 1; i < arguments.length; i++) {
    result += esc(arguments[i]) + strings[i];
  }
  return result;
}
</script>

Usage in templates:
  // BEFORE (vulnerable):
  container.innerHTML = '<div>' + user.name + '</div>';

  // AFTER (safe):
  container.innerHTML = safe'<div>${user.name}</div>';
  // or:
  container.textContent = user.name;
  // or:
  container.innerHTML = esc(user.name);
''')

    # ════════════════════════════════════════════════════════
    # 6. SRI — Subresource Integrity
    # ════════════════════════════════════════════════════════
    print_section('6. Subresource Integrity (base.html — CDN links)')

    print('''Replace current CDN links with SRI versions:

<!-- Tabler Icons -->
<link rel="stylesheet" 
      href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.24.0/dist/tabler-icons.min.css"
      integrity="sha384-2UZ4CqOJtM2lX8K1Sj9pFE0O6eJHfQMgCnLkYz5o2QHKq3hfW8GdVY7K1BZpV6E"
      crossorigin="anonymous">

<!-- Font Awesome -->
<link rel="stylesheet" 
      href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"
      integrity="sha384-DVvF6Pq8aJ6sDEvJ/Z2Uq2l0Q4s5p4OJ5tTXskz/Zt+Z3w2kRz4pMfPRQZuGSiH"
      crossorigin="anonymous">

<!-- SweetAlert2 -->
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"
        integrity="sha384-2ZfT5J8e4JfT0x8kE4Gv5K0F0h5l5j6F5p5n5j5n5j5"
        crossorigin="anonymous"></script>

<!-- Google Fonts -->
<link rel="stylesheet" 
      href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap"
      crossorigin="anonymous">

NOTE: Replace the integrity hash values with actual hashes from srihash.org.
''')

    # ════════════════════════════════════════════════════════
    # 7. ERROR PAGES
    # ════════════════════════════════════════════════════════
    print_section('7. Custom Error Pages')

    print('''Create these templates to prevent default error pages:

templates/errors/404.html — not found
templates/errors/500.html — server error (NO stack traces!)
templates/errors/csrf.html — CSRF failure

app.py changes:
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        log.error('500 on %s %s', request.method, request.path)
        log.exception(e)
        return render_template('errors/500.html'), 500
''')

    # ════════════════════════════════════════════════════════
    # 8. SERVICE WORKER
    # ════════════════════════════════════════════════════════
    print_section('8. Service Worker / PWA Security')

    print('''The current service worker is a Python string in routes/auth.py:34-42.
Move to a static file for better security and maintainability.

static/sw.js (actual .js file, not generated):
    const CACHE = 'bb-v4';
    const OFFLINE = ['/login', '/manifest.json'];
    self.addEventListener('install', e => {
      self.skipWaiting();
      e.waitUntil(caches.open(CACHE).then(c => c.addAll(OFFLINE)));
    });
    self.addEventListener('activate', e => {
      e.waitUntil(caches.keys().then(ks =>
        Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))
      ));
    });
    self.addEventListener('fetch', e => {
      if (e.request.method !== 'GET') return;
      e.respondWith(
        fetch(e.request).catch(() => caches.match(e.request))
      );
    });
''')

    # ════════════════════════════════════════════════════════
    # 9. REQUIREMENTS
    # ════════════════════════════════════════════════════════
    print_section('9. Requirements Checklist')

    print('''After implementing all above:

[X] SESSION_COOKIE_HTTPONLY = True
[X] SESSION_COOKIE_SAMESITE = 'Lax'
[X] SESSION_COOKIE_SECURE = True (prod)
[X] Content-Security-Policy header set
[X] X-Frame-Options: DENY
[X] X-Content-Type-Options: nosniff
[X] HSTS: max-age=31536000 (prod)
[ ] Referrer-Policy: strict-origin-when-cross-origin
[ ] Permissions-Policy restricting features
[ ] SRI on all CDN links
[ ] Global esc() function for XSS prevention
[ ] CSRF token on all state-changing requests
[ ] Custom 404/500 error pages
[ ] No eval() / document.write() / new Function()
[ ] No sensitive data in localStorage
[ ] Cache-Control: no-store for admin pages
''')

    print(f'\n{SEP}')
    print('  END OF FRONTEND SECURITY CONFIGURATION')
    print(f'{SEP}')


if __name__ == '__main__':
    print_config()
