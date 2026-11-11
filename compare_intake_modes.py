#----- Lia's code: compare today's app and the multi-question intake on the same scripted patients -----
r"""Runs the same scripted patients through both intake modes and prints one table.

  one     the team's current app (main.py default): one question at a time
  group   multi-question intake, one typed reply fills a group of questions

The "patient" is a script: for each question it has the words the patient would say.
In group mode the script answers a whole group at once by joining those words.
Nothing is typed by a person, so the minutes are not real visit times; CHW inputs and answers are what to compare.

How to run (from the project folder):

  Windows (PowerShell):
    $PROTOCOLS = "..\intelehealth-ayu-protocols\protocols\v2\All Protocols (JSON)"
    python compare_intake_modes.py "$PROTOCOLS"
    python compare_intake_modes.py "$PROTOCOLS" "D:\JHU\AI_ML\models\medpsy-1.7b-q4_k_m-imat.gguf"

  Mac (Terminal):
    PROTOCOLS="../intelehealth-ayu-protocols/protocols/v2/All Protocols (JSON)"
    python compare_intake_modes.py "$PROTOCOLS"
    python compare_intake_modes.py "$PROTOCOLS" medpsy-1.7b-q4_k_m-imat.gguf

  Add --show to print every question and answer of every visit (long).
  Each visit is also saved as compare_<mode>_<number>_visit.json (ignored by git).
"""
import json
import sys

import protocols as p
from keyword_mapper import KeywordMapper
from main import run_visit


# Each patient: complaint words, story, then (question starts with, what the patient says).
# "since when" says "sometimes in a day" on purpose: it is vague, so group mode should follow up.
# The story says "no fever" and the reply says "maybe fever" on purpose: the answers disagree.
PATIENTS = [
    {
        "complaint": "my stomach pain",
        "story": "Pain near my right ribs, I vomited twice, no fever.",
        "words": [
            ("which part of the abdomen", "near my right ribs"),
            ("does the pain move", "it does not move"),
            ("since when", "sometimes in a day"),
            ("how did the pain start", "it was sudden"),
            ("what time of the day", "mostly at night"),
            ("character of the pain", "it is a dull ache, it comes and goes"),
            ("do you have the following symptom", "nausea and vomiting, maybe fever"),
            ("what worsens the pain", "food makes it worse"),
            ("what relieves", "vomiting makes it better"),
            ("have you taken any treatment", "no treatment yet"),
            ("do you have a history of any", "I have diabetes"),
            ("have you recently taken any kind of medicine", "no medicine"),
            ("do you have any allergies", "no known allergies"),
            ("smoking history", "never smoked, I am a never-smoker"),
            ("alcohol use", "no alcohol"),
        ],
        "how_long": "3 days",
    },
    {
        "complaint": "I have fever",
        "story": "Fever for 4 days with chills, my body aches.",
        "words": [
            ("since when", "for 4 days"),
            ("nature of fever", "it comes and goes"),
            ("in a day, when do you feel fever", "mostly at night"),
            ("have you taken any treatment", "no treatment yet"),
            ("do you have the following symptom", "chills and body ache"),
            ("do you have a history of any", "high blood pressure"),
            ("have you recently taken any kind of medicine", "no medicine"),
            ("do you have any allergies", "no known allergies"),
            ("smoking history", "never smoked, I am a never-smoker"),
            ("alcohol use", "no alcohol"),
        ],
        "how_long": "4 days",
    },
]

MODES = ["one", "group"]


class ScriptedPatient:
    """Plays the CHW typing what the scripted patient says. Answers y to every 'Save? / Correct? / Keep?'."""

    def __init__(self, patient, show=False):
        self.patient = patient
        self.show_all = show
        self.question = ""
        self.group = []
        self.tried_words = set()

    def show(self, text=""):
        if self.show_all:
            print(text)
        stripped = text.strip()
        if text.startswith("--- Question group"):
            self.group = []
        elif stripped.startswith("Q") and ". " in stripped[:5]:
            self.group.append(stripped.split(". ", 1)[1].lower())
        elif text and not text.startswith(" ") and not text.startswith("-"):
            self.question = text.lower()

    def words_for(self, question):
        for start, words in self.patient["words"]:
            if question.startswith(start):
                return words
        return None

    def ask(self, prompt):
        reply = self.reply_to(prompt)
        if self.show_all:
            print(prompt, reply)
        return reply

    def reply_to(self, prompt):
        if "age" in prompt:
            return "34"
        if "sex" in prompt:
            return "female"
        if "Number, or type" in prompt:
            return self.patient["complaint"]
        if "tell me more" in prompt:
            return self.patient["story"]
        if "patient's reply to these questions" in prompt:
            said = [self.words_for(q) for q in self.group]
            return ", ".join(words for words in said if words)
        if "Which is right?" in prompt:
            return "u"
        if any(check in prompt for check in ("Save these?", "Correct?", "Keep?", "Save as 'No'?")):
            return "y"
        if "How long, in days" in prompt:
            return self.patient["how_long"]
        if "Number(s)" in prompt:
            words = self.words_for(self.question)
            if words and self.question not in self.tried_words:
                self.tried_words.add(self.question)
                return words
            return "1"
        # a typed value (duration, describe, ...): the question is in the prompt itself
        words = self.words_for(prompt.strip().split(" (")[0].lower()) or self.words_for(self.question)
        if words:
            return words
        return "3 days" if "(duration)" in prompt else "none"


def required_answered(visit, folder):
    """Of the required top-level questions that apply to this patient, how many have an answer."""
    sections = {"hpi": visit["chief_complaint"]["protocol"], "past_history": "patHist", "family_history": "famHist"}
    total = 0
    answered = 0
    for section, name in sections.items():
        protocol = p.load_protocol(folder, name)
        for question in p.children(protocol):
            if not p.is_required(question) or not p.applies_to_patient(question, visit["patient"]):
                continue
            total += 1
            for answer in visit["answers"]:
                if (answer["section"] == section and answer["question_id"] == question.get("id")
                        and answer["status"] in ("present", "said_no", "unsure")):
                    answered += 1
                    break
    return answered, total


def run_all(folder, mapper, show=False):
    rows = []
    for number, patient in enumerate(PATIENTS, start=1):
        for mode in MODES:
            if hasattr(mapper, "timings"):
                mapper.timings = []
            visit = run_visit(ScriptedPatient(patient, show), mapper, folder, intake_mode=mode)
            with open(f"compare_{mode}_{number}_visit.json", "w", encoding="utf-8") as f:
                json.dump(visit, f, indent=2, ensure_ascii=False)
            info = visit["run_info"]
            statuses = [answer["status"] for answer in visit["answers"]]
            done, total = required_answered(visit, folder)
            rows.append({
                "patient": f"{number}. {visit['chief_complaint']['protocol']}",
                "mode": mode,
                "chw_inputs": info["chw_inputs"],
                "required": f"{done}/{total}",
                "answered": statuses.count("present"),
                "said_no": statuses.count("said_no"),
                "unsure": statuses.count("unsure"),
                "no_answer": statuses.count("not_answered"),
                "follow_ups": info.get("follow_ups_asked", 0),
                "from_reply": info.get("filled_from_group_reply", 0),
                "ai_calls": len(info["ai_timings"]),
                "ai_seconds": round(sum(t["seconds"] for t in info["ai_timings"]), 1),
            })
    return rows


def print_table(rows, mapper_name):
    print(f"\n========== Intake modes compared ({mapper_name}) ==========")
    columns = ["patient", "mode", "chw_inputs", "required", "answered", "said_no", "unsure",
               "no_answer", "follow_ups", "from_reply", "ai_calls", "ai_seconds"]
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in columns}
    print("  ".join(c.ljust(widths[c]) for c in columns))
    for row in rows:
        print("  ".join(str(row[c]).ljust(widths[c]) for c in columns))
    print("\nchw_inputs = times the CHW typed something; required = required questions with an answer;")
    print("from_reply = answers filled from one group reply (group mode only).")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--show"]
    if not args:
        print("Usage: python compare_intake_modes.py PROTOCOL_FOLDER [MODEL.gguf] [--show]")
        sys.exit(1)
    folder = args[0]
    if len(args) > 1:
        from ai_mapper import AIMapper
        mapper = AIMapper(args[1])
        name = mapper.model_name
    else:
        mapper = KeywordMapper()
        name = "no AI, keyword matching"
    print_table(run_all(folder, mapper, show="--show" in sys.argv), name)
#----- end of Lia's code -----
