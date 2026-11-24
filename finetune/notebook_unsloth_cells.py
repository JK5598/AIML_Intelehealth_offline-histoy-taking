"""The Unsloth version of the Colab notebook. make_notebook.py turns this into finetune_medpsy_unsloth.ipynb.

Same data, same LoRA settings, same scoring as finetune_medpsy.ipynb. Only the training tool changes (Unsloth).
Part A trains with Unsloth. Part B scores and converts with plain Hugging Face code, reusing the first
notebook's cells word for word, so the two runs are measured the same way.
Nothing is saved to Google Drive: the results are downloaded straight to the laptop at the end."""

from notebook_cells import CELLS as FIRST_RUN

CELLS = []


def text(s):
    CELLS.append(("markdown", s.strip("\n")))


def code(s):
    CELLS.append(("code", s.strip("\n")))


def first_run_cell(marker):
    """The code cell from the first notebook that contains this text."""
    for kind, source in FIRST_RUN:
        if kind == "code" and marker in source:
            return source
    raise ValueError(marker)


text("""
# Group 6: LoRA fine-tuning of MedPsy-1.7B with Unsloth

Same data, same LoRA settings and same scoring as our first run (Hugging Face PEFT). Only the training tool is different,
so we can compare the two.

**How to run**
1. Runtime > Change runtime type > **T4 GPU**.
2. Runtime > **Run all**. Upload `ft_data_unsloth.zip` when asked.
3. Part A trains (about 20-30 min), then **restarts the Python session on purpose** (a "session crashed/restarted" message is expected).
4. Click the first cell of **Part B**, then Runtime > **Run cell and below**. Part B scores the model, makes the GGUF file
   and downloads the results to your laptop (allow multiple downloads if the browser asks).

Nothing is saved to Google Drive. If Colab disconnects in the middle, just run it again.
""")

text("# Part A: train with Unsloth")
code("""
!pip -q install unsloth
""")

code("""
from unsloth import FastLanguageModel, is_bfloat16_supported   # Unsloth must be imported before transformers
import json, math, os, random, time, zipfile
import torch
from datasets import Dataset
from transformers import Trainer, TrainingArguments, DataCollatorForSeq2Seq

MODEL_NAME = "qvac/MedPsy-1.7B"
SEED = 6
END = "<|im_end|>"
random.seed(SEED)
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE - change the runtime to T4 GPU")
""")

code("""
# Upload ft_data_unsloth.zip (train, val, holdout, the explain prompts, and the replay answers from the first run).
from google.colab import files
uploaded = files.upload()
zipfile.ZipFile(list(uploaded)[0]).extractall("/content/data")


def load(name):
    with open(f"/content/data/{name}.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


train = load("train")
val = load("val")
replay = load("replay")
print("train", len(train), "| val", len(val), "| replay", len(replay))
""")

code("""
model, tokenizer = FastLanguageModel.from_pretrained(model_name=MODEL_NAME, max_seq_length=2048,
                                                     dtype=None, load_in_4bit=False)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth", random_state=SEED)
model.print_trainable_parameters()
print("vocabulary size:", len(tokenizer), "(should be the same as the original model)")
""")

text("""
Same settings as the first run: 3 epochs, learning rate 2e-4, batch of 8, linear schedule with 5% warmup,
and the loss only on the reply (`{"answer": N}<|im_end|>`), not on the prompt.
""")
code("""
def encode(example):
    prompt_ids = tokenizer(example["prompt"], add_special_tokens=False)["input_ids"]
    reply_ids = tokenizer(example["completion"] + END, add_special_tokens=False)["input_ids"]
    return {"input_ids": prompt_ids + reply_ids,
            "attention_mask": [1] * (len(prompt_ids) + len(reply_ids)),
            "labels": [-100] * len(prompt_ids) + reply_ids}


train_set = Dataset.from_list([encode(r) for r in train + replay]).shuffle(seed=SEED)
val_set = Dataset.from_list([encode(r) for r in val])
total_steps = 3 * math.ceil(len(train_set) / 8)   # batch of 8 = 4 per step x 2 steps of gradient accumulation

settings = TrainingArguments(
    output_dir="/content/unsloth_run", num_train_epochs=3, learning_rate=2e-4,
    per_device_train_batch_size=4, gradient_accumulation_steps=2, per_device_eval_batch_size=4,
    lr_scheduler_type="linear", warmup_steps=int(0.05 * total_steps), weight_decay=0.0, max_grad_norm=1.0,
    fp16=not is_bfloat16_supported(), bf16=is_bfloat16_supported(), optim="adamw_torch",
    logging_steps=25, eval_strategy="epoch", save_strategy="no", seed=SEED, report_to="none")
trainer = Trainer(model=model, args=settings, train_dataset=train_set, eval_dataset=val_set,
                  data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100))

started = time.time()
trainer.train()
minutes = round((time.time() - started) / 60, 1)

history = [{"epoch": round(log["epoch"]), "val_loss": log["eval_loss"]}
           for log in trainer.state.log_history if "eval_loss" in log]
print("training minutes:", minutes)
print(history)
model.save_pretrained("/content/adapter_unsloth")
tokenizer.save_pretrained("/content/adapter_unsloth")
json.dump({"tool": "unsloth", "training_minutes": minutes, "history": history,
           "peak_gpu_memory_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)},
          open("/content/unsloth_history.json", "w"), indent=1)
""")

code("""
# Restart Python so Part B scores with plain Hugging Face code, exactly like the first run.
# Colab will say the session crashed or restarted: that is expected. Then run Part B.
os.kill(os.getpid(), 9)
""")

text("""
# Part B: score and convert (same code as the first run)
Click the first code cell below, then Runtime > **Run cell and below**.
""")

setup = first_run_cell("MODEL_NAME = \"qvac/MedPsy-1.7B\"").replace(
    '!pip -q install -U "transformers>=4.51" peft accelerate\n', "")
code(setup + """


def load(name):
    with open(f"/content/data/{name}.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


val = load("val")
holdout = load("holdout")
keep_prompts = load("keep_prompts")
explain_before = json.load(open("/content/data/explain_before.json"))
SAVE = "/content/results_unsloth"
os.makedirs(SAVE, exist_ok=True)
""")

code("""
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.float32).to("cuda")
model = PeftModel.from_pretrained(model, "/content/adapter_unsloth")
model.eval()
END = "<|im_end|>"


def ids_of(text):
    return tokenizer(text, add_special_tokens=False)["input_ids"]
""")

code(first_run_cell("def allowed_replies(example):"))

code("""
after = {"val": score(val, "UNSLOTH AFTER - validation"),
         "holdout": score(holdout, "UNSLOTH AFTER - holdout (10 unseen complaints)")}
json.dump(after, open(SAVE + "/scores_after_unsloth.json", "w"), indent=1)
print("first run (PEFT) for comparison: validation 97.2%, holdout 94.1%; before training: 73.6% and 68.4%")
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


explain_after = []
for row in keep_prompts[:20]:
    explain_after.append({"text": row["meta"]["text"], "answer": first_sentence(generate(row["prompt"]))})
json.dump(explain_after, open(SAVE + "/explain_after_unsloth.json", "w"), indent=1)
same = sum(1 for b, a in zip(explain_before, explain_after) if b["answer"] == a["answer"])
print(same, "of 20 explanations identical to the original model")
""")

code(first_run_cell("merged = model.merge_and_unload()"))

gguf = first_run_cell("convert_hf_to_gguf.py /content/medpsy-ft").replace("medpsy-1.7b-ft-q4_k_m", "medpsy-1.7b-unsloth-q4_k_m")
gguf_lines = [line for line in gguf.split("\n") if "$SAVE" not in line]
code("\n".join(gguf_lines))

code("""
# Download the results to the laptop. The model file is 1.1 GB, so it takes a few minutes.
# If the browser blocks it: open the folder icon on the left, right-click the file, Download.
import shutil
shutil.copy("/content/unsloth_history.json", SAVE)
shutil.make_archive("/content/results_unsloth", "zip", SAVE)
from google.colab import files
files.download("/content/results_unsloth.zip")
files.download("/content/medpsy-1.7b-unsloth-q4_k_m.gguf")
""")
