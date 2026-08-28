import os
import time
import socket
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from typing import Optional

DEBUG_PORT = 9222


def _is_port_open(port: int, host: str = "localhost") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _find_chrome_exe() -> str:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("Could not find chrome.exe in standard install locations.")


def _launch_real_chrome_with_debug():
    """Close any running Chrome and relaunch it (with YOUR real profile) with the
    debug port open, so Playwright can attach to it directly instead of spinning
    up a separate automated browser. This preserves all your real logins."""
    chrome_path = _find_chrome_exe()
    user_data_dir = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data")

    print("  Restarting your Chrome with debug access (your open tabs will close, logins are kept)...")
    subprocess.run("taskkill /F /IM chrome.exe", shell=True, capture_output=True)
    time.sleep(3)

    subprocess.Popen([
        chrome_path,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={user_data_dir}",
    ])

    for i in range(60):
        if _is_port_open(DEBUG_PORT):
            time.sleep(1.5)
            return
        time.sleep(0.5)
    raise RuntimeError("Chrome did not open a debuggable connection in time (waited 30s).")


class BrowserController:
    def __init__(self, headless: bool = False):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self):
        self.playwright = sync_playwright().start()
        try:
            if not _is_port_open(DEBUG_PORT):
                _launch_real_chrome_with_debug()

            self.browser = self.playwright.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            self.page = self.context.new_page()
        except Exception:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
            raise

    def stop(self):
        """Detach from the real Chrome without closing it — the user's browser
        stays open so they can see the result."""
        if self.playwright:
            self.playwright.stop()

    def navigate(self, url: str):
        if url == "about:blank" or "://" in url:
            pass
        else:
            url = "https://" + url
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(1500)
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
                    const result = { tag: el.tagName.toLowerCase(), text: text, _el: el };
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
                    const out = { index: i, tag: item.tag, text: item.text, selector: `[data-agent-id="${i}"]` };
                    if (item.href) out.href = item.href;
                    return out;
                });
            }""",
            max_elements
        )
        return {"title": title, "url": url, "elements": elements}

    def get_page_text(self, max_chars: int = 800) -> str:
        try:
            text = self.page.inner_text("body")
        except Exception:
            text = ""
        text = " ".join(text.split())
        return text[:max_chars]

    def is_started(self) -> bool:
        return self.page is not None

    def screenshot(self, path: str = "screenshot.png"):
        self.page.screenshot(path=path)