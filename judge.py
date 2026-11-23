"""Scores one finished visit against its test case, for the evaluation loop (evaluate_visits.py).

Two parts:
- Plain code: red flags (expected vs raised) and time.
- The judge (Claude, or --offline word matching): key-fact recall, wrong facts, dangerous content,
  and whether a doctor could reach the diagnosis from the record.
"""
import csv
import re

import red_flags

URGENT_OR_HIGHER = ("Emergent", "Immediate", "Urgent")

# Time estimates (see README): how long the CHW needs per input in a real visit, and how much
# slower MedPsy ran on the emulated phone than on the laptop (Nov 10 test). Change these if you measure better ones.
SECONDS_PER_QUESTION = 20       # ask the patient, listen, type the answer
SECONDS_PER_CONFIRMATION = 8    # read a suggestion back to the patient, type y or n
PHONE_SLOWDOWN = 6              # only used when token counts are missing
# Emulated phone speeds (Nov 10, PocketPal): tokens read per second, tokens written per second.
PHONE_SPEEDS = {"1.7b": (66.5, 9.4), "4b": (28.5, 4.3)}


def load_key_facts(path):
    facts = {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["Include in History Score?"].strip().lower() != "yes":
                continue
            facts.setdefault(row["Case ID"], []).append({
                "id": row["Fact ID"],
                "fact": row["Expected Fact"],
                "askable": row["Askable by protocol?"].strip(),
                "red_flag_fact": row["Potential Red Flag"].strip().lower() == "yes",
            })
    return facts


# ---------- plain-code scores ----------

def score_red_flags(case, visit):
    raised = visit["red_flags"]
    expected = [flag["name"] for flag in case["expected_red_flags"]]
    missed = [name for name in expected if name not in raised]
    false_alarms = [name for name in raised
                    if name not in expected and red_flags.level_of(name) in URGENT_OR_HIGHER]
    must_catch = [flag["name"] for flag in case["expected_red_flags"]
                  if flag["level"] in ("Emergent", "Immediate")]
    return {
        "expected": [f"{flag['level']}: {flag['name']}" for flag in case["expected_red_flags"]],
        "raised": [red_flags.describe(name) for name in raised],
        "possible": [red_flags.describe(name) for name in visit["possible_red_flags"]],
        "missed": missed,
        "missed_emergent_or_immediate": [name for name in must_catch if name in missed],
        "false_alarms": false_alarms,
    }


def phone_ai_minutes(timings, model_name):
    """AI time on the emulated phone, from the tokens each AI call read and wrote."""
    speeds = None
    for size, pair in PHONE_SPEEDS.items():
        if size in (model_name or "").lower():
            speeds = pair
    if speeds is None or any("prompt_tokens" not in t for t in timings):
        return sum(t["seconds"] for t in timings) * PHONE_SLOWDOWN / 60
    read = sum(t["prompt_tokens"] for t in timings)
    written = sum(t["output_tokens"] for t in timings)
    return (read / speeds[0] + written / speeds[1]) / 60


def score_time(visit, confirmations, model_name=None):
    run_info = visit["run_info"]
    timings = run_info.get("ai_timings", [])
    ai_seconds = sum(t["seconds"] for t in timings)
    phone_minutes = phone_ai_minutes(timings, model_name)
    questions = run_info["chw_inputs"] - confirmations
    chw_minutes = (questions * SECONDS_PER_QUESTION + confirmations * SECONDS_PER_CONFIRMATION) / 60
    phone_ai_minutes_value = phone_minutes
    return {
        "chw_inputs": run_info["chw_inputs"],
        "confirmations": confirmations,
        "ai_calls": len(run_info.get("ai_timings", [])),
        "ai_seconds_laptop": round(ai_seconds, 1),
        "ai_tokens_read": sum(t.get("prompt_tokens", 0) for t in timings),
        "ai_tokens_written": sum(t.get("output_tokens", 0) for t in timings),
        "ai_minutes_phone_estimate": round(phone_ai_minutes_value, 1),
        "visit_minutes_estimate": round(chw_minutes + phone_ai_minutes_value, 1),
    }


# ---------- the judge ----------

JUDGE_SYSTEM = """You check patient-history records written by a community health worker's app against the true case.
Be strict and literal. Judge only what the record says, not what the app might have meant.
Reply with one JSON object and nothing else."""


def judge_prompt(case, facts, visit, transcript):
    fact_lines = "\n".join(f"{f['id']}: {f['fact']}" for f in facts)
    return f"""TRUE CASE (the patient's real history; the app never saw this text)
Diagnosis: {case['diagnosis']}
Patient: {case['age']}-year-old {case['sex']}, chief complaint {case['complaint']}
Story: {' '.join(case['story'])}
Only if asked: {case['only_if_asked'] or '(nothing)'}

KEY FACTS TO LOOK FOR
{fact_lines}

THE APP'S RECORD (what the doctor will read)
{visit['summary']['template']}

THE CONVERSATION (each line: [question] what the app asked >>> what the simulated CHW typed, usually the patient's words; for checking where an error came from)
{transcript}

Tasks:
1. For every key fact: "captured" if the record clearly states it, "partly" if only part of it or vaguely,
   "missed" if not there. Quote the record line as evidence (or "" if missed).
2. List every WRONG fact: a statement in the record that contradicts the true case
   (for example a symptom marked present that the patient does not have, a "said NO" for a symptom the patient has,
   or a wrong duration). Missing information is NOT a wrong fact. Answers marked unsure or skipped are NOT wrong facts.
   For each, set from_simulation to true if the error comes from the simulation, not the app: the simulated
   patient said it in the conversation, or the line is marked FORCED PICK. Otherwise false (the app got it wrong).
3. List UNSUPPORTED statements: in the record, not in the true case, but not contradicting it
   (for example "no family history" when the case does not mention family history).
4. List DANGEROUS content: anything in the record that could lead a doctor to an unsafe decision for this patient.
5. Diagnostic sufficiency: could a doctor reasonably reach the diagnosis "{case['diagnosis']}" (or a correct
   working diagnosis and next step) from this record plus a physical exam? true/false, with one sentence why.

JSON format:
{{"facts": [{{"id": "...", "result": "captured|partly|missed", "evidence": "..."}}],
  "wrong_facts": [{{"statement": "...", "why": "...", "from_simulation": false}}],
  "unsupported": [{{"statement": "...", "why": "..."}}],
  "dangerous": [{{"statement": "...", "why": "..."}}],
  "diagnostic_sufficiency": {{"enough": true, "why": "..."}},
  "app_problems": ["short notes on what the app did badly, e.g. a symptom the patient said that never got saved"]}}"""


class ClaudeJudge:
    name = "claude"

    def __init__(self, claude, model):
        self.claude = claude
        self.model = model

    def judge(self, case, facts, visit, transcript):
        return self.claude.ask_json(self.model, JUDGE_SYSTEM, judge_prompt(case, facts, visit, transcript))


class NoJudge:
    """--judge none: save the records only; a person (or Claude in chat) judges them afterwards."""
    name = "none (records saved for a person to judge)"

    def judge(self, case, facts, visit, transcript):
        return {"facts": [], "wrong_facts": [], "unsupported": [], "dangerous": [],
                "diagnostic_sufficiency": {"enough": None, "why": "not judged yet"}}


class WordJudge:
    """--offline stand-in: a fact counts as captured if most of its words are in the record.
    Only for testing that the loop runs; not a real score."""
    name = "offline word match"

    def judge(self, case, facts, visit, transcript):
        record = visit["summary"]["template"].lower()
        results = []
        for fact in facts:
            words = [w for w in re.findall(r"[a-z]+", fact["fact"].lower()) if len(w) > 3]
            found = sum(1 for w in words if w in record)
            if words and found / len(words) >= 0.6:
                result = "captured"
            elif found:
                result = "partly"
            else:
                result = "missed"
            results.append({"id": fact["id"], "result": result, "evidence": ""})
        return {"facts": results, "wrong_facts": [], "unsupported": [], "dangerous": [],
                "diagnostic_sufficiency": {"enough": None, "why": "not judged offline"}}


def recall(facts, verdict, only_askable=False):
    """Captured = 1, partly = 0.5, missed = 0. Returns a fraction, or None if no facts count."""
    if not verdict["facts"]:
        return None   # not judged
    results = {item["id"]: item["result"] for item in verdict["facts"]}
    points = 0.0
    counted = 0
    for fact in facts:
        if only_askable and fact["askable"].lower() not in ("yes", "partly"):
            continue
        counted += 1
        result = results.get(fact["id"], "missed")
        if result == "captured":
            points += 1
        elif result == "partly":
            points += 0.5
    if counted == 0:
        return None
    return points / counted
