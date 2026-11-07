import sys

from ai_mapper import AIMapper
from main import run_visit
from smoke_test import AutoConsole


# (what the patient says first, the patient's story). Headache is not in explanations.json, so '?' goes to the AI there.
VISITS = [
    ("my stomach pain", "Pain near my right ribs for 3 days, I vomited twice, no fever."),
    ("I have fever", "Fever for 4 days with chills, it comes and goes, and my body aches. No cough."),
    ("bad headache", "Throbbing headache on one side since yesterday, light hurts my eyes, I feel like vomiting."),
]

# Option questions the CHW answers by typing the patient's words: (question starts with, patient's words).
# About half of the option questions in the three visits are on this list; the rest get a number as before.
PATIENT_WORDS = [
    ("which part of the abdomen", "near my right ribs"),
    ("how did the pain start", "it started suddenly"),
    ("character of the pain", "it comes and goes"),
    ("describe the pain", "it feels like cramps"),
    ("what worsens the pain", "it hurts more after eating"),
    ("what relieves", "it gets better after I vomit"),
    ("how does fever change", "it comes and goes"),
    ("in a day, when do you feel fever", "mostly at night"),
    ("which part of your head", "all over my head"),
    ("how did the symptom start", "it started yesterday morning, I remember the time"),
    ("character of headache", "it throbs"),
    ("in a day, when do you feel pain", "worst when I wake up"),
    ("does the symptom get worse", "when I bend down"),
    ("do you have the following symptom", "nausea and vomiting"),
    ("do you have a history of any", "I have sugar disease"),
    ("current medication", "I'm not taking any medicine"),
    ("do you have any allergies", "no allergies"),
    ("smoking history", "I have never smoked"),
    ("alcohol use", "I don't drink"),
    ("do you have a family history", "my mother has high blood pressure"),
]


class WordsConsole(AutoConsole):
    """Like AutoConsole, but answers the option questions in PATIENT_WORDS with the patient's words.
    If the AI can't match them, the question comes back and gets a number instead."""

    def __init__(self, complaint_words, story):
        super().__init__(complaint_words, story)
        self.question = ""
        self.option_questions = set()
        self.answered_in_words = set()

    def show(self, text=""):
        super().show(text)
        if text and not text.startswith(" "):
            self.question = text.lower()

    def ask(self, prompt):
        if "Number(s)" in prompt:
            self.option_questions.add(self.question)
        words = self.words_for(prompt)
        if words is None:
            return super().ask(prompt)
        self.answered_in_words.add(self.question)
        self.log.append(prompt + " " + words)
        return words

    def words_for(self, prompt):
        # Let AutoConsole type its '?' and '?2' first, and never retype words for the same question.
        if "Number(s)" not in prompt or not self.help_asked_on_option:
            return None
        if self.question in self.answered_in_words:
            return None
        for start, words in PATIENT_WORDS:
            if self.question.startswith(start):
                return words
        return None

# Task names used in ai_mapper.py, grouped the way we report them.
GROUPS = {
    "match complaint": "complaint match",
    "map answer": "option mapping",
    "answer from story": "story check",
    "story with evidence": "story check",
    "value from story": "story check",
    "double-check": "yes/no check",
    "explain": "explain",
}
GROUP_ORDER = ["complaint match", "option mapping", "story check", "yes/no check", "explain"]


def empty_row():
    return {"calls": 0, "prompt_tokens": 0, "output_tokens": 0, "seconds": 0}


def add_up(timings):
    """Adds up calls, tokens and seconds for each group of AI tasks."""
    totals = {}
    for timing in timings:
        group = GROUPS.get(timing["task"], timing["task"])
        if group not in totals:
            totals[group] = empty_row()
        totals[group]["calls"] += 1
        totals[group]["prompt_tokens"] += timing["prompt_tokens"]
        totals[group]["output_tokens"] += timing["output_tokens"]
        totals[group]["seconds"] += timing["seconds"]
    return totals


def print_table(title, totals, visit_count=1):
    """Prints one row per group, then the total. With visit_count > 1 it prints the average per visit."""
    print(f"\n{title}")
    print(f"   {'task':16} {'AI calls':>9} {'prompt tokens':>14} {'output tokens':>14} {'AI seconds':>11}")
    groups = GROUP_ORDER + [group for group in totals if group not in GROUP_ORDER]
    everything = empty_row()
    for group in groups:
        row = totals.get(group, empty_row())
        for key in everything:
            everything[key] += row[key]
        print_row(group, row, visit_count)
    print_row("all", everything, visit_count)


def print_row(name, row, visit_count):
    print(f"   {name:16} {row['calls'] / visit_count:9.1f} {row['prompt_tokens'] / visit_count:14.0f} "
          f"{row['output_tokens'] / visit_count:14.0f} {row['seconds'] / visit_count:11.1f}")


def run(model_path, folder):
    print(f"\n========== {model_path.split('/')[-1]} ==========")
    mapper = AIMapper(model_path)
    all_visits = {}
    for number, (complaint_words, story) in enumerate(VISITS, start=1):
        mapper.timings = []
        console = WordsConsole(complaint_words, story)
        visit = run_visit(console, mapper, folder)
        totals = add_up(visit["run_info"]["ai_timings"])
        print_table(f"Visit {number}: {visit['chief_complaint']['protocol']} "
                    f"(\"{complaint_words}\")", totals)
        mapped = 0
        for answer in visit["answers"]:
            if answer["source"] == mapper.name:
                mapped += 1
        print(f"   {len(console.answered_in_words)} of {len(console.option_questions)} option questions "
              f"answered in the patient's words; the AI matched {mapped} of them")
        for group, row in totals.items():
            if group not in all_visits:
                all_visits[group] = empty_row()
            for key in row:
                all_visits[group][key] += row[key]
    print_table(f"Average per visit ({len(VISITS)} visits)", all_visits, len(VISITS))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python workload_report.py PROTOCOL_FOLDER MODEL.gguf [MODEL.gguf ...]")
        sys.exit(1)
    for model_path in sys.argv[2:]:
        run(model_path, sys.argv[1])
