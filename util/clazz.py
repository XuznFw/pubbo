def create_class(name: str, parents: tuple, attribute: dict):
    return type(name, parents, attribute)
