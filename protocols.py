import json
import os


HISTORY_FILES = ["patHist.json", "famHist.json", "physExam.json"]

NO_STORY_PREFILL_WORDS = ["severe", "severity"]


def list_complaints(protocol_folder):
    names = []
    for file_name in sorted(os.listdir(protocol_folder)):
        if file_name.endswith(".json") and file_name not in HISTORY_FILES:
            names.append(file_name[:-5])
    return names


KNOWN_FIXES = {
    "Lower (R) - Left Illiac Fossa": "Lower (L) - Left Iliac Fossa",
    "Illiac": "Iliac",
}


def fix_known_errors(node):
    text = node.get("text", "")
    for wrong, right in KNOWN_FIXES.items():
        text = text.replace(wrong, right)
    node["text"] = text
    for child in node.get("options", []):
        fix_known_errors(child)


def load_protocol(protocol_folder, name):
    path = os.path.join(protocol_folder, name + ".json")
    with open(path, encoding="utf-8") as f:
        protocol = json.load(f)
    fix_known_errors(protocol)
    return protocol


def is_true(value):
    return value is True or str(value).lower() == "true"


def children(node):
    return node.get("options", [])


def is_required(node):
    if is_true(node.get("isRequired")):
        return True
    return node.get("text", "").strip().endswith("*") or node.get("display", "").strip().endswith("*")


def is_multi_choice(node):
    return is_true(node.get("multi-choice")) or "pos-condition" in node


def is_exclusive(option):
    return is_true(option.get("exclude-from-multi-choice")) or is_true(option.get("is-exclusive-option"))


def input_type(node):
    return node.get("input-type")


def display_text(node, language="en"):
    if language != "en":
        translated = node.get("display-" + language)
        if translated:
            return translated.strip()
    text = node.get("display") or node.get("text", "")
    return text.replace("*", "").strip()


def story_prefill_allowed(question):
    text = display_text(question).lower()
    for word in NO_STORY_PREFILL_WORDS:
        if word in text:
            return False
    return True


def option_label(node, language="en"):
    if language != "en":
        translated = node.get("display-" + language)
        if translated:
            return translated.strip()
    return node.get("text", "").strip()


def applies_to_patient(node, patient):
    gender = node.get("gender")
    if gender is not None:
        if str(gender) == "0" and patient["sex"] != "female":
            return False
        if str(gender) == "1" and patient["sex"] != "male":
            return False

    age = patient["age"]
    age_min = node.get("age_min")
    age_max = node.get("age_max")
    if age_min is not None and age < float(age_min):
        return False
    if age_max is not None and age > float(age_max):
        return False
    return True


def split_children(answer_node):
    """An answer can hold plain choices, follow-up questions, or input boxes."""
    choices = []
    follow_up_questions = []
    for child in children(answer_node):
        if children(child) or input_type(child):
            follow_up_questions.append(child)
        else:
            choices.append(child)
    return choices, follow_up_questions


def physical_exam_steps(protocol):
    steps = protocol.get("perform-physical-exam", "")
    return [step for step in steps.split(";") if step.strip()]
