"""Questions that the complaint protocol (hpi) and the history protocols (patHist, famHist) both ask.

When the later question comes up, the app suggests its answer from the earlier one and the CHW confirms it
("Patient already said: ... Keep?"), like an answer taken from the patient's story. No question is removed:
if there is nothing to reuse or the CHW says no, the question is asked as usual.

The option is chosen by the table below, not by the AI: in our tests MedPsy-1.7B read "10 to 15 cigarettes
a day for 10 years" as Ex-smoker. The AI only fills the typed follow-ups (Since, When, Reason, ...) from
the earlier answer, and the CHW checks those too."""


# (later question, earlier complaint questions, earlier answer -> later option)
# An earlier answer that is not in the map is not reused. Where the earlier question is narrower (only
# food/insects/latex, only long-term drinking, only recent stays, only breast cancer, "medication" without
# herbal remedies), only its "yes" is in the map: its "no" says nothing about the later question.
# None: the earlier answer doesn't say which option ("Yes, 10 cigarettes a day" could be current or ex),
# so the CHW picks it, and only the follow-ups under it are filled from the earlier answer.
REPEATED = [
    ("Smoking history", ["Do you smoke/have ever smoked?", "Do you smoke or have ever smoked?"],
     {"Yes": "Current-smoker", "Ex-smoker": "Ex-smoker", "No": "Never-smoker", "Yes [Describe in your words]": None}),
    ("Have you recently taken any kind of medicine",
     ["Have you taken any medication recently?", "Have you recently taken any medication?"],
     {"Yes [Describe]": "Yes", "[Describe]": "Yes"}),
    ("Pregnancy status", ["Are you currently pregnant?"], {"Yes": "Yes", "No": "No"}),
    ("Has your child been vaccinated?", ["Did you complete your vaccination during your childhoold?"],
     {"Yes": "Complete"}),
    ("Do you have any allergies?", ["Any known allergies to food/insects/latex"], {"Yes": "Yes [Describe]"}),
    ("Alcohol use", ["Have you consumed alcohol for long duration?"], {"Yes": "Yes"}),
    ("Do you have a history of any of the following?",
     ["Have you had a recent period of prolonged immobilization", "Have you recently been hospitalized?"],
     {"Yes": "Hospitalization"}),
    ("Do you have a history of any of the following?", ["Have you ever been diagnosed with HIV/AIDS?"],
     {"Since when": "HIV/AIDS"}),
    ("Do you have a family history of any of the following?",
     ["Did any of your immediate family members have breast cancer?"], {"Yes": "Cancer"}),
]


def describe(answer):
    labels = [label for label in answer["answers"] if label]
    text = f"{answer['question']}: {', '.join(labels)}"
    if answer["value"]:
        value = answer["value"].rstrip(".")
        text += f" - {value}" if labels else value
    if answer["status"] == "said_no":
        text += " (patient said no)"
    text += "."
    # Words from the opening story are left out: they are about everything, not this question.
    if answer["patient_words"] and answer["source"] != "from story":
        text += f' Patient said: "{answer["patient_words"]}"'
    return text


def find_earlier_answer(question_text, asked):
    """asked: {complaint question text: the answers saved for it and its follow-ups}.
    Returns the earlier answers as one text, and the later options they point to (None: the whole
    question, but no option chosen). Returns ("", []) when there is nothing to reuse."""
    lines = []
    targets = []
    for later, earlier_questions, answer_map in REPEATED:
        if not question_text.startswith(later):
            continue
        for earlier_text, answers in asked.items():
            if not any(earlier_text.startswith(earlier) for earlier in earlier_questions):
                continue
            if not answers or answers[0]["status"] != "present" or len(answers[0]["answers"]) != 1:
                continue
            label = answers[0]["answers"][0]
            if label not in answer_map:
                continue
            lines += [describe(answer) for answer in answers]
            targets.append(answer_map[label])
    return " ".join(lines), targets
