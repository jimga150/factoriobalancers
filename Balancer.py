import copy
import sys
from argparse import ArgumentError

import common
from Belt import Belt
from Node import Node
from Splitter import Splitter

try:
    from graphviz import Digraph
except ModuleNotFoundError:
    print('"graphviz" not installed: network rendering will not work')
    sys.exit(1)


class Balancer:
    def __init__(self):
        self.balance = list()
        self.nodes = set()

    def postprocess_nodes(self):
        self.nodes.clear()

        input_char = ord('A')
        for belt in self.balance:
            self.nodes.add(belt.source)
            self.nodes.add(belt.dest)
            if self.is_input(belt):
                belt.source.name = str(chr(input_char))
                input_char += 1

    @staticmethod
    def make3x3() -> Balancer:
        ans = Balancer()

        node_a = Node()
        node_b = Node()
        node_c = Node()
        node_1 = Node()
        node_2 = Node()
        node_3 = Node()
        node_4 = Node()
        node_5 = Node()
        node_6 = Node()
        node_o1 = Node()
        node_o2 = Node()
        node_o3 = Node()

        ans.balance.append(Belt(node_a, node_1))
        ans.balance.append(Belt(node_b, node_1))
        ans.balance.append(Belt(node_c, node_2))
        ans.balance.append(Belt(node_1, node_2))
        ans.balance.append(Belt(node_2, node_3))
        ans.balance.append(Belt(node_1, node_3))
        ans.balance.append(Belt(node_2, node_4))
        ans.balance.append(Belt(node_3, node_5))
        ans.balance.append(Belt(node_4, node_5))
        ans.balance.append(Belt(node_3, node_6))
        ans.balance.append(Belt(node_4, node_6))
        ans.balance.append(Belt(node_5, node_4))
        ans.balance.append(Belt(node_5, node_o1))
        ans.balance.append(Belt(node_6, node_o2))
        ans.balance.append(Belt(node_6, node_o3))

        ## make BAD 3->1
        # node_7 = Node()
        # node_o = Node()
        # self.balance.append(Belt(node_6, node_7))
        # self.balance.append(Belt(node_7, node_o))

        ans.postprocess_nodes()
        return ans

    @staticmethod
    def make4x4() -> Balancer:
        ans = Balancer()

        node_a = Node()
        node_b = Node()
        node_c = Node()
        node_d = Node()
        node_1 = Node()
        node_2 = Node()
        node_3 = Node()
        node_4 = Node()
        node_o1 = Node()
        node_o2 = Node()
        node_o3 = Node()
        node_o4 = Node()

        ans.balance.append(Belt(node_a, node_1))
        ans.balance.append(Belt(node_b, node_1))
        ans.balance.append(Belt(node_c, node_2))
        ans.balance.append(Belt(node_d, node_2))
        ans.balance.append(Belt(node_1, node_3))
        ans.balance.append(Belt(node_1, node_4))
        ans.balance.append(Belt(node_2, node_3))
        ans.balance.append(Belt(node_2, node_4))
        ans.balance.append(Belt(node_3, node_o1))
        ans.balance.append(Belt(node_3, node_o2))
        ans.balance.append(Belt(node_4, node_o3))
        ans.balance.append(Belt(node_4, node_o4))

        ans.postprocess_nodes()
        return ans

    @staticmethod
    def make_3x1() -> Balancer:
        ans = Balancer()

        node_a = Node()
        node_b = Node()
        node_c = Node()
        node_1 = Node()
        node_2 = Node()
        node_3 = Node()
        node_o = Node()

        ans.balance.append(Belt(node_a, node_1))
        ans.balance.append(Belt(node_b, node_2))
        ans.balance.append(Belt(node_c, node_2))
        ans.balance.append(Belt(node_1, node_3))
        ans.balance.append(Belt(node_2, node_3))
        ans.balance.append(Belt(node_3, node_1))
        ans.balance.append(Belt(node_3, node_o, True))

        ans.postprocess_nodes()
        return ans

    @staticmethod
    def make_2x2() -> Balancer:

        ans = Balancer()

        node_a = Node()
        node_b = Node()
        node_1 = Node()
        node_o1 = Node()
        node_o2 = Node()

        ans.balance.append(Belt(node_a, node_1))
        ans.balance.append(Belt(node_b, node_1))
        ans.balance.append(Belt(node_1, node_o1))
        ans.balance.append(Belt(node_1, node_o2))

        ans.postprocess_nodes()
        return ans

    @staticmethod
    def make_2x2_pri_out() -> Balancer:

        ans = Balancer()

        node_a = Node()
        node_b = Node()
        node_1 = Node()
        node_o1 = Node()
        node_o2 = Node()

        ans.balance.append(Belt(node_a, node_1))
        ans.balance.append(Belt(node_b, node_1))
        ans.balance.append(Belt(node_1, node_o1, True))
        ans.balance.append(Belt(node_1, node_o2))

        ans.postprocess_nodes()
        return ans

    @staticmethod
    def make_2x1_pri_in() -> Balancer:

        ans = Balancer()

        node_a = Node()
        node_b = Node()
        node_1 = Node()
        node_o1 = Node()

        ans.balance.append(Belt(node_a, node_1, False, True))
        ans.balance.append(Belt(node_b, node_1))
        ans.balance.append(Belt(node_1, node_o1))

        ans.postprocess_nodes()
        return ans

    @staticmethod
    def combine_balancers(upstream: Balancer, downstream: Balancer) -> Balancer:

        ans = copy.deepcopy(upstream)
        downstream_copy = copy.deepcopy(downstream)

        upstream_output_belts = ans.get_outputs()
        downstream_input_belts = downstream_copy.get_inputs()

        assert len(upstream_output_belts) == len(downstream_input_belts)

        # connect all upstream output to all downstream inputs using a dummy splitter
        for belt_idx in range(len(upstream_output_belts)):

            output_belt = upstream_output_belts[belt_idx]
            input_belt = downstream_input_belts[belt_idx]

            output_belt.dest = input_belt.dest
            output_belt.dest_priority = input_belt.dest_priority

        for belt in downstream_copy.balance:
            if downstream_copy.is_input(belt):
                continue
            ans.balance.append(belt)

        ans.postprocess_nodes()
        return ans

    def get_splitter(self, node) -> Splitter:
        inputs = [x for x in self.balance if x.dest == node and x.enabled]
        outputs = [x for x in self.balance if x.source == node and x.enabled]

        if len(inputs) == 0 and len(outputs) == 0:
            raise ArgumentError(None, f"No inputs or outputs")

        return Splitter(inputs, outputs)

    def get_inputs(self) -> list[Belt]:
        return [x for x in self.balance if self.is_input(x)]

    def get_outputs(self) -> list[Belt]:
        return [x for x in self.balance if self.is_output(x)]

    def is_input(self, belt: Belt) -> bool:
        return len([x for x in self.balance if x.dest == belt.source]) == 0

    def is_output(self, belt: Belt) -> bool:
        return len([x for x in self.balance if x.source == belt.dest]) == 0

    def get_num_outputs(self) -> int:
        return len(self.get_outputs())

    def get_num_inputs(self) -> int:
        return len(self.get_inputs())

    def calc_demand_iter(self) -> bool:
        common.debug_print("calc_demand_iter")
        is_changed = False
        for node in self.nodes:
            try:
                is_changed |= self.get_splitter(node).update_check_input_demand()
            except ArgumentError:
                pass

        return is_changed

    # return True if balance changed
    def calc_balance_iter(self) -> bool:
        common.debug_print("calc_balance_iter")
        is_changed = False
        for node in self.nodes:
            try:
                is_changed |= self.get_splitter(node).update_check_output_balance()
            except ArgumentError:
                pass

        return is_changed

    def calc_balance(self) -> None:

        common.debug_print("calc_balance")

        for belt in self.balance:
            belt.supply_balance.clear()
            belt.demand = 1

        iters = 0
        while self.calc_demand_iter():
            common.debug_print(f"Trying to converge demand, iteration {iters}")
            iters += 1
            if iters > 100:
                raise Exception(f"Balancer failed to converge demand after {iters} iterations")

        iters = 0
        while self.calc_balance_iter():
            common.debug_print(f"Trying to balance, iteration {iters}")
            iters += 1
            if iters > 100:
                raise Exception(f"Balancer failed to converge balance after {iters} iterations")

    def render(self, name: str = "Network") -> None:
        g = Digraph(engine='dot', node_attr={'shape': 'rect', 'height': '0.3', 'width': '0.5'},
                    graph_attr={'rankdir': 'BT'})
        for belt in self.balance:
            g.edge(str(belt.source), str(belt.dest), label=belt.get_label(), color=belt.get_color())
        g.render(name, format='png', view=(name == "Network"), cleanup=True)