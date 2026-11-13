"""Evaluation loop: plays every test case through the app and scores it against Dr. Verma's targets.

For each case, a simulated patient (Claude) answers from the case story, a simulated CHW (plain code)
types the patient's words into the app, and a judge (Claude) compares the app's record with the case.

How to run (from the project folder, Mac Terminal):
    PROTOCOLS="../intelehealth-ayu-protocols/protocols/v2/All Protocols (JSON)"
    python evaluate_visits.py "$PROTOCOLS" --offline                      (free test of the loop itself)
    python evaluate_visits.py "$PROTOCOLS"                                (keyword app, Claude patient + judge)
    python evaluate_visits.py "$PROTOCOLS" --model medpsy-1.7b-q4_k_m-imat.gguf
    python evaluate_visits.py "$PROTOCOLS" --model medpsy-1.7b-q4_k_m-imat.gguf --only TC01
Results go to eval_results/<date-time>/ (report.md, results.csv, and per case the visit, transcript, judge).
"""
import argparse
import csv
import json
import os
import time

from main import run_visit
from keyword_mapper import KeywordMapper
from sim_patient import ClaudePatient, ScriptedPatient, SimulatedCHW
import judge as j

TARGETS = {
    "recall": 0.85,            # key-fact recall, average over cases
    "sufficiency": 0.80,       # share of cases where the doctor could reach the diagnosis
    "wrong_facts": 0,          # wrong facts caused by the app, all cases together
    "false_alarm_cases": 0.2,  # at most 1 case in 5 with a false alarm
    "visit_minutes": 20,       # every visit
    "ai_minutes_phone": 10,    # every visit
}


def load_cases(path, only):
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    if only:
        wanted = [c.strip() for c in only.split(",")]
        cases = [c for c in cases if c["id"] in wanted]
    return cases


def make_mapper(model_path):
    if not model_path:
        return KeywordMapper()
    from ai_mapper import AIMapper
    return AIMapper(model_path, story_check="yes_no")


def run_case(case, facts, args, mapper, claude, judge, out_folder):
    if args.offline:
        patient = ScriptedPatient(case)
    else:
        patient = ClaudePatient(case, claude, args.patient_model)
    chw = SimulatedCHW(case, patient, careful=not args.accept_all)
    if hasattr(mapper, "timings"):
        mapper.timings = []   # count AI time for this visit only

    started = time.time()
    visit = run_visit(chw, mapper, args.protocols, intake_mode=args.intake)
    print(f"   visit done in {time.time() - started:.0f} s ({chw.prompts} prompts). Judging...")

    conversation = "\n".join(chw.conversation)
    verdict = judge.judge(case, facts, visit, conversation)

    case_folder = os.path.join(out_folder, case["id"])
    os.makedirs(case_folder, exist_ok=True)
    with open(os.path.join(case_folder, "visit.json"), "w", encoding="utf-8") as f:
        json.dump(visit, f, indent=2, ensure_ascii=False)
    with open(os.path.join(case_folder, "transcript.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(chw.transcript))
    with open(os.path.join(case_folder, "judge.json"), "w", encoding="utf-8") as f:
        json.dump(verdict, f, indent=2, ensure_ascii=False)

    app_wrong = [w for w in verdict["wrong_facts"] if not w.get("from_simulation")]
    simulation_wrong = [w for w in verdict["wrong_facts"] if w.get("from_simulation")]
    results = {item["id"]: item["result"] for item in verdict["facts"]}
    return {
        "id": case["id"],
        "recall": j.recall(facts, verdict),
        "recall_askable": j.recall(facts, verdict, only_askable=True),
        "facts": len(facts),
        "missed_facts": [f"{f['id']}: {f['fact']}" for f in facts if results.get(f["id"], "missed") == "missed"],
        "partly_facts": [f"{f['id']}: {f['fact']}" for f in facts if results.get(f["id"]) == "partly"],
        "app_wrong_facts": app_wrong,
        "simulation_wrong_facts": simulation_wrong,
        "unsupported": verdict["unsupported"],
        "dangerous": verdict["dangerous"],
        "sufficient": verdict["diagnostic_sufficiency"]["enough"],
        "sufficient_why": verdict["diagnostic_sufficiency"]["why"],
        "red_flags": j.score_red_flags(case, visit),
        "time": j.score_time(visit, chw.notes["confirmations"]),
        "suggestions_rejected": visit["run_info"]["suggestions_rejected"],
        "chw_notes": chw.notes,
    }


def percent(value):
    return "-" if value is None else f"{value * 100:.0f}%"


def overall(rows):
    done = [r for r in rows if "error" not in r]
    recalls = [r["recall"] for r in done if r["recall"] is not None]
    judged = [r for r in done if r["sufficient"] is not None]
    summary = {
        "cases": len(done),
        "recall": sum(recalls) / len(recalls) if recalls else None,
        "sufficiency": sum(1 for r in judged if r["sufficient"]) / len(judged) if judged else None,
        "wrong_facts": sum(len(r["app_wrong_facts"]) for r in done),
        "missed_must_catch": sum(len(r["red_flags"]["missed_emergent_or_immediate"]) for r in done),
        "false_alarm_cases": sum(1 for r in done if r["red_flags"]["false_alarms"]),
        "longest_visit": max((r["time"]["visit_minutes_estimate"] for r in done), default=0),
        "longest_ai": max((r["time"]["ai_minutes_phone_estimate"] for r in done), default=0),
    }
    return summary


def write_report(rows, summary, args, judge_name, cost, out_folder):
    lines = ["# Evaluation report", ""]
    lines.append(f"Run {time.strftime('%Y-%m-%d %H:%M')}. App: {'MedPsy ' + os.path.basename(args.model) if args.model else 'keyword (no AI)'}, "
                 f"intake {args.intake}, CHW {'accepts every suggestion' if args.accept_all else 'checks every suggestion with the patient'}. "
                 f"Patient: {'offline stand-in' if args.offline else args.patient_model}. Judge: {judge_name}.")
    if args.offline:
        lines.append("")
        lines.append("**Offline run: this only tests that the loop works. The scores are not real.**")
    if cost is not None:
        lines.append(f"Claude cost for this run: about ${cost} (estimate, see PRICES in claude_api.py).")
    lines.append("")

    n = summary["cases"]
    false_alarm_share = summary["false_alarm_cases"] / n if n else 0
    if n == 0:
        lines.append("**No case finished, so nothing was measured. See the errors below.**")
        lines.append("")
    checks = [
        ("Key-fact recall (average)", percent(summary["recall"]), "≥ 85%",
         summary["recall"] is not None and summary["recall"] >= TARGETS["recall"]),
        ("Diagnosis reachable", percent(summary["sufficiency"]), "≥ 80% of cases",
         summary["sufficiency"] is not None and summary["sufficiency"] >= TARGETS["sufficiency"]),
        ("Wrong facts caused by the app", str(summary["wrong_facts"]), "0", summary["wrong_facts"] == 0),
        ("Emergent/Immediate red flags missed", str(summary["missed_must_catch"]), "0", summary["missed_must_catch"] == 0),
        ("Cases with a false alarm", f"{summary['false_alarm_cases']} of {n}", "≤ 1 in 5",
         false_alarm_share <= TARGETS["false_alarm_cases"]),
        ("Longest visit (estimate)", f"{summary['longest_visit']} min", "< 20 min",
         summary["longest_visit"] < TARGETS["visit_minutes"]),
        ("Most AI time on the phone (estimate)", f"{summary['longest_ai']} min", "≤ 10 min",
         summary["longest_ai"] <= TARGETS["ai_minutes_phone"]),
    ]
    lines += ["## Against the targets", "", "| Metric | Result | Target | Met? |", "| --- | --- | --- | --- |"]
    if n == 0:
        checks = [(name, result, target, False) for name, result, target, met in checks]
    for name, result, target, met in checks:
        lines.append(f"| {name} | {result} | {target} | {'yes' if met else 'NO'} |")

    lines += ["", "## Per case", "",
              "| Case | Recall | Recall (askable facts) | Wrong facts | Diagnosis reachable | Red flags missed | False alarms | CHW inputs | AI min (phone est.) | Visit min (est.) |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['id']} | ERROR: {r['error']} | | | | | | | | |")
            continue
        t = r["time"]
        lines.append(f"| {r['id']} | {percent(r['recall'])} | {percent(r['recall_askable'])} | {len(r['app_wrong_facts'])} | "
                     f"{'-' if r['sufficient'] is None else ('yes' if r['sufficient'] else 'no')} | "
                     f"{', '.join(r['red_flags']['missed']) or '0'} | {', '.join(r['red_flags']['false_alarms']) or '0'} | "
                     f"{t['chw_inputs']} | {t['ai_minutes_phone_estimate']} | {t['visit_minutes_estimate']} |")

    for r in rows:
        if "error" in r:
            continue
        lines += ["", f"### {r['id']}", ""]
        lines.append(f"- Red flags expected: {', '.join(r['red_flags']['expected']) or 'none'}; "
                     f"raised: {', '.join(r['red_flags']['raised']) or 'none'}")
        if r["red_flags"]["possible"]:
            lines.append(f"- Possible red flags shown: {', '.join(r['red_flags']['possible'])}")
        lines.append(f"- Diagnosis reachable: {r['sufficient']} ({r['sufficient_why']})")
        for title, items in (("Missed facts", r["missed_facts"]), ("Partly captured", r["partly_facts"])):
            if items:
                lines.append(f"- {title}: " + "; ".join(items))
        for title, items in (("Wrong facts (app)", r["app_wrong_facts"]),
                             ("Wrong facts from the simulation (not counted)", r["simulation_wrong_facts"]),
                             ("Dangerous", r["dangerous"]), ("Unsupported (not counted)", r["unsupported"])):
            for item in items:
                lines.append(f"- {title}: {item['statement']} ({item['why']})")
        lines.append(f"- AI suggestions the CHW rejected: {r['suggestions_rejected']}; CHW notes: {r['chw_notes']}")

    lines += ["", f"Time estimates: {j.SECONDS_PER_QUESTION} s per CHW input, {j.SECONDS_PER_CONFIRMATION} s per y/n check, "
              f"plus laptop AI time × {j.PHONE_SLOWDOWN} (emulated phone, Nov 10). "
              "Recall: captured = 1, partly = 0.5. False alarm: an Urgent-or-higher red flag not expected for the case."]
    with open(os.path.join(out_folder, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return checks


def write_csv(rows, out_folder):
    with open(os.path.join(out_folder, "results.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["case", "recall", "recall_askable", "app_wrong_facts", "diagnosis_reachable",
                         "red_flags_missed", "false_alarms", "chw_inputs", "ai_seconds_laptop",
                         "ai_minutes_phone_estimate", "visit_minutes_estimate", "error"])
        for r in rows:
            if "error" in r:
                writer.writerow([r["id"]] + [""] * 10 + [r["error"]])
                continue
            t = r["time"]
            writer.writerow([r["id"], r["recall"], r["recall_askable"], len(r["app_wrong_facts"]), r["sufficient"],
                             ";".join(r["red_flags"]["missed"]), ";".join(r["red_flags"]["false_alarms"]),
                             t["chw_inputs"], t["ai_seconds_laptop"], t["ai_minutes_phone_estimate"],
                             t["visit_minutes_estimate"], ""])


def main():
    parser = argparse.ArgumentParser(description="Evaluation loop: simulated patient + app + judge")
    parser.add_argument("protocols", help="folder with the Intelehealth v2 JSON files")
    parser.add_argument("--model", help="MedPsy .gguf file for the app (leave out for the keyword app)")
    parser.add_argument("--cases", default="eval_cases.json")
    parser.add_argument("--facts", default="eval_key_facts.csv")
    parser.add_argument("--only", help="run only these cases, e.g. TC01,TC03")
    parser.add_argument("--intake", default="one", choices=["one", "group"])
    parser.add_argument("--accept-all", action="store_true", help="stress test: the CHW accepts every suggestion")
    parser.add_argument("--offline", action="store_true", help="no Claude: stand-in patient and judge (tests the loop only)")
    parser.add_argument("--patient-model", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    cases = load_cases(args.cases, args.only)
    facts = j.load_key_facts(args.facts)
    out_folder = args.out or os.path.join("eval_results", time.strftime("%Y-%m-%d_%H%M"))
    os.makedirs(out_folder, exist_ok=True)

    claude = None
    if args.offline:
        judge = j.WordJudge()
    else:
        import claude_api
        claude = claude_api.Claude()
        args.patient_model = args.patient_model or claude_api.PATIENT_MODEL
        judge = j.ClaudeJudge(claude, args.judge_model or claude_api.JUDGE_MODEL)
    mapper = make_mapper(args.model)

    rows = []
    for case in cases:
        print(f"\n=== {case['id']} ({case['complaint']}, {case['age']} {case['sex']}) ===")
        try:
            rows.append(run_case(case, facts.get(case["id"], []), args, mapper, claude, judge, out_folder))
        except Exception as error:   # one broken case must not stop the others
            print(f"   ERROR: {error}")
            rows.append({"id": case["id"], "error": str(error)})

    summary = overall(rows)
    cost = claude.cost() if claude else None
    checks = write_report(rows, summary, args, judge.name, cost, out_folder)
    write_csv(rows, out_folder)

    print("\n========== Against the targets ==========")
    if summary["cases"] == 0:
        print("   No case finished, so nothing was measured. Fix the ERROR above and run again.")
    for name, result, target, met in checks:
        print(f"   {'OK ' if met else 'NO '} {name}: {result} (target {target})")
    if args.offline:
        print("   (offline run: tests the loop only, scores are not real)")
    if cost is not None:
        print(f"   Claude cost: about ${cost}")
    print(f"\nFull report: {os.path.join(out_folder, 'report.md')}")


if __name__ == "__main__":
    main()
