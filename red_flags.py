import negation

# DRAFT red-flag rules for the 5 evaluation complaints (Abdominal Pain, Chest Discomfort or Pain,
# Cough, Fever, Headache). Not yet clinician-checked.
#
# Sources:
#   Guidelines = Intelehealth, Clinical Treatment Guidelines for Telemedicine Doctors (288 pages).
#                "page" is the PDF page, which matches the guideline's own page numbers.
#   ETAT       = WHO Paediatric Emergency Triage, Assessment and Treatment (2016). Used only for the
#                Emergent level, which the guidelines do not define. Page numbers still to be added.
#
# Levels (most urgent first):
#   Emergent  = WHO ETAT emergency sign
#   Immediate = the guideline section for that condition says "immediately"
#   Urgent    = the guideline section says "urgently" (and never "immediately")
#   Refer     = the guideline section says "refer" with no urgency word
# When a section uses two different words (e.g. Pneumonia: "urgently" in the plan box,
# "immediately" in the referral note), the more urgent word is used.
#
# How matching works: the complaint name, the chosen answer labels ("question: answer" too),
# and the patient's words are joined into one lowercase text.
#   any_of: fires if any keyword is in the text
#   all_of: fires if every keyword is in the text
#   groups: a list of keyword lists; fires if every group has at least one keyword in the text
# Keywords copy the protocol option labels exactly where possible (including the protocol's own
# spelling, e.g. "conciousness"), then add common patient phrasings as backups.
# Patient words lose punctuation before matching ("can't" becomes "cant"), so patient-phrase
# keywords need a no-punctuation version too.

LEVELS = ["Emergent", "Immediate", "Urgent", "Refer"]

BREATHING = ["difficulty breathing", "breathlessness", "shortness of breath", "breathing difficulty",
             "can't breathe", "cant breathe", "cannot breathe", "hard to breathe"]
BLOOD_IN_SPUTUM = ["hemoptysis", "haemoptysis", "red or pink", "blood in sputum", "blood in phlegm",
                   "coughing blood", "coughing up blood", "cough up blood", "coughed up blood"]
URINE_SYMPTOMS = ["burning sensation during urination", "pain during urination", "burning urination",
                  "burning while urinating", "painful urination", "dysuria"]
SEVERE_PAIN = ["severe, 7-9", "very severe, 10"]
PERSISTENT_VOMITING = ["persistent vomiting", "can't stop vomiting", "cant stop vomiting", "cannot stop vomiting",
                       "vomiting again and again", "vomiting a lot"]

RULES = [
    # ---------------- Emergent (WHO ETAT) ----------------
    {"name": "Convulsions", "level": "Emergent", "source": "ETAT", "page": None,
     "any_of": ["convulsion", "seizure", "fitting", "had a fit"]},
    {"name": "Unconscious or unresponsive", "level": "Emergent", "source": "ETAT", "page": None,
     "any_of": ["unconscious", "unresponsive", "not responding", "coma"]},
    {"name": "Severe breathing distress (chest indrawing, stridor, cyanosis)", "level": "Emergent",
     "source": "ETAT", "page": None, "also": "Guidelines p. 271 lists the same signs under Pneumonia",
     "any_of": ["chest indrawing: yes", "stridor/grunting: yes", "cyanosis", "blue lips", "lips turned blue",
                "air hunger", "gasping", "noisy breathing"]},
    {"name": "Signs of shock", "level": "Emergent", "source": "ETAT", "page": None,
     "any_of": ["cold and clammy", "cold clammy", "clammy skin", "cold hands and feet"]},

    # ---------------- Immediate ----------------
    {"name": "Suspected pneumonia", "level": "Immediate", "source": "Guidelines", "page": 271,
     "also": "children: p. 33, p. 73",
     "groups": [["cough"], ["fever"],
                BREATHING + ["chest discomfort", "chest pain", "pain/tightness of chest"] + BLOOD_IN_SPUTUM]},
    {"name": "Blood in sputum", "level": "Immediate", "source": "Guidelines", "page": 271,
     "groups": [["cough", "sputum", "phlegm"], BLOOD_IN_SPUTUM]},
    {"name": "Suspected appendicitis", "level": "Immediate", "source": "Guidelines", "page": 269,
     "groups": [["right iliac fossa", "lower right", "right lower"],
                ["nausea", "vomiting", "fever", "anorexia", "movement", "coughing"]]},
    {"name": "Upper or complicated urinary infection", "level": "Immediate", "source": "Guidelines",
     "page": 174, "groups": [URINE_SYMPTOMS, ["fever", "vomiting", "flanks", "flank pain", "confusion"]]},
    {"name": "Diarrhea with persistent vomiting or severe pain", "level": "Immediate", "source": "Guidelines",
     "page": 161, "groups": [["diarrhea", "loose stool", "loose motion"], PERSISTENT_VOMITING + SEVERE_PAIN]},

    # ---------------- Refer ----------------
    {"name": "Bloody, bilious or projectile vomiting", "level": "Refer", "source": "Guidelines", "page": 126,
     "also": "haematemesis also p. 131",
     "any_of": ["vomiting blood", "vomited blood", "blood in vomit", "hematemesis", "haematemesis",
                "bilious", "green vomit", "projectile"]},
    {"name": "Jaundice", "level": "Refer", "source": "Guidelines", "page": 126,
     "also": "with fever: complicated malaria, p. 84-85",
     "any_of": ["jaundice", "yellow eyes", "yellow skin", "eyes are yellow", "eyes turned yellow"]},
    {"name": "Severe abdominal pain", "level": "Refer", "source": "Guidelines", "page": 126,
     "groups": [["abdominal pain", "stomach pain", "belly pain"], SEVERE_PAIN]},
    {"name": "Abdominal distention", "level": "Refer", "source": "Guidelines", "page": 159,
     "also": "typhoid p. 138",
     "any_of": ["abdominal distention", "abdominal distension", "swollen belly", "swollen stomach",
                "belly is swollen", "stomach is swollen"]},
    {"name": "Persistent vomiting", "level": "Refer", "source": "Guidelines", "page": 159,
     "also": "p. 131, p. 138, p. 155", "any_of": PERSISTENT_VOMITING},
    {"name": "Weight loss, swallowing difficulty or abdominal mass", "level": "Refer", "source": "Guidelines",
     "page": 131, "also": "GERD p. 155",
     "any_of": ["weight loss", "losing weight", "lost weight", "difficulty swallowing", "trouble swallowing",
                "dysphagia", "abdominal mass", "lump in my stomach", "lump in the stomach", "lump in abdomen"]},
    {"name": "Chest pain", "level": "Refer", "source": "Guidelines", "page": 155,
     "also": "GERD referral criterion; no cardiac chapter in the guidelines",
     "any_of": ["chest discomfort or pain", "chest pain", "pain/tightness of chest"]},
    {"name": "Cough for more than 2 weeks", "level": "Refer", "source": "Guidelines", "page": 215,
     "any_of": ["subacute ( 2 - 8 weeks)", "chronic (more than 8 weeks)"]},
    {"name": "Breathing difficulty with cough", "level": "Refer", "source": "Guidelines", "page": 215,
     "groups": [["cough"], BREATHING]},
    {"name": "Fever with signs of complicated malaria", "level": "Refer", "source": "Guidelines", "page": 85,
     "groups": [["fever"], ["confusion", "confused", "altered sensorium", "drowsy", "very pale",
                            "severe pallor", "cold hands", "cold feet"]]},
    {"name": "Frequent or chronic headache", "level": "Refer", "source": "Guidelines", "page": 141,
     "also": "same text p. 275",
     "any_of": ["chronic, continuous", "acute, recurrent"]},
]

RULES_BY_NAME = {rule["name"]: rule for rule in RULES}


def describe(name):
    """Alert text for the CHW, e.g. 'IMMEDIATE: Suspected pneumonia (Guidelines p. 271)'."""
    rule = RULES_BY_NAME.get(name)
    if not rule:
        return name
    where = rule["source"] + (f" p. {rule['page']}" if rule.get("page") else "")
    return f"{rule['level'].upper()}: {name} ({where})"


def level_of(name):
    rule = RULES_BY_NAME.get(name)
    return rule["level"] if rule else None


def sort_by_level(names):
    return sorted(names, key=lambda n: LEVELS.index(level_of(n)) if level_of(n) in LEVELS else len(LEVELS))


def answer_pieces(answer):
    pieces = list(answer["answers"])
    label = (answer.get("question_label") or "").replace("*", "").strip()
    if label:
        pieces.extend(f"{label}: {a}" for a in answer["answers"])
    return pieces


def visit_text(complaint, answers, keep_no_phrases):
    """Answers the CHW saved as 'No' are always left out. 'no ...' phrases in the patient's words are optional."""
    pieces = [complaint]
    for answer in answers:
        if answer.get("status") in ("said_no", "skipped"):
            continue
        pieces.extend(answer_pieces(answer))
        if answer["value"]:
            pieces.append(str(answer["value"]))
        if answer["patient_words"]:
            if keep_no_phrases:
                pieces.append(answer["patient_words"])
            else:
                pieces.append(negation.remove_negated(answer["patient_words"]))
    return " | ".join(pieces).lower()


def rule_matches(rule, text):
    if "groups" in rule:
        return all(any(word in text for word in group) for group in rule["groups"])
    if "all_of" in rule:
        return all(word in text for word in rule["all_of"])
    if "any_of" in rule:
        return any(word in text for word in rule["any_of"])
    return False


def matching_rules(text):
    return [rule["name"] for rule in RULES if rule_matches(rule, text)]


def said_no_text(complaint, answers):
    pieces = [complaint]
    for answer in answers:
        if answer.get("status") == "said_no":
            pieces.extend(answer_pieces(answer))
    return " | ".join(pieces).lower()


def check(complaint, answers):
    """Returns (red flags, possible red flags), most urgent first.
    A possible red flag only shows up inside a 'no ...' phrase. We still show it, because
    missing a real red flag is worse than a false alarm. Once the CHW has saved the matching
    'No', the possible red flag is dropped."""
    flags = matching_rules(visit_text(complaint, answers, keep_no_phrases=False))
    explained = matching_rules(said_no_text(complaint, answers))
    possible = []
    for name in matching_rules(visit_text(complaint, answers, keep_no_phrases=True)):
        if name not in flags and name not in explained:
            possible.append(name)
    return sort_by_level(flags), sort_by_level(possible)