#!/usr/bin/env python3
from pathlib import Path
import html

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"
OUT = ROOT / "verification.html"

# Known real WEBP files in this fork. We intentionally verify the files stored
# inside each workflow folder, not a generated graph or an external screenshot.
PREFERRED_IDS = [2653, 4049, 4731, 6288, 8093, 3151]


def is_real_webp(path: Path) -> bool:
    try:
        head = path.read_bytes()[:12]
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    except Exception:
        return False


def find_by_id(template_id: int):
    suffix = f"-{template_id}"
    for folder in WORKFLOWS.iterdir():
        if not folder.is_dir() or not folder.name.rstrip().endswith(suffix):
            continue
        for file in folder.iterdir():
            if file.is_file() and file.suffix.lower() == ".webp" and is_real_webp(file):
                return folder, file
    return None


def title_for(folder: Path):
    name = folder.name.strip()
    if "-" in name:
        name = name.rsplit("-", 1)[0]
    return name

cards = []
for template_id in PREFERRED_IDS:
    hit = find_by_id(template_id)
    if not hit:
        continue
    folder, image = hit
    rel = image.relative_to(ROOT).as_posix()
    cards.append((template_id, title_for(folder), rel))

if len(cards) < 3:
    # Fallback: scan for the first six real WEBP screenshots.
    cards = []
    for folder in sorted((p for p in WORKFLOWS.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        for image in folder.glob("*.webp"):
            if is_real_webp(image):
                tid = folder.name.rstrip().rsplit("-", 1)[-1]
                try:
                    tid = int(tid)
                except Exception:
                    tid = 0
                cards.append((tid, title_for(folder), image.relative_to(ROOT).as_posix()))
                break
        if len(cards) >= 6:
            break

card_html = "\n".join(
    f'''<article class="card"><div class="media"><img src="/{html.escape(rel, quote=True)}" alt="{html.escape(title, quote=True)} preview"><span class="free">Free</span><span class="id">#{tid}</span></div><div class="body"><h3>{html.escape(title)}</h3><div class="tags"><span>Workflow preview</span><span>Real .webp</span></div><div class="open">Open workflow →</div></div></article>'''
    for tid, title, rel in cards
)

OUT.write_text(f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Workflow Library Verification</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f7f7fb;color:#251a35;font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}}.top{{height:66px;background:#fff;border-bottom:1px solid #e8e4ed;display:flex;align-items:center}}.shell{{width:min(1320px,calc(100% - 40px));margin:auto}}.brand{{font-weight:900;color:#33137a;font-size:17px}}.brand b{{display:inline-grid;place-items:center;width:38px;height:38px;background:#e52535;color:#fff;border-radius:10px;font-size:12px;margin-right:10px}}.hero{{background:#fff;border-bottom:1px solid #e8e4ed;padding:34px 0 26px}}.kicker{{display:inline-block;background:#fff0f2;color:#c91d2c;padding:7px 10px;border-radius:8px;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.08em}}h1{{font-size:46px;line-height:1.02;letter-spacing:-.04em;color:#260b61;margin:12px 0 8px}}.sub{{color:#756f7f;font-size:15px}}.verified{{margin-top:18px;display:inline-block;padding:10px 12px;border:1px solid #cbe9da;background:#f3fbf7;color:#147447;border-radius:10px;font-size:12px;font-weight:800}}.main{{padding:24px 0 50px}}.head{{font-size:14px;color:#756f7f;margin-bottom:12px}}.head strong{{color:#33137a}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}.card{{background:#fff;border:1px solid #e8e4ed;border-radius:16px;overflow:hidden;box-shadow:0 12px 30px rgba(38,11,97,.07)}}.media{{position:relative;aspect-ratio:16/9;background:#f4f3f7;border-bottom:1px solid #e8e4ed}}.media img{{width:100%;height:100%;object-fit:contain;background:#fff}}.free,.id{{position:absolute;top:10px;padding:6px 8px;background:#fff;border:1px solid #e8e4ed;border-radius:8px;font-size:10px;font-weight:900;box-shadow:0 4px 10px rgba(38,11,97,.08)}}.free{{left:10px;color:#128653}}.id{{right:10px;color:#33137a}}.body{{padding:14px;min-height:142px;display:flex;flex-direction:column}}h3{{font-size:15px;line-height:1.38;color:#260b61;margin:0 0 10px}}.tags{{display:flex;gap:6px;flex-wrap:wrap}}.tags span{{background:#f3f0f8;color:#655276;border-radius:7px;padding:5px 8px;font-size:10px;font-weight:800}}.open{{margin-top:auto;padding-top:14px;color:#e52535;font-size:12px;font-weight:900}}@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:620px){{.grid{{grid-template-columns:1fr}}h1{{font-size:36px}}}}
</style></head><body><div class="top"><div class="shell brand"><b>n8n</b>Workflow Library</div></div><section class="hero"><div class="shell"><span class="kicker">Verification build</span><h1>Real workflow screenshots are loading.</h1><div class="sub">This page is rendered from the actual <code>.webp</code> files checked out from your GitHub workflow folders.</div><div class="verified">✓ WEBP magic bytes verified before rendering</div></div></section><main class="shell main"><div class="head"><strong>{len(cards)}</strong> real workflow previews shown</div><div class="grid">{card_html}</div></main></body></html>''', encoding="utf-8")
print(f"Created {OUT} with {len(cards)} verified WEBP previews")
