"""Only official public sources. No arbitrary model-selected URLs or redirects."""

import asyncio
import email.utils
import ipaddress
import os
import socket
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
import httpx
from bs4 import BeautifulSoup
from defusedxml import ElementTree
from .db import db, now
from .ingest import add_event

OFFICIAL_HOSTS = {
    "www.cbr.ru",
    "cbr.ru",
    "rosstat.gov.ru",
    "alfabank.ru",
    "minfin.gov.ru",
    "www.minfin.gov.ru",
    "economy.gov.ru",
    "www.economy.gov.ru",
}
FEEDS = [
    {"id": "cbr", "name": "Банк России", "url": "https://www.cbr.ru/rss/RssNews"},
    {
        "id": "cbr-press",
        "name": "Банк России · пресс-релизы",
        "url": "https://www.cbr.ru/rss/RssPress",
    },
]


def validate_url(url):
    u = urlsplit(url)
    if (
        u.scheme != "https"
        or u.hostname not in OFFICIAL_HOSTS
        or u.username
        or u.password
        or u.port not in (None, 443)
    ):
        raise ValueError(
            "Допускаются только HTTPS-адреса официальных источников из списка разрешённых"
        )
    try:
        addresses = socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        # In Codex cloud DNS is handled by the egress proxy. Destinations are
        # still an exact, fixed official-host allowlist, validated on each hop.
        if any(
            os.getenv(k)
            for k in ["HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"]
        ):
            return url
        raise
    for addr in addresses:
        ip = ipaddress.ip_address(addr[4][0])
        if not ip.is_global:
            raise ValueError("Внутренние адреса запрещены")
    return url


async def fetch(url, limit=3_000_000):
    validate_url(url)
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        for _ in range(4):
            async with client.stream(
                "GET",
                url,
                headers={
                    "User-Agent": "BusinessPulse/1.0 (public official news reader)"
                },
            ) as r:
                if r.is_redirect:
                    url = validate_url(urljoin(url, r.headers["location"]))
                    continue
                r.raise_for_status()
                body = bytearray()
                async for chunk in r.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        raise ValueError("Материал превышает допустимый размер")
                return bytes(body), url
    raise ValueError("Слишком много перенаправлений")


def plain(html):
    soup = BeautifulSoup(html, "html.parser")
    for el in soup(["script", "style", "nav", "header", "footer", "form", "aside"]):
        el.decompose()
    return " ".join(soup.stripped_strings)


def parse_feed(content, source):
    root = ElementTree.fromstring(content)
    added = []
    for item in root.findall(".//item")[:50]:
        title = plain(item.findtext("title") or "")
        url = (item.findtext("link") or "").strip()
        body = plain(item.findtext("description") or "")
        raw_date = item.findtext("pubDate")
        if not title or not url or not raw_date:
            continue
        # An official feed cannot introduce an unapproved destination.
        if (
            urlsplit(url).hostname not in OFFICIAL_HOSTS
            or urlsplit(url).scheme != "https"
        ):
            continue
        try:
            published = email.utils.parsedate_to_datetime(raw_date).date().isoformat()
            added.append(add_event(title, body or title, url, source, published))
        except (ValueError, TypeError):
            continue
    return added


async def refresh_sources():
    async def one(feed):
        try:
            content, _ = await fetch(feed["url"])
            ids = parse_feed(content, feed["name"])
            status, detail = (
                ("ok", f"Обработано материалов: {len(ids)}")
                if ids
                else ("empty", "Лента не содержит подходящих датированных записей")
            )
        except Exception as e:
            status, detail = (
                "error",
                f"{type(e).__name__}: источник недоступен; проверьте доступ к {urlsplit(feed['url']).hostname}",
            )
        with db() as c:
            c.execute(
                "INSERT OR REPLACE INTO source_status VALUES(?,?,?,?)",
                (feed["id"], now(), status, detail),
            )
        return {
            "id": feed["id"],
            "name": feed["name"],
            "status": status,
            "detail": detail,
        }

    return await asyncio.gather(*(one(f) for f in FEEDS))


async def import_url(url, published=None):
    content, url = await fetch(url)
    soup = BeautifulSoup(content, "html.parser")
    title = soup.find("h1") or soup.find("title")
    if not title:
        raise ValueError("Не найден заголовок материала")
    if not published:
        meta = soup.find("meta", property="article:published_time") or soup.find(
            "meta", attrs={"name": "date"}
        )
        time = soup.find("time")
        published = (
            meta.get("content", "")[:10]
            if meta
            else (time.get("datetime", "")[:10] if time else None)
        )
    if not published:
        raise ValueError("Источник не сообщает дату: укажите дату публикации вручную")
    article = (
        soup.find("article") or soup.find("main") or soup.find(class_="news") or soup
    )
    body = plain(str(article))
    if len(body) < 80:
        raise ValueError("Слишком мало текста для анализа")
    eid = add_event(
        title.get_text(" ", strip=True),
        body[:30000],
        url,
        urlsplit(url).hostname,
        published,
    )
    return {"id": eid}
