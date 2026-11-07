import sys

from ai_mapper import AIMapper
from main import run_visit
from smoke_test import AutoConsole


# (what the patient says first, the patient's story). Headache is not in explanations.json, so '?' goes to the AI there.
VISITS = [
    ("my stomach pain", "Pain near my right ribs for 3 days, I vomited twice, no fever."),
    ("I have fever", "Fever for 4 days with chills, it comes and goes, and my body aches. No cough."),
    ("bad headache", "Throbbing headache on one side since yesterday, light hurts my eyes, I feel like vomiting."),
]

# Task names used in ai_mapper.py, grouped the way we report them.
GROUPS = {
    "match complaint": "complaint match",
    "map answer": "option mapping",
    "answer from story": "story check",
    "story with evidence": "story check",
    "value from story": "story check",
    "double-check": "yes/no check",
    "explain": "explain",
}
GROUP_ORDER = ["complaint match", "option mapping", "story check", "yes/no check", "explain"]


def empty_row():
    return {"calls": 0, "prompt_tokens": 0, "output_tokens": 0, "seconds": 0}


def add_up(timings):
    """Adds up calls, tokens and seconds for each group of AI tasks."""
    totals = {}
    for timing in timings:
        group = GROUPS.get(timing["task"], timing["task"])
        if group not in totals:
            totals[group] = empty_row()
        totals[group]["calls"] += 1
        totals[group]["prompt_tokens"] += timing["prompt_tokens"]
        totals[group]["output_tokens"] += timing["output_tokens"]
        totals[group]["seconds"] += timing["seconds"]
    return totals


def print_table(title, totals, visit_count=1):
    """Prints one row per group, then the total. With visit_count > 1 it prints the average per visit."""
    print(f"\n{title}")
    print(f"   {'task':16} {'AI calls':>9} {'prompt tokens':>14} {'output tokens':>14} {'AI seconds':>11}")
    groups = GROUP_ORDER + [group for group in totals if group not in GROUP_ORDER]
    everything = empty_row()
    for group in groups:
        row = totals.get(group, empty_row())
        for key in everything:
            everything[key] += row[key]
        print_row(group, row, visit_count)
    print_row("all", everything, visit_count)


def print_row(name, row, visit_count):
    print(f"   {name:16} {row['calls'] / visit_count:9.1f} {row['prompt_tokens'] / visit_count:14.0f} "
          f"{row['output_tokens'] / visit_count:14.0f} {row['seconds'] / visit_count:11.1f}")


def run(model_path, folder):
    print(f"\n========== {model_path.split('/')[-1]} ==========")
    mapper = AIMapper(model_path)
    all_visits = {}
    for number, (complaint_words, story) in enumerate(VISITS, start=1):
        mapper.timings = []
        console = AutoConsole(complaint_words, story)
        visit = run_visit(console, mapper, folder)
        totals = add_up(visit["run_info"]["ai_timings"])
        print_table(f"Visit {number}: {visit['chief_complaint']['protocol']} "
                    f"(\"{complaint_words}\")", totals)
        for group, row in totals.items():
            if group not in all_visits:
                all_visits[group] = empty_row()
            for key in row:
                all_visits[group][key] += row[key]
    print_table(f"Average per visit ({len(VISITS)} visits)", all_visits, len(VISITS))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python workload_report.py PROTOCOL_FOLDER MODEL.gguf [MODEL.gguf ...]")
        sys.exit(1)
    for model_path in sys.argv[2:]:
        run(model_path, sys.argv[1])
