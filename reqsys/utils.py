import uuid


class PrefixedIdGenerator:
    def __init__(self, prefix):
        self.prefix = prefix

    def __call__(self):
        return f"{self.prefix}_{uuid.uuid4().hex}"

    def deconstruct(self):
        return ('utils.PrefixedIdGenerator', [self.prefix], {})
