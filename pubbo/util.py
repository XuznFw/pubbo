import re


def camel_to_under_score(message):
    return re.sub(r'([a-z]|\d)([A-Z])', r'\1_\2', message).lower()


def under_score_to_camel(message):
    return re.sub(r'(_\w)', lambda x: x.group(1)[1].upper(), message)
