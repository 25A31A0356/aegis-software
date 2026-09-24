#!/usr/bin/env python3
import sys
import time
import urllib.request
import json
import argparse

def check_health(endpoint: str, timeout: int = 30) -> bool:
    print(f"Validating health gate for: {endpoint} (timeout={timeout}s)")
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"{endpoint}/health/ready", headers={"User-Agent": "AEGIS-HealthGate/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    print(f"✓ Health Gate PASSED: {data}")
                    return True
        except Exception as e:
            print(f"Probe waiting... ({e})")
            time.sleep(2)
    print("✗ Health Gate FAILED! Triggering automatic rollback safeguard.")
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://localhost:8000")
    args = parser.parse_args()
    if not check_health(args.endpoint):
        sys.exit(1)
