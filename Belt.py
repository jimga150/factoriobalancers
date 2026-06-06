from common import *


class Belt:

    def __init__(self, source, dest):
        self.source = source
        self.dest = dest

        # keys are names of input belts
        # values are ratio of that input's items (where 1 = this belt is full capacity with this input belt)
        self.supply_balance = dict()
        self.leftover_balance = dict()
        self.demand = 1

        self.enabled = True

    def __eq__(self, other):
        return self.source == other.source and self.dest == other.dest

    def __ne__(self, other):
        return self.source != other.source or self.dest != other.dest

    def get_balance_str(self):

        if len(self.supply_balance.keys()) > 1:
            first_frac = list(self.supply_balance.values())[0]
            is_equal = True
            for name, frac in self.supply_balance.items():
                if frac != first_frac:
                    is_equal = False
                    break

            if is_equal and abs(1/first_frac - len(self.supply_balance.values())) < diff_threshold_verif:
                balance_node_names = [str(x) for x in self.supply_balance.keys()]
                return "|".join(balance_node_names)

        return " + ".join([f"{frac:.{decimals_verif}f}*{name}" if frac != 1 else str(name) for name, frac in self.supply_balance.items()])

    def get_label(self):
        if not self.enabled:
            return ""
        return f"{self.get_balance_str()} ({self.demand:.{decimals_verif}f})"

    def add_balance(self, other_balance: dict):
        for name, frac in other_balance.items():
            if name in self.supply_balance:
                # print(f"\t{name} already in balance, adding {frac}")
                self.supply_balance[name] += frac
            else:
                # print(f"\t{name} = {frac}")
                self.supply_balance[name] = frac

    def is_balanced(self):
        return len(self.supply_balance.keys()) == 1 or "|" in self.get_label()

    def get_strength(self):
        return sum(self.supply_balance.values())

    def __str__(self):
        return f"{self.source}->{self.dest}"