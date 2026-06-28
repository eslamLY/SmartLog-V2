"""
ZKTeco Device Tool — Connect, test, pull data from ZKTeco device
Usage:
    python scripts/zkteco_tool.py <command> [options]

Commands:
    test         Test connection to device
    info         Get full device info
    users        List all enrolled users
    attendance   Pull attendance logs
    pull_all     Pull users + attendance + save to DB
"""
import sys, os, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zk import ZK
from zk.exception import ZKError, ZKNetworkError, ZKErrorConnection


DEVICE_IP = '192.168.1.55'
DEVICE_PORT = 4370
DEVICE_PASSWORD = 0


def connect():
    zk = ZK(DEVICE_IP, port=DEVICE_PORT, timeout=30,
            password=DEVICE_PASSWORD, force_udp=False,
            verbose=False, ommit_ping=True)
    conn = zk.connect()
    return zk, conn


def cmd_test():
    try:
        zk, conn = connect()
        print(f'Connected: {conn}')
        name = zk.get_device_name()
        serial = zk.get_serialnumber()
        fw = zk.get_firmware_version()
        mac = zk.get_mac()
        platform = zk.get_platform()
        print(f'Device Name: {name}')
        print(f'Serial: {serial}')
        print(f'Firmware: {fw}')
        print(f'MAC: {mac}')
        print(f'Platform: {platform}')
        zk.disconnect()
        return True
    except Exception as e:
        print(f'FAILED: {e}')
        return False


def cmd_info():
    try:
        zk, conn = connect()
        info = {
            'device_name': zk.get_device_name(),
            'serial': zk.get_serialnumber(),
            'firmware': zk.get_firmware_version(),
            'mac': zk.get_mac(),
            'platform': zk.get_platform(),
            'time': str(zk.get_time()),
            'fp_version': zk.get_fp_version(),
            'face_version': zk.get_face_version(),
            'pin_width': zk.get_pin_width(),
            'network_params': zk.get_network_params(),
        }
        try:
            info['face_fun'] = zk.get_face_fun_on()
        except:
            info['face_fun'] = 'N/A'
        try:
            sizes = zk.read_sizes()
            info['sizes'] = sizes if isinstance(sizes, dict) else {'raw': str(sizes)}
        except:
            info['sizes'] = 'N/A'
        zk.disconnect()
        print(json.dumps(info, indent=2, ensure_ascii=False, default=str))
        return info
    except Exception as e:
        print(f'FAILED: {e}')
        return None


def cmd_users():
    try:
        zk, conn = connect()
        users = zk.get_users()
        zk.disconnect()
        print(f'Total Users: {len(users)}')
        for u in users:
            print(f'  UID={u.uid}, UserID={u.user_id}, Name={u.name}, '
                  f'Privilege={u.privilege}, Card={u.card}')
        return users
    except Exception as e:
        print(f'FAILED: {e}')
        return []


def cmd_attendance():
    try:
        zk, conn = connect()
        zk.disable_device()
        atts = zk.get_attendance()
        zk.enable_device()
        zk.disconnect()
        print(f'Total Attendance Records: {len(atts)}')
        for a in atts:
            print(f'  UID={a.uid}, UserID={a.user_id}, Time={a.timestamp}, '
                  f'Status={a.status}, Punch={a.punch}')
        return atts
    except Exception as e:
        print(f'FAILED: {e}')
        return []


def cmd_pull_all():
    try:
        zk, conn = connect()
        zk.disable_device()

        users = zk.get_users()
        atts = zk.get_attendance()
        device_name = zk.get_device_name()
        serial = zk.get_serialnumber()
        mac = zk.get_mac()

        zk.enable_device()
        zk.disconnect()

        output = {
            'device': {
                'ip': DEVICE_IP,
                'port': DEVICE_PORT,
                'name': device_name,
                'serial': serial,
                'mac': mac,
            },
            'users': [
                {'uid': u.uid, 'user_id': u.user_id, 'name': u.name,
                 'privilege': u.privilege, 'card': str(u.card)}
                for u in users
            ],
            'attendance': [
                {'uid': a.uid, 'user_id': a.user_id,
                 'timestamp': str(a.timestamp), 'status': a.status,
                 'punch': a.punch}
                for a in atts
            ],
        }

        filepath = os.path.join(os.path.dirname(__file__), 'zkteco_data.json')
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f'Saved to: {filepath}')
        print(f'Users: {len(users)}, Attendance: {len(atts)}')
        return output
    except Exception as e:
        print(f'FAILED: {e}')
        return None


def cmd_sync_smartlog():
    """Pull data from ZKTeco and save into SmartLog database"""
    from models import db, BioTimeDevice, Employee, AttendanceLog
    from datetime import datetime, UTC, date

    try:
        zk, conn = connect()
        zk.disable_device()

        users = zk.get_users()
        atts = zk.get_attendance()
        serial = zk.get_serialnumber()
        device_name = zk.get_device_name()
        mac = zk.get_mac()

        zk.enable_device()
        zk.disconnect()

        import app as smartlog_app
        with smartlog_app.app.app_context():
            device = BioTimeDevice.query.filter_by(serial_no=serial).first()
            if not device:
                device = BioTimeDevice(
                    serial_no=serial,
                    name=device_name or f'ZKTeco-{serial}',
                    ip_address=DEVICE_IP,
                    port=DEVICE_PORT,
                    mac_address=mac,
                    device_model='zkteco_custom',
                )
                db.session.add(device)
                db.session.flush()

            device.is_online = True
            device.last_online_at = datetime.now(UTC)

            imported_users = 0
            for u in users:
                emp = Employee.query.filter_by(username=str(u.user_id)).first()
                if not emp:
                    from werkzeug.security import generate_password_hash
                    emp = Employee(
                        username=str(u.user_id),
                        full_name=u.name or f'User-{u.user_id}',
                        department='عام',
                        password_hash=generate_password_hash('123456'),
                    )
                    db.session.add(emp)
                    imported_users += 1

            imported_att = 0
            for a in atts:
                emp = Employee.query.filter_by(username=str(a.user_id)).first()
                if not emp:
                    continue
                pt = a.timestamp
                if isinstance(pt, str):
                    try:
                        pt = datetime.fromisoformat(pt)
                    except:
                        pt = datetime.now(UTC)
                log_date = pt.date() if hasattr(pt, 'date') else pt
                existing = AttendanceLog.query.filter_by(
                    employee_id=emp.id, log_date=log_date,
                    clock_in=pt
                ).first()
                if not existing:
                    att = AttendanceLog(
                        employee_id=emp.id,
                        log_date=log_date,
                        clock_in=pt,
                        status='present',
                        is_inside_geofence=True,
                    )
                    db.session.add(att)
                    imported_att += 1

            device.records_pulled = (device.records_pulled or 0) + imported_att
            device.last_sync = datetime.now(UTC)
            db.session.commit()

        print(f'Sync complete: {imported_users} users, {imported_att} attendance records')
        return True
    except Exception as e:
        print(f'Sync FAILED: {e}')
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    commands = {
        'test': cmd_test,
        'info': cmd_info,
        'users': cmd_users,
        'attendance': cmd_attendance,
        'pull_all': cmd_pull_all,
        'sync': cmd_sync_smartlog,
    }
    fn = commands.get(command)
    if not fn:
        print(f'Unknown command: {command}')
        sys.exit(1)

    result = fn()
    if result is None or result is False:
        sys.exit(1)
