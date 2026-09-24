import urllib.request
import json
import socket
import sys

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0

services = [
    ('Central Software (Backend Gateway)', 'http://localhost:8000/api/v1/health', 8000),
    ('Web (Vite React Portal)', 'http://localhost:5173', 5173),
    ('App (Expo Mobile Web)', 'http://localhost:8081', 8081)
]

print("="*60)
print("[*] AEGIS SYSTEM SERVICE HEALTH & RUNTIME STATUS")
print("="*60)

for name, url, port in services:
    is_open = check_port(port)
    if not is_open:
        print(f"[FAIL] {name}: PORT {port} NOT LISTENING")
        continue
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'StatusChecker'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            status_code = resp.getcode()
            if 'health' in url:
                body = json.loads(resp.read().decode('utf-8'))
                sys_status = body.get('data', {}).get('system_status', 'UNKNOWN')
                db_engine = body.get('data', {}).get('database', {}).get('engine', 'UNKNOWN')
                db_status = body.get('data', {}).get('database', {}).get('status', 'UNKNOWN')
                providers = body.get('data', {}).get('providers_summary', {}).get('healthy', 0)
                print(f"[PASS] {name}: RUNNING (HTTP {status_code} OK)")
                print(f"       Endpoint: {url}")
                print(f"       System Status: {sys_status}")
                print(f"       Database: {db_engine} ({db_status})")
                print(f"       Active Providers: {providers}/7")
            else:
                print(f"[PASS] {name}: RUNNING (HTTP {status_code} OK)")
                print(f"       URL: {url}")
    except Exception as e:
        print(f"[WARN] {name}: Port {port} open but request error: {e}")

print("="*60)
