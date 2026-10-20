"""Real Chromium end-to-end checks on an isolated live server and seeded corpus."""

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from datetime import date
import httpx
import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    executable = (
        os.getenv("BROWSER_EXECUTABLE")
        or shutil.which("chromium")
        or shutil.which("google-chrome")
    )
    if not executable:
        pytest.skip("Install Chromium or set BROWSER_EXECUTABLE")
    if not (ROOT / "frontend/dist/index.html").exists():
        pytest.skip("Build the frontend before browser tests")
    temp = tmp_path_factory.mktemp("browser")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {
        **os.environ,
        "DATA_DIR": str(temp / "data"),
        "DEMO_MODE": "true",
        "LLM_API_KEY": "",
        "APP_ACCESS_TOKEN": "",
    }
    log = (temp / "server.log").open("w")
    process = subprocess.Popen(
        [
            str(ROOT / ".venv/bin/python"),
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=log,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError((temp / "server.log").read_text())
            try:
                if httpx.get(base + "/api/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Server failed to start")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=executable, headless=True, args=["--no-sandbox"]
            )
            yield base, browser
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()


def test_desktop_business_scenario(live):
    base, browser = live
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base, wait_until="networkidle")
    page.get_by_label("Компания", exact=True).select_option("demo-retail")
    expect(page.locator(".event-card")).to_have_count(6)
    page.get_by_role("button", name="Сохранить событие").first.click()
    page.get_by_role("button", name="Разобрать влияние").first.click()
    expect(
        page.get_by_role("heading", name="Почему это важно для вашей компании")
    ).to_be_visible()
    page.get_by_role("button", name="Действия агента", exact=True).click()
    expect(page.locator(".trace-step").first).to_be_visible()
    assert page.locator(".trace-step").count() >= 5
    page.get_by_role("button", name="Источники", exact=True).click()
    expect(page.locator(".evidence-card").first).to_be_visible()
    page.get_by_role("button", name="Влияние на бизнес").click()
    page.get_by_label("Уточняющий вопрос").fill(
        "Какие условия договора нужно проверить?"
    )
    page.get_by_role("button", name="Отправить вопрос").click()
    expect(page.locator(".chat-answer")).to_contain_text("Ответ по правилам")
    page.get_by_role("button", name="Полезно", exact=True).click()
    expect(page.get_by_role("button", name="Полезно", exact=True)).to_be_disabled()
    page.get_by_role("button", name="Закрыть анализ").click()
    page.get_by_label("Роль", exact=True).select_option("treasurer")
    expect(page.locator(".event-card")).to_have_count(6)
    page.get_by_role("button", name="Сохранённое", exact=True).click()
    expect(page.locator(".event-card")).to_have_count(1)
    assert not errors
    page.close()


def test_new_event_and_scenario(live):
    base, browser = live
    page = browser.new_page(viewport={"width": 1280, "height": 1000})
    page.goto(base, wait_until="networkidle")
    page.get_by_role("button", name="Добавить новость", exact=True).click()
    page.get_by_text("Добавить тестовый текст для проверки", exact=True).click()
    page.get_by_label("Заголовок", exact=True).fill(
        "Новая тестовая новость об экспортных поставках"
    )
    page.get_by_label("Дата", exact=True).fill(date.today().isoformat())
    page.get_by_label("Текст", exact=True).fill(
        "Новый учебный сценарий: меняются условия экспорта и импорта, логистики и поставок из Китая. Событие ранее не использовалось в подготовленной ленте. "
        * 2
    )
    page.get_by_role("button", name="Добавить тестовый материал", exact=True).click()
    expect(
        page.get_by_role(
            "heading", name="Новая тестовая новость об экспортных поставках"
        )
    ).to_be_visible()
    page.get_by_role(
        "heading", name="Новая тестовая новость об экспортных поставках"
    ).click()
    expect(
        page.get_by_role("heading", name="Почему это важно для вашей компании")
    ).to_be_visible()
    page.get_by_role(
        "button", name="Проверить сценарий финансирования", exact=False
    ).click()
    page.get_by_role("button", name="Рассчитать", exact=True).click()
    expect(page.locator(".scenario-result h2")).to_contain_text("1 000 000")
    page.close()


def test_mobile_navigation_and_layout(live):
    base, browser = live
    page = browser.new_page(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    page.goto(base, wait_until="networkidle")
    expect(page.locator(".event-card").first).to_be_visible()
    assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
    assert page.locator(".sidebar").bounding_box()["x"] <= -240
    page.get_by_role("button", name="Открыть меню", exact=True).click()
    page.get_by_role("button", name="Источники и данные", exact=True).click()
    expect(
        page.get_by_role("heading", name="Источники и данные", exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="Импорт данных", exact=True).click()
    expect(page.get_by_role("heading", name="Импорт исходных данных")).to_be_visible()
    page.get_by_role("button", name="Закрыть окно", exact=True).click()
    page.get_by_role("button", name="Открыть меню", exact=True).click()
    page.get_by_role("button", name="Настройки", exact=True).click()
    expect(page.get_by_role("heading", name="Настройки продукта")).to_be_visible()
    assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
    page.close()
