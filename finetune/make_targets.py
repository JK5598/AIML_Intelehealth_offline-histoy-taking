"""Step 1 of the fine-tuning data: pick real protocol questions and choose the correct answer FIRST.
The patient sentences are written afterwards for these answers, so every label is known by design.
Output: targets.jsonl (one line per sentence to write)."""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))      # the app folder, for protocols.py
import protocols as p  # noqa: E402

PROTOCOLS = os.environ.get("PROTOCOLS", os.path.join(HERE, "..", "..", "intelehealth-ayu-protocols",
                                                     "protocols", "v2", "All Protocols (JSON)"))
SEED = 6
HOLDOUT_COUNT = 10          # whole complaints kept out of training, to test on unseen questions
KEEP_IN_TRAINING = {"Abdominal Pain", "Cough", "Fever", "Difficulty breathing"}
NONE_WORDS = ("none", "no", "never", "do not", "don't", "not ")


def option_nodes(question):
    """The answer options of a question: children with a label that are not just a text box."""
    options = []
    for child in p.children(question):
        label = p.option_label(child)
        if not label:
            continue
        if p.input_type(child) and not p.children(child):
            continue
        options.append(child)
    return options


def is_section_list(node, options, complaint):
    """Protocol headings like 'Red or painful eye' -> Site / Duration / ... are not real questions."""
    if p.display_text(node).strip().lower() == complaint.lower():
        return True
    with_sub_questions = [o for o in options if len(p.children(o)) >= 2]
    if len(with_sub_questions) * 2 > len(options):
        return True
    text = p.display_text(node).strip().lower()
    return text in ("yes", "no") or text.startswith("medication name") or len(text) < 4


def collect_questions(node, complaint, found):
    options = option_nodes(node)
    if len(options) >= 2 and p.display_text(node) and not is_section_list(node, options, complaint):
        found.append({
            "complaint": complaint,
            "question": p.display_text(node),
            "options": [p.option_label(o) for o in options],
            "multi": bool(p.is_multi_choice(node)),
            "exclusive": [i for i, o in enumerate(options) if p.is_exclusive(o)],
        })
    for child in p.children(node):
        collect_questions(child, complaint, found)


def none_option(question):
    """An option that itself means 'no / none' (e.g. 'None', 'No', 'Never-smoker'), if the question has one."""
    for i, label in enumerate(question["options"]):
        text = label.lower()
        if text.startswith(NONE_WORDS) or i in question["exclusive"] and "none" in text:
            return i
    return None


def real_options(question):
    """Options a patient can describe in words (not 'None', 'Other [describe]' or 'Don't know')."""
    skip = []
    for i, label in enumerate(question["options"]):
        text = label.lower()
        if i == none_option(question) or "other" in text or "describe" in text or "know" in text or "unsure" in text:
            skip.append(i)
    return [i for i in range(len(question["options"])) if i not in skip]


def choose_kind(question, rng):
    usable = real_options(question)
    kinds = ["single"] * 45 + ["unclear"] * 10
    if none_option(question) is not None:
        kinds += ["no_answer"] * 20          # "No, I don't smoke" -> the question's own "No"
    if question["multi"] and len(usable) >= 2:
        kinds += ["deny"] * 15               # "No fever, no rash" -> nothing to record here (0)
    if question["multi"] and len(usable) >= 3 and "severit" not in question["question"].lower():
        kinds += ["two"] * 30 + ["has_and_deny"] * 15
    return rng.choice(kinds)


def make_target(question, kind, rng):
    usable = real_options(question)
    target = {"has": [], "denies": [], "expected": []}
    if kind == "single":
        target["has"] = [rng.choice(usable)]
    elif kind == "two":
        target["has"] = sorted(rng.sample(usable, 2))
    elif kind == "deny":
        target["denies"] = sorted(rng.sample(usable, min(2, len(usable))))
    elif kind == "has_and_deny":
        has, denied = rng.sample(usable, 2)
        target["has"], target["denies"] = [has], [denied]
    elif kind == "no_answer":
        target["denies"] = usable[:]
    # what the model should end up recording
    if target["has"]:
        target["expected"] = target["has"]
    elif kind == "no_answer":
        target["expected"] = [none_option(question)]
    return target


def main():
    rng = random.Random(SEED)
    complaints = p.list_complaints(PROTOCOLS)
    questions = []
    for name in complaints:
        collect_questions(p.load_protocol(PROTOCOLS, name), name, questions)
    for history_file, label in (("patHist", "Past history"), ("famHist", "Family history")):
        collect_questions(p.load_protocol(PROTOCOLS, history_file), label, questions)

    candidates = [c for c in complaints if c not in KEEP_IN_TRAINING and c not in ("Other", "Follow up visit")]
    holdout = sorted(rng.sample(candidates, HOLDOUT_COUNT))

    # at most 10 questions per complaint (keeps big protocols from taking over), shuffled
    by_complaint = {}
    for q in questions:
        by_complaint.setdefault(q["complaint"], []).append(q)
    picked = []
    for name, qs in by_complaint.items():
        rng.shuffle(qs)
        unique = {}
        for q in qs:
            unique.setdefault(q["question"] + "|" + "|".join(q["options"]), q)
        picked.extend(list(unique.values())[:10])
    rng.shuffle(picked)

    targets = []
    for number, q in enumerate(picked, start=1):
        if not real_options(q):
            continue
        kind = choose_kind(q, rng)
        target = make_target(q, kind, rng)
        split = "holdout" if q["complaint"] in holdout else ("val" if rng.random() < 0.15 else "train")
        targets.append({"id": f"T{number:04d}", "split": split, "kind": kind, **q, **target,
                        "story": rng.random() < 0.3})
    with open(os.path.join(HERE, "targets.jsonl"), "w", encoding="utf-8") as f:
        for t in targets:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    counts = {}
    for t in targets:
        counts[(t["split"], t["kind"])] = counts.get((t["split"], t["kind"]), 0) + 1
    print("questions found:", len(questions), "| targets:", len(targets))
    print("holdout complaints:", holdout)
    for key in sorted(counts):
        print("  ", key, counts[key])


if __name__ == "__main__":
    main()
