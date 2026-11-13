"""Builds eval_patient_answers.json: the simulated patient's answers for TC01-TC05, written by Claude
(Nov 13) from the fixed case stories in eval_cases.json. Teammates: correct an answer here, then run
this file again.

Rules used:
- Symptoms: only what the story says. If it doesn't say, the patient answers "I'm not sure."
- Personal history the story leaves out (smoking, alcohol, allergies, medicines, family history):
  the plain "no", listed under "assumed" so a judge treats it as unsupported, not as an app error.
- "has" = the option labels that are true; "not" = labels the patient denies; "accept" = words a correct
  typed value contains (used when the app offers a value from the story).
"""
import json

UNSURE = {"say": "I'm not sure."}


def assumed_history(has_smoke="Never-smoker"):
    return {
        "Have you recently taken any kind of medicine (including ayurvedic/homeopathic/unani/herbal)?":
            {"say": "No, I'm not taking any medicines.", "has": ["No"]},
        "Do you have any allergies?": {"say": "No, no allergies.", "has": ["No known allergies"]},
        "Do you chew tobbaco?": {"say": "No, I don't chew tobacco.", "has": ["Do not Chew"]},
        "Smoking history": {"say": "I've never smoked.", "has": [has_smoke]},
        "Alcohol use": {"say": "No, I don't drink.", "has": ["No"]},
        "Do you have a family history of any of the following?":
            {"say": "No, nothing runs in my family that I know of.", "has": ["None"]},
    }


ASSUMED_KEYS = list(assumed_history().keys())

sheets = {}

# ---------- TC01: 25-year-old woman, abdominal pain (appendicitis) ----------
q = assumed_history()
q.update({
    "Which part of the abdomen do you feel pain?": {
        "say": "It started around my belly button, kind of up in the middle, and then it moved down to the lower right side.",
        "has": ["Middle (C) - Umbilical", "Upper (C) - Epigastric", "Lower (R) - Right Iliac Fossa"]},
    "Does the pain move to other parts of the body?": {
        "say": "It moved from around my belly button down to the lower right side. It doesn't spread anywhere else.",
        "has": ["Does not move"]},
    "Since when have you had this symptom?": {
        "say": "Less than two days.", "accept": ["2 day", "two day", "48", "1 day", "one day", "yesterday", "less than"]},
    "How did the pain start?": UNSURE,
    "What time of the day do you feel the pain?": UNSURE,
    "Character of the pain": {"say": "I can't really describe it. It just keeps getting worse.", "has": ["Other [describe]"]},
    "Other [describe]": {"say": "It keeps getting worse over time."},
    "How severe is the pain?": {"say": "It's really starting to bother me now. I'm not sure what number."},
    "Do you have the following symptom(s)?": {
        "say": "I feel sick to my stomach and I've been throwing up, and I have no appetite at all. "
               "No diarrhea, no constipation, and no fever.",
        "has": ["Nausea", "Vomiting", "Anorexia", "Change in appetite"],
        "not": ["Diarrhea", "Constipation", "Fever"]},
    "Change in appetite": {"say": "I have no appetite at all.", "has": ["Decreased"]},
    "What worsens the pain?": {"say": "Moving around makes it worse.", "has": ["Movement"]},
    "What relieves/lessens the pain?": {
        "say": "I don't really know what helps. I just lie still with my knees drawn up so it doesn't get worse.",
        "has": ["Don't know/Unsure"]},
    "Menstrual history": UNSURE,
    "Have you taken any treatment (including self-medication or home remedies) or seen any health provider for this problem before coming here today?":
        {"say": "No, I haven't taken anything for it.", "has": ["None"]},
    "Additional information": {
        "say": "The pain started around my belly button and moved down to the lower right side, and it keeps getting worse. "
               "The vomiting always comes after the pain starts. When it hurts I lie still with my knees drawn up, "
               "because moving makes it worse."},
    "Pregnancy status": {"say": "No, I'm not pregnant. I'm not sexually active.", "has": ["No"]},
    "Do you have a history of any of the following?": {
        "say": "No, I don't have any other medical problems.", "has": ["None"]},
    "Do you have a family history of any of the following?": {
        "say": "Nothing runs in my family.", "has": ["None"]},
})
sheets["TC01"] = {"questions": q, "denies": ["Diarrhea", "Constipation", "Fever"],
                  "assumed": [k for k in ASSUMED_KEYS if k != "Do you have a family history of any of the following?"]
                  + ["Have you taken any treatment (including self-medication or home remedies) or seen any health provider for this problem before coming here today?"]}

# ---------- TC02: 41-year-old woman, abdominal pain (gallstones) ----------
q = assumed_history()
q.update({
    "Which part of the abdomen do you feel pain?": {"say": "In my upper right belly.", "has": ["Upper (R) - Right Hypochondrium"]},
    "Does the pain move to other parts of the body?": {"say": "Yes, it spread to my back and my chest.", "has": ["Pain radiates to"]},
    "Pain radiates to": {"say": "To my back and my chest.", "has": ["Chest"]},
    "Since when have you had this symptom?": {
        "say": "About six months. It comes in attacks; the last one was about two weeks ago.",
        "accept": ["6 month", "six month", "half a year"]},
    "How did the pain start?": {"say": "It started mild but quickly turned into a steady pain.", "has": ["Rapidly increasing"]},
    "What time of the day do you feel the pain?": UNSURE,
    "Character of the pain": {"say": "It's a steady, constant pain. Not crampy, not coming and going.",
                              "has": ["Constant"], "not": ["Colicky / Intermittent (comes & goes)", "Cramping"]},
    "How severe is the pain?": {"say": "Mild at first, then a steady pain. I'm not sure what number."},
    "Do you have the following symptom(s)?": {
        "say": "I threw up once. I might have had a bit of a fever, I'm not sure, but no shaking chills. "
               "No diarrhea or constipation, no black stools, and I haven't noticed any yellowing of my skin or eyes.",
        "has": ["Vomiting"], "not": ["Diarrhea", "Constipation", "Blood in stool", "Color change in stool [describe]"]},
    "What worsens the pain?": {"say": "Nothing really. It's not related to eating, and moving or changing position doesn't change it.",
                               "has": ["None"], "not": ["Food", "Movement"]},
    "What relieves/lessens the pain?": {"say": "It eased off by itself after about five hours.", "has": ["Other [describe]"]},
    "Other [describe]": {"say": "It eases off by itself after about five hours."},
    "Menstrual history": UNSURE,
    "Have you taken any treatment (including self-medication or home remedies) or seen any health provider for this problem before coming here today?":
        {"say": "No, I haven't taken anything for it.", "has": ["None"]},
    "Additional information": {
        "say": "It has happened three times in six months, the last time about two weeks ago, and each attack lasted about "
               "five hours before it eased off. Cabbage, okra and beets give me bloating and gas, but never pain. I've always "
               "avoided greasy, fried and spicy food. I've never had heartburn, reflux or burning in my upper belly. "
               "No weight loss and no change in my bowel habits."},
    "Pregnancy status": {"say": "No, I'm not pregnant.", "has": ["No"]},
    "Do you have a history of any of the following?": {"say": "No other illnesses that I know of.", "has": ["None"]},
})
sheets["TC02"] = {"questions": q,
                  "denies": ["Diarrhea", "Constipation", "Blood in stool", "Color change in stool [describe]"],
                  "assumed": ASSUMED_KEYS + ["Pregnancy status", "Do you have a history of any of the following?",
                                             "Have you taken any treatment (including self-medication or home remedies) or seen any health provider for this problem before coming here today?"]}

# ---------- TC03: 66-year-old man, cough (pneumonia) ----------
q = assumed_history()
q.update({
    "Since when have you had this symptom?": {"say": "About four days.", "has": ["Acute (0-2 weeks)"]},
    "Is there a specific time of occurence of cough?": {
        "say": "It's bad at night. I barely slept last night because I was coughing so much.", "has": ["Night"]},
    "What aggravates the cough?": UNSURE,
    "Is the cough dry or wet?": {"say": "It was dry at first, but now I'm coughing up rusty-colored phlegm.", "has": ["Wet"]},
    "What is the colour of the sputum?": {"say": "Rusty-colored.", "has": ["Brown"]},
    "Do you have the following symptom(s)?": {
        "say": "Last night I suddenly got chills and felt feverish and run-down. After a long coughing fit I got a sharp pain "
               "in the right side of my chest. I don't feel short of breath exactly. No nausea, vomiting or diarrhea.",
        "has": ["Fever", "Pain/Tightness of chest", "Other [describe]"],
        "not": ["Shortness of breath", "Recurrent diarrhoea"]},
    "Other [describe]": {"say": "Chills last night, and I feel generally unwell and run-down."},
    "Have you taken any medication recently?": {"say": "I haven't taken any antibiotics in the past three months."},
    "Do you smoke/have ever smoked?": {"say": "No, I don't smoke.", "has": ["No"]},
    "What is your occupation?": {"say": "I'd rather not say.", "has": ["Declined to answer"]},
    "Have you taken any treatment (including self-medication or home remedies) or seen any health provider for this problem before coming here today?":
        {"say": "No. At first I thought it was just a cold.", "has": ["No"]},
    "Additional information": {
        "say": "The cough started dry four days ago and now I cough up rusty phlegm. Last night I suddenly got chills, felt "
               "feverish and generally unwell. It's been getting worse, not better. I might be breathing a little faster than "
               "usual. After a long coughing fit I got a sharp pain on the right side of my chest; no pain on the left or in "
               "the middle. No swelling in my legs, and it doesn't get worse when I lie flat. No nausea, vomiting or diarrhea. "
               "No antibiotics in the past three months."},
    "Do you have a history of any of the following?": {
        "say": "I have high blood pressure and high cholesterol.", "has": ["High Blood Pressure", "Other [Describe]"]},
    "Diagnosed on": UNSURE,
    "Current medication": UNSURE,
    "Other [Describe]": {"say": "High cholesterol."},
    "Have you recently taken any kind of medicine (including ayurvedic/homeopathic/unani/herbal)?":
        {"say": "No antibiotics in the past three months. I'm not sure about anything else."},
})
sheets["TC03"] = {"questions": q, "denies": ["Shortness of breath", "Recurrent diarrhoea"],
                  "assumed": ASSUMED_KEYS + ["Do you smoke/have ever smoked?", "What is your occupation?",
                                             "Have you taken any treatment (including self-medication or home remedies) or seen any health provider for this problem before coming here today?"]}

# ---------- TC04: 50-year-old man, difficulty breathing (asthma) ----------
q = assumed_history()
q.update({
    "Have you ever been diagnosed with any of the following specific diseases?": {
        "say": "No heart problem that I know of. Nobody has told me a name for my breathing problem; I just use the inhalers.",
        "not": ["Heart disease"]},
    "Since when have you had this symptom?": {"say": "A few years.", "accept": ["year"]},
    "How did the symptom start?": {"say": "Slowly. At first it came and went, mostly in the winter.", "has": ["Gradual"]},
    "Gradual": {"say": "Over a few years.", "has": ["Over years"]},
    "Severity (Let patient describe the severity and then pick the best option)": {
        "say": "Any kind of activity makes my breathing worse."},
    "Do you smoke or have ever smoked?": {
        "say": "Yes, about 10 to 15 cigarettes a day for the past 10 years.", "has": ["Yes [Describe in your words]"]},
    "Yes [Describe in your words]": {"say": "10 to 15 cigarettes a day for 10 years."},
    "Do you have the following symptom(s)?": {
        "say": "I have a cough, wheezing and chest tightness. Sometimes a runny nose and sneezing around dust. "
               "No fever and no weight loss.",
        "has": ["Cough", "Wheezing", "Chest pain/discomfort", "Other [describe]"],
        "not": ["Fever", "Weight change (kg)"]},
    "Cough": {"say": "Usually dry, sometimes a little phlegm. No blood.", "has": ["Dry", "Productive (With sputum)"]},
    "Productive (With sputum)": {"say": "Sometimes a little phlegm. No blood.", "has": ["Color of sputum"]},
    "Color of sputum": {"say": "I'm not sure of the color. No blood in it.", "not": ["Red or pink"]},
    "Other [describe]": {"say": "Runny nose and sneezing, especially around dust."},
    "Does the symptom get worse with the following situation(s)?": {
        "say": "Dust, cold air and any kind of activity make it worse. I don't have to prop myself up to breathe at night.",
        "has": ["Exposure to dust, pollen", "Excercise", "Other [Describe]"], "not": ["Orthopnea"]},
    "Other [Describe]": {"say": "Cold air."},
    "Does the symptom get better with the following situation(s)?": UNSURE,
    "What is your occupation?": {"say": "I'm a school teacher. I've never worked around cotton or coal dust.", "has": ["[Describe]"]},
    "[Describe]": {"say": "School teacher; never worked around cotton or coal dust."},
    "Have you had a recent period of prolonged immobilization (ie.hospitalization)?": {
        "say": "I've been in the hospital twice in the last two months because my breathing and coughing got so bad.",
        "has": ["Yes"]},
    "When": {"say": "In the last two months."},
    "How long": UNSURE,
    "Reason": {"say": "My breathing and coughing got very bad."},
    "Any known allergies to food/insects/latex": {"say": "Not that I know of. My brother has a food allergy.", "has": ["No"]},
    "Have you taken any treatment (including self-medication or home remedies) or seen any health provider for this problem before coming here today?": {
        "say": "Yes. I use a bronchodilator and a steroid inhaler, and before that I took aminophylline, ketotifen and montelukast.",
        "has": ["Yes [Describe]"]},
    "Yes [Describe]": {"say": "Bronchodilator and steroid inhaler now; before: aminophylline, ketotifen and montelukast."},
    "Additional information": {
        "say": "At first it came and went, mostly in winter, and I was fine in between. Over the last few years it's there "
               "almost all the time and sometimes gets worse. The breathing is worse at night and sometimes in the day. "
               "I cough day and night, worse with dust or cold air. I don't wake up gasping. My bowels and urination are normal. "
               "No heart problem or reflux that I know of."},
    "Do you have a history of any of the following?": {
        "say": "I've been in the hospital twice in the last two months for my breathing. I don't have high blood pressure or diabetes.",
        "has": ["Hospitalization"], "not": ["High Blood Pressure", "Diabetes"]},
    "When did it occur?": {"say": "In the last two months."},
    "How long were you hospitalized?": UNSURE,
    "Have you recently taken any kind of medicine (including ayurvedic/homeopathic/unani/herbal)?": {
        "say": "Yes, I use a bronchodilator and a steroid inhaler.", "has": ["Yes"]},
    "Name of Medications": {"say": "A bronchodilator and a steroid inhaler.", "has": ["Medication name 1"]},
    "Medication Name": {"say": "Bronchodilator and steroid inhalers."},
    "From": UNSURE,
    "To": UNSURE,
    "How often do you have trouble taking medicines the way you have been told to take them?": UNSURE,
    "Smoking history": {"say": "I smoke 10 to 15 cigarettes a day, for the past 10 years.", "has": ["Current-smoker"]},
    "Since": {"say": "10 years."},
    "How many cigarettes per day do you smoke?": {"say": "10 to 15."},
    "Do you have a family history of any of the following?": {
        "say": "My brother has asthma and a food allergy.", "has": ["Asthma", "Other"]},
    "Asthma": {"say": "My brother.", "has": ["Brother"]},
    "[Describe relation]": {"say": "Brother."},
    "Other": {"say": "Brother has a food allergy."},
})
sheets["TC04"] = {"questions": q, "denies": ["Fever", "Weight change (kg)", "Orthopnea", "High Blood Pressure", "Diabetes",
                                             "Heart disease"],
                  "assumed": ["Do you have any allergies?", "Do you chew tobbaco?", "Alcohol use",
                              "Any known allergies to food/insects/latex"]}

# ---------- TC05: 20-year-old woman, fever (malaria) ----------
q = assumed_history()
q.update({
    "Since when have you had this symptom?": {"say": "Recently. I'm not sure exactly how many days.",
                                              "accept": ["few", "recent", "not sure", "unsure"]},
    "Nature of fever": {"say": "It comes and goes. It seems to hit every other day.",
                        "has": ["Alternate days", "Irregular (comes & goes)"]},
    "In a day, when do you feel fever the most?": {"say": "In the evening.", "has": ["Evening"]},
    "Severity": {"say": "They're high fevers.", "has": ["High"]},
    "Do you have the following symptom(s)?": {
        "say": "I get chills and shivering with the fever. I feel generally unwell, I have no appetite, and I feel kind of nauseous.",
        "has": ["Chills", "General weakness", "Nausea"]},
    "Have you ever been diagnosed with any of the following specific diseases?": {"say": "No, none of those.", "has": ["None"]},
    "Have you experienced the following situation within the previous months before fever started?": UNSURE,
    "Has there been a recent epidemic in the community (other than Covid-19)?": UNSURE,
    "Have you taken any treatment (including self-medication or home remedies) or seen any health provider for this problem before coming here today?": {
        "say": "I tried some over-the-counter antibiotics, but they didn't help at all.", "has": ["Yes [Describe]"]},
    "Yes [Describe]": {"say": "Over-the-counter antibiotics; they didn't help."},
    "Additional information": {
        "say": "The fevers come with chills and shivering, get worse in the evening and seem to come every other day. "
               "I feel generally unwell, I have no appetite and I feel a bit nauseous. The antibiotics I bought didn't help."},
    "Pregnancy status": {"say": "No, I'm not pregnant.", "has": ["No"]},
    "Do you have a history of any of the following?": {"say": "No, no other illnesses.", "has": ["None"]},
})
sheets["TC05"] = {"questions": q, "denies": [],
                  "assumed": ASSUMED_KEYS + ["Pregnancy status", "Do you have a history of any of the following?",
                                             "Have you ever been diagnosed with any of the following specific diseases?"]}

# Red-flag checks: answered by the CHW from the story and the exam findings. Teaching cases write down
# only abnormal findings, so a sign that is not mentioned is answered "no".
NOT_DEHYDRATED = {
    "Is the patient drinking poorly or unable to drink?": "no",
    "Are the eyes sunken?": "no",
    "Pinch the skin of the belly and let go: does it go back very slowly (2 seconds or more)?": "no",
    "Is the patient unusually sleepy, floppy or hard to wake?": "no",
}
for case_id in sheets:
    sheets[case_id]["checks"] = dict(NOT_DEHYDRATED)
# TC04 exam: breathless and sitting propped up, RR 24/min. Breathless, but able to talk; 24/min is fast
# but not "very fast"; no muscle use or blue lips written down.
sheets["TC04"]["checks"].update({
    "Is the patient too breathless to say a full sentence (or, for a baby, to feed)?": "no",
    "Is the patient breathing very fast, or using neck, chest or belly muscles to breathe? (Child: chest pulling in, nostrils flaring, grunting)": "no",
    "Are the lips or tongue blue or grey?": "no",
})

# The opening: the first paragraph of each story, as the patient says it when asked to tell more.
with open("eval_cases.json", encoding="utf-8") as f:
    cases = {c["id"]: c for c in json.load(f)["cases"]}
for case_id, sheet in sheets.items():
    sheet["opening"] = cases[case_id]["story"][0]

with open("eval_patient_answers.json", "w", encoding="utf-8") as f:
    json.dump(sheets, f, indent=2, ensure_ascii=False)
print("saved eval_patient_answers.json")
