"""On the phone there is no llama-cpp-python. This small stand-in gives ai_mapper.py the same things it
uses on the laptop: Llama(model_path=...), calling the model with a prompt, and LlamaGrammar.from_string().
The work is done by llama.cpp through LlmEngine (Kotlin) and engine.cpp (C++)."""
from java import jclass

LlmEngine = jclass("com.example.intakeapp.LlmEngine")


class LlamaGrammar:
    def __init__(self, text):
        self.text = text

    @classmethod
    def from_string(cls, text, verbose=True):
        return cls(text)


class Llama:
    def __init__(self, model_path, n_ctx=4096, verbose=False, **other_settings):
        if not LlmEngine.load(model_path, n_ctx):
            raise RuntimeError("Could not load the model: " + str(LlmEngine.lastError()))

    def __call__(self, prompt, max_tokens=16, temperature=0, grammar=None, stop=None, **other_settings):
        # The engine always picks the most likely token, which is what temperature=0 means.
        grammar_text = grammar.text if grammar is not None else ""
        text = str(LlmEngine.generate(prompt, max_tokens, grammar_text))
        error = str(LlmEngine.lastError())
        if error:
            raise RuntimeError(error)
        for word in stop or []:
            if word in text:
                text = text[:text.index(word)]
        prompt_tokens, reused_tokens, output_tokens = list(LlmEngine.lastCounts())
        return {"choices": [{"text": text}],
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": output_tokens,
                          "reused_tokens": reused_tokens}}
