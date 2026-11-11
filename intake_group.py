#----- Lia's code: multi-question intake -----
r"""Multi-question intake: ask a group of questions together, fill them from ONE reply, then follow up.

For each group of questions (4 by default, in the protocol's own order):
  1. Story: if the patient's story already answered a question, the CHW confirms it (same as today).
  2. Group: the app lists the rest; the CHW asks them together and types the patient's whole reply once.
  3. Fill: the app checks each question against that reply and suggests an answer.
     All suggestions of the group are shown together, and ONE reply from the CHW checks them:
     y = all correct, "2" or "1,3" = those are wrong, "u2" = save Q2 as unsure, n = none.
     With a model, the AI reads the reply with its own instructions (GROUP_RULES), answers by option
     number only, and every pick gets the yes/no double-check, like the story check in step 1.
     Without a model, it uses keyword matching, and plain code for durations ("3 days").
  4. Follow-up: every question still missing, or with a rejected suggestion, is asked once on its own.
     Questions about severity, and free-text boxes, are never filled from the reply; they are always asked on their own.
  5. Then the checks in followup.py: vague durations and "no"/"yes" disagreements.

How to run (from the project folder):

  Windows (PowerShell):
    $PROTOCOLS = "..\intelehealth-ayu-protocols\protocols\v2\All Protocols (JSON)"
    python main.py --protocols "$PROTOCOLS" --intake group
    python main.py --protocols "$PROTOCOLS" --intake group --model "D:\JHU\AI_ML\models\medpsy-1.7b-q4_k_m-imat.gguf"

  Mac (Terminal):
    PROTOCOLS="../intelehealth-ayu-protocols/protocols/v2/All Protocols (JSON)"
    python main.py --protocols "$PROTOCOLS" --intake group
    python main.py --protocols "$PROTOCOLS" --intake group --model medpsy-1.7b-q4_k_m-imat.gguf

  (If your protocols folder is inside the project folder, as in the README, drop the "../" or "..\".)
"""
import negation
import protocols as p
from followup import (FollowUpIntake, NoAnswer, PatientUnsure, find_duration, is_duration_question,
                      is_no_answer_option, is_vague_duration, no_option_from_reply, read_checks,
                      unsure_about)
from intake import option_to_explain


SOURCE = "from group reply"

# Instructions for the AI when it reads a group reply. The story instructions (ai_mapper.STORY_RULES) say
# "if the patient did not mention this topic, choose 0", which fits a free story but made the AI skip
# answers the patient gave on purpose, because here the CHW just asked these questions.
# Same safety rules as the story: options by number only, never against a "no", never guess,
# and every pick still gets the yes/no double-check ("Did the patient clearly say this?").
GROUP_RULES = ("A community health worker asked the patient several questions at once, and the patient "
               "answered them together. You fill in ONE of those questions. Use ONLY the patient's words. "
               "Pick the ONE option that matches what the patient said for this question. "
               "Parts of the answer may be about the other questions; ignore those parts. "
               "If the patient's words do not answer this question, choose 0. "
               "If some options are already recorded, pick another one only if the patient clearly "
               "mentioned it too. Otherwise choose 0. "
               "Never pick something the patient said they do NOT have. Never guess.")


def can_fill_from_reply(question):
    """Severity questions and free-text boxes ('Additional information') are never filled from the reply."""
    if not p.story_prefill_allowed(question):
        return False
    if is_duration_question(question):
        return True
    options = p.children(question)
    return bool(options) and not (len(options) == 1 and p.input_type(options[0]))


class GroupIntake(FollowUpIntake):
    mode = "group"

    def __init__(self, patient, mapper, console, language="en", group_size=4):
        super().__init__(patient, mapper, console, language, group_size)
        self.filled_from_reply = 0
        self.group_replies = []

    # --- one group ---

    def ask_group(self, group, number, group_count):
        remaining = []
        for question in group:
            if self.from_story_first(question):
                continue
            remaining.append(question)
        if not remaining:
            return

        self.groups_asked += 1
        to_fill = [q for q in remaining if can_fill_from_reply(q)]
        on_its_own = [q for q in remaining if not can_fill_from_reply(q)]
        reply = self.ask_for_reply(remaining, on_its_own, number, group_count) if to_fill else ""

        suggestions = []
        not_filled = []
        for question in to_fill:
            result = self.suggest(question, reply, remaining) if reply else "asked one by one"
            if isinstance(result, dict):
                result["position"] = remaining.index(question) + 1
                suggestions.append(result)
            elif result:
                not_filled.append((question, result))

        for suggestion, decision in self.confirm_all(suggestions, reply):
            question = suggestion["question"]
            if decision == "no":
                self.note_rejected(question, suggestion["chosen"], "group reply", reply, value=suggestion["value"])
                not_filled.append((question, "suggestion rejected"))
                continue
            self.filled_from_reply += 1
            if decision == "unsure":
                self.record(question, suggestion["save"], value=suggestion["value"], source=SOURCE,
                            patient_words=reply, status="unsure")
            elif suggestion["value"] is not None:
                self.record(question, suggestion["save"], value=suggestion["value"], source=SOURCE,
                            patient_words=reply)
            else:
                self.save_with_follow_ups(question, suggestion["chosen"], reply)

        for question in on_its_own:
            not_filled.append((question, "always asked on its own"))
        not_filled.sort(key=lambda item: remaining.index(item[0]))
        for question, reason in not_filled:
            if not self.has_answer(question):
                self.ask_follow_up(question, reason)

    def from_story_first(self, question):
        """Step 1, same as today: use the patient's story if it already answered this question."""
        if not (self.use_story and self.story and p.story_prefill_allowed(question)):
            return False
        options = [o for o in p.children(question) if p.applies_to_patient(o, self.patient)]
        if not options:
            return False
        try:
            with self.shortcuts("u", "x"):
                return self.try_story(question, options)
        except PatientUnsure:
            self.record(question, [], source=None, status="unsure")
            return True
        except NoAnswer:
            return False

    def ask_for_reply(self, remaining, on_its_own, number, group_count):
        """Step 2: show the group, take the patient's whole reply once."""
        self.console.show("")
        self.console.show(f"--- Question group {number} of {group_count}: ask these together ---")
        for position, question in enumerate(remaining, start=1):
            note = "   (asked on its own after this)" if question in on_its_own else ""
            self.console.show(f"   Q{position}. {p.display_text(question, self.language)}{note}")
        self.console.show("   (Type ? to explain the questions, or ?2 to explain Q2 and its options.)")
        while True:
            reply = self.console.ask("Type the patient's reply to these questions (Enter = ask them one by one):")
            if reply == "?":
                for question in remaining:
                    self.explainer.show(p.display_text(question))
                continue
            position = option_to_explain(reply)
            if position is not None:
                if 1 <= position <= len(remaining):
                    question = remaining[position - 1]
                    labels = [p.option_label(o) for o in p.children(question)]
                    self.explainer.show(p.display_text(question), labels)
                else:
                    self.console.show(f"   There is no Q{position}.")
                continue
            if reply:
                self.group_replies.append(reply)
            return reply

    # --- step 3: suggest an answer for each question, then the CHW checks them all at once ---

    def suggest(self, question, reply, asked=()):
        """Returns a suggestion (dict), or the reason this question needs a follow-up (text)."""
        if not p.applies_to_patient(question, self.patient):
            return None
        options = [o for o in p.children(question) if p.applies_to_patient(o, self.patient)]
        question_text = p.display_text(question)
        if is_duration_question(question):
            if self.mapper.name == "keyword":
                value = find_duration(reply)
            else:
                value = self.mapper.value_from_story(question_text, reply)
            if not value:
                return "not in the reply"
            if is_vague_duration(value):
                return f"vague duration: \"{value}\""
            return {"question": question, "chosen": [], "save": options, "value": value,
                    "shown": value, "english": [], "hedge": unsure_about(reply, [value])}

        labels = [p.option_label(o) for o in options]
        multi = p.is_multi_choice(question)
        if self.mapper.name == "keyword":
            picked = self.mapper.map_answer(question_text, labels, reply, multi)["indexes"]
        elif hasattr(self.mapper, "pick_best_then_more"):
            picked = self.ai_pick_from_reply(question_text, labels, reply, multi, asked)
        else:
            picked = self.mapper.answer_from_story(question_text, labels, reply, multi)
        kept, dropped = negation.check_picks(labels, picked, reply)
        # keep 'No' / 'None' / 'Never-smoker' style options: there the patient's "no" IS the answer
        picked = [i for i in picked if i in kept or is_no_answer_option(labels[i])]
        no_options = [i for i, label in enumerate(labels) if is_no_answer_option(label)]
        if not picked:
            # "no medicine" -> No, "no known allergies" -> No known allergies (plain code, see followup.py)
            index = no_option_from_reply(question_text, labels, reply)
            if index is not None:
                picked = [index]
        self.offer_said_no(question, options, reply, SOURCE, skip=picked + no_options)
        if not picked:
            return "not in the reply"
        chosen = [options[i] for i in picked]
        if not multi or any(p.is_exclusive(option) for option in chosen):
            chosen = chosen[:1]
        english = [p.option_label(option) for option in chosen]
        return {"question": question, "chosen": chosen, "save": chosen, "value": None,
                "shown": ", ".join(p.option_label(option, self.language) for option in chosen),
                "english": english, "hedge": unsure_about(reply, english)}

    def ai_pick_from_reply(self, question_text, labels, reply, multi, asked):
        """The AI reads the reply knowing which questions the CHW asked together (GROUP_RULES above).
        check_first=True: even the first pick gets the yes/no double-check, like the story."""
        asked_line = "; ".join(p.display_text(q) for q in asked)
        words_line = f"The CHW asked: {asked_line}\nPatient said: \"{reply}\""
        return self.mapper.pick_best_then_more(GROUP_RULES, words_line, question_text, labels, multi,
                                               "Not answered in the patient's reply", "answer from group reply",
                                               check_first=True)

    def confirm_all(self, suggestions, reply):
        """Shows every suggestion of the group at once. One reply from the CHW checks them all:
        y = save all, '2' or '1,3' = those are wrong, 'u2' = save Q2 as unsure, n = all wrong."""
        if not suggestions:
            return []
        self.console.show("")
        self.console.show("   From the patient's reply:")
        for s in suggestions:
            self.console.show(f"   Q{s['position']}. {p.display_text(s['question'], self.language)} -> {s['shown']}")
            if s["hedge"]:
                self.console.show(f"        (patient sounded unsure: \"{s['hedge']}\")")
        positions = [s["position"] for s in suggestions]
        while True:
            answer = self.console.ask("   Save these? y = all correct, or type the wrong ones (e.g. 2 or 1,3), "
                                      "u2 = Q2 unsure, n = none:").strip().lower()
            if answer == "?":
                for s in suggestions:
                    self.explainer.show(p.display_text(s["question"]), s["english"])
                continue
            decisions = read_checks(answer, positions)
            if decisions is None:
                self.console.show(f"   Please type y, n, or Q numbers from: {', '.join(map(str, positions))}.")
                continue
            return [(s, decisions[s["position"]]) for s in suggestions]

    def save_with_follow_ups(self, question, chosen, reply):
        """Saves the answer, then asks the questions that sit under it (for example 'Pain radiates to' -> where?)."""
        try:
            with self.shortcuts("u", "x"):
                self.follow_up(question, chosen, SOURCE, reply)
        except PatientUnsure:
            self.record(question, chosen, source=SOURCE, patient_words=reply, status="unsure")
        except NoAnswer:
            self.record(question, chosen, source=SOURCE, patient_words=reply)

    def extra_run_info(self):
        info = super().extra_run_info()
        info["filled_from_group_reply"] = self.filled_from_reply
        info["group_replies"] = self.group_replies
        return info
#----- end of Lia's code -----
