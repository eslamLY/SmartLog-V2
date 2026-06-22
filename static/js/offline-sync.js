var OfflineSync = (function () {
  var syncing = {
    in_progress: false,
    total_pending: 0,
    successfully_synced: 0,
    failed_records: [],
    heartbeatId: null,
  };

  var listeners = {
    onSyncStart: [],
    onSyncProgress: [],
    onSyncComplete: [],
    onSyncError: [],
  };

  function init() {
    listenForServiceWorkerMessages();
    startHeartbeat();
    window.addEventListener('online', function () {
      showToast('📶 تم استعادة الاتصال بالإنترنت', 'info');
      if (hasPendingRecords()) {
        syncOfflineRecords();
      }
    });
    window.addEventListener('offline', function () {
      showToast('🌐 أنت في وضع بدون إنترنت', 'info');
    });
  }

  function listenForServiceWorkerMessages() {
    navigator.serviceWorker.addEventListener('message', function (event) {
      var data = event.data;
      if (!data) return;
      switch (data.type) {
        case 'SYNC_STARTED':
          fireEvent('onSyncStart', []);
          break;
        case 'SYNC_PROGRESS':
          fireEvent('onSyncProgress', [data]);
          break;
        case 'SYNC_COMPLETE':
          fireEvent('onSyncComplete', [data]);
          syncing.in_progress = false;
          break;
        case 'SYNC_ERROR':
          fireEvent('onSyncError', [data]);
          syncing.in_progress = false;
          break;
      }
    });
  }

  function checkServerConnectivity() {
    return new Promise(function (resolve) {
      var controller = new AbortController();
      var timeout = setTimeout(function () { controller.abort(); }, 5000);
      fetch('/api/health', {
        method: 'GET',
        signal: controller.signal,
        cache: 'no-store',
      }).then(function (r) {
        clearTimeout(timeout);
        resolve(r.ok);
      }).catch(function () {
        clearTimeout(timeout);
        resolve(false);
      });
    });
  }

  function isOnline() {
    return navigator.onLine;
  }

  async function hasPendingRecords() {
    try {
      var db = await openAttendanceDB();
      var tx = db.transaction('attendance_records', 'readonly');
      var store = tx.objectStore('attendance_records');
      var index = store.index('sync_status');
      var range = IDBKeyRange.only('pending');
      var count = await countIndex(index, range);
      db.close();
      return count > 0;
    } catch (e) {
      return false;
    }
  }

  async function getPendingRecords() {
    try {
      var db = await openAttendanceDB();
      var tx = db.transaction('attendance_records', 'readonly');
      var store = tx.objectStore('attendance_records');
      var index = store.index('sync_status');
      var range = IDBKeyRange.only('pending');
      var records = await getAllFromIndex(index, range);
      db.close();
      return records.sort(function (a, b) { return a.created_at - b.created_at; });
    } catch (e) {
      return [];
    }
  }

  async function getAllRecords() {
    try {
      var db = await openAttendanceDB();
      var tx = db.transaction('attendance_records', 'readonly');
      var store = tx.objectStore('attendance_records');
      var records = await getAllFromStore(store);
      db.close();
      return records.sort(function (a, b) { return b.created_at - a.created_at; });
    } catch (e) {
      return [];
    }
  }

  async function syncOfflineRecords() {
    if (syncing.in_progress) return;
    var online = await checkServerConnectivity();
    if (!online) return;
    var pending = await getPendingRecords();
    if (pending.length === 0) return;

    syncing.in_progress = true;
    syncing.total_pending = pending.length;
    syncing.successfully_synced = 0;
    syncing.failed_records = [];
    fireEvent('onSyncStart', [pending.length]);

    var sessionData = getSession();
    if (!sessionData || !sessionData.token) {
      syncing.in_progress = false;
      fireEvent('onSyncError', [{ error: 'no_session', message: 'يرجى تسجيل الدخول أولاً' }]);
      return;
    }

    var batches = [];
    for (var i = 0; i < pending.length; i += 10) {
      batches.push(pending.slice(i, i + 10));
    }

    for (var b = 0; b < batches.length; b++) {
      var batch = batches[b];
      var payload = {
        records: batch.map(function (rec) {
          var encrypted = encryptRecordForTransfer(rec);
          return {
            id: rec.id,
            employee_id: rec.employee_id,
            record_type: rec.record_type,
            client_timestamp: rec.client_timestamp,
            gps_location: rec.gps_location || null,
            device_id: rec.device_id || null,
            biometric_type: rec.biometric_type || 'gps',
            retry_count: rec.retry_count || 0,
            encrypted_data: encrypted,
          };
        }),
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
        var db = await openAttendanceDB();
        var tx = db.transaction('attendance_records', 'readwrite');
        var store = tx.objectStore('attendance_records');

        if (result.synced_records) {
          for (var s = 0; s < result.synced_records.length; s++) {
            var sr = result.synced_records[s];
            var localRec = batch.find(function (r) { return r.id === sr.local_id; });
            if (localRec) {
              store.put(Object.assign({}, localRec, {
                sync_status: 'synced',
                server_response: sr,
                synced_at: Date.now(),
              }));
              syncing.successfully_synced++;
            }
          }
        }

        if (result.failed_records) {
          for (var f = 0; f < result.failed_records.length; f++) {
            var fr = result.failed_records[f];
            var localRecF = batch.find(function (r) { return r.id === fr.local_id; });
            if (localRecF) {
              store.put(Object.assign({}, localRecF, {
                sync_status: 'failed',
                server_response: fr,
                retry_count: (localRecF.retry_count || 0) + 1,
              }));
              syncing.failed_records.push(fr);
            }
          }
        }

        await new Promise(function (resolve, reject) {
          tx.oncomplete = resolve;
          tx.onerror = reject;
        });

        db.close();

        fireEvent('onSyncProgress', [{
          synced: syncing.successfully_synced,
          failed: syncing.failed_records.length,
          total: pending.length,
          current: Math.min(
            syncing.successfully_synced + syncing.failed_records.length + (b * 10),
            pending.length
          ),
        }]);

      } catch (err) {
        var db2 = await openAttendanceDB();
        var tx2 = db2.transaction('attendance_records', 'readwrite');
        var store2 = tx2.objectStore('attendance_records');
        for (var r = 0; r < batch.length; r++) {
          var recRetry = batch[r];
          var newRetry = (recRetry.retry_count || 0) + 1;
          if (newRetry >= 5) {
            store2.put(Object.assign({}, recRetry, {
              sync_status: 'failed',
              server_response: { reason: 'max_retries_exceeded', message: 'تجاوز عدد المحاولات المسموح به' },
              retry_count: newRetry,
            }));
            syncing.failed_records.push({ local_id: recRetry.id, reason: 'max_retries_exceeded' });
          } else {
            store2.put(Object.assign({}, recRetry, { retry_count: newRetry }));
          }
        }
        await new Promise(function (resolve, reject) {
          tx2.oncomplete = resolve;
          tx2.onerror = reject;
        });
        db2.close();

        fireEvent('onSyncProgress', [{
          synced: syncing.successfully_synced,
          failed: syncing.failed_records.length,
          total: pending.length,
          current: Math.min(
            syncing.successfully_synced + syncing.failed_records.length + (b * 10),
            pending.length
          ),
        }]);
      }
    }

    syncing.in_progress = false;
    fireEvent('onSyncComplete', [{
      count: syncing.successfully_synced,
      failed: syncing.failed_records.length,
      failedDetails: syncing.failed_records,
    }]);
  }

  function encryptRecordForTransfer(record) {
    try {
      if (typeof encryptData === 'function') {
        var sensitive = JSON.stringify({
          employee_id: record.employee_id,
          client_timestamp: record.client_timestamp,
          gps_location: record.gps_location,
        });
        return encryptData(sensitive);
      }
    } catch (e) {}
    return null;
  }

  function startHeartbeat() {
    if (syncing.heartbeatId) {
      clearInterval(syncing.heartbeatId);
    }
    syncing.heartbeatId = setInterval(async function () {
      if (!syncing.in_progress) {
        var online = await checkServerConnectivity();
        if (online) {
          var pending = await getPendingRecords();
          if (pending.length > 0) {
            syncOfflineRecords();
          }
        }
      }
    }, 30000);
  }

  function stopHeartbeat() {
    if (syncing.heartbeatId) {
      clearInterval(syncing.heartbeatId);
      syncing.heartbeatId = null;
    }
  }

  function getSession() {
    try {
      var raw = localStorage.getItem('attendance_session');
      if (!raw) return null;
      if (typeof decryptData === 'function') {
        var decrypted = decryptData(raw);
        if (decrypted) return JSON.parse(decrypted);
      }
      var parsed = JSON.parse(raw);
      if (parsed.iv || parsed.ciphertext) return null;
      return parsed;
    } catch (e) {
      return null;
    }
  }

  function on(event, callback) {
    if (listeners[event]) {
      listeners[event].push(callback);
    }
    return {
      remove: function () {
        var idx = listeners[event].indexOf(callback);
        if (idx !== -1) listeners[event].splice(idx, 1);
      },
    };
  }

  function fireEvent(event, args) {
    if (listeners[event]) {
      listeners[event].forEach(function (cb) {
        try { cb.apply(null, args); } catch (e) {}
      });
    }
  }

  function getSyncStatus() {
    return {
      in_progress: syncing.in_progress,
      total_pending: syncing.total_pending,
      synced: syncing.successfully_synced,
      failed: syncing.failed_records.length,
    };
  }

  return {
    init: init,
    syncOfflineRecords: syncOfflineRecords,
    hasPendingRecords: hasPendingRecords,
    getPendingRecords: getPendingRecords,
    getAllRecords: getAllRecords,
    isOnline: isOnline,
    checkServerConnectivity: checkServerConnectivity,
    getSession: getSession,
    getSyncStatus: getSyncStatus,
    on: on,
    startHeartbeat: startHeartbeat,
    stopHeartbeat: stopHeartbeat,
  };
})();
