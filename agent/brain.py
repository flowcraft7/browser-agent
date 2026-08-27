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
        """Call Groq with pacing + retry/backoff to respect low free-tier TPM limits."""
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

    def classify_task(self, task: str) -> str:
        prompt = f"""Classify this task as "browser" or "os" only.
- browser: websites, YouTube, Instagram, search, online forms, playing videos, commenting
- os: local files, folders, desktop apps (Word, Notepad), writing/typing documents

Task: "{task}"
Answer with ONLY one word: browser or os."""

        response = self._safe_call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        result = response.choices[0].message.content.strip().lower()
        return "os" if "os" in result else "browser"

    def decide_next_action(self, task: str, page_state: dict, history: list) -> dict:
        system_prompt = """You are an autonomous agent's brain. Decide the SINGLE next action.
Respond ONLY with valid JSON, no markdown, no extra text:
{"action": "click|type|scroll|navigate|wait|open_file|open_folder|list_folder|launch_app|open_word_blank|write_content|type_text|done", "target": "...", "value": "...", "reasoning": "short reason"}

Action guide:
- navigate: go to a URL directly (target = url)
- click: click an element (target = selector from the elements list EXACTLY as given)
- type: fill an input (target = selector, value = text)
- scroll: scroll the page down
- open_word_blank: opens a new blank Microsoft Word document (use this before writing any document)
- write_content: generate written content and type it into the currently open app (target = topic/description of what to write, value = extra instructions e.g. word count/tone). ONLY use this after open_word_blank if the goal is writing a document.
- type_text: type exact literal text into the active window (target = the text)
- list_folder / open_folder / open_file / launch_app: OS actions (target = path or app name)
- done: task is fully complete

Rules:
- For browser tasks prefer direct "navigate" to a known URL when possible instead of clicking through a search engine.
- Use selectors EXACTLY as given in the elements list (format: [data-agent-id="N"]) — never invent your own selector.
- For "write an assignment/essay/document" tasks: first open_word_blank, then write_content — do NOT try to type_text raw content yourself, use write_content so it's generated properly.
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
        """Generate one small chunk of written content — kept short to respect low TPM limits."""
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
        """Generate a longer document by chunking generation into small, rate-limit-safe calls."""
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