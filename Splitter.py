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
        sources = ", ".join([str(x.source) for x in self.inputs])
        dests = ", ".join([str(x.dest) for x in self.outputs])
        return f"{sources} --> {dests}"

    def get_output_demand(self) -> float:
        return sum([x.demand for x in self.outputs])

    def get_input_demand(self) -> float:
        return sum([x.demand for x in self.inputs])

    # return True if input demands changed
    def update_check_input_demand(self) -> bool:

        common.debug_print("update_check_input_demand")
        common.debug_print(f"Splitter: {self}")

        is_changed = False

        old_demands = [x.demand for x in self.inputs if x.enabled]

        output_demand = self.get_output_demand()
        input_demand = self.get_input_demand()

        if output_demand == 0:
            assert len(self.inputs) == 1
            common.debug_print(f"Output splitter: setting belt {self.inputs[0]} to 1")
            self.inputs[0].demand = 1
        elif output_demand < input_demand:
            new_demand = output_demand / len(self.inputs)
            # print(f"{self.node}: output demand ({output_demand}) < input demand ({input_demand}), setting input demands each to {new_demand}")
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

        if len(self.inputs) == 0:
            # represents an input, just set it to itself
            assert len(self.outputs) == 1
            self.outputs[0].supply_balance[self.node] = self.outputs[0].demand
            common.debug_print(f"No inputs, setting {self.node} to demand ({self.outputs[0].demand})")
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
        for belt in self.inputs:
            if not belt.enabled:
                continue
            print(f"Adding belt {belt.get_label()}")
            ans = {i: ans.get(i, 0) + belt.supply_balance.get(i, 0)
                   for i in set(ans).union(belt.supply_balance)}

        print("total_supply_balance:")
        for k, v in ans.items():
            print(f"\t{k}: {v}")
        return ans