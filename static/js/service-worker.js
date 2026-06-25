const CACHE_NAME = 'smartlog-v1';
const STATIC_CACHES = [CACHE_NAME + '-assets', CACHE_NAME + '-pages'];

const STATIC_ASSETS = [
  '/',
  '/login',
  '/manifest.json',
  '/static/manifest.json',
  '/static/css/pwa.css',
  '/static/js/app.js',
  '/static/js/offline-sync.js',
  '/static/js/indexeddb-manager.js',
  '/static/js/encryption-utils.js',
  '/static/icons/icon-72.png',
  '/static/icons/icon-96.png',
  '/static/icons/icon-128.png',
  '/static/icons/icon-144.png',
  '/static/icons/icon-152.png',
  '/static/icons/icon-192.png',
  '/static/icons/icon-384.png',
  '/static/icons/icon-512.png',
];

const API_PATHS = [
  '/api/',
  '/auth/api/',
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME + '-assets').then(function (cache) {
      return cache.addAll(STATIC_ASSETS).catch(function (err) {
        console.warn('SW: some assets failed to cache', err);
      });
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(
        names.filter(function (name) {
          return name.indexOf(CACHE_NAME) !== 0;
        }).map(function (name) {
          return caches.delete(name);
        })
      );
    }).then(function () {
      return self.clients.claim();
    })
  );
});

function isApiRequest(url) {
  return API_PATHS.some(function (path) {
    return url.indexOf(path) !== -1;
  });
}

function isStaticAsset(url) {
  var exts = ['.js', '.css', '.png', '.svg', '.jpg', '.jpeg', '.webp', '.ico', '.woff', '.woff2', '.ttf'];
  return exts.some(function (ext) {
    return url.indexOf(ext) !== -1;
  }) || url.indexOf('/static/') !== -1;
}

function isHtmlRequest(request) {
  return request.method === 'GET' && request.headers.get('Accept') &&
    request.headers.get('Accept').indexOf('text/html') !== -1;
}

self.addEventListener('fetch', function (event) {
  var url = event.request.url;
  var request = event.request;

  if (request.method !== 'GET') {
    return;
  }

  if (isApiRequest(url)) {
    event.respondWith(networkFirstThenCache(request));
    return;
  }

  if (isStaticAsset(url)) {
    event.respondWith(cacheFirstThenNetwork(request));
    return;
  }

  if (isHtmlRequest(request)) {
    event.respondWith(networkFirstWithFallback(request));
    return;
  }

  event.respondWith(networkFirstThenCache(request));
});

function cacheFirstThenNetwork(request) {
  return caches.match(request).then(function (cached) {
    if (cached) {
      return cached;
    }
    return fetchAndCache(request, CACHE_NAME + '-assets');
  }).catch(function () {
    return caches.match(request).then(function (r) { return r || offlineResponse(); });
  });
}

function networkFirstThenCache(request) {
  return fetchAndCache(request, CACHE_NAME + '-pages').catch(function () {
    return caches.match(request).then(function (r) { return r || offlineResponse(); });
  });
}

function networkFirstWithFallback(request) {
  return fetchAndCache(request, CACHE_NAME + '-pages').catch(function () {
    return caches.match(request).then(function (cached) {
      if (cached) {
        return cached;
      }
      return caches.match('/login').then(function (r) { return r || offlineResponse(); });
    });
  });
}

function offlineResponse() {
  return new Response(JSON.stringify({ ok: false, msg: 'غير متصل بالإنترنت' }), {
    status: 503,
    headers: { 'Content-Type': 'application/json' },
  });
}

function fetchAndCache(request, cacheName) {
  return fetch(request).then(function (response) {
    if (!response || response.status !== 200) {
      return response;
    }
    var clone = response.clone();
    caches.open(cacheName).then(function (cache) {
      cache.put(request, clone);
    });
    return response;
  });
}

self.addEventListener('message', function (event) {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (event.data && event.data.type === 'CACHE_CLEAR') {
    caches.keys().then(function (names) {
      return Promise.all(
        names.filter(function (n) { return n.indexOf(CACHE_NAME) === 0; })
          .map(function (n) { return caches.delete(n); })
      );
    });
  }
});

self.addEventListener('sync', function (event) {
  if (event.tag === 'sync-attendance') {
    event.waitUntil(syncAttendanceRecords());
  }
});

async function syncAttendanceRecords() {
  try {
    var clients = await self.clients.matchAll({ type: 'window' });
    clients.forEach(function (client) {
      client.postMessage({ type: 'SYNC_STARTED' });
    });

    var db = await openIndexedDB();
    var tx = db.transaction('attendance_records', 'readonly');
    var store = tx.objectStore('attendance_records');
    var index = store.index('sync_status');
    var range = IDBKeyRange.only('pending');
    var records = await getAllFromIndex(index, range);

    if (!records || records.length === 0) {
      clients.forEach(function (c) { c.postMessage({ type: 'SYNC_COMPLETE', count: 0 }); });
      return;
    }

    var sessionData = await getSessionFromClients(clients);
    if (!sessionData) {
      clients.forEach(function (c) { c.postMessage({ type: 'SYNC_ERROR', error: 'no_session' }); });
      return;
    }

    var batches = [];
    for (var i = 0; i < records.length; i += 10) {
      batches.push(records.slice(i, i + 10));
    }

    var totalSynced = 0;
    var totalFailed = 0;
    var failedDetails = [];

    for (var b = 0; b < batches.length; b++) {
      var batch = batches[b];
      var payload = {
        records: batch.map(function (rec) {
          return {
            id: rec.id,
            employee_id: rec.employee_id,
            record_type: rec.record_type,
            client_timestamp: rec.client_timestamp,
            gps_location: rec.gps_location || null,
            device_id: rec.device_id || null,
            biometric_type: rec.biometric_type || 'gps',
            retry_count: rec.retry_count || 0,
          };
        })
      };

      try {
        var response = await fetch('/api/attendance/offline-sync', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + sessionData.token,
          },
          body: JSON.stringify(payload),
        });

        var result = await response.json();

        var tx2 = db.transaction('attendance_records', 'readwrite');
        var store2 = tx2.objectStore('attendance_records');

        if (result.synced_records) {
          for (var s = 0; s < result.synced_records.length; s++) {
            var sr = result.synced_records[s];
            var localRec = batch.find(function (r) { return r.id === sr.local_id; });
            if (localRec) {
              var updateData = {
                sync_status: 'synced',
                server_response: sr,
                synced_at: Date.now(),
                retry_count: localRec.retry_count,
              };
              store2.put(Object.assign({}, localRec, updateData));
              totalSynced++;
            }
          }
        }

        if (result.failed_records) {
          for (var f = 0; f < result.failed_records.length; f++) {
            var fr = result.failed_records[f];
            var localRecF = batch.find(function (r) { return r.id === fr.local_id; });
            if (localRecF) {
              var updateFail = {
                sync_status: 'failed',
                server_response: fr,
                retry_count: (localRecF.retry_count || 0) + 1,
              };
              store2.put(Object.assign({}, localRecF, updateFail));
              totalFailed++;
              failedDetails.push(fr);
            }
          }
        }
      } catch (err) {
        var tx3 = db.transaction('attendance_records', 'readwrite');
        var store3 = tx3.objectStore('attendance_records');
        for (var r = 0; r < batch.length; r++) {
          var recRetry = batch[r];
          var newRetry = (recRetry.retry_count || 0) + 1;
          if (newRetry >= 5) {
            store3.put(Object.assign({}, recRetry, {
              sync_status: 'failed',
              server_response: { reason: 'max_retries_exceeded', message: 'تجاوز عدد المحاولات المسموح به' },
              retry_count: newRetry,
            }));
            totalFailed++;
          } else {
            store3.put(Object.assign({}, recRetry, {
              retry_count: newRetry,
            }));
          }
        }
      }

      clients.forEach(function (client) {
        client.postMessage({
          type: 'SYNC_PROGRESS',
          synced: totalSynced,
          failed: totalFailed,
          total: records.length,
          current: Math.min(totalSynced + totalFailed + (b * 10), records.length),
        });
      });
    }

    clients.forEach(function (client) {
      client.postMessage({
        type: 'SYNC_COMPLETE',
        count: totalSynced,
        failed: totalFailed,
        failedDetails: failedDetails,
      });
    });

  } catch (err) {
    var c2 = await self.clients.matchAll({ type: 'window' });
    c2.forEach(function (client) {
      client.postMessage({ type: 'SYNC_ERROR', error: err.message });
    });
  }
}

function openIndexedDB() {
  return new Promise(function (resolve, reject) {
    var req = indexedDB.open('attendance_app', 1);
    req.onupgradeneeded = function (e) {
      var db = e.target.result;
      if (!db.objectStoreNames.contains('attendance_records')) {
        var store = db.createObjectStore('attendance_records', { keyPath: 'id', autoIncrement: true });
        store.createIndex('employee_id', 'employee_id', { unique: false });
        store.createIndex('sync_status', 'sync_status', { unique: false });
        store.createIndex('created_at', 'created_at', { unique: false });
        store.createIndex('offline_recorded', 'offline_recorded', { unique: false });
      }
    };
    req.onsuccess = function (e) { resolve(e.target.result); };
    req.onerror = function (e) { reject(e.target.error); };
  });
}

function getAllFromIndex(index, range) {
  return new Promise(function (resolve, reject) {
    var results = [];
    var req = index.openCursor(range);
    req.onsuccess = function (e) {
      var cursor = e.target.result;
      if (cursor) {
        results.push(cursor.value);
        cursor.continue();
      } else {
        resolve(results);
      }
    };
    req.onerror = function (e) { reject(e.target.error); };
  });
}

function getSessionFromClients(clients) {
  return new Promise(function (resolve) {
    if (!clients || clients.length === 0) {
      resolve(null);
      return;
    }
    var client = clients[0];
    var channel = new MessageChannel();
    channel.port1.onmessage = function (e) {
      resolve(e.data || null);
    };
    client.postMessage({ type: 'GET_SESSION' }, [channel.port2]);
    setTimeout(function () { resolve(null); }, 1000);
  });
}
