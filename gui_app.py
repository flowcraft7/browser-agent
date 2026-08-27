import threading
import sys
import customtkinter as ctk
from agent.browser_actions import BrowserController
from agent.os_actions import OSController
from agent.brain import Brain
import main as agent_main  # reuse run_browser_task / run_os_task logic

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class TextRedirector:
    """Redirects print() output into the GUI log box, live, line by line."""
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        if text.strip():
            self.widget.after(0, self._append, text)

    def _append(self, text):
        self.widget.configure(state="normal")
        self.widget.insert("end", text)
        self.widget.see("end")
        self.widget.configure(state="disabled")

    def flush(self):
        pass


class AgentApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Autonomous Agent")
        self.geometry("900x600")

        self.brain = Brain()
        self.running = False

        # --- Task input ---
        ctk.CTkLabel(self, text="Task", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(20, 0))
        self.task_entry = ctk.CTkEntry(self, placeholder_text="e.g. search for cats on youtube and play the first video", height=40)
        self.task_entry.pack(fill="x", padx=20, pady=10)

        # --- Buttons ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20)
        self.run_btn = ctk.CTkButton(btn_frame, text="▶ Run Task", command=self.run_task)
        self.run_btn.pack(side="left", padx=(0, 10))
        self.status_label = ctk.CTkLabel(btn_frame, text="Idle", text_color="gray")
        self.status_label.pack(side="left")

        # --- Log output ---
        ctk.CTkLabel(self, text="Agent Log", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(20, 0))
        self.log_box = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=10)
        self.log_box.configure(state="disabled")

        sys.stdout = TextRedirector(self.log_box)

    def set_status(self, text, color="gray"):
        self.status_label.configure(text=text, text_color=color)

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
        self.set_status("Classifying task...", "orange")

        thread = threading.Thread(target=self._execute, args=(task,), daemon=True)
        thread.start()

    def _execute(self, task: str):
        try:
            task_type = self.brain.classify_task(task)
            self.set_status(f"Running as {task_type.upper()} task...", "orange")
            print(f"🧠 Classified as: {task_type.upper()} task\n")

            if task_type == "browser":
                agent_main.run_browser_task(task, self.brain)
            else:
                agent_main.run_os_task(task, self.brain)

            self.set_status("✅ Done", "green")
        except Exception as e:
            print(f"❌ Error: {e}")
            self.set_status("❌ Failed", "red")
        finally:
            self.running = False
            self.run_btn.configure(state="normal", text="▶ Run Task")


if __name__ == "__main__":
    app = AgentApp()
    app.mainloop()