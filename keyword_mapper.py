import re


STOP_WORDS = {"the", "and", "for", "with", "have", "has", "had", "since", "from",
              "that", "this", "there", "your", "you", "any", "not", "other",
              "describe", "enter", "upper", "lower", "middle"}


def words_in(text):
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOP_WORDS}


class KeywordMapper:
    """No-AI baseline: picks options whose words appear in the patient's words."""

    name = "keyword"

    def map_answer(self, question_text, option_labels, patient_words, multi_choice):
        patient = words_in(patient_words)
        scores = []
        for index, label in enumerate(option_labels):
            overlap = len(words_in(label) & patient)
            scores.append((overlap, index))

        best_score = max(score for score, index in scores) if scores else 0
        if best_score == 0:
            return {"indexes": [], "unclear": True}

        if multi_choice:
            chosen = [index for score, index in scores if score > 0]
        else:
            chosen = [index for score, index in scores if score == best_score][:1]
        return {"indexes": chosen, "unclear": False}

    def match_complaint(self, complaint_names, patient_words):
        result = self.map_answer("Main complaint", complaint_names, patient_words, multi_choice=False)
        return result

    def answer_from_story(self, question_text, option_labels, story, multi_choice):
        return []

    def value_from_story(self, question_text, story):
        return ""

    def write_summary(self, facts_text):
        return None

    def explain(self, text, kind, question_text="", complaint=""):
        return None
