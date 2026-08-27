from agent.browser_actions import BrowserController
import time

if __name__ == "__main__":
    bot = BrowserController(headless=False)
    bot.start()
    bot.navigate("https://www.youtube.com")
    time.sleep(2)
    state = bot.get_page_state()
    print("Title:", state["title"])
    print("URL:", state["url"])
    print(f"Found {len(state['elements'])} interactive elements")
    for el in state["elements"][:10]:
        print(el)
    time.sleep(3)
    bot.stop()