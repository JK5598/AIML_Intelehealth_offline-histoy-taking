#----- Lia's code: decide what the phone screen shows for each line and each question (round 1 UI fixes) -----
"""Reads the same text the laptop prints, and tells the phone screen:
  - how to style each line (section header, question title, red flag, or plain text), and
  - which buttons to show for the question being asked now:
      "options"  -> one button per option (tap = that option's number); Yes/No buttons hidden
      "yes_no"   -> Yes / No buttons only (Keep? / Correct? / Save as 'No'? / Patient not sure?)
      "red_flag" -> Yes / No / Don't know buttons
      "text"     -> no Yes/No buttons, only typing (the patient's words, a duration, a date, a name)
      "choice"   -> fixed buttons that send a word (sex: female / male)
Plain code, no AI. The visit itself (intake.py, main.py) is unchanged: buttons only send the same text a
CHW would type, so a tap and a typed answer always do the same thing.

Why: in Lia's typed TC01/TC04 visits (Nov 22) the Yes/No buttons were refused 9 times on numbered
questions, one "No" turned into "2" = Yes (allergies), and "y" was saved as Additional information."""
import re

OPTION_LINE = re.compile(r"^\s+(\d+)\. (.+)$")
MULTI_MARK = " (choose one or more)"

# What the app shows that is NOT a question title, even though the line does not start with spaces.
NOT_A_TITLE = ("(", "Python ", "MedPsy", "No model file", "Loading MedPsy", "Checked explanations",
               "AI on this phone", "=== ", "All test cases done", "Patient:", "Chief complaint:",
               "Patient's own words:", "Physical exam to perform:", "RED FLAGS", "- ", "Something went wrong")


def line_style(text):
    """'section', 'question', 'red_flag', 'summary' or 'plain' for one line the app shows."""
    stripped = text.strip()
    if not stripped:
        return "plain"
    if "RED FLAG" in stripped:
        return "red_flag"
    if stripped.startswith("--- ") and stripped.endswith(" ---"):
        return "section"
    if stripped.startswith("==========") or stripped.startswith("=== "):
        return "summary"
    if text.startswith(" ") or text.startswith("\n") or text.startswith(NOT_A_TITLE):
        return "plain"
    return "question"


class ScreenState:
    """Remembers the options of the question on screen, so the buttons match what was just listed."""

    def __init__(self):
        self.options = []      # [(number as text, label)]
        self.multi = False
        self.after_blank = True     # the app prints an empty line before every question title
        self.in_summary = False     # after "SUMMARY FOR THE DOCTOR" nothing is a question title

    def saw(self, text):
        """Takes what the app shows and returns [(line, style)]: the style of each line for the screen.
        A line is a question title only right after an empty line, and never inside the doctor's summary,
        so the second line of a long answer or story is never shown as a title (Lia's TC04 visit, Nov 23)."""
        styled = []
        for line in text.split("\n"):
            style = line_style(line)
            if "SUMMARY FOR THE DOCTOR" in line:
                self.in_summary = True
            if style == "question" and (self.in_summary or not self.after_blank):
                style = "plain"
            self.after_blank = (not line.strip()) or style == "section"
            styled.append((line, style))
            if style == "question":
                self.options = []
                self.multi = line.rstrip().endswith(MULTI_MARK)
            elif style in ("section", "summary"):
                self.options = []
                self.multi = False
            else:
                match = OPTION_LINE.match(line)
                if match:
                    number, label = match.group(1), match.group(2).strip()
                    if number == "1":           # a list starts again (e.g. shown again after "?")
                        self.options = []
                    self.options.append((number, label))
        return styled

    def buttons_for(self, prompt):
        """(kind, buttons, multi): buttons is a list of (text to send, label on the button)."""
        p = prompt.strip()
        if p.startswith("Save these?"):            # group mode: "y", "2", "1,3", "u2" or "n" are all allowed
            return "text", [("y", "All correct"), ("n", "None correct")], False
        if p.startswith("Which is right?"):         # group mode: the story and the reply disagree
            return "red_flag", [("y", "Has it"), ("n", "Does NOT have it"), ("u", "Unsure")], False
        if "RED-FLAG CHECK" in p and "d = don't know" in p:
            return "red_flag", [("y", "Yes"), ("n", "No"), ("d", "Don't know")], False
        if "(y/n)" in p or "(y = " in p or p.endswith("Correct?") or "Keep?" in p:
            return "yes_no", [("y", "Yes"), ("n", "No")], False
        if "(female/male)" in p:
            return "choice", [("female", "Female"), ("male", "Male")], False
        if p.startswith("Number(s)") or p.startswith("Number, or type"):
            return "options", list(self.options), self.multi
        return "text", [], False
#----- end of Lia's code -----
