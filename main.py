import time
from agent.browser_actions import BrowserController
from agent.os_actions import OSController
from agent.brain import Brain

MAX_STEPS = 12


def run_browser_task(task: str, brain: Brain):
    bot = BrowserController(headless=False)
    bot.start()
    bot.navigate("about:blank")
    history = []

    for step in range(MAX_STEPS):
        state = bot.get_page_state()
        decision = brain.decide_next_action(task, state, history)
        print(f"\n[Step {step + 1}] Action: {decision}")

        action = decision.get("action")
        target = decision.get("target")
        value = decision.get("value")

        try:
            if action == "navigate":
                bot.navigate(target)
            elif action == "click":
                bot.click(target)
            elif action == "type":
                bot.type_text(target, value)
            elif action == "scroll":
                bot.scroll()
            elif action == "wait":
                time.sleep(2)
            elif action == "done":
                print("\n✅ Task marked done by agent.")
                break
            else:
                print(f"⚠️ Unknown action: {action}")
        except Exception as e:
            print(f"⚠️ Action failed: {e}")

        history.append(decision)
        time.sleep(1)

    time.sleep(3)
    bot.stop()


def run_os_task(task: str, brain: Brain):
    os_bot = OSController()
    history = []
    current_state = {"info": "starting OS task"}

    for step in range(MAX_STEPS):
        decision = brain.decide_next_action(task, current_state, history)
        print(f"\n[Step {step + 1}] Action: {decision}")

        action = decision.get("action")
        target = decision.get("target")

        try:
            if action == "open_file":
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
                current_state = {"info": f"launched app {target}"}
            elif action == "done":
                print("\n✅ Task marked done by agent.")
                break
            else:
                print(f"⚠️ Unknown action: {action}")
        except Exception as e:
            print(f"⚠️ Action failed: {e}")
            current_state = {"error": str(e)}

        history.append(decision)
        time.sleep(1)


def main():
    brain = Brain()
    task = input("Enter your task: ").strip()
    if not task:
        print("No task entered. Exiting.")
        return

    task_type = brain.classify_task(task)
    print(f"\n🧠 Classified as: {task_type.upper()} task\n")

    if task_type == "browser":
        run_browser_task(task, brain)
    else:
        run_os_task(task, brain)


if __name__ == "__main__":
    main()