import uuid

class Node:
    def __init__(self):
        self.uuid = uuid.uuid4()
        self.name = ""
        self.order = -1

    def __str__(self):
        if self.order != -1:
            return f"{self.order}"
        if self.name != "":
            return self.name
        return self.uuid.hex[-4:]

    def __eq__(self, other):
        return self.uuid == other.uuid

    def __ne__(self, other):
        return not self.uuid != other.uuid

    def __hash__(self):
        return hash(self.uuid)