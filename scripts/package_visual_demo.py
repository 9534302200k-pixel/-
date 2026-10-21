"""Inline the visual bundle so double-clicking one HTML works offline in Windows."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "frontend/visual-dist"
html = (source / "index.html").read_text()

def inline_js(match):
    path = source / match.group(1).removeprefix("./").removeprefix("/")
    script = path.read_text().replace("</script", "<\\/script")
    return '<script type="module">' + script + '</script>'

def inline_css(match):
    path = source / match.group(1).removeprefix("./").removeprefix("/")
    return '<style>' + path.read_text() + '</style>'

html = re.sub(r'<script[^>]*src="([^"]+)"[^>]*></script>', inline_js, html)
html = re.sub(r'<link[^>]*href="([^"]+\.css)"[^>]*>', inline_css, html)
html = re.sub(r'<link[^>]*rel="icon"[^>]*>', '', html)
html = re.sub(r'(?m)^[ \t]+$', '', html)
html = html.replace('Бизнес Пульс — персональная аналитика', 'Бизнес Пульс — визуальная демонстрация')
out = ROOT / 'preview'
out.mkdir(exist_ok=True)
(out / 'business-pulse.html').write_text(html)
print(f'Created self-contained visual demo: {len(html.encode()):,} bytes')
