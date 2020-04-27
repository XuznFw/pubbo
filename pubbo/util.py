import re


def create_class(name: str, parents: tuple, attribute: dict):
    return type(name, parents, attribute)


def byte_length(p):
    sniffer = format(p, "#010b")
    if sniffer.startswith("0b0") or sniffer.startswith("0b10"):
        length = 1
    elif sniffer.startswith("0b110"):
        length = 2
    elif sniffer.startswith("0b1110"):
        length = 3
    elif sniffer.startswith("0b11110"):
        length = 4
    else:
        raise Exception("oop")
    return length


def camel_to_under_score(message):
    return re.sub(r'([a-z]|\d)([A-Z])', r'\1_\2', message).lower()


def under_score_to_camel(message):
    return re.sub(r'(_\w)', lambda x: x.group(1)[1].upper(), message)
