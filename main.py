import argparse
import json
import time
import uuid

import protocols as p
import summary
from intake import Console, Intake, parse_numbers
from keyword_mapper import KeywordMapper


SCHEMA_VERSION = "0.3"


def ask_patient(console):
    while True:
        age = console.ask("Patient age (years):")
        if age.replace(".", "", 1).isdigit():
            break
    while True:
        sex = console.ask("Patient sex (female/male):").lower()
        if sex in ("female", "male", "f", "m"):
            sex = "female" if sex.startswith("f") else "male"
            break
    return {"age": float(age), "sex": sex}


def pick_complaint(console, mapper, complaint_names, rejected):
    console.show("")
    console.show("Main complaint:")
    for number, name in enumerate(complaint_names, start=1):
        console.show(f"   {number}. {name}")
    while True:
        reply = console.ask("Number, or type the patient's words:")
        picked = parse_numbers(reply, len(complaint_names))
        if picked:
            return complaint_names[picked[0]], None
        result = mapper.match_complaint(complaint_names, reply)
        if result["unclear"] or not result["indexes"]:
            console.show("   Not sure. Please pick a number.")
            continue
        name = complaint_names[result["indexes"][0]]
        if console.ask(f"   Suggested: {name}. Correct? (y/n)").lower() in ("y", "yes"):
            return name, reply
        rejected.append({
            "section": "chief_complaint",
            "question_id": None,
            "question": "Main complaint",
            "suggested_ids": [],
            "suggested": [name],
            "value": None,
            "kind": "match complaint",
            "patient_words": reply,
        })


def run_visit(console, mapper, protocol_folder, language="en", ai_summary=False):
    started = time.time()
    patient = ask_patient(console)
    intake = Intake(patient, mapper, console, language)

    complaint_names = p.list_complaints(protocol_folder)
    complaint, first_words = pick_complaint(console, mapper, complaint_names, intake.rejected)
    intake.complaint = complaint
    protocol = p.load_protocol(protocol_folder, complaint)

    more = console.ask("\nIn the patient's own words, tell me more about the problem (Enter to skip):")
    intake.story = " ".join(part for part in (first_words, more) if part)

    console.show(f"\n--- {complaint} ---")
    intake.run_section(protocol, "hpi", use_story=True)

    console.show("\n--- Past medical history ---")
    intake.run_section(p.load_protocol(protocol_folder, "patHist"), "past_history")
    console.show("\n--- Family history ---")
    intake.run_section(p.load_protocol(protocol_folder, "famHist"), "family_history")

    exam_steps = p.physical_exam_steps(protocol)
    text = summary.template_summary(patient, complaint, intake.answers, intake.alerts,
                                    intake.possible_alerts, exam_steps, intake.story)

    ai_text = mapper.write_summary(text) if ai_summary else None
    if ai_text:
        missing = summary.missing_red_flags(ai_text, intake.alerts)
        if missing:
            ai_text = "RED FLAGS: " + "; ".join(missing) + "\n" + ai_text

    console.show("\n========== SUMMARY FOR THE DOCTOR ==========")
    console.show(text)
    if ai_text:
        console.show("\n---------- AI draft (experimental, CHW must check every line) ----------")
        console.show(ai_text)

    accepted_suggestions = 0
    if first_words:
        accepted_suggestions += 1
    for answer in intake.answers:
        if answer["source"] in (mapper.name, "from story"):
            accepted_suggestions += 1

    visit = {
        "schema_version": SCHEMA_VERSION,
        "visit_id": str(uuid.uuid4()),
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "patient": patient,
        "chief_complaint": {
            "protocol": complaint,
            "patient_words": first_words,
        },
        "patient_story": intake.story,
        "answers": intake.answers,
        "red_flags": intake.alerts,
        "possible_red_flags": intake.possible_alerts,
        "physical_exam_steps": exam_steps,
        "summary": {
            "template": text,
            "ai_draft": ai_text,
        },
        "synced": False,
        "run_info": {
            "mapper": mapper.name,
            "minutes": round((time.time() - started) / 60, 2),
            "questions_asked": intake.questions_asked,
            "filled_from_story": intake.filled_from_story,
            "suggestions_accepted": accepted_suggestions,
            "suggestions_rejected": len(intake.rejected),
            "rejected_suggestions": intake.rejected,
            "ai_timings": getattr(mapper, "timings", []),
        },
    }
    return visit


def main():
    parser = argparse.ArgumentParser(description="Offline history-taking prototype")
    parser.add_argument("--protocols", required=True, help="folder with the Intelehealth v2 JSON files")
    parser.add_argument("--model", help="path to a MedPsy .gguf file (leave out for the no-AI baseline)")
    parser.add_argument("--language", default="en", help="display language, e.g. hi, bn, mr")
    parser.add_argument("--ai-summary", action="store_true",
                        help="also print an AI-written summary draft (experimental - see README)")
    parser.add_argument("--story-check", default="yes_no", choices=["off", "yes_no", "evidence"],
                        help="extra check on single-choice answers taken from the story (AI only)")
    parser.add_argument("--out", default="visit.json")
    args = parser.parse_args()

    if args.model:
        from ai_mapper import AIMapper
        mapper = AIMapper(args.model, story_check=args.story_check)
    else:
        mapper = KeywordMapper()

    visit = run_visit(Console(), mapper, args.protocols, args.language, args.ai_summary)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(visit, f, indent=2, ensure_ascii=False)
    print(f"\nSaved visit to {args.out}")


if __name__ == "__main__":
    main()
