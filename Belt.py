import common
from Node import Node

class Belt:

    def __init__(self, source: Node, dest: Node, source_priority: bool = False, dest_priority: bool = False):

        self.source = source
        self.dest = dest

        # is the source node prioritizing this output
        self.source_priority = source_priority

        # is the destination node prioritizing this input
        self.dest_priority = dest_priority

        # keys are input nodes
        # values are ratio of that input's items (where 1 = this belt is full capacity with this input belt)
        self.supply_balance = dict()
        self.demand = 1

        self.enabled = True

    def __eq__(self, other):
        return self.source == other.source and self.dest == other.dest

    def __ne__(self, other):
        return self.source != other.source or self.dest != other.dest

    def get_balance_str(self):

        if len(self.supply_balance.keys()) == 0:
            return ""

        first_frac = list(self.supply_balance.values())[0]
        is_equal = True
        for name, frac in self.supply_balance.items():
            if abs(frac - first_frac) > common.diff_threshold_verif:
                is_equal = False
                break

        if first_frac < common.diff_threshold_verif and is_equal:
            return ""

        if is_equal and abs(1 / first_frac - len(self.supply_balance.values())) < diff_threshold_verif:
            balance_node_names = [str(x) for x in self.supply_balance.keys()]
            return "|".join(balance_node_names)

        return " + ".join([f"{frac:.{decimals_verif}f}*{name}" if frac != 1 else str(name) for name, frac in self.supply_balance.items()])

    def get_label(self) -> str:
        if not self.enabled:
            return ""
        return f"{self.get_balance_str()} ({self.demand:.{common.decimals_verif}f})"

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

    @staticmethod
    def merge_balances(dictA: dict, weightA: float, dictB: dict, weightB: float) -> dict:
        return {i: dictA.get(i, 0) * weightA + dictB.get(i, 0) * weightB
                for i in set(dictA).union(dictB)}

    @staticmethod
    def merge_balances_eq(dictA: dict, dictB: dict) -> dict:
        return Belt.merge_balances(dictA, 1, dictB, 1)

    def add_balance(self, other_balance: dict):
        self.supply_balance = Belt.merge_balances_eq(self.supply_balance, other_balance)

    # returns supply less what the belt took
    def fill_with(self, supply: dict) -> dict:

        supply_magnitude = sum(supply.values())

        belt_full_magnitude = sum(self.supply_balance.values())

        additional_demand = self.demand - belt_full_magnitude
        if supply_magnitude < additional_demand:
            common.debug_print(f"supply_magnitude ({supply_magnitude}) < additional_demand ({additional_demand})")
            as_ratio = 1
        else:
            common.debug_print(f"supply_magnitude ({supply_magnitude}) >= additional_demand ({additional_demand})")
            as_ratio = additional_demand / supply_magnitude

        common.debug_print(f"as_ratio: {as_ratio}")

        self.supply_balance = Belt.merge_balances(self.supply_balance, 1, supply, as_ratio)

        supply = {k: v * (1 - as_ratio) for k, v in supply.items()}

        common.debug_print("Belt supply balance after adding more:")
        for k, v in self.supply_balance.items():
            common.debug_print(f"\t{k}: {v}")

        return supply

    def is_balanced(self):
        return len(self.supply_balance.keys()) == 1 or "|" in self.get_label()

    def get_strength(self):
        return sum(self.supply_balance.values())

    def __str__(self):
        return f"{self.source}->{self.dest}"