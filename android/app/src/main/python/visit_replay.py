#----- Lia's code: the Back button and "End this visit" (round 2), without changing the visit code -----
r"""How Back works
The visit code (main.run_visit, intake.py) only moves forward. So Back does not rewind it. Instead:
  1. the phone remembers every answer the CHW sent (PhoneConsole.history),
  2. Back removes the last answer and quietly starts the visit again,
  3. the new run gets the remembered answers back one by one (no waiting), and stops at the question
     whose answer was removed, which the CHW answers again.
MedPsy is not asked again during the replay: AnswerMemory keeps every AI answer of this visit, so the
replay takes a moment, not minutes, and the AI suggestions come out exactly the same as before.

Plain code, no AI. Used only by the phone app (app_bridge.py); the laptop app is unchanged."""

BACK = "[[back]]"   # what the Back button sends (a CHW would never type this)
END = "[[end]]"     # what "End this visit" in the menu sends


class GoBack(BaseException):
    """The CHW tapped Back. BaseException (like Ctrl+C), so no 'except Exception' in the visit code
    can swallow it."""


class EndVisit(BaseException):
    """The CHW chose 'End this visit' in the menu: stop without saving."""


class AnswerMemory:
    """Remembers MedPsy's answer to every prompt of one visit. During a replay the same prompt gets the
    same answer straight away, without running the model again (and without adding AI time)."""

    def __init__(self, mapper):
        self.mapper = mapper
        self.answers = {}
        self.original = getattr(mapper, "generate", None)   # keyword matching has no generate(): nothing to do
        if self.original is not None:
            mapper.generate = self.generate

    def generate(self, prompt, grammar=None, max_tokens=40, task="task"):
        grammar_text = getattr(grammar, "text", None) or getattr(grammar, "_grammar", None) or ""
        key = (prompt, str(grammar_text), max_tokens, task)
        if key not in self.answers:
            self.answers[key] = self.original(prompt, grammar=grammar, max_tokens=max_tokens, task=task)
        return self.answers[key]

    def stop(self):
        """Puts the model's own generate() back (MedPsy stays loaded for the next visit)."""
        if self.original is not None:
            del self.mapper.generate
#----- end of Lia's code -----
