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
        return sum([x.demand for x in self.outputs])

    def get_input_demand(self) -> float:
        return sum([x.demand for x in self.inputs])

    def is_input_proxy(self):
        return len(self.inputs) == 0

    def is_output_proxy(self):
        return len(self.outputs) == 0

    # return True if input demands changed
    def update_check_input_demand(self) -> bool:

        common.debug_print(f"update_check_input_demand, Splitter: {self}")

        if self.is_input_proxy():
            common.debug_print(f"This splitter is an input proxy")
            return False

        is_changed = False

        old_demands = [x.demand for x in self.inputs if x.enabled]

        output_demand = self.get_output_demand()
        input_demand = self.get_input_demand()

        enabled_outputs = [x for x in self.outputs if x.enabled]

        if self.is_output_proxy():
            assert len(self.inputs) == 1
            common.debug_print(f"Output splitter: setting belt {self.inputs[0]} to 1")
            self.inputs[0].demand = 1
        elif abs(output_demand - input_demand) > common.diff_threshold_iter:

            enabled_inputs = [x for x in self.inputs if x.enabled]
            priority_input_belts = [x for x in enabled_inputs if x.dest_priority]
            has_priority_input = len(priority_input_belts) > 0

            if has_priority_input:
                priority_input_belt = priority_input_belts[0]
                priority_input_belt.demand = min(output_demand, 1)

                common.debug_print(f"{self.node} has priority input")
                common.debug_print(f"Set {priority_input_belt} demand to {priority_input_belt.demand}")

                non_priority_inputs = [x for x in enabled_inputs if not x.dest_priority]
                if len(non_priority_inputs) > 0:
                    non_priority_input = [x for x in enabled_inputs if not x.dest_priority][0]
                    remaining_demand = output_demand - 1
                    non_priority_input.demand = max(remaining_demand, 0)
                    common.debug_print(f"Set {non_priority_input} demand to {non_priority_input.demand}")
            else:
                new_demand = min(output_demand / len(self.inputs), 1)
                common.debug_print(f"{self.node}: output demand ({output_demand}) != input demand ({input_demand}), setting input demands each to {new_demand}")
                for belt in self.inputs:
                    belt.demand = new_demand

        new_demands = [x.demand for x in self.inputs if x.enabled]
        for i in range(len(new_demands)):
            new_demand = new_demands[i]
            old_demand = old_demands[i]
            if abs(new_demand - old_demand) > common.diff_threshold_iter:
                is_changed = True

        return is_changed

    def update_check_output_balance(self) -> bool:

        is_changed = False

        # record old balances for change detection
        old_balances = [copy.deepcopy(x.supply_balance) for x in self.outputs if x.enabled]
        num_enabled_outputs = len(old_balances)

        if num_enabled_outputs == 0:
            return False

        self.update_output_balance()

        # check for any changes in balance
        new_balances = [x.supply_balance for x in self.outputs if x.enabled]
        for i in range(len(new_balances)):
            new_balance = new_balances[i]
            old_balance = old_balances[i]
            for name, frac in new_balance.items():
                if name not in old_balance or abs(old_balance[name] - frac) > common.diff_threshold_iter:
                    is_changed = True
            for name in old_balance.keys():
                if name not in new_balance:
                    is_changed = True

        return is_changed

    def update_output_balance(self):

        num_enabled_outputs = len([x for x in self.outputs if x.enabled])

        common.debug_print(f"update_output_balance, Splitter: {self}")

        if self.is_input_proxy():
            # represents an input, just set it to itself
            assert len(self.outputs) == 1
            self.outputs[0].supply_balance[self.node] = self.outputs[0].demand
            common.debug_print(f"Input proxy, setting {self.node} to demand ({self.outputs[0].demand})")
            return

        input_balances = [x for x in self.inputs if x.enabled]

        total_supply_balance = self.get_total_supply_balance()

        common.debug_print("Total supply balance:")
        for k, v in total_supply_balance.items():
            common.debug_print(f"\t{k}: {v}")

        # sum of magnitude of all balances coming into splitter
        total_supply = sum(total_supply_balance.values())
        common.debug_print(f"Total supply: {total_supply}")

        if len(input_balances) == 0 or total_supply == 0:
            # no supply to work with, just wipe the record and move on
            for belt in self.outputs:
                belt.supply_balance.clear()
            common.debug_print(f"No supply available, clearing output balances")
            return

        common.debug_print("Balancing inputs:")
        for belt in self.inputs:
            common.debug_print(f"\t{belt.get_label()}")

        # minimum of output belt demands--input supply will be split evenly up to this magnitude
        min_demand = min([x.demand if x.enabled else 0 for x in self.outputs])

        # no more than 1 priority output please
        assert len([x for x in self.outputs if x.enabled and x.source_priority]) < 2

        has_priority_output = any([x.source_priority for x in self.outputs])

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
        for belt in self.outputs:
            if not belt.enabled:
                continue
            belt.supply_balance = {k: v * min_demand_scaling_factor for k, v in total_supply_balance.items()}

        common.debug_print(f"After filling belts to min demand: ")
        for belt in self.outputs:
            if not belt.enabled:
                continue
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
        for belt in self.outputs:

            if not belt.enabled:
                continue
            if belt.demand <= min_demand:
                continue
            if has_priority_output and not belt.source_priority:
                continue

            common.debug_print(f"Belt {belt} has higher demand (or priority): {belt.demand}")

            total_supply_balance = belt.fill_with(total_supply_balance)

        non_priority_outputs = [x for x in self.outputs if x.enabled and not x.source_priority]
        if has_priority_output and len(non_priority_outputs) > 0:
            total_supply_balance = non_priority_outputs[0].fill_with(total_supply_balance)


    def get_total_supply_balance(self) -> dict:
        # calculate the sum of the input belt balances as a dict

        ans = dict()

        enabled_inputs = [x for x in self.inputs if x.enabled]
        priority_input_belts = [x for x in enabled_inputs if x.dest_priority]
        has_priority_input = len(priority_input_belts) > 0

        # no more than 1 priority input belt please
        assert len(priority_input_belts) < 2

        if has_priority_input:

            common.debug_print(f"This splitter has a priority input")

            priority_input_belt = priority_input_belts[0]
            priority_supply = priority_input_belt.get_strength()
            downstream_demand = sum([x.demand for x in self.outputs if x.enabled])

            if downstream_demand < priority_supply:
                common.debug_print(f"Downstream demand ({downstream_demand}) < priority_supply ({priority_supply})")
                ratio = downstream_demand / priority_supply
                common.debug_print(f"Ratio: {ratio}")
                return {k: v*ratio for k, v in priority_input_belt.supply_balance.items()}

            ans = copy.deepcopy(priority_input_belt.supply_balance)

            if len(enabled_inputs) == 1:
                # the priority belt was the only one.
                common.debug_print(f"Priority input was alone")
                return ans

            other_belt = [x for x in enabled_inputs if not x.dest_priority][0]
            additional_demand = downstream_demand - priority_supply
            other_supply_magnitude = other_belt.get_strength()

            common.debug_print(f"Adding belt {other_belt.get_label()}")

            if other_supply_magnitude < additional_demand:
                ratio = 1
            elif additional_demand == 0:
                ratio = 0
            else:
                ratio = additional_demand / other_supply_magnitude

            common.debug_print(f"Ratio: {ratio}")

            ans = Belt.merge_balances(ans, 1, other_belt.supply_balance, ratio)
            return ans

        common.debug_print(f"This splitter has no priority input")

        for belt in enabled_inputs:
            common.debug_print(f"Adding belt {belt.get_label()}")
            ans = Belt.merge_balances_eq(ans, belt.supply_balance)

        common.debug_print("total_supply_balance:")
        for k, v in ans.items():
            common.debug_print(f"\t{k}: {v}")
        return ans