"""The standalone visual preview must work without a backend or external assets."""
import shutil
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect


@pytest.mark.browser
def test_visual_preview_without_network():
    executable = shutil.which("chromium") or shutil.which("google-chrome")
    html = Path(__file__).resolve().parents[1] / "preview/business-pulse.html"
    if not executable or not html.exists():
        pytest.skip("Chromium and packaged visual preview are required")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=executable, headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors, requests = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append(request.url))
        page.set_content(html.read_text(), wait_until="networkidle")
        expect(page.get_by_text("Визуальная демонстрация.", exact=True)).to_be_visible()
        expect(page.locator(".event-card")).to_have_count(6)
        page.get_by_label("Компания", exact=True).select_option("demo-retail")
        page.get_by_label("Роль", exact=True).select_option("treasurer")
        page.get_by_role("button", name="Разобрать влияние").first.click()
        expect(page.get_by_role("heading", name="Почему это важно для вашей компании")).to_be_visible()
        page.get_by_role("button", name="Действия агента", exact=True).click()
        expect(page.locator(".trace-step").first).to_be_visible()
        page.get_by_role("button", name="Закрыть анализ").click()
        page.get_by_role("button", name="Сохранить событие").first.click()
        page.get_by_role("button", name="Сохранённое", exact=True).click()
        expect(page.locator(".event-card")).to_have_count(1)
        assert not errors
        assert not requests
        browser.close()
