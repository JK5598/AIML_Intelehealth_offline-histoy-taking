"""Free, offline stand-in for Claude in the evaluation loop: a bigger model run on the laptop with llama.cpp.

Same ask() / ask_json() / cost() as claude_api.Claude, so the simulated patient and the judge
work with either one. Tested with Qwen3-8B (Q4_K_M, about 5 GB), the same family as MedPsy.
"""
import json
import os
import time

from llama_cpp import Llama, LlamaGrammar

from ai_mapper import SKIP_THINKING

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": {"type": "string"},
                           "result": {"type": "string", "enum": ["captured", "partly", "missed"]},
                           "evidence": {"type": "string"}},
            "required": ["id", "result", "evidence"]}},
        "wrong_facts": {"type": "array", "items": {
            "type": "object",
            "properties": {"statement": {"type": "string"}, "why": {"type": "string"},
                           "from_simulation": {"type": "boolean"}},
            "required": ["statement", "why", "from_simulation"]}},
        "unsupported": {"type": "array", "items": {
            "type": "object",
            "properties": {"statement": {"type": "string"}, "why": {"type": "string"}},
            "required": ["statement", "why"]}},
        "dangerous": {"type": "array", "items": {
            "type": "object",
            "properties": {"statement": {"type": "string"}, "why": {"type": "string"}},
            "required": ["statement", "why"]}},
        "diagnostic_sufficiency": {
            "type": "object",
            "properties": {"enough": {"type": "boolean"}, "why": {"type": "string"}},
            "required": ["enough", "why"]},
    },
    "required": ["facts", "wrong_facts", "unsupported", "dangerous", "diagnostic_sufficiency"],
}


class LocalLLM:
    def __init__(self, model_path, context_size=16384):
        print(f"Loading {os.path.basename(model_path)} for the patient and the judge...")
        self.model = Llama(model_path=model_path, n_ctx=context_size, n_gpu_layers=-1, verbose=False)
        self.name = os.path.basename(model_path)
        self.tokens = {}
        self.seconds = 0.0
        self.judge_grammar = LlamaGrammar.from_json_schema(json.dumps(JUDGE_SCHEMA), verbose=False)

    def ask(self, model, system, prompt, max_tokens=300, think=False, grammar=None):
        text = (f"<|im_start|>system\n{system}<|im_end|>\n"
                f"<|im_start|>user\n{prompt}<|im_end|>\n"
                f"<|im_start|>assistant\n{SKIP_THINKING}")
        started = time.time()
        result = self.model(text, max_tokens=max_tokens, temperature=0, grammar=grammar, stop=["<|im_end|>"])
        self.seconds += time.time() - started
        used = self.tokens.setdefault(self.name, {"input": 0, "output": 0})
        used["input"] += result["usage"]["prompt_tokens"]
        used["output"] += result["usage"]["completion_tokens"]
        return result["choices"][0]["text"].strip()

    def ask_json(self, model, system, prompt, max_tokens=6000):
        """The judge's answer. A grammar makes the model write valid JSON in the right shape."""
        text = self.ask(model, system, prompt, max_tokens, grammar=self.judge_grammar)
        return json.loads(text)

    def cost(self):
        return 0.0
