from UniqueIDObj import UniqueIDObj

class Node(UniqueIDObj):
    def __init__(self):
        super().__init__()
        self.name = ""

    def __str__(self):
        if self.name != "":
            return self.name
        return super().__str__()