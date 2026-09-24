#!/usr/bin/env python3
import os
import sys
import yaml
import argparse
from datetime import datetime

MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "deployment", "versions.yaml")

def bump_version(current: str, part: str) -> str:
    major, minor, patch = map(int, current.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return current

def main():
    parser = argparse.ArgumentParser(description="AEGIS Master Release Manager")
    parser.add_argument("--service", choices=["api", "web", "mobile", "ingestion", "ai-engine", "sos-engine", "all"], default="all")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], default="patch")
    args = parser.parse_args()

    if not os.path.exists(MANIFEST_PATH):
        print(f"Error: manifest not found at {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    print(f"=== BUMPING AEGIS VERSIONS ({args.bump.upper()}) ===")
    services = data.get("services", {})
    
    for s_name, s_info in services.items():
        if args.service in ["all", s_name]:
            old_v = s_info.get("version", "1.0.0")
            new_v = bump_version(old_v, args.bump)
            s_info["version"] = new_v
            if "image" in s_info:
                prefix = s_info["image"].split(":")[0]
                s_info["image"] = f"{prefix}:{new_v}"
            print(f"Service [{s_name}]: {old_v} -> {new_v}")

    data["last_updated"] = datetime.utcnow().isoformat() + "Z"
    
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False)
        
    print("✓ deployment/versions.yaml updated successfully.")

if __name__ == "__main__":
    main()
