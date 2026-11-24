"""Makes the hand-check sheet: 100 targets (50 for Lia, 50 for Morrison) with the patient sentence and the answer we will train on."""
import json
import os
import random

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

SEED = 6
HERE = os.path.dirname(os.path.abspath(__file__))
targets = [json.loads(line) for line in open(os.path.join(HERE, "targets.jsonl"), encoding="utf-8")]
sentences = {}
for line in open(os.path.join(HERE, "sentences.jsonl"), encoding="utf-8"):
    row = json.loads(line)
    sentences[row["id"]] = row["text"]
targets = [t for t in targets if t["id"] in sentences]

rng = random.Random(SEED)
by_kind = {}
for t in targets:
    by_kind.setdefault(t["kind"], []).append(t)
picked = []
for kind, group in sorted(by_kind.items()):
    share = round(100 * len(group) / len(targets))
    picked.extend(rng.sample(group, min(share, len(group))))
picked = picked[:100]
rng.shuffle(picked)


def answer_text(t):
    if not t["expected"]:
        return "0 = nothing matches / not clear (the app should NOT pick any option)"
    return " AND ".join(t["options"][i] for i in t["expected"])


def denied_text(t):
    return ", ".join(t["options"][i] for i in t["denies"])


bold = Font(name="Arial", bold=True, color="FFFFFF")
normal = Font(name="Arial")
head_fill = PatternFill("solid", fgColor="1F4E79")
input_fill = PatternFill("solid", fgColor="FFF2CC")
wrap = Alignment(wrap_text=True, vertical="top")

book = Workbook()
guide = book.active
guide.title = "How to check"
lines = [
    "Fine-tuning data check (Group 6)",
    "",
    "Each row is one training example. The patient's words were written for a chosen correct answer.",
    "Please read the question, the options and what the patient said, then decide:",
    "  Y = the 'Correct answer' column is right, and the patient's words do NOT also point to another option",
    "  N = the answer is wrong, or the words are unclear, or they also point to another option",
    "If you put N, write what is wrong in the Comment column (or a better sentence).",
    "",
    "Only fill in the yellow columns. About 15-20 minutes for 50 rows.",
    "Rows marked 'story' are the patient's opening story: the answer can be hidden among other details.",
    "'0 = nothing matches' rows are on purpose: the patient was vague, or only said what they do NOT have.",
]
for number, text in enumerate(lines, start=1):
    guide.cell(row=number, column=1, value=text).font = Font(name="Arial", bold=(number == 1), size=14 if number == 1 else 11)
guide.column_dimensions["A"].width = 110

headers = ["#", "ID", "Complaint", "Question", "Options", "Patient said", "Correct answer", "Patient said NO to",
           "Story?", "OK? (Y/N)", "Comment"]
widths = [4, 7, 18, 30, 40, 45, 28, 22, 7, 10, 30]
for name, rows in (("Lia", picked[:50]), ("Morrison", picked[50:])):
    sheet = book.create_sheet(name)
    for column, (header, width) in enumerate(zip(headers, widths), start=1):
        cell = sheet.cell(row=1, column=column, value=header)
        cell.font, cell.fill, cell.alignment = bold, head_fill, wrap
        sheet.column_dimensions[cell.column_letter].width = width
    check = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
    sheet.add_data_validation(check)
    for number, t in enumerate(rows, start=1):
        options = "\n".join(f"{i + 1}. {label}" for i, label in enumerate(t["options"]))
        values = [number, t["id"], t["complaint"], t["question"], options, sentences[t["id"]], answer_text(t),
                  denied_text(t), "story" if t["story"] else "", "", ""]
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=number + 1, column=column, value=value)
            cell.font, cell.alignment = normal, wrap
        for column in (10, 11):
            sheet.cell(row=number + 1, column=column).fill = input_fill
        check.add(f"J{number + 1}")
    sheet.freeze_panes = "A2"
    total_row = len(rows) + 3
    sheet.cell(row=total_row, column=9, value="Y count").font = Font(name="Arial", bold=True)
    sheet.cell(row=total_row, column=10, value=f'=COUNTIF(J2:J{len(rows) + 1},"Y")').font = normal
    sheet.cell(row=total_row + 1, column=9, value="N count").font = Font(name="Arial", bold=True)
    sheet.cell(row=total_row + 1, column=10, value=f'=COUNTIF(J2:J{len(rows) + 1},"N")').font = normal

book.save(os.path.join(HERE, "Group6_Finetune_Data_Check.xlsx"))
kinds = {}
for t in picked:
    kinds[t["kind"]] = kinds.get(t["kind"], 0) + 1
print(len(picked), kinds)
