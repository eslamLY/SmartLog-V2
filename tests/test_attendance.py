from tests.helpers import login
import json
from datetime import datetime, timedelta

def test_employee_dashboard(client):
    login(client, 'EMP001', '123456')
    r = client.get('/employee')
    assert r.status_code == 200

def test_admin_attendance_page(client):
    login(client)
    r = client.get('/admin/attendance')
    assert r.status_code == 200
