"""Streaming, repeatable import. Source records and ambiguity are retained."""

import csv
import hashlib
import io
import json
import math
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
import fitz
from .config import settings
from .db import db, dumps, now, rows

TOPICS = {
    "rates": ("ставк", "кредит", "инфляц", "денежно-кредит", "рефинанс"),
    "trade": (
        "экспорт",
        "импорт",
        "тамож",
        "логист",
        "торговл",
        "валют",
        "санкц",
        "постав",
    ),
    "demand": ("спрос", "потреблен", "рознич", "доход", "продаж"),
    "industry": ("промышлен", "сталь", "металл", "нефт", "золот", "производств"),
    "regulation": ("закон", "налог", "регулир", "пошлин", "норматив"),
}
TOPIC_NAMES = {
    "rates": "Финансирование",
    "trade": "Внешняя торговля",
    "demand": "Спрос",
    "industry": "Промышленность",
    "regulation": "Регулирование",
    "economy": "Экономика",
}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def classify(text):
    lower = text.lower()
    return [k for k, words in TOPICS.items() if any(w in lower for w in words)] or [
        "economy"
    ]


def number(value):
    try:
        result = float(
            str(value).replace("\u00a0", "").replace(" ", "").replace(",", ".")
        )
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(16000)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("CSV не содержит заголовков")
        for row in reader:
            yield {
                k.strip(): v.strip() if isinstance(v, str) else v
                for k, v in row.items()
                if k
            }


def import_csv(path, kind):
    count = 0
    with open(path, "rb") as source:
        file_hash = hashlib.file_digest(source, "sha256").hexdigest()
    with db() as c:
        for index, r in enumerate(csv_rows(path)):
            raw = dumps(r)
            fp = digest(raw if kind == "companies" else f"{file_hash}:{index}:{raw}")
            if kind == "companies":
                uid = r.get("SYNTHETIC_U")
                if not uid:
                    raise ValueError("Нужен столбец SYNTHETIC_U")
                cur = c.execute(
                    "INSERT OR IGNORE INTO company_records(company_id,raw,fingerprint) VALUES(?,?,?)",
                    (uid, raw, fp),
                )
                if cur.rowcount == 0:
                    continue
                variants = [
                    json.loads(x[0])
                    for x in c.execute(
                        "SELECT raw FROM company_records WHERE company_id=?", (uid,)
                    )
                ]
                keys = set().union(*(v.keys() for v in variants))
                conflicts = [
                    k
                    for k in sorted(keys)
                    if len({str(v.get(k, "")) for v in variants}) > 1
                ]
                # Conflicting fields stay unknown; never take an arbitrary first/last record.
                merged = {
                    k: variants[0].get(k) if k not in conflicts else None for k in keys
                }
                rev = number(merged.get("REVENUE_COMPANY"))
                credit = number(merged.get("CL_PRODUCT_LOA_MARK"))
                c.execute(
                    """INSERT INTO companies(id,name,sector,region,revenue,credit,fts,group_id,raw,conflicts)
                  VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,sector=excluded.sector,
                  region=excluded.region,revenue=excluded.revenue,credit=excluded.credit,fts=excluded.fts,group_id=excluded.group_id,
                  raw=excluded.raw,conflicts=excluded.conflicts""",
                    (
                        uid,
                        f"Компания {uid}",
                        merged.get("MAINOKVED_NAME"),
                        merged.get("REGION"),
                        rev * settings.revenue_multiplier if rev is not None else None,
                        int(credit) if credit in (0, 1) else None,
                        merged.get("FTS_COUNTRY_NAME"),
                        merged.get("GROUP_ID"),
                        dumps(merged),
                        dumps(conflicts),
                    ),
                )
            elif kind == "payments":
                if not r.get("PAYER") or not r.get("BENEFICIARY"):
                    raise ValueError("Нужны столбцы PAYER и BENEFICIARY")
                cur = c.execute(
                    "INSERT OR IGNORE INTO payments(payer,beneficiary,amount,count,fingerprint,raw) VALUES(?,?,?,?,?,?)",
                    (
                        r["PAYER"],
                        r["BENEFICIARY"],
                        number(r.get("PAY_AMT")),
                        number(r.get("PAY_CNT")),
                        fp,
                        raw,
                    ),
                )
            elif kind == "links":
                if not r.get("SYNTHETIC_F") or not r.get("SYNTHETIC_U"):
                    raise ValueError("Нужны SYNTHETIC_F и SYNTHETIC_U")
                cur = c.execute(
                    "INSERT OR IGNORE INTO person_links(person_id,company_id,fingerprint,raw) VALUES(?,?,?,?)",
                    (r["SYNTHETIC_F"], r["SYNTHETIC_U"], fp, raw),
                )
            else:
                raise ValueError("Неизвестный тип CSV")
            count += max(0, cur.rowcount)
        c.execute(
            "INSERT OR REPLACE INTO metadata VALUES(?,?)", ("data_updated", now())
        )
    return {"imported": count, "kind": kind}


def tokens(text):
    return set(re.findall(r"[а-яa-z0-9]{3,}", text.lower()))


def add_event(title, body, url, source, published, synthetic=False):
    published = date.fromisoformat(published[:10]).isoformat()
    if published > date.today().isoformat():
        raise ValueError("Дата новости находится в будущем")
    title, body = title.strip(), body.strip()
    eid = digest(title.lower() + "\n" + body)[:24]
    with db() as c:
        existing = c.execute("SELECT id FROM events WHERE id=?", (eid,)).fetchone()
        if existing:
            return existing["id"]
        new_tokens = tokens(title + " " + body)
        for r in c.execute(
            "SELECT * FROM events WHERE published=? AND synthetic=? ORDER BY fetched DESC LIMIT 200",
            (published, int(synthetic)),
        ):
            old_tokens = tokens(r["title"] + " " + r["body"])
            similarity = len(old_tokens & new_tokens) / max(
                1, len(old_tokens | new_tokens)
            )
            if similarity > 0.82:
                aliases = json.loads(r["aliases"])
                if url != r["url"] and url not in aliases:
                    aliases.append(url)
                    c.execute(
                        "UPDATE events SET duplicate_count=duplicate_count+1,aliases=? WHERE id=?",
                        (dumps(aliases), r["id"]),
                    )
                return r["id"]
        c.execute(
            "INSERT INTO events(id,title,body,url,source,published,fetched,topics,synthetic) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                eid,
                title,
                body,
                url,
                source,
                published,
                now(),
                dumps(classify(title + " " + body)),
                int(synthetic),
            ),
        )
    return eid


def import_pdf(path, title, published=None, url="", synthetic=False):
    content = Path(path).read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    doc_id = sha[:24]
    if rows("SELECT id FROM documents WHERE id=?", (doc_id,)):
        return {"id": doc_id, "already_imported": True}
    if published:
        published = date.fromisoformat(published).isoformat()
        if published > date.today().isoformat():
            raise ValueError("Документ датирован будущим")
    pages = []
    with fitz.open(stream=content, filetype="pdf") as document:
        if len(document) > 300:
            raise ValueError("Максимум 300 страниц в одном документе")
        for i, page in enumerate(document):
            text = page.get_text().strip()
            ocr = len(re.sub(r"\W", "", text)) < 80
            if ocr:
                with tempfile.TemporaryDirectory() as temp:
                    image = Path(temp) / "page.png"
                    page.get_pixmap(dpi=180).save(str(image))
                    command = ["tesseract", str(image), "stdout", "-l", "rus+eng"]
                    tessdata = settings.tessdata_prefix
                    if not tessdata and (settings.data_dir / "tessdata").is_dir():
                        tessdata = str(settings.data_dir / "tessdata")
                    if tessdata:
                        command += ["--tessdata-dir", tessdata]
                    result = subprocess.run(
                        command, capture_output=True, text=True, timeout=90
                    )
                    if result.returncode:
                        raise ValueError(
                            "OCR недоступен: установите Tesseract и языки rus+eng"
                        )
                    text = result.stdout.strip()
            if not text:
                raise ValueError(f"На странице {i + 1} не найден текст после OCR")
            # Overlapping chunks preserve page-level citations.
            for offset in range(0, len(text), 1400):
                pages.append(
                    (
                        f"{doc_id}:{i + 1}:{offset}",
                        i + 1,
                        text[offset : offset + 1700],
                        int(ocr),
                    )
                )
    dest = settings.data_dir / "documents" / f"{doc_id}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    with db() as c:
        c.execute(
            "INSERT INTO documents VALUES(?,?,?,?,?,?,?)",
            (doc_id, title, published, url, dest.name, int(synthetic), sha),
        )
        for cid, page, text, ocr in pages:
            c.execute(
                "INSERT INTO chunks VALUES(?,?,?,?,?)", (cid, doc_id, page, text, ocr)
            )
            c.execute("INSERT INTO chunks_fts VALUES(?,?)", (cid, text))
    return {
        "id": doc_id,
        "pages": len({p[1] for p in pages}),
        "chunks": len(pages),
        "ocr_pages": len({p[1] for p in pages if p[3]}),
    }
