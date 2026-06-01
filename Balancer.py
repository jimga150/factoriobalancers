import copy

import common
from Belt import *

try:
    from graphviz import Digraph
except ModuleNotFoundError:
    print('"graphviz" not installed: network rendering will not work')


class Balancer:
    def __init__(self):
        self.balance = list()

        # self.balance.append(Belt("A", 1))
        # self.balance.append(Belt("B", 1))
        # self.balance.append(Belt("C", 2))
        # self.balance.append(Belt("D", 2))
        # self.balance.append(Belt(1, 3))
        # self.balance.append(Belt(1, 4))
        # self.balance.append(Belt(2, 3))
        # self.balance.append(Belt(2, 4))
        # self.balance.append(Belt(3, "O1"))
        # self.balance.append(Belt(3, "O2"))
        # self.balance.append(Belt(4, "O3"))
        # self.balance.append(Belt(4, "O4"))

        self.balance.append(Belt("A", 1))
        self.balance.append(Belt("B", 1))
        self.balance.append(Belt("C", 2))
        self.balance.append(Belt(1, 2))
        self.balance.append(Belt(2, 3))
        self.balance.append(Belt(1, 3))
        self.balance.append(Belt(2, 4))
        self.balance.append(Belt(3, 5))
        self.balance.append(Belt(4, 5))
        self.balance.append(Belt(3, 6))
        self.balance.append(Belt(4, 6))
        self.balance.append(Belt(5, 4))
        # self.balance.append(Belt(5, "O1"))
        # self.balance.append(Belt(6, "O2"))
        # self.balance.append(Belt(6, "O3"))

        self.balance.append(Belt(5, 7))
        self.balance.append(Belt(6, 8))
        self.balance.append(Belt(7, 8))
        self.balance.append(Belt(8, 7))
        self.balance.append(Belt(8, "O"))

        # self.balance.append(Belt("A", 1))
        # self.balance.append(Belt("B", 2))
        # self.balance.append(Belt("C", 2))
        # self.balance.append(Belt(1, 3))
        # self.balance.append(Belt(2, 3))
        # self.balance.append(Belt(3, 1))
        # self.balance.append(Belt(3, "O"))

    def get_inputs(self):
        return [x for x in self.balance if x.is_input()]

    def get_outputs(self):
        return [x for x in self.balance if x.is_output()]

    def get_num_outputs(self) -> int:
        return len(self.get_outputs())

    def get_num_inputs(self) -> int:
        return len(self.get_inputs())

    # return True if balance changed
    def calc_balance_iter(self) -> bool:
        is_changed = False
        for belt in self.balance:

            if not belt.enabled:
                continue

            old_balance = copy.deepcopy(belt.balance)

            # print(f"Belt: {belt}")

            # belts inputting to the splitter that feeds this belt
            source_belts = [x for x in self.balance if x.dest == belt.source]

            if len(source_belts) == 0:
                # this is an input belt, a source of truth
                belt.balance[belt.source] = 1
                continue

            # print(f"\tHas sources")
            belt.balance = copy.deepcopy(source_belts[0].balance)
            # print(f"\tStart: {belt.get_label()}")
            for source_belt in source_belts[1:]:
                if not source_belt.enabled:
                    continue
                for (name, frac) in source_belt.balance.items():
                    if name in belt.balance:
                        # print(f"\t{name} already in balance, adding {frac}")
                        belt.balance[name] += frac
                    else:
                        # print(f"\t{name} = {frac}")
                        belt.balance[name] = frac

            # print(f"\tEnd: {belt.get_label()}")

            # divide by number of belts sharing this splitter
            # this includes 'belt'
            num_outputs_this_splitter = len([x for x in self.balance if x.source == belt.source and x.enabled])
            belt.balance = {k: v / num_outputs_this_splitter for (k, v) in belt.balance.items()}

            # normalize balance
            total = sum(belt.balance.values())
            if total > 1:
                belt.balance = {k: v / total for (k, v) in belt.balance.items()}

            # check for any changes in balance
            for name, frac in belt.balance.items():
                if name not in old_balance or abs(old_balance[name] - frac) > common.diff_threshold_iter:
                    is_changed = True
            for name in old_balance.keys():
                if name not in belt.balance:
                    is_changed = True

        return is_changed

    def calc_balance(self) -> None:
        for belt in self.balance:
            belt.balance.clear()
        iters = 0
        while self.calc_balance_iter():
            # print(f"Trying to balance, iteration {iters}")
            iters += 1
            if iters > 100:
                raise Exception(f"Balancer failed to converge after {iters} iterations")

    def render(self, name: str = "Network") -> None:
        g = Digraph(engine='dot', node_attr={'shape': 'rect', 'height': '0.5', 'width': '0.3'},
                    graph_attr={'rankdir': 'LR'})
        for belt in self.balance:
            g.edge(str(belt.source), str(belt.dest), label=belt.get_label())
        g.render(name, format='png', view=(name == "Network"), cleanup=True)