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
import main
from keyword_mapper import KeywordMapper



class PhoneConsole:
    def __init__(self, screen):
        self.screen = screen            # the Kotlin side (MainActivity's Screen)
        self.answers = queue.Queue()    # answers typed on the phone wait here

    def show(self, text=""):
        self.screen.show(text)

    def ask(self, prompt):
        self.screen.ask(prompt)
        return self.answers.get().strip()   # wait until the CHW taps Send / Yes / No / Skip


current_console = None


def answer(text):
    """Called by the screen when the CHW sends an answer."""
    current_console.answers.put(text)


def make_mapper(screen, model_path):
    """MedPsy if its model file is on the phone, otherwise keyword matching (as in milestone 2)."""
    if not os.path.exists(model_path):
        screen.show(f"No model file at {model_path}\nMatching: keywords (no AI).")
        return KeywordMapper()
    from ai_mapper import AIMapper   # imported here, so the keyword app works without the engine
    screen.show("Loading MedPsy (" + os.path.basename(model_path) + ")...")
    started = time.time()
    mapper = AIMapper(model_path)
    screen.show(f"MedPsy loaded in {time.time() - started:.1f} s. Matching: AI.")
    return mapper


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

    visit = main.run_visit(current_console, mapper, protocol_folder)

    report = ai_time_report(mapper)
    if report:
        screen.show("\n" + report)
        visit["ai_timings_on_phone"] = mapper.timings

    os.makedirs(save_folder, exist_ok=True)
    path = os.path.join(save_folder, "visit_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(visit, f, indent=2, ensure_ascii=False)
    screen.finished(path)
