"""Download the exact two public Drive folders linked on pp.15/17 of the case.

Only official contest inputs, no external news aggregators. Errors are not hidden.
Usage: python -m scripts.import_case --download /app/data/case [--import-data]
"""

import argparse
import hashlib
import json
import re
from pathlib import Path
import httpx
from backend.db import init_db, db, dumps
from backend.ingest import import_csv, import_pdf

FOLDERS = {
    "companies": "https://drive.google.com/drive/folders/1Ep8wWoEHTg5Q8kwrLx2j_xFyxGUEVxFq",
    "bank": "https://drive.google.com/drive/folders/15xZTLF1lZ65p6o5xpNA_fRbxjoV-UlG1",
}
FILES = {
    "df_Uid_data_hack.csv": "companies",
    "df_Fid_Uid_link_hack.csv": "links",
    "df_Uid_payment_hack.csv": "payments",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", type=Path, required=True)
    parser.add_argument("--import-data", action="store_true")
    args = parser.parse_args()
    import gdown

    args.download.mkdir(parents=True, exist_ok=True)
    for kind, url in FOLDERS.items():
        target = args.download / kind
        if not (target / ".download-complete").exists():
            result = gdown.download_folder(
                url,
                output=str(target) + "/",
                quiet=False,
                remaining_ok=False,
                use_cookies=False,
                skip_download=True,
            )
            if result is None:
                raise SystemExit(
                    f"Не удалось скачать папку {kind}: проверьте доступ к Google Drive и сетевую политику."
                )
            if not result:
                raise SystemExit(f"Папка {kind} пуста; данные кейса не получены.")
            for item in result:
                destination = Path(item.local_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(destination.suffix + ".part")
                # Public Google Drive download endpoint avoids ephemeral signed
                # CDN addresses, while keeping TLS and the same public file ID.
                with httpx.stream(
                    "GET",
                    "https://drive.usercontent.google.com/download",
                    params={"id": item.id, "export": "download", "confirm": "t"},
                    timeout=90,
                    follow_redirects=True,
                ) as response:
                    response.raise_for_status()
                    if "text/html" in response.headers.get("content-type", ""):
                        raise SystemExit(
                            f"Google Drive не выдал файл {destination.name}: требуется проверка доступа."
                        )
                    with temporary.open("wb") as output:
                        for chunk in response.iter_bytes():
                            output.write(chunk)
                temporary.replace(destination)
                print(
                    f"Получен файл: {destination.name} ({destination.stat().st_size} байт)",
                    flush=True,
                )
            (target / ".download-complete").write_text(
                "Downloaded successfully via verified HTTPS\n"
            )
    manifest = []
    init_db()
    # Optional reviewed metadata: {"original.pdf":{"title":"...","published":"YYYY-MM-DD"}}.
    metadata_file = args.download / "bank-metadata.json"
    metadata = json.loads(metadata_file.read_text()) if metadata_file.exists() else {}
    verified_catalog = (
        Path(__file__).resolve().parents[1] / "docs" / "case-materials.json"
    )
    catalog = (
        json.loads(verified_catalog.read_text()) if verified_catalog.exists() else {}
    )
    for path in sorted(args.download.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".csv", ".pdf"}:
            continue
        with path.open("rb") as f:
            sha = hashlib.file_digest(f, "sha256").hexdigest()
        entry = {
            "file": str(path.relative_to(args.download)),
            "sha256": sha,
            "bytes": path.stat().st_size,
        }
        if args.import_data:
            if path.name in FILES:
                entry["result"] = import_csv(path, FILES[path.name])
            elif path.suffix.lower() == ".pdf":
                meta = metadata.get(path.name, catalog.get(sha, {}))
                entry["result"] = import_pdf(
                    path,
                    meta.get("title", path.stem),
                    meta.get("published"),
                    FOLDERS["bank"],
                )
                if meta.get("published"):
                    # Explicit reviewed metadata also updates previously undated imports.
                    from datetime import date

                    published = date.fromisoformat(meta["published"]).isoformat()
                    if published > date.today().isoformat():
                        raise ValueError("Дата из каталога находится в будущем")
                    with db() as c:
                        c.execute(
                            "UPDATE documents SET title=?,published=? WHERE sha256=?",
                            (meta.get("title", path.stem), published, sha),
                        )
                if not meta.get("published"):
                    entry["warning"] = (
                        "Дата не подтверждена. Добавьте её в интерфейсе библиотеки: документ исключён из текущего поиска."
                    )
        manifest.append(entry)
        print(dumps(entry), flush=True)
    (args.download / "manifest.json").write_text(dumps(manifest), encoding="utf-8")


if __name__ == "__main__":
    main()
