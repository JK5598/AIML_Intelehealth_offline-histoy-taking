import negation

# DRAFT red-flag rules for the 5 evaluation complaints (Abdominal Pain, Chest Discomfort or Pain,
# Cough, Fever, Headache). Not yet clinician-checked.
#
# Sources:
#   Guidelines = Intelehealth, Clinical Treatment Guidelines for Telemedicine Doctors (288 pages).
#                "page" is the PDF page, which matches the guideline's own page numbers.
#   IITT       = WHO / ICRC / MSF Interagency Integrated Triage Tool: the "Age >= 12" chart, the
#                "Age < 12" chart, and the Reference Card. One-page charts, so "section" says where.
#
# Levels (most urgent first):
#   Emergent  = IITT RED criterion ("move to high acuity resuscitation area immediately")
#   Immediate = the Intelehealth section for that condition says "immediately"
#   Urgent    = IITT YELLOW criterion ("clinical treatment area"), or Intelehealth says "urgently"
#   Refer     = Intelehealth says "refer" with no urgency word
# When an Intelehealth section uses two different words (e.g. Pneumonia: "urgently" in the plan
# box, "immediately" in the referral note), the more urgent word is used.
# Wording is applied literally, even where it looks high or low; the review sheet flags those.
#
# How matching works: the complaint name, the chosen answer labels ("question: answer" too),
# and the patient's words are joined into one lowercase text.
#   any_of:  fires if any keyword is in the text
#   all_of:  fires if every keyword is in the text
#   groups:  list of keyword lists; fires if every group has at least one keyword in the text
#   two_of:  list of keyword lists; fires if at least two groups have a keyword in the text
#   need_any: extra check; at least one of these keywords must also be in the text
#   always:  fires on the age limits alone
#   follow_up: when the rule fires, the app asks these yes/no questions (see FOLLOW_UPS)
#   min_age / max_age (years): rule only applies if min_age <= age < max_age
# Keywords copy the protocol option labels exactly where possible (including the protocol's own
# spelling, e.g. "conciousness"), then add common patient phrasings as backups.
# Patient words lose punctuation before matching ("can't" becomes "cant"), so patient-phrase
# keywords need a no-punctuation version too.

LEVELS = ["Emergent", "Immediate", "Urgent", "Refer"]

ADULT = 12  # IITT uses separate charts for age >= 12 and age < 12

BREATHING = ["difficulty breathing", "breathlessness", "shortness of breath", "breathing difficulty",
             "can't breathe", "cant breathe", "cannot breathe", "hard to breathe"]
BLOOD_IN_SPUTUM = ["hemoptysis", "haemoptysis", "red or pink", "blood in sputum", "blood in phlegm",
                   "coughing blood", "coughing up blood", "cough up blood", "coughed up blood"]
URINE_SYMPTOMS = ["burning sensation during urination", "pain during urination", "burning urination",
                  "burning while urinating", "painful urination", "dysuria"]
SEVERE_PAIN = ["severe, 7-9", "very severe, 10", "very severe / prostrating"]
PERSISTENT_VOMITING = ["persistent vomiting", "can't stop vomiting", "cant stop vomiting", "cannot stop vomiting",
                       "vomiting again and again", "vomiting a lot"]
PREGNANT = ["pregnancy status: yes", "pregnant"]
ALTERED_MENTAL = ["confused", "confusion", "altered mental", "altered sensorium", "not making sense",
                  "drowsy", "very sleepy", "agitated", "lethargic"]
FEVER_OR_COLD = ["fever", "hypothermia", "very cold body"]
STIFF_NECK = ["neck stiffness", "stiff neck"]
FAINTING = ["fainting/loss of conciousness", "fainted", "fainting", "passed out", "blacked out"]
VISION = ["visual impairment/change in vision", "double vision", "blurred vision", "change in field of vision",
          "decreased eyesight", "loss of vision", "lost vision"]
FOCAL_NEURO = ["specific weakness in particular part or side of the body", "weakness on one side",
               "one side of the body", "face drooping", "slurred speech", "cant move my arm", "can't move my arm",
               "cant move my leg", "can't move my leg"]

RULES = [
    # ================= Emergent: IITT RED =================
    {"name": "Unresponsive", "level": "Emergent", "source": "IITT", "section": "both charts, red: top",
     "any_of": ["unresponsive", "unconscious", "not responding", "coma"]},
    {"name": "Respiratory distress, stridor or cyanosis", "level": "Emergent", "source": "IITT",
     "section": "both charts, red: Airway & Breathing; Reference Card: signs of respiratory distress",
     "also": "Guidelines p. 271 lists the same signs under Pneumonia",
     "any_of": ["chest indrawing: yes", "stridor/grunting: yes", "cyanosis", "blue lips", "lips turned blue",
                "gasping", "nasal flaring", "noisy breathing", "unable to talk", "cant talk", "can't talk",
                "cannot speak", "unable to breastfeed", "cant breastfeed", "accessory muscle"]},
    {"name": "Signs of shock or heavy bleeding", "level": "Emergent", "source": "IITT",
     "section": "both charts, red: Circulation",
     "any_of": ["cold and clammy", "cold clammy", "clammy skin", "cold hands and feet", "cold extremities",
                "heavy bleeding", "bleeding a lot", "bleeding wont stop", "bleeding won't stop"]},
    {"name": "Convulsions", "level": "Emergent", "source": "IITT", "section": "both charts, red: Disability",
     "any_of": ["convulsion", "seizure", "fitting", "had a fit"]},
    {"name": "Possible meningitis (stiff neck or confusion, with fever or headache)", "level": "Emergent",
     "source": "IITT", "section": "Age >= 12 chart, red: Disability ('any two of')", "min_age": ADULT,
     "also": "Team decision: headache + fever alone is Urgent and triggers the follow-up questions",
     "two_of": [ALTERED_MENTAL, FEVER_OR_COLD, STIFF_NECK, ["headache"]], "need_any": ALTERED_MENTAL + STIFF_NECK},
    {"name": "Headache with fever (meningitis signs checked)", "level": "Urgent", "source": "IITT",
     "section": "Age >= 12 chart, red: Disability ('any two of'); team decision: Urgent unless a follow-up answer is yes",
     "min_age": ADULT, "groups": [["headache"], FEVER_OR_COLD], "follow_up": "meningitis"},
    {"name": "Child: headache with fever (meningitis signs checked)", "level": "Urgent", "source": "IITT",
     "section": "Age < 12 chart, yellow: Headache; red: Disability", "max_age": ADULT,
     "groups": [["headache"], FEVER_OR_COLD], "follow_up": "meningitis"},
    {"name": "Child: altered mental status with stiff neck or fever", "level": "Emergent", "source": "IITT",
     "section": "Age < 12 chart, red: Disability", "max_age": ADULT,
     "groups": [ALTERED_MENTAL + ["continuously irritable", "restless"], STIFF_NECK + FEVER_OR_COLD]},
    {"name": "Chest or abdominal pain over age 50", "level": "Emergent", "source": "IITT",
     "section": "Age >= 12 chart, red: Other ('acute chest or abdominal pain (>50 years old)')", "min_age": 50.0001,
     "any_of": ["chest discomfort or pain", "chest pain", "pain/tightness of chest", "abdominal pain"]},
    {"name": "Pregnant with bleeding, seizures, confusion, vision change or labour", "level": "Emergent",
     "source": "IITT", "section": "Age >= 12 chart, red: Pregnant with any of",
     "groups": [PREGNANT, ["heavy bleeding", "bleeding", "convulsion", "seizure", "confused", "confusion"]
                + VISION + ["labour", "labor pain", "water broke", "injury", "accident", "fell"]]},
    {"name": "Pregnant with severe abdominal pain", "level": "Emergent", "source": "IITT",
     "section": "Age >= 12 chart, red: Pregnant with any of",
     "groups": [PREGNANT, ["abdominal pain", "stomach pain", "belly pain"], SEVERE_PAIN]},
    {"name": "Pregnant with severe headache", "level": "Emergent", "source": "IITT",
     "section": "Age >= 12 chart, red: Pregnant with any of", "groups": [PREGNANT, ["headache"], SEVERE_PAIN]},
    {"name": "Snake bite", "level": "Emergent", "source": "IITT", "section": "both charts, red: Other",
     "any_of": ["snake bite", "snakebite", "bitten by a snake", "snake bit"]},
    {"name": "Poisoning or dangerous ingestion", "level": "Emergent", "source": "IITT",
     "section": "both charts, red: Other; Reference Card",
     "any_of": ["poison", "pesticide", "overdose", "drank kerosene", "swallowed kerosene"]},
    {"name": "Newborn under 8 days old", "level": "Emergent", "source": "IITT",
     "section": "Age < 12 chart, red: Other", "max_age": 8 / 365, "always": True},
    {"name": "Infant under 2 months with fever", "level": "Emergent", "source": "IITT",
     "section": "Age < 12 chart, red: Other (temp <36 or >39C; reported fever used here)", "max_age": 2 / 12,
     "any_of": FEVER_OR_COLD},

    # ================= Immediate: Intelehealth "immediately" =================
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

    # ================= Urgent: IITT YELLOW =================
    {"name": "Wheezing", "level": "Urgent", "source": "IITT", "section": "both charts, yellow: Airway & Breathing",
     "any_of": ["wheezing", "wheeze"]},
    {"name": "Swelling or mass of mouth, throat or neck", "level": "Urgent", "source": "IITT",
     "section": "both charts, yellow: Airway & Breathing",
     "any_of": ["swelling in my throat", "throat swelling", "neck swelling", "swelling in the neck",
                "lump in my neck", "lump in the neck", "swollen tongue", "mouth swelling"]},
    {"name": "Vomits everything or unable to drink", "level": "Urgent", "source": "IITT",
     "section": "both charts, yellow: Circulation",
     "any_of": ["vomits everything", "vomiting everything", "cant keep anything down", "can't keep anything down",
                "unable to drink", "cant drink", "can't drink", "unable to eat or drink", "not able to drink",
                "unable to feed", "not feeding"] + PERSISTENT_VOMITING},
    {"name": "Ongoing diarrhoea", "level": "Urgent", "source": "IITT", "section": "both charts, yellow: Circulation",
     "any_of": ["diarrhea", "diarrhoea", "loose motion", "loose stool"]},
    {"name": "Child: dehydration", "level": "Urgent", "source": "IITT", "section": "Age < 12 chart, yellow: Circulation",
     "max_age": ADULT, "any_of": ["dehydrat", "very thirsty", "sunken eyes", "no urine", "not passing urine"]},
    {"name": "Severe pallor", "level": "Urgent", "source": "IITT", "section": "both charts, yellow: Circulation",
     "any_of": ["severe pallor", "very pale"]},
    {"name": "Recent fainting", "level": "Urgent", "source": "IITT", "section": "Age >= 12 chart, yellow: Circulation",
     "min_age": ADULT, "any_of": FAINTING},
    {"name": "Altered mental status or agitation", "level": "Urgent", "source": "IITT",
     "section": "Age >= 12 chart, yellow: Disability", "min_age": ADULT, "any_of": ALTERED_MENTAL},
    {"name": "Child: restless, irritable or lethargic", "level": "Urgent", "source": "IITT",
     "section": "Age < 12 chart, yellow: Disability", "max_age": ADULT,
     "any_of": ["restless", "continuously irritable", "lethargic", "lethargy", "very sleepy"]},
    {"name": "Acute general weakness", "level": "Urgent", "source": "IITT", "section": "Age >= 12 chart, yellow: Disability",
     "min_age": ADULT, "any_of": ["general weakness", "too weak to stand", "cant stand", "can't stand"]},
    {"name": "Acute focal neurologic complaint", "level": "Urgent", "source": "IITT",
     "section": "Age >= 12 chart, yellow: Disability", "min_age": ADULT, "any_of": FOCAL_NEURO},
    {"name": "Acute visual disturbance", "level": "Urgent", "source": "IITT",
     "section": "Age >= 12 chart, yellow: Disability", "min_age": ADULT, "any_of": VISION},
    {"name": "Severe pain", "level": "Urgent", "source": "IITT", "section": "both charts, yellow: Disability",
     "any_of": SEVERE_PAIN + ["worst pain", "unbearable pain"]},
    {"name": "Child: headache", "level": "Urgent", "source": "IITT", "section": "Age < 12 chart, yellow: Other",
     "max_age": ADULT, "any_of": ["headache"]},
    {"name": "Child: pregnancy", "level": "Urgent", "source": "IITT", "section": "Age < 12 chart, yellow: Other",
     "max_age": ADULT, "any_of": PREGNANT},
    {"name": "Infant 8 days to 6 months old", "level": "Urgent", "source": "IITT",
     "section": "Age < 12 chart, yellow: Other", "min_age": 8 / 365, "max_age": 0.5, "always": True},
    {"name": "Child: severe wasting or swelling of both feet", "level": "Urgent", "source": "IITT",
     "section": "Age < 12 chart, yellow: Other", "max_age": ADULT,
     "any_of": ["severe wasting", "very thin", "both feet swollen", "swelling of both feet", "swollen feet"]},
    {"name": "Testicular or scrotal pain", "level": "Urgent", "source": "IITT", "section": "both charts, yellow/red: Other",
     "also": "red on the Age < 12 chart", "any_of": ["testicular pain", "pain in testicle", "scrotal pain",
                                                   "scrotum", "testicle"]},
    {"name": "Unable to pass urine", "level": "Urgent", "source": "IITT", "section": "Age >= 12 chart, yellow: Other",
     "min_age": ADULT, "any_of": ["unable to pass urine", "cant pass urine", "can't pass urine", "cannot pass urine",
                                  "not passing urine"]},
    {"name": "Animal bite", "level": "Urgent", "source": "IITT", "section": "both charts, yellow: Other",
     "any_of": ["dog bite", "animal bite", "bitten by a dog", "monkey bite", "cat bite"]},
    {"name": "Rash worsening over hours or peeling", "level": "Urgent", "source": "IITT",
     "section": "both charts, yellow: Other", "any_of": ["peeling skin", "skin peeling", "rash spreading fast",
                                                         "rash getting worse quickly"]},

    # ================= Refer: Intelehealth plain "refer" =================
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
     "also": "GERD referral criterion; over 50 it is also IITT red",
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

# Follow-up questions: asked once, as soon as a rule with "follow_up" fires.
#   Yes        -> saves "label", which matches the keywords of the more urgent rule (e.g. Emergent meningitis)
#   No         -> saved as a "No", so it can never raise a flag
#   Don't know -> saved as "label (not sure)", which still matches: an unsure answer never lowers the level
# The questions are the IITT red criteria themselves, so the level still traces to the chart.
FOLLOW_UPS = {
    "meningitis": [
        {"id": "stiff_neck", "label": "Neck stiffness",
         "question": "Is the neck stiff? (Ask the patient to touch chin to chest. Pain or can't = yes)"},
        {"id": "altered", "label": "Confusion or drowsiness",
         "question": "Is the patient confused, very drowsy or hard to wake? (Ask the family too)"},
        {"id": "seizure", "label": "Seizure",
         "question": "Has the patient had a seizure or fit with this illness?"},
    ],
}


def follow_ups_for(flag_names):
    """Follow-up questions for the flags that fired, in order, without repeats."""
    items, seen = [], set()
    for name in flag_names:
        key = RULES_BY_NAME.get(name, {}).get("follow_up")
        for item in FOLLOW_UPS.get(key, []):
            if item["id"] not in seen:
                seen.add(item["id"])
                items.append(item)
    return items


def describe(name):
    """Alert text for the CHW, e.g. 'IMMEDIATE: Suspected pneumonia (Guidelines p. 271)'."""
    rule = RULES_BY_NAME.get(name)
    if not rule:
        return name
    if rule.get("page"):
        where = f"{rule['source']} p. {rule['page']}"
    else:
        where = rule["source"] + (" red" if rule["level"] == "Emergent" else " yellow" if rule["source"] == "IITT" else "")
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


def age_applies(rule, patient):
    if "min_age" not in rule and "max_age" not in rule:
        return True
    if not patient or patient.get("age") is None:
        return False
    age = float(patient["age"])
    return rule.get("min_age", 0) <= age < rule.get("max_age", 200)


def rule_matches(rule, text, patient=None):
    if not age_applies(rule, patient):
        return False
    if rule.get("always"):
        return True
    if "need_any" in rule and not any(word in text for word in rule["need_any"]):
        return False
    if "two_of" in rule:
        return sum(any(word in text for word in group) for group in rule["two_of"]) >= 2
    if "groups" in rule:
        return all(any(word in text for word in group) for group in rule["groups"])
    if "all_of" in rule:
        return all(word in text for word in rule["all_of"])
    if "any_of" in rule:
        return any(word in text for word in rule["any_of"])
    return False


def matching_rules(text, patient=None):
    return [rule["name"] for rule in RULES if rule_matches(rule, text, patient)]


def said_no_text(complaint, answers):
    pieces = [complaint]
    for answer in answers:
        if answer.get("status") == "said_no":
            pieces.extend(answer_pieces(answer))
    return " | ".join(pieces).lower()


def check(complaint, answers, patient=None):
    """Returns (red flags, possible red flags), most urgent first.
    A possible red flag only shows up inside a 'no ...' phrase. We still show it, because
    missing a real red flag is worse than a false alarm. Once the CHW has saved the matching
    'No', the possible red flag is dropped."""
    flags = matching_rules(visit_text(complaint, answers, keep_no_phrases=False), patient)
    explained = matching_rules(said_no_text(complaint, answers), patient)
    possible = []
    for name in matching_rules(visit_text(complaint, answers, keep_no_phrases=True), patient):
        if name not in flags and name not in explained:
            possible.append(name)
    return sort_by_level(flags), sort_by_level(possible)