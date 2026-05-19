import re


def is_upper_name(text):
    letters = [character for character in text if character.isalpha()]
    return bool(letters) and all(character.isupper() for character in letters)


def is_title_case_name(text):
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return False
    return text[:1].isupper()


def lower_key(token):
    return (token.lemma or token.lower or "").lower()


def is_sentence_start(previous_token):
    return previous_token is None or previous_token.text in {".", "!", "?", '"', "“", "”", ":"}


def is_time_token(text):
    return bool(re.fullmatch(r"\d{1,2}\.\d{2}", text))
