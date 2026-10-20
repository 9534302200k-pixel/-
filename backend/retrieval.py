import json
import re
from datetime import date, timedelta
from .db import rows, company
from .config import settings
from .ingest import classify, TOPICS, TOPIC_NAMES

ROLE_NAMES = {
    "cfo": "Финансовый директор",
    "ceo": "Генеральный директор",
    "treasurer": "Казначей",
}


def payment_context(company_id):
    # No time/currency/supplier claims: only observed directed relationships.
    summary = rows(
        """SELECT COUNT(*) AS records, COUNT(DISTINCT CASE WHEN payer=? THEN beneficiary ELSE payer END) AS counterparties,
      SUM(CASE WHEN p.id IS NULL THEN 1 ELSE 0 END) AS missing_profiles
      FROM payments t LEFT JOIN companies p ON p.id=CASE WHEN t.payer=? THEN t.beneficiary ELSE t.payer END
      WHERE payer=? OR beneficiary=?""",
        (company_id, company_id, company_id, company_id),
    )[0]
    top = rows(
        """SELECT CASE WHEN payer=? THEN beneficiary ELSE payer END AS counterparty, COUNT(*) AS observed_rows
      FROM payments WHERE payer=? OR beneficiary=? GROUP BY counterparty ORDER BY observed_rows DESC LIMIT 5""",
        (company_id, company_id, company_id),
    )
    summary["top"] = top
    summary["limitations"] = (
        "Период и валюта неизвестны. Повторные пары сохранены. Денежная связь не устанавливает роль поставщика, владение или контроль."
    )
    return summary


def profile(company_id):
    p = company(company_id)
    p["payments"] = payment_context(company_id)
    p["linked_companies"] = rows(
        """SELECT DISTINCT b.company_id FROM person_links a JOIN person_links b ON a.person_id=b.person_id
       WHERE a.company_id=? AND b.company_id<>? LIMIT 30""",
        (company_id, company_id),
    )
    p["group_members"] = (
        rows(
            "SELECT id,name,sector FROM companies WHERE group_id=? AND id<>? LIMIT 50",
            (p["group_id"], company_id),
        )
        if p["group_id"]
        else []
    )
    p["limitations"] = [
        "Роль пользователя выбрана в интерфейсе и не выводится из связей физлиц.",
        "Доля рынка неизвестна: нет объёма рынка. Групповая выручка не консолидируется.",
        "Наличие кредита не раскрывает его сумму, ставку и дату пересмотра.",
    ]
    if not p["synthetic"] and not settings.revenue_unit_confirmed:
        p["limitations"].append(
            "Единицы выручки не подтверждены: нельзя утверждать соответствие порогу крупного бизнеса в рублях."
        )
    p["limitations"].append(
        "NEGATIVEMARK не используется как показатель неблагонадёжности; CLOSE_CLIENT не расшифровывается без метаданных."
    )
    if p["conflicts"]:
        p["limitations"].append(
            "Конфликтующие поля исключены из интерпретации: "
            + ", ".join(p["conflicts"])
        )
    return p


def relevance(event, p, role):
    topics = (
        json.loads(event["topics"])
        if isinstance(event["topics"], str)
        else event["topics"]
    )
    text = (event["title"] + " " + event["body"]).lower()
    sector = (p.get("sector") or "").lower()
    score, reasons = 10, []
    if "rates" in topics and p.get("credit") == 1:
        score += 42
        reasons.append("В профиле есть кредитный продукт")
    if "trade" in topics and p.get("fts"):
        score += 35
        reasons.append("В профиле есть внешнеторговые связи: " + p["fts"])
    if "demand" in topics and any(
        w in sector for w in ["торгов", "пищ", "рознич", "потреб", "производств"]
    ):
        score += 32
        reasons.append("Спрос связан с основной деятельностью компании")
    words = [
        w
        for w in re.findall(r"[а-яa-z]{5,}", sector)
        if w not in {"производство", "деятельность", "прочая", "прочих"}
    ]
    if any(w[:7] in text for w in words):
        score += 27
        reasons.append("Есть связь с видом деятельности компании")
    if p.get("region") and p["region"].lower() in text:
        score += 15
        reasons.append("Упоминается регион регистрации")
    if role in {"cfo", "treasurer"} and "rates" in topics:
        score += 12 if role == "cfo" else 18
        reasons.append("Приоритет роли: " + ROLE_NAMES[role])
    if role == "ceo" and any(t in topics for t in ["demand", "industry", "trade"]):
        score += 12
        reasons.append("Приоритет роли: операционная деятельность")
    age = max(0, (date.today() - date.fromisoformat(event["published"])).days)
    score += max(0, 8 - age // 7)
    if not reasons:
        reasons = [
            "Общий экономический контекст; прямая связь с профилем не установлена"
        ]
    return min(99, score), reasons


def feed(company_id, role, topic="", bookmarked=False):
    p = company(company_id)
    events = rows(
        "SELECT * FROM events WHERE published<=? ORDER BY published DESC LIMIT 1000",
        (date.today().isoformat(),),
    )
    marks = {
        r["event_id"]
        for r in rows(
            "SELECT event_id FROM bookmarks WHERE company_id=?", (company_id,)
        )
    }
    result = []
    for e in events:
        if not p["synthetic"] and e["source"].startswith("Учебный сценарий"):
            continue
        e["topics"] = json.loads(e["topics"])
        if topic and topic not in e["topics"] or bookmarked and e["id"] not in marks:
            continue
        e["score"], e["reasons"] = relevance(e, p, role)
        e["bookmarked"] = e["id"] in marks
        e["summary"] = e["body"][:280]
        result.append(e)
    return sorted(result, key=lambda e: (e["score"], e["published"]), reverse=True)


def search_bank(query, as_of, limit=6, recent_only=False):
    words = re.findall(r"[а-яa-z0-9]{3,}", query.lower())[:18]
    # Prefix search works with Russian inflections without an external embedding model.
    match = " OR ".join('"' + w[:7] + '"*' for w in dict.fromkeys(words))
    if not match:
        return []
    sql = """SELECT c.id,c.page,c.text,c.ocr,d.id AS document_id,d.title,d.published,d.url,d.synthetic,
       bm25(chunks_fts) AS distance FROM chunks_fts f JOIN chunks c ON c.id=f.chunk_id
       JOIN documents d ON d.id=c.document_id WHERE chunks_fts MATCH ? AND d.published IS NOT NULL AND d.published<=?"""
    args = [match, as_of]
    if recent_only:
        sql += " AND d.published>=?"
        args.append((date.fromisoformat(as_of) - timedelta(days=120)).isoformat())
    sql += " ORDER BY d.synthetic ASC, distance, d.published DESC LIMIT ?"
    args.append(limit)
    result = rows(sql, args)
    for r in result:
        r["stale"] = (
            date.fromisoformat(as_of) - date.fromisoformat(r["published"])
        ).days > 120
        r["type"] = "bank"
        r["url"] = f"/api/documents/{r['document_id']}/file#page={r['page']}"
    return result
