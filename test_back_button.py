#----- Lia's code: check the phone's Back button and "End this visit" on all 5 test cases, no phone needed -----
r"""For each test case (TC01-TC05, answer-sheet patient + simulated CHW, keyword app, no AI):
  1. a normal visit gives the "right" answers,
  2. then the same visit is run through the phone's code (app_bridge.py) many times; each time, at one
     step, the CHW sends a WRONG answer and then taps Back (sometimes two wrong answers and two Backs),
     then carries on with the right answers.
The saved visit must be exactly the same as the normal visit: same answers, same red flags.
Also checks that "End this visit" stops without saving a file, and that AnswerMemory gives MedPsy's
first answer again during a replay without running the model again.
Ends with "PROBLEMS: 0" when everything matches.

How to run (from the project folder):
  Windows (PowerShell):
    $PROTOCOLS = "..\intelehealth-ayu-protocols\protocols\v2\All Protocols (JSON)"
    python test_back_button.py "$PROTOCOLS"
  Mac (Terminal):
    PROTOCOLS="../intelehealth-ayu-protocols/protocols/v2/All Protocols (JSON)"
    python test_back_button.py "$PROTOCOLS"
"""
import glob
import json
import os
import sys
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
sys.path.insert(0, os.path.join(here, "android", "app", "src", "main", "python"))
import app_bridge
import main
from keyword_mapper import KeywordMapper
from sim_patient import SheetPatient, SimulatedCHW
from visit_replay import BACK, END, AnswerMemory

protocols = sys.argv[1]
cases = json.load(open(os.path.join(here, "eval_cases.json"), encoding="utf-8"))["cases"]
sheets = json.load(open(os.path.join(here, "eval_patient_answers.json"), encoding="utf-8"))
problems = []


class Recorder:
    """Wraps the simulated CHW and writes down every answer it gives."""
    def __init__(self, chw):
        self.chw, self.replies = chw, []

    def show(self, text=""):
        self.chw.show(text)

    def ask(self, prompt):
        reply = self.chw.ask(prompt).strip()
        self.replies.append(reply)
        return reply


class FakeScreen:
    """Stands in for the phone screen: each time a question is asked, it 'taps' the next scripted answer."""
    def __init__(self, script):
        self.script, self.ended_message, self.saved, self.clears = list(script), None, None, 0

    def show(self, text): pass
    def showStyled(self, text, style): pass
    def clearLog(self): self.clears += 1
    def finished(self, path): self.saved = path
    def ended(self, message): self.ended_message = message

    def askWith(self, prompt, kind, buttons, multi):
        if not self.script:
            raise RuntimeError("the script ran out of answers at: " + prompt)
        app_bridge.current_console.answers.put(self.script.pop(0))


def answers_of(visit):
    return [(a["section"], a["question_id"], tuple(a["answers"]), a["value"], a["status"], a["source"])
            for a in visit["answers"]], visit["red_flags"]


def phone_visit(script, folder):
    screen = FakeScreen(script)
    app_bridge.run_visit(screen, protocols, folder, "no-model-here.gguf")   # no model: keyword matching
    return screen


checked = 0
for case in cases:
    recorder = Recorder(SimulatedCHW(case, SheetPatient(case, sheets[case["id"]])))
    normal = main.run_visit(recorder, KeywordMapper(), protocols)
    right = recorder.replies
    want = answers_of(normal)

    # Not the very last answer: after it the visit is over (summary shown), so there is nothing to go back to.
    steps = sorted(set([0, 1, 2, 3, len(right) // 3, len(right) // 2, len(right) - 3, len(right) - 2]))
    for step in steps:
        for wrong in (["zzz wrong"], ["n", "zzz wrong"]):           # one mistake + Back, or two + two Backs
            script = right[:step] + wrong + [BACK] * len(wrong) + right[step:]
            with tempfile.TemporaryDirectory() as folder:
                screen = phone_visit(script, folder)
                files = glob.glob(os.path.join(folder, "visit_*.json"))
                if len(files) != 1:
                    problems.append((case["id"], step, "no saved visit"))
                    continue
                visit = json.load(open(files[0], encoding="utf-8"))
                if answers_of(visit) != want:
                    problems.append((case["id"], step, wrong, "answers differ after Back"))
                if visit["run_info"]["back_presses"] != len(wrong):
                    problems.append((case["id"], step, "back_presses", visit["run_info"]["back_presses"]))
                if screen.script:
                    problems.append((case["id"], step, "answers left over", screen.script[:3]))
                checked += 1

    # End this visit halfway: nothing saved
    with tempfile.TemporaryDirectory() as folder:
        screen = phone_visit(right[: len(right) // 2] + [END], folder)
        if glob.glob(os.path.join(folder, "visit_*.json")) or not screen.ended_message:
            problems.append((case["id"], "End this visit did not stop cleanly"))
    print(f"{case['id']}: {len(right)} answers, Back checked at {len(steps)} steps x 2, End checked")


# AnswerMemory: the second identical AI call comes from memory (no model run, no AI time added)
class FakeAI:
    def __init__(self):
        self.timings, self.runs = [], 0

    def generate(self, prompt, grammar=None, max_tokens=40, task="task"):
        self.runs += 1
        self.timings.append({"task": task, "seconds": 1.0})
        return f"answer {self.runs}"


ai = FakeAI()
memory = AnswerMemory(ai)
first, again = ai.generate("same prompt"), ai.generate("same prompt")
other = ai.generate("another prompt")
memory.stop()
if not (first == again == "answer 1" and other == "answer 2" and ai.runs == 2 and len(ai.timings) == 2):
    problems.append(("AnswerMemory", first, again, other, ai.runs))
if ai.generate("same prompt") != "answer 3":
    problems.append(("AnswerMemory still on after stop()",))

print(f"\nvisits with Back checked: {checked}")
print("PROBLEMS:", len(problems))
for problem in problems[:20]:
    print("  ", problem)
#----- end of Lia's code -----
