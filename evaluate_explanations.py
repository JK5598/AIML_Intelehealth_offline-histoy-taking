import argparse
import csv
import os
import time

from ai_mapper import AIMapper


TEST_FILE = "explanation_test_cases.csv"


def load_cases(path=TEST_FILE):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run(model_path, cases):
    """Asks the model about every test word and saves a CSV for a person to grade."""
    model_name = os.path.basename(model_path)
    print(f"\n{model_name}:")
    mapper = AIMapper(model_path)

    rows = []
    started = time.time()
    for case in cases:
        call_started = time.time()
        text = mapper.explain(case["word"], case["kind"], case["question"], case["complaint"])
        seconds = round(time.time() - call_started, 2)
        print(f"   {seconds:5.2f} s  {case['word'][:30]:30} -> {text}")
        rows.append({
            "complaint": case["complaint"],
            "question": case["question"],
            "word": case["word"],
            "kind": case["kind"],
            "ai_explanation": text,
            "expected_meaning": case["expected_meaning"],
            "seconds": seconds,
            "correct (y/n/partly)": "",
            "checked_by": "",
        })
    total = time.time() - started

    seconds = [row["seconds"] for row in rows]
    print(f"   {len(rows)} words in {total:.1f} s: average {sum(seconds) / len(seconds):.2f} s, "
          f"slowest {max(seconds):.2f} s per word on this computer")

    out_file = f"explanation_results_{model_name.replace('.gguf', '')}.csv"
    with open(out_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"   Saved to {out_file}. Fill in the 'correct (y/n/partly)' column by hand.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask the AI to explain the words in explanation_test_cases.csv")
    parser.add_argument("models", nargs="+", help="MedPsy .gguf files to test")
    args = parser.parse_args()
    cases = load_cases()
    print(f"{len(cases)} test words from {TEST_FILE}")
    for model_path in args.models:
        run(model_path, cases)
