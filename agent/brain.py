import os
import json
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-120b"


class Brain:
    def __init__(self):
        self.client = client

    def _safe_call(self, messages, temperature=0.2, max_tokens=None):
        for attempt in range(5):
            try:
                time.sleep(1.5)
                kwargs = {"model": MODEL, "messages": messages, "temperature": temperature}
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens
                return self.client.chat.completions.create(**kwargs)
            except Exception as e:
                msg = str(e)
                if "rate_limit" in msg or "429" in msg or "413" in msg:
                    wait = 6 * (attempt + 1)
                    print(f"⏳ Rate limit hit, waiting {wait}s before retry...")
                    time.sleep(wait)
                    continue
                raise
        raise RuntimeError("Max retries exceeded due to rate limiting.")

    def decide_next_action(self, task: str, page_state: dict, history: list) -> dict:
        system_prompt = """You are an autonomous agent's brain that can control BOTH a web browser
AND the local computer (files/folders/apps) within the SAME task. Decide the SINGLE next action.
Respond ONLY with valid JSON, no markdown, no extra text:
{"action": "click|type|scroll|navigate|wait|extract_text|open_file|open_folder|list_folder|launch_app|write_content|type_text|done", "target": "...", "value": "...", "reasoning": "short reason"}

Action guide:
- navigate: go to a URL directly (target = url)
- click: click an element (target = selector from the elements list EXACTLY as given)
- type: fill an input (target = selector, value = text)
- scroll: scroll the page down
- extract_text: read the visible text content of the current page (e.g. email subjects, article text, prices). The result appears as "extracted_text" in the next STATE.
- launch_app: launch ANY desktop application by name (target = e.g. "notepad", "winword", "excel"). IMPORTANT: Never use launch_app to open Chrome or "the browser" — browser actions (navigate/click/type/scroll/extract_text) automatically use an already-connected Chrome browser. launch_app is ONLY for other desktop apps, never for the browser itself.
- write_content: generate NEW written content on a topic and type it into the currently focused app (target = topic, value = extra instructions). Use when content should be freshly generated (e.g. "write an essay").
- type_text: type exact literal text into the active window (target = the text). Use this when YOU already know what to write — e.g. after extract_text gave you real page content to summarize, compose the summary yourself and put it directly in "target".
- list_folder / open_folder / open_file: OS file/folder actions (target = path)
- done: task is fully complete

CROSS-DOMAIN TASKS (e.g. "check gmail then write a note about it in notepad"):
1. Use browser actions (navigate/click/extract_text) to gather the information.
2. Once you have read the relevant content via extract_text, use launch_app to open the target app (e.g. notepad).
3. Then use type_text with a "target" you compose yourself, summarizing what you read — do NOT use write_content here since the content must come from what was actually read, not freshly invented.

IMPORTANT for opening videos/articles/content:
- Elements whose href contains "/watch?v=", "/shorts/", "/status/", or similar are REAL content links, sorted to the TOP of the elements list. Prefer "navigate" with target = that href over "click".
- If your last 2+ actions look like they had no effect (same URL/title repeating in STATE), stop clicking and use navigate with an href instead.

CREDENTIAL RULE:
- If the task mentions placeholders like {{UNI_USERNAME}} or {{UNI_PASSWORD}}, use those EXACT placeholder strings as the "value". Never invent real credentials.

Rules:
- Use selectors EXACTLY as given in the elements list (format: [data-agent-id="N"]) — never invent your own selector.
- Use "done" only when the task is fully complete."""

        user_prompt = f"""TASK: {task}

STATE: {json.dumps(page_state, separators=(',', ':'))}

RECENT ACTIONS: {json.dumps(history[-3:], separators=(',', ':'))}

Next action?"""

        response = self._safe_call(
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

    def generate_content(self, topic: str, instructions: str = "", max_words: int = 120) -> str:
        prompt = f"""Write approximately {max_words} words of plain content for this task.
Topic/Task: {topic}
Additional instructions: {instructions}
Plain text only. No markdown, no headers, no bullet points unless asked."""
        response = self._safe_call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=350
        )
        return response.choices[0].message.content.strip()

    def generate_long_document(self, topic: str, instructions: str = "", num_chunks: int = 3, words_per_chunk: int = 120) -> str:
        full_text = []
        for i in range(num_chunks):
            part_instruction = instructions
            if i > 0:
                part_instruction += f"\nThis is part {i + 1} of {num_chunks}. Continue naturally, don't repeat the intro."
            print(f"  ✍️ Generating part {i + 1}/{num_chunks}...")
            chunk = self.generate_content(topic, part_instruction, words_per_chunk)
            full_text.append(chunk)
            time.sleep(4)
        return "\n\n".join(full_text)
