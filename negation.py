import re


NEGATION_WORDS = {"no", "not", "never", "without", "denies", "denied", "none", "nothing",
                  "dont", "doesnt", "didnt", "havent", "hasnt", "hadnt", "isnt", "wasnt",
                  "nahi", "nahin"}

# "not sure", "don't know", "can't remember", "don't think": the patient is unsure, not saying no
UNSURE_AFTER_NEGATION = {"sure", "know", "certain", "remember", "think", "recall"}
# "No appetite", "no energy", "no sleep": here "no" describes a symptom, it is not a denial.
SYMPTOM_AFTER_NO = {"appetite", "energy", "strength", "sleep", "taste", "smell", "hunger"}

# "maybe", "might": the patient is unsure, so nothing after it counts as a no
UNSURE_WORDS = {"maybe", "might", "perhaps", "possibly", "unsure", "probably"}

SCOPE_ENDERS = {"but", "however", "although", "though", "except", "only", "just", "yet"}

PUNCTUATION = {".", ",", ";", "!", "?"}

GENERIC_WORDS = {"pain", "other", "describe", "with", "change", "feeling", "loss", "specific",
                 "particular", "part", "side", "body", "during", "when", "from", "that"}

WINDOW = 5

# "No nausea, vomiting, or diarrhea": a "no" in front of a list covers every item in it.
# After a comma, the "no" carries on only if the rest of the sentence is clearly a list:
# short items (3 words or fewer each) that ends with "or" / "nor" before the last item.
# This is strict on purpose. Wrongly marking a symptom as "no" hides it, so these stay as they are:
#   "no fever, I vomited twice"                      (new sentence part)
#   "no fever, cough started yesterday and got worse" (no "or", so not clearly a list)
#   "no fever, cough and cold"                       (could mean the patient HAS cough and cold)
LIST_ITEM_MAX_WORDS = 3
LIST_SPLITTERS = {",", "or", "nor", "and"}
LIST_ENDERS = {"or", "nor"}
SENTENCE_ENDERS = {".", ";", "!", "?"}
CLAUSE_STARTERS = {"i", "im", "ive", "id", "he", "she", "it", "its", "we", "they", "you", "my", "his", "her",
                   "our", "their", "the", "this", "that", "there", "then", "also", "so", "because",
                   "when", "after", "before", "since", "while"}


def tokens(text):
    text = text.lower().replace("'", "").replace("’", "")
    return re.findall(r"[a-z]+|[.,;!?]", text)


def list_length(words, comma_position):
    """If the words after this comma finish a 'no X, Y, or Z' list, returns how many words
    are left in the list. Otherwise returns 0 (the "no" stops at the comma, as before)."""
    rest = []
    for word in words[comma_position + 1:]:
        if word in SENTENCE_ENDERS:
            break
        rest.append(word)

    items = [[]]
    ends_with_or = False
    for word in rest:
        if word in LIST_SPLITTERS:
            items.append([])
            if word in LIST_ENDERS:
                ends_with_or = True
        else:
            items[-1].append(word)
    items = [item for item in items if item]

    if not ends_with_or or not items:
        return 0
    for item in items:
        if len(item) > LIST_ITEM_MAX_WORDS:
            return 0
        if item[0] in CLAUSE_STARTERS or item[0] in SCOPE_ENDERS or item[0] in NEGATION_WORDS:
            return 0
    return len(rest)


def stem(word):
    return word[:5]


def split_words(text):
    """Splits the patient's words into words said 'no' to and everything else."""
    words = tokens(text)
    negated = []
    affirmed = []
    words_left_in_scope = 0
    in_no_list = False
    unsure = False

    for position, word in enumerate(words):
        if position + 1 < len(words):
            next_word = words[position + 1]
        else:
            next_word = ""

        if word == "," and in_no_list and list_length(words, position) > 0:
            words_left_in_scope = list_length(words, position)
        elif word in PUNCTUATION or word in SCOPE_ENDERS:
            words_left_in_scope = 0
            in_no_list = False
            unsure = False
        elif word in UNSURE_WORDS:
            words_left_in_scope = 0
            unsure = True
        elif word in NEGATION_WORDS and next_word in SYMPTOM_AFTER_NO:
            words_left_in_scope = 0   # the symptom word that follows stays an affirmed word
        elif word in NEGATION_WORDS and next_word in UNSURE_AFTER_NEGATION:
            words_left_in_scope = 0
            unsure = True
        elif word in NEGATION_WORDS and not unsure:
            words_left_in_scope = WINDOW
            in_no_list = True
        elif words_left_in_scope > 0:
            negated.append(word)
            words_left_in_scope -= 1
        else:
            affirmed.append(word)
            in_no_list = False
    return negated, affirmed


def label_stems(label):
    words = re.findall(r"[a-z]+", label.lower())
    return {stem(w) for w in words if len(w) > 3 and w not in GENERIC_WORDS}


def is_negated(label, text):
    negated, affirmed = split_words(text)
    stems = label_stems(label)
    negated_hits = stems & {stem(w) for w in negated}
    affirmed_hits = stems & {stem(w) for w in affirmed}
    return len(negated_hits) > 0 and len(negated_hits) >= len(affirmed_hits)


def check_picks(option_labels, picked, text):
    kept = []
    dropped = []
    for index in picked:
        if is_negated(option_labels[index], text):
            dropped.append(index)
        else:
            kept.append(index)
    return kept, dropped


def find_negated(option_labels, text, skip=()):
    found = []
    for index, label in enumerate(option_labels):
        if index not in skip and is_negated(label, text):
            found.append(index)
    return found


def remove_negated(text):
    negated, affirmed = split_words(text)
    return " ".join(affirmed)
