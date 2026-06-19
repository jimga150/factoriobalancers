import copy

import common
from Balance import Balance
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

    def update_check_flow_rate(self, new_splitter: Splitter):

        old_enabled_inputs = self.get_enabled_inputs()
        old_enabled_outputs = self.get_enabled_outputs()

        old_demands = [x.demand for x in old_enabled_inputs]
        old_supplies = [x.supply for x in old_enabled_outputs]

        common.debug_print(f"------------------------------------------------")
        common.debug_print(f"update_check_flow_rate, Splitter: {self}")
        common.debug_print(f"Inputs:")
        for in_belt in old_enabled_inputs:
            common.debug_print(f"\tfrom {in_belt.source}:")
            common.debug_print(f"\t\t{in_belt.get_label()}")
        common.debug_print(f"Outputs:")
        for out_belt in old_enabled_outputs:
            common.debug_print(f"\tto {out_belt.dest}:")
            common.debug_print(f"\t\t{out_belt.get_label()}")
        common.debug_print(f"------------------------------------------------")

        self.update_flow_rate(new_splitter)

        common.debug_print(f"------------------------------------------------")
        common.debug_print(f"Done with update_check_flow_rate, Splitter: {self}")
        common.debug_print(f"Inputs:")
        for in_belt in old_enabled_inputs:
            common.debug_print(f"\tfrom {in_belt.source}:")
            common.debug_print(f"\t\t{in_belt.get_label()}")
        common.debug_print(f"Outputs:")
        for out_belt in old_enabled_outputs:
            common.debug_print(f"\tto {out_belt.dest}:")
            common.debug_print(f"\t\t{out_belt.get_label()}")
        common.debug_print(f"------------------------------------------------")

        new_enabled_inputs = new_splitter.get_enabled_inputs()
        new_enabled_outputs = new_splitter.get_enabled_outputs()

        new_demands = [x.demand for x in new_enabled_inputs]
        new_supplies = [x.supply for x in new_enabled_outputs]

        is_changed = False

        for i in range(len(new_demands)):
            new_demand = new_demands[i]
            old_demand = old_demands[i]
            if abs(new_demand - old_demand) > common.diff_threshold_iter:
                common.debug_print(f"\tchange: demand of {new_enabled_inputs[i]} changed from {old_demand} to {new_demand}")
                if common.debug:
                    is_changed = True
                else:
                    return True

        for i in range(len(new_supplies)):
            new_supply = new_supplies[i]
            old_supply = old_supplies[i]
            if abs(new_supply - old_supply) > common.diff_threshold_iter:
                common.debug_print(f"\tchange: demand of {new_enabled_outputs[i]} changed from {old_supply} to {new_supply}")
                if common.debug:
                    is_changed = True
                else:
                    return True

        return is_changed

    def update_flow_rate(self, new_splitter: Splitter):

        # -------------------------------------------------------------
        # Weeding out base cases
        # -------------------------------------------------------------

        if self.is_input_proxy():
            # represents an input, just set it to itself
            assert len(self.outputs) == 1
            new_splitter.outputs[0].supply = 1
            common.debug_print(f"Input proxy, setting {self.node} to demand ({self.outputs[0].demand})")
            return

        if self.is_output_proxy():
            assert len(self.inputs) == 1
            common.debug_print(f"Output proxy: setting demand of {self.inputs[0]} to 1")
            new_splitter.inputs[0].demand = 1
            return

        enabled_inputs = new_splitter.get_enabled_inputs()
        enabled_outputs = new_splitter.get_enabled_outputs()

        num_enabled_inputs = len(enabled_inputs)
        num_enabled_outputs = len(enabled_outputs)

        if num_enabled_inputs == 0:
            common.debug_print(f"No enabled inputs, skipping")
            return

        for belt in enabled_inputs:
            assert belt.demand >= 0

        for belt in enabled_outputs:
            assert belt.demand >= 0

        # -------------------------------------------------------------
        # Calculate demand of inputs
        # -------------------------------------------------------------

        total_demand = sum([x.demand for x in enabled_outputs])

        supplies = [x.supply for x in enabled_inputs]

        min_supply = min(supplies)
        total_supply = sum(supplies)

        has_priority_input = any([x.dest_priority for x in enabled_inputs])

        if has_priority_input:
            common.debug_print(f"Has priority input")
            priority_belt = next(x for x in enabled_inputs if x.dest_priority)
            priority_belt.demand = min(total_demand, 1)
            if num_enabled_inputs > 1:
                assert num_enabled_inputs == 2
                non_priority_belt = next(x for x in enabled_inputs if not x.dest_priority)
                non_priority_belt.demand = min(total_demand - priority_belt.supply, 1)
                if non_priority_belt.demand < 0:
                    non_priority_belt.demand = 0
        else:
            common.debug_print(f"No priority input")
            if min_supply * num_enabled_inputs >= total_demand:
                common.debug_print(f"Applying backpressure evenly to inputs")
                for belt in enabled_inputs:
                    belt.demand = total_demand / num_enabled_inputs
            elif total_supply > total_demand:
                assert num_enabled_inputs == 2
                common.debug_print(f"Applying backpressure to higher throughput belt to meet demand limit")
                min_supply_belt = next(x for x in enabled_inputs if x.supply == min_supply)
                max_supply_belt = next(x for x in enabled_inputs if x != min_supply_belt)
                oversupply = total_supply - total_demand
                max_supply_belt.demand = max_supply_belt.supply - oversupply
                min_supply_belt.demand = min_supply_belt.supply
            else:
                common.debug_print(f"Relaxing backpressure")

                demand_slack = total_demand - total_supply

                # apply demand evenly, letting out slack for
                for belt in enabled_inputs:
                    belt.demand = belt.supply

                common.debug_print(f"Step 1:")
                for in_belt in enabled_inputs:
                    common.debug_print(f"\tfrom {in_belt.source}: {in_belt.get_label()}")

                # attempt to add slack evenly to inputs, capping demand at 1
                remaining_demand_slack = 0
                for belt in enabled_inputs:
                    to_add = demand_slack / num_enabled_inputs
                    belt.demand += to_add
                    if belt.demand > 1:
                        remaining_demand_slack += belt.demand - 1
                        belt.demand = 1

                # take slack that wasn't added to capped inputs and apply it to other input as available
                # this only works because there's at most 2 inputs,
                # so 2 iterations of this process is all that is necessary
                assert num_enabled_inputs <= 2
                for belt in enabled_inputs:
                    if belt.demand < 1:
                        belt.demand = min(1, belt.demand + remaining_demand_slack)
                        break

        common.debug_print(f"After applying backpressure:")
        for in_belt in enabled_inputs:
            common.debug_print(f"\tfrom {in_belt.source}: {in_belt.get_label()}")

        # -------------------------------------------------------------
        # Calculate supply of outputs
        # -------------------------------------------------------------

        priority_outputs = [x for x in enabled_outputs if x.source_priority]
        nonpriority_outputs = [x for x in enabled_outputs if not x.source_priority]

        has_priority_output = len(priority_outputs) > 0

        # no more than 1 priority output please
        assert len(priority_outputs) < 2

        if has_priority_output:
            common.debug_print("Has priority output")
            priority_output = priority_outputs[0]
            priority_output.supply = min(1, total_supply)
            if len(nonpriority_outputs) > 0:
                nonpriority_output = nonpriority_outputs[0]
                nonpriority_output.supply = total_supply - priority_output.supply
        else:
            common.debug_print("No priority output")
            oversupplies = dict()
            for belt in enabled_outputs:
                belt.supply = min(1, total_supply / num_enabled_outputs)
                oversupplies[belt] = max(0, belt.supply - belt.demand)

            for belt in enabled_outputs:
                other_oversupplies = sum(v for k, v in oversupplies.items() if k != belt)
                belt.supply = min(1, belt.supply + other_oversupplies)

        common.debug_print(f"After filling output supplies: ")
        for belt in enabled_outputs:
            common.debug_print(belt.get_label())

        return

    def update_check_output_balance(self) -> bool:

        enabled_inputs = self.get_enabled_inputs()
        enabled_outputs = self.get_enabled_outputs()

        # record old balances for change detection
        old_balances = [copy.deepcopy(x.balance) for x in enabled_outputs]

        common.debug_print(f"------------------------------------------------")
        common.debug_print(f"update_output_balance, Splitter: {self}")
        common.debug_print(f"Inputs:")
        for in_belt in enabled_inputs:
            common.debug_print(f"\tfrom {in_belt.source}:")
            common.debug_print(f"\t\t{in_belt.get_label()}")
        common.debug_print(f"Outputs:")
        for out_belt in enabled_outputs:
            common.debug_print(f"\tto {out_belt.dest}:")
            common.debug_print(f"\t\t{out_belt.get_label()}")
        common.debug_print(f"------------------------------------------------")

        self.update_output_balance()

        common.debug_print(f"------------------------------------------------")
        common.debug_print(f"Done with update_output_balance, Splitter: {self}")
        common.debug_print(f"Inputs:")
        for in_belt in enabled_inputs:
            common.debug_print(f"\tfrom {in_belt.source}:")
            common.debug_print(f"\t\t{in_belt.get_label()}")
        common.debug_print(f"Outputs:")
        for out_belt in enabled_outputs:
            common.debug_print(f"\tto {out_belt.dest}:")
            common.debug_print(f"\t\t{out_belt.get_label()}")
        common.debug_print(f"------------------------------------------------")

        # check for any changes in balance

        new_balances = [x.balance for x in enabled_outputs]

        is_changed = False

        for i in range(len(new_balances)):
            new_balance = new_balances[i]
            old_balance = old_balances[i]
            for name, frac in new_balance.items():
                if name not in old_balance:
                    common.debug_print(f"\tchange: {name} added to {enabled_outputs[i]}")
                    if common.debug:
                        is_changed = True
                    else:
                        return True
                elif abs(old_balance[name] - frac) > common.diff_threshold_iter:
                    common.debug_print(f"\tchange: {name} in {enabled_outputs[i]} changed from {old_balance[name]} to {frac}")
                    if common.debug:
                        is_changed = True
                    else:
                        return True
            for name in old_balance.keys():
                if name not in new_balance:
                    common.debug_print(f"\tchange: {name} removed from {enabled_outputs[i]}")
                    if common.debug:
                        is_changed = True
                    else:
                        return True

        return is_changed

    # apply input supply to outputs, and apply output demand to inputs based on actual flow rate
    def update_output_balance(self):

        if self.is_input_proxy():
            # represents an input, just set it to itself
            assert len(self.outputs) == 1
            self.outputs[0].balance[self.node] = self.outputs[0].flow()
            common.debug_print(f"Input proxy, setting {self.node} to demand ({self.outputs[0].demand})")
            return

        if self.is_output_proxy():
            assert len(self.inputs) == 1
            common.debug_print(f"Output proxy, skipping")
            return

        enabled_inputs = self.get_enabled_inputs()
        enabled_outputs = self.get_enabled_outputs()

        if len(enabled_inputs) == 0:
            common.debug_print(f"No enabled inputs, skipping")
            return

        total_supply_balance = self.get_total_supply_balance()
        tsb_flow = total_supply_balance.magnitude()

        common.debug_print(f"Total supply balance: {total_supply_balance} ({tsb_flow})")

        if tsb_flow == 0:
            common.debug_print(f"Supply balance is 0, skipping")
            return

        for belt in enabled_outputs:
            ratio = belt.flow() / tsb_flow
            belt.balance = total_supply_balance * ratio

        common.debug_print(f"after applying input balance to outputs:")
        for belt in enabled_outputs:
            common.debug_print(f"\tto {belt.dest}: {belt.get_label()}")

        return

    def get_total_supply_balance(self) -> Balance:
        # calculate the sum of the input belt balances as a dict
        balance = Balance()

        for belt in self.get_enabled_inputs():
            common.debug_print(f"Adding belt {belt.get_label()}")
            balance += belt.balance

        return balance
