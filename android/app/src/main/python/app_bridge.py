"""The bridge between the Android screen (Kotlin) and our Python prototype.
Our code talks to a "console" with two functions: show(text) and ask(prompt). On the laptop that is
print() and input(). Here, show() and ask() go to the phone screen, and the CHW's typed answer comes
back through answer(). The visit itself is the same run_visit() as on the laptop."""
import json
import os
import queue
import sys
import time

import explanations
import judge
import main
from keyword_mapper import KeywordMapper
from sim_patient import SheetPatient, SimulatedCHW
#----- Lia's code: screen rules for the round 1 UI fixes, and Back / End this visit (round 2) -----
import screen_ui
from visit_replay import BACK, END, AnswerMemory, EndVisit, GoBack
#----- end of Lia's code -----



class PhoneConsole:
    def __init__(self, screen):
        self.screen = screen            # the Kotlin side (MainActivity's Screen)
        self.answers = queue.Queue()    # answers typed on the phone wait here
        #----- Lia's code: remember the options on screen, so the phone can show the right buttons -----
        self.state = screen_ui.ScreenState()
        #----- end of Lia's code -----
        #----- Lia's code: remember every answer, so Back can replay the visit without the last one -----
        self.history = []      # every answer the CHW sent in this visit, in order
        self.replay = []       # answers still to give back during a replay after Back
        self.back_presses = 0
        #----- end of Lia's code -----

    def show(self, text=""):
        #----- Lia's code: send each line with its style (section / question / red flag / plain) -----
        for line, style in self.state.saw(text):
            self.screen.showStyled(line, style)
        #----- end of Lia's code -----

    def ask(self, prompt):
        #----- Lia's code: replay after Back: give the remembered answer back straight away -----
        if self.replay:
            reply = self.replay.pop(0)
            self.screen.showStyled(">> " + prompt.strip() + "  " + reply, "plain")
            return reply
        #----- end of Lia's code -----
        while True:
            #----- Lia's code: send the buttons that fit this question (options, Yes/No, or none for typing) -----
            kind, buttons, multi = self.state.buttons_for(prompt)
            self.screen.askWith(prompt, kind, json.dumps(buttons), multi)
            #----- end of Lia's code -----
            reply = self.answers.get().strip()   # wait until the CHW taps Send / Skip / an option button
            #----- Lia's code: one clean line: line breaks (e.g. from pasting) and double spaces become one space -----
            reply = " ".join(reply.split())
            #----- end of Lia's code -----
            #----- Lia's code: Back removes the last answer and starts the replay; End stops the visit -----
            if reply == END:
                raise EndVisit()
            if reply == BACK:
                if not self.history:
                    continue            # nothing to undo yet: ask the same question again
                self.history.pop()
                self.back_presses += 1
                raise GoBack()
            self.history.append(reply)
            #----- end of Lia's code -----
            return reply


current_console = None


def answer(text):
    """Called by the screen when the CHW sends an answer."""
    current_console.answers.put(text)


loaded_ai = None   # MedPsy stays loaded between visits


def make_mapper(screen, model_path):
    """MedPsy if its model file is on the phone, otherwise keyword matching (as in milestone 2)."""
    global loaded_ai
    if loaded_ai is not None:
        loaded_ai.timings = []   # count AI time for this visit only
        screen.show("MedPsy already loaded. Matching: AI.")
        return loaded_ai
    if not os.path.exists(model_path):
        screen.show(f"No model file at {model_path}\nMatching: keywords (no AI).")
        return KeywordMapper()
    from ai_mapper import AIMapper   # imported here, so the keyword app works without the engine
    screen.show("Loading MedPsy (" + os.path.basename(model_path) + ")...")
    started = time.time()
    loaded_ai = AIMapper(model_path)
    screen.show(f"MedPsy loaded in {time.time() - started:.1f} s. Matching: AI.")
    return loaded_ai


def ai_time_report(mapper):
    """One line per kind of AI task: how many calls and how many seconds on this phone."""
    if not hasattr(mapper, "timings") or not mapper.timings:
        return ""
    tasks = {}
    for timing in mapper.timings:
        count, seconds = tasks.get(timing["task"], (0, 0.0))
        tasks[timing["task"]] = (count + 1, seconds + timing["seconds"])
    total = sum(t["seconds"] for t in mapper.timings)
    prompt_tokens = sum(t["prompt_tokens"] for t in mapper.timings)
    output_tokens = sum(t["output_tokens"] for t in mapper.timings)
    lines = [f"AI on this phone: {len(mapper.timings)} calls, {total:.1f} s ({total / 60:.1f} min), "
             f"{prompt_tokens} tokens read, {output_tokens} written"]
    for task, (count, seconds) in sorted(tasks.items(), key=lambda item: -item[1][1]):
        lines.append(f"  {task}: {count} calls, {seconds:.1f} s ({seconds / count:.2f} s each)")
    return "\n".join(lines)


def run_visit(screen, protocol_folder, save_folder, model_path):
    """Runs one whole visit, then saves it and shows the summary and the AI time."""
    global current_console
    current_console = PhoneConsole(screen)
    terms, questions = explanations.load()
    screen.show(f"Python {sys.version.split()[0]} on the phone. Checked explanations loaded: "
                f"{len(terms)} terms, {len(questions)} questions.")
    mapper = make_mapper(screen, model_path)

    #----- Lia's code: Back = start the visit again and replay the answers; End = stop without saving -----
    first_start = time.time()
    memory = AnswerMemory(mapper)
    try:
        while True:
            current_console.replay = list(current_console.history)
            current_console.state = screen_ui.ScreenState()
            try:
                visit = main.run_visit(current_console, mapper, protocol_folder)
                break
            except GoBack:
                screen.clearLog()
                screen.show("(Back: the last answer was removed. Replaying the earlier answers...)")
    except EndVisit:
        screen.ended("Visit ended. Nothing was saved.")
        return
    finally:
        memory.stop()
    # The replay restarts main.run_visit's clock, so use the real start; count Back taps too.
    visit["run_info"]["minutes"] = round((time.time() - first_start) / 60, 2)
    visit["run_info"]["back_presses"] = current_console.back_presses
    #----- end of Lia's code -----

    report = ai_time_report(mapper)
    if report:
        screen.show("\n" + report)
        visit["ai_timings_on_phone"] = mapper.timings

    os.makedirs(save_folder, exist_ok=True)
    path = os.path.join(save_folder, "visit_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(visit, f, indent=2, ensure_ascii=False)
    screen.finished(path)


def run_test_cases(screen, protocol_folder, save_folder, model_path):
    """Plays the 5 test cases (TC01-TC05) on the phone with no typing: the answer-sheet patient and the
    simulated CHW from the evaluation (evaluate_visits.py) answer the app. Measures the real AI time on
    this phone. Saves each visit and transcript in visits/test_runs/<time>/<case>/."""
    mapper = make_mapper(screen, model_path)
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "eval_cases.json"), encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    with open(os.path.join(here, "eval_patient_answers.json"), encoding="utf-8") as f:
        sheets = json.load(f)
    run_folder = os.path.join(save_folder, "test_runs", time.strftime("%Y%m%d_%H%M%S"))
    rows = []

    for case in cases:
        screen.show(f"\n=== {case['id']} ({case['complaint']}, {case['age']} {case['sex']}) ===")
        patient = SheetPatient(case, sheets[case["id"]])
        chw = SimulatedCHW(case, patient)
        if hasattr(mapper, "timings"):
            mapper.timings = []   # count AI time for this visit only
        started = time.time()
        visit = main.run_visit(chw, mapper, protocol_folder)
        seconds = time.time() - started

        case_folder = os.path.join(run_folder, case["id"])
        os.makedirs(case_folder, exist_ok=True)
        with open(os.path.join(case_folder, "visit.json"), "w", encoding="utf-8") as f:
            json.dump(visit, f, indent=2, ensure_ascii=False)
        with open(os.path.join(case_folder, "transcript.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(chw.transcript))

        timings = getattr(mapper, "timings", [])
        ai_seconds = sum(t["seconds"] for t in timings)
        inputs = visit["run_info"]["chw_inputs"]
        confirmations = chw.notes["confirmations"]
        chw_seconds = ((inputs - confirmations) * judge.SECONDS_PER_QUESTION
                       + confirmations * judge.SECONDS_PER_CONFIRMATION)
        visit_minutes = (chw_seconds + ai_seconds) / 60
        flags = ", ".join(visit["red_flags"]) or "none"
        screen.show(f"   done in {seconds:.0f} s. CHW inputs: {inputs} ({confirmations} y/n checks). "
                    f"AI on this phone: {len(timings)} calls, {ai_seconds:.1f} s. "
                    f"Visit estimate: {visit_minutes:.1f} min.\n   Red flags: {flags}")
        rows.append([case["id"], case["complaint"], inputs, confirmations, len(timings),
                     round(ai_seconds, 1), round(visit_minutes, 1), flags])

    with open(os.path.join(run_folder, "results.csv"), "w", encoding="utf-8") as f:
        f.write("case,complaint,chw_inputs,yes_no_checks,ai_calls,ai_seconds_phone,visit_minutes_estimate,red_flags\n")
        for row in rows:
            f.write(",".join('"' + str(value) + '"' for value in row) + "\n")

    screen.show("\nAll test cases done. AI seconds on this phone: "
                + ", ".join(f"{row[0]} {row[5]}" for row in rows))
    screen.finished(run_folder)
