import os
import subprocess
import platform
from pathlib import Path
from typing import List


class OSController:
    """Handles local file, folder, and application automation."""

    def __init__(self):
        self.os_name = platform.system()

    def _resolve_path(self, raw_path: str) -> Path:
        """Expand env vars, ~, and Windows shell: shortcuts, then resolve to absolute path."""
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

    def open_file(self, file_path: str):
        path = self._resolve_path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if self.os_name == "Windows":
            os.startfile(str(path))
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
        """List files/folders inside a directory (capped to avoid huge token payloads)."""
        path = self._resolve_path(folder_path)
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Not a folder: {path}")

        all_entries = list(path.iterdir())
        items = []
        for entry in all_entries[:max_items]:
            items.append({
                "name": entry.name,
                "type": "folder" if entry.is_dir() else "file"
            })
        if len(all_entries) > max_items:
            items.append({"note": f"...and {len(all_entries) - max_items} more items (truncated)"})
        return items

    def launch_app(self, app_name: str):
        if self.os_name == "Windows":
            subprocess.Popen(f"start {app_name}", shell=True)
        elif self.os_name == "Darwin":
            subprocess.run(["open", "-a", app_name])
        else:
            subprocess.Popen([app_name])

    def read_text_file(self, file_path: str) -> str:
        path = self._resolve_path(file_path)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def create_folder(self, folder_path: str):
        self._resolve_path(folder_path).mkdir(parents=True, exist_ok=True)

    def move_file(self, src: str, dest: str):
        self._resolve_path(src).rename(self._resolve_path(dest))

    def delete_file(self, file_path: str):
        self._resolve_path(file_path).unlink(missing_ok=True)