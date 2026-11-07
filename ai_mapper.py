import json
import os
import re
import time

import llama_cpp.llama_chat_format as chat_format



class TemplateFix(chat_format.Jinja2ChatFormatter):
    """MedPsy's built-in chat template uses a tag this library can't read. We build prompts ourselves."""

    def __init__(self, template, *args, **kwargs):
        template = re.sub(r"\{%-?\s*(end)?generation\s*-?%\}", "", template)
        super().__init__(template, *args, **kwargs)


chat_format.Jinja2ChatFormatter = TemplateFix

from llama_cpp import Llama, LlamaGrammar  # noqa: E402


SKIP_THINKING = "<think>\n\n</think>\n\n"


def chat_prompt(system, user):
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n{SKIP_THINKING}"
    )


def number_choice(count):
    return " | ".join(f'"{n}"' for n in range(count, 0, -1))


def one_number_grammar(option_count):
    """The reply must be {"answer": N}, where N is 0 or a real option number."""
    return LlamaGrammar.from_string(
        f'root ::= "{{\\"answer\\": " num "}}"\n'
        f'num ::= {number_choice(option_count)} | "0"\n',
        verbose=False,
    )


MAX_PICKS = 4

YES_NO_GRAMMAR = 'root ::= "{\\"answer\\": \\"yes\\"}" | "{\\"answer\\": \\"no\\"}"\n'

CHECK_RULES = ("You double-check one answer on a patient history form. "
               "Answer yes ONLY if the patient's own words clearly say this. "
               "If the patient did not say it, said something only similar, or said they do NOT have it, answer no.")

ANSWER_RULES = ("You help a community health worker record a patient's answer. "
                "Pick the ONE option that best matches what the patient said. "
                "If the patient's words do not clearly match any option, choose 0. "
                "If some options are already recorded, pick another one only if the patient clearly "
                "mentioned it too. Otherwise choose 0. "
                "Never pick something the patient said they do NOT have.")

STORY_RULES = ("You help a community health worker fill in a patient history form from what the patient said. "
               "Answer ONLY from the patient's words. Pick the ONE option that best matches. "
               "If the patient did not mention this topic, choose 0. "
               "If some options are already recorded, pick another one only if the patient clearly "
               "mentioned it too. Otherwise choose 0. "
               "Never pick something the patient said they do NOT have. Never guess.")

EVIDENCE_RULES = ("You help a community health worker fill in a patient history form from what the patient said. "
                  "Answer ONLY from the patient's words. Pick the ONE option that best matches, and copy the "
                  "exact words from the patient that show it as evidence. "
                  "If the patient did not mention this topic, choose 0 with empty evidence. "
                  "Never pick something the patient said they do NOT have. Never guess.")

EXPLAIN_RULES = ("You explain medical words to a community health worker who has no medical training. "
                 "Give the usual medical meaning of the word itself, in everyday words, simple enough for a 12-year-old. "
                 "Do not connect it to the patient's complaint unless the word is about that body part. "
                 "Do not give advice. Do not guess a diagnosis. Answer in one short sentence only.")

# Worked examples shown to the model before the real word: (complaint, question, option, good answer).
# When option is None, the example explains the question itself.
EXPLAIN_EXAMPLES = [
    ("Abdominal Pain", "Which part of the abdomen do you feel pain?", "Epigastric",
     "The upper middle part of the belly, just below where the ribs meet."),
    ("Cough", "Associated symptoms", "Hemoptysis",
     "Coughing up blood, or mucus (phlegm) with blood in it."),
    ("Fever", "H/o specific illness", "Tuberculosis",
     "An infection, usually of the lungs, that causes a long-lasting cough, fever, night sweats, "
     "and weight loss, and spreads through the air."),
    ("Abdominal Pain", "Timing", "Postprandial", "After eating."),
    ("Fever", "Character", "Intermittent", "Comes and goes."),
    ("Fever", "Nature of fever", None,
     "Asks about the pattern of the fever: is it there all the time, or does it come and go?"),
    ("Cough", "What aggravates the cough?", None, "Asks what makes the cough worse."),
]

STORY_CHECKS = ["off", "yes_no", "evidence"]


def evidence_grammar(option_count):
    """The reply must be {"answer": 0, "evidence": ""} or {"answer": N, "evidence": "<up to 60 characters>"}."""
    return LlamaGrammar.from_string(
        'root ::= nothing | pick\n'
        'nothing ::= "{\\"answer\\": 0, \\"evidence\\": \\"\\"}"\n'
        'pick ::= "{\\"answer\\": " num ", \\"evidence\\": \\"" evidence "\\"}"\n'
        f'num ::= {number_choice(option_count)}\n'
        "evidence ::= [a-zA-Z0-9 ,.'-]{1,60}\n",
        verbose=False,
    )


def plain_words(text):
    text = text.lower().replace("'", "").replace("’", "")
    return re.findall(r"[a-z0-9]+", text)


def mostly_from_story(value, story):
    """Plain-code check: at least half of the words in the answer must be the patient's own words.
    Short words like 'for' or 'the' are not counted, but numbers always are."""
    answer_words = []
    for word in plain_words(value):
        if word.isdigit() or len(word) > 3:
            answer_words.append(word)
    if not answer_words:
        return False
    story_words = set(plain_words(story))
    found = 0
    for word in answer_words:
        if word in story_words:
            found += 1
    return found * 2 >= len(answer_words)


def evidence_in_story(evidence, story):
    """Plain-code check: the evidence must be the patient's exact words and hold at least one real word."""
    evidence_words = plain_words(evidence)
    has_long_word = False
    for word in evidence_words:
        if word.isalpha() and len(word) > 3:
            has_long_word = True
    if not has_long_word:
        return False
    evidence_text = " " + " ".join(evidence_words) + " "
    story_text = " " + " ".join(plain_words(story)) + " "
    return evidence_text in story_text


def explain_message(text, kind, question_text, complaint):
    message = ""
    if complaint:
        message += f"The patient's main complaint is {complaint}.\n"
    if kind == "question":
        message += (f"Question on a patient history form: \"{text}\"\n"
                    f"What is this question asking? Explain in everyday words.")
    else:
        message += (f"Question on a patient history form: \"{question_text}\"\n"
                    f"Answer option: \"{text}\"\n"
                    f"What does \"{text}\" mean? Explain in everyday words.")
    return message


def explain_prompt(text, kind, question_text, complaint):
    """The rules, then the worked examples as earlier turns of the chat, then the real word."""
    prompt = f"<|im_start|>system\n{EXPLAIN_RULES}<|im_end|>\n"
    for example_complaint, example_question, example_option, answer in EXPLAIN_EXAMPLES:
        if example_option is None:
            user = explain_message(example_question, "question", "", example_complaint)
        else:
            user = explain_message(example_option, "option", example_question, example_complaint)
        prompt += f"<|im_start|>user\n{user}<|im_end|>\n"
        prompt += f"<|im_start|>assistant\n{SKIP_THINKING}{answer}<|im_end|>\n"
    user = explain_message(text, kind, question_text, complaint)
    prompt += f"<|im_start|>user\n{user}<|im_end|>\n"
    prompt += f"<|im_start|>assistant\n{SKIP_THINKING}"
    return prompt


def first_sentence(text):
    """Keeps only the first sentence, so a long reply stays short."""
    text = " ".join(text.split())
    match = re.search(r"[.!?](\s|$)", text)
    if match:
        return text[:match.end()].strip()
    return text


class AIMapper:
    name = "ai"

    def __init__(self, model_path, context_size=4096, story_check="yes_no"):
        if story_check not in STORY_CHECKS:
            raise ValueError(f"story_check must be one of {STORY_CHECKS}")
        self.model = Llama(model_path=model_path, n_ctx=context_size, verbose=False)
        self.model_name = os.path.basename(model_path)
        self.story_check = story_check
        self.timings = []

    def generate(self, prompt, grammar=None, max_tokens=40, task="task"):
        started = time.time()
        result = self.model(prompt, max_tokens=max_tokens, temperature=0,
                            grammar=grammar, stop=["<|im_end|>"])
        seconds = time.time() - started
        usage = result["usage"]
        self.timings.append({"task": task, "seconds": round(seconds, 2),
                             "prompt_tokens": usage["prompt_tokens"],
                             "output_tokens": usage["completion_tokens"]})
        return result["choices"][0]["text"].strip()

    def pick_one(self, rules, words_line, question_text, option_labels, remaining, already, zero_meaning, task):
        lines = [f"0. {zero_meaning}"]
        for number, index in enumerate(remaining, start=1):
            lines.append(f"{number}. {option_labels[index]}")

        user = f"{words_line}\n\nQuestion: {question_text}\n"
        if already:
            user += "Already recorded: " + ", ".join(option_labels[i] for i in already) + "\n"
        user += "Options:\n" + "\n".join(lines) + "\nReply with JSON."

        reply = self.generate(chat_prompt(rules, user), one_number_grammar(len(remaining)),
                              max_tokens=12, task=task)
        number = json.loads(reply)["answer"]
        if number == 0:
            return None
        return remaining[number - 1]

    def patient_clearly_said(self, words_line, question_text, label):
        user = (f"{words_line}\n\nQuestion: {question_text}\nProposed answer: {label}\n"
                f"Did the patient clearly say this? Reply with JSON.")
        grammar = LlamaGrammar.from_string(YES_NO_GRAMMAR, verbose=False)
        reply = self.generate(chat_prompt(CHECK_RULES, user), grammar, max_tokens=10, task="double-check")
        return json.loads(reply)["answer"] == "yes"

    def pick_best_then_more(self, rules, words_line, question_text, option_labels, multi_choice,
                            first_zero_meaning, task, check_first=False):
        """Single best answer first. For multi-choice, keep asking 'anything else?' until the model says 0."""
        picked = []
        while True:
            remaining = [i for i in range(len(option_labels)) if i not in picked]
            if not remaining:
                break
            if picked:
                zero_meaning = "Nothing else"
            else:
                zero_meaning = first_zero_meaning
            index = self.pick_one(rules, words_line, question_text, option_labels,
                                  remaining, picked, zero_meaning, task)
            if index is None:
                break
            needs_check = check_first or len(picked) > 0
            if needs_check and not self.patient_clearly_said(words_line, question_text, option_labels[index]):
                break
            picked.append(index)
            if not multi_choice or len(picked) >= MAX_PICKS:
                break
        return picked

    def map_answer(self, question_text, option_labels, patient_words, multi_choice, task="map answer"):
        words_line = f"Patient said: \"{patient_words}\""
        picked = self.pick_best_then_more(ANSWER_RULES, words_line, question_text, option_labels,
                                          multi_choice, "Unclear / no option matches", task)
        return {"indexes": picked, "unclear": not picked}

    def match_complaint(self, complaint_names, patient_words):
        return self.map_answer("What is the patient's main complaint?", complaint_names,
                               patient_words, multi_choice=False, task="match complaint")

    def answer_from_story(self, question_text, option_labels, story, multi_choice):
        """Checks one question against the patient's story. Returns [] when it wasn't mentioned."""
        words_line = f"Patient said: \"{story}\""
        if not multi_choice and self.story_check == "evidence":
            return self.pick_with_evidence(words_line, question_text, option_labels, story)
        check_first = not multi_choice and self.story_check == "yes_no"
        return self.pick_best_then_more(STORY_RULES, words_line, question_text, option_labels,
                                        multi_choice, "Not mentioned by the patient", "answer from story",
                                        check_first=check_first)

    def pick_with_evidence(self, words_line, question_text, option_labels, story):
        """Single-choice story questions only: the model must quote the patient's words, and plain code checks the quote."""
        lines = ["0. Not mentioned by the patient"]
        for number, label in enumerate(option_labels, start=1):
            lines.append(f"{number}. {label}")
        user = (f"{words_line}\n\nQuestion: {question_text}\nOptions:\n" + "\n".join(lines)
                + "\nReply with JSON.")
        reply = self.generate(chat_prompt(EVIDENCE_RULES, user), evidence_grammar(len(option_labels)),
                              max_tokens=80, task="story with evidence")
        result = json.loads(reply)
        if result["answer"] == 0:
            return []
        if not evidence_in_story(result["evidence"], story):
            return []
        return [result["answer"] - 1]

    def model_value_from_story(self, question_text, story):
        system = ("You help a community health worker fill in a patient history form from what the patient said. "
                  "Copy the answer from the patient's words in a few words. "
                  "If the patient did not say it, answer \"not mentioned\".")
        user = f"Patient said: \"{story}\"\n\nQuestion: {question_text}\nReply with JSON."
        grammar = LlamaGrammar.from_string(
            'root ::= "{\\"answer\\": \\"" text "\\"}"\n'
            "text ::= [a-zA-Z0-9 ,.'-]{1,150}\n", verbose=False)
        reply = self.generate(chat_prompt(system, user), grammar, max_tokens=170, task="value from story")
        return json.loads(reply)["answer"].strip()

    def value_from_story(self, question_text, story):
        value = self.model_value_from_story(question_text, story)
        if value.lower().startswith("not mentioned"):
            return ""
        if not mostly_from_story(value, story):
            return ""
        return value

    def explain(self, text, kind, question_text="", complaint=""):
        """One short, plain sentence about a question or an answer option. Free text, so no grammar."""
        prompt = explain_prompt(text, kind, question_text, complaint)
        reply = self.generate(prompt, max_tokens=60, task="explain")
        reply = reply.split("</think>")[-1]
        return first_sentence(reply)

    def write_summary(self, facts_text):
        system = ("You write short summaries of patient histories for a remote doctor. "
                  "Use ONLY the facts given. Do not add, guess, or diagnose anything. "
                  "Start with any RED FLAGS. Keep it under 120 words.")
        user = "Facts recorded during the visit:\n" + facts_text + "\n\nWrite the summary."
        text = self.generate(chat_prompt(system, user), max_tokens=220, task="summary")
        return text.split("</think>")[-1].strip()
