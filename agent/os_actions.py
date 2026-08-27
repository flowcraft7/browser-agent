import os
import time
import subprocess
import platform
from pathlib import Path
from typing import List, Optional
from pywinauto.keyboard import send_keys
from pywinauto import Desktop


class OSController:
    """Handles local file, folder, application, and typing automation — generic, not tied to any specific app."""

    def __init__(self):
        self.os_name = platform.system()
        self._tracked_handle: Optional[int] = None

    def _resolve_path(self, raw_path: str) -> Path:
        path_str = raw_path.strip()

        shell_shortcuts = {
            "shell:downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
            "shell:desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
            "shell:documents": os.path.join(os.path.expanduser("~"), "Documents"),
            "shell:mydocuments": os.path.join(os.path.expanduser("~"), "Documents"),
            "shell:pictures": os.path.join(os.path.expanduser("~"), "Pictures"),
        }
        lowered = path_str.lower()
        if lowered in shell_shortcuts:
            path_str = shell_shortcuts[lowered]
        elif lowered == "downloads":
            path_str = os.path.join(os.path.expanduser("~"), "Downloads")
        elif lowered == "desktop":
            path_str = os.path.join(os.path.expanduser("~"), "Desktop")
        elif lowered == "documents":
            path_str = os.path.join(os.path.expanduser("~"), "Documents")

        path_str = os.path.expandvars(path_str)
        path_str = os.path.expanduser(path_str)
        return Path(path_str).resolve()

    # ---------- Generic window tracking (works regardless of which process owns the window) ----------

    def _snapshot_windows(self) -> dict:
        """Return {handle: title} for all current top-level windows with a visible title."""
        snapshot = {}
        try:
            for w in Desktop(backend="uia").windows():
                try:
                    title = w.window_text()
                    if title:
                        snapshot[w.handle] = title
                except Exception:
                    continue
        except Exception:
            pass
        return snapshot

    def _find_and_focus_new_window(self, before: dict, retries: int = 4, wait_between: float = 1.0) -> bool:
        """Diff window snapshots to find a NEW window that appeared, then focus it. Retries a few times
        since some apps take a moment to actually show their window."""
        for _ in range(retries):
            time.sleep(wait_between)
            after = self._snapshot_windows()
            new_handles = [h for h in after if h not in before]
            if new_handles:
                handle = new_handles[-1]  # most recently added
                try:
                    win = Desktop(backend="uia").window(handle=handle)
                    win.wait("visible ready", timeout=10)
                    win.set_focus()
                    self._tracked_handle = handle
                    print(f"  🪟 Focused new window: '{after[handle]}'")
                    return True
                except Exception as e:
                    print(f"⚠️ Found new window but couldn't focus it: {e}")
                    return False
        print("⚠️ No new window detected after launch — typing may go to the wrong place.")
        return False

    def _focus_tracked_window(self):
        """Re-focus the last tracked window right before typing (safety net)."""
        if self._tracked_handle:
            try:
                win = Desktop(backend="uia").window(handle=self._tracked_handle)
                win.set_focus()
                time.sleep(0.3)
            except Exception as e:
                print(f"⚠️ Could not re-focus tracked window: {e}")

    def focus_window_by_title(self, title_substring: str) -> bool:
        """Fallback: find any open window whose title contains the given text and focus it."""
        try:
            win = Desktop(backend="uia").window(title_re=f".*{title_substring}.*")
            win.wait("visible ready", timeout=10)
            win.set_focus()
            self._tracked_handle = win.handle
            time.sleep(0.3)
            print(f"  🪟 Focused window matching '{title_substring}'.")
            return True
        except Exception as e:
            print(f"⚠️ Could not find/focus window '{title_substring}': {e}")
            return False

    # ---------- Generic app launching ----------

    def launch_app(self, app_command: str, wait_seconds: float = 2.0):
        """Launch ANY application (notepad, winword, excel, chrome, a .exe path, etc.)
        and reliably focus its window using a before/after window diff — works even
        when the app hands off to a different owning process (common on Windows 11)."""
        if self.os_name != "Windows":
            raise NotImplementedError("Focus-tracked launch_app is Windows-only for now.")

        cmd = app_command.strip()
        if cmd.lower() in ("word",):
            cmd = "winword /n"
        elif cmd.lower() in ("winword",):
            cmd = "winword /n"

        before = self._snapshot_windows()
        subprocess.Popen(f"start {cmd}", shell=True)
        time.sleep(wait_seconds)
        self._find_and_focus_new_window(before)

    # ---------- File / folder operations ----------

    def open_file(self, file_path: str):
        """Open a file with its default associated app, then focus whatever window appears."""
        path = self._resolve_path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if self.os_name == "Windows":
            before = self._snapshot_windows()
            os.startfile(str(path))
            self._find_and_focus_new_window(before)
        elif self.os_name == "Darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])

    def open_folder(self, folder_path: str):
        path = self._resolve_path(folder_path)
        if not path.exists():
            raise FileNotFoundError(f"Folder not found: {path}")
        if self.os_name == "Windows":
            os.startfile(str(path))
        elif self.os_name == "Darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])

    def list_folder(self, folder_path: str, max_items: int = 25) -> List[dict]:
        path = self._resolve_path(folder_path)
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Not a folder: {path}")

        all_entries = list(path.iterdir())
        items = []
        for entry in all_entries[:max_items]:
            items.append({"name": entry.name, "type": "folder" if entry.is_dir() else "file"})
        if len(all_entries) > max_items:
            items.append({"note": f"...and {len(all_entries) - max_items} more items (truncated)"})
        return items

    def create_folder(self, folder_path: str):
        self._resolve_path(folder_path).mkdir(parents=True, exist_ok=True)

    def move_file(self, src: str, dest: str):
        self._resolve_path(src).rename(self._resolve_path(dest))

    def delete_file(self, file_path: str):
        self._resolve_path(file_path).unlink(missing_ok=True)

    def read_text_file(self, file_path: str) -> str:
        path = self._resolve_path(file_path)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    # ---------- Generic typing (works in whatever app is focused) ----------

    def type_text_in_active_window(self, text: str, chunk_size: int = 40, delay: float = 0.03):
        """Type text into the active window. Re-focuses the tracked window first as a safety net."""
        self._focus_tracked_window()

        special = {
            '{': '{{}', '}': '{}}', '+': '{+}', '^': '{^}',
            '%': '{%}', '~': '{~}', '(': '{(}', ')': '{)}'
        }
        safe_text = text
        for char, escaped in special.items():
            safe_text = safe_text.replace(char, escaped)

        for i in range(0, len(safe_text), chunk_size):
            send_keys(safe_text[i:i + chunk_size], pause=delay, with_spaces=True, with_newlines=True)
            time.sleep(0.25)