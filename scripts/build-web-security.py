"""Build standalone scenario images outside the platform; export one image per tar."""
import argparse
import json
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=root / "dist" / "web-security")
    parser.add_argument("--base-image", default="python:3.12-alpine", help="Python 3.12 Alpine base (or compatible local teaching image)")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((root / "backend/app/data/web_security.json").read_text(encoding="utf-8"))
    manifest = []
    for item in catalog:
        slug = item["slug"]
        tag = f"cyberlab/web-{slug}:2025-v1"
        subprocess.run(["docker", "build", "--pull=false", "--build-arg", "BASE_IMAGE=" + args.base_image,
                        "--build-arg", "LAB_SCENARIO=" + slug, "-t", tag, str(root / "docker/targets/web-top10")], check=True)
        image_id = subprocess.check_output(["docker", "image", "inspect", tag, "--format", "{{.Id}}"], text=True).strip()
        subprocess.run(["docker", "save", "-o", str(args.output / (slug + ".tar")), tag], check=True)
        manifest.append({"slug": slug, "tag": tag, "image_id": image_id, "title": item["title"]})
        print("Exported", slug, flush=True)
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
