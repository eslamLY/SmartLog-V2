import requests
import json

BASE_URL = "http://localhost:5000"

# Login as employee
session = requests.Session()
login_data = {
    "username": "EMP001",
    "password": "emp123"
}

print("="*60)
print("Testing Employee Portal Screens")
print("="*60)

# Login first
print("\n[1/2] Logging in as employee...")
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

# Employee screens to test
employee_screens = [
    ("/employee", "Employee Dashboard"),
    ("/employee/shifts", "Employee Shifts"),
    ("/employee/documents", "Employee Documents"),
    ("/employee/history", "Employee History"),
    ("/employee/leaves", "Employee Leaves"),
    ("/employee/reports", "Employee Reports"),
    ("/employee/my_profile", "Employee Profile"),
]

print("\n[2/2] Testing employee screens...")
print("="*60)

results = []
for path, name in employee_screens:
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
        else:
            print(f"❓ {name:40} - {path:40} [{status}]")
            results.append((name, path, f"Status {status}", None))
    except Exception as e:
        print(f"❌ {name:40} - {path:40} [Error: {str(e)[:30]}]")
        results.append((name, path, "Error", str(e)))

print("\n" + "="*60)
print("Employee Portal Summary")
print("="*60)

ok_count = sum(1 for _, _, status, _ in results if status == "OK")
redirect_count = sum(1 for _, _, status, _ in results if status == "Redirect")
error_count = sum(1 for _, _, status, _ in results if status not in ["OK", "Redirect"])

print(f"✅ Working: {ok_count}")
print(f"⚠️  Redirects: {redirect_count}")
print(f"❌ Errors: {error_count}")
print(f"📊 Total: {len(results)}")

# Save results to file
with open("employee_screen_test_results.json", "w", encoding="utf-8") as f:
    json.dump([
        {"name": name, "path": path, "status": status, "error": error}
        for name, path, status, error in results
    ], f, indent=2, ensure_ascii=False)

print("\nResults saved to employee_screen_test_results.json")
