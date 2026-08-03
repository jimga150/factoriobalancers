
class Node:
    def __init__(self):
        self.name = ""

    def __str__(self):
        if self.name != "":
            return self.name
        return str(hash(self))[-4:]

    def __hash__(self):
        return hash(str(id(self)))