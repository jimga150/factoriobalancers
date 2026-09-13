import copy
import logging
import os
import sys
from argparse import ArgumentError
from pathlib import Path
from types import NoneType

import z3
import networkx

import common
from Belt import Belt, ColorStrategy
from Node import Node
from Splitter import Splitter

logger = logging.getLogger(__name__)
common.setup_logger(logger)

try:
    from graphviz import Digraph
except ModuleNotFoundError:
    logger.error('"graphviz" not installed: network rendering will not work')
    sys.exit(1)


class Balancer:

    default_img_filename = "Network"

    # when generating false oversupply, go over by this amount
    oversupply_amt = common.diff_threshold_iter

    def __init__(self):
        self.belts = list()
        self.nodes = list()

        self.z3solver = None
        self.total_throughput_var = None

    def equivalent_to(self, other: Balancer) -> bool:
        # true if this balancer is isomorphic to other
        this_nx = self.to_networkx()
        other_nx = other.to_networkx()
        return networkx.is_isomorphic(this_nx, other_nx)

    def to_networkx(self) -> networkx.MultiDiGraph:
        ans = networkx.MultiDiGraph()
        for belt in self.belts:
            ans.add_node(belt.source, name=str(belt.source))
            ans.add_node(belt.dest, name=str(belt.dest))
            ans.add_edge(belt.source, belt.dest)
        return ans

    def postprocess_nodes(self, optimize: bool = True):
        self.nodes.clear()
        self.z3solver = None
        self.total_throughput_var = None

        min_input_char = ord('A')
        max_input_char = ord('Z')
        input_char = min_input_char

        output_idx = 1
        for belt in self.belts:

            if belt.source not in self.nodes:
                self.nodes.append(belt.source)
            if belt.dest not in self.nodes:
                self.nodes.append(belt.dest)

            if self.is_input(belt):
                belt.source.name = str(chr(input_char))
                input_char += 1
                if input_char > max_input_char:
                    raise RuntimeError(f"Can't handle more than {max_input_char - min_input_char} inputs.")
            else:
                belt.source.name = ""

            if self.is_output(belt):
                belt.dest.name = f"O{output_idx}"
                output_idx += 1
            else:
                belt.dest.name = ""

        for node in self.nodes:
            same_names = [x for x in self.nodes if str(x) == str(node)]
            if len(same_names) > 1:
                logger.error(f"Error: {node} has a duplicate in the node list. Nodes:")
                for node in self.nodes:
                    logger.error(f"{str(node)} ({hash(node)}) ({id(node)})")
                logger.error("same_names:")
                for node in same_names:
                    logger.error(f"{str(node)} ({hash(node)}) ({id(node)})")
                raise AssertionError(f"{node} has a duplicate in the node list.")

        nodes_to_remove = []
        belts_to_remove = []
        for node in self.nodes:
            splitter = self.get_splitter(node)
            if len(splitter.get_enabled_inputs()) > 2:
                raise AssertionError(f"Error: {node} has more than 2 inputs. This balancer is illegal.")

            outputs = splitter.get_enabled_outputs()
            if len(outputs) > 2:
                raise AssertionError(f"Error: {node} has more than 2 outputs. This balancer is illegal.")

            if optimize and len(outputs) == 2 and outputs[0].dest == outputs[1].dest:
                nodes_to_remove.append(outputs[0].dest)
                belts_to_remove.extend(outputs)
                splitter_to_remove = self.get_splitter(outputs[0].dest)
                for b in splitter_to_remove.get_enabled_outputs():
                    b.source = node

        for node in nodes_to_remove:
            self.nodes.remove(node)
        for belt in belts_to_remove:
            self.belts.remove(belt)


    @staticmethod
    def combine_endtoend(upstream: Balancer, downstream: Balancer | NoneType = None, optimize: bool = True) -> Balancer:

        if downstream is None:
            downstream = upstream

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

        for belt in downstream_copy.belts:
            if downstream_copy.is_input(belt):
                continue
            ans.belts.append(belt)

        ans.postprocess_nodes(optimize)
        return ans

    @staticmethod
    def make_tap_loop(simple_balancer: Balancer, rebalancer: Balancer | NoneType = None) -> Balancer:

        if rebalancer is None:
            rebalancer = simple_balancer

        assert simple_balancer.get_num_outputs() == rebalancer.get_num_inputs()
        assert rebalancer.get_num_outputs() == simple_balancer.get_num_inputs()

        ans = copy.deepcopy(simple_balancer)
        excess_rebalancer = copy.deepcopy(rebalancer)

        pri_in_nodes = []

        for belt in ans.get_inputs():
            # insert a new splitter into the input path, we'll use it later to reconnect the rebalancer
            pri_in_node = Node()
            ans.belts.append(Belt(belt.source, pri_in_node, dest_priority=True))
            belt.source = pri_in_node
            pri_in_nodes.append(pri_in_node)

        pri_out_nodes = []

        for belt in ans.get_outputs():
            # insert a new splitter into the output path, we'll use it later to source the rebalancer
            pri_out_node = Node()
            ans.belts.append(Belt(pri_out_node, belt.dest, source_priority=True))
            belt.dest = pri_out_node
            pri_out_nodes.append(pri_out_node)

        input_idx = 0
        output_idx = 0
        for belt in excess_rebalancer.belts:
            if excess_rebalancer.is_input(belt):
                belt.source = pri_out_nodes[output_idx]
                output_idx += 1
            if excess_rebalancer.is_output(belt):
                belt.dest = pri_in_nodes[input_idx]
                input_idx += 1
            ans.belts.append(belt)

        ans.postprocess_nodes()
        return ans
    
    @staticmethod
    def combine_sidebyside(sub_balancer: Balancer) -> Balancer:
        ans = copy.deepcopy(sub_balancer)
        sideB = copy.deepcopy(sub_balancer)

        num_sub_balancer_outputs = len(ans.get_outputs())

        assert len(sideB.get_outputs()) == num_sub_balancer_outputs

        sideA_outputs = ans.get_outputs()
        sideB_outputs = sideB.get_outputs()

        for belt in sideB.belts:
            ans.belts.append(belt)

        for i in range(num_sub_balancer_outputs):
            sideA_output = sideA_outputs[i]
            sideB_output = sideB_outputs[i]

            # reuse an output proxy node as the merge splitter
            merge_node = sideA_output.dest
            new_out_node_1 = sideB_output.dest
            new_out_node_2 = Node()

            sideA_output.dest = merge_node
            sideB_output.dest = merge_node

            # add belts going from the merge to the new output proxies
            ans.belts.append(Belt(merge_node, new_out_node_1))
            ans.belts.append(Belt(merge_node, new_out_node_2))

        ans.postprocess_nodes()
        return ans

    def get_solver(self) -> z3.Solver:

        if self.z3solver is not None:
            return self.z3solver

        self.z3solver = z3.Solver()
        logger.debug("populating z3 model of balancer...")

        for belt in self.belts:
            logger.debug(f"Belt {belt}")

            # removed since oversupply logic can force supply to be greater than belt capacity
            self.z3solver.assert_and_track(belt.supply_var() <= Belt.max_belt_val, f"{str(belt)}_s_lte_{Belt.max_belt_val}")
            self.z3solver.assert_and_track(belt.supply_var() >= 0, f"{str(belt)}_s_gte_0")
            self.z3solver.assert_and_track(belt.demand_var() <= Belt.max_belt_val, f"{str(belt)}_d_lte_{Belt.max_belt_val}")
            self.z3solver.assert_and_track(belt.demand_var() >= 0, f"{str(belt)}_d_gte_0")

            self.z3solver.assert_and_track(z3.Implies(belt.pushing_var(), belt.supply_var() == belt.demand_var()), f"{str(belt)}_sat_if_p")

        for belt in self.get_inputs():
            self.z3solver.assert_and_track(belt.pushing_var() == False, f"{str(belt)}_p_false")
            # # gotta assert them on the input supplies since they will not be driven from our oversupply rules
            # self.z3solver.assert_and_track(belt.supply_var() <= Belt.max_belt_val, f"{str(belt)}_s_lte_{Belt.max_belt_val}")

        for node in self.nodes:
            try:
                splitter = self.get_splitter(node)
            except ArgumentError:
                logger.debug(f"Node {node} could not access splitter")
                continue

            logger.debug(f"Splitter {splitter}")

            splitter.populate_solver(self.z3solver)

        if common.use_quant_ext_vars:
            # force all input supplies and output demands to be quantized
            for belt in self.get_inputs():
                int_supply = z3.Int(f"{belt.varname()}_supply_int")
                self.z3solver.assert_and_track(
                    int_supply == belt.supply_var(),#*common.ext_var_quant_denom,
                    f"{belt}_s_quant_{common.ext_var_quant_denom}"
                )

            for belt in self.get_outputs():
                int_demand = z3.Int(f"{belt.varname()}_demand_int")
                self.z3solver.assert_and_track(
                    int_demand == belt.demand_var(),#*common.ext_var_quant_denom,
                    f"{belt}_d_quant_{common.ext_var_quant_denom}"
                )

        total_throughput_expr = z3.Sum([x.flow_var() for x in self.get_outputs()])
        self.total_throughput_var = z3.Real("total_throughput")
        self.z3solver.assert_and_track(total_throughput_expr == self.total_throughput_var, "total_throughput_expr")

        logger.debug(f"Assertions:")
        for a in self.z3solver.assertions():
            logger.debug(a)

        return self.z3solver

    def set_to_model(self):
        solver = self.get_solver()
        model = solver.model()
        logger.debug("Full model:")
        for assignment in model:
            logger.debug(f"{str(assignment)} = {model[assignment]}")
        for belt in self.belts:
            belt.supply = float(model[belt.supply_var()].as_fraction())
            belt.demand = float(model[belt.demand_var()].as_fraction())
            belt.pushing = bool(model[belt.pushing_var()])

    def get_splitter(self, node) -> Splitter:
        inputs = [x for x in self.belts if x.dest == node]
        outputs = [x for x in self.belts if x.source == node]

        if len(inputs) == 0 and len(outputs) == 0:
            raise ArgumentError(None, f"No inputs or outputs")

        return Splitter(inputs, outputs)

    def get_inputs(self) -> list[Belt]:
        return [x for x in self.belts if self.is_input(x)]

    def get_outputs(self) -> list[Belt]:
        return [x for x in self.belts if self.is_output(x)]

    def is_input(self, belt: Belt) -> bool:
        return len([x for x in self.belts if x.dest == belt.source]) == 0

    def is_output(self, belt: Belt) -> bool:
        return len([x for x in self.belts if x.source == belt.dest]) == 0

    def get_num_outputs(self) -> int:
        return len(self.get_outputs())

    def get_num_inputs(self) -> int:
        return len(self.get_inputs())

    def get_enabled_inputs(self) -> list[Belt]:
        return [x for x in self.get_inputs() if x.enabled]

    def get_enabled_outputs(self) -> list[Belt]:
        return [x for x in self.get_outputs() if x.enabled]

    def get_num_enabled_inputs(self) -> int:
        return len(self.get_enabled_inputs())

    def get_num_enabled_outputs(self) -> int:
        return len(self.get_enabled_outputs())

    def render_all_methods(self, name: str = default_img_filename) -> None:
        for cs in ColorStrategy:
            self.render(f"{name} ({ColorStrategy(cs)})", cs)

    def render(self, name: str = default_img_filename, color_strat: ColorStrategy = ColorStrategy.PRIORITY) -> None:
        g = Digraph(engine='dot', node_attr={'shape': 'rect', 'height': '0.4', 'width': '0.5'},
                    graph_attr={'rankdir': 'BT'})

        view_render = name == Balancer.default_img_filename

        if not Path.exists(Path(common.output_folder)):
            os.makedirs(common.output_folder)
        name = str(Path(common.output_folder) / name)

        valid_nodes = []
        for node in self.nodes:
            try:
                splitter = self.get_splitter(node)
                if len(splitter.get_enabled_inputs()) > 0 or len(splitter.get_enabled_outputs()) > 0:
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

        for belt in self.belts:
            if not belt.enabled:
                continue
            g.edge(str(belt.source), str(belt.dest), label=belt.get_label(), color=belt.get_color(color_strat))
        g.render(name, format='png', view=view_render, cleanup=True)

    def export_to_sat_network(self) -> None:

        belt_indices = dict()

        i = 1
        for belt in self.belts:
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