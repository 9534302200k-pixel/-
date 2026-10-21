"""Export only generated synthetic fixtures into an isolated browser demo.

Never reads the working case database or exports secrets. No LLM calls.
"""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.config import ROOT, settings
from backend.db import init_db, rows
from backend.seed import seed
from backend.retrieval import feed, profile, ROLE_NAMES
from backend.agent import analyze
from backend.main import status


async def export():
    original_dir, original_key = settings.data_dir, settings.llm_api_key
    with TemporaryDirectory(prefix="pulse-visual-") as directory:
        try:
            settings.data_dir = Path(directory)
            settings.llm_api_key = ""
            init_db()
            seed()
            companies = rows("SELECT * FROM companies ORDER BY revenue DESC")
            assert companies and all(c["synthetic"] == 1 for c in companies)
            assert all(e["synthetic"] == 1 for e in rows("SELECT synthetic FROM events"))
            profiles = {c["id"]: profile(c["id"]) for c in companies}
            feeds, analyses = {}, {}
            for c in companies:
                for role in ROLE_NAMES:
                    key = c["id"] + ":" + role
                    feeds[key] = feed(c["id"], role)
                    for event in feeds[key]:
                        analyses[key + ":" + event["id"]] = await analyze(c["id"], event["id"], role)
            state = status()
            state["visual_demo"] = True
            state["counts"]["runs"] = 0
            output = {"status": state, "companies": companies, "profiles": profiles,
                      "feeds": feeds, "analyses": analyses, "documents": rows("SELECT * FROM documents")}
            destination = ROOT / "frontend/src/visual-data.json"
            destination.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print("Exported synthetic visual demo: 4 companies, 3 roles, 6 events. No original case data.")
        finally:
            settings.data_dir, settings.llm_api_key = original_dir, original_key


if __name__ == "__main__":
    asyncio.run(export())
