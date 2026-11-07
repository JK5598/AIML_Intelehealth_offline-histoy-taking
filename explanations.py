import json
import os
import time


FOLDER = os.path.dirname(os.path.abspath(__file__))
EXPLANATIONS_FILE = os.path.join(FOLDER, "explanations.json")
LOG_FILE = os.path.join(FOLDER, "explanation_log.jsonl")

DRAFT_LABEL = "Draft – not checked yet"
AI_LABEL = "AI explanation – not checked"
NOTHING_YET = "No explanation available yet."


def simple_key(text):
    """'Other [Describe]', 'Other[describe]' and 'other describe' all become 'other describe'."""
    text = text.replace("[", " ").replace("]", " ").replace("*", " ")
    return " ".join(text.lower().split())


def load(path=EXPLANATIONS_FILE):
    if not os.path.exists(path):
        return {}, {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    terms = {}
    for name, entry in data.get("terms", {}).items():
        terms[simple_key(name)] = entry
    questions = {}
    for name, entry in data.get("questions", {}).items():
        questions[simple_key(name)] = entry
    return terms, questions


def find(entries, text):
    """Looks up a label. 'Upper (R) - Right Hypochondrium' is also found under 'Right Hypochondrium'."""
    key = simple_key(text)
    if key in entries:
        return entries[key]
    if " - " in key:
        short_key = key.split(" - ")[-1]
        return entries.get(short_key)
    return None


class Explainer:
    """Shows plain-language explanations when the CHW types '?'.
    Where they come from, in order: explanations.json, then the AI (if a model is loaded), then nothing."""

    def __init__(self, mapper, console, path=EXPLANATIONS_FILE, log_path=LOG_FILE):
        self.mapper = mapper
        self.console = console
        self.terms, self.questions = load(path)
        self.log_path = log_path
        self.complaint = ""
        self.ai_explanations = []
        self.already_asked = {}

    def show(self, question_text, option_labels=()):
        """'?': explains the question, plus only the options that have an entry in explanations.json."""
        self.console.show("")
        self.console.show("   --- Simple explanation ---")
        text = self.explain(question_text, question_text, "question")
        self.console.show(f"   Question: {text or NOTHING_YET}")
        for label in option_labels:
            entry = find(self.terms, label)
            if entry and entry.get("text"):
                self.console.show(f"   - {label}: {self.explain(label, question_text, 'term')}")
        self.console.show("")

    def show_option(self, label, question_text):
        """'?3': explains one option. This is the only way an option goes to the AI."""
        self.console.show("")
        self.console.show("   --- Simple explanation ---")
        text = self.explain(label, question_text, "term")
        self.console.show(f"   - {label}: {text or NOTHING_YET}")
        self.console.show("")

    def explain(self, text, question_text, kind):
        if kind == "question":
            # Follow-up questions are built from an answer's label (e.g. "Cough"), so look in terms too.
            entry = find(self.questions, text) or find(self.terms, text)
        else:
            entry = find(self.terms, text)

        if entry and entry.get("text"):
            if entry.get("checked_by"):
                return entry["text"]
            return f"{entry['text']} ({DRAFT_LABEL})"

        ai_text = self.ask_ai(text, question_text, kind)
        if ai_text:
            return f"{ai_text} ({AI_LABEL})"
        return None

    def ask_ai(self, text, question_text, kind):
        """Asks the model once per visit for each text. Every AI explanation is logged for review."""
        key = (kind, text)
        if key in self.already_asked:
            return self.already_asked[key]

        started = time.time()
        answer = self.mapper.explain(text, kind, question_text, self.complaint)
        seconds = round(time.time() - started, 2)
        self.already_asked[key] = answer
        if not answer:
            return None

        entry = {
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "kind": kind,
            "term": text,
            "question": question_text,
            "complaint": self.complaint,
            "text": answer,
            "seconds": seconds,
            "model": getattr(self.mapper, "model_name", self.mapper.name),
        }
        self.ai_explanations.append(entry)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return answer
