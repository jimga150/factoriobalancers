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
        self.real_balance = dict()
        self.desired_balance = dict()

        self.demand = 1

        self.enabled = True

    def __str__(self):
        return f"{self.source}->{self.dest}"

    def key(self):
        return f"{self.source}_{self.dest}"

    def __eq__(self, other):
        return self.source == other.source and self.dest == other.dest

    def __ne__(self, other):
        return self.source != other.source or self.dest != other.dest

    def __hash__(self):
        return hash((self.source, self.dest))

    def scale_real_to_demand(self):
        strength = self.get_desired_strength()
        if strength == 0:
            return
        ratio = min(self.demand / strength, 1)
        self.real_balance.clear()
        for name, frac in self.desired_balance.items():
            self.real_balance[name] = frac*ratio

    def get_balance_str(self, use_desired_balance: bool = False):

        balance = self.real_balance
        if use_desired_balance:
            balance = self.desired_balance

        if len(balance.keys()) == 0:
            return ""

        first_frac = list(balance.values())[0]
        is_equal = True
        for name, frac in balance.items():
            if abs(frac - first_frac) > common.diff_threshold_verif:
                is_equal = False
                break

        if first_frac < common.diff_threshold_verif and is_equal:
            return ""

        if is_equal and abs(1 / first_frac - len(balance.values())) < common.diff_threshold_verif:
            balance_node_names = [str(x) for x in balance.keys()]
            return "|".join(balance_node_names)

        balance_terms = [common.term_str(name, frac) for name, frac in balance.items()]
        balance_terms = [x for x in balance_terms if x != ""]
        return " + ".join(balance_terms)

    def get_label(self, use_desired_balance: bool = False) -> str:
        if not self.enabled:
            return ""
        ans = f"{self.get_balance_str(use_desired_balance)} ({common.term_str("", self.demand)})"
        if use_desired_balance:
            ans += " (Des)"
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

    @staticmethod
    def merge_balances(dictA: dict, weightA: float, dictB: dict, weightB: float) -> dict:
        return {i: dictA.get(i, 0) * weightA + dictB.get(i, 0) * weightB
                for i in set(dictA).union(dictB)}

    @staticmethod
    def merge_balances_eq(dictA: dict, dictB: dict) -> dict:
        return Belt.merge_balances(dictA, 1, dictB, 1)

    def add_real_balance(self, other_balance: dict):
        self.real_balance = Belt.merge_balances_eq(self.real_balance, other_balance)

    # returns supply less what the belt took
    def fill_desired_with(self, supply: dict) -> dict:

        supply_magnitude = sum(supply.values())

        belt_full_magnitude = sum(self.desired_balance.values())

        additional_demand = self.demand - belt_full_magnitude
        if supply_magnitude <= additional_demand or supply_magnitude == 0:
            common.debug_print(f"supply_magnitude ({supply_magnitude}) <= additional_demand ({additional_demand})")
            as_ratio = 1
        else:
            common.debug_print(f"supply_magnitude ({supply_magnitude}) > additional_demand ({additional_demand})")
            as_ratio = additional_demand / supply_magnitude

        common.debug_print(f"as_ratio: {as_ratio}")

        self.desired_balance = Belt.merge_balances(self.desired_balance, 1, supply, as_ratio)

        supply = {k: v * (1 - as_ratio) for k, v in supply.items()}

        common.debug_print("Belt desired balance after adding more:")
        for k, v in self.desired_balance.items():
            common.debug_print(f"\t{k}: {v}")

        return supply

    def is_balanced(self):
        return len(self.real_balance.keys()) == 1 or "|" in self.get_label()

    def get_real_strength(self):
        return sum(self.real_balance.values())

    def get_desired_strength(self):
        return sum(self.desired_balance.values())
