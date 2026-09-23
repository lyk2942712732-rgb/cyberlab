"""ADMIN API upload workflow. Uses httpx from backend requirements; never calls Docker."""
import argparse
import json
import os
import time
from pathlib import Path
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://backend:8000")
    parser.add_argument("--image-dir", required=True, type=Path)
    parser.add_argument("--insecure", action="store_true", help="Allow a local self-signed HTTPS certificate")
    args = parser.parse_args()
    manifest = json.loads((args.image_dir / "manifest.json").read_text(encoding="utf-8"))
    mapping = {}
    with httpx.Client(base_url=args.url + "/api", verify=not args.insecure, timeout=300, trust_env=False) as client:
        response = client.post("/auth/login", json={"username": "admin", "password": os.environ["ADMIN_PASSWORD"]})
        response.raise_for_status()
        client.headers["Authorization"] = "Bearer " + response.json()["data"]["access_token"]
        for item in manifest:
            response = client.get("/admin/images"); response.raise_for_status()
            existing = next((row for row in response.json()["data"] if row["image_id"] == item["image_id"] and row["status"] == "READY"), None)
            if existing:
                mapping[item["slug"]] = existing["id"]
                continue
            with (args.image_dir / (item["slug"] + ".tar")).open("rb") as stream:
                response = client.post("/admin/images/upload", data={"display_name": item["title"]}, files={"file": (item["slug"] + ".tar", stream, "application/x-tar")})
            response.raise_for_status()
            identifier = response.json()["data"]["id"]
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                response = client.get("/admin/images"); response.raise_for_status()
                image = next(row for row in response.json()["data"] if row["id"] == identifier)
                if image["status"] == "FAILED":
                    raise RuntimeError(f"Import failed for {item['slug']}: {image['error_message']}")
                if image["status"] == "READY":
                    if image["image_id"] != item["image_id"]:
                        raise RuntimeError("Imported image differs from build manifest")
                    mapping[item["slug"]] = identifier
                    break
                time.sleep(2)
            else:
                raise TimeoutError("Image import timed out: " + item["slug"])
            print("READY", item["slug"], flush=True)
    destination = args.image_dir / "image-map.json"
    destination.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print("Image map saved:", destination)


if __name__ == "__main__":
    main()
