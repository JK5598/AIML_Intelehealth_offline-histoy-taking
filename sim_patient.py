"""The simulated patient and the simulated CHW for the evaluation loop (evaluate_visits.py).

The CHW is plain code: it reads what the app shows, asks the patient, and types the patient's
words into the app, like a real CHW would. The patient is Claude (or, with --offline, a simple
word-matching stand-in) and only knows the case story. Nothing here changes the app.
"""
import re

OPTION_LINE = re.compile(r"^\s+(\d+)\. (.+)$")
GROUP_LINE = re.compile(r"^\s+Q(\d+)\. (.+?)(\s+\(asked on its own after this\))?$")
CHECK_LINE = re.compile(r"^\s+Q(\d+)\. (.+) -> (.+)$")

MAX_PROMPTS = 400   # a visit that needs more than this is stuck in a loop


def patient_system_prompt(case):
    text = (f"You are role-playing a patient at a rural clinic in India, talking to a community health "
            f"worker (CHW). You are a {case['age']}-year-old {case['sex']}.\n\n"
            "Everything you know about your problem:\n")
    text += "\n".join(case["story"])
    if case["only_if_asked"]:
        text += f"\n\nOnly if the CHW asks about it: {case['only_if_asked']}"
    text += ("\n\nRules:\n"
             "- Answer only what the CHW asks, in 1-2 short everyday sentences, the way a patient talks.\n"
             "- Use only facts from the description above. Never invent symptoms, numbers, dates, "
             "medicines or history.\n"
             "- If the description does not say, answer \"I'm not sure\" or \"not that I know of\".\n"
             "- Do not use medical words the description does not use. Never name a diagnosis.\n"
             "- When the CHW reads out a list of choices, say which ones you have and which you don't, "
             "only for the ones the description covers.\n"
             "- The CHW may use medical words when checking an answer; you understand what they mean.")
    return text


def examiner_system_prompt(case):
    """Red-flag checks are often things the CHW looks at (sunken eyes, fast breathing), not things the
    patient can say. The CHW answers those from the case's exam findings."""
    return (f"You are the community health worker examining a {case['age']}-year-old {case['sex']}.\n"
            f"What the patient told you: {' '.join(case['story'])}\n"
            f"Only if asked: {case['only_if_asked'] or '(nothing)'}\n"
            f"What you find when you examine the patient: {case['exam_findings_not_for_patient'] or '(nothing abnormal written down)'}\n\n"
            "Answer the check from the story and the exam findings only. Teaching cases write down only the "
            "abnormal findings, so if something is not mentioned, answer no. Answer unsure only when the story "
            "itself says the patient is unsure.")


class ClaudePatient:
    def __init__(self, case, claude, model):
        self.case = case
        self.claude = claude
        self.model = model
        self.system = patient_system_prompt(case)
        self.examiner = examiner_system_prompt(case)

    def say(self, prompt, max_tokens=150):
        return self.claude.ask(self.model, self.system, prompt, max_tokens)

    def opening(self):
        return self.say("The CHW says: \"What brings you here today? Tell me about the problem in your "
                        "own words.\" Answer in 2-4 sentences.", 250)

    def answer(self, question, options):
        prompt = f"The CHW asks: \"{question}\""
        if options:
            prompt += "\nThe CHW reads out the choices: " + "; ".join(options)
        return self.say(prompt + "\nAnswer in your own words.")

    def answer_group(self, questions):
        prompt = "The CHW asks you these questions together:\n" + "\n".join(f"- {q}" for q in questions)
        return self.say(prompt + "\nAnswer them all in a few sentences, in your own words.", 300)

    def choose(self, question, options):
        """The CHW shows the choices and asks which are true. Returns numbers like '2,5', or ''."""
        lines = "\n".join(f"{number}. {label}" for number, label in enumerate(options, start=1))
        reply = self.say(f"The CHW asks: \"{question}\" and shows you the choices:\n{lines}\n"
                         "Which numbers are true for you? Reply with the numbers only, separated by commas, "
                         "or the word none.", 20)
        numbers = [n for n in re.findall(r"\d+", reply) if 1 <= int(n) <= len(options)]
        return ",".join(numbers)

    def check(self, statement, **details):
        """The CHW checks one statement with the patient. Returns 'yes', 'no' or 'unsure'."""
        reply = self.say(f"The CHW checks with you: \"{statement}\" Is that right?\n"
                         "Reply with exactly one word: yes, no, or unsure.", 10)
        return first_word(reply)

    def yes_no(self, question):
        reply = self.say(f"The CHW asks: \"{question}\"\nReply with exactly one word: yes, no, or unsure.", 5)
        return first_word(reply)

    def observe(self, question):
        """A red-flag check, answered by the CHW from the story and the exam findings."""
        reply = self.claude.ask(self.model, self.examiner,
                                f"Red-flag check: \"{question}\"\nReply with exactly one word: yes, no, or unsure.", 5)
        return first_word(reply)


def first_word(reply):
    words = re.findall(r"[a-z]+", reply.lower())
    if not words:
        return "unsure"
    if words[0] in ("yes", "no"):
        return words[0]
    return "unsure"


class ScriptedPatient:
    """--offline stand-in: answers with the story sentences that share words with the question.
    Good enough to test that the loop runs end to end; NOT a real patient, so its scores mean nothing."""

    def __init__(self, case):
        self.case = case
        text = " ".join(case["story"]) + " " + case["only_if_asked"]
        self.sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

    def best_sentences(self, words, how_many=2):
        wanted = {w for w in re.findall(r"[a-z]+", words.lower()) if len(w) > 3}
        scored = []
        for sentence in self.sentences:
            have = set(re.findall(r"[a-z]+", sentence.lower()))
            overlap = len(wanted & have)
            if overlap:
                scored.append((overlap, sentence))
        scored.sort(key=lambda pair: -pair[0])
        return " ".join(sentence for _, sentence in scored[:how_many])

    def opening(self):
        return " ".join(self.sentences[:3])

    def answer(self, question, options):
        return self.best_sentences(question + " " + " ".join(options)) or "I'm not sure."

    def answer_group(self, questions):
        return self.best_sentences(" ".join(questions), 4) or "I'm not sure."

    def choose(self, question, options):
        story = " ".join(self.sentences).lower()
        numbers = []
        for number, label in enumerate(options, start=1):
            words = [w for w in re.findall(r"[a-z]+", label.lower()) if len(w) > 3]
            if words and all(w in story for w in words):
                numbers.append(str(number))
        return ",".join(numbers)

    def check(self, statement, **details):
        return "yes" if self.best_sentences(statement) else "unsure"

    def yes_no(self, question):
        return "yes" if self.best_sentences(question) else "no"

    def observe(self, question):
        return self.yes_no(question)


class SheetPatient:
    """A patient whose answers were written in advance, one per question (eval_patient_answers.json).
    The same answers every run, so two versions of the app can be compared fairly, and teammates can
    read and correct them. Each question has:
      "say": the patient's own words,  "has": the option labels that are true,  "not": labels the patient denies,
      "accept": for typed values, words that a correct value contains (e.g. ["2 day", "two day"]).
    Questions missing from the sheet are collected in self.missing so they can be added."""

    def __init__(self, case, sheet):
        self.case = case
        self.sheet = sheet
        self.questions = sheet["questions"]
        self.missing = []

    def entry(self, question):
        if question in self.questions:
            return self.questions[question]
        if question not in self.missing:
            self.missing.append(question)
        return {}

    def opening(self):
        return self.sheet["opening"]

    def answer(self, question, options):
        return self.entry(question).get("say", "I'm not sure.")

    def answer_group(self, questions):
        return " ".join(self.entry(q).get("say", "") for q in questions).strip() or "I'm not sure."

    def choose(self, question, options):
        has = self.entry(question).get("has", [])
        return ",".join(str(n) for n, label in enumerate(options, start=1) if label in has)

    def check(self, statement, question=None, shown=None, kind="has", **details):
        entry = self.entry(question) if question else {}
        if kind == "not":
            labels = set(entry.get("not", [])) | set(self.sheet.get("denies", []))
        else:
            labels = set(entry.get("has", []))
        if shown is None:
            return "unsure"
        if entry.get("accept") and kind == "has":
            return "yes" if any(word.lower() in shown.lower() for word in entry["accept"]) else "no"
        if covered_by(shown, labels):
            return "yes"
        return "no"

    def yes_no(self, question):
        checks = self.sheet.get("checks", {})
        if question in checks:
            return checks[question]
        if question.startswith("Do you have ") and question.endswith("?"):
            label = question[len("Do you have "):-1]
            if any(label in e.get("has", []) for e in self.questions.values()):
                return "yes"
            if label in self.sheet.get("denies", []) or any(label in e.get("not", []) for e in self.questions.values()):
                return "no"
        if question not in self.missing:
            self.missing.append(question)
        return "unsure"

    def observe(self, question):
        return self.yes_no(question)


def covered_by(shown, labels):
    """True if the shown text is made only of these labels (labels may contain commas themselves)."""
    rest = shown
    for label in sorted(labels, key=len, reverse=True):
        rest = rest.replace(label, "")
    return bool(labels) and rest.replace(",", "").strip() == "" and rest != shown


class SimulatedCHW:
    """Plays the CHW at the app's console. careful=True: every AI suggestion is checked with the
    patient (the app's real design). careful=False: the CHW accepts every suggestion (stress test)."""

    def __init__(self, case, patient, careful=True):
        self.case = case
        self.patient = patient
        self.careful = careful
        self.screen = []          # lines the app showed since the CHW last typed
        self.transcript = []      # everything shown and typed, for people to read
        self.conversation = []    # only what the CHW typed, with the question it was for (for the judge)
        self.question = ""
        self.options = []
        self.last_words = ""      # the patient's last answer, as typed into the app
        self.word_tries = 0       # how often the patient's words were typed for this question
        self.number_tries = 0     # how often the CHW picked numbers itself for this question
        self.group = []
        self.prompts = 0
        self.multi = True
        self.forced_pick = False
        self.notes = {"confirmations": 0, "chw_picked_numbers": 0, "skipped": 0, "checks_said_no": 0}

    # ----- the console the app talks to -----

    def show(self, text=""):
        self.screen.append(text)
        self.transcript.append(text)

    def ask(self, prompt):
        self.prompts += 1
        if self.prompts > MAX_PROMPTS:
            raise RuntimeError("The visit seems stuck in a loop (over %d prompts)." % MAX_PROMPTS)
        self.read_screen()
        reply = self.reply_to(prompt.strip())
        self.screen = []
        self.transcript.append(f"{prompt}  >>> {reply}")
        line = f"[{self.question}] {prompt.strip()} >>> {reply}"
        if self.forced_pick:
            line += "   (FORCED PICK: the patient gave no usable answer, the simulated CHW had to choose)"
            self.forced_pick = False
        self.conversation.append(line)
        return reply

    # ----- reading the screen -----

    def read_screen(self):
        options = []
        question = ""
        for position, line in enumerate(self.screen):
            match = OPTION_LINE.match(line)
            if match and int(match.group(1)) == len(options) + 1:
                if not options:
                    question = previous_text(self.screen, position)
                options.append(match.group(2).strip())
        if options:
            self.multi = question.endswith("(choose one or more)")
            self.new_question(question.replace(" (choose one or more)", ""), options)
            return
        groups = [GROUP_LINE.match(line) for line in self.screen]
        group = [m.group(2).strip() for m in groups if m and " -> " not in m.group(2)]
        if group and any("Question group" in line for line in self.screen):
            self.group = group
            return
        text = [line.strip() for line in self.screen if line.strip() and not line.strip().startswith("(")]
        if text and not text[-1].startswith(("!!!", "??", ">>", "From the patient", "Patient's words",
                                             "---", "Q", "There is no", "Not sure", "This", "Please", "That")):
            self.new_question(text[-1], [])

    def new_question(self, question, options):
        self.question = question
        self.options = options
        self.word_tries = 0
        self.number_tries = 0

    # ----- what the CHW types -----

    def reply_to(self, prompt):
        if prompt.startswith("Patient age"):
            return str(self.case["age"])
        if prompt.startswith("Patient sex"):
            return self.case["sex"]
        if prompt.startswith("Number, or type the patient's words"):
            return self.pick_complaint()
        if "tell me more about the problem" in prompt:
            self.last_words = self.patient.opening()
            return self.last_words
        if prompt.startswith("RED-FLAG CHECK:"):
            question = prompt[len("RED-FLAG CHECK:"):].split(" (y = yes")[0].strip()
            return {"yes": "y", "no": "n"}.get(self.patient.observe(question), "d")
        if prompt.startswith("Suggested:") or prompt.startswith("Patient already said:"):
            shown = prompt.split(":", 1)[1].rsplit(". ", 1)[0].strip()
            return self.check(f"For \"{self.question}\", the answer is: {shown}.", self.question, shown, "has")
        if prompt.startswith("Patient said they do NOT have:"):
            shown = prompt.split(":", 1)[1].split(". Save as")[0].strip()
            return self.check(f"You do NOT have: {shown}.", self.question, shown, "not")
        if prompt.startswith("Number(s), or type the patient's words"):
            return self.answer_choices()
        if prompt.startswith("Type the patient's reply to these questions"):
            self.last_words = self.patient.answer_group(self.group)
            return self.last_words
        if prompt.startswith("Save these?"):
            return self.check_group()
        if prompt.startswith("Which is right?"):
            label = disagree_label(self.transcript)
            answer = self.patient.yes_no(f"Do you have {label}?")
            return {"yes": "y", "no": "n"}.get(answer, "u")
        if prompt.endswith("(? = explain):"):
            question = prompt.rsplit(" (", 2)[0].strip()
            return self.answer_value(question)
        self.notes["skipped"] += 1
        return ""   # anything else: press Enter

    def pick_complaint(self):
        for number, name in enumerate(self.options, start=1):
            if name.lower() == self.case["complaint"].lower():
                return str(number)
        raise RuntimeError(f"Complaint {self.case['complaint']!r} is not in the app's list.")

    def answer_choices(self):
        """First the patient's own words (this is what tests the AI). If the app can't use them,
        or the patient said its suggestion was wrong, the CHW picks the numbers, as a real CHW would."""
        if self.word_tries == 0:
            self.word_tries += 1
            self.last_words = self.patient.answer(self.question, self.options)
            return self.last_words
        self.number_tries += 1
        if self.number_tries == 1:
            self.notes["chw_picked_numbers"] += 1
            picked = self.patient.choose(self.question, self.options)
            if not self.multi:
                picked = picked.split(",")[0]   # single-choice question: only the first
            return picked
        # The app says the question is required and nothing the patient said fits. The CHW has to pick
        # something: "unknown" if there is one, else "none"/"no", else "other", else the first option.
        # These picks come from the simulation, not the app, so they are marked for the judge.
        self.notes["forced_picks"] = self.notes.get("forced_picks", 0) + 1
        self.forced_pick = True
        for words in (("unknown", "not sure", "don't know"), ("none", "never", "no "), ("other",)):
            for number, label in enumerate(self.options, start=1):
                text = label.lower() + " "
                if any(text.startswith(word) or f" {word}" in f" {text}" for word in words):
                    return str(number)
        return "1"

    def answer_value(self, question):
        self.last_words = self.patient.answer(question, [])
        return self.last_words or "not sure"

    def check(self, statement, question=None, shown=None, kind="has"):
        self.notes["confirmations"] += 1
        if not self.careful:
            return "y"
        answer = self.patient.check(statement, question=question, shown=shown, kind=kind)
        if answer != "yes":
            self.notes["checks_said_no"] += 1
        return "y" if answer == "yes" else "n"

    def check_group(self):
        lines = [CHECK_LINE.match(line) for line in self.screen]
        checks = [(m.group(1), m.group(2), m.group(3)) for m in lines if m]
        self.notes["confirmations"] += 1
        if not self.careful or not checks:
            return "y"
        wrong = []
        for position, question, shown in checks:
            if self.patient.check(f"For \"{question}\", the answer is: {shown}.",
                                  question=question, shown=shown, kind="has") != "yes":
                wrong.append(position)
        self.notes["checks_said_no"] += len(wrong)
        if not wrong:
            return "y"
        if len(wrong) == len(checks):
            return "n"
        return ",".join(wrong)


def previous_text(lines, position):
    for line in reversed(lines[:position]):
        if line.strip():
            return line.strip()
    return ""


def disagree_label(transcript):
    for line in reversed(transcript):
        match = re.search(r'said NO to "(.+?)"', line)
        if match:
            return match.group(1)
    return "this"
