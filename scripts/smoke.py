"""Functional API check, not a readiness claim for unconfigured LLM/data."""

import argparse
import os
import httpx
from backend.config import settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    token = os.getenv("APP_ACCESS_TOKEN") or settings.app_access_token
    with httpx.Client(
        base_url=args.base_url,
        headers={"Authorization": "Bearer " + token} if token else {},
        timeout=180,
    ) as client:
        r = client.get("/api/health")
        r.raise_for_status()
        assert r.json()["status"] == "ok"
        r = client.get("/api/companies")
        r.raise_for_status()
        companies = r.json()
        if not companies:
            raise SystemExit("Нет компаний. Импортируйте исходные данные.")
        company = companies[0]["id"]
        r = client.get("/api/feed", params={"company_id": company, "role": "cfo"})
        r.raise_for_status()
        feed = r.json()
        if not feed:
            raise SystemExit(
                "Нет событий. Обновите официальные источники или включите DEMO_MODE для теста."
            )
        r = client.post(
            "/api/analyze",
            json={"company_id": company, "event_id": feed[0]["id"], "role": "cfo"},
        )
        r.raise_for_status()
        a = r.json()
        assert a["company_id"] == company and a["trace"] and a["answer"]["explanation"]
        r = client.post(
            "/api/scenario", json={"principal": 100000000, "delta_pp": 1, "months": 12}
        )
        r.raise_for_status()
        assert r.json()["period_delta"] == 1000000
        status = client.get("/api/status").json()
        print(
            "PASS: health, companies, personalized feed, analysis, evidence, trace, calculator"
        )
        print("Analysis mode:", a["mode"], "synthetic:", a["synthetic"])
        print(
            "Real corpus:", status["real_counts"], "model ready:", status["model_ready"]
        )


if __name__ == "__main__":
    main()
