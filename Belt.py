import common
from Balance import Balance
from Node import Node

class Belt:

    def __init__(self, source: Node, dest: Node, source_priority: bool = False, dest_priority: bool = False):

        self.source = source
        self.dest = dest

        # is the source node prioritizing this output
        self.source_priority = source_priority

        # is the destination node prioritizing this input
        self.dest_priority = dest_priority

        self.enabled = True

        # PyCharm gets mad if I don't put these here
        self.supply = None
        self.demand = None
        self.balance = Balance()
        self.reset()

    def reset(self):
        # keys are input nodes
        # values are ratio of that input's items (where 1 = this belt is full capacity with this input belt)
        # self.real_balance = dict()
        # self.desired_balance = dict()
        self.balance = Balance()

        self.demand = 1
        self.supply = 0

    def __str__(self):
        return f"{self.source}->{self.dest}"

    def __eq__(self, other):
        return self.source == other.source and self.dest == other.dest

    def __ne__(self, other):
        return self.source != other.source or self.dest != other.dest

    def __hash__(self):
        return hash((self.source, self.dest))

    def flow(self) -> float:
        return min(self.demand, self.supply)

    def get_label(self) -> str:
        if not self.enabled:
            return ""
        ans = (f"{str(self.balance)} "
               f"[{common.frac_str(self.demand)}, {common.frac_str(self.supply)}]")
        return ans

    def get_color(self) -> str:
        if not self.enabled:
            return "white"
        if self.source_priority and self.dest_priority:
            return "green"
        if self.source_priority:
            return "red"
        if self.dest_priority:
            return "blue"
        return "black"
