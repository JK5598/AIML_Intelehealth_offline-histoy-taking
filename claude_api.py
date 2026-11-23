"""Small helper for calling Claude, used only by the evaluation loop (never by the app itself).

Setup once (Mac Terminal):
    pip install anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."     (your key from console.anthropic.com)
"""
import json
import os
import time

PATIENT_MODEL = "claude-haiku-5-5"   # plays the patient: many short calls, so the small fast model
JUDGE_MODEL = "claude-sonnet-5-5"    # judges the finished record: one careful call per case

# Rough prices in US dollars per million tokens, only for the cost line in the report.
# Check console.anthropic.com for today's prices.
PRICES = {
    PATIENT_MODEL: {"input": 1.0, "output": 5.0},
    JUDGE_MODEL: {"input": 3.0, "output": 15.0},
}


class Claude:
    def __init__(self):
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY is not set. See the top of claude_api.py, or use --offline.")
        self.client = anthropic.Anthropic()
        self.tokens = {}   # model -> {"input": n, "output": n}
        self.can_turn_off_thinking = True

    def ask(self, model, system, prompt, max_tokens=300, think=False):
        """think=False: answer straight away (the patient's short answers). think=True: the model may
        think first (the judge). Only network problems and busy servers are retried."""
        import anthropic
        request = {"model": model, "max_tokens": max_tokens, "system": system,
                   "messages": [{"role": "user", "content": prompt}]}
        if not think and self.can_turn_off_thinking:
            request["thinking"] = {"type": "disabled"}
        for attempt in range(4):
            try:
                response = self.client.messages.create(**request)
                break
            except anthropic.BadRequestError as error:
                if "thinking" in str(error) and "thinking" in request:
                    self.can_turn_off_thinking = False   # this model can't turn thinking off: just leave it
                    request.pop("thinking")
                    request["max_tokens"] = max(max_tokens, 1000)
                    continue
                raise
            except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError) as error:
                if attempt == 3:
                    raise
                print(f"   (Claude call failed: {error}. Trying again in {5 * (attempt + 1)} s)")
                time.sleep(5 * (attempt + 1))
        used = self.tokens.setdefault(model, {"input": 0, "output": 0})
        used["input"] += response.usage.input_tokens
        used["output"] += response.usage.output_tokens
        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text
        return text.strip()

    def ask_json(self, model, system, prompt, max_tokens=16000):
        """Asks for a JSON answer and reads it. Tries once more if the reply is not valid JSON."""
        for attempt in range(2):
            text = self.ask(model, system, prompt, max_tokens, think=True)
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            prompt += "\n\nYour last reply was not valid JSON. Reply with the JSON object only."
        raise ValueError("Claude did not return valid JSON:\n" + text[:500])

    def cost(self):
        dollars = 0.0
        for model, used in self.tokens.items():
            price = PRICES.get(model, {"input": 0, "output": 0})
            dollars += used["input"] / 1e6 * price["input"] + used["output"] / 1e6 * price["output"]
        return round(dollars, 3)
