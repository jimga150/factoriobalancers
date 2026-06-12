import copy

import common
from Belt import Belt

class Splitter:

    def __init__(self, inputs: list[Belt], outputs: list[Belt]):
        self.inputs = inputs
        self.outputs = outputs

        if len(self.inputs) > 0:
            self.node = self.inputs[0].dest
        else:
            assert len(self.outputs) > 0
            self.node = self.outputs[0].source

        for belt in self.outputs:
            assert belt.source == self.node

        for node in self.inputs:
            assert node.dest == self.node

    def __str__(self):
        return str(self.node)

    def get_output_demand(self) -> float:
        return sum([x.demand for x in self.get_enabled_outputs()])

    def get_input_demand(self) -> float:
        return sum([x.demand for x in self.get_enabled_outputs()])

    def is_input_proxy(self):
        return len(self.inputs) == 0

    def is_output_proxy(self):
        return len(self.outputs) == 0

    def get_enabled_inputs(self) -> list[Belt]:
        return [x for x in self.inputs if x.enabled]

    def get_enabled_outputs(self) -> list[Belt]:
        return [x for x in self.outputs if x.enabled]

    def update_check_output_balance(self) -> bool:

        # record old balances for change detection
        old_balances = [copy.deepcopy(x.supply_balance) for x in self.outputs if x.enabled]
        old_demands = [x.demand for x in self.inputs if x.enabled]

        self.update_output_balance()

        # check for any changes in balance
        new_balances = [x.supply_balance for x in self.outputs if x.enabled]
        for i in range(len(new_balances)):
            new_balance = new_balances[i]
            old_balance = old_balances[i]
            for name, frac in new_balance.items():
                if name not in old_balance or abs(old_balance[name] - frac) > common.diff_threshold_iter:
                    return True
            for name in old_balance.keys():
                if name not in new_balance:
                    return True

        # check for any changes in demand
        new_demands = [x.demand for x in self.inputs if x.enabled]
        for i in range(len(new_demands)):
            new_demand = new_demands[i]
            old_demand = old_demands[i]
            if abs(new_demand - old_demand) > common.diff_threshold_iter:
                return True

        return False

    # apply input supply to outputs, and apply output demand to inputs based on actual flow rate
    def update_output_balance(self):

        enabled_inputs = [x for x in self.inputs if x.enabled]
        enabled_outputs = [x for x in self.outputs if x.enabled]

        num_enabled_outputs = len(enabled_outputs)

        common.debug_print(f"update_output_balance, Splitter: {self}")

        if self.is_input_proxy():
            # represents an input, just set it to itself
            assert len(self.outputs) == 1
            self.outputs[0].supply_balance[self.node] = self.outputs[0].demand
            common.debug_print(f"Input proxy, setting {self.node} to demand ({self.outputs[0].demand})")
            return

        if self.is_output_proxy():
            assert len(self.inputs) == 1
            common.debug_print(f"Output proxy: setting demand of {self.inputs[0]} to 1")
            self.inputs[0].demand = 1
            return

        total_supply_balance = self.get_total_supply_balance()

        common.debug_print("Total supply balance:")
        for k, v in total_supply_balance.items():
            common.debug_print(f"\t{k}: {v}")

        # sum of magnitude of all balances coming into splitter
        total_supply = sum(total_supply_balance.values())
        common.debug_print(f"Total supply: {total_supply}")

        if len(enabled_inputs) == 0 or total_supply == 0:
            # no supply to work with, just wipe the record and move on
            for belt in enabled_outputs:
                belt.supply_balance.clear()
            for belt in enabled_inputs:
                belt.demand = 1 # we're hungry
            common.debug_print(f"No supply available, clearing output balances and setting input demand to 1")
            return

        common.debug_print("Balancing inputs:")
        for belt in enabled_inputs:
            common.debug_print(f"\t{belt.get_label()}")

        # minimum of output belt demands--input supply will be split evenly up to this magnitude
        min_demand = min([x.demand for x in enabled_outputs])

        # no more than 1 priority output please
        assert len([x for x in enabled_outputs if x.source_priority]) < 2

        has_priority_output = any([x.source_priority for x in enabled_outputs])

        if has_priority_output:
            # priority output detected, we're sharing /no/ output
            min_demand = 0

        common.debug_print(f"Min demand: {min_demand}")
        if min_demand * num_enabled_outputs > total_supply:
            min_demand_scaling_factor = 1.0 / num_enabled_outputs
            tsb_scale_factor = 0
        else:
            min_demand_scaling_factor = min_demand / total_supply
            new_total_supply = total_supply - (min_demand * num_enabled_outputs)
            tsb_scale_factor = new_total_supply / total_supply

        common.debug_print(f"Min demand scaling factor: {min_demand_scaling_factor}")
        common.debug_print(f"Total Supply Balance scaling factor: {tsb_scale_factor}")

        # fill all outputs with equal amount of supply
        for belt in enabled_outputs:
            belt.supply_balance = {k: v * min_demand_scaling_factor for k, v in total_supply_balance.items()}

        common.debug_print(f"After filling belts to min demand: ")
        for belt in enabled_outputs:
            common.debug_print(belt.get_label())

        # scale total supply down to represent what hasn't yet been moved to output belts
        total_supply_balance = {k: v * tsb_scale_factor for k, v in total_supply_balance.items()}

        common.debug_print("After scaling down supply:")
        common.debug_print("Total supply balance:")
        for k, v in total_supply_balance.items():
            common.debug_print(f"\t{k}: {v}")

        # sum of magnitude of all balances coming into splitter
        total_supply = sum(total_supply_balance.values())
        common.debug_print(f"Total supply: {total_supply}")

        # if one belt has greater demand, fill that with more supply
        for belt in enabled_outputs:

            if belt.demand <= min_demand:
                continue
            if has_priority_output and not belt.source_priority:
                continue

            common.debug_print(f"Belt {belt} has higher demand (or priority): {belt.demand}")

            total_supply_balance = belt.fill_with(total_supply_balance)

        non_priority_outputs = [x for x in enabled_outputs if not x.source_priority]
        if has_priority_output and len(non_priority_outputs) > 0:
            total_supply_balance = non_priority_outputs[0].fill_with(total_supply_balance)

        common.debug_print("After filling outputs with input supply, this is left over in inputs:")
        for k, v in total_supply_balance.items():
            common.debug_print(f"\t{k}: {v}")

        # represents the amount of backpressure we must exert on the inputs total
        leftover_supply = sum(total_supply_balance.values())
        common.debug_print(f"Leftover supply: {leftover_supply}")

        priority_inputs = [x for x in enabled_inputs if x.dest_priority]
        has_priority_input = len(priority_inputs) > 0
        assert len(priority_inputs) < 2

        non_priority_inputs = [x for x in enabled_inputs if not x.dest_priority]
        assert len(non_priority_inputs) > 0

        if has_priority_input:
            common.debug_print(f"This splitter has a priority input")
            priority_input = priority_inputs[0]
            non_priority_input = non_priority_inputs[0]

            # if the nonpri input doesnt entirely account of the leftover supply
            if non_priority_input.demand < leftover_supply:
                # nix it anyways
                leftover_supply -= non_priority_input.demand
                non_priority_input.demand = 0
            else:
                # this is if the nonpri input would still have supply leftover after the backpressure propagates
                # (so this wont go negative)
                non_priority_input.demand -= leftover_supply
                leftover_supply = 0

            # now apply any remaining backpressure to the priority input
            priority_input.demand -= leftover_supply

            common.debug_print(f"Set nonpriority input demand to {non_priority_input.demand}")
            common.debug_print(f"Set priority input demand to {priority_input.demand}")
            return

        # here, no priority inputs. apply backpressure evenly
        backpressure_per_input = leftover_supply / len(enabled_inputs)
        for belt in enabled_inputs:
            belt.demand -= backpressure_per_input


    def get_total_supply_balance(self) -> dict:
        # calculate the sum of the input belt balances as a dict

        ans = dict()

        enabled_inputs = self.get_enabled_inputs()

        for belt in enabled_inputs:
            # common.debug_print(f"Adding belt {belt.get_label()}")
            ans = Belt.merge_balances_eq(ans, belt.supply_balance)
        return ans