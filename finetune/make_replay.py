"""Turns the original model's explain answers (explain_before.json, from the first Colab run) into replay examples,
so the Unsloth run trains on exactly the same replay data without generating it again."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
prompts = [json.loads(line) for line in open(os.path.join(HERE, "data", "keep_prompts.jsonl"), encoding="utf-8")]
answers = json.load(open(os.path.join(HERE, "data", "explain_before.json"), encoding="utf-8"))

count = 0
with open(os.path.join(HERE, "data", "replay.jsonl"), "w", encoding="utf-8") as f:
    for row, answer in zip(prompts, answers):
        if answer["text"] != row["meta"]["text"]:
            raise SystemExit("explain_before.json is not in the same order as keep_prompts.jsonl")
        if not answer["answer"]:
            continue
        example = {"prompt": row["prompt"], "completion": answer["answer"],
                   "meta": {"mode": "explain", "step": "replay", "id": ""}}
        f.write(json.dumps(example, ensure_ascii=False) + "\n")
        count += 1
print(count, "replay examples")
