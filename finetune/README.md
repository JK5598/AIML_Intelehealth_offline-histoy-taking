# Fine-tuning MedPsy-1.7B (final project: trained and evaluated model)

## What we train, and why

The app uses MedPsy for one main job: **turn what the patient said into an option on the protocol form**.
It does this in small steps, and each step must answer with only `{"answer": N}` or `{"answer": "yes"/"no"}`:

| Step | Prompt rules in `ai_mapper.py` | The model answers |
|---|---|---|
| first pick | `ANSWER_RULES` (CHW typed the answer) or `STORY_RULES` (patient's opening story) | the best option, or 0 |
| "anything else?" | same rules, with "Already recorded: ..." | another option, or 0 "Nothing else" |
| double-check | `CHECK_RULES` | "yes" if the patient clearly said it |

Our tests showed where the original model goes wrong: it **rejects correct story answers** at the double-check
(the patient said "the pain is there all the time", the proposed answer is "Constant", the model says "no"),
and it sometimes **picks an option for a question the patient never talked about**. That is what we train.

We train a small LoRA adapter (about 1% of the weights) on the app's exact prompts. Nothing else in the app changes:
same prompts, same grammar, same 4-bit size on the phone.

## The data

Labels first, words second, so every label is known by design:

1. `make_targets.py` takes real questions from the Intelehealth protocols (at most 10 per complaint, 674 found)
   and **chooses the correct answer before any patient words exist**: one option, two options, an option plus
   one the patient denies, only denials, a plain "no", or a vague answer that matches nothing. 473 targets.
2. Claude (the AI assistant) wrote one patient sentence for each target, in everyday words, usually *not* copying
   the option label. 30% are longer "opening stories" with the answer hidden among other details.
   463 sentences kept (10 odd protocol items skipped). File: `sentences.jsonl`.
3. `build_examples.py` runs the **app's own `AIMapper` code** with a "teacher" in place of the model, so the prompts
   are exactly what the app sends. Each sentence becomes several examples: map mode, story mode, the yes/no
   double-check (right answers get "yes", one wrong option gets "no"), and the same words checked against a
   question the patient never talked about (answer 0, "Not mentioned").
4. `make_keep_prompts.py` makes 120 "explain this word" prompts. In Colab the original model answers them first and
   those answers are mixed into training ("replay"), so the model keeps that skill.

| Split | Sentences | Examples | Complaints |
|---|---|---|---|
| train | 318 | 1,626 | 43 |
| val | 54 | 254 | 31 (same complaints as train, new sentences) |
| holdout | 96 | 490 | 10 complaints **never seen in training** |

Holdout complaints: Abdominal distention, Animal bites & Insect stings, Breast complaints, Constipation, Ear pain,
Hypertension follow up, Oedema, Oral Pain, Sleep disorder, Smell & Taste disorder.

**Not used for training, ever:** TC01-TC05, Yuqi's new cases, Dr. Verma's 10 cases, `test_cases.csv`,
`eval_patient_answers.json`. (Checked: no sentence shares more than a common 5-word phrase like "gets worse after I eat" with them.)

## Before training (original MedPsy-1.7B)

Measured 2026-11-22 on CPU in bf16 with the notebook's scoring (all allowed replies, most likely one wins).
Colab measures again before training, so before/after there use the exact same setup.

| Step | Validation (254) | Holdout, unseen complaints (490) | Main mistake |
|---|---|---|---|
| **All** | **74.0%** right | **68.2%** right | |
| first pick, CHW typed it | 88.9% | 83.3% | picks an option when the patient was vague or only said "no X" (42-44% of those) |
| first pick, from story | 81.5% | 76.0% | same (42-50%) |
| "anything else?" | 50-83% | 47% | adds an extra option the patient never said (56%) |
| double-check, right answer | 21.6% | 17.2% | **says "no" to correct answers** (78-83%) |
| double-check, wrong answer | 94.9% | 92.9% | |
| question the patient never talked about | 64.9% | 55.6% | picks an option anyway (35-44%) |

So the original model is too strict at the double-check (correct story answers get thrown away, which lowers recall)
and too loose when nothing matches (which risks wrong facts). Fine-tuning should fix both without new mistakes.

## First run (Hugging Face PEFT, Colab T4, 11/22)

| | Before | After |
|---|---|---|
| Validation, right | 73.6% | **97.2%** |
| Holdout (10 unseen complaints), right | 68.4% | **94.1%** |
| Holdout, made up | 28.2% | **6.6%** |
| Holdout, missed | 27.7% | **3.2%** |

Validation loss 0.0109, 0.0081, 0.0080 after epochs 1-3. 19 of 20 explanations unchanged. Raw files:
`eval_results/2026-11-22_finetune-colab/`.

## Second run: Unsloth (suggested by Dr. Soenksen)

`finetune_medpsy_unsloth.ipynb` trains the same LoRA on the same data with [Unsloth](https://unsloth.ai/) instead of
plain PEFT, then scores it with the first run's exact code, so the two tools can be compared (accuracy, training
time, GPU memory). It reuses the first run's replay answers (`make_replay.py` makes `data/replay.jsonl` from
`data/explain_before.json`), and saves nothing to Google Drive: upload `ft_data_unsloth.zip`, and the results and the
GGUF file are downloaded to the laptop at the end.

## Hand-check of the data (Lia and Morrison, Nov 26)

Lia and Morrison checked 50 examples each in `Group6_Finetune_Data_Check.xlsx` (100 in all): 94 Y, 6 N. None of the
6 has a plainly wrong answer; in each, the patient's sentence could also fit a second option:

| ID | Split | Sentence | Why it's unclear |
|---|---|---|---|
| T0412 | train | "I vomit after the headache starts." | After headache, or During? |
| T0399 | train | "The pain is on the left side, in the middle of my belly." | Left Lumbar, or Umbilical? |
| T0305 | train | "Urine leaks when I sneeze. It also leaks sometimes for no reason at all." | "Sometimes" is not really Continuous |
| T0223 | train | "It's a pounding headache, like a hammer." | Pounding vs Throbbing (the patient said "pounding", so kept) |
| T0011 | holdout | "My stool is very hard, like small stones." | Hard, or Lumpy? |
| T0033 | holdout | "...itching and a rash all over, I am allergic to them." | Allergy, or Side-effects? |

**Decision: no retraining.** The 4 training targets are 4 of 473, and they are unclear sentences, not wrong answers.
**Holdout without the 2 unclear targets** (12 of 490 prompts dropped, 4-bit files): original 69.9%, fine-tuned 95.0%
(McNemar p < 0.001), the same as with them (69.6% -> 94.3%). We report 94.3% (the more cautious number). The data
files are left as they were trained; if we ever train again, reword these 6 sentences first.

## Steps

1. **Hand-check** (Lia and Morrison): `Group6_Finetune_Data_Check.xlsx`, 50 rows each. Fix or drop any row marked N
   in `sentences.jsonl`, then `python finetune/build_examples.py`.
2. **Train** in Google Colab (free T4 GPU): upload `finetune_medpsy.ipynb`, then Run all, and upload `ft_data.zip`
   when asked. About 45-60 minutes. It prints before/after scores and saves the GGUF files to Google Drive.
3. **Score the real 4-bit files on the laptop** (llama.cpp and grammar, like the phone):
   ```
   python finetune/score_gguf.py --model medpsy-1.7b-base-q4_k_m.gguf --data finetune/data/holdout.jsonl
   python finetune/score_gguf.py --model medpsy-1.7b-ft-q4_k_m.gguf   --data finetune/data/holdout.jsonl
   ```
4. **Full visit test** with the new model on TC01-TC05 (`evaluate_visits.py --model medpsy-1.7b-ft-q4_k_m.gguf`),
   plus explanations (`evaluate_explanations.py`). Keep the new model only if recall goes up without more wrong facts.
5. **Phone**: copy the new GGUF with the app's Load model button.
6. **Last**: Dr. Verma's 10 unseen cases, once, with the model we keep.

## Files

| File | What it is |
|---|---|
| `make_targets.py` | picks protocol questions and the correct answers (`targets.jsonl`) |
| `show_batch.py` | prints targets compactly, for writing the sentences |
| `sentences.jsonl` | the patient's words for each target |
| `build_examples.py` | builds `data/train.jsonl`, `val.jsonl`, `holdout.jsonl` with the app's prompts |
| `make_keep_prompts.py` | builds `data/keep_prompts.jsonl` (explain prompts for replay) |
| `make_check_sheet.py` | builds the hand-check spreadsheet |
| `notebook_cells.py`, `notebook_unsloth_cells.py`, `make_notebook.py` | the two Colab notebooks' source, and the script that writes both `.ipynb` files |
| `make_replay.py` | turns the first run's explain answers into `data/replay.jsonl` for the Unsloth run |
| `score_gguf.py` | scores a GGUF file on the examples with the app's grammar |

To rebuild everything: `PROTOCOLS=<protocols folder> python finetune/make_targets.py` (gives the same `targets.jsonl`;
the sentences are tied to its IDs), then `build_examples.py`, `make_keep_prompts.py`, `make_notebook.py`,
and zip the four files in `data/` as `ft_data.zip`.
