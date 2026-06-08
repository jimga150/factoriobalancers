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
        self.nodes = list()

    def postprocess_nodes(self):
        self.nodes.clear()

        input_char = ord('A')
        for belt in self.balance:
            if belt.source not in self.nodes:
                self.nodes.append(belt.source)
            if belt.dest not in self.nodes:
                self.nodes.append(belt.dest)
            if self.is_input(belt):
                belt.source.name = str(chr(input_char))
                input_char += 1

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

        # iters = 0
        # self.render(f"demand_only_iter_{iters}")
        # while self.calc_demand_iter():
        #     common.debug_print(f"Trying to converge demand, iteration {iters}")
        #     iters += 1
        #     self.render(f"demand_only_iter_{iters}")
        #     if iters > 1000:
        #         raise Exception(f"Balancer failed to converge demand after {iters} iterations")

        # self.render("demand_only")

        iters = 0
        while self.calc_balance_iter():
            common.debug_print(f"Trying to balance, iteration {iters}")
            iters += 1
            if iters > common.max_iters:
                raise Exception(f"Balancer failed to converge balance after {iters} iterations")

    def render(self, name: str = "Network") -> None:
        g = Digraph(engine='dot', node_attr={'shape': 'rect', 'height': '0.4', 'width': '0.5'},
                    graph_attr={'rankdir': 'BT'})

        valid_nodes = []
        for node in self.nodes:
            try:
                self.get_splitter(node)
                valid_nodes.append(node)
            except ArgumentError:
                continue

        input_splitters = [x for x in valid_nodes if self.get_splitter(x).is_input_proxy()]
        output_splitters = [x for x in valid_nodes if self.get_splitter(x).is_output_proxy()]
        middle_splitters = [x for x in valid_nodes if x not in input_splitters and x not in output_splitters]

        with g.subgraph() as s:
            s.attr(rank='source')
            for node in input_splitters:
                s.node(str(node))

        with g.subgraph() as s:
            s.attr(rank='sink')
            for node in output_splitters:
                s.node(str(node))

        with g.subgraph() as s:
            # s.attr(ordering='out')
            for node in middle_splitters:
                s.node(str(node))

        for belt in self.balance:
            if not belt.enabled:
                continue
            g.edge(str(belt.source), str(belt.dest), label=belt.get_label(), color=belt.get_color())
        g.render(name, format='png', view=(name == "Network"), cleanup=True)

    def export_to_sat_network(self) -> None:

        belt_indices = dict()

        i = 1
        for belt in self.balance:
            if not belt.enabled:
                belt_indices[belt] = -1
                continue
            if self.get_splitter(belt.source).is_input_proxy():
                belt_indices[belt] = 0
                continue
            belt_indices[belt] = i
            i += 1

        sat_network_str = ""

        for node in self.nodes:
            splitter = self.get_splitter(node)
            if splitter.is_input_proxy() or splitter.is_output_proxy():
                continue

            input_line = " ".join([str(belt_indices[belt]) for belt in splitter.inputs])
            if len(splitter.inputs) == 1:
                input_line = "-1 " + input_line

            output_line = " ".join([str(belt_indices[belt]) for belt in splitter.outputs])
            if len(splitter.outputs) == 1:
                output_line = "-1 " + output_line

            line = input_line + " " + output_line
            sat_network_str += line + "\n"

        with open("sat_network.txt", "w") as f:
            f.write(sat_network_str)