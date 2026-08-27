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
        if not url.startswith("http"):
            url = "https://" + url
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

    def get_page_state(self, max_elements: int = 20) -> dict:
        """Return simplified, LLM-readable page state with UNIQUE, RELIABLE selectors."""
        title = self.page.title()
        url = self.page.url

        elements = self.page.evaluate(
            """(maxEls) => {
                const nodes = Array.from(document.querySelectorAll(
                    'a, button, input, textarea, select, [role=button]'
                ));
                const visible = nodes.filter(el => {
                    const r = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return r.width > 0 && r.height > 0
                        && style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && el.type !== 'hidden';
                }).slice(0, maxEls);

                return visible.map((el, i) => {
                    el.setAttribute('data-agent-id', i);
                    const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 40);
                    return {
                        index: i,
                        tag: el.tagName.toLowerCase(),
                        text: text,
                        selector: `[data-agent-id="${i}"]`
                    };
                });
            }""",
            max_elements
        )
        return {"title": title, "url": url, "elements": elements}

    def screenshot(self, path: str = "screenshot.png"):
        self.page.screenshot(path=path)