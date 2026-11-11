#----- Lia's code: follow-up step for the multi-question intake -----
"""Shared parts of the multi-question intake.

The multi-question intake (intake_group.py) uses this file:
  - checks for answers that are missing or unclear (vague duration, patient sounds unsure,
    a "no" and a "yes" for the same option)
  - asks each missing or unclear question ONCE more, on its own
  - saves "unsure" or "not_answered" when it still has no answer, so nothing is left blank

During a follow-up the CHW can type:
   u   the patient is unsure / doesn't know   -> saved with status "unsure"
   x   the patient gave no answer             -> saved with status "not_answered"

This file is plain code (no AI), so it works the same with or without a model.
"""
import re

import negation
import protocols as p
from intake import Intake


# ---------- Words that make an answer unclear ----------

NUMBER_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                "eleven", "twelve", "fifteen", "twenty", "thirty", "half"}
UNITS = r"(minute|min|hour|hr|day|week|wk|month|year|yr)s?"
AMOUNT = r"(\d+(\.\d+)?|" + "|".join(sorted(NUMBER_WORDS)) + r"|a|an)"
EXACT_DAY_WORDS = ["yesterday", "today", "this morning", "last night", "since birth", "day before yesterday"]

# "sometimes in a day", "twice a day": says how OFTEN, not since WHEN
FREQUENCY = r"\b(sometimes|often|usually|every|daily|weekly|once|twice|times|per|in a (day|week|month))\b"
# "for 3 days", "since 2 weeks", "2 months ago": says since WHEN
SINCE_WHEN = r"\b(for|since|ago|last|past|started|began|back)\b"


def has_amount_of_time(text):
    text = text.lower()
    if re.search(r"\b" + AMOUNT + r"\s+" + UNITS + r"\b", text):
        return True
    return any(words in text for words in EXACT_DAY_WORDS)


def is_vague_duration(value):
    """'3 days', 'for 2 weeks', 'since yesterday' are clear.
    'a while ago', 'few days', 'sometimes in a day' are vague (no amount, or how often instead of how long)."""
    text = (value or "").lower().strip()
    if not text:
        return False
    if not has_amount_of_time(text):
        return True
    if re.search(FREQUENCY, text) and not re.search(SINCE_WHEN, text):
        return True
    return False


def find_duration(text):
    """No-AI helper: copies a duration out of the patient's words ('...started 3 days ago...' -> '3 days ago').
    Only takes it when it clearly says how long: a real number ('3 days'), or 'for/since ... ago' around it.
    'in a day' alone is NOT taken, because it usually means how often."""
    text = (text or "").lower()
    pattern = r"((for|since)\s+)?" + AMOUNT + r"\s+" + UNITS + r"(\s+ago)?"
    for match in re.finditer(r"\b" + pattern + r"\b", text):
        words = match.group(0)
        amount = match.group(3)
        if amount in ("a", "an") and not (match.group(1) or words.endswith("ago")):
            continue
        return words.strip()
    for words in EXACT_DAY_WORDS:
        if words in text:
            return ("since " + words) if words == "yesterday" else words
    return ""


def unsure_words(text):
    """Returns the words that make the patient sound unsure ('maybe', 'not sure', "don't know"), or ''."""
    words = negation.tokens(text or "")
    for position, word in enumerate(words):
        if word in negation.UNSURE_WORDS:
            return word
        next_word = words[position + 1] if position + 1 < len(words) else ""
        if word in negation.NEGATION_WORDS and next_word in negation.UNSURE_AFTER_NEGATION:
            return word + " " + next_word
    return ""


def unsure_about(reply, labels):
    """Like unsure_words, but only for the part of the reply that talks about these answers.
    'nausea and vomiting, maybe fever' -> unsure about Fever ('maybe'), not about Nausea."""
    parts = re.split(r"[,.;]|\bbut\b", (reply or "").lower())
    for label in labels:
        stems = negation.label_stems(label)
        for part in parts:
            words = {negation.stem(w) for w in negation.tokens(part)}
            if (stems & words) or (label.lower() in part):
                hedge = unsure_words(part)
                if hedge:
                    return hedge
    return ""


def read_checks(answer, positions):
    """Reads the CHW's one-line check of a group's suggestions.
    'y' -> all yes; 'n' -> all no; '2' or '1,3' -> those are wrong; 'u2' -> Q2 unsure; '2 u3' mixes both.
    Returns {position: 'yes' | 'no' | 'unsure'}, or None when it can't read the answer."""
    answer = answer.strip().lower()
    if answer in ("y", "yes"):
        return {position: "yes" for position in positions}
    if answer in ("n", "no"):
        return {position: "no" for position in positions}
    decisions = {position: "yes" for position in positions}
    pieces = [piece for piece in re.split(r"[,\s]+", answer) if piece]
    if not pieces:
        return None
    for piece in pieces:
        match = re.fullmatch(r"(u?)q?(\d+)", piece)
        if not match or int(match.group(2)) not in decisions:
            return None
        decisions[int(match.group(2))] = "unsure" if match.group(1) else "no"
    return decisions


def is_no_answer_option(label):
    """Options that ARE a 'no' answer: 'No', 'None', 'No known allergies', 'Never-smoker', 'Does not move',
    'Not taking any medication', 'Do not Chew'. The 'no' check (negation.check_picks) is meant to stop the AI
    from picking a symptom the patient denied ('no fever' -> not Fever). For these options, the patient saying
    'no' is the answer itself, so they must not be thrown away."""
    words = negation.tokens(label.replace("-", " "))
    return bool(words) and (words[0] in negation.NEGATION_WORDS or words[0] in ("do", "does", "is", "has")
                            and len(words) > 1 and words[1] in ("not", "no"))


# Words in a question that don't say what it is about ("Have you recently taken any kind of medicine?" -> medicine)
QUESTION_FILLER = {"have", "does", "what", "when", "which", "your", "with", "from", "there", "been", "taken",
                   "kind", "recently", "following", "history", "including", "this", "that", "they", "were",
                   "anything", "today", "here", "coming", "before", "problem", "seen", "health", "provider",
                   "self", "home", "remedies", "medication"}


def no_option_from_reply(question_text, labels, reply):
    """Plain code, no AI: 'no medicine', 'no known allergies', 'no alcohol', 'no treatment yet' answer the
    question with its 'No' / 'None' option. The small AI often misses these, because its rules say
    'never pick something the patient said they do NOT have'.
    Returns the index of that option when the reply says 'no' to the question's own topic, else None."""
    topic = {negation.stem(w) for w in re.findall(r"[a-z]+", question_text.lower())
             if len(w) > 3 and w not in QUESTION_FILLER and w not in negation.GENERIC_WORDS}
    if not topic:
        return None
    negated, affirmed = negation.split_words(reply or "")
    said_no = topic & {negation.stem(w) for w in negated}
    said_yes = topic & {negation.stem(w) for w in affirmed}
    if not said_no or said_yes:
        return None
    for preferred in ("no", "none", "never", "not", "nil"):
        for index, label in enumerate(labels):
            words = negation.tokens(label.replace("-", " "))
            if words and words[0] == preferred:
                return index
    return None


def is_duration_question(question):
    """'Since when have you had this symptom?' has one option, '[Enter since when]', with input-type 'duration'."""
    options = p.children(question)
    if p.input_type(question) == "duration" and not options:
        return True
    return len(options) == 1 and p.input_type(options[0]) == "duration" and not p.children(options[0])


# ---------- Shortcuts the CHW can type ----------

class PatientUnsure(Exception):
    """CHW typed 'u'."""


class NoAnswer(Exception):
    """CHW typed 'x'."""


SHORTCUTS = {"u": PatientUnsure, "x": NoAnswer}


class ShortcutConsole:
    """Sits between the intake and the real console. When a shortcut is switched on and the CHW types it,
    it stops the current question (by raising the matching exception). Everything else passes through."""

    def __init__(self, console):
        self.inner = console
        self.allowed = set()

    def show(self, text=""):
        self.inner.show(text)

    def ask(self, prompt):
        reply = self.inner.ask(prompt)
        key = reply.strip().lower()
        if key in self.allowed:
            raise SHORTCUTS[key]()
        return reply


class CountingConsole:
    """Counts how many times the CHW had to type something (any mode). Saved as run_info['chw_inputs']."""

    def __init__(self, console):
        self.inner = console
        self.inputs = 0

    def show(self, text=""):
        self.inner.show(text)

    def ask(self, prompt):
        self.inputs += 1
        return self.inner.ask(prompt)

    def __getattr__(self, name):
        # Lets test consoles (smoke_test.py) keep their own fields, e.g. console.log
        return getattr(self.inner, name)


# ---------- The base class both options share ----------

class FollowUpIntake(Intake):
    """The base of the multi-question intake. Built on Intake from intake.py, so the
    option picker, AI matching, story check, 'said no' check, red flags and saving all stay the same.
    Each option only changes how one group of questions is asked (ask_group)."""

    mode = "grouped"

    def __init__(self, patient, mapper, console, language="en", group_size=4):
        super().__init__(patient, mapper, ShortcutConsole(console), language)
        self.group_size = group_size
        self.groups_asked = 0
        self.follow_ups = []
        self.asked_again = set()
        self.asked_how_long = set()

    # --- walking a section in groups ---

    def run_section(self, protocol, section, use_story=False):
        self.section = section
        self.use_story = use_story
        questions = [q for q in p.children(protocol) if p.applies_to_patient(q, self.patient)]
        groups = [questions[i:i + self.group_size] for i in range(0, len(questions), self.group_size)]
        for number, group in enumerate(groups, start=1):
            first_answer = len(self.answers)
            self.ask_group(group, number, len(groups))
            self.check_vague_durations(group, first_answer)
            self.check_yes_and_no()
        self.use_story = False

    def ask_group(self, group, number, group_count):
        raise NotImplementedError

    # --- one question, with the shortcuts caught ---

    def ask_question(self, question):
        """Same as Intake.ask_question, but catches the CHW's shortcuts (u, x) for THIS question only.
        Follow-up questions under an answer go through here too, so each one is caught at its own level."""
        try:
            super().ask_question(question)
        except PatientUnsure:
            self.record(question, [], source=None, status="unsure")
        except NoAnswer:
            self.record(question, [], source=None, status="not_answered")

    def shortcuts(self, *keys):
        """with self.shortcuts('u', 'x'): ... switches those shortcuts on, then back to what they were."""
        intake = self

        class Switch:
            def __enter__(self):
                self.before = set(intake.console.allowed)
                intake.console.allowed = set(keys)

            def __exit__(self, *error):
                intake.console.allowed = self.before
                return False

        return Switch()

    # --- the follow-up step ---

    def has_answer(self, question):
        """True if the question already has a real answer (not just a 'No' to some options)."""
        for answer in self.answers:
            if answer["question_id"] == question.get("id") and answer["status"] in ("present", "unsure", "not_answered"):
                if answer["section"] == self.section:
                    return True
        return False

    def ask_follow_up(self, question, reason):
        """Asks one missing or unclear question once more, on its own. u / x are allowed here."""
        if question.get("id") in self.asked_again:
            return
        self.asked_again.add(question.get("id"))
        if reason.startswith("vague duration"):
            self.asked_how_long.add(question.get("id"))
        self.console.show("")
        self.console.show(f"   >> Follow-up ({reason})")
        self.console.show("   (u = patient unsure, x = no answer)")
        with self.shortcuts("u", "x"):
            use_story = self.use_story
            self.use_story = False
            self.ask_question(question)
            self.use_story = use_story
        self.note_follow_up(question, reason)

    def note_follow_up(self, question, reason):
        result = "no answer saved"
        for answer in reversed(self.answers):
            if answer["question_id"] == question.get("id"):
                result = answer["status"]
                break
        self.follow_ups.append({
            "section": self.section,
            "question_id": question.get("id"),
            "question": p.display_text(question),
            "reason": reason,
            "result": result,
        })

    def check_vague_durations(self, group, first_answer):
        """'Since when?' answered with 'a while ago' or 'sometimes in a day' -> ask once for days/weeks/months.
        This can come after a 'missing' follow-up too, but a vague duration is never asked about twice."""
        for question in group:
            if not is_duration_question(question) or question.get("id") in self.asked_how_long:
                continue
            for answer in self.answers[first_answer:]:
                if answer["question_id"] != question.get("id") or answer["status"] != "present":
                    continue
                if not is_vague_duration(answer["value"]):
                    continue
                self.ask_duration_again(question, answer)

    def ask_duration_again(self, question, answer):
        self.asked_again.add(question.get("id"))
        self.asked_how_long.add(question.get("id"))
        old_value = answer["value"]
        reason = f"vague duration: \"{old_value}\""
        self.console.show("")
        self.console.show(f"   >> Follow-up ({reason})")
        self.console.show(f"   {p.display_text(question, self.language)}")
        self.console.show(f"   The patient said \"{old_value}\". That doesn't say how long. Ask: how many days, weeks or months?")
        self.console.show("   (u = patient unsure, x = no answer)")
        options = p.children(question)
        node = options[0] if options else question
        try:
            with self.shortcuts("u", "x"):
                new_value = self.ask_value(node, "How long, in days / weeks / months", about=question)
        except PatientUnsure:
            answer["status"] = "unsure"
            new_value = ""
        except NoAnswer:
            new_value = ""
        if new_value:
            answer["value"] = new_value
            answer["patient_words"] = " | ".join(w for w in (answer["patient_words"], old_value) if w)
            answer["source"] = "tapped"
        self.follow_ups.append({
            "section": self.section,
            "question_id": question.get("id"),
            "question": p.display_text(question),
            "reason": reason,
            "result": answer["status"] if not new_value else "present",
        })

    def check_yes_and_no(self):
        """The patient said 'no fever' earlier but 'fever' now: ask the CHW which one is right."""
        for qid, option_id, label, yes_answer, no_answer in self.yes_and_no_pairs():
            self.console.show("")
            self.console.show(f"   >> Follow-up (answers disagree): the patient said NO to \"{label}\" "
                              f"but also said they have it.")
            reply = self.console.ask("   Which is right? y = has it, n = does NOT have it, u = unsure:").strip().lower()
            if reply in ("y", "yes"):
                self.drop_option(no_answer, option_id)
                result = "present"
            elif reply in ("n", "no"):
                self.drop_option(yes_answer, option_id)
                result = "said_no"
            else:
                # Only this one option becomes "unsure"; the other options in the answer stay as they were.
                self.drop_option(no_answer, option_id)
                self.drop_option(yes_answer, option_id)
                unsure = dict(yes_answer, answer_ids=[option_id], answers=[label], value=None, status="unsure")
                self.answers.append(unsure)
                result = "unsure"
            self.follow_ups.append({
                "section": self.section,
                "question_id": qid,
                "question": yes_answer["question"],
                "reason": f"answers disagree: \"{label}\"",
                "result": result,
            })
            self.check_red_flags()

    def yes_and_no_pairs(self):
        said_no = {}
        for answer in self.answers:
            if answer["section"] == self.section and answer["status"] == "said_no":
                for option_id, label in zip(answer["answer_ids"], answer["answers"]):
                    said_no[(answer["question_id"], option_id)] = (label, answer)
        pairs = []
        for answer in self.answers:
            if answer["section"] != self.section or answer["status"] != "present":
                continue
            for option_id in answer["answer_ids"]:
                key = (answer["question_id"], option_id)
                if key in said_no:
                    label, no_answer = said_no[key]
                    pairs.append((answer["question_id"], option_id, label, answer, no_answer))
        return pairs

    def drop_option(self, answer, option_id):
        """Takes one option out of a saved answer. An answer left with no options is removed."""
        if option_id not in answer["answer_ids"]:
            return
        index = answer["answer_ids"].index(option_id)
        answer["answer_ids"].pop(index)
        answer["answers"].pop(index)
        if not answer["answer_ids"] and not answer["value"] and answer in self.answers:
            self.answers.remove(answer)

    # --- numbers for run_info in visit.json ---

    def extra_run_info(self):
        statuses = [answer["status"] for answer in self.answers]
        return {
            "group_size": self.group_size,
            "groups_asked": self.groups_asked,
            "follow_ups_asked": len(self.follow_ups),
            "saved_unsure": statuses.count("unsure"),
            "saved_not_answered": statuses.count("not_answered"),
            "follow_ups": self.follow_ups,
        }
#----- end of Lia's code -----
