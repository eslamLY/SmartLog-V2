var IndexedDBManager = (function () {
  var DB_NAME = 'attendance_app';
  var DB_VERSION = 2;
  var _db = null;

  function openDB() {
    return new Promise(function (resolve, reject) {
      if (_db) {
        resolve(_db);
        return;
      }
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        var oldVersion = e.oldVersion;

        if (oldVersion < 1) {
          var store = db.createObjectStore('attendance_records', {
            keyPath: 'id',
            autoIncrement: true,
          });
          store.createIndex('employee_id', 'employee_id', { unique: false });
          store.createIndex('sync_status', 'sync_status', { unique: false });
          store.createIndex('created_at', 'created_at', { unique: false });
          store.createIndex('offline_recorded', 'offline_recorded', { unique: false });
          store.createIndex('record_type', 'record_type', { unique: false });
          store.createIndex('client_timestamp', 'client_timestamp', { unique: false });
        }

        if (oldVersion < 2) {
          if (!db.objectStoreNames.contains('sync_metadata')) {
            var metaStore = db.createObjectStore('sync_metadata', {
              keyPath: 'key',
            });
            metaStore.put({ key: 'last_sync_time', value: 0 });
            metaStore.put({ key: 'total_synced', value: 0 });
            metaStore.put({ key: 'total_failed', value: 0 });
          }
          if (!db.objectStoreNames.contains('cached_employee_data')) {
            var empStore = db.createObjectStore('cached_employee_data', {
              keyPath: 'employee_id',
            });
            empStore.createIndex('department', 'department', { unique: false });
            empStore.createIndex('full_name', 'full_name', { unique: false });
          }
          if (!db.objectStoreNames.contains('offline_log')) {
            var logStore = db.createObjectStore('offline_log', {
              keyPath: 'id',
              autoIncrement: true,
            });
            logStore.createIndex('created_at', 'created_at', { unique: false });
            logStore.createIndex('level', 'level', { unique: false });
          }
        }
      };
      req.onsuccess = function (e) {
        _db = e.target.result;
        _db.onversionchange = function () {
          _db.close();
          _db = null;
        };
        resolve(_db);
      };
      req.onerror = function (e) {
        reject(e.target.error);
      };
      req.onblocked = function () {
        reject(new Error('IndexedDB blocked - close other tabs'));
      };
    });
  }

  function closeDB() {
    if (_db) {
      _db.close();
      _db = null;
    }
  }

  function addAttendanceRecord(record) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('attendance_records', 'readwrite');
        var store = tx.objectStore('attendance_records');
        var req = store.add(record);
        req.onsuccess = function (e) {
          resolve(e.target.result);
        };
        req.onerror = function (e) {
          reject(e.target.error);
        };
        tx.oncomplete = function () {
          db.close();
        };
      }).catch(reject);
    });
  }

  function updateAttendanceRecord(id, updates) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('attendance_records', 'readwrite');
        var store = tx.objectStore('attendance_records');
        var getReq = store.get(id);
        getReq.onsuccess = function (e) {
          var record = e.target.result;
          if (!record) {
            reject(new Error('Record not found: ' + id));
            return;
          }
          Object.assign(record, updates);
          var putReq = store.put(record);
          putReq.onsuccess = function () { resolve(record); };
          putReq.onerror = function (e2) { reject(e2.target.error); };
        };
        getReq.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function getRecordById(id) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('attendance_records', 'readonly');
        var store = tx.objectStore('attendance_records');
        var req = store.get(id);
        req.onsuccess = function (e) { resolve(e.target.result || null); };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function getRecordsByStatus(status) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('attendance_records', 'readonly');
        var store = tx.objectStore('attendance_records');
        var index = store.index('sync_status');
        var range = IDBKeyRange.only(status);
        var results = [];
        var req = index.openCursor(range);
        req.onsuccess = function (e) {
          var cursor = e.target.result;
          if (cursor) {
            results.push(cursor.value);
            cursor.continue();
          } else {
            resolve(results.sort(function (a, b) { return b.created_at - a.created_at; }));
          }
        };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function getRecordsByEmployee(employeeId) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('attendance_records', 'readonly');
        var store = tx.objectStore('attendance_records');
        var index = store.index('employee_id');
        var range = IDBKeyRange.only(employeeId);
        var results = [];
        var req = index.openCursor(range);
        req.onsuccess = function (e) {
          var cursor = e.target.result;
          if (cursor) {
            results.push(cursor.value);
            cursor.continue();
          } else {
            resolve(results.sort(function (a, b) { return b.created_at - a.created_at; }));
          }
        };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function getAllRecords() {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('attendance_records', 'readonly');
        var store = tx.objectStore('attendance_records');
        var results = [];
        var req = store.openCursor();
        req.onsuccess = function (e) {
          var cursor = e.target.result;
          if (cursor) {
            results.push(cursor.value);
            cursor.continue();
          } else {
            resolve(results.sort(function (a, b) { return b.created_at - a.created_at; }));
          }
        };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function deleteRecord(id) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('attendance_records', 'readwrite');
        var store = tx.objectStore('attendance_records');
        var req = store.delete(id);
        req.onsuccess = function () { resolve(true); };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function clearRecords() {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('attendance_records', 'readwrite');
        var store = tx.objectStore('attendance_records');
        var req = store.clear();
        req.onsuccess = function () { resolve(true); };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function countRecordsByStatus(status) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('attendance_records', 'readonly');
        var store = tx.objectStore('attendance_records');
        var index = store.index('sync_status');
        var range = IDBKeyRange.only(status);
        var count = 0;
        var req = index.openCursor(range);
        req.onsuccess = function (e) {
          var cursor = e.target.result;
          if (cursor) {
            count++;
            cursor.continue();
          } else {
            resolve(count);
          }
        };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function setSyncMetadata(key, value) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('sync_metadata', 'readwrite');
        var store = tx.objectStore('sync_metadata');
        var req = store.put({ key: key, value: value });
        req.onsuccess = function () { resolve(value); };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function getSyncMetadata(key) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('sync_metadata', 'readonly');
        var store = tx.objectStore('sync_metadata');
        var req = store.get(key);
        req.onsuccess = function (e) {
          var result = e.target.result;
          resolve(result ? result.value : null);
        };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function cacheEmployeeData(employee) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('cached_employee_data', 'readwrite');
        var store = tx.objectStore('cached_employee_data');
        var req = store.put(employee);
        req.onsuccess = function () { resolve(employee); };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function getCachedEmployee(employeeId) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('cached_employee_data', 'readonly');
        var store = tx.objectStore('cached_employee_data');
        var req = store.get(employeeId);
        req.onsuccess = function (e) { resolve(e.target.result || null); };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function getAllCachedEmployees() {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('cached_employee_data', 'readonly');
        var store = tx.objectStore('cached_employee_data');
        var results = [];
        var req = store.openCursor();
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
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function addLogEntry(level, message, data) {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('offline_log', 'readwrite');
        var store = tx.objectStore('offline_log');
        var entry = {
          level: level,
          message: message,
          data: data || null,
          created_at: Date.now(),
        };
        var req = store.add(entry);
        req.onsuccess = function () { resolve(true); };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function getLogs(limit) {
    limit = limit || 50;
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('offline_log', 'readonly');
        var store = tx.objectStore('offline_log');
        var index = store.index('created_at');
        var results = [];
        var req = index.openCursor(null, 'prev');
        req.onsuccess = function (e) {
          var cursor = e.target.result;
          if (cursor && results.length < limit) {
            results.push(cursor.value);
            cursor.continue();
          } else {
            resolve(results);
          }
        };
        req.onerror = function (e) { reject(e.target.error); };
        tx.oncomplete = function () { db.close(); };
      }).catch(reject);
    });
  }

  function getDatabaseInfo() {
    return new Promise(function (resolve, reject) {
      openDB().then(function (db) {
        var tx = db.transaction('attendance_records', 'readonly');
        var store = tx.objectStore('attendance_records');
        var totalReq = store.count();
        totalReq.onsuccess = function () {
          var total = totalReq.result;
          var statusIndex = store.index('sync_status');
          var pendingReq = statusIndex.count(IDBKeyRange.only('pending'));
          pendingReq.onsuccess = function () {
            var pending = pendingReq.result;
            var syncedReq = statusIndex.count(IDBKeyRange.only('synced'));
            syncedReq.onsuccess = function () {
              var synced = syncedReq.result;
              var failedReq = statusIndex.count(IDBKeyRange.only('failed'));
              failedReq.onsuccess = function () {
                resolve({
                  total_records: total,
                  pending_sync: pending,
                  synced: synced,
                  failed: failedReq.result,
                  db_name: DB_NAME,
                  db_version: DB_VERSION,
                });
                db.close();
              };
            };
          };
        };
      }).catch(reject);
    });
  }

  function exportDatabase() {
    return new Promise(function (resolve, reject) {
      getAllRecords().then(function (records) {
        var exportData = {
          version: DB_VERSION,
          exported_at: Date.now(),
          records: records.map(function (r) {
            return {
              employee_id: r.employee_id,
              record_type: r.record_type,
              client_timestamp: r.client_timestamp,
              gps_location: r.gps_location,
              biometric_type: r.biometric_type,
              offline_recorded: r.offline_recorded,
              sync_status: r.sync_status,
              created_at: r.created_at,
            };
          }),
        };
        var blob = new Blob([JSON.stringify(exportData, null, 2)], {
          type: 'application/json',
        });
        resolve(blob);
      }).catch(reject);
    });
  }

  function importDatabase(jsonData) {
    return new Promise(function (resolve, reject) {
      try {
        var data = typeof jsonData === 'string' ? JSON.parse(jsonData) : jsonData;
        if (!data.records || !Array.isArray(data.records)) {
          reject(new Error('Invalid import format'));
          return;
        }
        openDB().then(function (db) {
          var tx = db.transaction('attendance_records', 'readwrite');
          var store = tx.objectStore('attendance_records');
          var count = 0;
          data.records.forEach(function (rec) {
            var record = {
              employee_id: rec.employee_id,
              record_type: rec.record_type,
              client_timestamp: rec.client_timestamp,
              gps_location: rec.gps_location || null,
              device_id: rec.device_id || null,
              biometric_type: rec.biometric_type || 'gps',
              offline_recorded: true,
              sync_status: 'pending',
              server_response: null,
              retry_count: 0,
              created_at: rec.created_at || Date.now(),
              synced_at: null,
            };
            var req = store.add(record);
            req.onsuccess = function () { count++; };
          });
          tx.oncomplete = function () {
            resolve({ imported: count });
            db.close();
          };
          tx.onerror = function (e) { reject(e.target.error); };
        }).catch(reject);
      } catch (e) {
        reject(e);
      }
    });
  }

  return {
    openDB: openDB,
    closeDB: closeDB,
    addAttendanceRecord: addAttendanceRecord,
    updateAttendanceRecord: updateAttendanceRecord,
    getRecordById: getRecordById,
    getRecordsByStatus: getRecordsByStatus,
    getRecordsByEmployee: getRecordsByEmployee,
    getAllRecords: getAllRecords,
    deleteRecord: deleteRecord,
    clearRecords: clearRecords,
    countRecordsByStatus: countRecordsByStatus,
    setSyncMetadata: setSyncMetadata,
    getSyncMetadata: getSyncMetadata,
    cacheEmployeeData: cacheEmployeeData,
    getCachedEmployee: getCachedEmployee,
    getAllCachedEmployees: getAllCachedEmployees,
    addLogEntry: addLogEntry,
    getLogs: getLogs,
    getDatabaseInfo: getDatabaseInfo,
    exportDatabase: exportDatabase,
    importDatabase: importDatabase,
  };
})();
