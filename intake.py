import re

import explanations
import negation
import protocols as p
import red_flags


class Console:
    def show(self, text=""):
        print(text)

    def ask(self, prompt):
        return input(prompt + " ").strip()


def parse_numbers(reply, how_many):
    if not re.fullmatch(r"\s*\d+(\s*,\s*\d+)*\s*", reply):
        return None
    numbers = [int(n) for n in reply.split(",")]
    if all(1 <= n <= how_many for n in numbers):
        return [n - 1 for n in numbers]
    return None


def option_to_explain(reply):
    """'?3' -> 3. Anything else -> None."""
    match = re.fullmatch(r"\?\s*(\d+)", reply)
    if not match:
        return None
    return int(match.group(1))


def explain_hint(option_count):
    example = min(3, option_count)
    return f"   (Type ? to explain the question, or ?{example} to explain option {example}.)"


def is_yes(reply):
    return reply.strip().lower() in ("y", "yes")


class Intake:
    def __init__(self, patient, mapper, console, language="en"):
        self.patient = patient
        self.follow_ups_done = set()
        self.mapper = mapper
        self.console = console
        self.language = language
        self.answers = []
        self.complaint = ""
        self.story = ""
        self.use_story = False
        self.alerts = []
        self.possible_alerts = []
        self.questions_asked = 0
        self.filled_from_story = 0
        self.said_no_ids = set()
        self.section = ""
        self.rejected = []
        self.explainer = explanations.Explainer(mapper, console)

    def record(self, question, chosen, value=None, source="tapped", patient_words=None, status="present"):
        self.answers.append({
            "section": self.section,
            "question_id": question.get("id"),
            "question": p.display_text(question),
            "question_label": question.get("text", "").strip(),
            "answer_ids": [option.get("id") for option in chosen],
            "answers": [option.get("text", "").strip() for option in chosen],
            "value": value,
            "source": source,
            "patient_words": patient_words,
            "status": status,
        })
        self.check_red_flags()

    def note_rejected(self, question, suggested, kind, patient_words, value=None):
        """Keeps every AI suggestion the CHW said no to, so we can count confirmed vs rejected."""
        self.rejected.append({
            "section": self.section,
            "question_id": question.get("id"),
            "question": p.display_text(question),
            "suggested_ids": [option.get("id") for option in suggested],
            "suggested": [option.get("text", "").strip() for option in suggested],
            "value": value,
            "kind": kind,
            "patient_words": patient_words,
        })

    def check_red_flags(self):
        flags, possible = red_flags.check(self.complaint, self.answers, self.patient)
        for flag in flags:
            if flag not in self.alerts:
                self.alerts.append(flag)
                self.console.show("")
                self.console.show(f"   !!! RED FLAG - {red_flags.describe(flag)}. Refer as per level. !!!")
        for flag in possible:
            if flag not in self.alerts and flag not in self.possible_alerts:
                self.possible_alerts.append(flag)
                self.console.show("")
                self.console.show(f"   ?? POSSIBLE RED FLAG - {red_flags.describe(flag)}. It came up next to a 'no' or 'not'. "
                                  f"Please check with the patient. ??")
        still_possible = []
        for flag in self.possible_alerts:
            if flag in possible:
                still_possible.append(flag)
        self.possible_alerts = still_possible
        self.ask_red_flag_follow_ups(flags)

    def ask_red_flag_follow_ups(self, flags):
        """A broad red flag (e.g. headache + fever) fired: ask the yes/no questions that decide
        whether it is an emergency. Each answer is recorded like any other answer, so the
        red-flag check runs again and can raise the level."""
        for item in red_flags.follow_ups_for(flags):
            if item["id"] in self.follow_ups_done:
                continue
            self.follow_ups_done.add(item["id"])
            if red_flags.follow_up_already_known(item, self.complaint, self.answers):
                continue  # already answered earlier in the visit: don't ask twice
            reply = ""
            for _ in range(3):
                reply = self.console.ask(f"   RED-FLAG CHECK: {item['question']} (y = yes / n = no / d = don't know):")
                reply = reply.strip().lower()
                if reply[:1] in ("y", "n", "d"):
                    break
            question = {"id": "follow_up_" + item["id"], "text": item["label"], "display": item["question"]}
            if reply.startswith("n"):
                self.record(question, [{"id": item["id"], "text": item["label"]}],
                            source="red-flag follow-up", status="said_no")
            elif reply.startswith("y"):
                self.record(question, [{"id": item["id"], "text": item["label"]}], source="red-flag follow-up")
            else:  # don't know, or no clear answer: treat as yes so the level is never lowered by doubt
                self.record(question, [{"id": item["id"], "text": item["label"] + " (not sure)"}],
                            source="red-flag follow-up")

    def confirm(self, prompt, question, option_labels):
        """Asks a yes/no question. Typing '?' shows simple explanations, then asks again."""
        while True:
            reply = self.console.ask(prompt)
            if reply != "?":
                return is_yes(reply)
            self.explainer.show(p.display_text(question), option_labels)

    def ask_value(self, node, prompt, about=None):
        """'about' is the question to explain when the CHW types '?'. By default it is the node itself."""
        if about is None:
            about = node
        kind = p.input_type(node)
        if kind == "camera":
            self.console.show("   (photo step skipped in this prototype)")
            return ""
        self.questions_asked += 1
        while True:
            value = self.console.ask(f"   {prompt} ({kind}) (? = explain):")
            if value == "?":
                self.explainer.show(p.display_text(about))
                continue
            if value or not p.is_required(node):
                return value
            self.console.show("   This one is required.")

    def offer_said_no(self, question, options, words, source, skip=()):
        """Multi-choice only: if the patient said 'no fever', offer to save Fever as a 'No'."""
        if not words or not p.is_multi_choice(question):
            return
        labels = [p.option_label(option) for option in options]
        said_no = []
        for index in negation.find_negated(labels, words, skip):
            key = (question.get("id"), options[index].get("id"))
            if not p.is_exclusive(options[index]) and key not in self.said_no_ids:
                said_no.append(index)
        if not said_no:
            return
        shown = ", ".join(p.option_label(options[i], self.language) for i in said_no)
        chosen = [options[i] for i in said_no]
        english_labels = [p.option_label(option) for option in chosen]
        self.console.show(f"   Patient's words: \"{words}\"")
        if self.confirm(f"   Patient said they do NOT have: {shown}. Save as 'No'? (y/n)", question, english_labels):
            for option in chosen:
                self.said_no_ids.add((question.get("id"), option.get("id")))
            self.record(question, chosen, source=source, patient_words=words, status="said_no")
        else:
            self.note_rejected(question, chosen, "said no", words)

    def show_choices(self, question, labels, multi):
        self.console.show("")
        self.console.show(p.display_text(question, self.language) + (" (choose one or more)" if multi else ""))
        for number, label in enumerate(labels, start=1):
            self.console.show(f"   {number}. {label}")
        self.console.show(explain_hint(len(labels)))

    def choose_options(self, question, options):
        labels = [p.option_label(option, self.language) for option in options]
        english_labels = [p.option_label(option) for option in options]
        multi = p.is_multi_choice(question)
        required = p.is_required(question)
        self.questions_asked += 1

        self.show_choices(question, labels, multi)

        while True:
            reply = self.console.ask("   Number(s), or type the patient's words:")
            if reply == "?":
                self.explainer.show(p.display_text(question), english_labels)
                self.show_choices(question, labels, multi)
                continue
            number = option_to_explain(reply)
            if number is not None:
                if 1 <= number <= len(options):
                    self.explainer.show_option(english_labels[number - 1], p.display_text(question))
                    self.show_choices(question, labels, multi)
                else:
                    self.console.show(f"   There is no option {number}.")
                continue
            if reply == "":
                if required:
                    self.console.show("   This question is required.")
                    continue
                return [], None, None

            picked = parse_numbers(reply, len(options))
            if picked is not None:
                source, words = "tapped", None
            else:
                result = self.mapper.map_answer(p.display_text(question), english_labels, reply, multi)
                picked, dropped = negation.check_picks(english_labels, result["indexes"], reply)
                self.offer_said_no(question, options, reply, self.mapper.name, skip=picked)
                if not picked:
                    self.console.show("   Not sure what that matches. Please ask again or pick a number.")
                    continue
                suggestion = ", ".join(labels[i] for i in picked)
                picked_labels = [english_labels[i] for i in picked]
                if not self.confirm(f"   Suggested: {suggestion}. Correct? (y/n)", question, picked_labels):
                    self.note_rejected(question, [options[i] for i in picked], "map answer", reply)
                    continue
                source, words = self.mapper.name, reply

            chosen = [options[i] for i in picked]
            if not multi and len(chosen) > 1:
                self.console.show("   Please choose only one.")
                continue
            if len(chosen) > 1 and any(p.is_exclusive(option) for option in chosen):
                self.console.show("   That option can't be combined with others.")
                continue
            return chosen, source, words

    def try_story(self, question, options):
        """If the patient already mentioned this in their own words, confirm instead of asking."""
        question_text = p.display_text(question)
        single_input = len(options) == 1 and p.input_type(options[0]) and not p.children(options[0])

        if single_input:
            value = self.mapper.value_from_story(question_text, self.story)
            if not value:
                return False
            self.console.show("")
            self.console.show(p.display_text(question, self.language))
            if not self.confirm(f"   Patient already said: {value}. Keep? (y/n)", question, []):
                self.note_rejected(question, [], "from story", self.story, value=value)
                return False
            self.filled_from_story += 1
            self.record(question, options, value=value, source="from story", patient_words=self.story)
            return True

        labels = [p.option_label(option) for option in options]
        multi = p.is_multi_choice(question)
        picked = self.mapper.answer_from_story(question_text, labels, self.story, multi)
        picked, dropped = negation.check_picks(labels, picked, self.story)
        self.offer_said_no(question, options, self.story, "from story", skip=picked)
        if not picked:
            return False
        chosen = [options[i] for i in picked]
        if not multi or any(p.is_exclusive(option) for option in chosen):
            chosen = chosen[:1]
        shown = ", ".join(p.option_label(option, self.language) for option in chosen)
        chosen_labels = [p.option_label(option) for option in chosen]
        self.console.show("")
        self.console.show(p.display_text(question, self.language))
        if not self.confirm(f"   Patient already said: {shown}. Keep? (y/n)", question, chosen_labels):
            self.note_rejected(question, chosen, "from story", self.story)
            return False
        self.filled_from_story += 1
        self.follow_up(question, chosen, "from story", self.story)
        return True

    def ask_question(self, question):
        if not p.applies_to_patient(question, self.patient):
            return

        options = [o for o in p.children(question) if p.applies_to_patient(o, self.patient)]

        if (self.use_story and self.story and options and p.story_prefill_allowed(question)
                and self.try_story(question, options)):
            return

        if p.input_type(question) and not options:
            value = self.ask_value(question, p.display_text(question, self.language))
            if value:
                self.record(question, [], value=value)
            else:
                self.record(question, [], source=None, status="skipped")
            return

        if len(options) == 1 and p.input_type(options[0]) and not p.children(options[0]):
            value = self.ask_value(options[0], p.display_text(question, self.language), about=question)
            if value:
                self.record(question, options, value=value)
            else:
                self.record(question, [], source=None, status="skipped")
            return

        chosen, source, words = self.choose_options(question, options)
        if chosen:
            self.follow_up(question, chosen, source, words)
        else:
            self.record(question, [], source=None, status="skipped")

    def follow_up(self, question, chosen, source, words):
        value = None
        for option in chosen:
            if p.input_type(option) and not p.children(option):
                value = self.ask_value(option, p.option_label(option, self.language))
        self.record(question, chosen, value=value, source=source, patient_words=words)

        use_story = self.use_story
        self.use_story = False
        for option in chosen:
            choices, follow_ups = p.split_children(option)
            if choices:
                sub_question = {
                    "id": option.get("id"),
                    "text": option.get("text"),
                    "multi-choice": True,
                    "options": choices,
                }
                self.ask_question(sub_question)
            for follow_up in follow_ups:
                self.ask_question(follow_up)
        self.use_story = use_story

    def run_section(self, protocol, section, use_story=False):
        self.section = section
        self.use_story = use_story
        for question in p.children(protocol):
            self.ask_question(question)
        self.use_story = False