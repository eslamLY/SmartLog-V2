/* =============================================================
 * SMARTLOG — Attendance & HR Management System
 * PWA Initialization & Offline Support  v1.0
 * ============================================================= */

function csrfToken() {
  var m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}

(function() {
  'use strict';

  /* ── Register Service Worker ── */
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
      navigator.serviceWorker.register('/static/sw.js', { scope: '/' }).then(function(reg) {
        console.log('[PWA] SW registered, scope:', reg.scope);

        /* Check for updates */
        reg.addEventListener('updatefound', function() {
          var newSW = reg.installing;
          newSW.addEventListener('statechange', function() {
            if (newSW.state === 'installed' && navigator.serviceWorker.controller) {
              showUpdateBanner();
            }
          });
        });
      }).catch(function(err) {
        console.warn('[PWA] SW registration failed:', err);
      });

      /* Re-register on controller change (update) */
      navigator.serviceWorker.addEventListener('controllerchange', function() {
        console.log('[PWA] New SW activated');
      });
    });
  }

  /* ── Update Banner UI ── */
  function showUpdateBanner() {
    var banner = document.getElementById('swUpdateBanner');
    if (banner) { banner.style.display = 'flex'; return; }
    var div = document.createElement('div');
    div.id = 'swUpdateBanner';
    div.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);z-index:200;background:var(--card);border:1px solid var(--accent);border-radius:14px;padding:12px 20px;display:flex;align-items:center;gap:12px;box-shadow:0 8px 32px rgba(0,0,0,.5);animation:modalIn .3s ease;font-size:13px';
    div.innerHTML = 'تحديث جديد متاح' +
      '<button onclick="location.reload()" style="background:var(--accent);color:#fff;border:none;border-radius:8px;padding:6px 16px;font-family:Cairo,sans-serif;font-weight:600;cursor:pointer;font-size:12px">تحديث الآن</button>';
    document.body.appendChild(div);
  }

  /* ── Online / Offline Detection ── */
  var offlineBar = null;

  function createOfflineBar() {
    offlineBar = document.createElement('div');
    offlineBar.id = 'offlineBar';
    offlineBar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:999;background:#dc2626;color:#fff;text-align:center;padding:6px 10px;font-size:12px;font-weight:600;font-family:Cairo,sans-serif;transform:translateY(-100%);transition:transform .3s ease;display:flex;align-items:center;justify-content:center;gap:6px';
    offlineBar.innerHTML = '<i class="ti ti-wifi-off"></i> لا يوجد اتصال بالإنترنت — بعض البيانات قد لا تكون محدثة';
    document.body.prepend(offlineBar);
  }

  function updateOnlineStatus() {
    if (navigator.onLine) {
      if (offlineBar) offlineBar.style.transform = 'translateY(-100%)';
      document.body.classList.remove('is-offline');
    } else {
      if (!offlineBar) createOfflineBar();
      offlineBar.style.transform = 'translateY(0)';
      document.body.classList.add('is-offline');
    }
  }

  window.addEventListener('online', updateOnlineStatus);
  window.addEventListener('offline', updateOnlineStatus);
  if (document.readyState === 'complete') {
    if (!offlineBar) createOfflineBar();
    updateOnlineStatus();
  } else {
    document.addEventListener('DOMContentLoaded', function() {
      if (!offlineBar) createOfflineBar();
      updateOnlineStatus();
    });
  }

  /* ── PWA Install Prompt ── */
  var pwaDeferredPrompt = null;

  window.addEventListener('beforeinstallprompt', function(e) {
    e.preventDefault();
    pwaDeferredPrompt = e;
  });

  window.installPWA = function() {
    if (!pwaDeferredPrompt) {
      showIOSInstallGuide();
      return;
    }
    pwaDeferredPrompt.prompt();
    pwaDeferredPrompt.userChoice.then(function(result) {
      pwaDeferredPrompt = null;
    });
  };

  function showIOSInstallGuide() {
    var existing = document.getElementById('iosInstallGuide');
    if (existing) { existing.style.display = 'block'; return; }
    var div = document.createElement('div');
    div.id = 'iosInstallGuide';
    div.style.cssText = 'position:fixed;bottom:140px;left:20px;right:20px;z-index:200;background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px;box-shadow:0 8px 32px rgba(0,0,0,.5);animation:modalIn .3s ease;max-width:360px;margin:0 auto';
    div.innerHTML =
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">' +
      '<span style="font-size:14px;font-weight:700"><i class="ti ti-apple" style="color:var(--accent)"></i> تثبيت على iOS</span>' +
      '<button onclick="this.parentElement.parentElement.style.display=\'none\'" style="background:none;border:none;color:var(--muted);font-size:18px;cursor:pointer">&times;</button></div>' +
      '<ol style="margin:0;padding-right:20px;font-size:13px;color:var(--text);line-height:2">' +
      '<li>اضغط على زر المشاركة <span style="font-size:16px">⬆️</span> في شريط سفلي</li>' +
      '<li>مرر لأسفل واختر <strong style="color:var(--accent)">إضافة إلى الشاشة الرئيسية</strong></li>' +
      '<li>اضغط <strong style="color:var(--accent)">إضافة</strong> في الزاوية العلوية</li></ol>' +
      '<div style="margin-top:10px;padding:10px;background:var(--bg);border-radius:10px;font-size:12px;color:var(--muted);text-align:center">' +
      '<i class="ti ti-info-circle" style="color:var(--accent)"></i> سيتم تشغيل التطبيق بشكل مستقل بعد التثبيت</div>';
    document.body.appendChild(div);
  }

  window.addEventListener('appinstalled', function() {
    pwaDeferredPrompt = null;
    console.log('[PWA] App installed successfully');
  });

  /* ── IndexedDB: local data persistence ── */
  var DB_NAME = 'SmartLogDB';
  var DB_VERSION = 1;

  function openDB() {
    return new Promise(function(resolve, reject) {
      if (!window.indexedDB) { resolve(null); return; }
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function(ev) {
        var db = ev.target.result;
        if (!db.objectStoreNames.contains('attendance')) {
          db.createObjectStore('attendance', { keyPath: 'id', autoIncrement: true });
        }
        if (!db.objectStoreNames.contains('sync_queue')) {
          db.createObjectStore('sync_queue', { keyPath: 'id', autoIncrement: true });
        }
      };
      req.onsuccess = function(ev) { resolve(ev.target.result); };
      req.onerror = function(ev) { reject(ev.target.error); };
    });
  }

  window.cacheLocally = function(storeName, data) {
    return openDB().then(function(db) {
      if (!db) return;
      var tx = db.transaction(storeName, 'readwrite');
      var store = tx.objectStore(storeName);
      store.clear();
      if (Array.isArray(data)) {
        data.forEach(function(item) { store.add(item); });
      } else {
        store.add(data);
      }
      return new Promise(function(resolve) { tx.oncomplete = resolve; });
    });
  };

  window.getLocalCache = function(storeName) {
    return openDB().then(function(db) {
      if (!db) return [];
      return new Promise(function(resolve, reject) {
        var tx = db.transaction(storeName, 'readonly');
        var store = tx.objectStore(storeName);
        var req = store.getAll();
        req.onsuccess = function() { resolve(req.result); };
        req.onerror = function() { reject(req.error); };
      });
    });
  };

  window.queueSync = function(action, payload) {
    return openDB().then(function(db) {
      if (!db) return;
      var tx = db.transaction('sync_queue', 'readwrite');
      var store = tx.objectStore('sync_queue');
      return new Promise(function(resolve) {
        store.add({ action: action, payload: payload, created: Date.now() });
        tx.oncomplete = resolve;
      });
    });
  };

  /* Process sync queue when back online */
  window.addEventListener('online', function() {
    openDB().then(function(db) {
      if (!db) return;
      var tx = db.transaction('sync_queue', 'readwrite');
      var store = tx.objectStore('sync_queue');
      var req = store.getAll();
      req.onsuccess = function() {
        var items = req.result;
        if (!items.length) return;
        items.forEach(function(item) {
          fetch('/api/' + item.action, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify(item.payload)
          }).then(function() { store.delete(item.id); });
        });
      };
    });
  });

  /* ── Skeleton Screen Helper ── */
  window.renderSkeleton = function(container, rows, cols) {
    if (!container) return;
    var html = '';
    for (var r = 0; r < rows; r++) {
      html += '<div style="display:flex;gap:12px;padding:12px 0">';
      for (var c = 0; c < cols; c++) {
        var w = 60 + Math.random() * 120;
        html += '<div class="shimmer" style="height:18px;width:' + Math.round(w) + 'px;border-radius:6px"></div>';
      }
      html += '</div>';
    }
    container.innerHTML = html;
  };

  /* ── Lazy load images with IntersectionObserver ── */
  if ('IntersectionObserver' in window) {
    document.addEventListener('DOMContentLoaded', function() {
      var images = document.querySelectorAll('img[data-src]');
      if (images.length) {
        var obs = new IntersectionObserver(function(entries) {
          entries.forEach(function(entry) {
            if (entry.isIntersecting) {
              var img = entry.target;
              img.src = img.getAttribute('data-src');
              img.removeAttribute('data-src');
              obs.unobserve(img);
            }
          });
        });
        images.forEach(function(img) { obs.observe(img); });
      }
    });
  }

  console.log('[PWA] Initialized v1.0');
})();
