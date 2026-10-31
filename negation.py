import re


NEGATION_WORDS = {"no", "not", "never", "without", "denies", "denied", "none", "nothing",
                  "dont", "doesnt", "didnt", "havent", "hasnt", "hadnt", "isnt", "wasnt",
                  "nahi", "nahin"}

# "not sure", "don't know", "can't remember", "don't think": the patient is unsure, not saying no
UNSURE_AFTER_NEGATION = {"sure", "know", "certain", "remember", "think", "recall"}

# "maybe", "might": the patient is unsure, so nothing after it counts as a no
UNSURE_WORDS = {"maybe", "might", "perhaps", "possibly", "unsure", "probably"}

SCOPE_ENDERS = {"but", "however", "although", "though", "except", "only", "just", "yet"}

PUNCTUATION = {".", ",", ";", "!", "?"}

GENERIC_WORDS = {"pain", "other", "describe", "with", "change", "feeling", "loss", "specific",
                 "particular", "part", "side", "body", "during", "when", "from", "that"}

WINDOW = 5


def tokens(text):
    text = text.lower().replace("'", "").replace("’", "")
    return re.findall(r"[a-z]+|[.,;!?]", text)


def stem(word):
    return word[:5]


def split_words(text):
    """Splits the patient's words into words said 'no' to and everything else."""
    words = tokens(text)
    negated = []
    affirmed = []
    words_left_in_scope = 0
    unsure = False

    for position, word in enumerate(words):
        if position + 1 < len(words):
            next_word = words[position + 1]
        else:
            next_word = ""

        if word in PUNCTUATION or word in SCOPE_ENDERS:
            words_left_in_scope = 0
            unsure = False
        elif word in UNSURE_WORDS:
            words_left_in_scope = 0
            unsure = True
        elif word in NEGATION_WORDS and next_word in UNSURE_AFTER_NEGATION:
            words_left_in_scope = 0
            unsure = True
        elif word in NEGATION_WORDS and not unsure:
            words_left_in_scope = WINDOW
        elif words_left_in_scope > 0:
            negated.append(word)
            words_left_in_scope -= 1
        else:
            affirmed.append(word)
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
