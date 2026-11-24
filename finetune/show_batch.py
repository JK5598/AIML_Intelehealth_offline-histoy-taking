"""Prints targets compactly so the patient sentences can be written for them."""
import json
import sys

start, end = int(sys.argv[1]), int(sys.argv[2])
targets = [json.loads(line) for line in open("targets.jsonl", encoding="utf-8")]
for t in targets[start:end]:
    has = [t["options"][i] for i in t["has"]]
    denies = [t["options"][i] for i in t["denies"]]
    print(f'{t["id"]} [{t["kind"]}{", story" if t["story"] else ""}] {t["complaint"]} | Q: {t["question"]} | '
          f'options: {"; ".join(t["options"])} | HAS: {has} | DENIES: {denies}')
