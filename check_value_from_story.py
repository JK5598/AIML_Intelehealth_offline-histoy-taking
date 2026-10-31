import sys

from ai_mapper import AIMapper


CHEST_STORY = "Heavy pain in the center of my chest since this morning, I am sweating, no shortness of breath."

# (question, story, a word the answer must contain, or "" when the story does not answer the question)
CASES = [
    ("Additional information", CHEST_STORY, "breath"),
    ("Since when have you had this symptom?", "Pain near my right ribs for 3 days", "3 days"),
    ("Since when have you had this symptom?", "My stomach hurts", ""),
    ("Current medication", "Pain near my right ribs for 3 days", ""),
    ("Additional information", "Fever", ""),
    ("How long does the pain continue?", "My chest hurts", ""),
    ("Since when have you had this symptom?", "I have a cough and a runny nose", ""),
    ("Since when have you had this symptom?", "Headache on the left side, throbbing", ""),
    ("Last menstruation period", "Vomiting since last night", ""),
    ("Current medication", "Fever and chills, no cough", ""),
    ("Allergies", "My stomach hurts after I eat spicy food", ""),
    ("Number of drinks per day", "I have a cough for one week", ""),
    ("Since when have you had this symptom?", "My child is not eating well", ""),
    ("Current medication", "I took paracetamol yesterday for the fever", "paracetamol"),
    ("Since when have you had this symptom?", "Fever for 4 days, worse at night", "4 days"),
    ("Since when have you had this symptom?", "Dry cough since last Monday", "monday"),
    ("Additional information", "Loose motions since yesterday, I also feel very thirsty", "thirsty"),
]


def main():
    mapper = AIMapper(sys.argv[1])
    invented = 0
    stopped_by_model = 0
    stopped_by_word_check = 0
    good_answers_kept = 0
    good_answers_lost = 0

    for question, story, must_contain in CASES:
        model_value = mapper.model_value_from_story(question, story)
        final_value = mapper.value_from_story(question, story)

        if must_contain == "":
            if final_value:
                result = "INVENTED"
                invented += 1
            elif model_value.lower().startswith("not mentioned"):
                result = "ok, model said not mentioned"
                stopped_by_model += 1
            else:
                result = "ok, word check stopped it"
                stopped_by_word_check += 1
        else:
            if must_contain in final_value.lower():
                result = "ok"
                good_answers_kept += 1
            else:
                result = "GOOD ANSWER LOST"
                good_answers_lost += 1

        print(f"Q: {question}\n   story: {story}\n   model: {model_value!r}\n   kept:  {final_value!r}   -> {result}\n")

    print(f"Story does not answer: {invented} invented answers got through, "
          f"{stopped_by_model} stopped by the model, {stopped_by_word_check} stopped by the word check")
    print(f"Story does answer: {good_answers_kept} kept, {good_answers_lost} lost")


if __name__ == "__main__":
    main()
