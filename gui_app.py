import sys
import threading
import subprocess
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class AgentApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Autonomous Agent")
        self.geometry("900x600")

        self.running = False
        self.process = None

        ctk.CTkLabel(self, text="Task", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(20, 0))
        self.task_entry = ctk.CTkEntry(self, placeholder_text="e.g. go to gmail and check inbox, write updates in notepad", height=40)
        self.task_entry.pack(fill="x", padx=20, pady=10)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20)
        self.run_btn = ctk.CTkButton(btn_frame, text="▶ Run Task", command=self.run_task)
        self.run_btn.pack(side="left", padx=(0, 10))
        self.status_label = ctk.CTkLabel(btn_frame, text="Idle", text_color="gray")
        self.status_label.pack(side="left")

        ctk.CTkLabel(self, text="Agent Log", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(20, 0))
        self.log_box = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=10)
        self.log_box.configure(state="disabled")

    def set_status(self, text, color="gray"):
        self.status_label.configure(text=text, text_color=color)

    def append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def run_task(self):
        if self.running:
            return
        task = self.task_entry.get().strip()
        if not task:
            return

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        self.running = True
        self.run_btn.configure(state="disabled", text="Running...")
        self.set_status("Running...", "orange")

        self.process = subprocess.Popen(
            [sys.executable, "-u", "main.py", task],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        reader = threading.Thread(target=self._read_output, daemon=True)
        reader.start()

    def _read_output(self):
        for line in self.process.stdout:
            self.after(0, self.append_log, line)
        self.process.wait()
        self.after(0, self._on_finished)

    def _on_finished(self):
        if self.process.returncode == 0:
            self.set_status("✅ Done", "green")
        else:
            self.set_status("❌ Failed", "red")
        self.running = False
        self.run_btn.configure(state="normal", text="▶ Run Task")


if __name__ == "__main__":
    app = AgentApp()
    app.mainloop()