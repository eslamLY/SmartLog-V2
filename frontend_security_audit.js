/*
 * SmartLog V2 — Frontend Security Audit Script
 * ==============================================
 * Copy-paste this entire file into the browser console
 * while on the SmartLog V2 website.
 *
 * Output: JSON results + HTML table.
 */

(function() {
  'use strict';

  var results = [];
  var id = 0;

  function add(category, severity, title, detail) {
    results.push({ id: ++id, category: category, severity: severity,
                   title: title, detail: detail });
  }

  function color(sev) {
    return { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308',
             LOW: '#3b82f6', INFO: '#6b7280', PASS: '#22c55e' }[sev] || '#6b7280';
  }

  function esc(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                     .replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  // ── 1. Security Headers ─────────────────────────────────
  function checkHeaders(headers) {
    var headerTests = {
      'Content-Security-Policy': { sev: 'INFO', name: 'CSP' },
      'Strict-Transport-Security': { sev: 'INFO', name: 'HSTS' },
      'X-Content-Type-Options': { sev: 'INFO', name: 'X-Content-Type-Options' },
      'X-Frame-Options': { sev: 'INFO', name: 'X-Frame-Options' },
      'Referrer-Policy': { sev: 'MEDIUM', name: 'Referrer-Policy' },
      'Permissions-Policy': { sev: 'LOW', name: 'Permissions-Policy' },
    };
    for (var h in headerTests) {
      var val = headers[h];
      var info = headerTests[h];
      if (val) {
        add('HEADERS', info.sev, info.name + ' — Present',
            h + ': ' + val.slice(0, 120));
      } else {
        add('HEADERS', 'MEDIUM', info.name + ' — MISSING',
            h + ' header not found in response');
      }
    }
  }

  // ── 2. Cookies ────────────────────────────────────────────
  function checkCookies() {
    var cookies = document.cookie.split(';').map(function(c) { return c.trim(); }).filter(Boolean);
    if (cookies.length === 0) {
      add('COOKIES', 'INFO', 'No cookies (HttpOnly cookies not visible to JS)',
          'This is expected for HttpOnly session cookies');
      return;
    }
    cookies.forEach(function(c) {
      var parts = c.split('=');
      add('COOKIES', 'HIGH', 'Cookie accessible via JS: ' + parts[0],
          'Cookie "' + parts[0] + '" is not HttpOnly — vulnerable to XSS token theft');
    });
  }

  // ── 3. CSRF Meta Tag ──────────────────────────────────────
  function checkCSRF() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content && meta.content.length > 8) {
      add('CSRF', 'PASS', 'CSRF meta tag present with token',
          'Token length: ' + meta.content.length + ' chars');
    } else if (meta) {
      add('CSRF', 'HIGH', 'CSRF meta tag present but token is invalid/short',
          'Token: "' + meta.content + '"');
    } else {
      add('CSRF', 'HIGH', 'CSRF meta tag MISSING',
          'No <meta name="csrf-token"> found — CSRF protection may be absent');
    }
  }

  // ── 4. Check for eval() / innerHTML / dangerous patterns ─
  function checkDangerousJS() {
    var scripts = document.querySelectorAll('script:not([src])');
    scripts.forEach(function(s) {
      var text = s.textContent || '';
      if (text.includes('eval('))
        add('XSS', 'CRITICAL', 'eval() found in inline script',
            'Remove eval() — use JSON.parse or Function constructor alternatives');
      if (text.includes('new Function('))
        add('XSS', 'HIGH', 'new Function() found in inline script', '');
      if (text.includes('document.write('))
        add('XSS', 'HIGH', 'document.write() found', '');
    });

    // Check innerHTML assignments that use user data
    var allElements = document.querySelectorAll('*');
    var innerHTMLCount = 0;
    allElements.forEach(function(el) {
      if (el.innerHTML && el.innerHTML.includes('{{')) innerHTMLCount++;
    });
    if (innerHTMLCount > 0) {
      add('XSS', 'INFO', innerHTMLCount + ' element(s) contain unrendered Jinja2',
          'Jinja2 template syntax visible in DOM');
    }
  }

  // ── 5. External Resources & SRI ───────────────────────────
  function checkExternalResources() {
    var resources = [];
    document.querySelectorAll('script[src],link[href]').forEach(function(el) {
      var url = el.src || el.href;
      if (url && (url.startsWith('http:') || url.startsWith('https:'))) {
        var hasSRI = el.integrity && el.integrity.length > 20;
        var sameOrigin = url.includes(location.hostname);
        resources.push({ url: url, sri: hasSRI, sameOrigin: sameOrigin });
      }
    });

    var noSRI = resources.filter(function(r) { return !r.sri && !r.sameOrigin; });
    if (noSRI.length > 0) {
      add('THIRDPARTY', 'HIGH', noSRI.length + ' external resource(s) without SRI',
          noSRI.map(function(r) { return r.url; }).join('\n'));
    }
    resources.filter(function(r) { return r.sri; }).forEach(function(r) {
      add('THIRDPARTY', 'PASS', 'SRI on: ' + r.url.split('/').pop(), '');
    });
  }

  // ── 6. localStorage / sessionStorage ──────────────────────
  function checkStorage() {
    try {
      var ls = Object.keys(localStorage);
      if (ls.length > 0) {
        ls.forEach(function(k) {
          var val = localStorage.getItem(k);
          var isSensitive = /token|secret|key|password|auth|session/i.test(k);
          if (isSensitive) {
            add('STORAGE', 'CRITICAL', 'Sensitive data in localStorage: ' + k,
                'localStorage is accessible to any JS on this page');
          } else {
            add('STORAGE', 'LOW', 'localStorage key: ' + k,
                'Value length: ' + (val ? val.length : 0) + ' chars');
          }
        });
      } else {
        add('STORAGE', 'PASS', 'localStorage is empty (no sensitive data stored)');
      }
    } catch(e) {
      add('STORAGE', 'INFO', 'Cannot access localStorage', e.message);
    }
  }

  // ── 7. CSP Analysis ────────────────────────────────────────
  function checkCSP(csp) {
    if (!csp) {
      add('CSP', 'HIGH', 'Content-Security-Policy not set');
      return;
    }
    var parts = csp.split(';').map(function(p) { return p.trim(); }).filter(Boolean);
    parts.forEach(function(p) {
      if (p.includes("'unsafe-inline'"))
        add('CSP', 'MEDIUM', 'CSP allows unsafe-inline: ' + p.split(' ')[0],
            'Consider using nonces for inline scripts/styles');
      if (p.includes('*'))
        add('CSP', 'HIGH', 'CSP wildcard in: ' + p,
            'Restrict to specific domains');
    });
    add('CSP', 'PASS', 'CSP parsed: ' + parts.length + ' directives');
  }

  // ── RUN ──────────────────────────────────────────────────
  function run() {
    console.log('%c[SmartLog Frontend Security Audit]', 'font-weight:bold;font-size:14px');
    console.log('');

    // Fetch headers via /api/health
    fetch('/api/health', { method: 'HEAD' }).then(function(r) {
      checkHeaders(r.headers);
      checkCSP(r.headers.get('Content-Security-Policy'));
      checkCookies();
      checkCSRF();
      checkDangerousJS();
      checkExternalResources();
      checkStorage();

      // Render results
      console.log('');
      console.log('%cRESULTS', 'font-weight:bold;font-size:16px');
      console.table(results);

      // HTML report
      var html = '<style>td{padding:8px 12px;border-bottom:1px solid #eee;font-size:13px}</style>';
      html += '<h2>SmartLog V2 — Frontend Security Audit</h2>';
      html += '<table><tr><th>#</th><th>Category</th><th>Severity</th><th>Title</th><th>Detail</th></tr>';
      results.forEach(function(r) {
        html += '<tr><td>' + r.id + '</td><td>' + r.category + '</td>' +
                '<td style="color:' + color(r.severity) + ';font-weight:700">' + r.severity + '</td>' +
                '<td>' + esc(r.title) + '</td><td style="font-size:12px;color:#666">' +
                esc(r.detail) + '</td></tr>';
      });
      html += '</table>';

      var sevCounts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0, PASS: 0 };
      results.forEach(function(r) { sevCounts[r.severity]++; });

      console.log('%cSUMMARY', 'font-weight:bold;font-size:14px');
      for (var s in sevCounts) {
        if (sevCounts[s]) console.log('  ' + s + ': ' + sevCounts[s]);
      }
      console.log('');

      console.log('%cCopy the HTML below or view report:', 'font-weight:bold');
      console.log(html);

      // Also try to open in new window
      var w = window.open('', '_blank');
      if (w) {
        w.document.write('<html><head><meta charset="utf-8"><title>Frontend Security Audit</title></head><body>' +
                         html + '</body></html>');
        w.document.close();
      }
    }).catch(function(err) {
      console.error('Failed to fetch /api/health:', err);
      add('NETWORK', 'ERROR', 'Could not fetch headers', err.message);
      console.table(results);
    });
  }

  if (document.readyState === 'complete') {
    run();
  } else {
    window.addEventListener('load', run);
  }
})();
