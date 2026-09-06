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
URL_RE = re.compile(r"https?://\S+", re.I)
CATALOG_URL_RE = re.compile(r"https?://(?:www\.)?n8nworkflows\.xyz/\S*", re.I)


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


def clean_description_text(text: str) -> str:
    """Turn README prose into a clean card description."""
    text = CATALOG_URL_RE.sub("", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`>#]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -:\t\r\n")
    return text


def read_excerpt(readme: Path, title: str = "", limit: int = 240):
    if not readme:
        return ""
    try:
        text = readme.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    lines = text.replace("\r\n", "\n").split("\n")

    # Prefer the actual overview/description section instead of the README title/URL.
    overview_start = None
    for i, raw in enumerate(lines):
        heading = re.sub(r"^[#\s\d.:-]+", "", raw.strip()).strip().lower()
        if heading in {"workflow overview", "overview", "description", "workflow description"}:
            overview_start = i + 1
            break

    candidates = []
    scan = lines[overview_start:] if overview_start is not None else lines
    fenced = False

    for raw in scan:
        line = raw.strip()
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue

        # Stop at the next Markdown heading after we entered an overview section.
        if overview_start is not None and line.startswith("#"):
            break
        if not line:
            if candidates:
                break
            continue

        # Skip standalone URLs, catalog URLs, rules, table rows, and obvious list headings.
        if URL_RE.fullmatch(line) or "n8nworkflows.xyz" in line.lower():
            continue
        if re.fullmatch(r"[-|:\s]+", line):
            continue
        if line.startswith("|"):
            continue
        if re.match(r"^[-*]\s+", line):
            if candidates:
                break
            continue

        cleaned = clean_description_text(line)
        if not cleaned:
            continue

        # Avoid repeating the workflow title as its own description.
        if title and cleaned.lower().strip(" .") == title.lower().strip(" ."):
            continue

        candidates.append(cleaned)
        combined = " ".join(candidates)
        if len(combined) >= limit or combined.endswith(('.', '!', '?')):
            break

    # Fallback: first useful prose paragraph anywhere in the README.
    if not candidates:
        paragraph = []
        for raw in lines:
            line = raw.strip()
            if not line:
                if paragraph:
                    cleaned = clean_description_text(" ".join(paragraph))
                    if cleaned and (not title or cleaned.lower().strip(" .") != title.lower().strip(" .")):
                        candidates = [cleaned]
                        break
                    paragraph = []
                continue
            if line.startswith("#") or URL_RE.fullmatch(line) or "n8nworkflows.xyz" in line.lower() or line.startswith("|"):
                continue
            if re.match(r"^[-*]\s+", line):
                continue
            paragraph.append(line)

    excerpt = clean_description_text(" ".join(candidates))
    if not excerpt:
        return ""
    return (excerpt[:limit].rstrip(" ,;:-") + "…") if len(excerpt) > limit else excerpt


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
        title = clean_title(folder.name)

        cats = normalize_categories(meta)
        nodes, node_count = node_summary(meta, workflow)

        entry = {
            "id": template_id(folder.name),
            "folder": folder.name,
            "title": title,
            "preview": image.name if image else None,
            "preview_valid": bool(image),
            "has_preview_file": has_preview_file,
            "workflow_json": workflow_json_file.name if workflow_json_file else None,
            "readme": readme_file.name if readme_file else None,
            "metadata": metadata_file.name if metadata_file else None,
            "categories": cats,
            "excerpt": read_excerpt(readme_file, title),
            "workflow_name": workflow.get("name") or title,
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
        "version": 3,
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
