from UniqueIDObj import UniqueIDObj

class Node(UniqueIDObj):
    def __init__(self):
        super().__init__()
        self.name = ""
        self.is_input = False
        self.is_output = False

    def __str__(self):
        if self.name != "":
            ans = self.name
        else:
            ans = super().__str__()

        if self.is_input:
            return ans + " (in)"
        if self.is_output:
            return ans + " (out)"
        return ans