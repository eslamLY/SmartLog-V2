import requests
import json

BASE_URL = "http://localhost:5000"

# Login as admin
session = requests.Session()
login_data = {
    "username": "ADMIN001",
    "password": "admin123"
}

print("="*60)
print("Testing API Endpoints (Buttons & Actions)")
print("="*60)

# Login first
print("\n[1/2] Logging in as admin...")
try:
    response = session.post(f"{BASE_URL}/login", json=login_data)
    print(f"Login response: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if data.get('ok'):
            print("✅ Login successful")
        else:
            print(f"❌ Login failed: {data.get('msg')}")
    else:
        print(f"❌ Login failed with status {response.status_code}")
except Exception as e:
    print(f"❌ Login error: {e}")

# API endpoints to test (these represent button actions)
api_endpoints = [
    # Dashboard APIs
    ("/api/dashboard/stats", "Dashboard Stats"),
    ("/api/dashboard/charts/weekly", "Weekly Charts"),
    ("/api/dashboard/charts/donut", "Donut Charts"),
    ("/api/dashboard/charts/heatmap", "Heatmap Charts"),
    ("/api/dashboard/charts/punctuality", "Punctuality Charts"),
    ("/api/dashboard/charts/hourly", "Hourly Charts"),
    ("/api/dashboard/records", "Dashboard Records"),
    ("/api/dashboard/alerts", "Dashboard Alerts"),
    ("/api/dashboard/schedule", "Dashboard Schedule"),
    ("/api/dashboard/search", "Dashboard Search"),
    ("/api/dashboard/notifications", "Dashboard Notifications"),
    ("/api/dashboard/live", "Dashboard Live"),
    ("/api/dashboard/map", "Dashboard Map"),
    
    # Employee APIs
    ("/api/employees/list", "Employees List"),
    ("/api/employees/add", "Add Employee"),
    ("/api/employees/update", "Update Employee"),
    ("/api/employees/delete", "Delete Employee"),
    
    # Department APIs
    ("/api/departments/list", "Departments List"),
    ("/api/departments/add", "Add Department"),
    ("/api/departments/update", "Update Department"),
    
    # Attendance APIs
    ("/api/attendance/logs", "Attendance Logs"),
    ("/api/attendance/check-in", "Check In"),
    ("/api/attendance/check-out", "Check Out"),
    
    # Leave APIs
    ("/api/leaves/request", "Leave Request"),
    ("/api/leaves/approve", "Approve Leave"),
    ("/api/leaves/reject", "Reject Leave"),
    
    # Device APIs
    ("/api/devices/list", "Devices List"),
    ("/api/devices/sync", "Sync Devices"),
    ("/api/devices/status", "Device Status"),
    
    # Payroll APIs
    ("/api/payroll/calculate", "Calculate Payroll"),
    ("/api/payroll/generate", "Generate Payroll"),
    ("/api/payroll/export", "Export Payroll"),
    
    # Report APIs
    ("/api/reports/attendance", "Attendance Report"),
    ("/api/reports/employees", "Employees Report"),
    ("/api/reports/departments", "Departments Report"),
    
    # Backup APIs
    ("/api/backups/create", "Create Backup"),
    ("/api/backups/list", "List Backups"),
    ("/api/backups/restore", "Restore Backup"),
    
    # System APIs
    ("/api/system/health", "System Health"),
    ("/api/system/logs", "System Logs"),
]

print("\n[2/2] Testing API endpoints...")
print("="*60)

results = []
for path, name in api_endpoints:
    try:
        response = session.get(f"{BASE_URL}{path}")
        status = response.status_code
        if status == 200:
            print(f"✅ {name:40} - {path:40} [200 OK]")
            results.append((name, path, "OK", None))
        elif status == 302:
            print(f"⚠️  {name:40} - {path:40} [302 Redirect]")
            results.append((name, path, "Redirect", None))
        elif status == 404:
            print(f"❌ {name:40} - {path:40} [404 Not Found]")
            results.append((name, path, "Not Found", None))
        elif status == 403:
            print(f"🔒 {name:40} - {path:40} [403 Forbidden]")
            results.append((name, path, "Forbidden", None))
        elif status == 401:
            print(f"🔐 {name:40} - {path:40} [401 Unauthorized]")
            results.append((name, path, "Unauthorized", None))
        elif status == 405:
            print(f"🚫 {name:40} - {path:40} [405 Method Not Allowed]")
            results.append((name, path, "Method Not Allowed", None))
        else:
            print(f"❓ {name:40} - {path:40} [{status}]")
            results.append((name, path, f"Status {status}", None))
    except Exception as e:
        print(f"❌ {name:40} - {path:40} [Error: {str(e)[:30]}]")
        results.append((name, path, "Error", str(e)))

print("\n" + "="*60)
print("API Endpoints Summary")
print("="*60)

ok_count = sum(1 for _, _, status, _ in results if status == "OK")
redirect_count = sum(1 for _, _, status, _ in results if status == "Redirect")
error_count = sum(1 for _, _, status, _ in results if status not in ["OK", "Redirect"])

print(f"✅ Working: {ok_count}")
print(f"⚠️  Redirects: {redirect_count}")
print(f"❌ Errors: {error_count}")
print(f"📊 Total: {len(results)}")

# Save results to file
with open("api_test_results.json", "w", encoding="utf-8") as f:
    json.dump([
        {"name": name, "path": path, "status": status, "error": error}
        for name, path, status, error in results
    ], f, indent=2, ensure_ascii=False)

print("\nResults saved to api_test_results.json")
