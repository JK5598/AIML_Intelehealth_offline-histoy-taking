def facts_lines(answers):
    lines = []
    for answer in answers:
        labels = [a for a in answer["answers"] if not a.startswith("[")]
        if answer.get("status") == "said_no":
            text = ", ".join(labels) + ": patient said NO"
        elif labels and answer["value"]:
            text = ", ".join(labels) + ": " + str(answer["value"])
        elif answer["value"]:
            text = str(answer["value"])
        else:
            text = ", ".join(labels)
        if text:
            lines.append(f"- {answer['question']}: {text}")
    return lines


def template_summary(patient, complaint, answers, red_flags, possible_red_flags, exam_steps, story=""):
    lines = []
    if red_flags:
        lines.append("RED FLAGS: " + "; ".join(red_flags))
    if possible_red_flags:
        lines.append("POSSIBLE RED FLAGS (came up next to 'no' or 'not', please check): "
                     + "; ".join(possible_red_flags))
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
