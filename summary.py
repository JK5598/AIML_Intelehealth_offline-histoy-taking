import re

import red_flags as rf

# The patient's own words are shown under an answer when they say more than the chosen option
# ("Pain radiates to: Chest" + patient said "To my back and my chest"). Facts with no option in the
# protocol (back, jaundice, high cholesterol, "twice") would otherwise never reach the doctor.
# These words don't count as "saying more": common little words, and words that only restate the answer
# ("No, I don't drink." for Alcohol use: No).
COMMON_WORDS = set("""a an the i im ive id my me it its is was were be been am are and or but so to of in on at for
with that this there no not dont do does did have has had havent yes yeah just about like really very some any know
think sure maybe mostly usually also only when what which they theyre
drink drinking take taking took use used medicine medicines medical problems problem other anything nothing runs
family feel get around kind bit makes moving rather say all""".split())
SKIP_SOURCES = ("from story", "from earlier answer")   # the story is shown at the top already


def content_words(text):
    words = re.findall(r"[a-z]+", text.lower().replace("'", ""))
    return [w for w in words if len(w) > 2 and w not in COMMON_WORDS]


def says_more(words, answer):
    """True if the patient's words hold a word that the question and chosen options don't already cover."""
    covered = " ".join(answer["answers"]) + " " + str(answer["value"] or "") + " " + answer["question"]
    covered_starts = {w[:5] for w in content_words(covered)}
    return any(w[:5] not in covered_starts for w in content_words(words))


def quote_places(answers):
    """Which answer shows each reply. The same reply is often saved on two answers (the symptoms the
    patient has, and the ones they said no to): show it once, on the "has" answer if there is one."""
    places = {}
    for index, answer in enumerate(answers):
        words = answer.get("patient_words")
        if not words or answer.get("source") in SKIP_SOURCES or not says_more(words, answer):
            continue
        if words not in places or answers[places[words]].get("status") == "said_no":
            if words not in places or answer.get("status") != "said_no":
                places[words] = index
    return set(places.values())


def facts_lines(answers):
    lines = []
    quote_here = quote_places(answers)
    for index, answer in enumerate(answers):
        labels = [a for a in answer["answers"] if not a.startswith("[")]
        if answer.get("status") == "said_no":
            text = ", ".join(labels) + ": patient said NO"
        #----- Lia's code: show unsure / not answered (from the multi-question intake follow-ups) -----
        elif answer.get("status") == "unsure":
            text = ", ".join(labels + ([str(answer["value"])] if answer["value"] else []))
            text = (text + " (patient unsure)") if text else "patient unsure"
        elif answer.get("status") == "not_answered":
            text = "asked, no answer"
        #----- end of Lia's code -----
        elif labels and answer["value"]:
            text = ", ".join(labels) + ": " + str(answer["value"])
        elif answer["value"]:
            text = str(answer["value"])
        else:
            text = ", ".join(labels)
        if text:
            if index in quote_here:
                text += f' (patient said: "{answer["patient_words"]}")'
            lines.append(f"- {answer['question']}: {text}")
    return lines


def template_summary(patient, complaint, answers, red_flags, possible_red_flags, exam_steps, story=""):
    lines = []
    if red_flags:
        lines.append("RED FLAGS (most urgent first):")
        lines.extend("  - " + rf.describe(flag) for flag in rf.sort_by_level(red_flags))
    if possible_red_flags:
        lines.append("POSSIBLE RED FLAGS (came up next to 'no' or 'not', please check): "
                     + "; ".join(rf.describe(flag) for flag in rf.sort_by_level(possible_red_flags)))
    if red_flags or possible_red_flags:
        lines.append("")
    lines.append(f"Patient: {patient['age']:g}-year-old {patient['sex']}")
    lines.append(f"Chief complaint: {complaint}")
    if story:
        lines.append(f"Patient's own words: \"{story}\"")
    lines.append("")
    lines.extend(facts_lines(answers))
    if exam_steps:
        lines.append("")
        lines.append("Physical exam to perform: " + "; ".join(exam_steps))
    return "\n".join(lines)


def missing_red_flags(summary_text, red_flags):
    text = summary_text.lower()
    return [flag for flag in red_flags if flag.lower() not in text]