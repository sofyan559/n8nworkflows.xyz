#!/usr/bin/env python3
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'wordpress-plugin' / 'eg-n8n-workflow-library'
CATALOG = ROOT / 'catalog-index.json'
BUILD = ROOT / 'dist' / 'eg-n8n-workflow-library'
ZIP = ROOT / 'dist' / 'eg-n8n-workflow-library-v1.0.2.zip'

if not SRC.exists():
    raise SystemExit(f'Missing plugin source: {SRC}')
if not CATALOG.exists():
    raise SystemExit(f'Missing catalog: {CATALOG}')

shutil.rmtree(BUILD, ignore_errors=True)
BUILD.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(SRC, BUILD)
shutil.copy2(CATALOG, BUILD / 'catalog.json')

if ZIP.exists():
    ZIP.unlink()
with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in BUILD.rglob('*'):
        if p.is_file():
            z.write(p, Path('eg-n8n-workflow-library') / p.relative_to(BUILD))

print(f'Built {ZIP}')
print(f'Bundled catalog bytes: {(BUILD / "catalog.json").stat().st_size}')
