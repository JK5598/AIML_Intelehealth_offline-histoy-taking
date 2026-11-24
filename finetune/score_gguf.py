"""Scores a GGUF model on the fine-tuning examples, the way the app runs it: llama.cpp, 4-bit file, same grammar.

Run it once for each model, on the same file, and compare:
    python finetune/score_gguf.py --model medpsy-1.7b-base-q4_k_m.gguf --data finetune/data/holdout.jsonl
    python finetune/score_gguf.py --model medpsy-1.7b-ft-q4_k_m.gguf   --data finetune/data/holdout.jsonl

Saves eval_results/<date>_gguf-scores/<model>_<data>.json
"""
import argparse
import datetime
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ai_mapper  # noqa: E402  (also fixes MedPsy's chat template for llama_cpp)
from llama_cpp import Llama, LlamaGrammar  # noqa: E402


def grammar_for(example):
    if '"yes"' in example["completion"] or '"no"' in example["completion"]:
        return LlamaGrammar.from_string(ai_mapper.YES_NO_GRAMMAR, verbose=False)
    user = example["prompt"].split("<|im_start|>user\n")[-1]
    option_count = len(re.findall(r"^\d+\. ", user.split("Options:\n")[1], flags=re.M)) - 1
    return ai_mapper.one_number_grammar(option_count)


def is_nothing(reply):
    return reply in ('{"answer": 0}', '{"answer": "no"}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--limit", type=int, default=0, help="only the first N examples (quick try)")
    args = parser.parse_args()

    examples = [json.loads(line) for line in open(args.data, encoding="utf-8")]
    if args.limit:
        examples = examples[:args.limit]
    model = Llama(model_path=args.model, n_ctx=4096, verbose=False)

    groups = {}
    rows = []
    started = time.time()
    for number, example in enumerate(examples, start=1):
        result = model(example["prompt"], max_tokens=12, temperature=0, grammar=grammar_for(example),
                       stop=["<|im_end|>"])
        got = result["choices"][0]["text"].strip()
        want = example["completion"]
        meta = example["meta"]
        group_name = meta["mode"] + " / " + meta["step"]
        for name in ("ALL", group_name):
            g = groups.setdefault(name, {"n": 0, "right": 0, "made_up": 0, "nothing_cases": 0,
                                         "missed": 0, "something_cases": 0})
            g["n"] += 1
            g["right"] += int(got == want)
            if is_nothing(want):
                g["nothing_cases"] += 1
                g["made_up"] += int(not is_nothing(got))
            else:
                g["something_cases"] += 1
                g["missed"] += int(is_nothing(got))
        rows.append({"id": meta["id"], "group": group_name, "want": want, "got": got})
        if number % 50 == 0:
            print(f"  {number}/{len(examples)} ({(time.time() - started) / 60:.1f} min)")

    print(f"\n{os.path.basename(args.model)} on {os.path.basename(args.data)}")
    print(f"  {'group':28s} {'n':>5s} {'right':>7s} {'made up':>9s} {'missed':>8s}")
    for name in sorted(groups, key=lambda k: (k != "ALL", k)):
        g = groups[name]
        made_up = 100 * g["made_up"] / g["nothing_cases"] if g["nothing_cases"] else 0
        missed = 100 * g["missed"] / g["something_cases"] if g["something_cases"] else 0
        print(f"  {name:28s} {g['n']:5d} {100 * g['right'] / g['n']:6.1f}% {made_up:8.1f}% {missed:7.1f}%")
    print("  made up = picked something when the right reply was 0 / no;  missed = said 0 / no when there was an answer")

    folder = os.path.join(os.path.dirname(HERE), "eval_results", f"{datetime.date.today()}_gguf-scores")
    os.makedirs(folder, exist_ok=True)
    name = os.path.basename(args.model).replace(".gguf", "") + "_" + os.path.basename(args.data).replace(".jsonl", "")
    with open(os.path.join(folder, name + ".json"), "w", encoding="utf-8") as f:
        json.dump({"model": args.model, "data": args.data, "minutes": round((time.time() - started) / 60, 1),
                   "groups": groups, "rows": rows}, f, indent=1)
    print("saved", os.path.join(folder, name + ".json"))


if __name__ == "__main__":
    main()
