import os, socket, struct, json, logging
from datetime import datetime, UTC
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

BIOTIME_DEFAULT_PORT = 4370
BIOTIME_COMMAND_CONNECT = 1000
BIOTIME_COMMAND_DISCONNECT = 1001
BIOTIME_COMMAND_GET_INFO = 1100
BIOTIME_COMMAND_GET_ENROLLED = 1101
BIOTIME_COMMAND_GET_ATT_LOG = 1500
BIOTIME_COMMAND_SET_USER = 2000
BIOTIME_COMMAND_DELETE_USER = 2001
BIOTIME_COMMAND_RESTART = 3000
BIOTIME_COMMAND_CLEAR_LOGS = 3001


def test_connection(ip: str, port: int = BIOTIME_DEFAULT_PORT, timeout: int = 5) -> dict:
    result = {'online': False, 'ping_ms': None, 'error': None}
    try:
        import subprocess
        import platform
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        cmd = ['ping', param, '1', '-w', str(timeout * 1000), ip]
        start = datetime.now(UTC)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
        elapsed = (datetime.now(UTC) - start).total_seconds() * 1000
        if proc.returncode == 0:
            result['online'] = True
            result['ping_ms'] = round(elapsed, 1)
        else:
            result['error'] = 'جهاز بدون رد'
            try:
                sock_result = _test_tcp_port(ip, port, timeout)
                if sock_result.get('online'):
                    result['online'] = True
                    result['ping_ms'] = sock_result.get('ping_ms')
                    result['note'] = 'TCP port reachable (ICMP blocked)'
                else:
                    result['error'] = sock_result.get('error', 'لا يمكن الاتصال')
            except Exception as e:
                result['error'] = str(e)
    except subprocess.TimeoutExpired:
        result['error'] = 'انتهت مهلة الاتصال'
    except Exception as e:
        result['error'] = str(e)
    return result


def _test_tcp_port(ip: str, port: int, timeout: int = 5) -> dict:
    result = {'online': False, 'ping_ms': None, 'error': None}
    try:
        start = datetime.now(UTC)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        elapsed = (datetime.now(UTC) - start).total_seconds() * 1000
        sock.close()
        result['online'] = True
        result['ping_ms'] = round(elapsed, 1)
    except socket.timeout:
        result['error'] = 'انتهت مهلة الاتصال'
    except ConnectionRefusedError:
        result['error'] = 'تم رفض الاتصال'
    except socket.gaierror:
        result['error'] = 'عنوان IP غير صالح'
    except Exception as e:
        result['error'] = str(e)
    return result


def get_device_info(ip: str, port: int = BIOTIME_DEFAULT_PORT, password: str = None) -> dict:
    info = {
        'firmware_ver': None,
        'serial_no': None,
        'fp_capacity': 0,
        'fp_enrolled': 0,
        'face_capacity': 0,
        'face_enrolled': 0,
        'card_capacity': 0,
        'card_enrolled': 0,
        'txlog_capacity': 0,
        'txlog_used': 0,
        'device_model': None,
        'error': None,
    }
    try:
        conn = test_connection(ip, port)
        if not conn.get('online'):
            info['error'] = conn.get('error', 'لا يمكن الاتصال')
            return info
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((ip, port))
            _send_command(sock, BIOTIME_COMMAND_CONNECT)
            if password:
                _send_command(sock, 1102, password)
            resp = _send_command(sock, BIOTIME_COMMAND_GET_INFO)
            if resp:
                info['firmware_ver'] = resp.get('firmware', resp.get('Firmware', ''))
                info['serial_no'] = resp.get('serial', resp.get('Serial', ''))
                info['device_model'] = resp.get('model', resp.get('Model', ''))
                info['fp_capacity'] = int(resp.get('FPCap', resp.get('fp_cap', 0)))
                info['fp_enrolled'] = int(resp.get('FPCount', resp.get('fp_count', 0)))
                info['face_capacity'] = int(resp.get('FaceCap', resp.get('face_cap', 0)))
                info['face_enrolled'] = int(resp.get('FaceCount', resp.get('face_count', 0)))
                info['card_capacity'] = int(resp.get('CardCap', resp.get('card_cap', 0)))
                info['card_enrolled'] = int(resp.get('CardCount', resp.get('card_count', 0)))
                info['txlog_capacity'] = int(resp.get('TxLogCap', resp.get('txlog_cap', 0)))
                info['txlog_used'] = int(resp.get('TxLogCount', resp.get('txlog_count', 0)))
            _send_command(sock, BIOTIME_COMMAND_DISCONNECT)
            sock.close()
        except Exception as e:
            info['error'] = f'SDK error: {e}'
    except Exception as e:
        info['error'] = str(e)
    return info


def push_employee(ip: str, port: int, emp_data: dict, password: str = None) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))
        _send_command(sock, BIOTIME_COMMAND_CONNECT)
        if password:
            _send_command(sock, 1102, password)
        result = _send_command(sock, BIOTIME_COMMAND_SET_USER, {
            'uid': emp_data.get('uid', 0),
            'name': emp_data.get('name', ''),
            'password': emp_data.get('password', ''),
            'card': emp_data.get('card', ''),
            'privilege': emp_data.get('privilege', 0),
        })
        _send_command(sock, BIOTIME_COMMAND_DISCONNECT)
        sock.close()
        return result is not None
    except Exception as e:
        logger.error(f'Push employee failed: {e}')
        return False


def delete_employee(ip: str, port: int, uid: int, password: str = None) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))
        _send_command(sock, BIOTIME_COMMAND_CONNECT)
        if password:
            _send_command(sock, 1102, password)
        result = _send_command(sock, BIOTIME_COMMAND_DELETE_USER, {'uid': uid})
        _send_command(sock, BIOTIME_COMMAND_DISCONNECT)
        sock.close()
        return result is not None
    except Exception:
        return False


def restart_device(ip: str, port: int, password: str = None) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))
        _send_command(sock, BIOTIME_COMMAND_CONNECT)
        if password:
            _send_command(sock, 1102, password)
        result = _send_command(sock, BIOTIME_COMMAND_RESTART)
        _send_command(sock, BIOTIME_COMMAND_DISCONNECT)
        sock.close()
        return result is not None
    except Exception:
        return False


def clear_device_logs(ip: str, port: int, password: str = None) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))
        _send_command(sock, BIOTIME_COMMAND_CONNECT)
        if password:
            _send_command(sock, 1102, password)
        result = _send_command(sock, BIOTIME_COMMAND_CLEAR_LOGS)
        _send_command(sock, BIOTIME_COMMAND_DISCONNECT)
        sock.close()
        return result is not None
    except Exception:
        return False


def pull_attendance_logs(ip: str, port: int, password: str = None) -> list:
    logs = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect((ip, port))
        _send_command(sock, BIOTIME_COMMAND_CONNECT)
        if password:
            _send_command(sock, 1102, password)
        raw = _send_command(sock, BIOTIME_COMMAND_GET_ATT_LOG)
        if raw and isinstance(raw, list):
            logs = raw
        _send_command(sock, BIOTIME_COMMAND_DISCONNECT)
        sock.close()
    except Exception as e:
        logger.error(f'Pull attendance logs failed: {e}')
    return logs


def _send_command(sock, command: int, data=None) -> Optional[dict]:
    try:
        payload = struct.pack('>I', command)
        if data is not None:
            if isinstance(data, str):
                payload += data.encode('utf-8')
            elif isinstance(data, dict):
                payload += json.dumps(data, ensure_ascii=False).encode('utf-8')
            elif isinstance(data, bytes):
                payload += data
        sock.sendall(payload)
        resp = sock.recv(4096)
        if resp:
            try:
                return json.loads(resp.decode('utf-8').strip('\x00'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {'raw': resp.hex()}
        return None
    except Exception as e:
        logger.error(f'BIOTIME send_command error: {e}')
        return None


def scan_network(subnet: str = '192.168.1', timeout: int = 3) -> list:
    found = []
    for i in range(1, 255):
        ip = f'{subnet}.{i}'
        try:
            conn = test_connection(ip, BIOTIME_DEFAULT_PORT, timeout=timeout)
            if conn.get('online'):
                info = get_device_info(ip, BIOTIME_DEFAULT_PORT)
                if info.get('serial_no'):
                    found.append({
                        'ip': ip,
                        'serial_no': info['serial_no'],
                        'mac': info.get('mac', ''),
                        'firmware': info.get('firmware_ver', ''),
                        'model': info.get('device_model', ''),
                    })
        except Exception:
            pass
    return found
