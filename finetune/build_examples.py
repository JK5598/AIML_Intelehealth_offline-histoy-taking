"""Step 3 of the fine-tuning data: turn targets + patient sentences into the exact prompts the app sends MedPsy.

The app's own AIMapper code builds every prompt. We swap the model for a "teacher" that already knows the
right answer, run the same steps the app runs (first pick, "anything else?", yes/no double-check), and
save each prompt with the correct reply. So the training prompts can never drift from the app's prompts.

Each patient sentence is used twice:
  - map mode:   the CHW asked this question and typed what the patient said (ANSWER_RULES)
  - story mode: the patient's opening story is checked against this question (STORY_RULES)
Extra examples:
  - a wrong option offered to the yes/no check -> "no"
  - a story paired with a question the patient never talked about -> 0 "Not mentioned by the patient"

Output: data/train.jsonl, data/val.jsonl, data/holdout.jsonl with {"prompt", "completion", "meta"}.
"""
import json
import os
import random
import re
import sys
import types

# ai_mapper imports llama_cpp. We only need its prompt code, so give it an empty stand-in.
fake_llama = types.ModuleType("llama_cpp")
fake_format = types.ModuleType("llama_cpp.llama_chat_format")
fake_format.Jinja2ChatFormatter = object
fake_llama.llama_chat_format = fake_format
fake_llama.Llama = None
fake_llama.LlamaGrammar = types.SimpleNamespace(from_string=lambda *args, **kwargs: None)
sys.modules["llama_cpp"] = fake_llama
sys.modules["llama_cpp.llama_chat_format"] = fake_format

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))      # the app folder, for ai_mapper.py and protocols.py
sys.path.insert(0, HERE)
import ai_mapper  # noqa: E402

import make_targets  # noqa: E402
import protocols as p  # noqa: E402

SEED = 6
NOT_MENTIONED_PER_STORY = 1


class Teacher:
    """Plays the model's part: answers each prompt the way a perfect model would."""

    def __init__(self, expected_labels):
        self.expected = expected_labels
        self.records = []

    def __call__(self, prompt, grammar=None, max_tokens=40, task="task"):
        user = prompt.split("<|im_start|>user\n")[-1].split("<|im_end|>")[0]
        if "Proposed answer:" in user:
            label = re.search(r"Proposed answer: (.*)\n", user).group(1)
            reply = '{"answer": "yes"}' if label in self.expected else '{"answer": "no"}'
            step = "check"
        else:
            already = []
            match = re.search(r"Already recorded: (.*)\n", user)
            if match:
                already = match.group(1).split(", ")
            options = re.findall(r"^(\d+)\. (.*)$", user.split("Options:\n")[1], flags=re.M)
            number = 0
            for wanted in self.expected:
                if wanted in already:
                    continue
                for option_number, label in options:
                    if label == wanted and option_number != "0":
                        number = int(option_number)
                        break
                if number:
                    break
            reply = '{"answer": ' + str(number) + "}"
            step = "more" if already else "first"
        self.records.append({"prompt": prompt, "completion": reply, "step": step})
        return reply


def new_mapper(teacher):
    mapper = object.__new__(ai_mapper.AIMapper)
    mapper.story_check = "yes_no"
    mapper.timings = []
    mapper.generate = teacher
    return mapper


def content_stems(text):
    stems = set()
    for word in re.findall(r"[a-z]+", text.lower()):
        if len(word) > 3:
            stems.add(word[:5])
    return stems


GENERIC_STEMS = {"which", "there", "other", "about", "follo", "sympt", "have", "does", "part", "describ",
                 "with", "from", "your", "body", "start", "after", "befor", "durin", "situa", "speci"}


def unrelated(question, sentence, complaint):
    """True if the sentence clearly says nothing about this question (no shared words at all)."""
    words = question["question"] + " " + " ".join(question["options"]) + " " + complaint
    question_stems = content_stems(words) - GENERIC_STEMS
    return not (question_stems & content_stems(sentence))


def one_target_examples(target, sentence, question_pool, rng):
    labels = target["options"]
    expected = [labels[i] for i in target["expected"]]
    examples = []

    for mode in ("map", "story"):
        teacher = Teacher(expected)
        mapper = new_mapper(teacher)
        if mode == "map":
            mapper.map_answer(target["question"], labels, sentence, target["multi"])
        else:
            mapper.answer_from_story(target["question"], labels, sentence, target["multi"])
        for record in teacher.records:
            record["mode"] = mode
        examples.extend(teacher.records)

    # yes/no check: every right answer gets a "yes" (the app checks story picks and later picks)
    words_line = f"Patient said: \"{sentence}\""
    teacher = Teacher(expected)
    mapper = new_mapper(teacher)
    for label in expected:
        mapper.patient_clearly_said(words_line, target["question"], label)
    # ...and one wrong option gets a "no": a denied option if there is one, else any other option
    wrong = [labels[i] for i in target["denies"] if labels[i] not in expected]
    if not wrong:
        wrong = [label for label in labels if label not in expected]
    if wrong:
        mapper.patient_clearly_said(words_line, target["question"], rng.choice(wrong))
    for record in teacher.records:
        record["mode"] = "check"
    examples.extend(teacher.records)

    # a story checked against a question the patient never talked about -> 0
    same_complaint = [q for q in question_pool if q["complaint"] == target["complaint"]]
    others = [q for q in question_pool if q["complaint"] != target["complaint"]]
    rng.shuffle(same_complaint)
    rng.shuffle(others)
    added = 0
    for question in same_complaint + others:
        if added >= NOT_MENTIONED_PER_STORY:
            break
        if question["question"] == target["question"] or not unrelated(question, sentence, target["complaint"]):
            continue
        teacher = Teacher([])
        mapper = new_mapper(teacher)
        mapper.answer_from_story(question["question"], question["options"], sentence, question["multi"])
        for record in teacher.records:
            record["mode"] = "not_mentioned"
            record["other_question"] = question["question"]
        examples.extend(teacher.records)
        added += 1

    unique = {}
    for example in examples:
        unique.setdefault(example["prompt"], example)
    examples = list(unique.values())
    for example in examples:
        example["meta"] = {"id": target["id"], "kind": target["kind"], "complaint": target["complaint"],
                           "mode": example.pop("mode"), "step": example.pop("step"),
                           "other_question": example.pop("other_question", "")}
    return examples


def all_questions():
    questions = []
    for name in p.list_complaints(make_targets.PROTOCOLS):
        make_targets.collect_questions(p.load_protocol(make_targets.PROTOCOLS, name), name, questions)
    return [q for q in questions if make_targets.real_options(q)]


def main():
    rng = random.Random(SEED)
    targets = [json.loads(line) for line in open(os.path.join(HERE, "targets.jsonl"), encoding="utf-8")]
    sentences = {}
    for line in open(os.path.join(HERE, "sentences.jsonl"), encoding="utf-8"):
        row = json.loads(line)
        sentences[row["id"]] = row["text"]

    holdout_complaints = {t["complaint"] for t in targets if t["split"] == "holdout"}
    questions = all_questions()
    seen_pool = [q for q in questions if q["complaint"] not in holdout_complaints]
    holdout_pool = [q for q in questions if q["complaint"] in holdout_complaints]

    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    files = {name: open(os.path.join(HERE, "data", f"{name}.jsonl"), "w", encoding="utf-8") for name in ("train", "val", "holdout")}
    counts = {}
    for target in targets:
        if target["id"] not in sentences:
            continue
        pool = holdout_pool if target["split"] == "holdout" else seen_pool
        for example in one_target_examples(target, sentences[target["id"]], pool, rng):
            example["meta"]["split"] = target["split"]
            files[target["split"]].write(json.dumps(example, ensure_ascii=False) + "\n")
            key = (target["split"], example["meta"]["mode"], example["meta"]["step"], example["completion"])
            counts[key] = counts.get(key, 0) + 1
    for f in files.values():
        f.close()

    totals = {}
    for (split, mode, step, completion), n in counts.items():
        totals[split] = totals.get(split, 0) + n
    print("examples:", totals)
    for key in sorted(counts):
        if key[0] == "train":
            print("  ", key, counts[key])


if __name__ == "__main__":
    main()
