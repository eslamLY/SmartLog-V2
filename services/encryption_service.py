import os, base64, hashlib, logging, io
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_MASTER_PASSWORD = None
_SALT = None
_CACHE_KEY = None

PBKDF2_ITERATIONS = 600000
KEY_LENGTH = 32


def _get_or_derive_key(master_password: str = None) -> bytes:
    global _MASTER_PASSWORD, _SALT, _CACHE_KEY
    password = master_password or _MASTER_PASSWORD or os.environ.get('BACKUP_ENCRYPTION_KEY')
    if not password:
        raise RuntimeError('BACKUP_ENCRYPTION_KEY environment variable is required for backup encryption. '
                           'Generate one via: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
    if password == _MASTER_PASSWORD and _CACHE_KEY and _SALT:
        return _CACHE_KEY
    salt = _SALT or os.urandom(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LENGTH,
                     salt=salt, iterations=PBKDF2_ITERATIONS)
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    _MASTER_PASSWORD = password
    _SALT = salt
    _CACHE_KEY = key
    return key


def set_master_password(password: str):
    global _MASTER_PASSWORD, _SALT, _CACHE_KEY
    _MASTER_PASSWORD = password
    _SALT = os.urandom(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LENGTH,
                     salt=_SALT, iterations=PBKDF2_ITERATIONS)
    _CACHE_KEY = base64.urlsafe_b64encode(kdf.derive(password.encode()))


def encrypt_data(data: bytes, master_password: str = None) -> Optional[bytes]:
    try:
        key = _get_or_derive_key(master_password)
        f = Fernet(key)
        return f.encrypt(data)
    except Exception as e:
        logger.error(f'Encryption failed: {e}')
        return None


def decrypt_data(data: bytes, master_password: str = None) -> Optional[bytes]:
    try:
        key = _get_or_derive_key(master_password)
        f = Fernet(key)
        return f.decrypt(data)
    except Exception as e:
        logger.warning(f'Decryption failed: {e}')
        return None


def generate_new_key(master_password: str) -> dict:
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LENGTH,
                     salt=salt, iterations=PBKDF2_ITERATIONS)
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
    return {'key': key.decode(), 'salt': salt.hex(), 'iterations': PBKDF2_ITERATIONS}


def secure_delete(filepath: str, passes: int = 3) -> bool:
    if not os.path.exists(filepath):
        return False
    try:
        size = os.path.getsize(filepath)
        with open(filepath, 'ba') as f:
            for p in range(passes):
                f.seek(0)
                if p == 0:
                    f.write(os.urandom(size))
                elif p == 1:
                    f.write(b'\x00' * size)
                else:
                    f.write(b'\xff' * size)
                f.flush()
                os.fsync(f.fileno())
        os.remove(filepath)
        return True
    except Exception as e:
        logger.warning(f'Secure delete failed {filepath}: {e}')
        try:
            os.remove(filepath)
        except Exception:
            pass
        return False


def reencrypt_all_backups(old_password: str, new_password: str) -> dict:
    from services.backup_service import _read_manifest, _write_bak, _get_backup_dir
    bdir = _get_backup_dir()
    total = 0
    success = 0
    failed = 0
    for fn in os.listdir(bdir):
        if not fn.endswith('.bak'):
            continue
        fp = os.path.join(bdir, fn)
        total += 1
        manifest = _read_manifest(fp)
        if not manifest or not manifest.get('encrypted'):
            continue
        try:
            with open(fp, 'rb') as f:
                prefix = f.read(4)
                mlen = struct.unpack('>I', prefix)[0]
                f.seek(4 + mlen)
                data = f.read()
            dec = decrypt_data(data, old_password)
            if not dec:
                failed += 1
                continue
            new_enc = encrypt_data(dec, new_password)
            if not new_enc:
                failed += 1
                continue
            new_checksum = hashlib.sha256(new_enc).hexdigest()
            manifest['checksum'] = new_checksum
            tmp_fp = fp + '.tmp'
            ok = _write_bak(tmp_fp, manifest, new_enc)
            if ok:
                import shutil
                shutil.move(tmp_fp, fp)
                success += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning(f'Re-encrypt failed {fn}: {e}')
            failed += 1
    return {'ok': True, 'total': total, 'success': success, 'failed': failed}
