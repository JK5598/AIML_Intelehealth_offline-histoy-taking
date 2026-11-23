#----- Lia's code: check the phone's button rules (screen_ui.py) on all 5 test cases, no phone needed -----
r"""Plays TC01-TC05 (answer-sheet patient + simulated CHW, keyword app, no AI) in both intake modes and
checks android/app/src/main/python/screen_ui.py at every question the app asks:
  - on numbered questions, the option buttons are exactly the options the app just listed (1..n), and
  - every Keep? / Correct? / y-n question gets Yes / No buttons; text boxes get none.
Ends with "PROBLEMS: 0" when everything matches.

How to run (from the project folder):
  Windows (PowerShell):
    $PROTOCOLS = "..\intelehealth-ayu-protocols\protocols\v2\All Protocols (JSON)"
    python test_screen_ui.py . "$PROTOCOLS"
  Mac (Terminal):
    PROTOCOLS="../intelehealth-ayu-protocols/protocols/v2/All Protocols (JSON)"
    python test_screen_ui.py . "$PROTOCOLS"
"""
import collections, json, os, re, sys
repo = sys.argv[1]; protocols = sys.argv[2]
sys.path.insert(0, repo); sys.path.insert(0, os.path.join(repo, "android/app/src/main/python"))
import main
from keyword_mapper import KeywordMapper
from sim_patient import SheetPatient, SimulatedCHW
import screen_ui

class Watch:
    def __init__(self, inner):
        self.inner, self.state, self.listed = inner, screen_ui.ScreenState(), []
        self.kinds, self.problems, self.titles, self.asks = collections.Counter(), [], collections.Counter(), 0
    def show(self, text=""):
        summary_seen = self.state.in_summary
        for line, style in self.state.saw(text):
            if "SUMMARY FOR THE DOCTOR" in line: summary_seen = True
            if style == "question":
                self.titles[line.strip()[:70]] += 1
                if summary_seen: self.problems.append(("title styled inside the summary", line))
        for line in text.split("\n"):
            m = screen_ui.OPTION_LINE.match(line)
            if m:
                if m.group(1) == "1": self.listed = []
                self.listed.append((m.group(1), m.group(2).strip()))
            elif line.strip() and not line.startswith("   ("): pass
        self.inner.show(text)
    def ask(self, prompt):
        self.asks += 1
        kind, buttons, multi = self.state.buttons_for(prompt)
        self.kinds[(kind, re.sub(r"[:].*|Suggested: .*|Patient already said: .*|RED-FLAG CHECK: .*", lambda m: m.group(0)[:22], prompt.strip())[:60])] += 1
        if kind == "options":
            if not buttons: self.problems.append(("no option buttons", prompt))
            if buttons != self.listed: self.problems.append(("buttons differ from list", prompt, buttons[:3], self.listed[:3]))
            nums = [int(n) for n, _ in buttons]
            if nums != list(range(1, len(nums) + 1)): self.problems.append(("numbers not 1..n", nums))
        reply = self.inner.ask(prompt)
        if kind == "options" and reply.strip().isdigit() and not any(n == reply.strip() for n, _ in buttons):
            self.problems.append(("typed number has no button", prompt, reply))
        if kind == "yes_no" and reply.strip().lower() not in ("y", "n", "yes", "no", "", "?", "u", "x"):
            self.problems.append(("yes/no prompt got other reply", prompt, reply))
        return reply

# A long answer with a line break (e.g. pasted): its second line must not look like a question title.
check = screen_ui.ScreenState()
styles = [style for _, style in check.saw("\nDo you have the following symptom(s)?")]
styles += [style for _, style in check.saw("   Other [describe] (text): I have a cough and chest\ntightness. No fever")]
styles += [style for _, style in check.saw('Patient\'s own words: "Hi doctor. So I have had trouble\nbreathing for years."')]
if styles != ["plain", "question", "plain", "plain", "plain", "plain"]:
    print("STYLE CHECK FAILED:", styles); sys.exit(1)

cases = json.load(open(os.path.join(repo, "eval_cases.json")))["cases"]
sheets = json.load(open(os.path.join(repo, "eval_patient_answers.json")))
total = collections.Counter(); problems = []; titles = collections.Counter(); asks = 0
for mode in ("one", "group"):
    for case in cases:
        chw = SimulatedCHW(case, SheetPatient(case, sheets[case["id"]]))
        w = Watch(chw)
        main.run_visit(w, KeywordMapper(), protocols, intake_mode=mode) if "intake_mode" in main.run_visit.__code__.co_varnames else main.run_visit(w, KeywordMapper(), protocols)
        total.update(w.kinds); problems += [(mode, case["id"]) + p for p in w.problems]; titles.update(w.titles); asks += w.asks
print("prompts checked:", asks)
by_kind = collections.Counter()
for (k, p), n in total.items(): by_kind[k] += n
print("by kind:", dict(by_kind))
for (k, p), n in sorted(total.items()): print(f"  {k:8} {n:4}  {p}")
print("\nPROBLEMS:", len(problems))
for p in problems[:30]: print("  ", p)
print("\nlines styled as QUESTION title (count):")
for t, n in sorted(titles.items()): print(f"  {n:3} {t}")
#----- end of Lia's code -----
