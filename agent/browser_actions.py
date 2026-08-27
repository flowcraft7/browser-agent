from playwright.sync_api import sync_playwright, Page, Browser
from typing import Optional


class BrowserController:
    def __init__(self, headless: bool = False):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.headless = headless

    def start(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.page = self.browser.new_page()

    def stop(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def navigate(self, url: str):
        self.page.goto(url, wait_until="domcontentloaded")

    def click(self, selector: str):
        self.page.click(selector, timeout=5000)

    def type_text(self, selector: str, text: str):
        self.page.fill(selector, text)

    def scroll(self, direction: str = "down", amount: int = 500):
        delta = amount if direction == "down" else -amount
        self.page.mouse.wheel(0, delta)

    def press_key(self, key: str):
        self.page.keyboard.press(key)

    def get_page_state(self) -> dict:
        """Return simplified page info the LLM can reason about."""
        title = self.page.title()
        url = self.page.url
        # Simplified accessibility snapshot (interactive elements only)
        elements = self.page.eval_on_selector_all(
            "a, button, input, textarea, select, [role=button]",
            """els => els.slice(0, 50).map((el, i) => ({
                index: i,
                tag: el.tagName.toLowerCase(),
                text: (el.innerText || el.value || el.placeholder || '').trim().slice(0, 60),
                selector: el.id ? '#' + el.id : el.tagName.toLowerCase()
            }))"""
        )
        return {"title": title, "url": url, "elements": elements}

    def screenshot(self, path: str = "screenshot.png"):
        self.page.screenshot(path=path)