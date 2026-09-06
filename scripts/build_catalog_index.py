#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"
OUTPUT = ROOT / "catalog-index.json"

IMAGE_EXTS = {".webp", ".png", ".jpg", ".jpeg", ".gif"}
META_RE = re.compile(r"^metada(?:ta)?-\d+\.json$", re.I)
README_RE = re.compile(r"^readme-\d+\.md$", re.I)
ID_RE = re.compile(r"-(\d+)\s*$")

def clean_title(folder_name: str) -> str:
    return ID_RE.sub("", folder_name).replace("_", " ").strip()

def template_id(folder_name: str):
    m = ID_RE.search(folder_name)
    return int(m.group(1)) if m else None

def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def first_nonempty(*values):
    for v in values:
        if v not in (None, "", [], {}):
            return v
    return None

def is_real_image(path: Path) -> bool:
    try:
        data = path.read_bytes()[:16]
    except Exception:
        return False
    ext = path.suffix.lower()
    if ext == ".webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if ext == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in {".jpg", ".jpeg"}:
        return data.startswith(b"\xff\xd8\xff")
    if ext == ".gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    return False

def read_excerpt(readme: Path, limit=220):
    if not readme:
        return ""
    try:
        text = readme.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    lines = []
    fenced = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not line:
            continue
        if line.startswith("#"):
            continue
        line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"[*_`>#-]+", " ", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
        if len(" ".join(lines)) >= limit:
            break
    text = " ".join(lines).strip()
    return (text[:limit].rstrip() + "…") if len(text) > limit else text

def normalize_categories(meta):
    cats = meta.get("categories") or []
    out = []
    if isinstance(cats, list):
        for c in cats:
            if isinstance(c, dict):
                name = c.get("name")
            else:
                name = str(c)
            if name and name not in out:
                out.append(name)
    return out

def node_summary(meta, workflow):
    raw = meta.get("nodeTypes")
    if isinstance(raw, dict) and raw:
        out = []
        total = 0
        for node_type, info in raw.items():
            if isinstance(info, dict):
                count = int(info.get("count") or 1)
            else:
                try:
                    count = int(info)
                except Exception:
                    count = 1
            out.append({"type": node_type, "count": count})
            total += count
        return out, total

    nodes = workflow.get("nodes") or []
    counts = {}
    for n in nodes:
        t = n.get("type") if isinstance(n, dict) else None
        if t:
            counts[t] = counts.get(t, 0) + 1
    return [{"type": k, "count": v} for k, v in counts.items()], len(nodes)

def main():
    if not WORKFLOWS.exists():
        raise SystemExit(f"Missing workflows directory: {WORKFLOWS}")

    entries = []
    valid_previews = 0
    invalid_previews = 0

    for folder in sorted((p for p in WORKFLOWS.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        files = [p for p in folder.iterdir() if p.is_file()]

        image_candidates = [p for p in files if p.suffix.lower() in IMAGE_EXTS]
        image = next((p for p in image_candidates if is_real_image(p)), None)
        has_preview_file = bool(image_candidates)
        if image:
            valid_previews += 1
        elif has_preview_file:
            invalid_previews += 1

        metadata_file = next((p for p in files if META_RE.match(p.name)), None)
        readme_file = next((p for p in files if README_RE.match(p.name)), None)
        if readme_file is None:
            readme_file = next((p for p in files if p.suffix.lower() == ".md"), None)

        workflow_json_file = next(
            (p for p in files if p.suffix.lower() == ".json" and not META_RE.match(p.name)),
            None
        )

        meta = read_json(metadata_file) if metadata_file else {}
        workflow = read_json(workflow_json_file) if workflow_json_file else {}

        cats = normalize_categories(meta)
        nodes, node_count = node_summary(meta, workflow)

        entry = {
            "id": template_id(folder.name),
            "folder": folder.name,
            "title": clean_title(folder.name),
            "preview": image.name if image else None,
            "preview_valid": bool(image),
            "has_preview_file": has_preview_file,
            "workflow_json": workflow_json_file.name if workflow_json_file else None,
            "readme": readme_file.name if readme_file else None,
            "metadata": metadata_file.name if metadata_file else None,
            "categories": cats,
            "excerpt": read_excerpt(readme_file),
            "workflow_name": workflow.get("name") or clean_title(folder.name),
            "active": bool(workflow.get("active")),
            "node_count": node_count,
            "node_types": nodes,
            "author_name": first_nonempty(meta.get("user_name"), meta.get("user_username")),
            "author_username": meta.get("user_username"),
            "author_avatar": meta.get("user_avatar"),
            "author_bio": meta.get("user_bio"),
            "n8n_url": meta.get("url_n8n"),
        }

        search_parts = [
            entry["title"],
            " ".join(entry["categories"]),
            " ".join(n.get("type", "") for n in entry["node_types"]),
            entry["author_name"] or "",
            entry["excerpt"] or "",
        ]
        entry["search"] = " ".join(search_parts).lower()
        entries.append(entry)

    output = {
        "version": 2,
        "count": len(entries),
        "valid_preview_count": valid_previews,
        "invalid_preview_file_count": invalid_previews,
        "workflows": entries,
    }

    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )
    print(f"Wrote {len(entries)} workflows to {OUTPUT}")
    print(f"Valid image previews: {valid_previews}; invalid image-named files: {invalid_previews}")

if __name__ == "__main__":
    main()
