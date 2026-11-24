"""Prompts for the app's other jobs (explaining words), so training does not make MedPsy forget them.
In Colab the ORIGINAL model answers these first; its own answers are then mixed into training ("replay").
Only complaints from the training side are used, never the holdout complaints."""
import json
import os
import random

import build_examples  # sets up the stand-in llama_cpp and loads ai_mapper
import ai_mapper

SEED = 6
HOW_MANY = 120

HERE = os.path.dirname(os.path.abspath(__file__))
targets = [json.loads(line) for line in open(os.path.join(HERE, "targets.jsonl"), encoding="utf-8")]
holdout = {t["complaint"] for t in targets if t["split"] == "holdout"}
pool = [t for t in targets if t["complaint"] not in holdout]
rng = random.Random(SEED)
rng.shuffle(pool)

prompts = []
seen = set()
for t in pool:
    if len(prompts) >= HOW_MANY:
        break
    if rng.random() < 0.25:
        key = ("question", t["question"])
        prompt = ai_mapper.explain_prompt(t["question"], "question", "", t["complaint"])
    else:
        option = rng.choice(t["options"])
        key = ("option", option)
        prompt = ai_mapper.explain_prompt(option, "option", t["question"], t["complaint"])
    if key in seen:
        continue
    seen.add(key)
    prompts.append({"prompt": prompt, "meta": {"task": "explain", "kind": key[0], "text": key[1],
                                                "complaint": t["complaint"]}})

with open(os.path.join(HERE, "data", "keep_prompts.jsonl"), "w", encoding="utf-8") as f:
    for row in prompts:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print(len(prompts), "explain prompts")
