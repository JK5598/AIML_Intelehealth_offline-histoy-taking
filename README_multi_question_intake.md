# Multi-question intake (`--intake group`)

*Lia's task (#4 in Project Update 1): "Multi-question intake: ask several questions at once, then follow up on missing or unclear answers."*

The CHW asks a small group of protocol questions together, types the patient's whole reply once, and the app fills in every question that reply answers. It then asks again only about what is **missing** or **unclear**.

Today's app (one question at a time) is unchanged and is still the default. The new mode only runs when you add `--intake group`.

---

## Why

- Dr. Soenksen's feedback: ask several questions at once, then come back to what is missing or unclear.
- Dr. Verma's rule: a complete history matters more than a fast one (target under 20 minutes).

So the goal is **fewer CHW steps without losing any answers**.

## How one group works

1. The app shows the next 4 questions of the protocol together. Questions the patient's story already answered are skipped.
2. The CHW asks them as one open question and types the patient's whole reply.
3. The app suggests an answer for each question the reply covers: with the AI if a model is loaded, otherwise with keyword matching.
4. The CHW checks all suggestions with **one** reply:
   - `y` = all correct
   - `2` or `1,3` = those are wrong (they get asked again)
   - `u2` = save Q2 as "patient unsure"
   - `n` = none are correct
5. Every question that is still missing, or had a wrong suggestion, is asked **once more on its own**.

**Severity questions** and **free-text boxes** ("Additional information") are never filled from the reply. They are always asked on their own, as in today's app.

Example screen:

```
--- Question group 2 of 4: ask these together ---
   Q1. What time of the day do you feel the pain?
   Q2. Character of the pain
   Q3. How severe is the pain?   (asked on its own after this)
   Q4. Do you have the following symptom(s)?
Type the patient's reply to these questions (Enter = ask them one by one):
    mostly at night, it is a dull ache, nausea and vomiting, maybe fever

   From the patient's reply:
   Q1. What time of the day do you feel the pain? -> Night
   Q2. Character of the pain -> Dull, aching
   Q4. Do you have the following symptom(s)? -> Nausea, Vomiting, Fever
        (patient sounded unsure: "maybe")
   Save these? y = all correct, or type the wrong ones (e.g. 2 or 1,3), u2 = Q2 unsure, n = none:
```

## Missing and unclear: what the app checks after each group

| Check | Example | What the app does |
| --- | --- | --- |
| Missing | The reply never says where the pain is | Asks that question on its own |
| Vague duration | "sometimes in a day" or "a while ago" for *Since when?* | Asks once: "how many days, weeks or months?" |
| Patient unsure | "maybe fever" | Shows a note; the CHW can save it as unsure |
| Answers disagree | Story says "no fever", reply says "maybe fever" | Asks the CHW which is right; only Fever changes |
| Suggestion rejected | The CHW marks a suggestion wrong | Asks that question on its own |

Each question is followed up **once**. During a follow-up the CHW can type:

- `u` = patient is unsure → saved with status `unsure`
- `x` = patient gave no answer → saved with status `not_answered`

Nothing is left blank, so the doctor can tell "asked, unknown" apart from "never asked". The doctor's summary shows these as *"(patient unsure)"* and *"asked, no answer"*.

## Safety: same rules as the rest of the app

- The AI answers by **option number only**, never with free text.
- Every AI pick gets the **yes/no double-check** ("Did the patient clearly say this?").
- The AI is never allowed to pick something the patient said "no" to.
- The CHW confirms **every** answer before it is saved; red flags are checked after every saved answer.

---

## How to run it

Run from the project folder. These commands assume the protocols repo sits **next to** the project folder. If yours is **inside** the project folder (as in the main README), drop the `../` or `..\`.

**1. Set the protocol folder (once per terminal window)**

```
# Windows, VS Code terminal (PowerShell)
$PROTOCOLS = "..\intelehealth-ayu-protocols\protocols\v2\All Protocols (JSON)"

# Windows, Anaconda Prompt
set "PROTOCOLS=..\intelehealth-ayu-protocols\protocols\v2\All Protocols (JSON)"

# Mac, Terminal
PROTOCOLS="../intelehealth-ayu-protocols/protocols/v2/All Protocols (JSON)"
```

**2. Run a visit**

In Anaconda Prompt write `"%PROTOCOLS%"` instead of `"$PROTOCOLS"`.

```
# today's app (default, unchanged)
python main.py --protocols "$PROTOCOLS"

# multi-question intake, no AI (keyword matching)
python main.py --protocols "$PROTOCOLS" --intake group

# multi-question intake with MedPsy-1.7B (use the full path to the model file)
python main.py --protocols "$PROTOCOLS" --intake group --model medpsy-1.7b-q4_k_m-imat.gguf
```

Optional: `--group-size 3` changes how many questions are asked together (default 4).

**3. Compare both modes on scripted patients**

```
python compare_intake_modes.py "$PROTOCOLS"
python compare_intake_modes.py "$PROTOCOLS" medpsy-1.7b-q4_k_m-imat.gguf
```

This runs 2 scripted patients (stomach pain, fever) through today's app and the multi-question intake and prints one table. Nobody types anything. It also saves `compare_<mode>_<number>_visit.json` files (ignored by git).

The model files are not in the repo. Download them from Hugging Face: [MedPsy-1.7B](https://huggingface.co/qvac/MedPsy-1.7B-GGUF) (`medpsy-1.7b-q4_k_m-imat.gguf`) or [MedPsy-4B](https://huggingface.co/qvac/MedPsy-4B-GGUF) (`medpsy-4b-q4_k_m-imat.gguf`).

---

## Files

| File | New or changed | What it does |
| --- | --- | --- |
| `intake_group.py` | New | The multi-question intake: shows each group, takes the one reply, gets a suggestion for every question (AI or keyword), lets the CHW check them all at once, then hands leftovers to the follow-up step. Holds the AI instructions for group replies (`GROUP_RULES`). |
| `followup.py` | New | The follow-up step: finds missing and unclear answers, asks each one once, saves `unsure` / `not_answered`, handles `u` and `x`. Also the plain-code rules for "no medicine" style replies. **No AI in this file.** |
| `compare_intake_modes.py` | New | Test tool that compares today's app and the multi-question intake on the same scripted patients. |
| `main.py` | Changed (small) | New settings `--intake one / group` (default `one`) and `--group-size`; saves `intake_mode`, `chw_inputs` and the follow-up list in `run_info` of `visit.json`. |
| `summary.py` | Changed (small) | Shows "patient unsure" and "asked, no answer" in the doctor's summary. |

Every new or changed block of code starts with `#----- Lia's code: ... -----` and ends with `#----- end of Lia's code -----`. All other files (`intake.py`, `ai_mapper.py`, `negation.py`, `protocols.py`, red flags, explanations) are unchanged and reused as they are.

### New fields in `visit.json`

- `answers[].status` can now also be `"unsure"` or `"not_answered"`.
- `answers[].source` can be `"from group reply"`.
- `run_info` gets `intake_mode`, `chw_inputs`, `group_size`, `groups_asked`, `filled_from_group_reply`, `follow_ups_asked`, `saved_unsure`, `saved_not_answered`, `follow_ups` (each with `question`, `reason`, `result`) and `group_replies`.

---

## Results (Nov 10, 2026)

CHW inputs per visit (average of 2 scripted patients). Both modes answered **every required question** in every setting.

| Setting | Today | Multi-question intake | Saving |
| --- | --- | --- | --- |
| No AI (keyword) | 58 | 42.5 | 27% fewer inputs |
| MedPsy-1.7B | 41.5 | 36 | 13% fewer inputs |
| MedPsy-4B | 43 | 40.5 | 6% fewer inputs |

- **Fewer wrong answers:** in the 4B visits, today's mode saved "Allergies: Yes" from "no known allergies" and "Worsens: Urination" from "food makes it worse"; the multi-question intake saved *No known allergies* and *Food*.
- **Cost:** more AI time per visit (1.7B: about 19 s → 28 s on a laptop CPU).
- **Recommendation:** use `--intake group` with MedPsy-1.7B.
- **Also tried:** a form-style version (questions only shown in groups). It saved no inputs, so it was removed.

**Limits:** 2 scripted patients with replies we wrote; CHW inputs stand in for visit time; AI times are from a laptop, and a phone will be slower; no CHW or clinician has used it yet.

---

## Note for the team: the "no" check in `negation.py`

`negation.check_picks` drops any option the patient said "no" to. That is right for "no fever", but it also drops options that **are** a "no" answer, such as *No known allergies*, *Never-smoker* or *Does not move*.

The multi-question intake keeps those options (`is_no_answer_option` in `followup.py`). The story step in today's app still uses the original check, so a story like "it doesn't move" may lose *Does not move* there. Worth a look by whoever owns `negation.py`.
