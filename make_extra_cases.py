"""Builds the 10 extra test cases (TC06, TC07, TC09, TC14, TC19, TC20, TC21, TC27, TC28, TC30) from Yuqi's Nov 21
drafts (Test Case Patient Description.docx, Test Cases Organization.xlsx), in three separate files so TC01-TC05 stay
exactly as they were:
  eval_cases_extra.json            the case, its story and the expected red flags
  eval_patient_answers_extra.json  the answer-sheet patient (same format and rules as eval_patient_answers.json)
  eval_key_facts_extra.csv         the key facts (Yuqi's, with 'Askable' and 'Protocol question' added; a few merged,
                                   split or added from the patient's own words, marked in Review Status)
Written by Claude (Nov 23) for the team to check. Rules as for TC01-TC05:
- Symptoms: only what the story says. If it doesn't say, the patient answers "I'm not sure."
- Personal history the story leaves out (smoking, alcohol, allergies, medicines, family history): the plain "no",
  listed under "assumed" so a judge treats it as unsupported, not as an app error.
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
UNSURE = {"say": "I'm not sure."}

HISTORY_LIST = "Do you have a history of any of the following?"
MEDICINES = "Have you recently taken any kind of medicine (including ayurvedic/homeopathic/unani/herbal)?"
ALLERGIES = "Do you have any allergies?"
TOBACCO = "Do you chew tobbaco?"
SMOKING = "Smoking history"
ALCOHOL = "Alcohol use"
FAMILY = "Do you have a family history of any of the following?"
PREGNANCY = "Pregnancy status"
TREATMENT = ("Have you taken any treatment (including self-medication or home remedies) or seen any health provider "
             "for this problem before coming here today?")
SYMPTOMS = "Do you have the following symptom(s)?"
SINCE_WHEN = "Since when have you had this symptom?"
HOW_LONG = "How long, in days / weeks / months"


def assumed_history():
    return {
        MEDICINES: {"say": "No, I'm not taking any medicines.", "has": ["No"]},
        ALLERGIES: {"say": "No, no allergies.", "has": ["No known allergies"]},
        TOBACCO: {"say": "No, I don't chew tobacco.", "has": ["Do not Chew"]},
        SMOKING: {"say": "I've never smoked.", "has": ["Never-smoker"]},
        ALCOHOL: {"say": "No, I don't drink.", "has": ["No"]},
        FAMILY: {"say": "No, nothing runs in my family that I know of.", "has": ["None"]},
    }


ASSUMED = list(assumed_history().keys())
NOT_PREGNANT_ASSUMED = {"say": "No, I'm not pregnant.", "has": ["No"]}

cases = []
sheets = {}
facts = []
stories = json.load(open(os.path.join(HERE, "extra_case_stories.json"), encoding="utf-8"))


def add_case(case_id, source, diagnosis, age, sex, complaint, expected, only_if_asked="", notes=""):
    cases.append({"id": case_id, "source_case": source + " (Verma N., 190 teaching cases)", "diagnosis": diagnosis,
                  "age": age, "sex": sex, "complaint": complaint, "story": stories[case_id]["story"],
                  "only_if_asked": only_if_asked, "exam_findings_not_for_patient": notes,
                  "expected_red_flags": [{"name": n, "level": lv} for n, lv in expected]})


def add_facts(case_id, rows):
    """rows: (fact id number, category, expected fact, patient answer, scored?, askable, protocol question, red flag?,
    status)"""
    for n, category, fact, answer, scored, askable, protocol_q, red_flag, status in rows:
        facts.append({"Case ID": case_id, "Fact ID": f"{case_id}-F{n:02d}", "Category": category, "Source Text": "",
                      "Expected Fact": fact, "Patient Answer": answer,
                      "Include in History Score?": "Yes" if scored else "No",
                      "Askable by protocol?": askable, "Protocol question": protocol_q,
                      "Potential Red Flag": "Yes" if red_flag else "No", "Review Status": status, "Notes": ""})


Y = "Yuqi draft (Nov 21)"
YE = "Yuqi draft, wording matched to the patient description (Claude)"
C = "Added by Claude from the patient description (Nov 23)"

# =====================================================================================================
# TC06: 35-year-old woman, weight gain and swelling (hypothyroidism). Complaint: Weight gain
# =====================================================================================================
add_case("TC06", "Endoc7", "Hypothyroidism", 35, "female", "Weight gain", [])
q = assumed_history()
q.update({
    "Amount of weight gained in kgs": {"say": "I'm not sure how many kilos."},
    SINCE_WHEN: {"say": "A few months, and it keeps getting worse.", "accept": ["month"]},
    SYMPTOMS: {
        "say": "I feel really tired and weak and achy all over, I can't stand the cold, and I've been constipated. "
               "I'm sleepy most of the time, my concentration and memory are worse, my voice has gone hoarse and my "
               "skin is rough and dry. My periods haven't stopped; they've been very heavy.",
        "has": ["Constipation", "Cold intolerance", "Muscle weakness", "Other [describe]"],
        "not": ["Amenorrhea"]},
    "Other [describe]": {"say": "Sleepy most of the time, poor concentration and memory, hoarse voice, rough dry skin, "
                                "and my whole body is swelling."},
    "Have you ever been diagnosed with any of the following specific diseases?": {
        "say": "No, I've never had thyroid problems.", "not": ["Thyroid dysfunction ( Hypo/hyperthyroidism )"]},
    "Change of Appetite": {"say": "My appetite is gone. I'm barely eating anything.", "has": ["Decreased"]},
    "Eating habits": UNSURE,
    "Do you exercise regularly (>30 min/day)?": UNSURE,
    TREATMENT: {"say": "I was given calcium tablets and vitamins at some point.", "has": ["Yes [Describe]"]},
    "Yes [Describe]": {"say": "Calcium tablets and vitamins."},
    "Additional information": {
        "say": "My periods have been very heavy for the last few months; they used to be normal. No chest pain, "
               "palpitations or trouble breathing. No tingling or numbness, and I haven't passed out. No thyroid "
               "surgery or radiation to my neck. I haven't given birth in the last six months. Before this started I "
               "wasn't on any medicines, not even birth control pills. No one in my family has had anything like this."},
    "Have you taken any medication recently?": {
        "say": "Calcium tablets and vitamins. Before this started I wasn't on any medicines, not even birth control pills."},
    PREGNANCY: {"say": "I don't know.", "has": ["Don't know"]},
    HISTORY_LIST: {"say": "I don't have high blood pressure or diabetes, and no thyroid problems.",
                   "not": ["High Blood Pressure", "Diabetes"]},
    MEDICINES: {"say": "Yes, calcium tablets and vitamins.", "has": ["Yes"]},
    "Name of Medications": {"say": "Calcium tablets and vitamins.", "has": ["Medication name 1"]},
    "Medication Name": {"say": "Calcium tablets and vitamins."},
    "From": UNSURE, "To": UNSURE,
    "How often do you have trouble taking medicines the way you have been told to take them?": UNSURE,
    FAMILY: {"say": "No one in my family has had anything like this.", "has": ["None"]},
    HOW_LONG: {"say": "A few months. I can't say exactly."},
})
sheets["TC06"] = {"questions": q, "denies": ["Amenorrhea", "High Blood Pressure", "Diabetes",
                                             "Thyroid dysfunction ( Hypo/hyperthyroidism )"],
                  "assumed": [ALLERGIES, TOBACCO, SMOKING, ALCOHOL, FAMILY]}
add_facts("TC06", [
    (2, "Chief complaint / Duration", "Weight gain and generalized swelling for a few months.", "", True, "Yes",
     "Since when; Additional information", False, YE),
    (3, "Progression", "Weight gain and swelling are getting worse.", "", True, "Partly", "Since when / Additional information", False, Y),
    (4, "Appetite", "Appetite is reduced despite the weight gain.", "", True, "Yes", "Change of Appetite: Decreased", False, Y),
    (5, "Associated symptoms", "Cold intolerance; prefers warmth.", "", True, "Yes", "Symptoms: Cold intolerance", False, Y),
    (6, "Associated symptoms", "Tiredness and marked weakness.", "", True, "Yes", "Symptoms: Muscle weakness / Other", False, YE),
    (7, "Associated symptoms", "Generalized body aches.", "", True, "Partly", "Symptoms: Other [describe]", False, Y),
    (8, "Bowel symptoms", "Constipation.", "", True, "Yes", "Symptoms: Constipation", False, Y),
    (9, "Sleep / Functional impact", "Sleepy much of the time, including at work.", "", True, "Partly", "Symptoms: Other [describe]", False, Y),
    (10, "Cognitive symptoms", "Concentration and memory worse since the illness began.", "", True, "Partly", "Symptoms: Other [describe]", False, Y),
    (11, "Voice changes", "Recent hoarse voice.", "", True, "Partly", "Symptoms: Other [describe]", False, Y),
    (12, "Skin symptoms", "Rough, dry skin.", "", True, "Partly", "Symptoms: Other [describe]", False, Y),
    (13, "Pertinent negatives", "No chest pain, palpitations or breathlessness.", "", True, "Partly", "Additional information", False, Y),
    (14, "Pertinent negatives", "No tingling or numbness of hands or feet, and no loss of consciousness.", "", True, "Partly",
     "Additional information", False, Y),
    (15, "Menstrual history", "Heavy periods for the last few months; previously normal.", "", True, "Partly",
     "Symptoms: Amenorrhea said no; Additional information", False, YE),
    (16, "Past medical history", "No high blood pressure or diabetes.", "", True, "Yes", "Past history list (said no)", False, Y),
    (17, "Thyroid history", "No thyroid disease, thyroid surgery or neck radiation.", "", True, "Partly",
     "Diagnosed diseases: Thyroid dysfunction (said no); Additional information", False, Y),
    (18, "Obstetric history", "No childbirth or difficult delivery in the last 6 months.", "", True, "Partly", "Additional information", False, Y),
    (19, "Medication history", "No medicines, including birth control pills, before the illness began.", "", True, "Yes",
     "Have you taken any medication recently?", False, Y),
    (20, "Family history", "No one in the family has had a similar illness.", "", True, "Yes", "Family history", False, Y),
    (21, "Previous treatment", "Was given calcium tablets and vitamins.", "", True, "Yes", "Treatment taken: Yes [Describe]", False, Y),
])

# =====================================================================================================
# TC07: 49-year-old woman, upper GI discomfort for 2 years (functional dyspepsia). Complaint: Dyspepsia
# =====================================================================================================
add_case("TC07", "GI1", "Dyspepsia", 49, "female", "Dyspepsia", [])
q = assumed_history()
q.update({
    SINCE_WHEN: {"say": "About two years.", "accept": ["2 year", "two year"]},
    "How does this symptom start?": UNSURE,
    SYMPTOMS: {"say": "It's a discomfort in my upper stomach, and I feel really full even after a normal-sized meal, nothing big. "
                      "My weight hasn't changed.",
               "has": ["Abdominal pain", "Other [describe]"], "not": ["Weight change (kg)"]},
    "Which part of the abdomen do you feel pain?": {"say": "My upper stomach, in the middle.",
                                                    "has": ["Upper (C) - Epigastric"]},
    "How did the abdominal pain start?": UNSURE,
    "How has the abdominal pain progressed?": {
        "say": "It's there every day. It comes and goes in how bad it is, but it never really goes away."},
    "Describe the pain": {"say": "It's a discomfort that never really goes away, though how bad it is changes.",
                          "has": ["Constant"]},
    "When does the pain increase?": {"say": "Eating tends to make it worse.", "has": ["Postprandial"]},
    "Does the pain go to other part of the body?": UNSURE,
    "Other [describe]": {"say": "I feel really full even after a normal-sized meal, nothing big."},
    "Has anyone of your family members been diagnosed with cancers or gastric/duodenal ulcer?": {
        "say": "Nothing runs in the family that I know of.", "has": ["No"]},
    "Eating habits": UNSURE,
    "Have you ever been diagnosed with any of the following specific diseases?": {
        "say": "No. My only other medical thing is the occasional migraine.", "has": ["None"]},
    TREATMENT: {"say": "I've had a bunch of tests over the past couple of years, an upper GI series, an ultrasound and a "
                       "HIDA scan, an endoscopy and a gastric emptying scan, and I was told they were all normal.",
                "has": ["Yes [Describe]"]},
    "Yes [Describe]": {"say": "Upper GI series, ultrasound and HIDA scan, endoscopy and a gastric emptying scan; "
                              "all normal."},
    "Additional information": {
        "say": "It's there every day for two years; how bad it is changes, but it never goes away. My weight hasn't "
               "changed. I really just want to know what this is and what can be done about it."},
    PREGNANCY: NOT_PREGNANT_ASSUMED,
    HISTORY_LIST: {"say": "I get the occasional migraine. I had my appendix out as a kid and my wisdom teeth out "
                          "when I was a teenager.", "has": ["Operation", "Other [Describe]"]},
    "What was the operation?": {"say": "Appendix out as a kid, and wisdom teeth out as a teenager.",
                                "has": ["Abdomen (Stomach/Liver/Bile/Kidney/Colon)", "Head (Eyes/Ears/Nose/Mouth)"]},
    "When did it occur?": {"say": "Appendix as a kid, wisdom teeth as a teenager."},
    "Other [Describe]": {"say": "Occasional migraines."},
    SMOKING: {"say": "I don't smoke.", "has": ["Never-smoker"]},
    ALCOHOL: {"say": "I hardly ever drink.", "has": ["Yes"]},
    "Since": UNSURE,
    "How often do you take alcohol?": {"say": "Hardly ever."},
    "No. of drinks consumed in one go": UNSURE,
    FAMILY: {"say": "Nothing runs in the family that I know of.", "has": ["None"]},
    HOW_LONG: {"say": "About two years."},
})
sheets["TC07"] = {"questions": q, "denies": ["Weight change (kg)"],
                  "assumed": [MEDICINES, ALLERGIES, PREGNANCY]}
add_facts("TC07", [
    (2, "Chief complaint / Duration", "Upper stomach discomfort for 2 years.", "", True, "Yes", "Since when; Site", False, Y),
    (3, "Symptom pattern", "Present every day; varies in how bad it is but never goes away.", "", True, "Partly",
     "Describe the pain / progression; Additional information", False, Y),
    (4, "Aggravating factor", "Eating makes it worse.", "", True, "Yes", "When does the pain increase?: Postprandial", False, Y),
    (5, "Meal-related symptom", "Feels very full even after a modest (normal-sized) meal.", "", True, "Partly", "Symptoms: Other [describe]", False, Y),
    (6, "Weight change", "No weight change.", "", True, "Yes", "Symptoms: Weight change (said no)", False, Y),
    (7, "Past medical history", "Occasional migraine headaches.", "", True, "Yes", "Past history: Other [Describe]", False, Y),
    (8, "Surgical history", "Appendix removed as a child; wisdom teeth removed as a teenager.", "", True, "Yes",
     "Past history: Operation", False, YE),
    (9, "Tobacco use", "Does not use tobacco.", "", True, "Yes", "Smoking history; Do you chew tobacco?", False, Y),
    (10, "Alcohol use", "Rarely drinks alcohol.", "", True, "Yes", "Alcohol use", False, Y),
    (11, "Family history", "Nothing relevant runs in the family.", "", True, "Yes", "Family history", False, Y),
    (12, "Previous investigations", "Several earlier tests (upper GI series, ultrasound and HIDA scan, endoscopy, gastric "
     "emptying scan) were reported normal.", "", True, "Partly", "Treatment / provider seen: Yes [Describe]", False,
     "Yuqi F12-F15 merged into one fact: the patient blurs the tests and their timing (Claude)"),
    (13, "Previous investigations", "(merged into F12)", "", False, "Partly", "", False, "merged into F12"),
    (14, "Previous investigations", "(merged into F12)", "", False, "Partly", "", False, "merged into F12"),
    (15, "Previous investigations", "(merged into F12)", "", False, "Partly", "", False, "merged into F12"),
    (18, "Patient concerns / Goals", "Wants to know what this is and what can be done.", "", True, "Partly",
     "Additional information", False, Y),
])

# =====================================================================================================
# TC09: 23-year-old woman, burning urination for 2 days (lower urinary tract infection). Complaint: Urine disturbance
# =====================================================================================================
add_case("TC09", "Renal6", "Urinary tract infection", 23, "female", "Urine disturbance", [])
q = assumed_history()
q.update({
    "Describe the urinary disturbance you are experiencing": {
        "say": "It burns when I pee; it comes and goes. I'm going more often and I feel like I have to go urgently. "
               "Once I saw blood in my urine, and now my urine looks dark.",
        "has": ["Dysuria", "Increase in Frequency/urgency", "Urine color change"]},
    "Increase in Frequency/urgency": {"say": "I go more often, and I feel I have to go right away.",
                                      "has": ["Urgency (difficult to postpone urination)",
                                              "Daytime frequency (need to urinate again within 2 hours after urination)"]},
    "Urine color change": {"say": "Once I saw blood in it. Now it looks dark, I think from the Pyridium I took.",
                           "has": ["Red-brown", "Other (Describe)"]},
    "Red-brown": {"say": "I saw blood just once."},
    "Eyes:Jaundice;": UNSURE,
    "Nighttime frequency an average (times/night)": UNSURE,
    "Other (Describe)": {"say": "Dark urine now, after the leftover Pyridium."},
    SINCE_WHEN: {"say": "The past two days.", "accept": ["2 day", "two day", "couple"]},
    "How did the symptom start?": UNSURE,
    "How has the symptom progressed?": {"say": "The burning comes and goes."},
    SYMPTOMS: {"say": "No fever, and my back doesn't hurt.", "not": ["Fever"]},
    "Any change in fluid intake?": UNSURE,
    "Have you ever been diagnosed with any of the following specific diseases?": {
        "say": "I've had two urinary infections in the past year; the last one was a few months ago. Both cleared up "
               "with antibiotics. I've never had a kidney infection.",
        "has": ["Prior urinary tract infection (times)"]},
    "Prior urinary tract infection (times)": {"say": "Two, in the past year.", "accept": ["2", "two"]},
    TREATMENT: {"say": "I tried cranberry juice and some Pyridium 200 mg left over from my last urinary infection.",
                "has": ["Yes [Describe]"]},
    "Yes [Describe]": {"say": "Cranberry juice and leftover Pyridium 200 mg."},
    "Additional information": {
        "say": "My last urinary infection was a few months ago, and both cleared with antibiotics I was given; never a "
               "kidney infection. I've been sexually active since 18, I'm on the pill and haven't missed any, I have one "
               "partner and we're monogamous, and I've never had an STI. My last period was three weeks ago, right on "
               "time. I don't have any children."},
    PREGNANCY: {"say": "I don't think so. I'm on the pill and haven't missed any, and my last period was three weeks ago.",
                "has": ["No"]},
    HISTORY_LIST: {"say": "Just the two urinary infections. Never a kidney infection.", "has": ["None"]},
    MEDICINES: {"say": "I'm on the birth control pill, and I took some leftover Pyridium.", "has": ["Yes"]},
    "Name of Medications": {"say": "The birth control pill and Pyridium.", "has": ["Medication name 1", "Medication name 2"]},
    "Medication Name": {"say": "Birth control pill; Pyridium 200 mg."},
    "From": UNSURE, "To": UNSURE,
    "How often do you have trouble taking medicines the way you have been told to take them?": {
        "say": "I haven't missed any pills.", "has": ["I always take them as prescribed"]},
    HOW_LONG: {"say": "Two days."},
})
sheets["TC09"] = {"questions": q, "denies": ["Fever"],
                  "assumed": ASSUMED[1:] + [PREGNANCY, HISTORY_LIST]}
add_facts("TC09", [
    (2, "Obstetric history", "Has no children.", "", True, "Partly", "Additional information", False, Y),
    (3, "Urinary symptoms / Duration", "Burning when passing urine, on and off, for 2 days.", "", True, "Yes",
     "Urinary disturbance: Dysuria; Since when", False, YE),
    (4, "Urinary symptoms", "Urgency and increased frequency.", "", True, "Yes", "Frequency/urgency", False, Y),
    (5, "Urinary symptoms", "Saw blood in the urine once.", "", True, "Yes", "Urine color change: Red-brown", True, Y),
    (6, "Pertinent negatives", "No fever and no back pain.", "", True, "Partly", "Symptoms: Fever (said no); back pain only in words", False, Y),
    (7, "Self-treatment", "Tried cranberry juice and Pyridium 200 mg.", "", True, "Yes", "Treatment: Yes [Describe]", False, Y),
    (8, "Medication source", "The Pyridium was left over from a previous urinary infection.", "", True, "Yes",
     "Treatment: Yes [Describe]", False, Y),
    (9, "Urine appearance", "Urine now looks dark (after taking Pyridium).", "", True, "Yes", "Urine color change: Other", False, YE),
    (10, "Previous episodes", "Two urinary infections in the past year.", "", True, "Yes", "Diagnosed: Prior urinary tract infection (times)", False, Y),
    (11, "Previous treatment / Response", "Both earlier infections cleared with antibiotics.", "", True, "Partly",
     "Additional information", False, YE),
    (12, "Previous episode timing", "The last infection was a few months ago.", "", True, "Partly", "Additional information", False, YE),
    (13, "Past medical history", "Never had a kidney infection.", "", True, "Partly", "Additional information", False, Y),
    (14, "Sexual history", "Sexually active since age 18.", "", True, "No", "Not asked (Additional information only)", False, Y),
    (15, "Contraception / Adherence", "On the pill; no missed pills.", "", True, "Yes", "Medicines; adherence question", False, Y),
    (16, "Sexual history", "In a monogamous relationship.", "", True, "No", "Not asked (Additional information only)", False, Y),
    (17, "Sexual history", "Believes her partner is monogamous.", "", True, "No", "Not asked (Additional information only)", False, Y),
    (18, "Sexual history", "One lifetime sexual partner.", "", True, "No", "Not asked (Additional information only)", False, Y),
    (19, "STI history", "No history of sexually transmitted infection.", "", True, "No", "Not asked (Additional information only)", False, Y),
    (20, "Menstrual history", "Last period 3 weeks ago, on time.", "", True, "Partly", "Pregnancy status / Additional information", False, YE),
])

# =====================================================================================================
# TC14: 77-year-old woman, collapse then right-sided weakness (stroke); her daughter gives the history.
# Complaint: Muscle weakness or Paralysis
# =====================================================================================================
add_case("TC14", "Neuro1", "Stroke", 77, "female", "Muscle weakness or Paralysis",
         [("Acute focal neurologic complaint", "Urgent"), ("Recent fainting", "Urgent")],
         notes="Her daughter gives the history; the patient can communicate in writing.")
q = assumed_history()
q.update({
    SINCE_WHEN: {"say": "Since she collapsed. She slowly woke up over the next two days.", "accept": ["day", "collapse"]},
    "Which part of the body do you feel weakness/paralysis?": {
        "say": "She can't move the right side of her face or her right arm.",
        "has": ["One limb/part of one limb", "One side of the face"]},
    "One limb/part of one limb": {"say": "Her right arm.", "has": ["Right arm"]},
    "One side of the face": {"say": "The right side.", "has": ["Right"]},
    "How did the symptom start?": {"say": "She was cooking in the kitchen and collapsed onto the floor."},
    "How has the symptom progressed?": UNSURE,
    SYMPTOMS: {"say": "She can't feel it when the right side of her face or her right arm is touched. She understands "
                      "what we say but can't answer out loud; writing is easier for her. She collapsed and was "
                      "unconscious, and slowly came round over two days.",
               "has": ["Paresthesia", "Aphasia", "Other [describe]"]},
    "Describe the abnormal sensation": {"say": "Since she woke up, she can't feel touch there.", "has": ["Sensory loss"]},
    "Does the sensation stay the same or is it gradually increasing?": UNSURE,
    "Affected areas (Describe)": {"say": "The right side of her face and her right arm."},
    "Other [describe]": {"say": "She collapsed while cooking and slowly regained consciousness over two days."},
    "Eating habits": UNSURE,
    TREATMENT: {"say": "I called an ambulance when she collapsed.", "has": ["Yes [Describe]"]},
    "Yes [Describe]": {"say": "An ambulance came when she collapsed."},
    "Additional information": {
        "say": "She was cooking in the kitchen when she collapsed onto the floor, and I called an ambulance. She slowly "
               "regained consciousness over the next two days. She understands what we say but can't answer out loud; "
               "it's easier for her to write down what she wants to say."},
    HISTORY_LIST: UNSURE,
    HOW_LONG: {"say": "Since she collapsed; she came round over two days."},
})
sheets["TC14"] = {"questions": q, "denies": [], "assumed": ASSUMED}
add_facts("TC14", [
    (1, "Onset / circumstances", "Collapsed onto the kitchen floor while cooking.", "", True, "Yes", "How did it start; Additional information", False, YE),
    (2, "Consciousness / time course", "Slowly regained consciousness over two days.", "", True, "Partly",
     "Symptoms: Other [describe]; Additional information", True, Y),
    (3, "Motor symptoms", "After regaining consciousness, could not move the right side of her face or her right arm.", "", True, "Yes",
     "Weakness site: Right arm; One side of the face: Right", True, Y),
    (4, "Sensory symptoms", "After regaining consciousness, could not feel touch on the right side of her face or her right arm.", "", True, "Yes",
     "Paresthesia: Sensory loss; Affected areas", False, Y),
    (5, "Speech / comprehension", "Understands what is said but cannot answer out loud.", "", True, "Yes", "Symptoms: Aphasia", True, Y),
    (6, "Written communication", "Could express her thoughts more easily in writing than by speaking.", "", True, "Partly", "Additional information", False, Y),
])

# =====================================================================================================
# TC19: 19-year-old woman, fever, headache and spreading rash (meningitis). Complaint: Fever & Rash
# =====================================================================================================
add_case("TC19", "Infect1", "Meningitis", 19, "female", "Fever & Rash",
         [("Possible meningitis (stiff neck or confusion, with fever or headache)", "Emergent"),
          ("Headache with fever (meningitis signs checked)", "Urgent"), ("Rash spreading within hours", "Urgent")],
         notes="Source: she became agitated and combative on the way to hospital (observer account, not at the visit).")
q = assumed_history()
q.update({
    "Which part of the body has the rash?": {
        "say": "First on my body. Then tiny spots on my arms and legs, and within a few hours they spread to my body too.",
        "has": ["All over"]},
    "Since when have you had rash?": {"say": "It started with the fever; I'm not sure exactly how many days."},
    "Rate of rash spread": {"say": "The tiny spots spread from my arms and legs to my body within a few hours.",
                            "has": ["within hours"]},
    "How has the rash spread?": {"say": "From my arms and legs to my body.", "has": ["Centripetal"]},
    "Since when have you had fever?": {"say": "I'm not sure exactly. It started three days after I came home from college for spring break."},
    "How does fever change?": UNSURE,
    "Severity of Fever": UNSURE,
    "In a day, when do you feel fever the most?": UNSURE,
    SYMPTOMS: {"say": "I have a headache, I felt sick to my stomach and threw up, and the light really bothers me.",
               "has": ["Headache", "Nausea", "Vomiting", "Other [describe]"]},
    "Other [describe]": {"say": "Light really bothers my eyes."},
    "Any contact with persons with fever & rash in the past month?": UNSURE,
    "Any recent exposure to an animal in the past month?": UNSURE,
    "Any recent animal/insect/tick bites in the past month?": {"say": "Not that I know of. No ticks.", "has": ["No"]},
    "Have you recently eaten any contaminated food or water?": UNSURE,
    "Have you ever been diagnosed with HIV/AIDS?": UNSURE,
    "Have you recently taken any medication?": UNSURE,
    TREATMENT: UNSURE,
    "Additional information": {
        "say": "It started three days after I came home from college for spring break: fever, headache and a rash on my "
               "body. Then I felt sick, threw up, and the light bothered me. Then tiny spots came on my arms and legs and "
               "spread to my body within a few hours. No known medicine allergies, and no contact with ticks that I know of."},
    PREGNANCY: NOT_PREGNANT_ASSUMED,
    ALLERGIES: {"say": "No known medicine allergies.", "has": ["No known allergies"]},
    HISTORY_LIST: UNSURE,
    HOW_LONG: {"say": "It started three days after I came home from college for spring break; I can't say exactly."},
})
sheets["TC19"] = {"questions": q, "denies": [], "assumed": [MEDICINES, TOBACCO, SMOKING, ALCOHOL, FAMILY, PREGNANCY]}
add_facts("TC19", [
    (1, "Initial symptoms / rash location", "First had fever, headache and a rash on the body (trunk).", "", True, "Yes",
     "Symptoms: Headache; rash site", True, Y),
    (2, "Onset relative to travel", "Started three days after coming home from college for spring break.", "", True, "Partly", "Additional information", False, Y),
    (3, "Subsequent symptoms", "Then nausea, vomiting and sensitivity to light.", "", True, "Yes", "Symptoms: Nausea, Vomiting, Other", True, Y),
    (4, "Later rash / progression", "Later, tiny pinpoint spots spread from the arms and legs to the trunk within hours.", "", True, "Yes",
     "Rate of rash spread: within hours; How spread: Centripetal", True, Y),
    (5, "Allergy / exposure history", "No known medicine allergy and no known tick contact.", "", True, "Yes",
     "Allergies; tick bites: No", False, Y),
])

# =====================================================================================================
# TC20: 67-year-old man, denture discomfort and upper right tooth pain (diabetes, dry mouth). Complaint: Oral Pain
# =====================================================================================================
add_case("TC20", "Dental1", "Dry mouth associated with diabetes", 67, "male", "Oral Pain", [])
q = assumed_history()
q.update({
    SINCE_WHEN: UNSURE,
    "How did the symptom start?": UNSURE,
    "Do the following situations make the symptom worse?": UNSURE,
    SYMPTOMS: {"say": "The teeth on the top right hurt, my mouth feels dry, and I see a little blood when I "
                      "brush.", "has": ["Toothache", "Gum bleeding", "Other [describe]"]},
    "[Describe]": {"say": "The top right teeth hurt, and my upper partial denture bothers me."},
    "Other [describe]": {"say": "Dry mouth, and my upper partial denture bothers me."},
    TREATMENT: {"say": "No. I haven't seen a dentist in three years.", "has": ["None"]},
    "Additional information": {
        "say": "My upper partial denture bothers me. I haven't seen a dentist in three years. I was diagnosed with type 2 "
               "diabetes eight years ago. My feet feel strange when I walk, almost like I'm walking on clouds. I also "
               "broke my wrist recently without much of an injury; the bone doctor recommended a bone density test, but "
               "I haven't had it yet."},
    HISTORY_LIST: {"say": "I have type 2 diabetes, for eight years. I also broke my wrist recently without much of an "
                          "injury.", "has": ["Diabetes", "Other [Describe]"]},
    "When were you diagnosed?": {"say": "Eight years ago."},
    "Current medication": UNSURE,
    "Last measured Blood Sugar and HbA1C": {"say": "I don't know.", "has": ["Not known"]},
    "Other [Describe]": {"say": "Broke my wrist recently without much of an injury; bone density test recommended."},
    HOW_LONG: UNSURE,
})
sheets["TC20"] = {"questions": q, "denies": [], "assumed": ASSUMED}
add_facts("TC20", [
    (1, "Dental complaint / location", "Upper partial denture discomfort and pain in the upper right teeth.", "", True, "Yes",
     "Symptoms: Toothache [Describe]", False, Y),
    (2, "Bleeding / trigger", "Some bleeding when brushing.", "", True, "Yes", "Symptoms: Gum bleeding", False, Y),
    (3, "Oral symptom", "Dry mouth.", "", True, "Partly", "Symptoms: Other [describe]", False, Y),
    (4, "Dental care history", "Has not seen a dentist in three years.", "", True, "Partly", "Treatment / Additional information", False, Y),
    (5, "Medical history / diagnosis timing", "Type 2 diabetes diagnosed eight years ago.", "", True, "Yes", "Past history: Diabetes", False, Y),
    (6, "Sensory symptoms", "Feet feel strange when walking, 'like walking on clouds'.", "", True, "Partly", "Additional information", False, Y),
    (7, "Bone health", "Recently broke his wrist with little injury; bone density test recommended, not yet done.", "",
     True, "Partly", "Past history: Other [Describe]", False, C),
])

# =====================================================================================================
# TC21: 44-year-old man, severe chest pain at night with sweating (myocardial infarction).
# Complaint: Chest Discomfort or Pain
# =====================================================================================================
add_case("TC21", "Cardio2", "Myocardial infarction", 44, "male", "Chest Discomfort or Pain",
         [("Chest pain", "Refer"), ("Severe pain", "Urgent")])
q = assumed_history()
q.update({
    "Which part of the chest do you feel pain?": {"say": "Right behind my breastbone.",
                                                  "has": ["Retrosternal - Center of the chest"]},
    SINCE_WHEN: {"say": "Since about half past midnight.", "accept": ["hour", "night", "midnight", "12"]},
    "How did the symptom start?": {"say": "It started while I was asleep."},
    "How does the pain feel?": {"say": "It's really intense pain."},
    "How long does the pain continue?": {"say": "It lasted a long time.", "has": ["Prolonged"]},
    "In a day, when do you feel pain the most?": {"say": "It started at night, around half past midnight, while I was asleep.",
                                                  "has": ["At night"]},
    "Severity": {"say": "It's really bad.", "has": ["Severe, 7-9"]},
    "Does this pain go to other part(s) of the body?": {"say": "No, it stayed in my chest.", "has": ["Does not move"]},
    SYMPTOMS: {"say": "I broke out in a heavy cold sweat with the pain.", "has": ["Sweating"]},
    "Does the symptom get worse with the following situation(s)?": UNSURE,
    "Does the symptom get better with the following situation(s)?": UNSURE,
    TREATMENT: UNSURE,
    "Additional information": {
        "say": "Around half past midnight, while I was asleep, I got really intense pain right behind my breastbone. It "
               "lasted a long time and stayed in my chest. I broke out in a heavy cold sweat with it. I have high blood "
               "pressure, and I've been told my cholesterol and blood fat levels are abnormal."},
    HISTORY_LIST: {"say": "I have high blood pressure, and I've been told my cholesterol and blood fats are abnormal.",
                   "has": ["High Blood Pressure", "Other [Describe]"]},
    "Diagnosed on": UNSURE,
    "Current medication": UNSURE,
    "Other [Describe]": {"say": "Abnormal cholesterol and blood fat levels."},
    HOW_LONG: {"say": "Since about half past midnight."},
})
sheets["TC21"] = {"questions": q, "denies": [], "assumed": ASSUMED}
add_facts("TC21", [
    (1, "Pain location", "Pain right behind the breastbone.", "", True, "Yes", "Site: Retrosternal", True, Y),
    (2, "Pain radiation", "The pain did not spread anywhere else.", "", True, "Yes", "Radiation: Does not move", False, Y),
    (3, "Onset / circumstances", "Pain began around 12:30 a.m. while he was asleep.", "", True, "Partly",
     "When most: At night; Since when", True, Y),
    (4, "Associated symptom", "Heavy cold sweat with the pain.", "", True, "Yes", "Symptoms: Sweating", True, Y),
    (5, "Medical history", "High blood pressure and abnormal blood lipids (cholesterol).", "", True, "Yes",
     "Past history: High Blood Pressure; Other [Describe]", False, Y),
    (6, "Pain severity / duration", "Intense chest pain that lasted a long time (exact duration not given).", "", True, "Yes", "Severity; How long: Prolonged", True, C),
])

# =====================================================================================================
# TC27: 44-year-old man, swelling under the chin after a tooth extraction (Ludwig's angina). Complaint: Oral Pain
# =====================================================================================================
add_case("TC27", "Infect2", "Ludwig's angina", 44, "male", "Oral Pain",
         [("Neck swelling with breathing or swallowing trouble", "Urgent"),
          ("Breathing difficulty (distress signs checked)", "Refer"),
          ("Possible dental abscess (toothache with facial swelling or pus)", "Refer")])
q = assumed_history()
q.update({
    SINCE_WHEN: {"say": "It started five days after my right wisdom tooth was pulled. I'm not sure how many days ago."},
    "How did the symptom start?": UNSURE,
    "Do the following situations make the symptom worse?": {"say": "It's hard to swallow, and lying back makes the "
                                                                   "breathing harder."},
    SYMPTOMS: {"say": "The area under my chin is swelling and keeps getting bigger. It hurts, I have trouble opening my "
                      "mouth and swallowing, I've had fever and chills, and it's hard to breathe, especially "
                      "when I lie back.",
               "has": ["Facial swelling", "Fever", "Limited mandibular movement", "Other [describe]"]},
    "Other [describe]": {"say": "Trouble swallowing, chills, and it's hard to breathe, especially lying back."},
    TREATMENT: {"say": "I had my right wisdom tooth pulled; this started five days later.", "has": ["Yes [Describe]"]},
    "Yes [Describe]": {"say": "Right wisdom tooth pulled; the swelling started five days later."},
    "Additional information": {
        "say": "I had my right wisdom tooth pulled, and five days later the area under my chin started swelling. It keeps "
               "getting bigger and it hurts. I can't open my mouth well and it's hard to swallow. I've had fever and "
               "chills, and it's hard to breathe, especially when I lie back. No known allergies to medicines."},
    HISTORY_LIST: {"say": "I had my right wisdom tooth pulled recently.", "has": ["Operation"]},
    "What was the operation?": {"say": "My right wisdom tooth was pulled.", "has": ["Head (Eyes/Ears/Nose/Mouth)"]},
    "When did it occur?": {"say": "Five days before the swelling started."},
    ALLERGIES: {"say": "No known allergies to medicines.", "has": ["No known allergies"]},
    HOW_LONG: {"say": "It started five days after the tooth was pulled. I can't say exactly."},
})
sheets["TC27"] = {"questions": q, "denies": [], "assumed": [MEDICINES, TOBACCO, SMOKING, ALCOHOL, FAMILY]}
add_facts("TC27", [
    (1, "Dental procedure / timing", "Started five days after his right wisdom tooth was pulled.", "", True, "Yes",
     "Treatment / Operation; Since when", False, Y),
    (2, "Swelling / progression", "Swelling under the chin that keeps getting bigger.", "", True, "Yes", "Symptoms: Facial swelling", True, Y),
    (3, "Pain / mouth opening / swallowing", "Pain, trouble opening the mouth and trouble swallowing.", "", True, "Yes",
     "Symptoms: Limited mandibular movement; Other", True, Y),
    (4, "Associated symptoms", "Fever and chills.", "", True, "Yes", "Symptoms: Fever; Other", False, Y),
    (5, "Breathing difficulty / position", "Difficulty breathing, especially when lying back.", "", True, "Partly",
     "Symptoms: Other [describe]", True, Y),
    (6, "Drug allergy history", "No known medicine allergies.", "", True, "Yes", "Allergies", False, Y),
])

# =====================================================================================================
# TC28: 57-year-old woman, worsening constipation with IBS (chronic constipation). Complaint: Constipation
# =====================================================================================================
add_case("TC28", "GI2", "Chronic constipation", 57, "female", "Constipation", [])
q = assumed_history()
q.update({
    SINCE_WHEN: {"say": "About nine months, since a trip to Asia. I've had IBS with constipation for 20 years.",
                 "accept": ["9 month", "nine month"]},
    "How many times each week do you have satisfactory bowel movements/pass stool?": {
        "say": "I go two or three times a day, but I never feel like I've emptied completely."},
    "How much time does it take to pass stool?": UNSURE,
    "What is the consistency of the stool?": UNSURE,
    "Has the shape of the stool changed?": UNSURE,
    SYMPTOMS: {"say": "I have to push really hard, and I never feel like I've emptied my bowels completely. There's no "
                      "blood, and it doesn't hurt when I go. Fiber made my belly feel bloated.",
               "has": ["Tenesmus", "Other [describe]"],
               "not": ["Blood in stool", "Rectal bleeding", "Pain around the anus while passing stool"]},
    "Enter frequency of this symptom": {"say": "Every time, two or three times a day."},
    "Other [describe]": {"say": "I have to push really hard, and fiber made my belly uncomfortably bloated."},
    "Have you taken any medication or had any addiction?": {
        "say": "Lexapro 20 mg a day, and milk of magnesia now and then.", "has": ["Yes [Describe]"]},
    "Any recent change in diet?": {"say": "I tried adding fiber, but it made my belly bloated.", "has": ["Yes [Describe]"]},
    "Yes [Describe]": {"say": "Lexapro 20 mg a day and occasional milk of magnesia; I also tried adding fiber, which made me bloated."},
    TREATMENT: {"say": "It used to be well controlled with Lexapro 20 mg a day and milk of magnesia now and then. I tried fiber.",
                "has": ["Yes [Describe]"]},
    "Additional information": {
        "say": "I've had irritable bowel syndrome for 20 years, mostly constipation; it was well controlled with Lexapro "
               "20 mg a day and occasional milk of magnesia. Nine months ago on a trip to Asia I went several days "
               "without a bowel movement, then for several days had hard stools like little pebbles that were hard to pass. Now I go two or three times a "
               "day but have to push hard and never feel empty. No blood and no pain. Fiber made me bloated. I miss two "
               "or three days of work a month, and sometimes social plans."},
    HISTORY_LIST: {"say": "I've had irritable bowel syndrome for 20 years.", "has": ["Other [Describe]"]},
    "Other [Describe]": {"say": "Irritable bowel syndrome for 20 years, mostly constipation."},
    MEDICINES: {"say": "Yes, Lexapro 20 mg a day, and milk of magnesia now and then.", "has": ["Yes"]},
    "Name of Medications": {"say": "Lexapro and milk of magnesia.", "has": ["Medication name 1", "Medication name 2"]},
    "Medication Name": {"say": "Lexapro 20 mg a day; milk of magnesia now and then."},
    "From": UNSURE, "To": UNSURE,
    "How often do you have trouble taking medicines the way you have been told to take them?": UNSURE,
    HOW_LONG: {"say": "About nine months."},
})
sheets["TC28"] = {"questions": q, "denies": ["Blood in stool", "Rectal bleeding", "Pain around the anus while passing stool"],
                  "assumed": [ALLERGIES, TOBACCO, SMOKING, ALCOHOL, FAMILY]}
add_facts("TC28", [
    (1, "Gastrointestinal history / duration", "Irritable bowel syndrome with constipation for 20 years.", "", True, "Yes",
     "Past history: Other [Describe]", False, Y),
    (2, "Travel / stool changes", "After a trip to Asia nine months ago: several days without a bowel movement, then hard "
     "several days of hard, pebble-like stools that were difficult to pass.", "", True, "Partly", "Since when; Additional information", False, Y),
    (3, "Current bowel frequency / incomplete emptying", "Now passes stool two to three times a day but never feels empty.",
     "", True, "Yes", "Symptoms: Tenesmus", False, Y),
    (4, "Negative bowel symptoms", "No bleeding and no pain when passing stool.", "", True, "Yes",
     "Symptoms: Blood in stool, Rectal bleeding, Pain around the anus (said no)", False, Y),
    (5, "Straining", "Has to push very hard to pass stool.", "", True, "Partly", "Symptoms: Other [describe]", False, Y),
    (6, "Response to added fiber", "Added fiber caused uncomfortable bloating.", "", True, "Yes", "Recent change in diet: Yes [Describe]", False, Y),
    (7, "Functional impact", "Misses two to three workdays a month and sometimes social plans.", "", True, "Partly",
     "Additional information", False, Y),
    (8, "Medication", "Was previously well controlled with Lexapro 20 mg daily and occasional milk of magnesia.", "", True, "Yes",
     "Medication or addiction: Yes [Describe]; Medicines", False, C),
])

# =====================================================================================================
# TC30: 52-year-old man, sudden painful swollen right knee with fever (gout). Complaint: Leg, Knee or Hip Pain
# =====================================================================================================
add_case("TC30", "Renal2", "Gout", 52, "male", "Leg, Knee or Hip Pain", [("Severe pain", "Urgent")])
q = assumed_history()
q.update({
    "Which part of the leg or hip do you feel pain?": {"say": "My right knee.", "has": ["Right leg"]},
    "Right leg": {"say": "The knee.", "has": ["Knee"]},
    "Knee": {"say": "My right knee is swollen and warm.", "has": ["Swelling"]},
    "Swelling": {"say": "Yes, it's swollen.", "has": ["Yes"]},
    "Site of knee pain": UNSURE,
    SINCE_WHEN: {"say": "Since last night.", "accept": ["night", "1 day", "one day", "yesterday", "hour"]},
    "Pain characteristics": {"say": "It's terrible pain."},
    "How did the symptom start?": {"say": "Suddenly. I felt fine yesterday, and it woke me up last night.",
                                   "has": ["Sudden (minutes to hours)"]},
    "How has the symptom progressed?": UNSURE,
    "Does the pain move to other parts of the body?": UNSURE,
    SYMPTOMS: {"say": "It's swollen and warm, it woke me up at night, and I've felt feverish and sweaty.",
               "has": ["Fever", "Swelling in the painful area", "Night pain", "Other [describe]"]},
    "Other [describe]": {"say": "The knee feels warm, and I've been sweaty. I haven't checked my temperature."},
    "Is the pain in your leg made worse by the following(s)?": UNSURE,
    "Have you ever been diagnosed with any of following specific diseases?": {
        "say": "I have high blood pressure. Several years ago I had really bad pain in my left big toe that got better "
               "with aspirin.", "has": ["Hypertension", "Other (Describe)"]},
    "Other (Describe)": {"say": "Years ago, very bad pain in my left big toe that got better with aspirin."},
    "Recently have you had a trauma or surgery?": {"say": "No, I didn't injure it.", "has": ["No"]},
    "Have you ever taken any kind of injection drug?": {"say": "No.", "has": ["No"]},
    TREATMENT: UNSURE,
    "Additional information": {
        "say": "I felt fine yesterday and went to a crab feast in the afternoon. Last night I woke up with terrible pain in "
               "my right knee; it's swollen and warm and I didn't injure it. I've felt feverish and sweaty but haven't "
               "checked my temperature. No other joints hurt right now. Several years ago my left big toe was very "
               "painful and got better with aspirin. I have high blood pressure and take hydrochlorothiazide 25 mg."},
    HISTORY_LIST: {"say": "I have high blood pressure.", "has": ["High Blood Pressure"]},
    "Diagnosed on": UNSURE,
    "Current medication": {"say": "Hydrochlorothiazide 25 mg.", "has": ["[Describe]"]},
    "[Describe]": {"say": "Hydrochlorothiazide 25 mg."},
    MEDICINES: {"say": "Yes, hydrochlorothiazide 25 mg for my blood pressure.", "has": ["Yes"]},
    "Name of Medications": {"say": "Hydrochlorothiazide.", "has": ["Medication name 1"]},
    "Medication Name": {"say": "Hydrochlorothiazide 25 mg."},
    "From": UNSURE, "To": UNSURE,
    "How often do you have trouble taking medicines the way you have been told to take them?": UNSURE,
    HOW_LONG: {"say": "Since last night."},
})
sheets["TC30"] = {"questions": q, "denies": [],
                  "assumed": [ALLERGIES, TOBACCO, SMOKING, ALCOHOL, FAMILY,
                              "Have you ever taken any kind of injection drug?"]}
add_facts("TC30", [
    (1, "Joint pain / onset", "Severe right knee pain woke him from sleep last night.", "", True, "Yes",
     "Site: Right leg - Knee; Since when; Night pain", True, Y),
    (2, "Joint swelling / warmth", "The right knee is swollen and warm.", "", True, "Yes",
     "Knee: Swelling Yes; Symptoms: Swelling in the painful area; Other", True, Y),
    (3, "Preceding event", "Went to a crab feast the afternoon before.", "", True, "Partly", "Additional information", False, Y),
    (4, "Injury history", "No injury to the knee.", "", True, "Yes", "Trauma or surgery: No", False, Y),
    (5, "Subjective fever / sweating", "Feels feverish and sweaty; temperature not measured.", "", True, "Yes",
     "Symptoms: Fever; Other", True, Y),
    (6, "Current joint involvement", "No other joints hurt right now.", "", True, "Partly", "Additional information", False, Y),
    (7, "Prior joint episode / treatment response", "Years ago, very bad left big-toe pain that improved with aspirin.", "",
     True, "Yes", "Diagnosed diseases: Other (Describe)", False, Y),
    (8, "Medical history / medication", "High blood pressure; takes hydrochlorothiazide 25 mg.", "", True, "Yes",
     "Past history: High Blood Pressure, Current medication", False, C),
    (9, "Examination", "Temperature 39 C at the visit (exam finding, not from the patient).", "", False, "No", "", False,
     "Added from Yuqi's note (Nov 26)"),
])

# What was done with each of Yuqi's Nov 26 notes: fact ID -> (new Patient Answer or "", response).
# Where her own patient description blurs a detail on purpose (its notes say so: "a few months", test dates, ages, the
# antibiotic), the patient still blurs it, so the fact stays at the patient's level and the exact detail stays in
# Source Text. Otherwise the fact and the patient's words were both made exact.
KEPT_BLUR = "Kept at the patient's level: your patient description blurs this on purpose (see its note), so the app can't record the exact detail. The exact detail stays in Source Text."
RESPONSES = {
    "TC06-F02": ("", KEPT_BLUR),
    "TC06-F06": ("", KEPT_BLUR),
    "TC06-F10": ("", "No change needed: the fact already says since the illness began."),
    "TC06-F15": ("", KEPT_BLUR),
    "TC07-F02": ("", "Done (Nov 26): fact says 2 years."),
    "TC07-F05": ("I feel really full even after a normal-sized meal, nothing big.", "Done (Nov 26): fact and patient answer say a normal-sized (modest) meal."),
    "TC07-F08": ("", KEPT_BLUR),
    "TC07-F09": ("I don't smoke. / No, I don't chew tobacco.", "Done (Nov 26): fact says no tobacco use; the chewing answer now counts as from the source."),
    "TC07-F12": ("", KEPT_BLUR),
    "TC09-F03": ("The past two days.", "Done (Nov 26): fact and patient answer say 2 days."),
    "TC09-F05": ("", "No change needed: the dark urine after Pyridium is its own fact (F09)."),
    "TC09-F11": ("", KEPT_BLUR),
    "TC09-F12": ("", KEPT_BLUR),
    "TC09-F20": ("My last period was three weeks ago, right on time.", "Done (Nov 26): fact and patient answer say 3 weeks."),
    "TC14-F01": ("She was cooking in the kitchen and collapsed onto the floor.", "Done (Nov 26): 'suddenly' and the 'Very sudden' answer removed; the app now decides from her words."),
    "TC14-F03": ("", "Done (Nov 26): fact says after regaining consciousness."),
    "TC14-F04": ("", "Done (Nov 26): fact and patient answer say after she woke up."),
    "TC14-F05": ("", "No change needed: the fact already needs both parts."),
    "TC14-F06": ("", "Done (Nov 26): fact wording matched."),
    "TC19-F02": ("I'm not sure exactly. It started three days after I came home from college for spring break.", "Done (Nov 26): fact and patient answer say spring break."),
    "TC19-F04": ("", "Done (Nov 26): fact says pinpoint spots spread from arms and legs to the trunk within hours."),
    "TC20-F02": ("I see a little blood when I brush.", "Done (Nov 26): 'sometimes' removed from the fact and the patient's words."),
    "TC20-F07": ("", "Kept: it is in your patient description for TC20. Please confirm it against Dental1 when you can."),
    "TC21-F03": ("It started at night, around half past midnight, while I was asleep.", "Done (Nov 26): fact and patient answer no longer say the pain woke him."),
    "TC21-F05": ("I have high blood pressure, and I've been told my cholesterol and blood fats are abnormal.", "Done (Nov 26): fact says abnormal blood lipids."),
    "TC21-F06": ("It's really intense pain. / It lasted a long time.", "Done (Nov 26): fact says intense, prolonged, duration not given."),
    "TC27-F01": ("", "No change needed: the patient already says she doesn't know how many days ago."),
    "TC27-F02": ("", "Checked: the red-flag fix (Morrison, Nov 24) counts 'under my chin' as neck swelling."),
    "TC27-F05": ("It's also hard to breathe, especially when I lie back.", "Done (Nov 26): 'getting' removed from the fact and the patient's words."),
    "TC28-F02": ("", "Done (Nov 26): fact and patient answer say several days of hard stools."),
    "TC28-F04": ("", "Done (Nov 26): Potential Red Flag changed to No."),
    "TC28-F08": ("It used to be well controlled with Lexapro 20 mg a day and milk of magnesia now and then.", "Done (Nov 26): fact and patient answer give Lexapro 20 mg daily."),
    "TC30-F05": ("", "Done (Nov 26): the 39 C temperature is added as an exam row (F09, not scored)."),
    "TC30-F06": ("No other joints hurt right now.", "Done (Nov 26): mapped to Additional information; the radiation question is now answered 'I'm not sure'."),
    "TC30-F08": ("I have high blood pressure and take hydrochlorothiazide 25 mg.", "Done (Nov 26): fact and patient answer give 25 mg."),
}
CASE_ORDER = ["TC06", "TC07", "TC09", "TC14", "TC19", "TC20", "TC21", "TC27", "TC28", "TC30"]

# ---------- red-flag checks (asked by the app's follow-up questions; CHW answers from the story) ----------
# As for TC01-TC05: a sign the case does not mention is answered "no". These cases have no exam text in Yuqi's
# drafts, so "no" here means "not described".
NOT_DEHYDRATED = {
    "Is the patient drinking poorly or unable to drink?": "no",
    "Are the eyes sunken?": "no",
    "Pinch the skin of the belly and let go: does it go back very slowly (2 seconds or more)?": "no",
    "Is the patient unusually sleepy, floppy or hard to wake?": "no",
}
NO_DISTRESS = {
    "Is the patient too breathless to say a full sentence (or, for a baby, to feed)?": "no",
    "Is the patient breathing very fast, or using neck, chest or belly muscles to breathe? (Child: chest pulling in, nostrils flaring, grunting)": "no",
    "Are the lips or tongue blue or grey?": "no",
}
for case_id in sheets:
    sheets[case_id]["checks"] = dict(NOT_DEHYDRATED)
    sheets[case_id]["checks"].update(NO_DISTRESS)
sheets["TC14"]["checks"]["Has the patient fainted or nearly fainted with this?"] = "yes"
sheets["TC19"]["checks"].update({
    "Is the patient confused, very drowsy or hard to wake? (Ask the family too)": "no",
    "Has the patient had a seizure or fit with this illness?": "no",
})   # neck stiffness: not described in the draft, so left unanswered (the simulated CHW says 'unsure')

for case in cases:
    sheets[case["id"]]["opening"] = case["story"][0]

with open(os.path.join(HERE, "eval_cases_extra.json"), "w", encoding="utf-8") as f:
    json.dump({"about": "10 extra evaluation cases (Nov 23) from Yuqi's Nov 21 drafts of Dr. Verma's teaching cases. "
                        "Same format as eval_cases.json. Expected red flags labeled from the rule sources (Intelehealth "
                        "guidelines, WHO IITT). Never put Dr. Verma's 10 unseen cases in this public file.",
               "cases": cases}, f, indent=1, ensure_ascii=False)
with open(os.path.join(HERE, "eval_patient_answers_extra.json"), "w", encoding="utf-8") as f:
    json.dump(sheets, f, indent=2, ensure_ascii=False)
# Yuqi's check (Test Cases Organization.xlsx, Nov 26): her Source Text, Patient Answer, Review Status and Notes, plus
# the rows she added that are not scored (age, test results, exam). RESPONSES says what was done with each note.
review = json.load(open(os.path.join(HERE, "extra_case_yuqi_review.json"), encoding="utf-8"))["facts"]
by_id = {fact["Fact ID"]: fact for fact in facts}
for fact_id, row in review.items():
    if fact_id not in by_id:
        new = {"Case ID": fact_id.split("-")[0], "Fact ID": fact_id}
        new.update({key: row.get(key, "") for key in facts[0] if key not in new})
        facts.append(new)
        by_id[fact_id] = new
        continue
    fact = by_id[fact_id]
    fact["Source Text"] = row["Source Text"]
    if not fact["Patient Answer"]:
        fact["Patient Answer"] = row["Patient Answer"]
    fact["Review Status"] = row["Review Status"] + "; checked by Yuqi (Nov 26)"
    fact["Notes"] = row["Notes"]
for fact_id, (answer, response) in RESPONSES.items():
    fact = by_id[fact_id]
    if answer:
        fact["Patient Answer"] = answer
    fact["Notes"] = (fact["Notes"] + " " if fact["Notes"] else "") + "-> " + response
facts.sort(key=lambda fact: (CASE_ORDER.index(fact["Case ID"]), fact["Fact ID"]))
with open(os.path.join(HERE, "eval_key_facts_extra.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(facts[0].keys()))
    writer.writeheader()
    writer.writerows(facts)
scored = [x for x in facts if x["Include in History Score?"] == "Yes"]
print(len(cases), "cases,", len(scored), "scored key facts")
