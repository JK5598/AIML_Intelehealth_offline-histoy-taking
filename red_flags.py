import negation

# PLACEHOLDER RULES - not clinically validated.
# Replace with Intelehealth's / a clinician's red-flag criteria before any real use.
RULES = [
    {"name": "Chest pain with breathlessness", "all_of": ["chest", "breath"]},
    {"name": "Vomiting blood", "any_of": ["vomiting blood", "blood in vomit", "hematemesis"]},
    {"name": "Blood in stool or black stool", "any_of": ["black stool", "blood in stool", "malena", "melena"]},
    {"name": "Loss of consciousness", "any_of": ["loss of consciousness", "syncope", "fainted", "unconscious"]},
    {"name": "Breathing difficulty", "any_of": ["difficulty breathing", "breathlessness", "shortness of breath"]},
    {"name": "Sudden weakness or paralysis", "any_of": ["paralysis", "weakness in particular part"]},
    {"name": "Neck stiffness", "any_of": ["neck stiffness", "stiff neck"]},
]


def visit_text(complaint, answers, keep_no_phrases):
    """Answers the CHW saved as 'No' are always left out. 'no ...' phrases in the patient's words are optional."""
    pieces = [complaint]
    for answer in answers:
        if answer.get("status") in ("said_no", "skipped"):
            continue
        pieces.extend(answer["answers"])
        if answer["value"]:
            pieces.append(str(answer["value"]))
        if answer["patient_words"]:
            if keep_no_phrases:
                pieces.append(answer["patient_words"])
            else:
                pieces.append(negation.remove_negated(answer["patient_words"]))
    return " | ".join(pieces).lower()


def matching_rules(text):
    found = []
    for rule in RULES:
        if "all_of" in rule and all(word in text for word in rule["all_of"]):
            found.append(rule["name"])
        elif "any_of" in rule and any(word in text for word in rule["any_of"]):
            found.append(rule["name"])
    return found


def said_no_text(complaint, answers):
    pieces = [complaint]
    for answer in answers:
        if answer.get("status") == "said_no":
            pieces.extend(answer["answers"])
    return " | ".join(pieces).lower()


def check(complaint, answers):
    """Returns (red flags, possible red flags).
    A possible red flag only shows up inside a 'no ...' phrase. We still show it, because
    missing a real red flag is worse than a false alarm. Once the CHW has saved the matching
    'No', the possible red flag is dropped."""
    flags = matching_rules(visit_text(complaint, answers, keep_no_phrases=False))
    explained = matching_rules(said_no_text(complaint, answers))
    possible = []
    for name in matching_rules(visit_text(complaint, answers, keep_no_phrases=True)):
        if name not in flags and name not in explained:
            possible.append(name)
    return flags, possible
