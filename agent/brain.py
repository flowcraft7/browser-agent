import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-120b"


class Brain:
    def __init__(self):
        self.client = client

    def classify_task(self, task: str) -> str:
        prompt = f"""Classify this task as "browser" or "os" only.
- browser: websites, YouTube, Instagram, search, online forms
- os: local files, folders, desktop apps (Word, Notepad)

Task: "{task}"
Answer with ONLY one word: browser or os."""

        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        result = response.choices[0].message.content.strip().lower()
        return "os" if "os" in result else "browser"

    def decide_next_action(self, task: str, page_state: dict, history: list) -> dict:
        system_prompt = """You are an autonomous agent's brain. Decide the SINGLE next action.
Respond ONLY with valid JSON, no markdown, no extra text:
{"action": "click|type|scroll|navigate|open_file|open_folder|list_folder|launch_app|wait|done", "target": "...", "value": "...", "reasoning": "short reason"}

Rules:
- For browser tasks: prefer direct "navigate" to a known site/URL when possible (e.g. youtube.com/results?search_query=X) instead of clicking through a search engine.
- Use selectors EXACTLY as given in the elements list (they look like [data-agent-id="N"]) — never invent your own selector.
- Use "done" when task is complete."""

        user_prompt = f"""TASK: {task}

STATE: {json.dumps(page_state, separators=(',', ':'))}

RECENT ACTIONS: {json.dumps(history[-3:], separators=(',', ':'))}

Next action?"""

        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"action": "done", "reasoning": f"Failed to parse: {raw[:200]}"}