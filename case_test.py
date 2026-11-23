#----- Lia's code: test the app on the teaching cases (Test_Cases_Organization.xlsx) -----
r"""Runs each prepared teaching case through today's app and the multi-question intake,
then checks how many of the case's key facts ended up in the visit record.

What it needs:
  - Test_Cases_Organization.xlsx (the case sheet from the team's case-setup task):
      "Case Overview" sheet: Case ID, Age, Sex, Matching Protocol, Opening Statement
      one sheet per case:   Fact ID, Category, Expected Fact, Patient Answer, Include in History Score?
  - the protocol folder, and optionally a model file.
No extra packages: the .xlsx file is read with plain Python.

How the "patient" works (automatic, nobody types):
  - The opening statement is the patient's story.
  - For each question, the script picks the case's "Patient Answer" lines that fit that question
    (shared words with the question, its options, and the fact's category, e.g. Duration -> "Since when?").
  - In group mode, the reply to a group joins the answers that fit any question in the group.
  - With no fitting answer, the CHW picks "Don't know / None / No" if the question has it, skips it
    if it is optional, or else picks option 1. The same rule is used in both modes, so they compare
    fairly. Option-1 picks are counted as "guesses", because they can add wrong facts.

How facts are scored (automatic first pass, a person should check it):
  - A key fact counts as "captured" when one saved answer's chosen options (NOT the patient's own
    words) share its main words and have the same yes/no meaning. Typed values only count for
    duration facts ("Since when?"), because they are mostly copies of what the patient said.
  - Facts marked "No" under "Include in History Score?" (e.g. exam findings) are not scored.
  - Every fact is written to case_results.csv with the matched answer, so a reviewer can confirm
    or correct it. Treat the automatic numbers as a first pass, not the final score.

How to run (from the project folder):

  Windows, VS Code terminal (PowerShell):
    $PROTOCOLS = "..\intelehealth-ayu-protocols\protocols\v2\All Protocols (JSON)"
    python case_test.py "$PROTOCOLS" "D:\JHU\AI_ML\Test_Cases_Organization.xlsx"
    python case_test.py "$PROTOCOLS" "D:\JHU\AI_ML\Test_Cases_Organization.xlsx" "D:\JHU\AI_ML\models\medpsy-1.7b-q4_k_m-imat.gguf"

  Windows, Anaconda Prompt: same, but write "%PROTOCOLS%" instead of "$PROTOCOLS".

  Mac (Terminal):
    PROTOCOLS="../intelehealth-ayu-protocols/protocols/v2/All Protocols (JSON)"
    python case_test.py "$PROTOCOLS" ../Test_Cases_Organization.xlsx
    python case_test.py "$PROTOCOLS" ../Test_Cases_Organization.xlsx medpsy-1.7b-q4_k_m-imat.gguf

  Add --show to print every question and answer (long).
  Output: the table on screen, case_results.csv (one row per fact and mode), and
  case_<id>_<mode>_visit.json for each visit (ignored by git).
"""
import csv
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

import negation
import protocols as p
from compare_intake_modes import required_answered
from followup import is_no_answer_option
from keyword_mapper import KeywordMapper
from main import run_visit

MODES = ["one", "group"]
MAX_INPUTS = 600   # safety stop, in case a visit gets stuck asking the same thing


# ---------- 1. Reading the .xlsx with plain Python ----------

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def read_xlsx(path):
    """Returns {sheet name: list of rows}, each row a list of cell texts."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in item.iter("{%s}t" % NS["m"])))
        book = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        sheets = {}
        for sheet in book.find("m:sheets", NS):
            target = targets[sheet.get("{%s}id" % NS["r"])].lstrip("/")
            target = target if target.startswith("xl/") else "xl/" + target
            root = ET.fromstring(z.read(target))
            rows = []
            for row in root.iter("{%s}row" % NS["m"]):
                cells = {}
                for cell in row.findall("m:c", NS):
                    column = re.match(r"[A-Z]+", cell.get("r")).group(0)
                    kind = cell.get("t")
                    value = cell.find("m:v", NS)
                    if kind == "s" and value is not None:
                        text = shared[int(value.text)]
                    elif kind == "inlineStr":
                        text = "".join(t.text or "" for t in cell.iter("{%s}t" % NS["m"]))
                    else:
                        text = value.text if value is not None else ""
                    cells[column_number(column)] = (text or "").strip()
                if cells:
                    rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            sheets[sheet.get("name")] = rows
    return sheets


def column_number(letters):
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - 64
    return number - 1


def as_dicts(rows):
    header = rows[0]
    return [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in rows[1:]]


def load_cases(path, protocol_names):
    sheets = read_xlsx(path)
    cases = []
    for row in as_dicts(sheets["Case Overview"]):
        case_id = row.get("Case ID", "")
        if not case_id:
            continue
        protocol = protocol_from_cell(row.get("Matching Protocol", ""), protocol_names)
        facts = []
        if case_id in sheets and len(sheets[case_id]) > 1:
            for fact in as_dicts(sheets[case_id]):
                if fact.get("Fact ID"):
                    facts.append({
                        "id": fact["Fact ID"],
                        "category": fact.get("Category", ""),
                        "expected": fact.get("Expected Fact", ""),
                        "answer": fact.get("Patient Answer", ""),
                        "scored": fact.get("Include in History Score?", "").lower().startswith("y"),
                    })
        cases.append({
            "id": case_id,
            "age": row.get("Age", ""),
            "sex": row.get("Sex", "").lower(),
            "complaint": row.get("Chief Complaint", ""),
            "diagnosis": row.get("Reference Diagnosis", ""),
            "protocol": protocol,
            "protocol_cell": row.get("Matching Protocol", ""),
            "story": row.get("Opening Statement", ""),
            "facts": facts,
        })
    return cases


def protocol_from_cell(cell, protocol_names):
    """'Abdominal Pain — pending confirmation' -> 'Abdominal Pain'. 'Pending — ...' -> None."""
    first = re.split(r"\s+[—–-]\s+", cell)[0].strip()
    for name in protocol_names:
        if name.lower() == first.lower():
            return name
    return None


# ---------- 2. Words: which answer fits which question ----------

STOP = {"have", "does", "what", "which", "when", "your", "with", "this", "that", "from", "been", "were",
        "there", "about", "feel", "felt", "part", "body", "time", "following", "symptom", "symptoms",
        "pain", "patient", "since", "started", "really", "would", "into", "only", "some", "more", "than",
        "very", "they", "them", "also", "just", "like", "make", "makes", "made", "getting", "other",
        "high", "particular", "last", "noticed", "approximately", "after", "before", "during"}

# Fact category -> words that the matching protocol question uses
CATEGORY_HINTS = [
    ("duration", "since when long"),
    ("location", "abdomen where location"),
    ("radiation", "move radiates"),
    ("progression", "move radiates"),
    ("character", "character"),
    ("timing", "time night"),
    ("aggravating", "worsens worse"),
    ("relieving", "relieves relief"),
    ("associated symptom", "following symptom"),
    ("negative symptom", "following symptom"),
    ("uncertain symptom", "following symptom"),
    ("past medical history", "history following"),
    ("medication", "medicine medication taken treatment"),
    ("smoking", "smoking"),
    ("family", "family"),
    ("onset", "start"),
]


def stems(text):
    words = re.findall(r"[a-z]+", (text or "").lower())
    return {negation.stem(w) for w in words if len(w) > 3 and w not in STOP}


def hint_stems(category):
    category = category.lower()
    words = " ".join(hint for key, hint in CATEGORY_HINTS if key in category)
    return {negation.stem(w) for w in words.split()}


def all_stems(text):
    """Like stems(), but keeps words such as 'since' and 'when' (needed to spot 'Since when?')."""
    return {negation.stem(w) for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 3}


def fitting_answers(question, options, facts, limit=3):
    """The case's patient answers that fit this question, best first."""
    question_stems = stems(question) | {s for label in options for s in stems(label)}
    question_words = all_stems(question)
    if len(options) > 8:
        limit = 6          # a long checklist ("Do you have the following symptoms?") can take several answers
    scored = []
    for fact in facts:
        if not fact["answer"] or fact["answer"].lower().startswith("n/a"):
            continue
        fact_stems = stems(fact["answer"]) | stems(fact["expected"])
        score = len(question_stems & fact_stems) + 2 * len(question_words & hint_stems(fact["category"]))
        if score >= 2:
            scored.append((score, fact["answer"]))
    scored.sort(key=lambda item: -item[0])
    answers = []
    for _, answer in scored:
        if answer not in answers:
            answers.append(answer)
    return answers[:limit]


# ---------- 3. The scripted patient (and CHW) ----------

class StuckVisit(Exception):
    pass


class CasePatient:
    """Plays the CHW typing what the case's patient says."""

    UNKNOWN_OPTIONS = ("don't know", "dont know", "unsure", "not known", "none", "no")

    def __init__(self, case, show=False):
        self.case = case
        self.show_all = show
        self.question = ""
        self.options = []
        self.group = []
        self.x_allowed = False
        self.tried = {}
        self.guesses = 0
        self.inputs = 0

    def show(self, text=""):
        if self.show_all:
            print(text)
        stripped = text.strip()
        if text.startswith("--- Question group"):
            self.group = []
        elif re.match(r"Q\d+\. ", stripped) and text.startswith("   Q"):
            self.group.append(stripped.split(". ", 1)[1].split("   (asked")[0])
        elif re.match(r"\d+\. ", stripped) and text.startswith("   "):
            self.options.append(stripped.split(". ", 1)[1])
        elif "x = no answer" in text:
            self.x_allowed = True
        elif text and not text.startswith(" ") and not text.startswith("-"):
            self.question = text
            self.options = []

    def ask(self, prompt):
        self.inputs += 1
        if self.inputs > MAX_INPUTS:
            raise StuckVisit(f"more than {MAX_INPUTS} inputs, last prompt: {prompt}")
        reply = self.reply_to(prompt)
        if self.show_all:
            print(prompt, reply)
        if "Number(s)" in prompt or "(duration)" in prompt or "(text)" in prompt or "(date)" in prompt:
            self.x_allowed = False
        return reply

    def reply_to(self, prompt):
        if prompt.startswith("Patient age"):
            return str(self.case["age"])
        if prompt.startswith("Patient sex"):
            return self.case["sex"]
        if "Number, or type the patient's words" in prompt:
            return str(self.options.index(self.case["protocol"]) + 1)
        if "tell me more" in prompt:
            return self.case["story"]
        if "patient's reply to these questions" in prompt:
            said = []
            for question in self.group:
                for answer in fitting_answers(question, [], self.case["facts"], limit=6):
                    if answer not in said:
                        said.append(answer)
            return " ".join(said)
        if "Which is right?" in prompt:
            return "u"
        if any(check in prompt for check in ("Save these?", "Correct?", "Keep?", "Save as 'No'?")):
            return "y"
        if "How long, in days" in prompt:
            answers = [f["answer"] for f in self.case["facts"] if "duration" in f["category"].lower()]
            return answers[0] if answers else "unknown"
        if "Number(s)" in prompt:
            return self.choose(self.question)
        # a typed value: the question is in the prompt itself
        question = prompt.strip().split(" (")[0]
        answers = fitting_answers(question, [], self.case["facts"], limit=1)
        key = ("value", question)
        if answers and not self.tried.get(key):
            self.tried[key] = True
            return answers[0]
        return "unknown"

    def choose(self, question):
        key = ("choice", question)
        attempt = self.tried.get(key, 0)
        self.tried[key] = attempt + 1
        answers = fitting_answers(question, self.options, self.case["facts"])
        if attempt == 0 and answers:
            return " ".join(answers)            # the patient's words; the app matches them
        for number, label in enumerate(self.options, start=1):
            if label.lower().startswith(self.UNKNOWN_OPTIONS):
                return str(number)
        if attempt <= 1:
            return ""                           # Enter: skips an optional question
        self.guesses += 1
        return "1"                              # required and nothing fits: a guess


# ---------- 4. Scoring the key facts ----------

NEGATIVE_START = ("no ", "not ", "denies", "never", "none")


def record_lines(visit):
    """What the doctor sees: each saved answer's options and value (not the patient's own words)."""
    lines = []
    for answer in visit["answers"]:
        labels = [a for a in answer["answers"] if not a.startswith("[")]
        value = str(answer["value"]) if answer["value"] else ""
        if value.lower() == "unknown":
            value = ""          # the script's own "unknown" is not a fact
        text = " ".join(labels + [value]).strip()
        if not text or answer["status"] == "not_answered":
            continue
        negative = answer["status"] == "said_no" or any(is_no_answer_option(label) for label in labels)
        lines.append({"question": answer["question"], "text": text, "labels": " ".join(labels),
                      "value": value, "negative": negative, "unsure": answer["status"] == "unsure",
                      "shown": f"{answer['question']}: {text}" + (" (said NO)" if answer["status"] == "said_no" else "")})
    return lines


def fact_captured(fact, lines):
    """Returns the matching record line, or None."""
    fact_stems = stems(fact["expected"]) | stems(fact["answer"])
    negative = fact["expected"].lower().startswith(NEGATIVE_START)
    best, best_score = None, 0
    is_duration = "duration" in fact["category"].lower()
    uncertain = "uncertain" in fact["category"].lower()
    for line in lines:
        # Typed values are mostly copies of the patient's words, so they would match almost anything.
        # They only count for duration facts; every other fact must be in the chosen options.
        line_stems = stems(line["labels"]) | (stems(line["value"]) if is_duration else set())
        score = len(fact_stems & line_stems)
        if (is_duration and "since when" in line["question"].lower()
                and re.search(r"\d|one|two|three|four|five|six|seven|week|month|year|day|hour", line["value"].lower())):
            score += 2
        if uncertain and not line["unsure"]:
            continue        # "Fever is uncertain" is only captured if it was saved as unsure
        if score >= 1 and line["negative"] == negative and score > best_score:
            best, best_score = line, score
    return best


# ---------- 5. Running everything ----------

def run_all(folder, cases_path, mapper, show=False):
    protocol_names = p.list_complaints(folder)
    cases = load_cases(cases_path, protocol_names)
    rows, fact_rows = [], []
    for case in cases:
        if not case["facts"]:
            print(f"Skipping {case['id']}: its sheet has no key facts yet.")
            continue
        if not case["protocol"]:
            print(f"Skipping {case['id']}: matching protocol is \"{case['protocol_cell']}\" (not a protocol name).")
            continue
        scored = [f for f in case["facts"] if f["scored"]]
        for mode in MODES:
            if hasattr(mapper, "timings"):
                mapper.timings = []
            patient = CasePatient(case, show)
            try:
                visit = run_visit(patient, mapper, folder, intake_mode=mode)
            except StuckVisit as error:
                print(f"{case['id']} ({mode}) stopped: {error}")
                continue
            with open(f"case_{case['id']}_{mode}_visit.json", "w", encoding="utf-8") as f:
                json.dump(visit, f, indent=2, ensure_ascii=False)
            lines = record_lines(visit)
            captured = 0
            for fact in scored:
                match = fact_captured(fact, lines)
                captured += 1 if match else 0
                fact_rows.append({
                    "case": case["id"], "mode": mode, "fact_id": fact["id"], "category": fact["category"],
                    "expected_fact": fact["expected"], "patient_answer": fact["answer"],
                    "auto_captured": "yes" if match else "no",
                    "matched_answer": match["shown"] if match else "",
                    "reviewer_says": "",
                })
            info = visit["run_info"]
            done, total = required_answered(visit, folder)
            rows.append({
                "case": f"{case['id']} {case['protocol']}",
                "mode": mode,
                "key_facts": f"{captured}/{len(scored)}",
                "chw_inputs": info["chw_inputs"],
                "required": f"{done}/{total}",
                "guesses": patient.guesses,
                "unsure": sum(a["status"] == "unsure" for a in visit["answers"]),
                "follow_ups": info.get("follow_ups_asked", 0),
                "ai_seconds": round(sum(t["seconds"] for t in info["ai_timings"]), 1),
            })
    with open("case_results.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(fact_rows[0]) if fact_rows else ["case"])
        writer.writeheader()
        writer.writerows(fact_rows)
    return rows


def print_table(rows, mapper_name):
    print(f"\n========== Teaching cases ({mapper_name}) ==========")
    if not rows:
        print("No cases ran.")
        return
    columns = list(rows[0])
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in columns}
    print("  ".join(c.ljust(widths[c]) for c in columns))
    for row in rows:
        print("  ".join(str(row[c]).ljust(widths[c]) for c in columns))
    print("\nkey_facts = key facts found in the saved answers (automatic first pass; check case_results.csv);")
    print("guesses = times the script had to pick option 1 with nothing fitting (can add wrong facts).")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--show"]
    if len(args) < 2:
        print("Usage: python case_test.py PROTOCOL_FOLDER Test_Cases_Organization.xlsx [MODEL.gguf] [--show]")
        sys.exit(1)
    folder, cases_path = args[0], args[1]
    if len(args) > 2:
        from ai_mapper import AIMapper
        mapper = AIMapper(args[2])
        name = mapper.model_name
    else:
        mapper = KeywordMapper()
        name = "no AI, keyword matching"
    print_table(run_all(folder, cases_path, mapper, show="--show" in sys.argv), name)
#----- end of Lia's code -----
