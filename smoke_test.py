import json
import sys

from main import run_visit
from keyword_mapper import KeywordMapper


class AutoConsole:
    """Answers every prompt with a simple rule, so the whole flow can run without a person."""

    def __init__(self, complaint_words, story, quiet=True):
        self.complaint_words = complaint_words
        self.story = story
        self.quiet = quiet
        self.log = []
        self.help_asked_on_choice = False
        self.help_asked_on_option = False
        self.help_asked_on_value = False

    def show(self, text=""):
        self.log.append(text)
        if not self.quiet:
            print(text)

    def ask(self, prompt):
        if "age" in prompt:
            reply = "34"
        elif "sex" in prompt:
            reply = "female"
        elif "Number, or type" in prompt:
            reply = self.complaint_words
        elif "tell me more" in prompt:
            reply = self.story
        elif "Correct?" in prompt or "Keep?" in prompt or "Save as 'No'?" in prompt:
            reply = "y"
        elif "Number(s)" in prompt and not self.help_asked_on_choice:
            reply = "?"
            self.help_asked_on_choice = True
        elif "Number(s)" in prompt and not self.help_asked_on_option:
            reply = "?2"
            self.help_asked_on_option = True
        elif "Number(s)" in prompt:
            reply = "1"
        elif not self.help_asked_on_value:
            reply = "?"
            self.help_asked_on_value = True
        else:
            reply = "3 days"
        self.log.append(prompt + " " + reply)
        if not self.quiet:
            print(prompt, reply)
        return reply


def check_help(console, visit):
    """The CHW typed '?' twice and '?2' once. Explanations must have been shown, and '?' must never be saved."""
    explanations_shown = 0
    for line in console.log:
        if "Simple explanation" in line:
            explanations_shown += 1
    saved_question_marks = 0
    for answer in visit["answers"]:
        for text in (answer["value"], answer["patient_words"]):
            if text and text.startswith("?"):
                saved_question_marks += 1
    print(f"Help check: '?' or '?2' typed 3 times, explanations shown {explanations_shown} times, "
          f"'?' saved as an answer {saved_question_marks} times")
    if explanations_shown != 3 or saved_question_marks != 0:
        print("Help check FAILED")
        sys.exit(1)
    print("Help check OK")


if __name__ == "__main__":
    folder = sys.argv[1]
    mapper = KeywordMapper()
    if len(sys.argv) > 2:
        from ai_mapper import AIMapper
        story_check = "yes_no"
        if len(sys.argv) > 3:
            story_check = sys.argv[3]
        mapper = AIMapper(sys.argv[2], story_check=story_check)
    console = AutoConsole("my stomach pain", "Pain near my right ribs for 3 days, I vomited twice, no fever.", quiet=False)
    visit = run_visit(console, mapper, folder)
    with open("smoke_visit.json", "w", encoding="utf-8") as f:
        json.dump(visit, f, indent=2, ensure_ascii=False)
    print(json.dumps({"chief_complaint": visit["chief_complaint"], "red_flags": visit["red_flags"]}, indent=2))
    run_info = dict(visit["run_info"])
    run_info.pop("ai_timings")
    run_info.pop("rejected_suggestions")
    run_info.pop("ai_explanations")
    print(json.dumps(run_info, indent=2))
    print("Full record saved to smoke_visit.json")
    check_help(console, visit)
