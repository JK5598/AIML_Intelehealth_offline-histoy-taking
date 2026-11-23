"""Scripted visits for Difficulty breathing and Cough (no AI, no person). Checks that a past-history question
the complaint questions already asked (smoking, hospital stay) is filled from the earlier answer and confirmed
by the CHW, not asked again; that nothing is lost when the CHW says no; and that a narrower earlier "no"
(allergies to food/insects/latex) is not reused.
Run: python3 test_repeated_questions.py "$PROTOCOLS"   (ends with "Repeated-question check OK")"""

import sys

import protocols as p
from intake import Intake
from keyword_mapper import KeywordMapper


COMPLAINT_QUESTIONS = [
    "Do you smoke or have ever smoked?",
    "Do you smoke/have ever smoked?",
    "Have you had a recent period of prolonged immobilization (ie.hospitalization)?",
    "Any known allergies to food/insects/latex",
]

# What the CHW types, by question (for choices) or by the label in the prompt (for typed values)
REPLIES = {
    "Do you smoke or have ever smoked?": "1",
    "Do you smoke/have ever smoked?": "1",
    "How many cigarettes per day did you smoke?": "10 to 15",
    "[Enter since when]": "10 years",
    "Yes [Describe in your words]": "10 to 15 cigarettes a day for 10 years",
    "Have you had a recent period of prolonged immobilization (ie.hospitalization)?": "3",
    "When": "two months ago",
    "How long": "5 days",
    "Reason": "my breathing got worse",
    "Any known allergies to food/insects/latex": "1",
    "Do you have a history of any of the following?": "1",
    "Diagnosed on": "2015",
    "Current medication": "2",
    "When did it occur?": "two months ago",
    "How long were you hospitalized?": "5 days",
    "Have you recently taken any kind of medicine (including ayurvedic/homeopathic/unani/herbal)?": "1",
    "Do you have any allergies?": "2",
    "Do you chew tobbaco?": "1",
    "Smoking history": "2",
    "Since": "10 years",
    "How many cigarettes per day do you smoke?": "10 to 15",
    "Alcohol use": "2",
}


class ScriptedMapper(KeywordMapper):
    """Stands in for the AI: fills a typed value only from an earlier smoking or hospital answer,
    so this test checks the intake, not the model."""

    VALUES = {"Since": "10 years", "How many cigarettes per day do you smoke?": "10 to 15",
              "When did it occur?": "two months ago", "Reason": "my breathing got worse",
              "How long were you hospitalized?": "5 days"}

    def value_from_story(self, question_text, story):
        if not story.startswith(("Do you smoke", "Have you had a recent period")):
            return ""
        return self.VALUES.get(question_text, "FILLED BY MISTAKE")


HISTORY = "Do you have a history of any of the following?"


class ScriptedConsole:
    def __init__(self, keep):
        self.keep = keep   # what the CHW answers to "Patient already said: ... Keep?"
        self.log = []
        self.question = ""

    def show(self, text=""):
        self.log.append(text)
        if text and not text.startswith(" "):
            self.question = text.replace(" (choose one or more)", "")

    def ask(self, prompt):
        prompt = prompt.strip()
        required = self.log and self.log[-1].strip().startswith("This")
        if "Keep?" in prompt:
            reply = self.keep
        elif "Correct?" in prompt or "Save as 'No'?" in prompt:
            reply = "y"
        elif prompt.startswith("RED-FLAG CHECK"):
            reply = "n"
        elif prompt.startswith("Number(s)") and self.question == HISTORY and self.keep == "n":
            reply = "1,11"   # the full list: High BP and Hospitalization
        elif prompt.startswith("Number(s)"):
            reply = "1" if required else REPLIES.get(self.question, "")
        else:   # a typed value: "<label> (<kind>) (? = explain):"
            reply = "unknown" if required else REPLIES.get(prompt.rsplit(" (", 2)[0], "")
        self.log.append(f"{prompt} >>> {reply}")
        return reply


def run(folder, keep, complaint="Difficulty breathing"):
    console = ScriptedConsole(keep)
    intake = Intake({"age": 50.0, "sex": "male"}, ScriptedMapper(), console)
    intake.complaint = complaint
    protocol = p.load_protocol(folder, complaint)
    hpi = {"options": [q for q in p.children(protocol) if p.display_text(q) in COMPLAINT_QUESTIONS]}
    intake.run_section(hpi, "hpi", use_story=True)
    intake.run_section(p.load_protocol(folder, "patHist"), "past_history")
    return console.log, intake.answers


def saved(answers, question):
    return [a for a in answers if a["question"] == question and a["status"] == "present"]


def main(folder):
    results = []

    def check(name, ok):
        results.append(ok)
        print(f"   {'OK ' if ok else 'X  '} {name}")

    print("Difficulty breathing, CHW keeps the answers filled from the earlier answer:")
    log, answers = run(folder, keep="y")
    text = "\n".join(log)
    history = saved(answers, "Do you have a history of any of the following?")
    check("history list: Hospitalization filled from the earlier answer and confirmed, not asked again",
          "Patient already said: Hospitalization. Keep? (y/n) >>> y" in text and "11. Hospitalization" not in text
          and history and history[0]["answers"] == ["Hospitalization"] and history[0]["source"] == "from earlier answer")
    check("the CHW sees which answer it comes from",
          "(From the earlier answer: Have you had a recent period of prolonged immobilization" in text)
    check("its follow-ups filled and confirmed too: When, Reason, How long",
          [a["value"] for a in saved(answers, "When did it occur?")] == ["two months ago"]
          and [a["value"] for a in saved(answers, "How long were you hospitalized?")] == ["5 days"]
          and "When did it occur? (date)" not in text)
    check("the rest of the history list is still asked ('Anything else'), High BP saved with its own follow-ups",
          "Anything else for this question?" in text
          and any(a["answers"] == ["High Blood Pressure"] for a in history)
          and [a["value"] for a in saved(answers, "Diagnosed on")] == ["2015"])
    check("smoking: 'Yes, 10 to 15 a day' doesn't say current or ex, so the CHW picks; Since and cigarettes are filled",
          "1. Never-smoker" in text
          and [a["source"] for a in saved(answers, "Smoking history")] == ["tapped"]
          and [(a["value"], a["source"]) for a in saved(answers, "Since")] == [("10 years", "from earlier answer")]
          and [a["value"] for a in saved(answers, "How many cigarettes per day do you smoke?")] == ["10 to 15"])
    check("nothing filled where it should not be", "FILLED BY MISTAKE" not in text)
    allergies = saved(answers, "Do you have any allergies?")
    check("allergies asked as usual (an earlier 'no' to food/insects/latex says nothing about other allergies)",
          "1. Yes [Describe]" in text and [a["source"] for a in allergies] == ["tapped"])

    print("Cough, CHW keeps the answers filled from the earlier answer:")
    log, answers = run(folder, keep="y", complaint="Cough")
    text = "\n".join(log)
    check("Smoking history is not asked again: Cough 'Yes' -> Current-smoker, confirmed by the CHW",
          "1. Never-smoker" not in text and "Patient already said: Current-smoker. Keep? (y/n) >>> y" in text
          and [(a["answers"], a["source"]) for a in saved(answers, "Smoking history")]
          == [(["Current-smoker"], "from earlier answer")])
    check("Since and cigarettes per day filled and confirmed",
          [a["value"] for a in saved(answers, "Since")] == ["10 years"]
          and [a["value"] for a in saved(answers, "How many cigarettes per day do you smoke?")] == ["10 to 15"]
          and "Since (duration)" not in text)

    print("Difficulty breathing, CHW says no to every filled-in answer:")
    log, answers = run(folder, keep="n")
    text = "\n".join(log)
    check("the whole history list is shown, Hospitalization and its follow-ups typed by the CHW",
          "11. Hospitalization" in text and "When did it occur? (date) (? = explain): >>> two months ago" in text)
    check("Since and cigarettes per day are typed by the CHW", "Since (duration) (? = explain): >>> 10 years" in text
          and [a["value"] for a in saved(answers, "How many cigarettes per day do you smoke?")] == ["10 to 15"])

    print(f"   repeated-question checks correct: {sum(results)}/{len(results)}")
    if not all(results):
        print("Repeated-question check FAILED")
        sys.exit(1)
    print("Repeated-question check OK")


if __name__ == "__main__":
    main(sys.argv[1])
