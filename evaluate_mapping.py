import argparse
import csv
import time

import negation
import protocols as p
import red_flags
from keyword_mapper import KeywordMapper


TEST_FILE = "test_cases.csv"
RED_FLAG_FILE = "red_flag_cases.csv"


def load_cases(path=TEST_FILE):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def split_list(text):
    if text.strip() in ("", "none", "unclear"):
        return []
    return [part.strip() for part in text.split(";")]


def find_question(protocol, starts_with):
    for question in p.children(protocol):
        if p.display_text(question).lower().startswith(starts_with.lower()):
            return question
    return None


def find_label_indexes(labels, wanted):
    indexes = []
    for want in wanted:
        for index, label in enumerate(labels):
            if label.startswith(want):
                indexes.append(index)
                break
        else:
            print(f"   (test case problem: option '{want}' not found)")
    return indexes


def run(mapper, folder, cases, use_negation_guard=True):
    results = {"answer": [0, 0], "story": [0, 0]}
    extra_picks = 0
    missed_picks = 0
    picked_what_patient_said_no_to = 0
    invented_answers = 0
    started = time.time()

    for case in cases:
        if case["mode"] not in results:
            continue
        question = find_question(p.load_protocol(folder, case["complaint"]), case["question"])
        if question is None:
            print(f"   (question not found: {case['complaint']} / {case['question']})")
            continue
        labels = [p.option_label(o) for o in p.children(question)]
        multi = p.is_multi_choice(question)
        words = case["patient_words"]

        if case["mode"] == "answer":
            picked = mapper.map_answer(p.display_text(question), labels, words, multi)["indexes"]
        elif p.story_prefill_allowed(question):
            picked = mapper.answer_from_story(p.display_text(question), labels, words, multi)
        else:
            picked = []
        if use_negation_guard:
            picked, dropped = negation.check_picks(labels, picked, words)

        expected = set(find_label_indexes(labels, split_list(case["expected"])))
        said_no = set(find_label_indexes(labels, split_list(case["expected_said_no"])))
        got = set(picked)

        ok = got == expected
        results[case["mode"]][0] += ok
        results[case["mode"]][1] += 1
        extra_picks += len(got - expected)
        missed_picks += len(expected - got)
        picked_what_patient_said_no_to += len(got & said_no)
        if case["mode"] == "story" and not expected and got:
            invented_answers += 1

        shown = ", ".join(labels[i] for i in sorted(got)) or "(nothing)"
        mark = "OK " if ok else "X  "
        print(f"   {mark} {case['mode']:6} {words[:40]:40} -> {shown[:45]:45} (expected {case['expected']})")

    minutes = (time.time() - started) / 60
    for mode, (correct, total) in results.items():
        if total:
            print(f"   {mapper.name} [{mode}]: {correct}/{total} correct ({100 * correct / total:.0f}%)")
    print(f"   extra picks: {extra_picks}   missed picks: {missed_picks}   "
          f"picked something the patient said NO to: {picked_what_patient_said_no_to}")
    print(f"   invented answers (story says nothing, something picked): {invented_answers}")
    print(f"   took {minutes:.1f} min")
    return results, extra_picks, missed_picks, picked_what_patient_said_no_to, invented_answers


def check_said_no(folder, cases):
    """Negation is plain code, so this part is the same for every mapper."""
    correct = 0
    total = 0
    for case in cases:
        question = find_question(p.load_protocol(folder, case["complaint"]), case["question"])
        if question is None or not p.is_multi_choice(question):
            continue
        options = p.children(question)
        labels = [p.option_label(o) for o in options]
        expected = set(find_label_indexes(labels, split_list(case["expected_said_no"])))
        found = set(i for i in negation.find_negated(labels, case["patient_words"])
                    if not p.is_exclusive(options[i]))
        ok = found == expected
        correct += ok
        total += 1
        if not ok:
            shown = ", ".join(labels[i] for i in sorted(found)) or "(nothing)"
            print(f"   X  {case['patient_words'][:50]:50} -> said no {shown} (expected {case['expected_said_no']})")
    print(f"   'said no' options found correctly: {correct}/{total} multi-choice cases")


def check_red_flag_cases(path=RED_FLAG_FILE):
    """Red flags are plain code too. Each case is one sentence from the patient."""
    with open(path, encoding="utf-8") as f:
        cases = list(csv.DictReader(f))
    correct = 0
    for case in cases:
        answer = {"answers": [], "value": None, "patient_words": case["patient_words"], "status": "present"}
        answers = [answer]
        # Optional column: options the CHW picked, e.g. "Vomiting; Chest indrawing=Yes"
        # ("Question=Answer" fills in the question label, for Yes/No sub-questions).
        for picked in split_list(case.get("answer_labels") or ""):
            question_label, _, label = picked.rpartition("=")
            answers.append({"answers": [label], "question_label": question_label, "value": None,
                            "patient_words": None, "status": "present"})
        # Optional column: a typed value, e.g. what the CHW typed for "Additional information".
        if case.get("typed_value"):
            answers.append({"answers": [], "value": case["typed_value"], "patient_words": None, "status": "present"})
        said_no_labels = split_list(case["said_no_labels"])
        if said_no_labels:
            answers.append({"answers": said_no_labels, "value": None,
                            "patient_words": case["patient_words"], "status": "said_no"})
        # Optional "age" column (years); blank means a 30-year-old adult.
        patient = {"age": float(case.get("age") or 30), "sex": case.get("sex") or "female"}
        flags, possible = red_flags.check(case["complaint"], answers, patient)
        ok = (set(flags) == set(split_list(case["expected_red_flags"]))
              and set(possible) == set(split_list(case["expected_possible"])))
        correct += ok
        mark = "OK " if ok else "X  "
        said_no_shown = "; ".join(said_no_labels) or "-"
        print(f"   {mark} {case['patient_words'][:40]:40} said no: {said_no_shown[:22]:22} "
              f"-> flags {flags}, possible {possible}")
    print(f"   red-flag cases correct: {correct}/{len(cases)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare the keyword baseline and the AI on test_cases.csv")
    parser.add_argument("protocols", help="folder with the Intelehealth v2 JSON files")
    parser.add_argument("models", nargs="*", help="MedPsy .gguf files to test (leave out for no AI)")
    parser.add_argument("--story-check", default="yes_no", choices=["off", "yes_no", "evidence"])
    args = parser.parse_args()
    folder = args.protocols
    cases = load_cases()
    print(f"{len(cases)} test cases from {TEST_FILE}\n")

    print("Negation check (no AI):")
    check_said_no(folder, cases)

    print("\nRed-flag check (no AI, draft guideline rules):")
    check_red_flag_cases()

    print("\nNo-AI keyword baseline:")
    run(KeywordMapper(), folder, cases)

    for model_path in args.models:
        from ai_mapper import AIMapper
        print(f"\nAI ({model_path.split('/')[-1]}, story check: {args.story_check}):")
        mapper = AIMapper(model_path, story_check=args.story_check)
        run(mapper, folder, cases)
        seconds = [t["seconds"] for t in mapper.timings]
        print(f"   {len(seconds)} AI calls, average {sum(seconds) / len(seconds):.1f} s per call on this computer")