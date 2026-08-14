import copy
import logging
import sys
from argparse import ArgumentError
from types import NoneType

import z3

import common
from Belt import Belt, ColorStrategy
from Node import Node
from Splitter import Splitter

try:
    from graphviz import Digraph
except ModuleNotFoundError:
    print('"graphviz" not installed: network rendering will not work')
    sys.exit(1)

balancerLogger = logging.getLogger(__name__)

class Balancer:

    default_img_filename = "Network"
    default_logger = balancerLogger

    def __init__(self):
        self.belts = list()
        self.nodes = list()

        self.z3solver = None
        self.total_throughput_var = None

        self.logger = Balancer.default_logger

        if not self.logger.hasHandlers():
            if common.debug:
                self.logger.setLevel(logging.DEBUG)
            else:
                self.logger.setLevel(logging.INFO)
            self.logger.addHandler(logging.StreamHandler(sys.stdout))
            self.logger.addHandler(logging.FileHandler("main_out.txt", mode='w+'))

    def postprocess_nodes(self):
        self.nodes.clear()
        self.z3solver = None
        self.total_throughput_var = None

        input_char = ord('A')
        output_idx = 1
        for belt in self.belts:

            if belt.source not in self.nodes:
                self.nodes.append(belt.source)
            if belt.dest not in self.nodes:
                self.nodes.append(belt.dest)

            if self.is_input(belt):
                belt.source.name = str(chr(input_char))
                input_char += 1
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
                self.logger.error(f"Error: {node} has a duplicate in the node list. Nodes:")
                for node in self.nodes:
                    self.logger.error(f"{str(node)} ({hash(node)}) ({id(node)})")
                self.logger.error("same_names:")
                for node in same_names:
                    self.logger.error(f"{str(node)} ({hash(node)}) ({id(node)})")
                raise AssertionError(f"{node} has a duplicate in the node list.")

        nodes_to_remove = []
        belts_to_remove = []
        for node in self.nodes:
            splitter = self.get_splitter(node)
            if len(splitter.get_enabled_inputs()) > 2:
                raise AssertionError(f"Error: {node} has more than 2 inputs. This balancer is illegal.")
            if len(splitter.get_enabled_outputs()) > 2:
                raise AssertionError(f"Error: {node} has more than 2 outputs. This balancer is illegal.")

            outputs = splitter.get_enabled_outputs()
            if len(outputs) == 2 and outputs[0].dest == outputs[1].dest:
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
    def combine_endtoend(upstream: Balancer, downstream: Balancer | NoneType = None) -> Balancer:

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

        ans.postprocess_nodes()
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
        self.logger.debug("populating z3 model of balancer...")

        for belt in self.belts:
            self.logger.debug(f"Belt {belt}")

            self.z3solver.assert_and_track(belt.supply_var() <= Belt.max_belt_val, f"{str(belt)}_s_lte_10")
            self.z3solver.assert_and_track(belt.supply_var() >= 0, f"{str(belt)}_s_gte_0")
            self.z3solver.assert_and_track(belt.demand_var() <= Belt.max_belt_val, f"{str(belt)}_d_lte_10")
            self.z3solver.assert_and_track(belt.demand_var() >= 0, f"{str(belt)}_d_gte_0")

        for node in self.nodes:
            try:
                splitter = self.get_splitter(node)
            except ArgumentError:
                self.logger.debug(f"Node {node} could not access splitter")
                continue

            self.logger.debug(f"Splitter {splitter}")

            if splitter.is_input_proxy() or splitter.is_output_proxy():
                self.logger.debug(f"Proxy, skipping...")
                continue

            enabled_inputs = splitter.get_enabled_inputs()
            enabled_outputs = splitter.get_enabled_outputs()

            num_enabled_inputs = len(enabled_inputs)
            num_enabled_outputs = len(enabled_outputs)

            input_demand_vars = [belt.demand_var() for belt in enabled_inputs]
            output_demand_vars = [belt.demand_var() for belt in enabled_outputs]
            total_output_demand_var = z3.Sum(output_demand_vars)
            self.logger.debug(f"Adding: {str(splitter)}_d_io_eq")
            self.z3solver.assert_and_track(
                z3.Sum(input_demand_vars) == common.z3realMin(total_output_demand_var, num_enabled_inputs*Belt.max_belt_val),
                f"{str(splitter)}_d_io_eq")

            input_supply_vars = [belt.supply_var() for belt in enabled_inputs]
            output_supply_vars = [belt.supply_var() for belt in enabled_outputs]
            total_input_supply_var = z3.Sum(input_supply_vars)
            self.z3solver.assert_and_track(
                common.z3realMin(total_input_supply_var, num_enabled_outputs*Belt.max_belt_val) == z3.Sum(output_supply_vars),
                f"{str(splitter)}_s_io_eq")

            # -------------------------------------------------------------
            # Handle demand of inputs
            # -------------------------------------------------------------

            has_priority_input = any([x.dest_priority for x in enabled_inputs])

            no_backpressure = z3.And(
                z3.If(input_supply_vars[0] == Belt.max_belt_val, input_demand_vars[0] == Belt.max_belt_val,
                      input_demand_vars[0] > input_supply_vars[0]),
                z3.If(input_supply_vars[-1] == Belt.max_belt_val, input_demand_vars[-1] == Belt.max_belt_val,
                      input_demand_vars[-1] > input_supply_vars[-1])
            )

            if has_priority_input:
                self.logger.debug(f"Has priority input")

                # overall equation:
                # if total_demand > total_supply:
                #   both demands > their supply
                # else
                #   priority input demand = min(total demand, pri supply)
                #   (demand of other input derivable from splitter _d_io_eq rule)

                priority_belt = next(x for x in enabled_inputs if x.dest_priority)
                priority_belt_demand_var = priority_belt.demand_var()
                priority_belt_supply_var = priority_belt.supply_var()

                self.z3solver.assert_and_track(z3.If(
                    total_output_demand_var > total_input_supply_var,
                    no_backpressure,
                    priority_belt_demand_var == common.z3realMin(total_output_demand_var, priority_belt_supply_var)
                ), f"{str(splitter)}_pri_i")

            else:
                self.logger.debug(f"No priority input")

                # overall equation:
                # if min_supply * num_enabled_inputs >= total_demand:
                #   apply backpressure evenly
                # elif total_supply > total_demand:
                #   (belt with min input)'s demand = its supply
                #   other belt demand = total demand - former's demand
                # else (no backpressure)
                #   both demands > their supply

                min_input_supply_var = common.z3realMin(input_supply_vars[0], input_supply_vars[-1])

                uneven_backpressure = z3.And(
                    input_demand_vars[0] <= input_supply_vars[0],
                    input_demand_vars[-1] <= input_supply_vars[-1],
                    input_demand_vars[0] >= min_input_supply_var,
                    input_demand_vars[-1] >= min_input_supply_var
                )

                uneven_backpressure_cond = z3.If(
                    total_input_supply_var >= total_output_demand_var,
                    uneven_backpressure,
                    # input_demand_vars[0] - input_supply_vars[0] == input_demand_vars[-1] - input_supply_vars[-1]
                    no_backpressure
                )

                to_add = z3.If(
                    min_input_supply_var * num_enabled_inputs >= total_output_demand_var,
                    input_demand_vars[0] == input_demand_vars[-1],
                    uneven_backpressure_cond
                )

                self.logger.debug(f"to_add: {str(to_add)}")

                self.z3solver.assert_and_track(to_add, f"{str(splitter)}_nonpri_i")

            # -------------------------------------------------------------
            # Handle supply of outputs
            # -------------------------------------------------------------

            has_priority_output = any(x.source_priority for x in enabled_outputs)

            both_backpressure = z3.And(
                z3.If(output_demand_vars[0] == Belt.max_belt_val, output_supply_vars[0] == Belt.max_belt_val,
                      output_supply_vars[0] > output_demand_vars[0]),
                z3.If(output_demand_vars[-1] == Belt.max_belt_val, output_supply_vars[-1] == Belt.max_belt_val,
                      output_supply_vars[-1] > output_demand_vars[-1])
            )

            if has_priority_output:
                self.logger.debug("Has priority output")

                # overall equation:
                # if total_supply > total_demand:
                #   both supply > their demands
                # else
                #   priority output supply = min(total supply, pri demand)
                #   (supply of other output derivable from splitter _s_io_eq rule)

                priority_belt = next(x for x in enabled_outputs if x.source_priority)
                priority_belt_supply_var = priority_belt.supply_var()
                priority_belt_demand_var = priority_belt.demand_var()

                self.z3solver.assert_and_track(
                    z3.If(
                        total_input_supply_var > total_output_demand_var,
                        both_backpressure,
                        priority_belt_supply_var == common.z3realMin(total_input_supply_var, priority_belt_demand_var)
                    ),
                    f"{str(splitter)}_pri_o")

            else:
                self.logger.debug("No priority output")

                # overall equation:
                # if min_demand * num_enabled_outputs >= total_supply:
                #   apply supply evenly
                # elif total_supply < total_demand:
                #   (belt with min demand)'s supply = its demand
                #   other belt supply = total supply - former's supply
                # else (backpressure necessary from both outputs)
                #   both supply > their demands

                min_output_demand_var = common.z3realMin(output_demand_vars[0], output_demand_vars[-1])

                uneven_supply = z3.And(
                    output_supply_vars[0] <= output_demand_vars[0],
                    output_supply_vars[-1] <= output_demand_vars[-1],
                    output_supply_vars[0] >= min_output_demand_var,
                    output_supply_vars[-1] >= min_output_demand_var
                )

                uneven_supply_cond = z3.If(
                    total_input_supply_var <= total_output_demand_var,
                    uneven_supply,
                    both_backpressure
                )

                self.z3solver.assert_and_track(z3.If(
                    min_output_demand_var * num_enabled_outputs >= total_input_supply_var,
                    output_supply_vars[0] == output_supply_vars[-1],
                    uneven_supply_cond),
                    f"{str(splitter)}_nonpri_o"
                )

        total_throughput_expr = z3.Sum([x.flow_var() for x in self.get_outputs()])
        self.total_throughput_var = z3.Real("total_throughput")
        self.z3solver.assert_and_track(total_throughput_expr == self.total_throughput_var, "total_throughput_expr")

        self.logger.debug(f"Assertions:")
        for a in self.z3solver.assertions():
            self.logger.debug(a)

        return self.z3solver

    def set_to_model(self):
        solver = self.get_solver()
        model = solver.model()
        for belt in self.belts:
            belt.supply = float(model[belt.supply_var()].as_fraction())
            belt.demand = float(model[belt.demand_var()].as_fraction())

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

    # return -1 if no belts changed or index of belt if one did
    def calc_balance_iter(self, start_idx: int) -> int:
        self.logger.debug(f"calc_balance_iter({start_idx})")

        if start_idx >= len(self.nodes):
            start_idx = 0
            self.logger.debug(f"start_idx={start_idx}")

        idx_order = [x for x in range(start_idx, len(self.nodes))]
        idx_order.extend([x for x in range(0, start_idx)])

        rvrs_idx_order = copy.deepcopy(idx_order)
        rvrs_idx_order.reverse()

        idx_order.extend(rvrs_idx_order)

        changed_node_idxs = set()
        for i in idx_order:
            node = self.nodes[i]
            try:
                if self.get_splitter(node).update_check_output_balance(self.logger):
                    changed_node_idxs.add(i)
                    if common.deep_iteration_debug:
                        break
            except ArgumentError:
                pass

        if len(changed_node_idxs) == 0:
            self.logger.debug("No changed nodes")
            return -1

        self.logger.debug(f"Changed nodes:")
        for i in changed_node_idxs:
            self.logger.debug(f"\t{self.nodes[i]}")

        return list(changed_node_idxs)[0]

    # return -1 if no belts changed or index of belt if one did
    def calc_flow_rate_iter(self, start_idx: int, io_preset: bool = False) -> int:
        self.logger.debug(f"calc_flow_rate_iter({start_idx})")

        if start_idx >= len(self.nodes):
            start_idx = 0
            self.logger.debug(f"start_idx={start_idx}")

        idx_order = [x for x in range(start_idx, len(self.nodes))]
        idx_order.extend([x for x in range(0, start_idx)])

        rvrs_idx_order = copy.deepcopy(idx_order)
        rvrs_idx_order.reverse()

        idx_order.extend(rvrs_idx_order)

        changed_node_idxs = set()
        for i in idx_order:
            node = self.nodes[i]
            try:
                if self.get_splitter(node).update_check_flow_rate(self.logger, io_preset=io_preset):
                    changed_node_idxs.add(i)
                    if common.deep_iteration_debug:
                        break
            except ArgumentError:
                self.logger.debug(f"Splitter for node {node} raised an ArgumentError")

        if len(changed_node_idxs) == 0:
            self.logger.debug("No changed nodes")
            return -1

        self.logger.debug(f"Changed nodes:")
        for i in changed_node_idxs:
            self.logger.debug(f"\t{self.nodes[i]}")

        return list(changed_node_idxs)[0]

    # return True if flow is OK
    # check each splitter for equal in and out flow
    def verify_flow(self) -> bool:
        test_pass = True
        for node in self.nodes:
            try:
                splitter = self.get_splitter(node)

                if splitter.is_input_proxy() or splitter.is_output_proxy():
                    continue

                in_flow = sum(x.flow() for x in splitter.get_enabled_inputs())
                out_flow = sum(x.flow() for x in splitter.get_enabled_outputs())
                if abs(in_flow - out_flow) > common.diff_threshold_verif:
                    print(f"Error: Splitter {splitter} has inequal input and output flow. Input: {in_flow}, Output: {out_flow}")
                    test_pass = False

            except ArgumentError:
                pass
        return test_pass

    def calc_balance(self, io_preset: bool = False) -> None:

        self.logger.debug("calc_balance")

        if not io_preset:
            for belt in self.belts:
                belt.reset()

        iters = 0
        changed_node_idx = -1
        while True:

            iters += 1
            self.logger.debug(f"Trying to converge flow rate, iteration {iters}")

            changed_node_idx = self.calc_flow_rate_iter(changed_node_idx + 1, io_preset=io_preset)

            if common.deep_iteration_debug:
                self.render(f"Flow_Iter{iters}")

            self.logger.debug(f"changed_node_idx = {changed_node_idx}")
            if changed_node_idx < 0:
                break

            if iters > common.max_iters:
                raise Exception(f"Balancer failed to converge flow rate after {iters} iterations")

        self.logger.debug(f"Flow rate took {iters} iterations")

        if not self.verify_flow():
            self.render(f"Fail")
            raise Exception("Flow check failed")

        iters = 0
        changed_node_idx = -1
        while True:

            iters += 1
            self.logger.debug(f"Trying to balance, iteration {iters}")

            changed_node_idx = self.calc_balance_iter(changed_node_idx + 1)

            if common.deep_iteration_debug:
                self.render(f"Bal_Iter{iters}")

            self.logger.debug(f"changed_node_idx = {changed_node_idx}")
            if changed_node_idx < 0:
                break

            if iters > common.max_iters:
                raise Exception(f"Balancer failed to converge balance after {iters} iterations")

        self.logger.debug(f"Balance took {iters} iterations")

    def render_all_methods(self, name: str = default_img_filename) -> None:
        for cs in ColorStrategy:
            self.render(f"{name} ({ColorStrategy(cs)})", cs)

    def render(self, name: str = default_img_filename, color_strat: ColorStrategy = ColorStrategy.PRIORITY) -> None:
        g = Digraph(engine='dot', node_attr={'shape': 'rect', 'height': '0.4', 'width': '0.5'},
                    graph_attr={'rankdir': 'BT'})

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
        g.render(name, format='png', view=(name == Balancer.default_img_filename), cleanup=True)

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