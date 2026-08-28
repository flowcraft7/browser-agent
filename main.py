import os
import sys
import time
from dotenv import load_dotenv
from agent.browser_actions import BrowserController
from agent.os_actions import OSController
from agent.brain import Brain

load_dotenv()

MAX_STEPS = 18


def substitute_secrets(value: str) -> str:
    if not value:
        return value
    value = value.replace("{{UNI_USERNAME}}", os.getenv("UNI_USERNAME", ""))
    value = value.replace("{{UNI_PASSWORD}}", os.getenv("UNI_PASSWORD", ""))
    return value


def run_task(task: str, brain: Brain):
    """Unified agent loop — handles browser AND OS actions within the SAME task."""
    bot = BrowserController(headless=False)
    os_bot = OSController()
    browser_started = False
    task_completed_normally = False

    history = []
    current_state = {"info": "task starting — no browser or app opened yet"}

    for step in range(MAX_STEPS):
        decision = brain.decide_next_action(task, current_state, history)
        print(f"\n[Step {step + 1}] Action: {decision}")

        action = decision.get("action")
        target = decision.get("target")
        value = decision.get("value")

        try:
            if action in ("navigate", "click", "type", "scroll", "wait", "extract_text"):
                if not browser_started:
                    bot.start()
                    bot.navigate("about:blank")
                    browser_started = True

                if action == "navigate":
                    bot.navigate(target)
                elif action == "click":
                    bot.click(target)
                elif action == "type":
                    bot.type_text(target, substitute_secrets(value))
                elif action == "scroll":
                    bot.scroll()
                elif action == "wait":
                    time.sleep(2)
                elif action == "extract_text":
                    text = bot.get_page_text()
                    current_state = bot.get_page_state()
                    current_state["extracted_text"] = text
                    history.append(decision)
                    time.sleep(1)
                    continue

                current_state = bot.get_page_state()

            elif action == "open_file":
                os_bot.open_file(target)
                current_state = {"info": f"opened file {target}"}
            elif action == "open_folder":
                os_bot.open_folder(target)
                current_state = {"info": f"opened folder {target}"}
            elif action == "list_folder":
                items = os_bot.list_folder(target)
                current_state = {"folder_contents": items}
            elif action == "launch_app":
                os_bot.launch_app(target)
                current_state = {"info": f"launched and focused app: {target}"}
            elif action == "write_content":
                print("  📝 Generating content (paced to avoid rate limits)...")
                content = brain.generate_long_document(topic=target, instructions=value or "")
                os_bot.type_text_in_active_window(content)
                current_state = {"info": "content generated and typed into active window"}
            elif action == "type_text":
                os_bot.type_text_in_active_window(substitute_secrets(target))
                current_state = {"info": f"typed text starting with: {target[:40]}"}

            elif action == "done":
                print("\n✅ Task marked done by agent.")
                task_completed_normally = True
                break
            else:
                print(f"⚠️ Unknown action: {action}")

        except Exception as e:
            print(f"⚠️ Action failed: {e}")
            current_state = {"error": str(e)}

        history.append(decision)
        time.sleep(1)

    if browser_started and not task_completed_normally:
        print("⚠️ Max steps reached without completion — closing browser connection.")
        time.sleep(2)
        bot.stop()
    elif browser_started:
        print("Browser left open so you can see the result.")


def main():
    brain = Brain()
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:]).strip()
    else:
        task = input("Enter your task: ").strip()

    if not task:
        print("No task entered. Exiting.")
        return
    run_task(task, brain)


if __name__ == "__main__":
    main()