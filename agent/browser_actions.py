from playwright.sync_api import sync_playwright, Page, BrowserContext
from playwright_stealth import Stealth
from pathlib import Path
from typing import Optional

PROFILE_DIR = str(Path.home() / "AppData" / "Local" / "AutonomousAgentProfile")


class BrowserController:
    def __init__(self, headless: bool = False):
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.headless = headless

    def start(self):
        self.playwright = sync_playwright().start()
        # Persistent profile: logins/cookies (e.g. YouTube sign-in) are remembered across runs.
        # This is a SEPARATE profile from your real Chrome — log in once here, it'll stick.
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=self.headless,
                channel="chrome",
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                ),
            )
        except Exception:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=self.headless,
                viewport={"width": 1366, "height": 768},
            )

        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        Stealth().apply_stealth_sync(self.page)

    def stop(self):
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()

    def navigate(self, url: str):
        if url == "about:blank" or "://" in url:
            pass
        else:
            url = "https://" + url
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(1500)  # let JS-heavy SPAs (YouTube, etc.) finish rendering
        self._dismiss_consent_dialogs()

    def _dismiss_consent_dialogs(self):
        common_texts = [
            "Accept all", "I agree", "Agree", "Accept", "Reject all",
            "Accept cookies", "Allow all", "OK", "Got it"
        ]
        for text in common_texts:
            try:
                btn = self.page.get_by_role("button", name=text, exact=False)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click(timeout=1500)
                    self.page.wait_for_timeout(500)
                    return
            except Exception:
                continue

    def click(self, selector: str):
        self.page.click(selector, timeout=5000)
        self.page.wait_for_timeout(800)

    def type_text(self, selector: str, text: str):
        self.page.fill(selector, text)

    def scroll(self, direction: str = "down", amount: int = 500):
        delta = amount if direction == "down" else -amount
        self.page.mouse.wheel(0, delta)

    def press_key(self, key: str):
        self.page.keyboard.press(key)

    def get_page_state(self, max_elements: int = 40) -> dict:
        """Return simplified, LLM-readable page state.
        Elements linking to actual content (e.g. /watch?v= video pages) are sorted
        to the TOP of the list so they aren't buried behind header/sidebar clutter."""
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
                });

                const mapped = visible.map((el) => {
                    const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 40);
                    const result = {
                        tag: el.tagName.toLowerCase(),
                        text: text,
                        _el: el
                    };
                    if (el.tagName.toLowerCase() === 'a' && el.href) {
                        result.href = el.href;
                    }
                    return result;
                });

                const isContentLink = (r) => r.href && (
                    r.href.includes('/watch?v=') ||
                    r.href.includes('/shorts/') ||
                    r.href.includes('/status/') ||
                    r.href.includes('/posts/')
                );

                mapped.sort((a, b) => (isContentLink(b) ? 1 : 0) - (isContentLink(a) ? 1 : 0));

                const seen = new Set();
                const deduped = [];
                for (const item of mapped) {
                    const key = item.href || (item.tag + ':' + item.text);
                    if (seen.has(key)) continue;
                    seen.add(key);
                    deduped.push(item);
                    if (deduped.length >= maxEls) break;
                }

                return deduped.map((item, i) => {
                    item._el.setAttribute('data-agent-id', i);
                    const out = {
                        index: i,
                        tag: item.tag,
                        text: item.text,
                        selector: `[data-agent-id="${i}"]`
                    };
                    if (item.href) out.href = item.href;
                    return out;
                });
            }""",
            max_elements
        )
        return {"title": title, "url": url, "elements": elements}

    def screenshot(self, path: str = "screenshot.png"):
        self.page.screenshot(path=path)