var EncryptionUtils = (function () {
  var ALGORITHM = 'AES-GCM';
  var KEY_LENGTH = 256;
  var SALT_LENGTH = 16;
  var IV_LENGTH = 12;
  var ITERATIONS = 100000;

  function getDeviceKey() {
    return new Promise(function (resolve, reject) {
      var deviceId = localStorage.getItem('device_id') || 'unknown-device';
      var storedKey = localStorage.getItem('_ek');
      if (storedKey) {
        try {
          var parsed = JSON.parse(storedKey);
          resolve(base64ToArrayBuffer(parsed.k));
          return;
        } catch (e) {}
      }
      var salt = new Uint8Array(SALT_LENGTH);
      crypto.getRandomValues(salt);
      var enc = new TextEncoder();
      var password = 'bb-attendance-' + deviceId + '-' + navigator.userAgent.substring(0, 32);
      crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']).then(function (key) {
        return crypto.subtle.deriveKey(
          { name: 'PBKDF2', salt: salt, iterations: ITERATIONS, hash: 'SHA-256' },
          key,
          { name: ALGORITHM, length: KEY_LENGTH },
          true,
          ['encrypt', 'decrypt']
        );
      }).then(function (aesKey) {
        return crypto.subtle.exportKey('raw', aesKey);
      }).then(function (rawKey) {
        var keyObj = { k: arrayBufferToBase64(rawKey), s: arrayBufferToBase64(salt) };
        localStorage.setItem('_ek', JSON.stringify(keyObj));
        resolve(rawKey);
      }).catch(reject);
    });
  }

  function getCryptoKey() {
    return getDeviceKey().then(function (rawKey) {
      return crypto.subtle.importKey('raw', rawKey, { name: ALGORITHM, length: KEY_LENGTH }, false, ['encrypt', 'decrypt']);
    });
  }

  function encrypt(plaintext) {
    return new Promise(function (resolve, reject) {
      getCryptoKey().then(function (key) {
        var iv = crypto.getRandomValues(new Uint8Array(IV_LENGTH));
        var enc = new TextEncoder();
        return crypto.subtle.encrypt({ name: ALGORITHM, iv: iv }, key, enc.encode(plaintext)).then(function (ciphertext) {
          var combined = new Uint8Array(iv.length + ciphertext.byteLength);
          combined.set(iv, 0);
          combined.set(new Uint8Array(ciphertext), iv.length);
          resolve(arrayBufferToBase64(combined.buffer));
        });
      }).catch(reject);
    });
  }

  function decrypt(ciphertextB64) {
    return new Promise(function (resolve, reject) {
      getCryptoKey().then(function (key) {
        try {
          var combined = base64ToArrayBuffer(ciphertextB64);
          var iv = new Uint8Array(combined, 0, IV_LENGTH);
          var ciphertext = new Uint8Array(combined, IV_LENGTH);
          return crypto.subtle.decrypt({ name: ALGORITHM, iv: iv }, key, ciphertext).then(function (plaintext) {
            var dec = new TextDecoder();
            resolve(dec.decode(plaintext));
          });
        } catch (e) {
          reject(e);
        }
      }).catch(reject);
    });
  }

  function encryptSessionData(data) {
    var json = JSON.stringify(data);
    return encrypt(json);
  }

  function decryptSessionData(encrypted) {
    return decrypt(encrypted).then(function (json) {
      return JSON.parse(json);
    });
  }

  function encryptString(plaintext) {
    try {
      var key = getDeviceKeySync();
      if (!key) return null;
      var iv = crypto.getRandomValues(new Uint8Array(IV_LENGTH));
      var enc = new TextEncoder();
      return crypto.subtle.encrypt(
        { name: ALGORITHM, iv: iv },
        key,
        enc.encode(plaintext)
      ).then(function (ciphertext) {
        var combined = new Uint8Array(iv.length + ciphertext.byteLength);
        combined.set(iv, 0);
        combined.set(new Uint8Array(ciphertext), iv.length);
        return arrayBufferToBase64(combined.buffer);
      });
    } catch (e) {
      return null;
    }
  }

  function getDeviceKeySync() {
    try {
      var storedKey = localStorage.getItem('_ek');
      if (!storedKey) return null;
      var parsed = JSON.parse(storedKey);
      return base64ToArrayBuffer(parsed.k);
    } catch (e) {
      return null;
    }
  }

  function encryptData(data) {
    if (!data) return null;
    if (typeof data === 'object') {
      data = JSON.stringify(data);
    }
    var result = encrypt(data);
    return result;
  }

  function decryptData(encrypted) {
    if (!encrypted) return null;
    try {
      var parsed = JSON.parse(encrypted);
      if (parsed && parsed.encrypted && typeof parsed.encrypted === 'string') {
        var result = decrypt(parsed.encrypted);
        return result;
      }
      if (typeof encrypted === 'string' && encrypted.length > 50) {
        var result2 = decrypt(encrypted);
        return result2;
      }
    } catch (e) {}
    return null;
  }

  function arrayBufferToBase64(buffer) {
    var bytes = new Uint8Array(buffer);
    var binary = '';
    for (var i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  function base64ToArrayBuffer(base64) {
    var binary = atob(base64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  function generateSessionHash(employeeId, token) {
    var data = employeeId + ':' + token.substring(0, 16);
    var enc = new TextEncoder();
    return crypto.subtle.digest('SHA-256', enc.encode(data)).then(function (hash) {
      var hex = Array.from(new Uint8Array(hash)).map(function (b) {
        return b.toString(16).padStart(2, '0');
      }).join('');
      return hex.substring(0, 32);
    });
  }

  function hashEmployeeId(employeeId) {
    var enc = new TextEncoder();
    return crypto.subtle.digest('SHA-256', enc.encode(employeeId)).then(function (hash) {
      var hex = Array.from(new Uint8Array(hash)).map(function (b) {
        return b.toString(16).padStart(2, '0');
      }).join('');
      return hex;
    });
  }

  function checkIntegrity(data, hash) {
    var enc = new TextEncoder();
    return crypto.subtle.digest('SHA-256', enc.encode(JSON.stringify(data))).then(function (calculated) {
      var calcHex = Array.from(new Uint8Array(calculated)).map(function (b) {
        return b.toString(16).padStart(2, '0');
      }).join('');
      return calcHex === hash;
    });
  }

  return {
    encrypt: encrypt,
    decrypt: decrypt,
    encryptSessionData: encryptSessionData,
    decryptSessionData: decryptSessionData,
    encryptString: encryptString,
    encryptData: encryptData,
    decryptData: decryptData,
    generateSessionHash: generateSessionHash,
    hashEmployeeId: hashEmployeeId,
    checkIntegrity: checkIntegrity,
    getDeviceKey: getDeviceKey,
    arrayBufferToBase64: arrayBufferToBase64,
    base64ToArrayBuffer: base64ToArrayBuffer,
  };
})();
