import os
import time
import subprocess
import platform
from pathlib import Path
from typing import List, Optional
from pywinauto.keyboard import send_keys
from pywinauto import Desktop
import win32gui
import win32con
import win32api
import win32process


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

    # ---------- Robust foreground focus (works even from a background/spawned process) ----------

    def _force_foreground(self, hwnd: int) -> bool:
        """Standard robust Windows technique: temporarily attach our thread's input
        to the target window's thread, which lets SetForegroundWindow succeed even
        from a background/non-interactive process."""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
            current_thread_id = win32api.GetCurrentThreadId()

            attached = False
            if target_thread_id != current_thread_id:
                attached = win32process.AttachThreadInput(current_thread_id, target_thread_id, True)

            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)

            if attached:
                win32process.AttachThreadInput(current_thread_id, target_thread_id, False)

            time.sleep(0.3)
        except Exception as e:
            print(f"⚠️ Force-foreground failed: {e}")
            return False

        current = win32gui.GetForegroundWindow()
        success = current == hwnd
        if not success:
            print("⚠️ Focus verification failed (window may not have gained real focus).")
        return success

    def _snapshot_windows(self) -> dict:
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

    def _find_and_focus_new_window(self, before: dict, retries: int = 5, wait_between: float = 1.0) -> bool:
        for _ in range(retries):
            time.sleep(wait_between)
            after = self._snapshot_windows()
            new_handles = [h for h in after if h not in before]
            if new_handles:
                handle = new_handles[-1]
                self._tracked_handle = handle
                ok = self._force_foreground(handle)
                print(f"  🪟 {'Focused' if ok else 'Attempted focus on'} new window: '{after[handle]}'")
                return ok
        print("⚠️ No new window detected after launch — typing may go to the wrong place.")
        return False

    def _focus_tracked_window(self):
        if self._tracked_handle:
            ok = self._force_foreground(self._tracked_handle)
            if not ok:
                print("⚠️ Could not confirm re-focus before typing — text may not land correctly.")

    def focus_window_by_title(self, title_substring: str) -> bool:
        try:
            win = Desktop(backend="uia").window(title_re=f".*{title_substring}.*")
            win.wait("visible ready", timeout=10)
            self._tracked_handle = win.handle
            ok = self._force_foreground(win.handle)
            print(f"  🪟 {'Focused' if ok else 'Attempted focus on'} window matching '{title_substring}'.")
            return ok
        except Exception as e:
            print(f"⚠️ Could not find/focus window '{title_substring}': {e}")
            return False

    # ---------- Generic app launching ----------

    def launch_app(self, app_command: str, wait_seconds: float = 2.0):
        if self.os_name != "Windows":
            raise NotImplementedError("Focus-tracked launch_app is Windows-only for now.")

        cmd = app_command.strip()
        if cmd.lower() in ("word", "winword"):
            cmd = "winword /n"
        elif cmd.lower() in ("excel",):
            cmd = "excel /n"

        before = self._snapshot_windows()
        subprocess.Popen(f"start {cmd}", shell=True)
        time.sleep(wait_seconds)
        self._find_and_focus_new_window(before)

    # ---------- File / folder operations ----------

    def open_file(self, file_path: str):
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

    # ---------- Generic typing ----------

    def type_text_in_active_window(self, text: str, chunk_size: int = 40, delay: float = 0.03):
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