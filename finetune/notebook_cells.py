"""The Colab notebook, written as a list of cells. make_notebook.py turns this into finetune_medpsy.ipynb.
Cells that start with "## " are text cells; the rest are code."""

CELLS = []


def text(s):
    CELLS.append(("markdown", s.strip("\n")))


def code(s):
    CELLS.append(("code", s.strip("\n")))


text("""
# Group 6: LoRA fine-tuning of MedPsy-1.7B for the patient history app

What this notebook does, top to bottom:
1. Loads the original MedPsy-1.7B and our training data (made by `build_examples.py`, the app's exact prompts).
2. Measures the original model on the validation and holdout examples (**before**).
3. Lets the original model answer the "explain this word" prompts, so we can mix those answers into training and the model does not forget that job.
4. Trains a small LoRA adapter (about 1% of the weights) on the answer-mapping prompts.
5. Measures again (**after**), on the same examples.
6. Merges the adapter, converts to GGUF and makes the 4-bit file the phone app loads.

**Before you start:** Runtime > Change runtime type > **T4 GPU**. Then Runtime > Run all.
It asks you to upload `ft_data.zip` (cell 2). Total time on a free T4 is about 45-60 minutes.
Everything is saved to Google Drive in `Group6_finetune/`, so nothing is lost if Colab disconnects.

Test cases TC01-TC05, Yuqi's new cases and Dr. Verma's cases are **not** in this data. They are only used for testing, on the laptop.
""")

text("## 1. Setup")
code("""
!pip -q install -U "transformers>=4.51" peft accelerate
import json, math, os, random, re, time, zipfile
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, get_linear_schedule_with_warmup
from peft import LoraConfig, get_peft_model, PeftModel

MODEL_NAME = "qvac/MedPsy-1.7B"
SEED = 6
random.seed(SEED)
torch.manual_seed(SEED)
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE - change the runtime to T4 GPU")
""")

code("""
# Save everything to Google Drive so a disconnect does not lose the work.
from google.colab import drive
drive.mount("/content/drive")
SAVE = "/content/drive/MyDrive/Group6_finetune"
os.makedirs(SAVE, exist_ok=True)
""")

text("## 2. Load the data")
code("""
# Upload ft_data.zip (it holds train.jsonl, val.jsonl, holdout.jsonl, keep_prompts.jsonl).
# If you already uploaded it to Drive once, it is reused from there.
zip_path = SAVE + "/ft_data.zip"
if not os.path.exists(zip_path):
    from google.colab import files
    uploaded = files.upload()
    with open(zip_path, "wb") as f:
        f.write(uploaded["ft_data.zip"])
zipfile.ZipFile(zip_path).extractall("/content/data")


def load(name):
    with open(f"/content/data/{name}.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


train = load("train")
val = load("val")
holdout = load("holdout")
keep_prompts = load("keep_prompts")
print("train", len(train), "| val", len(val), "| holdout", len(holdout), "| explain prompts", len(keep_prompts))
print(train[0]["prompt"] + train[0]["completion"])
""")

text("## 3. Load the original model")
code("""
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.float32).to("cuda")
model.eval()
END = "<|im_end|>"


def ids_of(text):
    return tokenizer(text, add_special_tokens=False)["input_ids"]


print("parameters:", round(sum(p.numel() for p in model.parameters()) / 1e9, 2), "billion")
""")

text("""
## 4. How we score

The app forces MedPsy to reply with only `{"answer": N}` (or `"yes"`/`"no"`). So here we do the same: we give the
model every allowed reply and take the one it finds most likely. A reply counts as right only if it is exactly the correct one.

We also count the two mistakes that matter most for the app:
- **made up**: the right reply was 0 / "no", but the model picked an option / said "yes" (a wrong fact in the record)
- **missed**: the right reply was an option / "yes", but the model said 0 / "no" (the CHW has to ask again)
""")
code("""
def allowed_replies(example):
    if '"yes"' in example["completion"] or '"no"' in example["completion"]:
        return ['{"answer": "yes"}', '{"answer": "no"}']
    user = example["prompt"].split("<|im_start|>user\\n")[-1]
    option_count = len(re.findall(r"^\\d+\\. ", user.split("Options:\\n")[1], flags=re.M)) - 1
    return ['{"answer": ' + str(n) + "}" for n in range(option_count + 1)]


def padded_batch(pairs):
    # pairs = [(prompt_ids, reply_ids), ...]. Pads on the LEFT so every reply ends at the same place.
    rows = [prompt + reply for prompt, reply in pairs]
    longest = max(len(r) for r in rows)
    input_ids = torch.full((len(rows), longest), tokenizer.pad_token_id)
    mask = torch.zeros((len(rows), longest), dtype=torch.long)
    for i, r in enumerate(rows):
        input_ids[i, longest - len(r):] = torch.tensor(r)
        mask[i, longest - len(r):] = 1
    positions = (mask.cumsum(dim=1) - 1).clamp(min=0)
    return input_ids.to(model.device), mask.to(model.device), positions.to(model.device)


def reply_log_probs(pairs):
    # Log-probability of each reply token. Only the last few positions get logits (saves a lot of memory).
    input_ids, mask, positions = padded_batch(pairs)
    keep = max(len(reply) for _, reply in pairs) + 1
    with torch.autocast("cuda", dtype=torch.float16, enabled=torch.cuda.is_available()):
        logits = model(input_ids=input_ids, attention_mask=mask, position_ids=positions,
                       logits_to_keep=keep).logits.float()
    log_probs = torch.log_softmax(logits, dim=-1)
    length = input_ids.shape[1]
    first_kept = length - keep
    results = []
    for i, (_, reply) in enumerate(pairs):
        token_scores = []
        for position in range(length - len(reply), length):
            token_scores.append(log_probs[i, position - 1 - first_kept, input_ids[i, position]])
        results.append(torch.stack(token_scores))
    return results


@torch.no_grad()
def model_reply(example):
    replies = allowed_replies(example)
    prompt_ids = ids_of(example["prompt"])
    pairs = [(prompt_ids, ids_of(reply + END)) for reply in replies]
    scores = [s.sum().item() for s in reply_log_probs(pairs)]
    return replies[scores.index(max(scores))]


def is_nothing(reply):
    return reply in ('{"answer": 0}', '{"answer": "no"}')


def score(examples, label):
    groups = {}
    wrong_rows = []
    for example in examples:
        got = model_reply(example)
        want = example["completion"]
        meta = example["meta"]
        group_name = meta["mode"] + " / " + meta["step"]
        for name in ("ALL", group_name):
            g = groups.setdefault(name, {"n": 0, "right": 0, "made_up": 0, "nothing_cases": 0, "missed": 0, "something_cases": 0})
            g["n"] += 1
            g["right"] += int(got == want)
            if is_nothing(want):
                g["nothing_cases"] += 1
                g["made_up"] += int(not is_nothing(got))
            else:
                g["something_cases"] += 1
                g["missed"] += int(is_nothing(got))
        if got != want:
            wrong_rows.append({"id": meta["id"], "group": group_name, "want": want, "got": got})
    print(f"{label}")
    print(f"  {'group':28s} {'n':>5s} {'right':>7s} {'made up':>9s} {'missed':>8s}")
    for name in sorted(groups, key=lambda k: (k != "ALL", k)):
        g = groups[name]
        made_up = 100 * g["made_up"] / g["nothing_cases"] if g["nothing_cases"] else 0
        missed = 100 * g["missed"] / g["something_cases"] if g["something_cases"] else 0
        print(f"  {name:28s} {g['n']:5d} {100 * g['right'] / g['n']:6.1f}% {made_up:8.1f}% {missed:7.1f}%")
    return {"groups": groups, "wrong": wrong_rows}
""")

text("## 5. Before training: the original model")
code("""
started = time.time()
before = {"val": score(val, "BEFORE - validation (complaints also seen in training, new sentences)"),
          "holdout": score(holdout, "BEFORE - holdout (10 complaints never seen in training)")}
json.dump(before, open(SAVE + "/scores_before.json", "w"), indent=1)
print(round((time.time() - started) / 60, 1), "minutes")
""")

text("""
## 6. Keep the other jobs working ("replay")

The app also asks MedPsy to explain medical words in plain language. If we only train on `{"answer": N}`,
the model could forget how to do that. So the **original** model answers 120 explain prompts now, and those
answers go into training. The model is then trained to keep giving the same explanations.
""")
code("""
@torch.no_grad()
def generate(prompt, max_new_tokens=60):
    input_ids = torch.tensor([ids_of(prompt)]).to(model.device)
    with torch.autocast("cuda", dtype=torch.float16, enabled=torch.cuda.is_available()):
        output = model.generate(input_ids, max_new_tokens=max_new_tokens, do_sample=False,
                                eos_token_id=tokenizer.convert_tokens_to_ids(END),
                                pad_token_id=tokenizer.pad_token_id)
    return tokenizer.decode(output[0, input_ids.shape[1]:], skip_special_tokens=True).strip()


def first_sentence(text):
    text = " ".join(text.split("</think>")[-1].split())
    match = re.search(r"[.!?](\\s|$)", text)
    return text[:match.end()].strip() if match else text


replay = []
explain_before = []
for row in keep_prompts:
    answer = first_sentence(generate(row["prompt"]))
    explain_before.append({"text": row["meta"]["text"], "answer": answer})
    if answer:
        replay.append({"prompt": row["prompt"], "completion": answer, "meta": {"mode": "explain", "step": "replay", "id": ""}})
json.dump(explain_before, open(SAVE + "/explain_before.json", "w"), indent=1)
print(len(replay), "replay examples, e.g.:")
for row in explain_before[:5]:
    print(" ", row["text"], "->", row["answer"])
""")

text("""
## 7. Train the LoRA adapter

Settings (kept small on purpose, so the model changes only where it needs to):
- LoRA rank 16 on all attention and MLP layers, about 1% of the weights are trained
- 3 passes over the data, learning rate 2e-4, batch of 8
- the loss is only on the reply (`{"answer": N}<|im_end|>`), not on the prompt
""")
code("""
EPOCHS = 3
BATCH = 8
LEARNING_RATE = 2e-4

lora_settings = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                           target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
model.enable_input_require_grads()
model.config.use_cache = False
model = get_peft_model(model, lora_settings)
model.print_trainable_parameters()


def batch_loss(rows):
    # Average log-loss over the reply tokens only (the prompt is not trained on).
    pairs = [(ids_of(r["prompt"]), ids_of(r["completion"] + END)) for r in rows]
    token_scores = torch.cat(reply_log_probs(pairs))
    return -token_scores.mean()


def average_loss(rows):
    model.eval()
    total = 0.0
    with torch.no_grad():
        for start in range(0, len(rows), BATCH):
            total += batch_loss(rows[start:start + BATCH]).item()
    model.train()
    return total / math.ceil(len(rows) / BATCH)


training_rows = train + replay
steps = EPOCHS * math.ceil(len(training_rows) / BATCH)
optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LEARNING_RATE)
schedule = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=int(0.05 * steps), num_training_steps=steps)
scaler = torch.amp.GradScaler("cuda", enabled=torch.cuda.is_available())

print("validation loss before:", round(average_loss(val), 4))
history = []
model.train()
started = time.time()
step = 0
for epoch in range(1, EPOCHS + 1):
    random.shuffle(training_rows)
    for start in range(0, len(training_rows), BATCH):
        loss = batch_loss(training_rows[start:start + BATCH])
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad()
        schedule.step()
        step += 1
        if step % 25 == 0:
            print(f"epoch {epoch} step {step}/{steps} loss {loss.item():.4f} ({(time.time() - started) / 60:.1f} min)")
    val_loss = average_loss(val)
    history.append({"epoch": epoch, "val_loss": val_loss})
    print(f"== epoch {epoch} done, validation loss {val_loss:.4f}")
    model.save_pretrained(SAVE + f"/adapter_epoch{epoch}")
json.dump(history, open(SAVE + "/train_history.json", "w"), indent=1)
""")

text("## 8. After training: same examples, same scoring")
code("""
model.eval()
model.config.use_cache = True
after = {"val": score(val, "AFTER - validation"),
         "holdout": score(holdout, "AFTER - holdout (10 unseen complaints)")}
json.dump(after, open(SAVE + "/scores_after.json", "w"), indent=1)

print()
print(f"{'':10s} {'before':>8s} {'after':>8s}")
for split in ("val", "holdout"):
    b = before[split]["groups"]["ALL"]
    a = after[split]["groups"]["ALL"]
    print(f"{split:10s} {100 * b['right'] / b['n']:7.1f}% {100 * a['right'] / a['n']:7.1f}%")
""")

code("""
# Did the explanations stay sensible? Compare a few, old vs new.
explain_after = []
for row in keep_prompts[:20]:
    explain_after.append({"text": row["meta"]["text"], "answer": first_sentence(generate(row["prompt"]))})
json.dump(explain_after, open(SAVE + "/explain_after.json", "w"), indent=1)
for b, a in zip(explain_before[:20], explain_after):
    print(b["text"])
    print("   before:", b["answer"])
    print("   after: ", a["answer"])
""")

text("""
## 9. Make the phone file (GGUF, 4-bit)

1. Merge the adapter into the model and save it.
2. Convert with llama.cpp's converter (same llama.cpp version as the app, b12447).
3. Quantize to Q4_K_M, the same size as the file the app uses now.
""")
code("""
merged = model.merge_and_unload()
merged = merged.to(torch.float16)
merged.save_pretrained("/content/medpsy-ft", safe_serialization=True)
tokenizer.save_pretrained("/content/medpsy-ft")
for name in ("generation_config.json",):
    if os.path.exists(f"/content/medpsy-ft/{name}"):
        print("saved", name)
del merged, model
torch.cuda.empty_cache()
""")

code("""
!git clone -q --depth 1 --branch b12447 https://github.com/ggml-org/llama.cpp /content/llama.cpp
!pip -q install sentencepiece
!python /content/llama.cpp/convert_hf_to_gguf.py /content/medpsy-ft --outtype f16 --outfile /content/medpsy-ft-f16.gguf
!cmake -S /content/llama.cpp -B /content/llama.cpp/build -DLLAMA_CURL=OFF -DGGML_NATIVE=ON > /dev/null
!cmake --build /content/llama.cpp/build --target llama-quantize -j 4 > /dev/null
!/content/llama.cpp/build/bin/llama-quantize /content/medpsy-ft-f16.gguf /content/medpsy-1.7b-ft-q4_k_m.gguf Q4_K_M
!cp /content/medpsy-1.7b-ft-q4_k_m.gguf "$SAVE/"
!ls -la "$SAVE"
""")

text("""
### Same pipeline for the ORIGINAL model (for a fair comparison)
The app's current file was made by MedPsy's authors with an "importance matrix" (imat). Ours was not.
So we also make the original model's Q4_K_M here, the exact same way. Then the laptop comparison is
original vs fine-tuned with nothing else different.
""")
code("""
from huggingface_hub import snapshot_download
base_folder = snapshot_download(MODEL_NAME)
!python /content/llama.cpp/convert_hf_to_gguf.py {base_folder} --outtype f16 --outfile /content/medpsy-base-f16.gguf
!/content/llama.cpp/build/bin/llama-quantize /content/medpsy-base-f16.gguf /content/medpsy-1.7b-base-q4_k_m.gguf Q4_K_M
!cp /content/medpsy-1.7b-base-q4_k_m.gguf "$SAVE/"
""")

text("""
Done. In Google Drive, `Group6_finetune/` now has:
- `medpsy-1.7b-ft-q4_k_m.gguf`: the fine-tuned model for the laptop tests and the phone app
- `medpsy-1.7b-base-q4_k_m.gguf`: the original model, made the same way (fair comparison)
- `scores_before.json`, `scores_after.json`: the before/after numbers above
- `train_history.json`, `adapter_epoch*/`: training record and the LoRA adapter
- `explain_before.json`, `explain_after.json`: explanation check

Next, on the laptop: `python finetune/score_gguf.py` on the original and the new GGUF (real 4-bit files, real grammar),
then the full visit test (`evaluate_visits.py`) on TC01-TC05 with the new model.
""")
