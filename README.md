# Offline history-taking prototype (laptop version)

A Python prototype of the history-taking module. It runs in a terminal on a laptop, fully offline once the files are downloaded. The goal is to get the logic and the AI prompts right on a laptop first, then port them to Android.

## What it does

1. The CHW enters age and sex.
2. The CHW picks the main complaint by number, or types the patient's words and the AI suggests a match.
3. The CHW can type more of the patient's story in their own words.
4. The app walks the Intelehealth protocol one question at a time. For each question it:
   - checks whether the patient's story already answered it, and if so asks the CHW to confirm instead of asking again (AI only)
   - notices what the patient said "no" to and offers to save it as a "No" (works without AI too)
   - otherwise shows the options; the CHW types a number, or the patient's words for the AI to map
   - skips questions by age and sex, enforces required questions, and asks the follow-up questions under each answer
5. It runs past medical history and family history.
6. It shows a red-flag alert as soon as a danger sign is recorded, and a softer "possible red flag, please check" when a danger sign only came up next to a "no" or "not".
7. It prints a summary for the doctor (template, or an AI draft) with the physical-exam steps, and saves the visit as JSON.
8. Whenever the app is waiting for an answer, the CHW can type `?` to see plain-language explanations of the question and its medical-term options, or `?3` to explain option 3 (see "Simple explanations" below).

## Files

| File | Job |
|---|---|
| `main.py` | Runs one visit from start to finish and saves `visit.json` |
| `protocols.py` | Loads the Intelehealth JSON files, fixes the known label errors, and reads the rules (required, multi-choice, age and sex filters) |
| `intake.py` | The protocol walker: asks questions, follows branches, records answers |
| `keyword_mapper.py` | **No-AI baseline**: matches the patient's words to options by shared keywords |
| `ai_mapper.py` | **AI version**: MedPsy through llama.cpp, with constrained JSON output and thinking skipped |
| `negation.py` | **No-AI negation check**: finds what the patient said "no" to ("no fever", "I have not fainted") |
| `red_flags.py` | Red-flag rules (78) from the Intelehealth Clinical Treatment Guidelines and the WHO Interagency Integrated Triage Tool (IITT), each with a level and a page or chart section; also the red-flag follow-up questions |
| `summary.py` | Template summary (red flags listed most urgent first, with level and source), and a check that red flags appear in the AI summary |
| `explanations.py` | The `?` help: looks up `explanations.json`, falls back to the AI, and logs every AI explanation |
| `explanations.json` | Plain-language explanations of questions and medical terms, written or reviewed by the team |
| `explanation_log.jsonl` | Made when the app runs: every AI explanation, one per line, for the team to review |
| `smoke_test.py` | Runs a whole visit with automatic answers, so you can test without typing, and saves `smoke_visit.json` |
| `evaluate_mapping.py` | Compares baseline vs AI on the test set in `test_cases.csv` |
| `test_cases.csv` | Test phrases with expected answers; open it in Excel, and a clinician can fill in `checked_by` |
| `red_flag_cases.csv` | 82 test cases: complaint, age, patient words, picked options, and the red flags (and possible red flags) they should raise |
| `evaluate_explanations.py` | Asks a model to explain every word in `explanation_test_cases.csv` and saves the answers for a person to grade |
| `explanation_test_cases.csv` | 24 medical words from six protocols with the meaning we expect; a clinician can fill in `checked_by` |
| `workload_report.py` | Runs 3 automatic visits with a model (about half the option questions answered in words) and prints AI calls, tokens and seconds per visit, split by task |
| `explanation_results_<model>.csv` | Made by `evaluate_explanations.py`: the AI's sentence next to the expected meaning, with an empty `correct (y/n/partly)` column |

## Setup

```bash
# 1. Protocol files
git clone https://github.com/Intelehealth/intelehealth-ayu-protocols.git

# 2. llama.cpp for Python (only needed for the AI version)
pip install llama-cpp-python

# 3. A MedPsy model file (only needed for the AI version)
#    1.7B, 1.3 GB:  https://huggingface.co/qvac/MedPsy-1.7B-GGUF  (medpsy-1.7b-q4_k_m-imat.gguf)
#    4B,   2.7 GB:  https://huggingface.co/qvac/MedPsy-4B-GGUF    (medpsy-4b-q4_k_m-imat.gguf)
```

## Run it

```bash
PROTOCOLS="intelehealth-ayu-protocols/protocols/v2/All Protocols (JSON)"

# No-AI baseline
python main.py --protocols "$PROTOCOLS"

# AI version
python main.py --protocols "$PROTOCOLS" --model medpsy-4b-q4_k_m-imat.gguf

# Show questions in Hindi (the AI still works in English)
python main.py --protocols "$PROTOCOLS" --model medpsy-4b-q4_k_m-imat.gguf --language hi

# Quick tests (the smoke test also types "?" twice and "?2" once, and checks they are never saved)
python smoke_test.py "$PROTOCOLS"
python -c "import evaluate_mapping as e; e.check_red_flag_cases()"   # red-flag rules only, no AI needed
python evaluate_mapping.py "$PROTOCOLS" medpsy-1.7b-q4_k_m-imat.gguf medpsy-4b-q4_k_m-imat.gguf   # run from this folder; reads test_cases.csv
python evaluate_explanations.py medpsy-1.7b-q4_k_m-imat.gguf medpsy-4b-q4_k_m-imat.gguf          # reads explanation_test_cases.csv
python workload_report.py "$PROTOCOLS" medpsy-1.7b-q4_k_m-imat.gguf medpsy-4b-q4_k_m-imat.gguf   # AI work per visit
```

## How the main ideas show up in the code

**Protocols lead, AI assists.** `intake.py` decides every question from the protocol tree. The AI is only called in `ai_mapper.py` for three things: matching the complaint, mapping the patient's words to options, and checking whether the story already answered a question. It can also draft the summary, and explain a word the team hasn't explained yet when the CHW types `?`.

**Constrained decoding.** Each AI call passes a *grammar* to llama.cpp (`one_number_grammar`, and `YES_NO_GRAMMAR` for the double-check). The grammar only allows replies like `{"answer": 2}`, using 0 or an option number that actually exists for that question, so the model can't invent an answer. The app sends short numbers (1, 2, 3...) instead of the long Intelehealth IDs and converts back to the IDs afterwards. That keeps the reply to about 7–8 tokens.

**Skipping thinking.** `chat_prompt` ends with an empty `<think></think>` block (the prefill trick), so the model answers straight away.

**"Not mentioned" option.** When checking the story, option 0 means "the patient didn't mention this." This was added because the first version, which filled the whole form in one go, made up a lot of answers (see the results below).

**Best answer first, then "anything else?"** For every question the model may pick only ONE option (or 0). For a multi-choice question it is then asked again with the options it already picked listed as "Already recorded" and 0 meaning "Nothing else", up to 4 rounds. This replaced letting the model pick up to 3 numbers at once, which made it over-pick.

**Negation is plain code, not AI.** `negation.py` looks for words like *no, not, never, without, denies* and treats the next few words (up to 5, stopping at a comma, period, or *but*) as things the patient said no to. If the patient sounds unsure ("not sure", "don't know", "don't think", "maybe"), nothing counts as a no. "Can't" is not treated as a no, because "can't breathe" or "can't stop vomiting" describes a symptom. It is used in three places:
- **Guard:** if the AI picks an option the patient said no to, the pick is dropped before the CHW sees it.
- **Saving "No" answers:** on multi-choice questions, the CHW sees the patient's words and is asked "Patient said they do NOT have: Fever. Save as 'No'?" Only on "y" is it saved, with `"status": "said_no"`. It shows as "Fever: patient said NO" in the summary. Questions the patient never mentioned are not saved as "No"; they stay blank.
- **Red flags:** answers the CHW saved as "No" never raise a red flag. A danger sign that only appears inside a "no ..." phrase in the patient's words is NOT ignored: it is shown as a **possible** red flag ("please check with the patient"), because missing a real red flag is worse than a false alarm.

**Red flags are plain code, from two published sources.** Every rule in `red_flags.py` cites where it comes from, and the alert shows it, for example `IMMEDIATE: Suspected appendicitis (Guidelines p. 269)`. There are four levels, most urgent first:

| Level | Comes from |
|---|---|
| Emergent | IITT red ("move to high acuity area immediately") |
| Immediate | Intelehealth guidelines say "refer immediately" |
| Urgent | IITT yellow ("seen soon"), or the guidelines say "urgently" |
| Refer | The guidelines say "refer" with no urgency word |

Rules read the answers the protocols already collect (copying the protocol's own option wording), so covering all 52 complaints adds no questions. Rules can use the patient's age, because IITT has separate charts for age 12+ and under 12. Keywords wrapped in bars, like `| black |`, only match a whole answer. A "Yes" answer also carries its question (`chest indrawing: yes`), so Yes/No sub-questions can raise flags.

**Red-flag follow-up questions.** Some flags need one or two facts the protocol never asks. When such a rule fires, the app asks a few yes/no questions right away (`RED-FLAG CHECK: ...`), taken from the IITT red criteria: meningitis signs (stiff neck, confusion, seizure) after headache + fever, breathing distress after any breathing difficulty, shock signs after bleeding, and dehydration signs after diarrhoea or vomiting everything. A "yes" raises the level, and "don't know" counts as yes, so doubt never lowers it. Each question is asked once, only when its rule fires, and skipped if the visit already has the answer.

We say "said_no" rather than "absent" (which reads like "no answer") or "denied" (the Intelehealth history files use "Denied" to mean the patient *refused to answer*).

**CHW always confirms.** Every AI pick is shown as "Suggested: … Correct?" or "Patient already said: … Keep?". Nothing the AI suggests is saved without a yes.

**Simple explanations (`?` and `?N`).** Many CHWs don't know words like "Right Hypochondrium", "Epigastric" or "Syncope". Every option list (and the complaint list) ends with the hint line `(Type ? to explain the question, or ?3 to explain option 3.)`. Typed-value prompts end with a shorter hint, for example `Since when have you had this symptom? (duration) (? = explain):`.
- `?` explains the question, plus only the options that already have an entry in `explanations.json`. It works whenever the app is waiting for an answer: an option list, a typed value, a "Correct? / Keep? / Save as 'No'?" check, or the complaint list.
- `?N` (for example `?3`) explains just option N. It works on option lists and the complaint list. **This is the only way an option goes to the AI**, so the AI is called at most once for the question and once per option the CHW asks about.

Then the app asks the same question again. `?` and `?N` are never saved as answers.

Where each explanation comes from, in this order:

| Source | When | What the CHW sees |
|---|---|---|
| `explanations.json`, `checked_by` filled in | the word or question is in the file and a teammate checked it | the text, no label |
| `explanations.json`, `checked_by` empty | the word or question is in the file but nobody has checked it yet | the text + `(Draft – not checked yet)` |
| AI (MedPsy) | not in the file, and a model is loaded | one short sentence + `(AI explanation – not checked)` |
| nothing | not in the file and no model (keyword mode) | `No explanation available yet.` |

If a word is in the file, the AI is never called for it. The AI call (`AIMapper.explain`) has no grammar because it needs free text, but it is capped at 60 tokens and cut to the first sentence. The rules (`EXPLAIN_RULES`) tell the model to give the usual medical meaning of the word itself in everyday words, for someone with no medical training, and not to tie it to the patient's complaint unless the word is about that body part. They also say: no advice, no diagnosis guessing, one sentence only. Before the real word, the prompt shows 7 worked examples (`EXPLAIN_EXAMPLES` in `ai_mapper.py`) as earlier turns of the chat: 5 answer options (Epigastric, Hemoptysis, Tuberculosis, Postprandial, Intermittent) and 2 questions ("Nature of fever", "What aggravates the cough?"), each in the same message format as the real word, each answer starting with the same empty `<think></think>` prefill. To change the examples, edit that list. Each message starts with the chief complaint ("The patient's main complaint is Headache."); on the complaint list there is no complaint yet, so that line is left out. Each text is asked about once per visit.

`explanations.json` has two parts:

```
terms       {"Right Hypochondrium": {"text": "...", "checked_by": ""}, ...}   answer options
questions   {"Nature of fever": {"text": "...", "checked_by": ""}, ...}        question texts
```

Keys are matched without caring about capital letters, extra spaces, `*` or `[` `]`, so "Other [Describe]" and "Other[describe]" are the same. For labels like "Upper (R) - Right Hypochondrium", the part after " - " also works as the key. Use the English label exactly as the app shows it: the app shows an option's `text` from the protocol file, which is sometimes different from its `display` (for example the CHW sees "Postprandial", not "After eating"). Explanations are always looked up and shown in English, even with `--language hi`. An option with no entry is simply left out of the `?` list; the CHW can still ask about it with `?N`.

The file is pre-filled for the three pilot protocols (Abdominal Pain, Fever, Cough), for past medical history and family history (they are asked in every visit), and for the medical words in the complaint list (Syncope, Dyspepsia, Oedema, ...). **All of these were written by the AI assistant (Claude) and have `checked_by` empty**, so they show as drafts until a teammate checks them.

**Reviewing AI explanations.** Every AI explanation is saved in two places:
- `run_info["ai_explanations"]` in the visit record, and
- `explanation_log.jsonl` in this folder (one JSON object per line, added to on every run).

Each entry has `created`, `kind` ("question" or "term"), `term` (the word or question explained), `question` (the question it came from), `complaint` (the chief complaint, empty on the complaint list), `text`, `seconds` and `model`. The log file is in `.gitignore`, so it stays on the computer that made it; share it with the team when you review it. To review:

1. Open `explanation_log.jsonl` in a text editor (or `python -c "import json; [print(json.loads(l)['term'], '|', json.loads(l)['text']) for l in open('explanation_log.jsonl')]"`).
2. For a good explanation, copy it into `explanations.json` under `terms` (or `questions` if `kind` is "question"). Fix the wording if needed.
3. When a teammate has checked an entry, put their name in `checked_by`. Only then does it show without a label.
4. You can delete lines from the log once they are handled.

**What gets saved (the visit record).** The model never writes the record. Plain code builds `visit.json` from answers the CHW confirmed, so it can only contain real protocol IDs. The summary is made *from* this record, not the other way round. Format (`schema_version` "0.4"; 0.4 added `run_info["ai_explanations"]`):

```
schema_version, visit_id, created, synced
patient            {age, sex}
chief_complaint    {protocol, patient_words}
patient_story      the patient's own words, as typed
answers            one entry per answered/skipped question:
    section        "hpi" | "past_history" | "family_history"
    question_id, question
    answer_ids, answers, value
    status         "present" | "said_no" (patient said they don't have it) | "skipped" (CHW skipped an optional question)
    source         "tapped" | "keyword" | "ai" | "from story" | null for skipped
    patient_words
red_flags, possible_red_flags, physical_exam_steps
summary            {template, ai_draft}
run_info           not patient data: mapper, minutes, questions_asked, filled_from_story,
                   suggestions_accepted, suggestions_rejected, rejected_suggestions, ai_timings,
                   ai_explanations (new in 0.4)
```

`ai_explanations` lists every AI explanation shown after `?` or `?N` in this visit, one entry each with `created, kind, term, question, complaint, text, seconds, model` (the same entries as in `explanation_log.jsonl`). Explanations that came from `explanations.json` are not listed, because they are already in the file.

`rejected_suggestions` keeps every suggestion the CHW said "no" to (complaint match, mapped answer, story pre-fill, or "save as No"), so we can measure how often the AI is wrong in real use. `suggestions_accepted` counts the ones the CHW kept.

## Not done yet

- Red-flag rules are not clinician-checked yet, and some literal IITT rules will cause false alarms (any diarrhoea, any child's headache, and general weakness are Urgent).
- Red-flag gaps: chest pain with heart-attack features under 50, ectopic pregnancy unless pregnancy status is "Yes", bowel obstruction, and scorpion stings. Vital signs are not used.
- Negation only understands English words and simple patterns.
- Red-flag keywords still match phrases, so an unusual wording in the patient's own words can be missed. Answers picked from the protocol options are matched reliably.
- The red-flag follow-up questions are asked right away; they may move into the multi-question follow-up round later.
- No ROS checklist yet (waiting to hear from Intelehealth).
- Photo steps (`camera`) are skipped.
- The AI summary is only checked for red flags, not yet fact by fact.
- No real syncing; the visit file just has `"synced": false`.
- This is a laptop terminal app. The Android version comes next.
- Explanations are English only, even with --language hi.
- Simple explanations (`?`):
  - Every entry in `explanations.json` is an unchecked draft written by the AI assistant. A clinician or teammate needs to check them and fill in `checked_by`.
  - Only the three pilot protocols, past/family history and the complaint list are covered. In other protocols `?` usually explains only the question, and the CHW has to use `?N` for each option.
  - The AI still gets meanings wrong sometimes, especially the 1.7B (see "Explanation test" below: for example "Photophobia" became "like the room is spinning when it's bright outside"). This is why AI explanations are labeled and logged.
  - The results of `evaluate_explanations.py` have not been graded by a person yet.
  - No pictures yet. The Android version could show images from Intelehealth's `protocols/v2/physicalExamAssets` next to the explanation, for example `abdominalregions9.jpg` for the nine abdomen regions and `jaundiceexample.jpg` for Jaundice.

## First results (October 29, 2026)

These ran on a 2-core cloud computer, so the speeds are much slower than a good laptop and aren't phone speeds. The test phrases were written by us, not checked by a clinician, so treat them as early signals.

**1. Mapping the patient's words to one question's options** (`evaluate_mapping.py`, 18 phrases)

| Method | Correct | Time per answer (2-core CPU) |
|---|---|---|
| Keyword baseline (no AI) | 6/18 (33%) | instant |
| MedPsy-1.7B | 12–14/18 (67–78%) | ~2.3 s |
| MedPsy-4B | 12–13/18 (67–72%) | ~5.3 s |

- The AI understands everyday phrasing the baseline misses completely ("around my belly button" → Umbilical, "nothing comes out when I cough" → Dry).
- On multi-select questions, the 4B often picks **too many** options (for example, the right region plus a neighboring one). Most of its misses were this kind.
- Small wording changes in the prompt shifted the scores by 1–2 cases, so we need a bigger test set before trusting the numbers.
- Fixing the "Lower (R) - Left Illiac Fossa" label error helped: after the fix, 1.7B got "lower left side" right.

**2. Filling several questions from one story** ("one sentence fills many questions")
- First try: one prompt that filled the whole form at once. **Both models made up many answers** (smoking, medications, treatments the patient never mentioned). We dropped this approach.
- Current approach: check the story **one question at a time**, with an explicit "0 = not mentioned" option. The 4B was much better at saying "not mentioned," but it still over-picks on multi-select questions, and once it picked "Fever" when the patient said "no fever."
- In a full test visit, 6 of 12 complaint questions were pre-filled from one sentence, but some of those suggestions were wrong. **CHW confirmation is essential**, and we should measure confirmed vs rejected suggestions.

**3. AI-written summary: not safe yet**
The 4B summary **invented facts**: exam findings that were never done, "no allergies" when the patient had allergies, and a possible diagnosis. It also leaked some of its thinking text. So the app now uses the **template summary by default**, and the AI draft only appears with `--ai-summary`, clearly labeled. This matches our plan to keep summaries checkable.

**4. Speed**
A full test visit took about 3.5 minutes of AI time on the 2-core computer, around 5 s per AI step with the 4B. We still need to measure real phone speed.

## Second results (October 29, 2026): negation and over-picking fixes

Same 2-core cloud computer. The test set grew from 18 to **57 cases** (`test_cases.csv`): 35 "map these words to this question" cases and 22 "did the patient's story already answer this?" cases, including multi-answer and "no ..." phrases. The first 18 are our own phrases from the first session; the 39 new ones were written by the AI assistant (Claude) during this session. None come from real patients, and **no clinician has checked them**, so the scores are likely optimistic.

**What changed in the code**
1. `negation.py` (no AI) finds what the patient said "no" to. AI picks that contradict it are dropped, and the CHW is offered to record them as absent (renamed "said_no" in the evening, see below).
2. The model picks **one** best option at a time instead of up to three at once.
3. For multi-choice questions it is then asked "anything else?" (0 = nothing else), and any extra pick has to pass a separate **yes/no double-check** ("Did the patient clearly say *Eye pain*?").

**Results on the 57 cases**

| Version | Model | Correct (words) | Correct (story) | Extra picks | Missed picks | Picked something the patient said NO to | AI calls | Avg s / call |
|---|---|---|---|---|---|---|---|---|
| Keyword baseline | none | 11/35 | 8/22 | 9 | 38 | 0 | 0 | – |
| Old (pick up to 3 at once) | 1.7B | 19/35 | 8/22 | 34 | 17 | 2 | 57 | 2.6 |
| Old (pick up to 3 at once) | 4B | 19/35 | 9/22 | 44 | 8 | 3 | 57 | 6.4 |
| Best first + "anything else?" | 1.7B | 22/35 | 12/22 | 26 | 5 | 0 | 108 | 2.5 |
| Best first + "anything else?" | 4B | 27/35 | 16/22 | 23 | 3 | 0 | 112 | 5.8 |
| **+ double-check extra picks (kept)** | **1.7B** | **28/35** | **15/22** | **8** | **9** | **0** | **109** | **2.6** |
| **+ double-check extra picks (kept)** | **4B** | **28/35** | **17/22** | **5** | **10** | **0** | **107** | **6.0** |
| + double-check every story pick too | 1.7B | 28/35 | 15/22 | 4 | 14 | 0 | 121 | 2.8 |
| + double-check every story pick too | 4B | 28/35 | 12/22 | 2 | 18 | 0 | 115 | 6.3 |

**What we learned**
- Asking for one best answer, then "anything else?", fixed most of the 4B's over-picking. The extra rounds still picked neighbors (the next abdominal region, "Nausea" after "Vomiting") until we added the yes/no double-check.
- Double-checking *every* story pick went too far: the model said "no" to correct answers written in medical words (it rejected "Right Hypochondrium" for "near my right ribs"). So only the extra picks are double-checked.
- After the negation guard, neither model ever suggested something the patient said "no" to (was 2–3 times before).
- The **1.7B is now about as accurate as the 4B at less than half the time per call**, which matters for phones.
- The negation code found the right "no" answers in 33/33 multi-choice cases, but we wrote those cases together with the rules, so this number is optimistic. It also misses synonyms ("no stomach pain" doesn't match "Abdominal pain") and only reads English.
- The main remaining error: on single-choice questions the story never mentioned (severity, nature of fever), the model sometimes still fills in an answer ("Moderate"). The CHW has to reject these, so we should count how often that happens with real users.
- The red-flag check used to search the raw words, so "chest pain, no shortness of breath" raised the breathlessness alert. At this point we made it ignore "no ..." phrases and absent answers; that turned out to hide real red flags and was changed in the evening (see below).

**What to improve next**
- Get the test set checked by a clinician (`checked_by` column) and grow it from Intelehealth's case histories
- Stop invented answers on single-choice story questions (for example, only pre-fill single-choice questions when the double-check also says yes)
- Hindi / Hinglish negation words in `negation.py`, once we know how CHWs type
- Port to Android and measure on a real mid-range phone

## Fixes after review (October 29, 2026, evening)

- **"absent" renamed to "said_no".** "Absent" read like "no answer". The CHW prompt now shows the patient's words and asks "Save as 'No'?". The summary shows the patient's own words near the top. Record `schema_version` is now 0.3.
- **Unsure is not a no.** "not sure if I have chills" used to be offered as "No chills". Now "not sure", "don't know", "don't think" and "maybe" stop the negation.
- **"Can't" removed from the negation words.** With it, "I can't stop vomiting blood" raised NO red flag, because the words after "can't" were thrown away. That was a dangerous miss introduced earlier the same day.
- **Red flags now err toward alerting.** Danger signs inside "no ..." phrases are shown as *possible* red flags instead of being dropped. Answers the CHW saved as "No" still never alert.
- **New tests:** 8 negation-only cases in `test_cases.csv` (mode `negation`) and 10 cases in `red_flag_cases.csv`. Results: "said no" found correctly in 41/41 multi-choice cases; red flags 9/10 (the miss is the placeholder rule gap above). These were also written by the AI assistant and are not clinician-checked.
- The AI scores above are unchanged: the negation change gives the same result on every option of the 57 earlier cases.
- **Possible red flags go away once the CHW saves the matching "No".** `red_flags.check()` drops a possible red flag when the complaint name plus the labels saved as "No" match the same rule (for example "Chest Discomfort or Pain" + "Difficulty breathing"). Real red flags are never hidden. `intake.py` cleans its list after every answer, so the summary and `possible_red_flags` in the record only list flags that are still open. `red_flag_cases.csv` has a new `said_no_labels` column and 3 new cases (12/13 pass; the miss is the same placeholder rule gap).
- **Story answers no longer get cut short.** `value_from_story()` now allows up to 150 characters (apostrophes too, but never `"` or `\`, so the reply stays valid JSON). A plain-code check then throws the answer away (treated as "not mentioned") if fewer than half of its words are the patient's own words.

## Story check results (October 29, 2026, night)

**The problem.** When the patient's story never talked about a single-choice question (severity, nature of fever), the model often still picked an answer. Only the *extra* picks on multi-choice questions were double-checked.

**What changed**
- `protocols.story_prefill_allowed()`: questions whose text says "severe" or "severity" are never pre-filled from the story; they are always asked. The words are in `NO_STORY_PREFILL_WORDS`. `evaluate_mapping.py` uses the same rule.
- `AIMapper(story_check=...)` adds an optional check on the first pick of single-choice story questions. Multi-choice questions and typed answers are unchanged. The default is `"yes_no"` (chosen after the results below); `"off"` gives the old behavior. Choose it with `--story-check` in `main.py` and `evaluate_mapping.py`, or as the third argument of `smoke_test.py`.
  - `yes_no`: reuses the existing yes/no double-check (`patient_clearly_said`).
  - `evidence`: the model must quote the patient's words, and plain code keeps the pick only if the quote really is in the story.
- 25 new `story` rows in `test_cases.csv`, all on single-choice questions: 15 where the story does not mention the topic, 10 where it clearly does. They were **written by the AI assistant (Claude) and are not clinician-checked**. There are now 47 story cases: 23 with "none" expected, 24 with an answer.
- New number in the report: **invented answers** (story cases with "none" expected where something was picked).

**Results** (65 answer + story cases; run on an Apple M5 laptop with 10 CPU cores and 16 GB, CPU only, so the speeds are not comparable with the 2-core cloud numbers above)

| Story check | Model | Correct (words) | Correct (story) | Extra picks | Missed picks | Invented answers | Picked something the patient said NO to | AI calls | Avg s / call |
|---|---|---|---|---|---|---|---|---|---|
| none (keyword baseline) | none | 11/35 | 23/47 | 9 | 48 | 0 | 0 | 0 | – |
| off | 1.7B | 28/35 | 33/47 | 15 | 10 | 11 | 0 | 128 | 0.6 |
| off | 4B | 28/35 | 41/47 | 6 | 12 | 1 | 0 | 128 | 1.5 |
| yes_no | 1.7B | 28/35 | 38/47 | 4 | 16 | **0** | 0 | 154 | 0.8 |
| yes_no | 4B | 28/35 | 35/47 | 2 | 19 | **0** | 0 | 145 | 1.9 |
| evidence | 1.7B | 28/35 | 30/47 | 9 | 19 | 5 | 0 | 128 | 1.0 |
| evidence | 4B | 28/35 | 38/47 | 9 | 13 | 3 | 0 | 128 | 2.1 |

The baseline's "story" score went up from 8/22 because it never picks anything, and most new story cases expect "none".

**What we learned**
- `yes_no` stopped every invented answer on both models. The price is correct answers it rejected (the question is then asked normally): 6 on the 1.7B and 7 on the 4B. Examples: "Wet" from "a lot of yellow phlegm", "Irregular" from "comes and goes", "No" from "I don't smoke".
- `evidence` did not work well. The quote only proves the words are in the story, not that they support the answer ("chills and weakness" was accepted as evidence for "Irregular (comes & goes)"). The 1.7B also lost good answers by writing `Patient said '...'` around its quote, or "sudden" when the story said "suddenly".
- The 4B with `off` already invents very little (1/23). The 1.7B with `off` invents a lot (11/23), so the check matters most for the small model we want on phones.

**`value_from_story()` test** (`check_value_from_story.py`: 17 cases, 11 where the story does not answer the question). `mostly_from_story()` now skips words of 3 letters or fewer, but always counts numbers.

| Model | Invented answers that got through | Stopped by the model ("not mentioned") | Stopped by the word check | Good answers kept |
|---|---|---|---|---|
| 1.7B | 1 ("Additional information" + story "Fever" gave "Fever") | 9 | 1 ("since yesterday" for a story with no time) | 6/6 |
| 4B | 0 | 11 | 0 | 6/6 |

## Explanation test (November 7, 2026)

**What changed.** New rules for `AIMapper.explain()`: give the usual medical meaning of the word itself, and don't tie it to the complaint unless the word is about that body part. Worked examples are now shown to the model before the real word (`EXPLAIN_EXAMPLES`). In our earlier hand test, the new rules and 5 option examples cut wrong explanations on the 1.7B from 5/24 to 2/24 and made them faster. Then, because all 5 were answer options and most mistakes were on question words, we added 2 question examples ("Nature of fever", "What aggravates the cough?").

**Test set.** `explanation_test_cases.csv` has 24 words that are not in `explanations.json`, from the Headache, Dizziness & Vertigo, Palpitations, Red or painful eye, Urine disturbance and Skin disorder protocols: 19 answer options and 5 questions (Paresthesia, Atopic dermatitis, Voiding difficulty, Provocative factors, Migratory). Phonophobia is not in the v2 Headache protocol (only in v3 Vomiting); it is listed under Headache so we can keep checking the old mistake. The expected meanings were **written by the AI assistant (Claude) and are not clinician-checked** (`checked_by` is empty).

**Speed** (Apple M5 laptop, 10 CPU cores, CPU only, one model at a time)

| Model | Examples | 24 words took | Average per word | Slowest word |
|---|---|---|---|---|
| MedPsy-1.7B | 5 options | 9.8 s | 0.41 s | 1.61 s |
| MedPsy-1.7B | 5 options + 2 questions | 10.4 s | 0.43 s | 2.00 s |
| MedPsy-4B | 5 options | 22.9 s | 0.95 s | 4.36 s |
| MedPsy-4B | 5 options + 2 questions | 24.0 s | 1.00 s | 6.24 s |

The slowest word is always the first one: the model reads the rules and the examples once, and llama.cpp reuses that part of the prompt for the next words. In the app, other AI calls happen between explanations, so each `?N` will usually be closer to the first-word time. The 2 extra examples made that first word about 0.4 s (1.7B) and 1.9 s (4B) slower.

**Correctness: not graded yet.** The answers from the latest run (7 examples) are in `explanation_results_medpsy-1.7b-q4_k_m-imat.csv` and `explanation_results_medpsy-4b-q4_k_m-imat.csv`; the 5-example answers are in the git history. A person should fill in `correct (y/n/partly)`. A first look (by Claude, not a grade):
- **Question words, 1.7B:** the question examples helped. Paresthesia and Atopic dermatitis are now explained as questions ("Asks about tingling, numbness, or pins and needles..."; before, Atopic dermatitis got a question back instead of an explanation). Voiding difficulty is still wrong ("trouble getting or staying in the bathroom"), Migratory is still tied to a rash instead of joint pain, and Provocative factors went from "happen or get worse" to "happen or get better".
- **Option words, 1.7B:** they changed too, because the prompt changed. Terminal dribbling is now right ("at the very end of urinating") and Metallic taste lost "cleaned with bleach", but Double vision got worse ("seeing two things that aren't there"). Photophobia is still wrong ("like the room is spinning") and Gonorrhoea is still tied to the eye.
- **4B:** mostly right both times. Still off: Provocative factors ("better or worse"), Migratory (rash), and Transient got worse ("goes away and comes back").
- Phonophobia is no longer "fear of loud sounds" on either model.

## Workload per visit (November 7, 2026)

`workload_report.py` runs 3 automatic visits: Abdominal Pain ("my stomach pain"), Fever ("I have fever") and Headache ("bad headache"), each with a short story. It uses its own `WordsConsole`, which answers like `smoke_test.py`'s `AutoConsole` (including `?` twice and `?2` once), except that about half of the option questions are answered with the patient's words from the `PATIENT_WORDS` list ("near my right ribs", "it comes and goes", "nausea and vomiting", ...). If the AI can't match the words, the question comes back and the console picks a number, like a CHW would. It adds up `run_info["ai_timings"]` by task. Apple M5 laptop, 10 CPU cores, CPU only, one model at a time.

**Average per visit, by task**

| Task | 1.7B calls | 1.7B prompt tokens | 1.7B output tokens | 1.7B seconds | 4B calls | 4B prompt tokens | 4B output tokens | 4B seconds |
|---|---|---|---|---|---|---|---|---|
| Complaint match | 1.0 | 511 | 7 | 1.6 | 1.0 | 511 | 7 | 4.1 |
| Option mapping | 12.0 | 1951 | 72 | 5.3 | 12.3 | 2005 | 74 | 12.6 |
| Story check | 13.3 | 2593 | 90 | 8.2 | 12.0 | 2320 | 91 | 18.0 |
| Yes/no check | 4.7 | 579 | 28 | 2.4 | 3.3 | 382 | 20 | 3.7 |
| Explain | 1.3 | 833 | 20 | 2.9 | 1.3 | 836 | 16 | 6.2 |
| **All** | **32.3** | **6466** | **217** | **20.4** | **30.0** | **6053** | **208** | **44.6** |

**Each visit**

| Visit | Model | Option questions in words (AI matched) | AI calls | Prompt tokens | Output tokens | AI seconds |
|---|---|---|---|---|---|---|
| Abdominal Pain | 1.7B | 9 of 17 (6) | 38 | 7036 | 241 | 21.1 |
| Fever | 1.7B | 7 of 18 (4) | 23 | 4824 | 153 | 14.0 |
| Headache | 1.7B | 10 of 20 (7) | 36 | 7539 | 257 | 26.0 |
| Abdominal Pain | 4B | 10 of 20 (7) | 35 | 6847 | 239 | 50.9 |
| Fever | 4B | 7 of 19 (4) | 21 | 4051 | 147 | 27.6 |
| Headache | 4B | 10 of 20 (7) | 34 | 7261 | 238 | 55.4 |

- Typing words instead of numbers added about 12 option-mapping calls per visit. Each typed answer takes one call, plus one for every "anything else?" round on multi-choice questions. The whole visit went from 20 to 32 AI calls (1.7B) and from 16 to 30 (4B), and from 14 to 20 s (1.7B) and 28 to 45 s (4B) of AI time.
- Option mapping and the story check now cost about the same. The 4B takes a bit more than twice as long as the 1.7B for the same work.
- Both models matched about two thirds of the typed answers (17 of 26 on the 1.7B, 18 of 27 on the 4B). The rest were "not sure", so the console picked a number. Some misses are our phrases not fitting the options (for example "I have sugar disease" for diabetes), so this is not a mapping accuracy score: `evaluate_mapping.py` is for that.
- The number of option questions differs between the models because the story pre-fills different questions, and pre-filled questions are not asked.
- Explain calls are few (most Abdominal Pain and Fever words are in `explanations.json`), but each one costs about 620 prompt tokens because of the 7 worked examples. On Headache, which has no entries in the file, all 3 went to the AI.
- The AI summary (`--ai-summary`) was not turned on, so it is not counted.
- Seconds are not simply proportional to tokens: llama.cpp reuses the start of the prompt when it matches the previous call.

## Red-flag rules from the guidelines and WHO IITT (November 9 to 12, 2026)

- **Placeholder rules replaced** with 78 rules from two sources: the Intelehealth *Clinical Treatment Guidelines for Telemedicine Doctors* (shared by Dr. Verma) and the WHO / ICRC / MSF *Interagency Integrated Triage Tool* (age 12+ chart, age under 12 chart, reference card). IITT replaces ETAT, because it covers adults too.
- **All 52 complaints checked.** Every answer option in the 52 protocols was compared with the danger signs in both sources. 49 complaints can now raise at least one flag from their own answers. Follow up visit, Other and Weight gain have no danger-sign answers, so only the general rules (convulsions, unresponsive, severe pain, and so on) apply there.
- **Levels follow the source wording literally**, even where it looks low (vomiting blood is "Refer" in the guidelines) or high. When a guideline section uses two words ("urgently" and "immediately" for pneumonia), the stronger one is used. One planned exception: IITT makes headache + fever red; we made it Urgent plus the meningitis follow-up questions, so every case is still flagged but Emergent is kept for real danger signs.
- **Left out on purpose:** routine "refer all" cases that are not danger signs (dental caries, chronic ear discharge, osteoarthritis), and "no response to treatment in X days", which can't be known at a first visit.
- **Bugs fixed while testing:** "ill-fitting" (clothes) matched the seizure word "fitting"; "clear discharge" (eye) matched "ear discharge"; and a "No" to "Does the child make a wheezing sound?" put "wheezing" in the text. Keywords can now match whole answers only, and only "Yes" answers carry their question.
- **Code changes:** `intake.py` saves which question a Yes/No answer belongs to, passes the patient's age to the red-flag check, and asks the follow-up questions. `summary.py` lists flags most urgent first with level and source. `evaluate_mapping.py` reads two new optional columns in `red_flag_cases.csv`: `age` and `answer_labels` (options the CHW picked, with `Question=Answer` for Yes/No sub-questions).
- **Results:** 82/82 red-flag cases pass, including cases that should NOT raise a flag and cases that show known gaps. Full scripted visits checked every follow-up path (no, yes, don't know). These cases were drafted with an AI assistant and are not clinician-checked; the expected red flags for the teaching-case evaluation should be labeled by someone who has not seen the rules.