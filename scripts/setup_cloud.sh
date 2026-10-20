#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
python -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.lock
npm --prefix frontend ci --cache "${NPM_CONFIG_CACHE:-/workspace/.npm-cache}" --no-audit --no-fund
npm --prefix frontend run build
# Docker includes both OCR languages. In this cloud, install the missing
# Russian model locally from the pinned official Tesseract release, with checksum.
.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,shutil,subprocess,urllib.request
root=Path.cwd()
if not shutil.which('tesseract'):
    raise SystemExit('Tesseract is missing; use Docker or install tesseract-ocr + tesseract-ocr-rus + tesseract-ocr-eng')
langs=subprocess.check_output(['tesseract','--list-langs'],text=True,stderr=subprocess.STDOUT)
if 'rus\n' not in langs:
    target=root/'data/tessdata';target.mkdir(parents=True,exist_ok=True)
    dest=target/'rus.traineddata'
    expected='e16e5e036cce1d9ec2b00063cf8b54472625b9e14d893a169e2b0dedeb4df225'
    if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest()!=expected:
        with urllib.request.urlopen('https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/rus.traineddata',timeout=45) as r:
            data=r.read()
        if hashlib.sha256(data).hexdigest()!=expected:raise SystemExit('Russian OCR model checksum mismatch')
        dest.write_bytes(data)
    english=Path('/usr/share/tesseract-ocr/5/tessdata/eng.traineddata')
    if not english.exists():raise SystemExit('English OCR language data missing; install tesseract-ocr-eng or use Docker')
    if not (target/'eng.traineddata').exists():shutil.copyfile(english,target/'eng.traineddata')
print('Tools, frontend and OCR ready.')
PY
