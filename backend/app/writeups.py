"""Versioned source solutions; teachers' persisted edits take precedence."""
import json
from pathlib import Path

ROOT = Path(__file__).parent / "data" / "writeups"
CATALOG = json.loads((ROOT.parent / "web_security.json").read_text(encoding="utf-8"))
NAMES = {"SQL 注入基础实验": "sqli-basic", **{
    item["category"] + " · " + item["title"]: item["slug"] for item in CATALOG}}


def reference(slug: str) -> str:
    if slug not in NAMES.values():
        raise ValueError("Unknown built-in writeup")
    return (ROOT / (slug + ".md")).read_text(encoding="utf-8").rstrip() + "\n\n" + (ROOT / "common.md").read_text(encoding="utf-8")


def fill_missing(db):
    from sqlalchemy import select
    from app.models import LabTemplate
    updated, preserved, unmatched = [], [], []
    for lab in db.scalars(select(LabTemplate).order_by(LabTemplate.name)):
        slug = NAMES.get(lab.name)
        if not slug:
            unmatched.append({"id": lab.id, "name": lab.name})
        elif lab.writeup.strip():
            preserved.append(lab.id)
        else:
            lab.writeup = reference(slug)
            updated.append(lab.id)
    return {"updated": updated, "preserved": preserved, "unmatched": unmatched}


if __name__ == "__main__":
    from app.core.db import SessionLocal
    with SessionLocal.begin() as db:
        result = fill_missing(db)
    print(json.dumps(result, ensure_ascii=False))
